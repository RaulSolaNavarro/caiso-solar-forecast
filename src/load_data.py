"""Load raw CSV files from the project's data/raw folder.

Examples
--------
>>> from src.load_data import read_raw
>>> eia = read_raw("eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv")
>>> wx = read_raw("openmeteo/openmeteo_prev_runs_<location_id>_2024-01-01_2026-10-17.csv.gz")

By default the file is read from GitHub (the repo is public). Pass source="local"
to read from your clone's data/raw folder instead.
"""
from pathlib import Path

import pandas as pd

GITHUB_BASE = "https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/"
LOCAL_BASE = Path(__file__).resolve().parents[1] / "data" / "raw"


def raw_url(relative_path: str, branch: str = "main") -> str:
    """Return the raw GitHub URL for a file under data/raw."""
    base = GITHUB_BASE.replace("/main/", f"/{branch}/")
    return base + relative_path.lstrip("/")


def read_raw(relative_path: str, source: str = "github", branch: str = "main", **kwargs) -> pd.DataFrame:
    """Read a raw CSV (or .csv.gz) into a DataFrame.

    relative_path: path under data/raw, for example "openmeteo/file.csv.gz".
    source: "github" or "local".
    branch: GitHub branch to read from (use your branch name before the pull request is merged).
    kwargs: passed to pandas.read_csv (for example parse_dates=["period"]).
    """
    if source == "github":
        return pd.read_csv(raw_url(relative_path, branch), **kwargs)
    if source == "local":
        return pd.read_csv(LOCAL_BASE / relative_path, **kwargs)
    raise ValueError("source must be 'github' or 'local'")
