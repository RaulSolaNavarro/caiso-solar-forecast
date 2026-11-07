"""Where the one test run differs from validation (Brief 4, summary item 4), from saved results only.

    python -m src.modeling.test_vs_validation

Compares nMAE for every forecast and group: pooled, season, Pacific hour, day-2 cloud bucket, curtailment,
and month of year (validation 2025-03 to 2026-04 against test 2026-04 to 2026-10; months that occur in
both are combined, hour-weighted). Writes reports/test_vs_validation.csv with every comparison and a
flag for differences above 0.5 points.
"""

from __future__ import annotations

import pandas as pd

from src.processing.build_hourly_table import ROOT

OUT_CSV = ROOT / "reports" / "test_vs_validation.csv"
MODELS = ["hgb", "ridge", "climatology", "persistence_d2", "persistence_d1", "caiso_published", "caiso_adjusted"]
THRESHOLD = 0.5


def collapse(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    d = df.copy()
    d["group"] = d["group"].where(~d["group"].str.startswith("month="), "month_of_year=" + d["group"].str[-2:])
    g = d.groupby(["model", "group"])
    return pd.DataFrame({value_name: g.apply(lambda x: (x["value"] * x["hours"]).sum() / x["hours"].sum(),
                                             include_groups=False),
                         f"{value_name}_hours": g["hours"].sum()}).reset_index()


def main() -> None:
    v = pd.read_csv(ROOT / "reports" / "model_results_validation.csv")
    t = pd.read_csv(ROOT / "reports" / "final_results_test.csv")
    v = v[(v["fold"] == "pooled") & (v["metric"] == "nmae_pct") & v["model"].isin(MODELS)]
    t = t[(t["metric"] == "nmae_pct") & t["model"].isin(MODELS)]
    m = collapse(v, "validation").merge(collapse(t, "test"), on=["model", "group"])
    m["diff_points"] = m["test"] - m["validation"]
    m["above_0_5"] = m["diff_points"].abs() > THRESHOLD
    m = m.round({"validation": 3, "test": 3, "diff_points": 3})
    m.to_csv(OUT_CSV, index=False)
    print(f"{len(m)} comparisons, {int(m['above_0_5'].sum())} differ by more than {THRESHOLD} points")
    print(m[m["above_0_5"]].groupby("model").size().to_string())
    print(f"written: {OUT_CSV.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
