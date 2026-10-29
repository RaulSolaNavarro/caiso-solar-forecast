"""Source 5: CAISO wind and solar curtailment.

Two raw files, because granularity and categories differ (Raúl, 2026-10-28):

1. caiso_curtailment_2024-01-01_2025-12-31.csv.gz
   The "Curtailments" sheet of CAISO's Production and Curtailments Data workbooks: 2024 from
   production-and-curtailments-data-2024.xlsx, 2025 from the one-time bulk upload
   production-and-curtailments-data-june-december-2025.xlsx (which, despite its title, covers all
   of 2025). Columns Date, Hour, Interval, Wind Curtailment, Solar Curtailment, Reason exactly as
   stored (5-minute MW; only intervals with curtailment are listed), plus source_file.

2. caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz
   Hourly curtailment by fuel and category from CAISO's Daily Renewable Report, one HTML page per
   operating day, read from the arrays in the page script (two formats: plain lists and
   JSON.parse strings). One row per operating day, hour position and fuel, with hourly MWh and
   hourly maximum MW for six categories, as text exactly as in the page, plus source_url.

Pages are cached in data/raw/.cache/curtailment/html/ and requested at least 2 seconds apart.
The run stops if more than 2% of pages fail, or if CAISO answers 403 or 429.

Run from the repo root:
    .venv\\Scripts\\python -m src.data_pull.caiso_curtailment --start 2024-01-01 --end 2026-10-17
"""
import argparse
import re
import time
from pathlib import Path

import openpyxl
import pandas as pd

from src.data_pull.common import (CACHE_DIR, RAW_DIR, PullError, add_date_args, get_logger, http_get,
                                  write_bytes_atomic, write_csv)

DOCS = "https://www.caiso.com/documents/"
WORKBOOKS = {  # year -> file name on caiso.com
    2024: "production-and-curtailments-data-2024.xlsx",
    2025: "production-and-curtailments-data-june-december-2025.xlsx",
}
WB_COLUMNS = ["Date", "Hour", "Interval", "Wind Curtailment", "Solar Curtailment", "Reason"]
REPORT_START = "2025-06-01"  # first Daily Renewable Report page (2025-05-31 and earlier: HTTP 404)
CATEGORIES = ["econ_local", "econ_system", "ss_local", "ss_system", "oi_local", "oi_system"]
FUELS = ["solar", "wind"]
PAUSE = 2
MAX_FAIL_SHARE = 0.02
CACHE = CACHE_DIR / "curtailment"
log = get_logger("caiso_curtailment")


# ---------- workbooks ----------

def workbook_rows(year: int) -> pd.DataFrame:
    name = WORKBOOKS[year]
    f = CACHE / "xlsx" / name
    if not f.exists():
        r = http_get(DOCS + name, logger=log, retries=3)
        if not r.content.startswith(b"PK"):
            raise PullError(f"{name} is not an Excel file")
        write_bytes_atomic(r.content, f)
        log.info("downloaded %s (%d bytes)", name, len(r.content))
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    rows = list(wb["Curtailments"].iter_rows(values_only=True))
    wb.close()
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    idx = [header.index(c) for c in WB_COLUMNS]
    out = []
    for r in rows[1:]:
        vals = [r[i] if i < len(r) else None for i in idx]
        if all(v is None for v in vals):
            continue
        out.append(["" if v is None else (v.isoformat(sep=" ") if hasattr(v, "isoformat") else str(v)) for v in vals])
    df = pd.DataFrame(out, columns=WB_COLUMNS)
    df["source_file"] = DOCS + name
    log.info("%s: %d curtailment rows", name, len(df))
    return df


# ---------- Daily Renewable Report pages ----------

def page_url(day: pd.Timestamp) -> str:
    return DOCS + f"daily-renewable-report-{day:%b-%d-%Y}.html".lower()


def parse_arrays(html: str) -> dict[str, list[str]]:
    """Every curt_* array in the page script, values as text. Handles both formats seen:
    name = [v, v, ...]   and   name = JSON.parse(["[v,v,...]"])"""
    arrays = {}
    for name, body in re.findall(r"\b(curt_[a-z0-9_]+)\s*=\s*\[([^\]]*)\]", html):
        arrays[name] = [v.strip().strip('"').strip("'") for v in body.split(",") if v.strip()]
    for name, body in re.findall(r"\b(curt_[a-z0-9_]+)\s*=\s*JSON\.parse\(\s*\[?\s*[\"']\[([^\]]*)\][\"']\s*\]?\s*\)", html):
        arrays[name] = [v.strip().strip('"').strip("'") for v in body.split(",") if v.strip()]
    return arrays


def page_date(html: str) -> pd.Timestamp | None:
    m = re.search(r"date_options\s*=\s*\{[^}]*?pointStart:\s*Date\.UTC\((\d+),\s*(\d+),\s*(\d+)\)", html, flags=re.S)
    return pd.Timestamp(int(m.group(1)), int(m.group(2)) + 1, int(m.group(3))) if m else None


