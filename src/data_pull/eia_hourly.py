"""Source 1: EIA hourly solar generation for CAISO (respondent CISO, fuel type SUN).

API v2 route electricity/rto/fuel-type-data, hourly (UTC) frequency.
Each month is fetched (paginated, at most 5,000 rows a page) and cached in
data/raw/.cache/eia/, so a re-run skips months already on disk. The final CSV
is the cached months stacked in period order, with every column the API returns.

Run from the repo root:
    .venv\\Scripts\\python -m src.data_pull.eia_hourly --start 2024-01-01 --end 2026-10-17
"""
import argparse
import time
from pathlib import Path

import pandas as pd

from src.data_pull.common import (CACHE_DIR, RAW_DIR, add_date_args, get_key, get_logger,
                                  http_get, write_csv)

URL = "https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/"
PAGE = 5000
CACHE = CACHE_DIR / "eia"
log = get_logger("eia_hourly")


def month_starts(start: str, end: str) -> list[pd.Timestamp]:
    return list(pd.date_range(pd.Timestamp(start).replace(day=1), pd.Timestamp(end), freq="MS"))


def fetch(start_hour: str, end_hour: str, key: str) -> pd.DataFrame:
    """All rows between two UTC hours (inclusive, format YYYY-MM-DDTHH), following pages."""
    rows, offset = [], 0
    while True:
        params = {
            "api_key": key,
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": "CISO",
            "facets[fueltype][]": "SUN",
            "start": start_hour,
            "end": end_hour,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": PAGE,
        }
        body = http_get(URL, params=params, logger=log).json()["response"]
        page = body.get("data", [])
        rows.extend(page)
        total = int(body.get("total", 0))
        offset += len(page)
        if not page or offset >= total:
            break
        time.sleep(1)
    return pd.DataFrame(rows)


def pull(start: str, end: str, out_dir: Path) -> Path:
    key = get_key("EIA_API_KEY")
    CACHE.mkdir(parents=True, exist_ok=True)
    last_day = pd.Timestamp(end)
    parts = []
    for m in month_starts(start, end):
        m_end = min(m + pd.offsets.MonthEnd(0), last_day)
        m_start = max(m, pd.Timestamp(start))
        cache_file = CACHE / f"eia_ciso_sun_{m_start:%Y-%m-%d}_{m_end:%Y-%m-%d}.csv"
        if cache_file.exists():
            log.info("cached: %s", cache_file.name)
        else:
            df = fetch(f"{m_start:%Y-%m-%d}T00", f"{m_end:%Y-%m-%d}T23", key)
            write_csv(df, cache_file)
            log.info("fetched %s: %d rows", cache_file.name, len(df))
            time.sleep(1)
        parts.append(pd.read_csv(cache_file, dtype=str, keep_default_na=False))
    out = pd.concat(parts, ignore_index=True).sort_values("period", kind="stable")
    path = out_dir / f"eia_ciso_solar_hourly_{start}_{end}.csv"
    write_csv(out, path)
    log.info("wrote %s: %d rows", path, len(out))
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_date_args(p)
    p.add_argument("--out-dir", type=Path, default=RAW_DIR, help="folder for the final CSV (default data/raw)")
    a = p.parse_args()
    pull(a.start, a.end, a.out_dir)
