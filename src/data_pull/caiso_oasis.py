"""Source 2: CAISO OASIS wind and solar forecast, report SLD_REN_FCST (benchmark, never used for training).

Pulls market_run_id=DAM (day-ahead forecast) and, as a backup target, market_run_id=ACTUAL.
Every row OASIS returns is kept: all trading hubs, solar and wind, all columns.

OASIS counts requests in Pacific operating days (at most 31 per request), so each request
covers whole operating days, from Pacific midnight to Pacific midnight, one calendar month at
a time. To cover every UTC hour from --start 00:00 to --end 23:00, the first operating day
pulled is the day before --start. Each month's CSV is cached in data/raw/.cache/oasis/<run>/,
so a re-run skips months already on disk. Requests are at least 5 seconds apart.
ACTUAL is requested differently, in overlapping half months (see OVERLAP_RUNS), cached in
data/raw/.cache/oasis/ACTUAL_overlap/.
Output files are gzip-compressed CSV (.csv.gz) to keep the repo small.

Run from the repo root:
    .venv\\Scripts\\python -m src.data_pull.caiso_oasis --start 2024-01-01 --end 2026-10-17
"""
import argparse
import io
import re
import time
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.data_pull.common import (CACHE_DIR, RAW_DIR, PullError, add_date_args, get_logger,
                                  http_get, write_bytes_atomic, write_csv)

URL = "https://oasis.caiso.com/oasisapi/SingleZip"
PACIFIC = ZoneInfo("America/Los_Angeles")
PAUSE = 5  # seconds between requests, per the brief
CACHE = CACHE_DIR / "oasis"
OUT_NAMES = {"DAM": "caiso_dam_solar_forecast", "ACTUAL": "caiso_actual_solar"}
# For ACTUAL, OASIS omits the first hour of a request that starts at Pacific midnight in winter
# (tested 2026-10-28). These runs are requested in half months that start one operating day
# early (at most 17 days, under the 31-day limit); the extra day is dropped when the file is built.
OVERLAP_RUNS = {"ACTUAL"}
log = get_logger("caiso_oasis")


def utc_midnight(day: pd.Timestamp) -> str:
    """Pacific midnight at the start of an operating day, in OASIS's UTC format."""
    t = pd.Timestamp(day.date(), tz=PACIFIC).tz_convert("UTC")
    return t.strftime("%Y%m%dT%H:%M-0000")


def chunks(first_day: pd.Timestamp, last_day: pd.Timestamp, half_months: bool = False):
    """(first, last) operating days, one calendar month (or half month: 1-15, 16-end) at a time."""
    d = first_day
    while d <= last_day:
        end = d + pd.offsets.MonthEnd(0)
        if half_months and d.day <= 15:
            end = min(end, d.replace(day=15))
        end = min(end, last_day)
        yield d, end
        d = end + pd.Timedelta(days=1)


class NoData(PullError):
    """OASIS error 1000: no data for the selection."""


def fetch(run: str, first: pd.Timestamp, last: pd.Timestamp) -> bytes:
    """The CSV bytes OASIS returns for operating days first..last. Raises PullError on an OASIS error."""
    params = {"queryname": "SLD_REN_FCST", "market_run_id": run, "version": 1, "resultformat": 6,
              "startdatetime": utc_midnight(first),
              "enddatetime": utc_midnight(last + pd.Timedelta(days=1))}
    r = http_get(URL, params=params, logger=log, backoff=10)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    csvs = [n for n in names if n.lower().endswith(".csv")]
    if len(csvs) != 1:
        text = z.read(names[0]).decode("utf-8", "replace") if names else ""
        code = re.search(r"<m:ERR_CODE>(.*?)</", text)
        desc = re.search(r"<m:ERR_DESC>(.*?)</", text)
        err = NoData if code and code.group(1) == "1000" else PullError
        raise err(f"OASIS {run} {first:%Y-%m-%d}..{last:%Y-%m-%d}: no CSV returned "
                  f"(members {names}; error {code and code.group(1)}: {desc and desc.group(1)})")
    return z.read(csvs[0])


