"""The one run on the locked test set (Brief 4, Task C). Frozen spec: reports/final_model_spec.md.

    python -m src.modeling.final_test                dry run: refits on the 763 training and validation
                                                     days and checks the frozen settings; reads no test row
    python -m src.modeling.final_test --final-test   the test run, once (refuses to run a second time)

Refit: HGB, ridge and climatology on all fit rows of Pacific dates 2024-03-08 to 2026-04-09. Settings
come from the inner split as in Brief 3: the last 10% of those days (76 days, 2026-01-24 to
2026-04-09) after a 1-day gap, the same grids and seed (models.py). The chosen settings must equal
FROZEN below, or the run stops before any test row is read.

Scoring: the test period (Pacific dates 2026-04-10 to 2026-10-17) under D27: daylight, EIA, CAISO
day-ahead and both persistence values present, outside wx_gap (D17), curt_mwh not null. Forecasts:
hgb, ridge, climatology, persistence_d2, persistence_d1, caiso_published, caiso_adjusted. Writes
reports/final_results_test.csv and data/processed/test_predictions.parquet (not committed).
"""

from __future__ import annotations

import argparse
import subprocess

import numpy as np
import pandas as pd

from src.modeling.features import MAIN_FEATURES, assert_no_leak, assert_tv_only, build_features, load_tv_table
from src.modeling.models import (SEED, fit_climatology, hgb_model, ridge_model, tune_hgb, tune_ridge)
from src.modeling.score_models import CLOUD_LABELS, CURT_SHARE, TARGET_FACTOR, long_rows, metrics
from src.processing.build_hourly_table import OUT_TABLE, PROCESSED, ROOT, TEST_START
from src.processing.score_references import score_frame

OUT_CSV = ROOT / "reports" / "final_results_test.csv"
OUT_PRED = PROCESSED / "test_predictions.parquet"
SPEC = ROOT / "reports" / "final_model_spec.md"
FIRST_DAY, LAST_DAY = pd.Timestamp("2024-03-08"), pd.Timestamp("2026-04-09")
INNER_SHARE, GAP_DAYS = 0.10, 1
MODELS = ["hgb", "ridge", "climatology", "persistence_d2", "persistence_d1", "caiso_published", "caiso_adjusted"]
FROZEN_PATHS = ["src/modeling", "src/processing", "reports/final_model_spec.md", "reports/hypotheses.md"]

# Settings chosen on the inner split by the dry run on 2026-11-07 (reports/final_model_spec.md).
FROZEN = {"hgb": {"max_depth": 5, "loss": "absolute_error", "max_iter": 86}, "ridge": {"alpha": 100.0}}


def final_masks(local_start: pd.Series) -> dict[str, pd.Series]:
    """Training (763 days), inner fit and inner validation masks by Pacific date of the hour start."""
    day = local_start.dt.tz_localize(None).dt.normalize()
    n_days = (LAST_DAY - FIRST_DAY).days + 1
    inner_days = round(n_days * INNER_SHARE)
    inner_start = LAST_DAY - pd.Timedelta(days=inner_days - 1)
    inner_fit_end = inner_start - pd.Timedelta(days=GAP_DAYS + 1)
    train = (day >= FIRST_DAY) & (day <= LAST_DAY)
    return {"train": train, "inner_fit": (day >= FIRST_DAY) & (day <= inner_fit_end),
            "inner_val": (day >= inner_start) & (day <= LAST_DAY),
            "dates": (n_days, inner_days, inner_start.date(), inner_fit_end.date())}


