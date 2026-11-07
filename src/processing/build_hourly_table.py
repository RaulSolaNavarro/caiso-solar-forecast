"""Build the processed hourly table (FAQ Decision D23) from the raw files.

Run from the repo root:
    python -m src.processing.build_hourly_table

Reads only data/raw/. Never reads a previous output, so it is safe to run again.
Writes data/processed/hourly_table.parquet and data/processed/build_report.txt
(neither is committed) and prints the build report.

One row per UTC hour ending, 2024-03-08 00:00 to 2026-10-17 23:00 UTC: 22,896 rows
(954 days x 24), the same calendar as docs/DATA_HOWTO.md section 3.4. The row count is
asserted after the calendar and after every join.

Decisions applied (docs/DATA_FAQ.md, section 6):
  D14 EIA alignment (shift labels back 1 hour only before 2025-12-02 22:00 UTC)
  D15 negative EIA values set to 0 in the modeling copy `eia_mw`
  D16 deep-night positive EIA values flagged in `eia_deep_night_flag` (not dropped here)
  D17 129-hour weather gap flagged in `wx_gap`
  D18, D19 capacity: EIA 860M monthly nameplate, all CISO (`capacity_mw`); CA only as a check
  D20 daylight: sun above 0 degrees at mid-hour at the capacity-weighted centre
  D21 CAISO totals are NP15 + SP15 + ZP26 Solar only; `AVA_` and wind left out
  D22 the 5 clock-change days have `curt_mwh` null and `curt_excluded` True
  D26 curtailment: workbook to 2025-12-31 except 2025-06-16; daily report for the rest
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUT_TABLE = PROCESSED / "hourly_table.parquet"
OUT_REPORT = PROCESSED / "build_report.txt"

EIA_FILE = RAW / "eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv"
DAM_FILE = RAW / "caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz"
ACT_FILE = RAW / "caiso_actual_solar_2024-01-01_2026-10-17.csv.gz"
LOC_FILE = RAW / "weather_locations.csv"
CAP_FILE = RAW / "eia860m_solar_ciso_capacity_by_month.csv"
CURT_WB_FILE = RAW / "caiso_curtailment_2024-01-01_2025-12-31.csv.gz"
CURT_RP_FILE = RAW / "caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz"
WX_PATTERN = "openmeteo/openmeteo_prev_runs_ecmwf_ifs025_{lid}_2024-03-08_2026-10-17.csv.gz"

LOCAL_TZ = "America/Los_Angeles"
WINDOW_START = pd.Timestamp("2024-03-08 00:00", tz="UTC")   # hour ending, UTC (DATA_HOWTO 3.4)
WINDOW_END = pd.Timestamp("2026-10-17 23:00", tz="UTC")
N_ROWS = 22_896                                             # 954 days x 24
SWITCH = pd.Timestamp("2025-12-02 22:00", tz="UTC")         # D14
TEST_START = pd.Timestamp("2026-04-10", tz=LOCAL_TZ)        # first Pacific day of the locked test set
HUBS = ["NP15", "SP15", "ZP26"]                             # D21
CLOCK_CHANGE_DAYS = ["2024-03-10", "2024-11-03", "2025-03-09", "2025-11-02", "2026-03-08"]  # D22
WORKBOOK_LAST_DAY = "2025-12-31"
WORKBOOK_MISSING_DAY = "2025-06-16"
REPORT_FROM = "2026-01-01"
DEEP_NIGHT_MW, DEEP_NIGHT_ELEV = 100.0, -12.0               # D16


# ----------------------------------------------------------------------------- shared helpers

def load_eia_labels() -> pd.Series:
    """EIA hourly CISO solar as published, indexed by EIA's UTC label (not yet aligned)."""
    e = pd.read_csv(EIA_FILE, usecols=["period", "value"])
    lab = pd.to_datetime(e["period"], format="%Y-%m-%dT%H", utc=True)
    s = pd.Series(e["value"].astype(float).values, index=pd.DatetimeIndex(lab, name="label"), name="eia")
    if s.index.has_duplicates:
        raise ValueError("EIA file has duplicate labels")
    return s.sort_index()


