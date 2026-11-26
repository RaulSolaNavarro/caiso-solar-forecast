"""Shared loaders and the reproduction checks for Brief 9 (post-hoc checks, not pre-registered tests).

Run from the repo root:
    python -m src.evidence.common

Loads the saved out-of-fold validation predictions and the saved test predictions (the way
src/modeling/reserve.py does), keeps the D27 common hours, and checks that the existing headline
numbers come back. Stops with an error if any nMAE differs by more than 0.01 points or any reserve
figure differs from reports/reserve_test.csv.
"""

from __future__ import annotations

import pandas as pd

from src.modeling.reserve import RESULTS, OUT_CSV as RESERVE_CSV, fleet_mw, reserve_table
from src.modeling.score_models import CURT_SHARE, OUT_OOF, metrics
from src.processing.build_hourly_table import PROCESSED, ROOT

TEST_PRED = PROCESSED / "test_predictions.parquet"
LABEL = "post-hoc check, not a pre-registered test"
TOL = 0.01   # points of nMAE (Brief 9)
MODELS = {"hgb": "HGB (our model)", "caiso_published": "CAISO as published", "caiso_adjusted": "CAISO adjusted",
          "persistence_d2": "Persistence D-2", "ridge": "Ridge"}
N_VAL, N_TEST = 4508, 2457


def load_val() -> pd.DataFrame:
    oof = pd.read_parquet(OUT_OOF)
    v = oof[oof["common"]].copy()
    if len(v) != N_VAL:
        raise SystemExit(f"validation common hours: {len(v)}, expected {N_VAL}")
    return v


def load_test() -> pd.DataFrame:
    if not TEST_PRED.exists():
        raise SystemExit(f"{TEST_PRED} not found (written by the one test run; do not rerun it)")
    pred = pd.read_parquet(TEST_PRED)
    t = pred[pred["common"]].copy()
    if len(t) != N_TEST:
        raise SystemExit(f"test common hours: {len(t)}, expected {N_TEST}")
    return t


def curtailed(df: pd.DataFrame) -> pd.Series:
    """D30 threshold: an hour is curtailed when curt_mwh is above 1% of capacity_mw."""
    if df["curt_mwh"].isna().any():
        raise SystemExit("curt_mwh has blanks in scored hours")
    return df["curt_mwh"] > CURT_SHARE * df["capacity_mw"]


def nmae(df: pd.DataFrame, model: str) -> float:
    return float(metrics(df, model)["nmae_pct"])


def reproduce() -> None:
    v, t = load_val(), load_test()
    fails: list[str] = []
    rows: list[tuple[str, float, float]] = []

    def check(name: str, got: float, want: float, tol: float = TOL) -> None:
        rows.append((name, got, want))
        if abs(got - want) > tol:
            fails.append(f"{name}: recomputed {got:.4f}, existing {want:.4f}")

    check("HGB pooled validation nMAE %", nmae(v, "hgb"), 4.02, 0.005 + TOL)
    for k, want in zip([1, 2, 3, 4], [4.60, 3.12, 3.91, 4.47]):
        check(f"HGB fold {k} nMAE %", nmae(v[v["fold"] == k], "hgb"), want, 0.005 + TOL)

    cut = curtailed(v)
    n_no, n_yes = int((~cut).sum()), int(cut.sum())
    if (n_no, n_yes) != (2344, 2164):
        fails.append(f"curtailment split hours: {n_no} not curtailed, {n_yes} curtailed; expected 2,344 and 2,164")
    for grp, mask, c, h in [("not curtailed", ~cut, 2.97, 3.58), ("curtailed", cut, 6.17, 4.51)]:
        check(f"CAISO as published, {grp} ({int(mask.sum()):,} h) nMAE %", nmae(v[mask], "caiso_published"), c, 0.005 + TOL)
        check(f"HGB, {grp} ({int(mask.sum()):,} h) nMAE %", nmae(v[mask], "hgb"), h, 0.005 + TOL)

    saved = pd.read_csv(RESERVE_CSV)
    redo = reserve_table(t, fleet_mw())
    for q in ["P90", "P95", "P99"]:
        pick = lambda d: d[(d["model"] == "hgb") & (d["season"] == "all") & (d["quantile"] == q)].iloc[0]
        a, b = pick(redo), pick(saved)
        for col in ["overshoot_mw_test", "mw_today_fleet"]:
            check(f"HGB reserve {q} {col} (MW)", float(a[col]), float(b[col]), 0.0)

    res = pd.read_csv(RESULTS)
    saved_test = float(res[(res["model"] == "hgb") & (res["metric"] == "nmae_pct") & (res["group"] == "all")]["value"].iloc[0])
    check("HGB test nMAE % (saved predictions vs final_results_test.csv)", nmae(t, "hgb"), saved_test)

    print(f"Reproduction checks: validation {len(v):,} hours, test {len(t):,} hours (saved predictions)\n")
    w = max(len(r[0]) for r in rows)
    for name, got, want in rows:
        ok = "ok" if abs(got - want) <= (0.0 if "reserve" in name else TOL + 0.005) else "DIFFERS"
        print(f"  {name:<{w}}  recomputed {got:>9.4f}   existing {want:>9.2f}   {ok}")
    if fails:
        print("\nSTOP: a recomputed value differs from the existing one:")
        for f in fails:
            print("  " + f)
        raise SystemExit(1)
    print("\nAll reproduction checks passed.")


if __name__ == "__main__":
    reproduce()
