"""Chart data for the deck, in long format, from the processed hourly table.

Run from the repo root, after build_hourly_table:
    python -m src.processing.deck_chart_data

Writes reports/deck_chart_data.csv with columns chart, series, x, value, n, note:
  season_profile             mean eia_mw (negatives set to 0, D15) by Pacific hour of the hour start and
                             season; series <season>_tv (before 2026-04-10 Pacific) and <season>_all.
  monthly_curtailment_share  the "New" column of the monthly table in reports/capstone2_numbers_corrected.md.
  cloud_buckets              output / capacity at midday by day-2 cloud cover bucket, training and validation.

Prints the summer and winter peaks of both versions and checks them against
reports/capstone2_numbers_corrected.md. Series that include test-period days are descriptive only.
"""

from __future__ import annotations

import pandas as pd

from src.processing.build_hourly_table import OUT_TABLE, ROOT, TEST_START
from src.processing.capstone2_numbers import (CLOUD_BINS, SEASON, cloud_buckets, curtailment_shares,
                                              season_peaks)

OUT_CSV = ROOT / "reports" / "deck_chart_data.csv"
SEASON_ORDER = ["Winter", "Spring", "Summer", "Fall"]
CLOUD_LABELS = ["0-10", "10-30", "30-60", "60-100"]
MIDDAY_HOURS = [10, 11, 12]                      # Pacific hour of the hour start, as in cloud_buckets
# Peaks in reports/capstone2_numbers_corrected.md (New column), MW rounded to 100
EXPECTED_PEAKS = {"tv": {"Summer": 16900, "Winter": 11900}, "all": {"Summer": 17500, "Winter": 11900}}


def season_profile(df: pd.DataFrame, tv_only: bool) -> pd.DataFrame:
    """Mean and count of eia_mw (clipped at 0) by season and Pacific hour of the hour start."""
    t = df[df["eia_mw"].notna()]
    if tv_only:
        t = t[t["local_start"] < TEST_START]
    g = t["eia_mw"].clip(lower=0).groupby([t["local_start"].dt.month.map(SEASON), t["local_start"].dt.hour])
    return g.agg(["mean", "count"])


def cloud_bucket_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Same selection as capstone2_numbers.cloud_buckets, with the hour count per bucket."""
    tv = df[df["local_start"] < TEST_START]
    mid = pd.DataFrame({"share": tv["eia_mw"] / tv["capacity_mw"] * 100, "cc": tv["cloud_cover_previous_day2"]})
    mid = mid[tv["local_start"].dt.hour.isin(MIDDAY_HOURS)].dropna()
    return mid.groupby(pd.cut(mid["cc"], CLOUD_BINS), observed=True)["share"].agg(["mean", "count"])


def main() -> None:
    df = pd.read_parquet(OUT_TABLE)
    rows = []

    # 1. Season profiles
    peaks = {}
    for version, tv_only in [("tv", True), ("all", False)]:
        prof = season_profile(df, tv_only)
        note = ("training and validation days (before 2026-04-10 Pacific)" if tv_only
                else "all days, includes test period (descriptive only)")
        for season in SEASON_ORDER:
            for hour, r in prof.loc[season].iterrows():
                rows.append(dict(chart="season_profile", series=f"{season.lower()}_{version}", x=int(hour),
                                 value=round(r["mean"], 1), n=int(r["count"]),
                                 note=f"mean EIA MW, Pacific hour of hour start; {note}"))
        peaks[version] = {s: prof.loc[s, "mean"].max() for s in SEASON_ORDER}
        # Cross-check against the reused function (it clips after averaging; eia_mw is already clipped)
        s_ref, w_ref, _ = season_peaks(df, "eia_mw", tv_only=tv_only)
        assert abs(s_ref - peaks[version]["Summer"]) < 1e-6 and abs(w_ref - peaks[version]["Winter"]) < 1e-6

    # 2. Monthly curtailment share (New column: Pacific months, clock-change days left out, D22)
    keep = df[~df["curt_excluded"]]
    _, monthly = curtailment_shares(keep, "curt_mwh", "eia_mw", "pacific_start")
    hours = keep["local_start"].dt.tz_localize(None).dt.to_period("M").value_counts()
    for m, v in monthly.sort_index().items():
        rows.append(dict(chart="monthly_curtailment_share", series="new", x=str(m), value=round(v, 1),
                         n=int(hours[m]), note="% curtailed / (curtailed + EIA output), Pacific month of hour "
                         "start, 5 clock-change days left out (D22); n = hours in month; includes test months"))

    # 3. Cloud buckets
    cb = cloud_bucket_rows(df)
    ref_means, ref_n = cloud_buckets(df, "eia_mw")
    assert [round(v, 9) for v in cb["mean"]] == [round(v, 9) for v in ref_means] and cb["count"].sum() == ref_n
    for label, (_, r) in zip(CLOUD_LABELS, cb.iterrows()):
        rows.append(dict(chart="cloud_buckets", series="tv", x=label, value=round(r["mean"], 1), n=int(r["count"]),
                         note="% mean EIA output / capacity (860M, all CISO), hours starting 10-12 Pacific, "
                         "day-2 cloud cover %, training and validation"))

    out = pd.DataFrame(rows, columns=["chart", "series", "x", "value", "n", "note"])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    # Console: peaks and check against capstone2_numbers_corrected.md
    print("Season peaks, mean EIA MW by Pacific hour (rounded to 100 MW)")
    all_ok = True
    for version, label in [("tv", "training and validation"), ("all", "all days")]:
        print(f"  {label}:")
        for s in SEASON_ORDER:
            r = round(peaks[version][s], -2)
            exp = EXPECTED_PEAKS[version].get(s)
            check = "" if exp is None else ("  matches report" if r == exp else f"  MISMATCH, report says {exp:,}")
            all_ok &= exp is None or r == exp
            print(f"    {s:<7} {r:>8,.0f} MW  (unrounded {peaks[version][s]:,.1f}){check}")
    print("All summer and winter peaks match the report." if all_ok else "Some peaks do NOT match the report.")
    print(f"written: {OUT_CSV.relative_to(ROOT).as_posix()} ({len(out)} rows)")


if __name__ == "__main__":
    main()