def record_nodata(nodata_file: Path, run: str, days: list[str]) -> None:
    """Add (run, day) lines to the no-data list, without duplicates, written atomically."""
    lines = nodata_file.read_text(encoding="utf-8").splitlines() if nodata_file.exists() else []
    merged = list(dict.fromkeys(l for l in lines + [f"{run},{d}" for d in days] if l.strip()))
    write_bytes_atomic(("\n".join(merged) + "\n").encode("utf-8") if merged else b"", nodata_file)


def fetch_by_day(run: str, first: pd.Timestamp, last: pd.Timestamp, nodata_file: Path,
                 overlap: bool = False) -> pd.DataFrame:
    """Fallback when a multi-day request returns error 1000: OASIS rejects the whole window if
    any day in it has no data, so fetch one day at a time and record the empty days.

    With overlap=True each day is requested together with the day before (see OVERLAP_RUNS),
    falling back to the day alone if that pair is refused. Only each requested day's own rows
    are kept, so the day before is never returned twice.
    """
    parts, empty = [], []
    for day in pd.date_range(first, last, freq="D"):
        tries = [(day - pd.Timedelta(days=1), day), (day, day)] if overlap else [(day, day)]
        for i, (a, b) in enumerate(tries):
            try:
                part = pd.read_csv(io.BytesIO(fetch(run, a, b)), dtype=str, keep_default_na=False)
                parts.append(part[part.OPR_DT == f"{day:%Y-%m-%d}"] if overlap else part)
                if overlap and i == 1:
                    log.warning("OASIS %s %s fetched without the day before; its first hour may be missing",
                                run, f"{day:%Y-%m-%d}")
                break
            except NoData:
                time.sleep(PAUSE)
        else:
            empty.append(f"{day:%Y-%m-%d}")
            log.warning("OASIS %s has no data for operating day %s", run, f"{day:%Y-%m-%d}")
        time.sleep(PAUSE)
    record_nodata(nodata_file, run, empty)
    return pd.concat(parts, ignore_index=True) if parts else None


def pull(start: str, end: str, out_dir: Path, runs: list[str]) -> list[Path]:
    first_day = pd.Timestamp(start) - pd.Timedelta(days=1)
    last_day = pd.Timestamp(end)
    paths = []
    for run in runs:
        overlap = run in OVERLAP_RUNS
        cache = CACHE / (f"{run}_overlap" if overlap else run)
        cache.mkdir(parents=True, exist_ok=True)
        parts = []
        for a, b in chunks(first_day, last_day, half_months=overlap):
            req_a = a - pd.Timedelta(days=1) if overlap else a
            f = cache / f"sld_ren_fcst_{run}_{req_a:%Y-%m-%d}_{b:%Y-%m-%d}.csv"
            if f.exists():
                log.info("cached: %s", f.name)
            else:
                try:
                    write_bytes_atomic(fetch(run, req_a, b), f)
                    log.info("fetched %s", f.name)
                except NoData as e:
                    log.warning("%s; retrying one day at a time", e)
                    time.sleep(PAUSE)
                    days = fetch_by_day(run, a, b, CACHE / "nodata_days.csv", overlap=overlap)
                    if days is None:
                        write_bytes_atomic(b"", f)  # every day empty; zero-byte file marks the window as done
                    else:
                        write_csv(days, f)
                    log.info("fetched %s day by day", f.name)
                time.sleep(PAUSE)
            if f.stat().st_size:
                part = pd.read_csv(f, dtype=str, keep_default_na=False)
                if overlap:
                    # keep only this window's own operating days; the day before is the previous window's
                    part = part[(part.OPR_DT >= f"{a:%Y-%m-%d}") & (part.OPR_DT <= f"{b:%Y-%m-%d}")]
                parts.append(part)
        out = pd.concat(parts, ignore_index=True).sort_values(
            ["INTERVALSTARTTIME_GMT", "RENEWABLE_TYPE", "TRADING_HUB"], kind="stable")
        path = out_dir / f"{OUT_NAMES[run]}_{start}_{end}.csv.gz"
        write_csv(out, path)
        log.info("wrote %s: %d rows", path, len(out))
        paths.append(path)
    return paths


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_date_args(p)
    p.add_argument("--out-dir", type=Path, default=RAW_DIR, help="folder for the final CSVs (default data/raw)")
    p.add_argument("--runs", nargs="+", default=["DAM", "ACTUAL"], choices=list(OUT_NAMES))
    a = p.parse_args()
    pull(a.start, a.end, a.out_dir, a.runs)