def fit_final(feat_tv: pd.DataFrame):
    """Fit hgb, ridge and climatology on training and validation days only. Returns predictors and settings."""
    assert_tv_only(feat_tv, "fit_final")
    assert_no_leak(feat_tv[MAIN_FEATURES])
    m = final_masks(feat_tv["local_start"])
    fit = feat_tv["fit_row"]
    tr, i_fit, i_val = m["train"] & fit, m["inner_fit"] & fit, m["inner_val"] & fit
    X, y = feat_tv[MAIN_FEATURES], feat_tv["cf"]
    hgb_params, hgb_log = tune_hgb(X[i_fit], y[i_fit], X[i_val], y[i_val])
    alpha, ridge_log = tune_ridge(X[i_fit], y[i_fit], X[i_val], y[i_val])
    hgb = hgb_model(hgb_params).fit(X[tr], y[tr])
    ridge = ridge_model(alpha).fit(X[tr], y[tr])
    month = feat_tv["local_start"].dt.month
    clim = fit_climatology(X[tr], y[tr], month[tr])
    n_days, inner_days, inner_start, inner_fit_end = m["dates"]
    settings = {"hgb": hgb_params, "ridge": {"alpha": alpha}}
    info = dict(train_days=n_days, train_rows=int(tr.sum()), inner_days=inner_days, inner_val_start=str(inner_start),
                inner_fit_end=str(inner_fit_end), inner_fit_rows=int(i_fit.sum()), inner_val_rows=int(i_val.sum()),
                hgb_inner=hgb_log, ridge_inner=ridge_log)

    def predict(feat: pd.DataFrame) -> pd.DataFrame:
        Xp = feat[MAIN_FEATURES]
        out = pd.DataFrame(index=feat.index)
        out["hgb"] = np.clip(hgb.predict(Xp), 0, 1)
        out["ridge"] = np.clip(ridge.predict(Xp), 0, 1)
        out["climatology"] = np.clip(clim(Xp, feat["local_start"].dt.month), 0, 1)
        return out.mul(feat["capacity_mw"], axis=0)
    return predict, settings, info


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def print_fit(settings, info) -> None:
    print(f"Refit on {info['train_days']} days ({info['train_rows']:,} fit rows); inner split: last "
          f"{info['inner_days']} days from {info['inner_val_start']} ({info['inner_val_rows']:,} rows), "
          f"inner fit to {info['inner_fit_end']} ({info['inner_fit_rows']:,} rows); seed {SEED}")
    print("  hgb inner nMAE (%) and best iteration: " + ", ".join(
        f"depth {d} {l}: {s * 100:.3f} at {it}" for (d, l), (s, it) in info["hgb_inner"].items()))
    print("  ridge inner nMAE (%): " + ", ".join(f"alpha {a}: {s * 100:.3f}" for a, s in info["ridge_inner"].items()))
    print(f"  chosen: hgb {settings['hgb']}, ridge {settings['ridge']}")
    same = settings == FROZEN
    print(f"  matches FROZEN: {'yes' if same else 'NO'}")
    if not same:
        raise SystemExit("settings differ from FROZEN; stop before any test row is read")


