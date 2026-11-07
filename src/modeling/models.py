"""Candidate models and reference forecasts on the validation folds (validation only, test locked).

Called by score_models. For each fold in reports/folds.csv (layout winter104, D29) every candidate is
fitted on that fold's training days only and predicts its validation days. Tuning uses only the
inner split (the last 10% of training days, after a 1-day gap): ridge alpha and the tree settings
and iteration count. The validation block is never used to choose anything.

Candidates (target = capacity factor, prediction x capacity_mw = MW, clipped to 0 to 1 of capacity):
  persistence_d2     EIA at t - 48 h (the fair reference, D27)
  persistence_d1     EIA at t - 24 h (labeled comparison only: breaks the 10 a.m. rule)
  caiso_published    CAISO day-ahead against EIA (reference, never trained on)
  caiso_adjusted     CAISO day-ahead against EIA + curt_mwh (reference)
  climatology        mean capacity factor by month and Pacific hour over the training fit rows
  ridge              median fill (training rows) + standardize + ridge; alpha from RIDGE_ALPHAS on the inner split
  hgb                HistGradientBoostingRegressor; HGB_GRID and the iteration count on the inner split
  <best>_day1        the better of ridge and hgb (pooled validation nMAE) refit with day-1 cloud and GHI
                     (labeled comparison: shows what the 10 a.m. rule costs)
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.modeling.features import MAIN_FEATURES, assert_no_leak, assert_tv_only, day1_features
from src.modeling.folds import fold_masks

SEED = 0
RIDGE_ALPHAS = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
HGB_GRID = {"max_depth": [3, 5], "loss": ["squared_error", "absolute_error"]}
HGB_FIXED = dict(learning_rate=0.05, max_iter=1500, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0,
                 early_stopping=False, random_state=SEED)
REFERENCES = ["persistence_d2", "persistence_d1", "caiso_published", "caiso_adjusted"]
TRAINED = ["climatology", "ridge", "hgb"]


def nmae(pred_cf: np.ndarray, true_cf: np.ndarray) -> float:
    """Mean |error| in capacity-factor units = normalized MAE as a fraction (same divisor per hour)."""
    return float(np.mean(np.abs(pred_cf - true_cf)))


def fit_climatology(X: pd.DataFrame, y: pd.Series, month: pd.Series):
    table = y.groupby([month, X["hour"]]).mean()
    overall = y.groupby(X["hour"]).mean()

    def predict(Xp: pd.DataFrame, month_p: pd.Series) -> np.ndarray:
        keys = pd.MultiIndex.from_arrays([month_p.values, Xp["hour"].values])
        v = table.reindex(keys).values
        return np.where(np.isnan(v), overall.reindex(Xp["hour"]).values, v)
    return predict


def ridge_model(alpha: float):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=alpha))


def tune_ridge(X_in, y_in, X_iv, y_iv) -> tuple[float, dict]:
    scores = {a: nmae(np.clip(ridge_model(a).fit(X_in, y_in).predict(X_iv), 0, 1), y_iv.values) for a in RIDGE_ALPHAS}
    return min(scores, key=scores.get), scores


def tune_hgb(X_in, y_in, X_iv, y_iv) -> tuple[dict, dict]:
    """Each grid point is fitted once on the inner-fit days; the iteration count is the one with the
    lowest inner-validation nMAE (early stopping on the last 10% of training days)."""
    best, log = None, {}
    for depth, loss in itertools.product(HGB_GRID["max_depth"], HGB_GRID["loss"]):
        m = HistGradientBoostingRegressor(max_depth=depth, loss=loss, **HGB_FIXED).fit(X_in, y_in)
        curve = [nmae(np.clip(p, 0, 1), y_iv.values) for p in m.staged_predict(X_iv)]
        it = int(np.argmin(curve)) + 1
        log[(depth, loss)] = (curve[it - 1], it)
        if best is None or curve[it - 1] < best[0]:
            best = (curve[it - 1], dict(max_depth=depth, loss=loss, max_iter=it))
    return best[1], log


def hgb_model(params: dict):
    kw = {**HGB_FIXED, **params}
    return HistGradientBoostingRegressor(**kw)


def run_fold(feat: pd.DataFrame, fold_row, model: str, features: list[str]) -> tuple[pd.Series, dict]:
    """Fit one trained candidate on one fold. Returns capacity-factor predictions for the fold's
    validation daylight rows and a record of what was chosen."""
    m = fold_masks(feat["local_start"], fold_row)
    fit = feat["fit_row"]
    tr, inner_fit, inner_val = m["train"] & fit, m["inner_fit"] & fit, m["inner_val"] & fit
    val = m["val"] & feat["daylight"]
    for name, mask in [("training", tr), ("validation", val)]:
        assert_tv_only(feat[mask], f"fold {fold_row.fold} {name}")
    assert not (tr & m["val"]).any(), "training rows inside the validation block"
    X, y = feat[features], feat["cf"]
    month = feat["local_start"].dt.month
    if model == "climatology":
        pred = fit_climatology(X[tr], y[tr], month[tr])(X[val], month[val])
        info = {}
    elif model == "ridge":
        alpha, scores = tune_ridge(X[inner_fit], y[inner_fit], X[inner_val], y[inner_val])
        pred = ridge_model(alpha).fit(X[tr], y[tr]).predict(X[val])
        info = {"alpha": alpha, "inner_nmae_pct": {a: round(s * 100, 3) for a, s in scores.items()}}
    elif model == "hgb":
        params, log = tune_hgb(X[inner_fit], y[inner_fit], X[inner_val], y[inner_val])
        pred = hgb_model(params).fit(X[tr], y[tr]).predict(X[val])
        info = {**params, "inner_nmae_pct": {f"depth{d}_{l}": (round(s * 100, 3), it) for (d, l), (s, it) in log.items()}}
    else:
        raise ValueError(model)
    info.update(train_rows=int(tr.sum()), inner_fit_rows=int(inner_fit.sum()), inner_val_rows=int(inner_val.sum()),
                val_rows=int(val.sum()))
    return pd.Series(np.clip(pred, 0, 1), index=feat.index[val]), info


def out_of_fold(feat: pd.DataFrame, refs: pd.DataFrame, folds: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Per-hour validation predictions (MW) for every reference and candidate, all 4 folds."""
    assert_tv_only(feat, "out_of_fold")
    assert_no_leak(feat[MAIN_FEATURES])
    parts, log = [], []
    for fr in folds.itertuples():
        m = fold_masks(feat["local_start"], fr)
        val = m["val"] & feat["daylight"]
        p = pd.DataFrame(index=feat.index[val])
        p["fold"] = fr.fold
        for r in REFERENCES:
            p[r] = refs.loc[val, r]
        for model in TRAINED:
            cf, info = run_fold(feat, fr, model, MAIN_FEATURES)
            p[model] = cf * feat.loc[val, "capacity_mw"]
            log.append({"fold": fr.fold, "model": model, **info})
            print(f"  fold {fr.fold} {model:<12} {', '.join(f'{k}={v}' for k, v in info.items() if k != 'inner_nmae_pct')}")
        parts.append(p)
    return pd.concat(parts), log


def day1_comparison(feat: pd.DataFrame, folds: pd.DataFrame, model: str) -> tuple[pd.Series, list[dict]]:
    feats = day1_features()
    assert_no_leak(feat[feats], allow_day1=True)
    preds, log = [], []
    for fr in folds.itertuples():
        cf, info = run_fold(feat, fr, model, feats)
        preds.append(cf * feat.loc[cf.index, "capacity_mw"])
        log.append({"fold": fr.fold, "model": f"{model}_day1", **info})
        print(f"  fold {fr.fold} {model + '_day1':<12} {', '.join(f'{k}={v}' for k, v in info.items() if k != 'inner_nmae_pct')}")
    return pd.concat(preds), log
