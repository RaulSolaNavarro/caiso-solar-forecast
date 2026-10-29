"""Source 4: EIA Form 860M monthly generator inventory, CAISO solar generators.

For each month, downloads the monthly workbook (archive URL first, then the current-month URL),
caches it in data/raw/.cache/eia860m/xlsx/, and keeps the rows of the Operating sheet with
Balancing Authority Code = CISO and Energy Source Code = SUN (all solar technologies; the
Technology and Status columns are kept so processing can filter). Every column of the sheet is
kept as text, exactly as read, plus file_month and source_url. Months with no published file
are logged as not available; nothing is estimated for them.

Run from the repo root:
    .venv\\Scripts\\python -m src.data_pull.eia860m --start 2024-01-01 --end 2026-10-17
"""
import argparse
import time
from pathlib import Path

import openpyxl
import pandas as pd

from src.data_pull.common import (CACHE_DIR, RAW_DIR, PullError, add_date_args, get_logger, http_get,
                                  write_bytes_atomic, write_csv)

BASE = "https://www.eia.gov/electricity/data/eia860m"
CACHE = CACHE_DIR / "eia860m" / "xlsx"
OUT_NAME = "eia860m_solar_ciso_capacity_by_month.csv"
SHEET = "Operating"
log = get_logger("eia860m")


def urls(month: pd.Timestamp) -> list[str]:
    name = f"{month:%B}".lower() + f"_generator{month:%Y}.xlsx"
    return [f"{BASE}/archive/xls/{name}", f"{BASE}/xls/{name}"]


def download(month: pd.Timestamp) -> tuple[Path, str] | None:
    """The cached workbook and its URL, or None if EIA has no file for this month."""
    f = CACHE / (f"{month:%B}".lower() + f"_generator{month:%Y}.xlsx")
    src = f.with_suffix(".url")
    if f.exists() and src.exists():
        return f, src.read_text(encoding="utf-8").strip()
    for url in urls(month):
        try:
            r = http_get(url, logger=log, retries=3)
        except PullError as e:
            if "HTTP 404" in str(e):
                continue
            raise
        if not r.content.startswith(b"PK"):  # an .xlsx is a zip file; anything else is an error page
            log.warning("%s did not return an Excel file", url)
            continue
        write_bytes_atomic(r.content, f)
        write_bytes_atomic(url.encode("utf-8"), src)
        log.info("downloaded %s (%d bytes)", url, len(r.content))
        time.sleep(2)
        return f, url
    return None


def read_operating(path: Path) -> pd.DataFrame:
    """The Operating sheet as text, with the header row found by its first cell ('Entity ID')."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[SHEET].iter_rows(values_only=True))
    wb.close()
    hdr = next(i for i, r in enumerate(rows) if r and r[0] == "Entity ID")
    cols = [str(c).strip() for c in rows[hdr]]
    body = [["" if v is None else str(v) for v in r] for r in rows[hdr + 1:]]
    return pd.DataFrame(body, columns=cols)


def pull(start: str, end: str, out_dir: Path) -> Path | None:
    months = pd.date_range(pd.Timestamp(start).replace(day=1), pd.Timestamp(end), freq="MS")
    parts, unavailable = [], []
    for m in months:
        got = download(m)
        if got is None:
            unavailable.append(f"{m:%Y-%m}")
            log.warning("no 860M file published for %s; not estimated", f"{m:%Y-%m}")
            continue
        path, url = got
        op = read_operating(path)
        sel = op[(op["Balancing Authority Code"].str.strip() == "CISO") & (op["Energy Source Code"].str.strip() == "SUN")]
        sel = sel.copy()
        sel.insert(0, "file_month", f"{m:%Y-%m}")
        sel["source_url"] = url
        parts.append(sel)
        log.info("%s: %d CISO solar rows of %d operating rows", f"{m:%Y-%m}", len(sel), len(op))
    if unavailable:
        log.warning("months without a published file: %s", ", ".join(unavailable))
    if not parts:
        return None
    out = pd.concat(parts, ignore_index=True)
    path = out_dir / OUT_NAME
    write_csv(out, path)
    log.info("wrote %s: %d rows", path, len(out))
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_date_args(p)
    p.add_argument("--out-dir", type=Path, default=RAW_DIR, help="folder for the final CSV (default data/raw)")
    a = p.parse_args()
    pull(a.start, a.end, a.out_dir)