def get_page(day: pd.Timestamp) -> str | None:
    """The page HTML (cached), or None if CAISO has no page for this day."""
    f = CACHE / "html" / f"daily-renewable-report-{day:%Y-%m-%d}.html"
    if f.exists():
        return f.read_text(encoding="utf-8")
    try:
        r = http_get(page_url(day), logger=log, retries=3)
    except PullError as e:
        if "HTTP 403" in str(e) or "HTTP 429" in str(e):
            raise PullError(f"CAISO refused the request ({e}); stopping") from None
        if "HTTP 404" in str(e):
            time.sleep(PAUSE)
            return None
        raise
    write_bytes_atomic(r.text.encode("utf-8"), f)
    time.sleep(PAUSE)
    return r.text


def report_rows(day: pd.Timestamp, html: str) -> tuple[pd.DataFrame, dict]:
    arrays = parse_arrays(html)
    names = {(fuel, cat, kind): f"curt_hr_{'tot' if kind == 'mwh' else 'max'}_{fuel}_{cat}_{kind}"
             for fuel in FUELS for cat in CATEGORIES for kind in ("mwh", "mw")}
    missing = [n for n in names.values() if n not in arrays]
    lengths = {n: len(arrays[n]) for n in names.values() if n in arrays}
    pdate = page_date(html)
    status = {"day": f"{day:%Y-%m-%d}", "page_date": f"{pdate:%Y-%m-%d}" if pdate is not None else "",
              "missing_arrays": len(missing), "lengths": sorted(set(lengths.values())),
              "json_parse_format": bool(re.search(r"curt_hr_tot_solar_econ_local_mwh\s*=\s*JSON\.parse", html))}
    if missing:
        return pd.DataFrame(), status
    n = max(lengths.values())
    rows = []
    for fuel in FUELS:
        for h in range(n):
            row = {"operating_date": f"{day:%Y-%m-%d}", "hour": h + 1, "fuel": fuel}
            for cat in CATEGORIES:
                for kind, col in (("mwh", f"{cat}_mwh"), ("mw", f"{cat}_max_mw")):
                    a = arrays[names[(fuel, cat, kind)]]
                    row[col] = a[h] if h < len(a) else ""
            row["source_url"] = page_url(day)
            rows.append(row)
    return pd.DataFrame(rows), status


def pull_reports(start: str, end: str, out_dir: Path) -> Path:
    days = pd.date_range(max(pd.Timestamp(start), pd.Timestamp(REPORT_START)), pd.Timestamp(end), freq="D")
    parts, statuses, failed = [], [], []
    for i, day in enumerate(days):
        html = get_page(day)
        if html is None or "curt_" not in html:
            failed.append(f"{day:%Y-%m-%d}")
            log.warning("no usable Daily Renewable Report for %s", f"{day:%Y-%m-%d}")
        else:
            df, st = report_rows(day, html)
            statuses.append(st)
            if df.empty:
                failed.append(f"{day:%Y-%m-%d}")
                log.warning("%s: %d expected arrays missing", st["day"], st["missing_arrays"])
            else:
                parts.append(df)
                if st["lengths"] != [24] or st["page_date"] != st["day"]:
                    log.warning("%s: array lengths %s, page date %s", st["day"], st["lengths"], st["page_date"])
        if len(failed) > MAX_FAIL_SHARE * len(days):
            raise PullError(f"{len(failed)} of {len(days)} pages failed (more than 2%): {failed}; stopping")
        if (i + 1) % 50 == 0:
            log.info("pages done: %d of %d", i + 1, len(days))
    st = pd.DataFrame(statuses)
    write_csv(st.assign(lengths=st["lengths"].astype(str)), CACHE / "report_status.csv")
    out = pd.concat(parts, ignore_index=True)
    path = out_dir / f"caiso_curtailment_daily_report_{days[0]:%Y-%m-%d}_{days[-1]:%Y-%m-%d}.csv.gz"
    write_csv(out, path)
    log.info("wrote %s: %d rows from %d pages; failed days: %s", path.name, len(out), len(parts), failed or "none")
    return path


def pull_workbooks(start: str, end: str, out_dir: Path) -> Path | None:
    years = [y for y in WORKBOOKS if pd.Timestamp(start).year <= y <= pd.Timestamp(end).year]
    if not years:
        return None
    out = pd.concat([workbook_rows(y) for y in years], ignore_index=True)
    path = out_dir / f"caiso_curtailment_{years[0]}-01-01_{years[-1]}-12-31.csv.gz"
    write_csv(out, path)
    log.info("wrote %s: %d rows", path.name, len(out))
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_date_args(p)
    p.add_argument("--out-dir", type=Path, default=RAW_DIR, help="folder for the final files (default data/raw)")
    p.add_argument("--part", choices=["workbooks", "reports", "both"], default="both")
    a = p.parse_args()
    if a.part in ("workbooks", "both"):
        pull_workbooks(a.start, a.end, a.out_dir)
    if a.part in ("reports", "both"):
        pull_reports(a.start, a.end, a.out_dir)
