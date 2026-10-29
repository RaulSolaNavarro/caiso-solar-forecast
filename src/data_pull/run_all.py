"""Run every data pull in order for one date range.

Order: EIA hourly (1), CAISO OASIS DAM and ACTUAL (2), EIA 860M (4), weather locations and
Open-Meteo (3, which needs the 860M file for capacity shares), curtailment (5). Every step skips
work already cached under data/raw/.cache/, so re-running is safe.

Run from the repo root:
    .venv\\Scripts\\python -m src.data_pull.run_all --start 2024-01-01 --end 2026-10-17

To test from an empty folder without touching data/raw, set DATA_RAW_DIR first (PowerShell):
    $env:DATA_RAW_DIR = "C:\\path\\to\\empty_folder"; .venv\\Scripts\\python -m src.data_pull.run_all --start 2025-07-01 --end 2025-07-31
"""
import argparse

import pandas as pd

from src.data_pull import caiso_curtailment, caiso_oasis, eia860m, eia_hourly, openmeteo, weather_locations
from src.data_pull.common import RAW_DIR, add_date_args, get_logger

log = get_logger("run_all")


def main(start: str, end: str) -> None:
    log.info("data folder: %s; range %s to %s", RAW_DIR, start, end)
    eia_hourly.pull(start, end, RAW_DIR)
    caiso_oasis.pull(start, end, RAW_DIR, ["DAM", "ACTUAL"])
    eia860m.pull(start, end, RAW_DIR)
    weather_locations.build()
    if pd.Timestamp(end) >= pd.Timestamp(openmeteo.MODEL_START):
        openmeteo.pull(start, end, RAW_DIR / "openmeteo")
    caiso_curtailment.pull_workbooks(start, end, RAW_DIR)
    if pd.Timestamp(end) >= pd.Timestamp(caiso_curtailment.REPORT_START):
        caiso_curtailment.pull_reports(start, end, RAW_DIR)
    log.info("all steps done")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_date_args(p)
    a = p.parse_args()
    main(a.start, a.end)
