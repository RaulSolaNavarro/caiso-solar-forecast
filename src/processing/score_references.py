"""Score the 4 reference forecasts (FAQ Decision D27) on the processed hourly table.

Run from the repo root, after build_hourly_table:
    python -m src.processing.score_references              training and validation days only
    python -m src.processing.score_references --with-test  also the locked test set
                                                           (reference forecasts only, models never)

Metric: normalized MAE = mean over the scored hours of |forecast - actual| / capacity_mw of that
hour, in %. capacity_mw is EIA 860M monthly nameplate, all CISO (D18, D19).

References:
  persistence_d1   EIA at hour ending t - 24 h (uses information after the 10 a.m. bid close)
  persistence_d2   EIA at hour ending t - 48 h (the fair one for the 10 a.m. rule)
  caiso_published  CAISO day-ahead (NP15 + SP15 + ZP26) against EIA
  caiso_adjusted   CAISO day-ahead against EIA + curt_mwh

Hours: `scorable` from the table (daylight, EIA, CAISO day-ahead, no wx_gap), recomputed for each
EIA rule, plus both persistence values present.
  hours_set = "common"        also curt_mwh not null; the same hours for all 4 (headline, D27)
  hours_set = "per_reference" only caiso_adjusted drops the curt_mwh-null hours (brief-literal)

Variants: rule = d14 (team rule) or blanket (old 1-hour rule, for comparison);
eia_variant = clipped (negatives set to 0, D15; headline) or raw (as published);
divisor = all_ciso (headline) or ca_only (the California-only check, D18).

Writes reports/reference_scores.csv (training and validation rows, every run, the same file each
time). With --with-test it also writes reports/reference_scores_test.csv (test rows only). Without
--with-test the test rows are dropped right after loading and the test file is not touched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.processing.build_hourly_table import OUT_TABLE, ROOT, TEST_START, align_eia, load_eia_labels

OUT_CSV = ROOT / "reports" / "reference_scores.csv"
OUT_CSV_TEST = ROOT / "reports" / "reference_scores_test.csv"
REFERENCES = ["persistence_d1", "persistence_d2", "caiso_published", "caiso_adjusted"]
DAY = pd.Timedelta(hours=24)


def load_table(with_test: bool) -> pd.DataFrame:
    if not OUT_TABLE.exists():
        raise SystemExit(f"{OUT_TABLE} not found. Run: python -m src.processing.build_hourly_table")
    df = pd.read_parquet(OUT_TABLE)
    if not with_test:
        df = df[df["local_start"] < TEST_START]          # test rows are never looked at below
    return df


def score_frame(df: pd.DataFrame, rule: str, eia_variant: str, eia_labels: pd.Series | None = None) -> pd.DataFrame:
    """Per-hour actual, forecasts and masks for one EIA rule and variant.

    The EIA series comes from the raw file through align_eia, so persistence has history before
    the window starts. For rule d14 and the clipped variant the actual equals the table's eia_mw.
    """
    eia = align_eia(eia_labels, rule=rule)
    if eia_variant == "clipped":
        eia = eia.clip(lower=0)
    elif eia_variant != "raw":
        raise ValueError(eia_variant)
    idx = df.index
    out = pd.DataFrame(index=idx)
    out["local_start"] = df["local_start"]
    out["actual"] = eia.reindex(idx).values
    out["persistence_d1"] = eia.reindex(idx - DAY).values
    out["persistence_d2"] = eia.reindex(idx - 2 * DAY).values
    out["caiso_published"] = df["caiso_dam_mw"]
    out["caiso_adjusted"] = df["caiso_dam_mw"]
    out["actual_adjusted"] = out["actual"] + df["curt_mwh"]
    out["capacity_mw"] = df["capacity_mw"]
    out["capacity_ca_mw"] = df["capacity_ca_mw"]
    base = (df["daylight"] & out["actual"].notna() & df["caiso_dam_mw"].notna() & ~df["wx_gap"]
            & out["persistence_d1"].notna() & out["persistence_d2"].notna())
    out["base"] = base
    out["common"] = base & df["curt_mwh"].notna()
    if rule == "d14" and eia_variant == "clipped":
        same = np.allclose(out["actual"], df["eia_mw"], equal_nan=True)
        if not same or not (df["scorable"] == (df["daylight"] & df["eia_mw"].notna() & df["caiso_dam_mw"].notna()
                                               & ~df["wx_gap"])).all():
            raise ValueError("align_eia(d14) disagrees with the table's eia_mw or scorable")
    return out


def nmae_rows(f: pd.DataFrame, period: str, rule: str, eia_variant: str, hours_set: str,
              divisor: str = "all_ciso") -> list[dict]:
    cap_col = "capacity_mw" if divisor == "all_ciso" else "capacity_ca_mw"
    rows = []
    for ref in REFERENCES:
        if hours_set == "common":
            m = f["common"]
        else:
            m = f["common"] if ref == "caiso_adjusted" else f["base"]
        g = f[m]
        actual = g["actual_adjusted"] if ref == "caiso_adjusted" else g["actual"]
        err = g[ref] - actual
        rows.append(dict(period=period, rule=rule, eia_variant=eia_variant, hours_set=hours_set, divisor=divisor,
                         reference=ref, hours=int(len(g)), days=int(g["local_start"].dt.date.nunique()),
                         nmae_pct=round(float((err.abs() / g[cap_col]).mean() * 100), 3),
                         mae_mw=round(float(err.abs().mean()), 1), bias_mw=round(float(err.mean()), 1)))
    return rows


def all_scores(df: pd.DataFrame, with_test: bool) -> pd.DataFrame:
    labels = load_eia_labels()
    periods = {"train_val": df["local_start"] < TEST_START}
    if with_test:
        periods["test"] = df["local_start"] >= TEST_START
    rows = []
    for rule in ("d14", "blanket"):
        for variant in ("clipped", "raw"):
            f = score_frame(df, rule, variant, labels)
            for period, pm in periods.items():
                for hs in ("common", "per_reference"):
                    rows += nmae_rows(f[pm], period, rule, variant, hs)
                if rule == "d14" and variant == "clipped":
                    rows += nmae_rows(f[pm], period, rule, variant, "common", divisor="ca_only")
    return pd.DataFrame(rows)


def show(scores: pd.DataFrame) -> None:
    wide = scores.pivot_table(index=["period", "divisor", "hours_set", "eia_variant", "rule"],
                              columns="reference", values="nmae_pct")[REFERENCES]
    hours = scores.pivot_table(index=["period", "divisor", "hours_set", "eia_variant", "rule"],
                               columns="reference", values="hours")
    wide.insert(0, "hours", hours.apply(lambda r: "/".join(str(int(v)) for v in r.unique()), axis=1))
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(wide.to_string())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--with-test", action="store_true",
                    help="also score the locked test set (reference forecasts only, models never)")
    args = ap.parse_args()

    df = load_table(args.with_test)
    scores = all_scores(df, args.with_test)

    print("Normalized MAE (% of EIA 860M nameplate, all CISO unless divisor = ca_only), daylight hours")
    print("hours column: one number when all 4 references use the same hours; otherwise the distinct counts\n")
    print("=== Training and validation (Pacific dates before 2026-04-10)")
    show(scores[scores["period"] == "train_val"])
    if args.with_test:
        print("\n=== Locked test set, 2026-04-10 to 2026-10-17: reference forecasts only, models never")
        show(scores[scores["period"] == "test"])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    tv = scores[scores["period"] == "train_val"]
    tv.to_csv(OUT_CSV, index=False)
    print(f"\nwritten: {OUT_CSV.relative_to(ROOT).as_posix()} ({len(tv)} rows, training and validation)")
    if args.with_test:
        test = scores[scores["period"] == "test"]
        test.to_csv(OUT_CSV_TEST, index=False)
        print(f"written: {OUT_CSV_TEST.relative_to(ROOT).as_posix()} ({len(test)} rows, test; "
              f"reference forecasts only, models never)")


if __name__ == "__main__":
    main()
