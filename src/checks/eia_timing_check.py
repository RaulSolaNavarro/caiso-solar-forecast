"""EIA timing check (FAQ Decision D14) and two related checks (D16, D22).

Re-runnable by anyone on the team. Reads only files in data/raw/ and writes nothing.

Run from the repo root:
    python -m src.checks.eia_timing_check

What it prints:
  1. Median offset per month, EIA minus CAISO ACTUAL (hours), from the energy-weighted
     centre of each day's curve.
  2. Daily offsets from 2025-11-15 to 2025-12-15.
  3. Gap of each series to astronomical solar noon, before 2025-11-25 and after 2025-12-05.
  4. Correlation of EIA with CAISO ACTUAL under 2 alignment rules.
  5. A scan of the switch hour near 2025-12-02 (which break hour fits best).
  6. Correlation of EIA with the capacity-weighted day-2 shortwave radiation (FAQ Q7.5),
     under the D14 rule, at weather shifts of -1, 0 and +1 hour.
  7. Deep-night positive EIA hours, with and without D14 (FAQ D16).
  8. Hourly solar curtailment on 2025-11-02 in the workbook and the daily report (FAQ D22).

Conventions: EIA `period` is a UTC label; EIA's page calls it hour ending. CAISO OASIS
`INTERVALENDTIME_GMT` is the UTC hour ending. Open-Meteo `time_utc` is the UTC hour ending
for radiation (mean of the preceding hour).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
EIA_FILE = RAW / "eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv"
ACT_FILE = RAW / "caiso_actual_solar_2024-01-01_2026-10-17.csv.gz"
LOC_FILE = RAW / "weather_locations.csv"
CURT_WB_FILE = RAW / "caiso_curtailment_2024-01-01_2025-12-31.csv.gz"
CURT_RP_FILE = RAW / "caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz"

# The D14 rule: labels before this time are 1 hour late; from this label on, label = hour ending.
SWITCH = pd.Timestamp("2025-12-02 22:00", tz="UTC")
WINDOW_START = pd.Timestamp("2024-03-08 00:00", tz="UTC")   # first hour ending in the window is 01:00
WINDOW_END = pd.Timestamp("2026-10-17 23:00", tz="UTC")
NOON_LON = -119.5


def load_eia():
    e = pd.read_csv(EIA_FILE, usecols=["period", "value"])
    e["label"] = pd.to_datetime(e["period"], format="%Y-%m-%dT%H", utc=True)
    return e.set_index("label")["value"].astype(float).rename("eia")


def d14_hour_end(labels):
    """Hour ending (UTC) for EIA labels under Decision D14."""
    return labels.where(labels >= SWITCH, labels - pd.Timedelta(hours=1))


def load_caiso_actual():
    a = pd.read_csv(ACT_FILE, usecols=["INTERVALENDTIME_GMT", "TRADING_HUB", "RENEWABLE_TYPE", "MW"])
    a = a[(a["RENEWABLE_TYPE"] == "Solar") & a["TRADING_HUB"].isin(["NP15", "SP15", "ZP26"])]
    a["end"] = pd.to_datetime(a["INTERVALENDTIME_GMT"], utc=True)
    by_hub = a.groupby(["end", "TRADING_HUB"])["MW"].sum().unstack()
    return by_hub.sum(axis=1, min_count=3).dropna().rename("caiso")


def capacity_centre():
    loc = pd.read_csv(LOC_FILE)
    loc = loc[loc["caiso_solar_capacity_share"] > 0]
    w = loc["caiso_solar_capacity_share"]
    return (loc["latitude"] * w).sum() / w.sum(), (loc["longitude"] * w).sum() / w.sum(), loc


def daily_centre(series):
    """Energy-weighted mean hour of each solar day. Day = UTC time minus 12 h, floored.
    Hour number = hours since 00:00 UTC of that day (so midday UTC is about 20).
    Only days with 24 values and a positive sum."""
    t = series.index
    day = (t - pd.Timedelta(hours=12)).floor("D").tz_localize(None)
    hour = (t.tz_localize(None) - day) / pd.Timedelta(hours=1)
    d = pd.DataFrame({"day": day, "h": hour, "v": series.values})
    g = d.groupby("day")
    ok = (g["v"].count() == 24) & (g["v"].sum() > 0)
    centre = (d["h"] * d["v"]).groupby(d["day"]).sum() / g["v"].sum()
    return centre[ok]


def solar_noon_utc_hour(days):
    doy = days.day_of_year
    b = 2 * np.pi * (doy - 81) / 364
    eot_min = 9.87 * np.sin(2 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)
    return pd.Series(12 - NOON_LON / 15 - eot_min / 60, index=days)


def section(title):
    print(f"\n=== {title}")


def main():
    eia = load_eia()
    act = load_caiso_actual()
    lat_c, lon_c, loc = capacity_centre()

    # 1 to 3. Offset from the daily curve centre, EIA labels as given, CAISO by interval end
    ce = daily_centre(eia)
    cc = daily_centre(act)
    both = pd.concat([ce.rename("eia"), cc.rename("caiso")], axis=1, sort=True).dropna()
    both["offset"] = both["eia"] - both["caiso"]
    section(f"1. Median offset per month, EIA minus CAISO (hours). Days with both series: {len(both):,}")
    monthly = both["offset"].groupby(both.index.to_period("M")).median()
    print(monthly.round(2).to_string())

    section("2. Daily offsets, 2025-11-15 to 2025-12-15 (hours)")
    print(both.loc["2025-11-15":"2025-12-15", "offset"].round(2).to_string())

    section("3. Mean gap to solar noon at lon -119.5 (hours; label read as hour ending, centre = label - 0.5)")
    noon = solar_noon_utc_hour(both.index)
    gap_e = both["eia"] - 0.5 - noon
    gap_c = both["caiso"] - 0.5 - noon
    before = both.index < "2025-11-25"
    after = both.index > "2025-12-05"
    print(f"before 2025-11-25: EIA {gap_e[before].mean():+.2f} h, CAISO {gap_c[before].mean():+.2f} h  ({before.sum()} days)")
    print(f"after  2025-12-05: EIA {gap_e[after].mean():+.2f} h, CAISO {gap_c[after].mean():+.2f} h  ({after.sum()} days)")

    # 4. Correlation under 2 rules, daylight rows where CAISO > 1,000 MW
    section("4. Correlation of EIA with CAISO ACTUAL (rows where CAISO > 1,000 MW)")
    rules = {
        "shift all labels back 1 hour": pd.Series(eia.values, index=eia.index - pd.Timedelta(hours=1)),
        "D14 (shift only before 2025-12-02 22:00 UTC)": pd.Series(eia.values, index=d14_hour_end(eia.index)),
    }
    periods = {"2024-03-08 to 2025-11-25": ("2024-03-08", "2025-11-26"),
               "2025-12-06 to 2026-10-17": ("2025-12-06", "2026-10-18")}
    for name, s in rules.items():
        j = pd.concat([s.rename("eia"), act], axis=1, sort=True).dropna()
        j = j[j["caiso"] > 1000]
        out = []
        for pname, (a, b) in periods.items():
            sub = j[(j.index >= pd.Timestamp(a, tz="UTC")) & (j.index < pd.Timestamp(b, tz="UTC"))]
            out.append(f"{pname}: {sub['eia'].corr(sub['caiso']):.4f} (n={len(sub):,})")
        print(f"{name}: " + "; ".join(out))

    # 5. Scan the switch hour: total absolute difference to CAISO over 2025-11-28 to 2025-12-07
    section("5. Switch-hour scan: mean |EIA - CAISO| (MW), 2025-11-28 to 2025-12-07, hours both exist")
    lo, hi = pd.Timestamp("2025-11-28", tz="UTC"), pd.Timestamp("2025-12-08", tz="UTC")
    for cand in pd.date_range("2025-12-02 14:00", "2025-12-03 04:00", freq="h", tz="UTC"):
        lab = eia.index
        he = lab.where(lab >= cand, lab - pd.Timedelta(hours=1))
        s = pd.Series(eia.values, index=he)
        s = s[~s.index.duplicated()]
        j = pd.concat([s.rename("eia"), act], axis=1, sort=True).dropna()
        j = j[(j.index >= lo) & (j.index < hi)]
        print(f"switch at label {cand:%Y-%m-%d %H:%M} UTC: {(j['eia'] - j['caiso']).abs().mean():7.1f}")

    # 6. FAQ Q7.5: EIA (D14) vs capacity-weighted day-2 shortwave radiation, full window
    section("6. EIA (D14 rule) vs capacity-weighted day-2 shortwave radiation, window 2024-03-08 to 2026-10-17")
    num = den = None
    for lid, share in zip(loc["location_id"], loc["caiso_solar_capacity_share"]):
        f = pd.read_csv(RAW / "openmeteo" / f"openmeteo_prev_runs_ecmwf_ifs025_{lid}_2024-03-08_2026-10-17.csv.gz",
                        usecols=["time_utc", "shortwave_radiation_previous_day2"])
        v = f.set_index("time_utc")["shortwave_radiation_previous_day2"].astype(float)
        num = v.fillna(0) * share if num is None else num + v.fillna(0) * share
        den = v.notna() * share if den is None else den + v.notna() * share
    sw = num / den
    sw.index = pd.to_datetime(sw.index, utc=True)
    grid = pd.date_range(WINDOW_START, WINDOW_END, freq="h")
    e14 = pd.Series(eia.values, index=d14_hour_end(eia.index)).reindex(grid)
    sw = sw.reindex(grid)
    for k in (-1, 0, 1):
        print(f"EIA shifted {k:+d} h: correlation {e14.shift(k).corr(sw):.4f}")
    print("(same method as notebook Raul_EDA_v2 cell 33; shift(k) moves EIA k rows later on the grid)")

    # 7. Deep-night positive EIA hours. Main definition (FAQ D16): EIA above 100 MW while the sun
    # is below -12 degrees at the middle of the hour, at the capacity-weighted centre.
    # Two comparison rows: the original pull-time definition (Westlands, sun below -12 at the
    # label and at the label minus 2 h, labels as given), and D14 with the whole hour below -12.
    section(f"7. EIA above 100 MW at deep night; capacity-weighted centre ({lat_c:.2f}, {lon_c:.2f})")

    def elev(t, lat, lon):
        return pvlib.solarposition.get_solarposition(t, lat, lon)["elevation"].values

    def report(name, he, hit, by_month=False):
        dates = pd.Index(he[hit].tz_localize(None).date).unique()
        print(f"{name}: {hit.sum()} hours on {len(dates)} UTC dates, max {eia.values[hit].max():.0f} MW")
        if by_month:
            m = pd.Series(1, index=he[hit]).groupby(he[hit].tz_localize(None).to_period("M")).sum()
            print("  by month: " + ", ".join(f"{p}: {n}" for p, n in m.items()))

    lab, v = eia.index, eia.values
    he = d14_hour_end(lab)
    westlands = (36.4, -120.1)
    report("pull-time definition (Westlands, label and label - 2 h, labels as given)", lab,
           (v > 100) & (elev(lab, *westlands) < -12) & (elev(lab - pd.Timedelta(hours=2), *westlands) < -12))
    report("D14, centre, middle of the hour (main definition)", he,
           (v > 100) & (elev(he - pd.Timedelta(minutes=30), lat_c, lon_c) < -12), by_month=True)
    report("D14, centre, whole hour (start and end) below -12", he,
           (v > 100) & (elev(he, lat_c, lon_c) < -12) & (elev(he - pd.Timedelta(hours=1), lat_c, lon_c) < -12),
           by_month=True)

    # 8. Curtailment on 2025-11-02 (25-hour Pacific day), workbook vs daily report
    section("8. Solar curtailment 2025-11-02, MWh by Hour position: workbook vs daily report")
    wb = pd.read_csv(CURT_WB_FILE, usecols=["Date", "Hour", "Solar Curtailment"])
    wb = wb[wb["Date"].str[:10] == "2025-11-02"]
    wb_h = (wb.groupby("Hour")["Solar Curtailment"].sum() / 12).reindex(range(1, 25), fill_value=0.0)
    rp = pd.read_csv(CURT_RP_FILE, dtype=str)
    rp = rp[(rp["operating_date"] == "2025-11-02") & (rp["fuel"] == "solar")]
    mwh_cols = [c for c in rp.columns if c.endswith("_mwh")]
    rp_h = rp[mwh_cols].apply(pd.to_numeric).sum(axis=1)
    rp_h.index = rp["hour"].astype(int)
    rp_h = rp_h.reindex(range(1, 25), fill_value=0.0)
    t = pd.DataFrame({"workbook": wb_h.round(1), "report": rp_h.round(1)})
    print(t[(t["workbook"] != 0) | (t["report"] != 0)].to_string())
    print(f"day total: workbook {wb_h.sum():.1f}, report {rp_h.sum():.1f} MWh")
    for k in (-1, 0, 1):
        print(f"report vs workbook shifted {k:+d}: correlation {rp_h.corr(wb_h.shift(k)):.4f}, "
              f"sum |diff| {(rp_h - wb_h.shift(k).fillna(0)).abs().sum():.1f} MWh")


if __name__ == "__main__":
    main()
