"""Fit every candidate on the 4 validation folds and score it (validation only, test locked).

Run from the repo root, after build_hourly_table:
    python -m src.modeling.score_models

Steps: load the table and drop test rows at once; build features (features.py); fit and predict each
fold (models.py, folds from folds.py, layout winter104); save per-hour predictions to
data/processed/oof_predictions.parquet (not committed); score on the D27 common hours.

Metrics (per model and fold, then pooled over all 4 validation blocks):
  nmae_pct        mean |forecast - actual| / capacity_mw, in % (D27)
  rmse_mw, skill_vs_persistence_d2 = 1 - RMSE / RMSE(persistence D-2), skill_vs_caiso_published
  p95_overshoot_mw  95th percentile of max(forecast - actual, 0) over all scored daylight hours
  p95_vs_persistence_d2_pct  percent difference of that against persistence D-2
  p95_undershoot_mw  95th percentile of max(actual - forecast, 0), same hours (and its difference vs D-2)
  mape_pct        on hours with actual above 5% of capacity_mw only (reported, not used to rank)
  bias_mw         mean forecast - actual
Breakdowns: month, season, Pacific hour, day-2 forecast cloud cover (0-10, 10-30, 30-60, 60-100%), and
curtailed hours (curt_mwh above 1% of capacity_mw) versus not, with EIA and EIA + curt_mwh as the
actual. The threshold is relative because curt_mwh is above 0 in 94% of scored hours, and in every
scored hour from 2026-01, when the source switches to the daily report (D26) with small values each hour.

caiso_adjusted is always scored against EIA + curt_mwh (D27); every other forecast against EIA.
Writes reports/model_results_validation.csv (model, fold, metric, group, value, hours).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.modeling.features import assert_tv_only, build_features, load_tv_table
from src.modeling.folds import DEFAULT_LAYOUT, OUT_CSV as FOLDS_CSV, fold_table
from src.modeling.models import REFERENCES, TRAINED, day1_comparison, out_of_fold
from src.processing.build_hourly_table import PROCESSED, ROOT
from src.processing.capstone2_numbers import CLOUD_BINS
from src.processing.score_references import score_frame

OUT_CSV = ROOT / "reports" / "model_results_validation.csv"
OUT_OOF = PROCESSED / "oof_predictions.parquet"
SEASON = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
          6: "summer", 7: "summer", 8: "summer", 9: "fall", 10: "fall", 11: "fall"}
TARGET_FACTOR = 1.25
CURT_SHARE = 0.01            # an hour counts as curtailed when curt_mwh > 1% of capacity_mw
CLOUD_LABELS = ["0-10", "10-30", "30-60", "60-100"]
LAST_CHECK = {"caiso_adjusted": 3.4, "caiso_published": 5.9}   # 1.25 x D27 scores, all training and validation hours
COMPARISONS = {"persistence_d1": "comparison: breaks the 10 a.m. rule", "ridge": "dropped (D30), kept for comparison",
               "climatology": "floor", "hgb": "carried forward (D30)"}
CARRY = "hgb"


def metrics(g: pd.DataFrame, model: str, actual_col: str | None = None) -> dict[str, float]:
    a = g[actual_col or ("actual_adjusted" if model == "caiso_adjusted" else "actual")]
    err = g[model] - a
    big = a > 0.05 * g["capacity_mw"]
    out = {"nmae_pct": (err.abs() / g["capacity_mw"]).mean() * 100,
           "mae_mw": err.abs().mean(), "rmse_mw": np.sqrt((err ** 2).mean()), "bias_mw": err.mean(),
           "p95_overshoot_mw": err.clip(lower=0).quantile(0.95),
           "p95_undershoot_mw": (-err).clip(lower=0).quantile(0.95),
           "mape_pct": (err[big].abs() / a[big]).mean() * 100}
    if actual_col is None:
        for ref in ("persistence_d2", "caiso_published"):
            ref_rmse = np.sqrt(((g[ref] - g["actual"]) ** 2).mean())
            out[f"skill_vs_{ref}"] = 1 - out["rmse_mw"] / ref_rmse
        p2_err = g["persistence_d2"] - g["actual"]
        out["p95_vs_persistence_d2_pct"] = (out["p95_overshoot_mw"] / p2_err.clip(lower=0).quantile(0.95) - 1) * 100
        out["p95_undershoot_vs_persistence_d2_pct"] = (out["p95_undershoot_mw"]
                                                       / (-p2_err).clip(lower=0).quantile(0.95) - 1) * 100
    return out


def long_rows(scored: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    rows = []

    def add(model, fold, group, g, actual_col=None, keep=None):
        for k, v in metrics(g, model, actual_col).items():
            if keep is None or k in keep:
                rows.append(dict(model=model, fold=fold, metric=k, group=group, value=round(float(v), 4), hours=len(g)))

    month = scored["local_start"].dt.strftime("%Y-%m")
    season = scored["local_start"].dt.month.map(SEASON)
    hour = scored["local_start"].dt.hour
    curt = np.where(scored["curt_mwh"] > CURT_SHARE * scored["capacity_mw"], "yes", "no")
    cloud = pd.cut(scored["cloud_cover_previous_day2"], CLOUD_BINS, labels=CLOUD_LABELS).astype(str)
    brief = ["nmae_pct", "bias_mw", "rmse_mw"]
    for model in models:
        for fold, g in [("pooled", scored)] + [(str(k), x) for k, x in scored.groupby("fold")]:
            add(model, fold, "all", g)
        for key, s in [("month", month), ("season", season), ("hour", hour), ("cloud_d2", cloud)]:
            for val, g in scored.groupby(s):
                add(model, "pooled", f"{key}={val}", g, keep=brief)
        for val, g in scored.groupby(curt):
            add(model, "pooled", f"curtailed={val}|actual=eia", g, "actual", keep=brief)
            add(model, "pooled", f"curtailed={val}|actual=eia_plus_curt", g, "actual_adjusted", keep=brief)
    return pd.DataFrame(rows)


def main() -> None:
    print("VALIDATION ONLY, TEST LOCKED (no row with a Pacific date from 2026-04-10 is read past load)\n")
    df = load_tv_table()
    assert_tv_only(df, "score_models")
    feat = build_features(df)
    refs = score_frame(df, "d14", "clipped")
    folds = fold_table(DEFAULT_LAYOUT)
    if FOLDS_CSV.exists():
        saved = pd.read_csv(FOLDS_CSV)
        if not (saved["val_start"].tolist() == folds["val_start"].astype(str).tolist()
                and saved["val_end"].tolist() == folds["val_end"].astype(str).tolist()):
            raise SystemExit(f"{FOLDS_CSV} does not match layout {DEFAULT_LAYOUT}; run python -m src.modeling.folds")

    print(f"Fitting on {len(folds)} folds (layout {DEFAULT_LAYOUT}); choices made on the inner split only:")
    oof, log = out_of_fold(feat, refs, folds)
    for c in ["actual", "actual_adjusted", "capacity_mw", "common"]:
        oof[c] = refs.loc[oof.index, c]
    oof["local_start"] = df.loc[oof.index, "local_start"]
    oof["curt_mwh"] = df.loc[oof.index, "curt_mwh"]
    oof["cloud_cover_previous_day2"] = df.loc[oof.index, "cloud_cover_previous_day2"]
    scored = oof[oof["common"]]
    assert_tv_only(scored, "scoring")

    pick = min(["ridge", "hgb"], key=lambda m: metrics(scored, m)["nmae_pct"])
    day1, log1 = day1_comparison(feat, folds, pick)
    oof[f"{pick}_day1"] = day1
    scored = oof[oof["common"]]
    if scored[REFERENCES + TRAINED + [f"{pick}_day1"]].isna().any().any():
        raise ValueError("a forecast is blank on a common hour")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    oof.to_parquet(OUT_OOF)

    models = REFERENCES + TRAINED + [f"{pick}_day1"]
    res = long_rows(scored, models)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT_CSV, index=False)

    pooled = res[(res["fold"] == "pooled") & (res["group"] == "all")].pivot(index="model", columns="metric", values="value")
    pooled = pooled.loc[models]
    adj, pub = pooled.loc["caiso_adjusted", "nmae_pct"], pooled.loc["caiso_published", "nmae_pct"]
    t_adj, t_pub = TARGET_FACTOR * adj, TARGET_FACTOR * pub
    days = scored["local_start"].dt.date.nunique()
    print(f"\nPooled over the 4 validation blocks: {len(scored):,} common hours (D27) on {days} days")
    print(f"nMAE targets on these hours: 1.25 x CAISO adjusted = {t_adj:.2f}%, 1.25 x CAISO as published = {t_pub:.2f}% "
          f"(last check on all training and validation hours: {LAST_CHECK['caiso_adjusted']}% and "
          f"{LAST_CHECK['caiso_published']}%)")
    print("Skill target at least 0.30 vs persistence D-2; P95 overshoot target at least 20% below persistence D-2\n")
    yn = lambda b: "pass" if b else "fail"
    lines = []
    for m in models:
        r = pooled.loc[m]
        label = COMPARISONS.get(m, "comparison: day-1 weather, breaks the 10 a.m. rule" if m.endswith("_day1")
                                else "reference" if m in REFERENCES else "")
        lines.append(dict(model=m, nMAE=f"{r.nmae_pct:.2f}%", skill_P2=f"{r.skill_vs_persistence_d2:.3f}",
                          skill_CAISO=f"{r.skill_vs_caiso_published:.3f}", P95_over_MW=f"{r.p95_overshoot_mw:,.0f}",
                          over_vs_P2=f"{r.p95_vs_persistence_d2_pct:+.1f}%",
                          P95_under_MW=f"{r.p95_undershoot_mw:,.0f}",
                          under_vs_P2=f"{r.p95_undershoot_vs_persistence_d2_pct:+.1f}%", MAPE=f"{r.mape_pct:.1f}%",
                          bias_MW=f"{r.bias_mw:+,.0f}",
                          t_adj=yn(r.nmae_pct <= t_adj), t_pub=yn(r.nmae_pct <= t_pub),
                          t_skill=yn(r.skill_vs_persistence_d2 >= 0.30), t_P95=yn(r.p95_vs_persistence_d2_pct <= -20),
                          note=label))
    with pd.option_context("display.width", 250, "display.max_columns", 20):
        print(pd.DataFrame(lines).to_string(index=False))

    print("\nPer fold nMAE (%):")
    per = res[(res["metric"] == "nmae_pct") & (res["group"] == "all")].pivot(index="model", columns="fold", values="value")
    hrs = res[(res["metric"] == "nmae_pct") & (res["group"] == "all") & (res["model"] == "persistence_d2")]
    print(per.loc[models].round(2).to_string())
    print("hours: " + ", ".join(f"fold {f} {h:,}" for f, h in zip(hrs["fold"], hrs["hours"])))

    print(f"\n{CARRY} against the nMAE targets, fold by fold (targets from CAISO on the same fold hours):")
    fl = []
    for f in ["1", "2", "3", "4", "pooled"]:
        h, p, a = per.loc[CARRY, f], per.loc["caiso_published", f], per.loc["caiso_adjusted", f]
        fl.append(dict(fold=f, nMAE=f"{h:.2f}%", t_pub=f"{TARGET_FACTOR * p:.2f}%", within_pub=yn(h <= TARGET_FACTOR * p),
                       t_adj=f"{TARGET_FACTOR * a:.2f}%", within_adj=yn(h <= TARGET_FACTOR * a)))
    print(pd.DataFrame(fl).to_string(index=False))

    show = ["persistence_d2", "caiso_published", CARRY]
    for prefix, title in [("cloud_d2=", "day-2 forecast cloud cover (%)"),
                          ("curtailed=", f"curtailed hours (curt_mwh above {CURT_SHARE:.0%} of capacity_mw)")]:
        x = res[(res["fold"] == "pooled") & res["group"].str.startswith(prefix) & res["metric"].isin(["nmae_pct", "bias_mw"])]
        t = x.pivot_table(index="group", columns=["metric", "model"], values="value")
        t = pd.concat({"nMAE %": t["nmae_pct"][show].round(2), "bias MW": t["bias_mw"][show].round(0)}, axis=1)
        t[("hours", "")] = x[(x["model"] == CARRY) & (x["metric"] == "nmae_pct")].set_index("group")["hours"]
        if prefix == "cloud_d2=":
            t = t.reindex([f"{prefix}{c}" for c in CLOUD_LABELS])
        print(f"\nBy {title}, pooled:")
        with pd.option_context("display.width", 200):
            print(t.to_string())
    print(f"\nwritten: {OUT_CSV.relative_to(ROOT).as_posix()} ({len(res):,} rows); "
          f"{OUT_OOF.relative_to(ROOT).as_posix()} (not committed)")


if __name__ == "__main__":
    main()