def align_eia(eia: pd.Series | None = None, rule: str = "d14") -> pd.Series:
    """Put EIA on the UTC hour-ending clock. Returns values as published (no clipping).

    rule="d14":     label L before 2025-12-02 22:00 UTC is the hour ending L - 1 h; from then on L.
                    The hour ending 2025-12-02 21:00 UTC has no value (FAQ D14).
    rule="blanket": every label L is the hour ending L - 1 h (the old rule, D11, superseded).
    """
    if eia is None:
        eia = load_eia_labels()
    lab = eia.index
    one_hour = pd.Timedelta(hours=1)
    if rule == "d14":
        he = lab.where(lab >= SWITCH, lab - one_hour)
    elif rule == "blanket":
        he = lab - one_hour
    else:
        raise ValueError(f"unknown rule {rule!r}; use 'd14' or 'blanket'")
    out = pd.Series(eia.values, index=pd.DatetimeIndex(he, name="hour_end_utc"), name="eia_mw_raw")
    if out.index.has_duplicates:
        raise ValueError(f"EIA alignment rule {rule!r} produced duplicate hours")
    return out.sort_index()


def calendar() -> pd.DatetimeIndex:
    return pd.date_range(WINDOW_START, WINDOW_END, freq="h", name="hour_end_utc")