def hypotheses(res: pd.DataFrame) -> None:
    g = lambda m, k, grp="all": float(res[(res["model"] == m) & (res["metric"] == k) & (res["group"] == grp)]["value"].iloc[0])
    pub, adj = g("caiso_published", "nmae_pct"), g("caiso_adjusted", "nmae_pct")
    h = g("hgb", "nmae_pct")
    v = lambda ok: "supported" if ok else "not supported"
    print("\nPre-registered hypotheses (reports/hypotheses.md), test numbers:")
    print(f"  H1 skill vs persistence D-2 >= 0.30: {g('hgb', 'skill_vs_persistence_d2'):.3f} -> "
          f"{v(g('hgb', 'skill_vs_persistence_d2') >= 0.30)}")
    p_ok, a_ok = h <= TARGET_FACTOR * pub, h <= TARGET_FACTOR * adj
    h2 = "supported" if p_ok and a_ok else "partly supported" if p_ok else "not supported"
    print(f"  H2 nMAE {h:.2f}% vs 1.25 x CAISO as published {TARGET_FACTOR * pub:.2f}% (primary: {'met' if p_ok else 'missed'}) "
          f"and 1.25 x CAISO adjusted {TARGET_FACTOR * adj:.2f}% (secondary, partly circular: {'met' if a_ok else 'missed'}) -> {h2}")
    r = g("ridge", "nmae_pct")
    print(f"  H3 hgb nMAE below ridge's: {h:.2f}% vs {r:.2f}% -> {v(h < r)}")
    lo, hi = g("hgb", "nmae_pct", "cloud_d2=0-10"), g("hgb", "nmae_pct", "cloud_d2=60-100")
    print(f"  H4 hgb nMAE 60-100% cloud above 0-10%: {hi:.2f}% vs {lo:.2f}% ({hi - lo:+.2f} points) -> {v(hi > lo)}")
    p95 = g("hgb", "p95_vs_persistence_d2_pct")
    print(f"  H5 P95 overshoot at least 20% below persistence D-2: {p95:+.1f}% -> {v(p95 <= -20)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--final-test", action="store_true", help="score the locked test set (run once)")
    args = ap.parse_args()

    if not args.final_test:
        print("DRY RUN, no test row is read (add --final-test for the one test run)\n")
        feat_tv = build_features(load_tv_table())
        _, settings, info = fit_final(feat_tv)
        print_fit(settings, info)
        return

    print("REFERENCE FORECASTS AND MODELS, TEST RUN 1 OF 1\n")
    if OUT_CSV.exists():
        raise SystemExit(f"{OUT_CSV.relative_to(ROOT).as_posix()} exists: the test set has already been scored once")
    dirty = git("status", "--porcelain", "--", *FROZEN_PATHS)
    if dirty:
        raise SystemExit("frozen code or spec has uncommitted changes; commit them before the test run:\n" + dirty)
    print(f"code version: {git('rev-parse', '--short', 'HEAD')} (frozen spec: {SPEC.relative_to(ROOT).as_posix()})")

    df = pd.read_parquet(OUT_TABLE)
    tv = df[df["local_start"] < TEST_START]
    predict, settings, info = fit_final(build_features(tv))      # fitted on training and validation days only
    print_fit(settings, info)

    feat = build_features(df, allow_test=True)
    test = df["local_start"] >= TEST_START
    refs = score_frame(df[test], "d14", "clipped")
    pred = predict(feat[test & df["daylight"]])
    out = refs.loc[pred.index, ["local_start", "actual", "actual_adjusted", "capacity_mw", "common",
                                "persistence_d2", "persistence_d1", "caiso_published", "caiso_adjusted"]].join(pred)
    out["curt_mwh"] = df.loc[out.index, "curt_mwh"]
    out["cloud_cover_previous_day2"] = df.loc[out.index, "cloud_cover_previous_day2"]
    out["fold"] = "test"
    scored = out[out["common"]]
    if scored[MODELS].isna().any().any():
        raise ValueError("a forecast is blank on a common test hour")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PRED)

    res = long_rows(scored, MODELS)
    res = res[res["fold"] != "test"].assign(fold="test_pooled")
    res.to_csv(OUT_CSV, index=False)

    pooled = res[res["group"] == "all"].pivot(index="model", columns="metric", values="value").loc[MODELS]
    pub, adj = pooled.loc["caiso_published", "nmae_pct"], pooled.loc["caiso_adjusted", "nmae_pct"]
    print(f"\nTest hours scored (D27 common): {len(scored):,} on {scored['local_start'].dt.date.nunique()} days, "
          f"{scored['local_start'].min():%Y-%m-%d} to {scored['local_start'].max():%Y-%m-%d}")
    print(f"nMAE targets: 1.25 x CAISO as published = {TARGET_FACTOR * pub:.2f}% (primary), "
          f"1.25 x CAISO adjusted = {TARGET_FACTOR * adj:.2f}% (secondary, partly circular, D27)\n")
    cols = {"nmae_pct": "nMAE %", "skill_vs_persistence_d2": "skill_P2", "skill_vs_caiso_published": "skill_CAISO",
            "p95_overshoot_mw": "P95_over_MW", "p95_vs_persistence_d2_pct": "over_vs_P2_%",
            "p95_undershoot_mw": "P95_under_MW", "p95_undershoot_vs_persistence_d2_pct": "under_vs_P2_%",
            "mape_pct": "MAPE %", "bias_mw": "bias_MW"}
    with pd.option_context("display.width", 220):
        print(pooled[list(cols)].rename(columns=cols).round(3).to_string())
    for prefix, title in [("cloud_d2=", "day-2 cloud cover"), ("month=", "month"),
                          ("curtailed=", f"curtailment (above {CURT_SHARE:.0%} of capacity_mw)")]:
        x = res[res["group"].str.startswith(prefix) & (res["metric"] == "nmae_pct")]
        t = x.pivot_table(index="group", columns="model", values="value")[MODELS].round(2)
        t["hours"] = x[x["model"] == "hgb"].set_index("group")["hours"]
        if prefix == "cloud_d2=":
            t = t.reindex([f"{prefix}{c}" for c in CLOUD_LABELS])
        print(f"\nnMAE (%) by {title}:")
        with pd.option_context("display.width", 220):
            print(t.to_string())
    hypotheses(res)
    print(f"\nwritten: {OUT_CSV.relative_to(ROOT).as_posix()} ({len(res):,} rows); "
          f"{OUT_PRED.relative_to(ROOT).as_posix()} (not committed)")


if __name__ == "__main__":
    main()
