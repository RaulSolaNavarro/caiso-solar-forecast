"""Check the 2 timing assumptions behind the 10 a.m. rule (Brief 5, FAQ Decision D32).

NOT PART OF THE PIPELINE. This script makes live API calls (Open-Meteo and EIA) and reads no
test-period model result. It does not touch the frozen model, final_test.py or reports/final_*.

Run from the repo root (needs the EIA key in .env for check 2):
    python -m src.modeling.assumption_checks

API responses are cached in a scratch folder outside the repo (%TEMP%/caiso_assumption_checks), so a
rerun makes no new calls. Open-Meteo calls are counted and capped at OPENMETEO_CAP.

Check 1 (weather): for 5 recent Pacific dates D and 3 daylight hours each, at weather point c01 (the
largest capacity share), compare *_previous_day2 from the Previous Runs API with the same valid hour
from the Single Runs API for the 00, 06, 12, 18 UTC runs on D-2 and the 00, 06 UTC runs on D-1. The
run that reproduces previous_day2 is the run behind it. Pass rule (Raúl's conservative choice, not an
ECMWF fact): that run started no later than 06:00 UTC on D-1, which leaves at least 11 hours before the
10 a.m. Pacific bid close.

Check 2 (EIA): re-pull EIA CISO solar hourly (same call as src/data_pull/eia_hourly.py) from
2026-08-01 to the latest complete UTC day and compare with data/raw (pulled 2026-10-27 and 28) on the
labels both cover. Pass rule: mean absolute difference below 0.1% of capacity_mw and no Pacific day with
a mean absolute difference above 1% of capacity_mw. Also checks that cf_d2_daily uses only hours of
Pacific day D-2.

Writes reports/assumption_checks_weather_runs.csv, _weather_match.csv, _eia_daily.csv, _eia_top5.csv.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import requests

from src.data_pull.common import get_key
from src.data_pull.eia_hourly import fetch as eia_fetch
from src.processing.build_hourly_table import EIA_FILE, LOCAL_TZ, ROOT, capacity_by_month

SCRATCH = Path(os.environ.get("TEMP", "/tmp")) / "caiso_assumption_checks"
REPORTS = ROOT / "reports"
PREV_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
SINGLE_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
MODEL = "ecmwf_ifs025"
POINT = ("c01", 35.00, -118.04)                     # largest caiso_solar_capacity_share in weather_locations.csv
DATES = ["2026-10-27", "2026-10-29", "2026-10-31", "2026-11-02", "2026-11-04"]   # Pacific D
HOURS = [9, 13, 17]                                  # Pacific hour of the hour start
VARS = ["shortwave_radiation", "cloud_cover"]
OPENMETEO_CAP = 100
PROBE_CALLS = 2                                      # 2 probe calls made by hand on 2026-11-07 before this script
EIA_START = "2026-08-01"

calls = {"openmeteo": PROBE_CALLS, "eia": 0}


def cached_get(url: str, params: dict, name: str, kind: str) -> dict:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    f = SCRATCH / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    if kind == "openmeteo" and calls["openmeteo"] >= OPENMETEO_CAP:
        raise SystemExit(f"Open-Meteo call cap of {OPENMETEO_CAP} reached")
    calls[kind] += 1
    r = requests.get(url, params=params, timeout=90)
    r.raise_for_status()
    j = r.json()
    if j.get("error"):
        raise SystemExit(f"{url}: {j.get('reason')}")
    f.write_text(json.dumps(j), encoding="utf-8")
    return j


def frame(j: dict, cols: list[str]) -> pd.DataFrame:
    h = j["hourly"]
    return pd.DataFrame({c: h[c] for c in cols}, index=pd.to_datetime(h["time"], utc=True))


# ----------------------------------------------------------------------------- check 1

def targets() -> pd.DataFrame:
    """Valid times: the hour ending (UTC) of each Pacific hour start, as the hourly table aligns weather."""
    rows = []
    for d in DATES:
        for h in HOURS:
            start = pd.Timestamp(f"{d} {h:02d}:00").tz_localize(LOCAL_TZ)
            rows.append(dict(D=d, pacific_hour_start=h, valid_utc=(start + pd.Timedelta(hours=1)).tz_convert("UTC")))
    return pd.DataFrame(rows)


def runs_for(d: str) -> list[pd.Timestamp]:
    d2, d1 = pd.Timestamp(d) - pd.Timedelta(days=2), pd.Timestamp(d) - pd.Timedelta(days=1)
    return [d2 + pd.Timedelta(hours=h) for h in (0, 6, 12, 18)] + [d1 + pd.Timedelta(hours=h) for h in (0, 6)]


def check1() -> tuple[pd.DataFrame, pd.DataFrame]:
    lid, lat, lon = POINT
    t = targets()
    prev_cols = [f"{v}_previous_day2" for v in VARS]
    first, last = pd.Timestamp(DATES[0]), pd.Timestamp(DATES[-1]) + pd.Timedelta(days=1)
    j = cached_get(PREV_URL, dict(latitude=lat, longitude=lon, models=MODEL, timezone="UTC", hourly=",".join(prev_cols),
                                  start_date=f"{first:%Y-%m-%d}", end_date=f"{last:%Y-%m-%d}"),
                   f"prev_{lid}_{first:%Y%m%d}_{last:%Y%m%d}", "openmeteo")
    prev = frame(j, prev_cols)
    rows = []
    for _, r in t.iterrows():
        p = prev.loc[r.valid_utc]
        for run in runs_for(r.D):
            js = cached_get(SINGLE_URL, dict(latitude=lat, longitude=lon, models=MODEL, timezone="UTC", run=f"{run:%Y-%m-%dT%H:%M}",
                                             hourly=",".join(VARS), forecast_days=4),
                            f"single_{lid}_{run:%Y%m%d%H}", "openmeteo")
            s = frame(js, VARS)
            v = s.loc[r.valid_utc] if r.valid_utc in s.index else pd.Series({c: None for c in VARS})
            rows.append(dict(D=r.D, pacific_hour_start=r.pacific_hour_start, valid_utc=r.valid_utc.strftime("%Y-%m-%d %H:%M"),
                             run_utc=run.strftime("%Y-%m-%d %H:%M"),
                             run_day="D-2" if run.normalize() == pd.Timestamp(r.D) - pd.Timedelta(days=2) else "D-1",
                             hours_before_valid=(r.valid_utc.tz_localize(None) - run).total_seconds() / 3600,
                             prev_day2_ghi=p["shortwave_radiation_previous_day2"], run_ghi=v["shortwave_radiation"],
                             prev_day2_cloud=p["cloud_cover_previous_day2"], run_cloud=v["cloud_cover"]))
    runs = pd.DataFrame(rows)
    runs["ghi_diff"] = runs["run_ghi"] - runs["prev_day2_ghi"]
    runs["cloud_diff"] = runs["run_cloud"] - runs["prev_day2_cloud"]
    runs["exact"] = (runs["ghi_diff"].abs() < 1e-9) & (runs["cloud_diff"].abs() < 1e-9)
    runs["distance"] = runs["ghi_diff"].abs() / 10 + runs["cloud_diff"].abs()   # 10 W/m2 weighs like 1 point of cloud

    match = []
    for (d, h), g in runs.groupby(["D", "pacific_hour_start"], sort=False):
        g = g.dropna(subset=["run_ghi"])
        exact = g[g["exact"]]
        best = exact if len(exact) else g.nsmallest(1, "distance")
        deadline = pd.Timestamp(d) - pd.Timedelta(days=1) + pd.Timedelta(hours=6)
        latest = pd.to_datetime(best["run_utc"]).max()
        match.append(dict(D=d, pacific_hour_start=h, valid_utc=g["valid_utc"].iloc[0],
                          matching_runs="; ".join(best["run_utc"]), how="exact" if len(exact) else "nearest",
                          hours_before_valid=best["hours_before_valid"].min(),
                          ghi_diff=best["ghi_diff"].iloc[0], cloud_diff=best["cloud_diff"].iloc[0],
                          run_by_0600_utc_on_D_minus_1=bool(latest <= deadline)))
    return runs, pd.DataFrame(match)


# ----------------------------------------------------------------------------- check 2

def check2() -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    last_day = (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1)).tz_localize(None)
    f = SCRATCH / f"eia_repull_{EIA_START}_{last_day:%Y-%m-%d}.csv"
    if f.exists():
        new = pd.read_csv(f, dtype=str, keep_default_na=False)
    else:
        key = get_key("EIA_API_KEY")
        parts = []
        for m in pd.date_range(EIA_START, last_day, freq="MS"):
            m_end = min(m + pd.offsets.MonthEnd(0), last_day)
            parts.append(eia_fetch(f"{m:%Y-%m-%d}T00", f"{m_end:%Y-%m-%d}T23", key))
            calls["eia"] += 1
        new = pd.concat(parts, ignore_index=True)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        new.to_csv(f, index=False)
    old = pd.read_csv(EIA_FILE, dtype=str, keep_default_na=False)
    old = old[old["period"] >= f"{EIA_START}T00"]
    m = old[["period", "value"]].merge(new[["period", "value"]], on="period", how="outer", suffixes=("_raw", "_now"),
                                       indicator=True)
    both = m[m["_merge"] == "both"].copy()
    both["raw"] = pd.to_numeric(both["value_raw"], errors="coerce")
    both["now"] = pd.to_numeric(both["value_now"], errors="coerce")
    both["diff_mw"] = both["now"] - both["raw"]
    label = pd.to_datetime(both["period"], format="%Y-%m-%dT%H", utc=True)   # after 2025-12-02 a label is the hour ending (D14)
    all_ciso, _ = capacity_by_month()
    month = label.dt.strftime("%Y-%m")
    month = month.where(month.isin(all_ciso.index), all_ciso.index.max())   # no 860M file for 2026-10: use the latest (as the table does)
    both["capacity_mw"] = month.map(all_ciso).values
    both["share_pct"] = both["diff_mw"].abs() / both["capacity_mw"] * 100
    both["pacific_day"] = (label - pd.Timedelta(hours=1)).dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d").values
    daily = both.groupby("pacific_day").agg(hours=("diff_mw", "size"), changed_hours=("diff_mw", lambda x: int((x.abs() > 0).sum())),
                                            mean_abs_diff_mw=("diff_mw", lambda x: x.abs().mean()),
                                            max_abs_diff_mw=("diff_mw", lambda x: x.abs().max()),
                                            mean_abs_share_pct=("share_pct", "mean")).reset_index()
    top5 = both.assign(abs_diff_mw=both["diff_mw"].abs()).nlargest(5, "abs_diff_mw")[
        ["period", "raw", "now", "diff_mw", "capacity_mw", "share_pct"]]
    summary = dict(rows_raw=int(len(old)), rows_now=int(len(new)), rows_compared=int(len(both)),
                   only_in_now=int((m["_merge"] == "right_only").sum()), only_in_raw=int((m["_merge"] == "left_only").sum()),
                   rows_changed=int((both["diff_mw"].abs() > 0).sum()), blank_raw=int(both["raw"].isna().sum()),
                   blank_now=int(both["now"].isna().sum()),
                   mean_abs_diff_mw=float(both["diff_mw"].abs().mean()), max_abs_diff_mw=float(both["diff_mw"].abs().max()),
                   mean_abs_share_pct=float(both["share_pct"].mean()), max_share_pct=float(both["share_pct"].max()),
                   max_daily_share_pct=float(daily["mean_abs_share_pct"].max()),
                   first=both["period"].min(), last=both["period"].max(), repull_last=new["period"].max())
    summary["pass"] = summary["mean_abs_share_pct"] < 0.1 and summary["max_daily_share_pct"] <= 1.0
    return summary, daily, top5


def check_d2_window() -> dict:
    """cf_d2_daily groups EIA by the Pacific date of each hour's start (features.py). Confirm on the
    training and validation table that every hour grouped into Pacific day X ends by midnight at the
    end of X, so no hour of D-1 enters the D-2 mean."""
    from src.modeling.features import HOUR, eia_history, load_tv_table
    df = load_tv_table()
    eia = eia_history(df.index.max())
    pac_day = (eia.index - HOUR).tz_convert(LOCAL_TZ).tz_localize(None).normalize()
    end_local = eia.index.tz_convert(LOCAL_TZ).tz_localize(None)
    late = end_local > pac_day + pd.Timedelta(days=1)
    return dict(hours_checked=int(len(eia)), hours_ending_after_their_day=int(late.sum()),
                latest_end_vs_day_start_h=float(((end_local - pac_day).max()).total_seconds() / 3600))


def main() -> None:
    print("Assumption checks (not part of the pipeline; makes API calls; no test-period model result is read)\n")
    runs, match = check1()
    REPORTS.mkdir(exist_ok=True)
    runs.round(3).to_csv(REPORTS / "assumption_checks_weather_runs.csv", index=False)
    match.round(3).to_csv(REPORTS / "assumption_checks_weather_match.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_colwidth", 60):
        print("Check 1: run behind previous_day2 (point c01, ecmwf_ifs025)")
        print(match.to_string(index=False))
    print(f"\nall {len(match)} target hours from a run started by 06:00 UTC on D-1: {bool(match['run_by_0600_utc_on_D_minus_1'].all())}")

    s, daily, top5 = check2()
    daily.round(4).to_csv(REPORTS / "assumption_checks_eia_daily.csv", index=False)
    top5.round(3).to_csv(REPORTS / "assumption_checks_eia_top5.csv", index=False)
    print("\nCheck 2: EIA re-pull against data/raw")
    for k, v in s.items():
        print(f"  {k}: {round(v, 4) if isinstance(v, float) else v}")
    print("  5 largest differences:")
    print(top5.round(2).to_string(index=False))
    w = check_d2_window()
    print(f"\n  cf_d2_daily window: {w}")
    print(f"\nAPI calls: Open-Meteo {calls['openmeteo']} (including {PROBE_CALLS} probe calls; cached reruns add none), "
          f"EIA {calls['eia']} monthly requests (each may page)")


if __name__ == "__main__":
    main()
