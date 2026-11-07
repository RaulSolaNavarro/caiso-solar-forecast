"""Feature table for the day-ahead solar models (the 10 a.m. rule, FAQ Decision D28).

Run from the repo root, after build_hourly_table:
    python -m src.modeling.features          prints the feature list, reasons and blank counts

The forecast for hour t of Pacific day D is issued before CAISO's bid close at 10:00 a.m. Pacific on
day D-1. Allowed inputs: day-2 weather forecasts, calendar and sun geometry for hour t, capacity_mw of
that month, and EIA output at hour ending t - 48 h or earlier (or daily values that end with Pacific
day D-2). Day-1 weather is used only in the labeled comparison (day1=True).

Test rows (Pacific dates from 2026-04-10) are dropped right after loading. The EIA history used for
lags is cut at the same point, so no test-period value is kept in memory after load.

Target: capacity factor cf = eia_mw / capacity_mw (eia_mw clipped at 0, D15). Fit rows (D16, D17):
daylight, EIA present, wx_gap False, eia_deep_night_flag False.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib

from src.processing.build_hourly_table import LOCAL_TZ, OUT_TABLE, TEST_START, align_eia, capacity_centre

HOUR = pd.Timedelta(hours=1)
MIN_LAG_HOURS = 48           # never t - 24 h: that hour can fall after the 10 a.m. bid close
MIN_DAY_OFFSET = 2           # daily features end with Pacific day D-2 at the latest
CSI_MIN_GHI = 20.0           # W/m2; below this the clear-sky index is left blank (dawn and dusk noise)

DAY2_WEATHER = ["cloud_cover_previous_day2", "shortwave_radiation_previous_day2", "direct_radiation_previous_day2",
                "diffuse_radiation_previous_day2", "direct_normal_irradiance_previous_day2",
                "temperature_2m_previous_day2", "relative_humidity_2m_previous_day2", "wind_speed_10m_previous_day2",
                "precipitation_previous_day2"]
DAY1_SWAP = {"cloud_cover_previous_day2": "cloud_cover_previous_day1",
             "shortwave_radiation_previous_day2": "shortwave_radiation_previous_day1",
             "csi_previous_day2": "csi_previous_day1"}

# name: (kind, lag_hours or day_offset, reason). kind: weather | calendar | capacity | eia_hourly | eia_daily
FEATURE_SPEC: dict[str, tuple[str, int | None, str]] = {
    "cloud_cover_previous_day2": ("weather", None, "Day-2 cloud cover (%), the main reason output drops below clear sky"),
    "shortwave_radiation_previous_day2": ("weather", None, "Day-2 forecast sunshine on a flat surface (GHI, W/m2), the strongest single driver"),
    "direct_radiation_previous_day2": ("weather", None, "Day-2 direct part of GHI; tracking plants respond to the direct beam"),
    "diffuse_radiation_previous_day2": ("weather", None, "Day-2 diffuse part; separates thin haze from thick cloud at the same GHI"),
    "direct_normal_irradiance_previous_day2": ("weather", None, "Day-2 beam on a surface facing the sun, close to what single-axis trackers see"),
    "temperature_2m_previous_day2": ("weather", None, "Day-2 air temperature; hot panels lose efficiency"),
    "relative_humidity_2m_previous_day2": ("weather", None, "Day-2 humidity; a weak proxy for haze and marine layer"),
    "wind_speed_10m_previous_day2": ("weather", None, "Day-2 wind; cools panels"),
    "precipitation_previous_day2": ("weather", None, "Day-2 rain; storm days and heavy cloud"),
    "csi_previous_day2": ("weather", None, "Day-2 GHI / clear-sky GHI: how cloudy the forecast is, independent of sun height (blank when clear-sky GHI < 20 W/m2)"),
    "hour": ("calendar", None, "Pacific hour of the hour start (0 to 23), the daily shape"),
    "hour_sin": ("calendar", None, "Hour as sine, so the linear model can draw a smooth daily curve"),
    "hour_cos": ("calendar", None, "Hour as cosine, with hour_sin"),
    "doy_sin": ("calendar", None, "Day of year as sine: season, sun path, day length"),
    "doy_cos": ("calendar", None, "Day of year as cosine, with doy_sin"),
    "sun_elev": ("calendar", None, "Sun elevation (degrees) at mid-hour at the capacity-weighted centre, from the table (D20)"),
    "clearsky_ghi": ("calendar", None, "pvlib Ineichen clear-sky GHI (W/m2) at the same centre and mid-hour as sun_elev: the most the sky could give"),
    "capacity_mw": ("capacity", None, "EIA 860M monthly nameplate, all CISO; tracks the changing fleet (target is already divided by it)"),
    "cf_lag48": ("eia_hourly", 48, "EIA at hour ending t - 48 h / capacity_mw of hour t: persistence D-2 as a capacity factor"),
    "cf_d2_daily": ("eia_daily", 2, "Mean EIA capacity factor over all hours of Pacific day D-2: how sunny the latest fully known day was"),
}
MAIN_FEATURES = list(FEATURE_SPEC)


def day1_features() -> list[str]:
    """Labeled comparison only: day-2 cloud cover and GHI swapped for their day-1 versions."""
    return [DAY1_SWAP.get(f, f) for f in MAIN_FEATURES]


def assert_tv_only(df: pd.DataFrame, where: str = "") -> None:
    """Startup check: no row with local_start on or after 2026-04-10 Pacific may reach a fit, fold or score."""
    if (df["local_start"] >= TEST_START).any():
        raise AssertionError(f"test-period rows reached {where or 'this step'}; the test set is locked")


def load_tv_table() -> pd.DataFrame:
    """The processed table with test rows dropped right after loading."""
    if not OUT_TABLE.exists():
        raise SystemExit(f"{OUT_TABLE} not found. Run: python -m src.processing.build_hourly_table")
    df = pd.read_parquet(OUT_TABLE)
    df = df[df["local_start"] < TEST_START].copy()
    assert_tv_only(df, "load_tv_table")
    return df


def eia_history(last_hour_end: pd.Timestamp) -> pd.Series:
    """Clipped EIA under D14 from the raw file (history before the window included), cut at the last
    training-and-validation hour so no test-period value is kept."""
    eia = align_eia(rule="d14").clip(lower=0)
    return eia[eia.index <= last_hour_end]


def build_features(df: pd.DataFrame | None = None, allow_test: bool = False) -> pd.DataFrame:
    """Feature table on the table's rows (training and validation only) with the target and fit mask.

    Columns: every name in FEATURE_SPEC, the 2 day-1 comparison columns (and csi_previous_day1),
    plus cf (target), eia_mw, capacity_mw, local_start, fit_row.

    allow_test=True is used only by final_test.py behind its --final-test flag (the one test run).
    """
    df = load_tv_table() if df is None else df
    if not allow_test:
        assert_tv_only(df, "build_features")
    idx = df.index
    eia = eia_history(idx.max())
    out = pd.DataFrame(index=idx)
    out["local_start"] = df["local_start"]

    for c in DAY2_WEATHER + ["cloud_cover_previous_day1", "shortwave_radiation_previous_day1"]:
        out[c] = df[c]

    ls = df["local_start"]
    out["hour"] = ls.dt.hour
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24)
    doy = ls.dt.day_of_year
    out["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    out["sun_elev"] = df["sun_elev"]
    lat, lon = capacity_centre()
    cs = pvlib.location.Location(lat, lon).get_clearsky(idx - pd.Timedelta(minutes=30), model="ineichen")
    out["clearsky_ghi"] = cs["ghi"].values
    for day in ("day2", "day1"):
        csi = df[f"shortwave_radiation_previous_{day}"] / out["clearsky_ghi"]
        out[f"csi_previous_{day}"] = csi.where(out["clearsky_ghi"] >= CSI_MIN_GHI).clip(0, 1.5)
    out["capacity_mw"] = df["capacity_mw"]

    # EIA lags: hourly at t - 48 h, divided by the capacity of hour t (so cf_lag48 * capacity = persistence D-2)
    out["cf_lag48"] = eia.reindex(idx - MIN_LAG_HOURS * HOUR).values / df["capacity_mw"].values
    # Daily: mean capacity factor of Pacific day D-2 (all hours present on that day, at least 20 of them)
    pac_day = (eia.index - HOUR).tz_convert(LOCAL_TZ).tz_localize(None).normalize()
    g = eia.groupby(pac_day).agg(["mean", "count"])
    daily_mw = g["mean"].where(g["count"] >= 20)
    d2 = ls.dt.tz_localize(None).dt.normalize() - pd.Timedelta(days=MIN_DAY_OFFSET)
    out["cf_d2_daily"] = daily_mw.reindex(d2).values / df["capacity_mw"].values

    out["eia_mw"] = df["eia_mw"]
    out["cf"] = df["eia_mw"] / df["capacity_mw"]
    out["fit_row"] = df["daylight"] & df["eia_mw"].notna() & ~df["wx_gap"] & ~df["eia_deep_night_flag"]
    out["daylight"] = df["daylight"]
    assert_no_leak(out[MAIN_FEATURES])
    return out


def assert_no_leak(features: pd.DataFrame, allow_day1: bool = False) -> None:
    """Fail if any EIA lag is under 48 h, any daily EIA feature ends after Pacific day D-2, any column is
    not in the spec, or a *_previous_day1 column is present outside the labeled comparison."""
    for c in features.columns:
        if c.endswith("_previous_day1"):
            if not allow_day1:
                raise AssertionError(f"{c}: day-1 weather is allowed only in the labeled comparison run")
            continue
        if c not in FEATURE_SPEC:
            raise AssertionError(f"{c}: not in FEATURE_SPEC, so its timing is not checked")
        kind, lag, _ = FEATURE_SPEC[c]
        if kind == "eia_hourly" and (lag is None or lag < MIN_LAG_HOURS):
            raise AssertionError(f"{c}: EIA lag {lag} h is under {MIN_LAG_HOURS} h")
        if kind == "eia_daily" and (lag is None or lag < MIN_DAY_OFFSET):
            raise AssertionError(f"{c}: daily EIA feature uses a day later than D-{MIN_DAY_OFFSET}")


def main() -> None:
    f = build_features()
    fit = f[f["fit_row"]]
    print("Feature table (training and validation only, test locked)")
    print(f"rows: {len(f):,}; fit rows (daylight, EIA present, no wx_gap, no deep-night flag): {len(fit):,}; "
          f"last local_start: {f['local_start'].max()}\n")
    print(f"{'#':>2}  {'feature':<40} {'kind':<11} {'blank in fit rows':>17}  reason")
    for i, (name, (kind, lag, reason)) in enumerate(FEATURE_SPEC.items(), 1):
        print(f"{i:>2}  {name:<40} {kind:<11} {int(fit[name].isna().sum()):>17,}  {reason}")
    print("\nDay-1 comparison run only: " + ", ".join(f"{a} -> {b}" for a, b in DAY1_SWAP.items()))
    assert_no_leak(f[day1_features()], allow_day1=True)
    print("assert_no_leak: passed for the main set and the day-1 comparison set")


if __name__ == "__main__":
    main()