def local_start(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Pacific time at the start of each hour (hour ending minus 1 hour)."""
    return (index - pd.Timedelta(hours=1)).tz_convert(LOCAL_TZ)


def capacity_centre() -> tuple[float, float]:
    """Capacity-weighted centre of the weather points with a share above 0 (D20)."""
    loc = pd.read_csv(LOC_FILE)
    loc = loc[loc["caiso_solar_capacity_share"] > 0]
    w = loc["caiso_solar_capacity_share"]
    return float((loc["latitude"] * w).sum() / w.sum()), float((loc["longitude"] * w).sum() / w.sum())


def git_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "src/processing"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + (" (src/processing has uncommitted changes)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown (git not available)"


class RowCountError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- source loaders

def caiso_total(path: Path, name: str) -> pd.Series:
    """Solar MW summed over NP15 + SP15 + ZP26 per interval end; kept only if all 3 hubs exist (D21)."""
    d = pd.read_csv(path, usecols=["INTERVALENDTIME_GMT", "TRADING_HUB", "RENEWABLE_TYPE", "MW"])
    d = d[(d["RENEWABLE_TYPE"] == "Solar") & d["TRADING_HUB"].isin(HUBS)].copy()
    d["hour_end_utc"] = pd.to_datetime(d["INTERVALENDTIME_GMT"], utc=True)
    by_hub = d.groupby(["hour_end_utc", "TRADING_HUB"])["MW"].sum().unstack()
    return by_hub.sum(axis=1, min_count=len(HUBS)).rename(name)


def weather_average(grid: pd.DatetimeIndex) -> tuple[pd.DataFrame, int]:
    """Capacity-share-weighted mean over the weather points with share above 0.

    Weights are renormalized over the points with a value in each hour, so an hour is null only
    when every point is null. Columns: every *_previous_day2 plus 2 day-1 comparison columns.
    """
    loc = pd.read_csv(LOC_FILE)
    loc = loc[loc["caiso_solar_capacity_share"] > 0]
    num = den = cols = None
    for lid, share in zip(loc["location_id"], loc["caiso_solar_capacity_share"]):
        f = pd.read_csv(RAW / WX_PATTERN.format(lid=lid))
        if cols is None:
            cols = [c for c in f.columns if c.endswith("_previous_day2")]
            cols += ["cloud_cover_previous_day1", "shortwave_radiation_previous_day1"]
        t = pd.to_datetime(f["time_utc"], format="%Y-%m-%dT%H:%M", utc=True)
        v = f[cols].astype(float).set_index(pd.DatetimeIndex(t, name="hour_end_utc"))
        if v.index.has_duplicates or not v.index.equals(grid):
            raise ValueError(f"weather file for {lid} does not cover exactly the calendar hours")
        num = v.fillna(0) * share if num is None else num + v.fillna(0) * share
        den = v.notna() * share if den is None else den + v.notna() * share
    return num / den.where(den > 0), len(loc)


def capacity_by_month() -> tuple[pd.Series, pd.Series]:
    """EIA 860M nameplate MW per file_month: all CISO, and Plant State = CA."""
    cap = pd.read_csv(CAP_FILE, usecols=["file_month", "Nameplate Capacity (MW)", "Plant State"],
                      na_values=[" "], low_memory=False)
    cap["Plant State"] = cap["Plant State"].astype(str).str.strip()
    mw = pd.to_numeric(cap["Nameplate Capacity (MW)"], errors="raise")
    all_ciso = mw.groupby(cap["file_month"]).sum()
    ca = mw[cap["Plant State"] == "CA"].groupby(cap.loc[cap["Plant State"] == "CA", "file_month"]).sum()
    return all_ciso, ca


def curtailment_hourly(grid: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series, list[str]]:
    """Hourly solar curtailment MWh on the calendar (D3, D22, D26).

    Workbook (5-minute MW, only curtailed intervals listed) summed over intervals and both
    reasons per Pacific date and Hour, divided by 12: 2024-01-01 to 2025-12-31 except 2025-06-16.
    Daily report (solar, sum of the 6 *_mwh columns): 2025-06-16 and from 2026-01-01.
    Hour = Pacific hour ending (1 to 24). Hours with no row are 0. The 5 clock-change days are
    null and flagged.
    """
    notes = []
    wb = pd.read_csv(CURT_WB_FILE, usecols=["Date", "Hour", "Solar Curtailment"])
    wb["date"] = wb["Date"].str[:10]
    if (wb["date"] == WORKBOOK_MISSING_DAY).any():
        notes.append(f"workbook unexpectedly has rows on {WORKBOOK_MISSING_DAY}; they are not used")
    wb = wb[(wb["date"] <= WORKBOOK_LAST_DAY) & (wb["date"] != WORKBOOK_MISSING_DAY)]
    wb_h = wb.groupby(["date", "Hour"])["Solar Curtailment"].sum().div(12).rename("mwh").reset_index()
    wb_h["source"] = "workbook"

    rp = pd.read_csv(CURT_RP_FILE)
    rp = rp[rp["fuel"] == "solar"].copy()
    mwh_cols = [c for c in rp.columns if c.endswith("_mwh")]
    if len(mwh_cols) != 6:
        raise ValueError(f"expected 6 *_mwh columns in the daily report, found {mwh_cols}")
    rp["mwh"] = rp[mwh_cols].apply(pd.to_numeric, errors="raise").sum(axis=1)
    rp = rp.rename(columns={"operating_date": "date", "hour": "Hour"})
    rp = rp[(rp["date"] == WORKBOOK_MISSING_DAY) | (rp["date"] >= REPORT_FROM)][["date", "Hour", "mwh"]]
    rp["source"] = "daily report"
    # Every report day we rely on must have 24 hours
    need = [WORKBOOK_MISSING_DAY] + [d.strftime("%Y-%m-%d") for d in
                                     pd.date_range(REPORT_FROM, WINDOW_END.tz_convert(LOCAL_TZ).date())]
    per_day = rp.groupby("date").size().reindex(need, fill_value=0)
    short = per_day[per_day != 24]
    if len(short):
        notes.append("daily report days without exactly 24 rows: " + ", ".join(f"{d} ({n})" for d, n in short.items()))

    c = pd.concat([wb_h, rp], ignore_index=True)
    if not c["Hour"].between(1, 24).all():
        raise ValueError("curtailment Hour outside 1 to 24 outside the clock-change days")
    c = c[~c["date"].isin(CLOCK_CHANGE_DAYS)]                  # D22: those days are set to null below
    local = pd.to_datetime(c["date"]) + pd.to_timedelta(c["Hour"], unit="h")
    c["hour_end_utc"] = local.dt.tz_localize(LOCAL_TZ, ambiguous="raise", nonexistent="raise").dt.tz_convert("UTC")
    by_hour = c.groupby("hour_end_utc")["mwh"].sum()
    if c.duplicated(["hour_end_utc"]).any():
        raise ValueError("2 curtailment rows map to the same UTC hour")

    curt = by_hour.reindex(grid).fillna(0.0).rename("curt_mwh")
    excluded = pd.Series(local_start(grid).strftime("%Y-%m-%d").isin(CLOCK_CHANGE_DAYS), index=grid,
                         name="curt_excluded")
    curt[excluded] = np.nan
    in_window = c[(c["hour_end_utc"] >= grid[0]) & (c["hour_end_utc"] <= grid[-1])]
    notes.append("curtailment rows in the window by source: " +
                 ", ".join(f"{k} {v:,}" for k, v in in_window["source"].value_counts().items()))
    return curt, excluded, notes


# ----------------------------------------------------------------------------- the build

def build_table(rule: str = "d14") -> tuple[pd.DataFrame, list[str]]:
    """Return the hourly table and the build report lines. rule is passed to align_eia."""
    lines: list[str] = []
    steps: list[tuple[str, int]] = []

    def check_rows(df: pd.DataFrame, step: str) -> None:
        steps.append((step, len(df)))
        if len(df) != N_ROWS:
            raise RowCountError(f"after step '{step}' the table has {len(df):,} rows, expected {N_ROWS:,}")
        if df.index.has_duplicates:
            raise RowCountError(f"after step '{step}' the table has duplicate hours")

    # 1. Calendar
    grid = calendar()
    df = pd.DataFrame(index=grid)
    df["local_start"] = local_start(grid)
    check_rows(df, "1 calendar")

    # 2. EIA (D14, D15); the deep-night flag needs the sun, so it is set in step 5
    eia = align_eia(rule=rule)
    df = df.join(eia)
    df["eia_mw"] = df["eia_mw_raw"].clip(lower=0)
    check_rows(df, f"2 EIA ({rule})")

    # 3. CAISO day-ahead and ACTUAL (D21)
    df = df.join(caiso_total(DAM_FILE, "caiso_dam_mw")).join(caiso_total(ACT_FILE, "oasis_actual_mw"))
    check_rows(df, "3 CAISO day-ahead and ACTUAL")

    # 4. Weather (D6, D8, D9, D17)
    wx, n_points = weather_average(grid)
    df = df.join(wx)
    df["wx_gap"] = df["cloud_cover_previous_day2"].isna()
    check_rows(df, f"4 weather ({n_points} points with share > 0)")

    # 5. Daylight (D20) and the deep-night flag (D16)
    lat_c, lon_c = capacity_centre()
    sun = pvlib.solarposition.get_solarposition(grid - pd.Timedelta(minutes=30), lat_c, lon_c)
    df["sun_elev"] = sun["elevation"].values
    df["daylight"] = df["sun_elev"] > 0
    df["eia_deep_night_flag"] = (df["eia_mw_raw"] > DEEP_NIGHT_MW) & (df["sun_elev"] < DEEP_NIGHT_ELEV)
    check_rows(df, "5 daylight")

    # 6. Capacity (D18, D19), by the Pacific month of the hour start
    all_ciso, ca = capacity_by_month()
    month = df["local_start"].dt.strftime("%Y-%m")
    latest = all_ciso.index.max()
    missing = sorted(set(month) - set(all_ciso.index))
    if any(m <= latest for m in missing):
        raise ValueError(f"860M file lacks months inside its range: {missing}")
    month = month.where(month.isin(all_ciso.index), latest)
    df["capacity_mw"] = month.map(all_ciso).values
    df["capacity_ca_mw"] = month.map(ca).values
    check_rows(df, "6 capacity")

    # 7. Curtailment (D3, D22, D26)
    curt, excluded, curt_notes = curtailment_hourly(grid)
    df = df.join(curt).join(excluded)
    check_rows(df, "7 curtailment")

    # 8. Scoring mask
    df["scorable"] = df["daylight"] & df["eia_mw"].notna() & df["caiso_dam_mw"].notna() & ~df["wx_gap"]
    check_rows(df, "8 scoring mask")

    order = ["local_start", "eia_mw_raw", "eia_mw", "eia_deep_night_flag", "caiso_dam_mw", "oasis_actual_mw"]
    order += list(wx.columns) + ["wx_gap", "sun_elev", "daylight", "capacity_mw", "capacity_ca_mw",
                                 "curt_mwh", "curt_excluded", "scorable"]
    df = df[order]

    # ------------------------------------------------------------------ build report
    def flag(value, expected):
        return "OK   " if value == expected else "CHECK"

    lines.append(f"Hourly table build report ({rule} EIA rule)")
    lines.append(f"code version: {git_version()}")
    lines.append(f"window: hour ending {grid[0]:%Y-%m-%d %H:%M} to {grid[-1]:%Y-%m-%d %H:%M} UTC")
    lines.append("")
    lines.append("Row count after each step (expected 22,896):")
    lines += [f"  {s:<45} {n:,}" for s, n in steps]
    lines.append("")
    lines.append("Blank values per column (only columns with blanks):")
    blanks = df.isna().sum()
    for col, n in blanks[blanks > 0].items():
        lines.append(f"  {col:<45} {n:,}")
    lines.append("")
    n_eia = int(df["eia_mw"].isna().sum())
    n_dam = int(df["caiso_dam_mw"].isna().sum())
    n_wx = int(df["wx_gap"].sum())
    any_gap = int((df["eia_mw"].isna() | df["caiso_dam_mw"].isna() | df["wx_gap"]).sum())
    lines.append("Gaps against expectations:")
    lines.append(f"  [{flag(n_eia, 25)}] EIA blank hours: {n_eia} (expected 25 = 24 missing + 1 switch hour)")
    if rule == "d14":
        sw_blank = pd.isna(df.loc[pd.Timestamp("2025-12-02 21:00", tz="UTC"), "eia_mw"])
        lines.append(f"  [{flag(sw_blank, True)}] hour ending 2025-12-02 21:00 UTC blank: {sw_blank}")
    lines.append(f"  [{flag(n_dam, 72)}] CAISO day-ahead blank hours: {n_dam} (expected 72)")
    lines.append(f"  [{flag(n_wx, 129)}] wx_gap hours: {n_wx} (expected 129)")
    lines.append(f"  [{flag(any_gap, 226)}] hours with any gap (EIA, day-ahead or wx_gap): {any_gap} (expected 226)")
    lines.append("")
    n_day = int(df["daylight"].sum())
    lines.append(f"capacity-weighted centre: {lat_c:.2f}, {lon_c:.2f}")
    lines.append(f"daylight hours: {n_day:,} of {len(df):,}")
    lines.append(f"scorable hours: {int(df['scorable'].sum()):,} (all periods, including the locked test set)")
    tv = df["local_start"] < TEST_START
    lines.append(f"  of which training and validation: {int((df['scorable'] & tv).sum()):,}; "
                 f"test: {int((df['scorable'] & ~tv).sum()):,}")
    lines.append(f"daylight hours inside wx_gap: {int((df['daylight'] & df['wx_gap']).sum())}")
    lines.append("")
    dn = df[df["eia_deep_night_flag"]]
    lines.append(f"eia_deep_night_flag: {len(dn)} hours on {pd.Index(dn.index.date).nunique()} UTC dates "
                 f"({dn['local_start'].dt.date.nunique()} Pacific dates: a Pacific night spans 2 Pacific dates), "
                 f"max {dn['eia_mw_raw'].max():.0f} MW")
    lines.append(f"negative eia_mw_raw values set to 0 in eia_mw: {int((df['eia_mw_raw'] < 0).sum()):,}")
    lines.append(f"curt_excluded hours: {int(df['curt_excluded'].sum())} "
                 f"({df.loc[df['curt_excluded'], 'local_start'].dt.date.nunique()} Pacific days)")
    lines.append(f"curtailed solar in the window (excluding those days): {df['curt_mwh'].sum() / 1e6:.3f} TWh")
    lines += [f"  {n}" for n in curt_notes]
    lines.append("")
    lines.append(f"capacity_mw (EIA 860M nameplate, all CISO): {df['capacity_mw'].min():,.1f} to "
                 f"{df['capacity_mw'].max():,.1f} MW")
    lines.append(f"capacity_ca_mw (EIA 860M nameplate, Plant State CA): {df['capacity_ca_mw'].min():,.1f} to "
                 f"{df['capacity_ca_mw'].max():,.1f} MW")
    if missing:
        lines.append(f"  months without an 860M file, given the {latest} value: {', '.join(missing)}")
    return df, lines


def main() -> None:
    df, lines = build_table(rule="d14")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_TABLE)
    size_mb = OUT_TABLE.stat().st_size / 1e6
    lines.append("")
    lines.append(f"written: {OUT_TABLE.relative_to(ROOT).as_posix()} ({len(df):,} rows, "
                 f"{df.shape[1]} columns, {size_mb:.1f} MB)")
    text = "\n".join(lines)
    print(text)
    OUT_REPORT.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
