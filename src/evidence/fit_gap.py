"""Brief 9, Tasks 2a and 2d: training error against out-of-sample error, and fold spread
(training and validation rows only; post-hoc check, not a pre-registered test).

Run from the repo root:
    python -m src.evidence.fit_gap

2a. For each D29 fold, HGB is tuned and refitted as models.run_fold does (tune_hgb on the inner split,
    hgb_model refitted on the fold's training fit rows). nMAE is reported on the training fit rows
    (in-sample), on the training fit rows that are also D27 common hours, and on the fold's scored
    validation hours. The validation predictions must equal the saved out-of-fold predictions.
    Then the frozen settings (max_depth 5, absolute_error, 86 iterations, the rest HGB_FIXED; spec in
    reports/final_model_spec.md) are refitted on the 763 training and validation days (9,187 fit rows)
    and scored in-sample (rows selected with final_test.final_masks, as in the spec). The test nMAE is read from reports/final_results_test.csv; no test row is loaded.
2d. From reports/model_results_validation.csv: mean, minimum, maximum and standard deviation (sample, n-1)
    of the 4 fold nMAEs for HGB, ridge, CAISO as published and persistence D-2, and in how many folds HGB
    is below each.

Writes reports/evidence_fit_gap.csv and reports/evidence_fold_spread.csv.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.evidence.common import LABEL, load_val
from src.modeling.features import MAIN_FEATURES, assert_no_leak, assert_tv_only, build_features, load_tv_table
from src.modeling.final_test import final_masks   # date window only; importing does not run the test
from src.modeling.folds import DEFAULT_LAYOUT, fold_masks, fold_table
from src.modeling.models import hgb_model, tune_hgb
from src.modeling.reserve import RESULTS
from src.modeling.score_models import OUT_CSV as VAL_RESULTS
from src.processing.build_hourly_table import ROOT
from src.processing.score_references import score_frame

OUT_GAP = ROOT / "reports" / "evidence_fit_gap.csv"
OUT_SPREAD = ROOT / "reports" / "evidence_fold_spread.csv"
FROZEN = dict(max_depth=5, loss="absolute_error", max_iter=86)
SPREAD_MODELS = {"hgb": "HGB (our model)", "ridge": "Ridge", "caiso_published": "CAISO as published",
                 "persistence_d2": "Persistence D-2"}


def pct(pred: np.ndarray, y: pd.Series) -> float:
    return float(np.mean(np.abs(np.clip(pred, 0, 1) - y.values)) * 100)


def task_2a() -> pd.DataFrame:
    df = load_tv_table()
    assert_tv_only(df, "fit_gap")
    feat = build_features(df)
    assert_no_leak(feat[MAIN_FEATURES])
    common = score_frame(df, "d14", "clipped")["common"]
    X, y = feat[MAIN_FEATURES], feat["cf"]
    saved = load_val()
    rows, val_parts = [], []
    for fr in fold_table(DEFAULT_LAYOUT).itertuples():
        m = fold_masks(feat["local_start"], fr)
        fit = feat["fit_row"]
        tr, inner_fit, inner_val = m["train"] & fit, m["inner_fit"] & fit, m["inner_val"] & fit
        val = m["val"] & feat["daylight"] & common
        params, _ = tune_hgb(X[inner_fit], y[inner_fit], X[inner_val], y[inner_val])
        model = hgb_model(params).fit(X[tr], y[tr])
        p_tr, p_val = model.predict(X[tr]), model.predict(X[val])
        mw = np.clip(p_val, 0, 1) * feat.loc[val, "capacity_mw"]
        diff = float((mw - saved.loc[mw.index, "hgb"]).abs().max())
        if diff > 0.01:
            raise SystemExit(f"STOP: fold {fr.fold} validation predictions differ from the saved ones by {diff:.3f} MW")
        tr_common = (tr & common)[tr].values
        val_parts.append((np.abs(np.clip(p_val, 0, 1) - y[val].values)))
        rows.append(dict(row=f"fold {fr.fold}", settings=f"max_depth {params['max_depth']}, {params['loss']}, "
                                                          f"{params['max_iter']} iterations",
                         train_rows=int(tr.sum()), train_nmae_pct=pct(p_tr, y[tr]),
                         train_common_rows=int(tr_common.sum()), train_common_nmae_pct=pct(p_tr[tr_common], y[tr][tr_common]),
                         val_hours=int(val.sum()), val_nmae_pct=pct(p_val, y[val])))
        print(f"  fold {fr.fold}: {rows[-1]['settings']}; validation predictions match the saved ones (largest difference {diff:.6f} MW)")
    pooled = float(np.concatenate(val_parts).mean() * 100)

    fm = final_masks(feat["local_start"])
    fit = feat["fit_row"] & fm["train"]
    days = fm["dates"][0]   # calendar days in the window, as in the spec
    if (int(fit.sum()), days) != (9187, 763):
        raise SystemExit(f"frozen refit rows {int(fit.sum())} on {days} days, expected 9,187 on 763")
    frozen = hgb_model(FROZEN).fit(X[fit], y[fit])
    p = frozen.predict(X[fit])
    fc = common[fit].values
    res = pd.read_csv(RESULTS)
    test = float(res[(res["model"] == "hgb") & (res["metric"] == "nmae_pct") & (res["group"] == "all")]["value"].iloc[0])
    rows.append(dict(row="frozen model (763 days)", settings="max_depth 5, absolute_error, 86 iterations (frozen)",
                     train_rows=int(fit.sum()), train_nmae_pct=pct(p, y[fit]), train_common_rows=int(fc.sum()),
                     train_common_nmae_pct=pct(p[fc], y[fit][fc]), val_hours=4508, val_nmae_pct=pooled,
                     test_hours=2457, test_nmae_pct=test))
    t = pd.DataFrame(rows)
    t["note"] = LABEL
    return t


def task_2d() -> pd.DataFrame:
    res = pd.read_csv(VAL_RESULTS)
    f = res[(res["metric"] == "nmae_pct") & (res["group"] == "all") & res["fold"].isin(["1", "2", "3", "4"])]
    w = f.pivot(index="fold", columns="model", values="value")
    rows = []
    for m, label in SPREAD_MODELS.items():
        v = w[m]
        rows.append(dict(model=m, label=label, fold1=v["1"], fold2=v["2"], fold3=v["3"], fold4=v["4"], mean=v.mean(),
                         min=v.min(), max=v.max(), std_sample=v.std(ddof=1),
                         folds_hgb_below=None if m == "hgb" else int((w["hgb"] < v).sum()), note=LABEL))
    return pd.DataFrame(rows)


def main() -> None:
    print(f"Task 2a: training against out-of-sample error ({LABEL}); no test row is loaded\n")
    gap = task_2a()
    num = gap.select_dtypes("float").columns
    gap[num] = gap[num].round(4)
    gap.to_csv(OUT_GAP, index=False)
    print("\n  nMAE %, capacity factor error / capacity (same as D27)")
    print(f"  {'':<26}{'training (fit rows)':>22}{'training (common h)':>22}{'validation':>14}{'test':>10}")
    for r in gap.itertuples():
        t = f"{r.test_nmae_pct:.2f}" if not pd.isna(r.test_nmae_pct) else ""
        v = f"{r.val_nmae_pct:.2f}" + (" pooled" if r.row.startswith("frozen") else "")
        print(f"  {r.row:<26}{r.train_nmae_pct:>14.2f} ({r.train_rows:>5,}){r.train_common_nmae_pct:>14.2f} ({r.train_common_rows:>5,})"
              f"{v:>14}{t:>10}")
    print("  The validation figure on the frozen row is the pooled out-of-fold score of the fold models, not of the frozen model;")
    print("  the test figure is from reports/final_results_test.csv.")

    print(f"\nTask 2d: spread of the 4 fold nMAEs, from {VAL_RESULTS.relative_to(ROOT).as_posix()} ({LABEL})\n")
    sp = task_2d()
    num = sp.select_dtypes("float").columns
    sp[num] = sp[num].round(4)
    sp.to_csv(OUT_SPREAD, index=False)
    print(f"  {'model':<20}{'fold 1':>8}{'fold 2':>8}{'fold 3':>8}{'fold 4':>8}{'mean':>8}{'min':>8}{'max':>8}{'std':>8}   HGB below in")
    for r in sp.itertuples():
        below = "" if r.folds_hgb_below is None or pd.isna(r.folds_hgb_below) else f"{int(r.folds_hgb_below)} of 4 folds"
        print(f"  {r.label:<20}{r.fold1:>8.2f}{r.fold2:>8.2f}{r.fold3:>8.2f}{r.fold4:>8.2f}{r.mean:>8.2f}{r.min:>8.2f}"
              f"{r.max:>8.2f}{r.std_sample:>8.2f}   {below}")
    print("  std is the sample standard deviation (n - 1) of the 4 fold values.")
    print(f"\nwritten: {OUT_GAP.relative_to(ROOT).as_posix()}, {OUT_SPREAD.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
