"""Brief 9, Task 1: which inputs earn their place (validation folds only; post-hoc check, not a pre-registered test).

Run from the repo root:
    python -m src.evidence.input_groups

Training and validation rows only: load_tv_table, build_features (allow_test False), the D29 folds and
the D27 common hours, as in score_models. Every tree variant is fitted with models.run_fold, so the inner
split, tune_hgb, HGB_GRID and HGB_FIXED are exactly those of score_models. Nothing touches the test set.

Variants (gradient-boosted trees, each refitted and retuned on every fold):
  all 20 inputs (must reproduce 4.02% pooled and the saved out-of-fold predictions)
  without each D28 input group in turn: day-2 weather, time and sun, capacity, recent output
Chapter 7 baselines:
  mean_cf     training-window mean capacity factor (fold training fit rows) x capacity_mw
  one_split   DecisionTreeRegressor(max_depth=1, min_samples_leaf=40, random_state=0) on the single input
              with the lowest inner-validation nMAE (chosen on the fold's inner split, then refitted on the
              fold's training fit rows)

Input ranking (numeric-target version of the Chapter 3 information gain table): for each input and fold,
the same one-split tree on that input alone, fitted on the fold's training fit rows; share of the capacity
factor's variance removed by the best split = 1 - (weighted child variance) / (parent variance), on those
rows. Averaged over the 4 folds and ranked.

Blank values: scikit-learn's DecisionTreeRegressor (1.3 and later) takes blanks directly and, at each
split, sends the blank rows to whichever side lowers the error. HistGradientBoostingRegressor in models.py
handles blanks the same way. No filling is done.

Writes reports/evidence_input_groups.csv and reports/evidence_input_ranking.csv.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import sklearn
from sklearn.tree import DecisionTreeRegressor

from src.evidence.common import LABEL, load_val
from src.modeling.features import DAY2_WEATHER, MAIN_FEATURES, assert_no_leak, assert_tv_only, build_features, load_tv_table
from src.modeling.folds import DEFAULT_LAYOUT, fold_masks, fold_table
from src.modeling.models import nmae as cf_nmae, run_fold
from src.modeling.score_models import SEASON, metrics
from src.processing.build_hourly_table import ROOT
from src.processing.score_references import score_frame

OUT_GROUPS = ROOT / "reports" / "evidence_input_groups.csv"
OUT_RANK = ROOT / "reports" / "evidence_input_ranking.csv"
GROUPS = {
    "day-2 weather": DAY2_WEATHER + ["csi_previous_day2"],
    "time and sun": ["hour", "hour_sin", "hour_cos", "doy_sin", "doy_cos", "sun_elev", "clearsky_ghi"],
    "capacity": ["capacity_mw"],
    "recent output": ["cf_lag48", "cf_d2_daily"],
}
GROUP_OF = {f: g for g, fs in GROUPS.items() for f in fs}
STUMP = dict(max_depth=1, min_samples_leaf=40, random_state=0)
SEASONS = ["spring", "summer", "fall", "winter"]


def stump() -> DecisionTreeRegressor:
    return DecisionTreeRegressor(**STUMP)


def variance_removed(x: pd.Series, y: pd.Series) -> float:
    t = stump().fit(x.to_frame(), y).tree_
    if t.node_count == 1:
        return 0.0
    n = t.n_node_samples
    child = (n[1] * t.impurity[1] + n[2] * t.impurity[2]) / n[0]
    return float(1 - child / t.impurity[0])


def one_split(feat: pd.DataFrame, fr) -> tuple[pd.Series, str, float]:
    m = fold_masks(feat["local_start"], fr)
    fit = feat["fit_row"]
    tr, inner_fit, inner_val = m["train"] & fit, m["inner_fit"] & fit, m["inner_val"] & fit
    val = m["val"] & feat["daylight"]
    y = feat["cf"]
    scores = {f: cf_nmae(np.clip(stump().fit(feat.loc[inner_fit, [f]], y[inner_fit]).predict(feat.loc[inner_val, [f]]), 0, 1),
                         y[inner_val].values) for f in MAIN_FEATURES}
    best = min(scores, key=scores.get)
    pred = stump().fit(feat.loc[tr, [best]], y[tr]).predict(feat.loc[val, [best]])
    return pd.Series(np.clip(pred, 0, 1), index=feat.index[val]), best, scores[best] * 100


def mean_cf(feat: pd.DataFrame, fr) -> pd.Series:
    m = fold_masks(feat["local_start"], fr)
    tr, val = m["train"] & feat["fit_row"], m["val"] & feat["daylight"]
    return pd.Series(float(feat.loc[tr, "cf"].mean()), index=feat.index[val])


def main() -> None:
    print(f"Task 1: which inputs earn their place ({LABEL})")
    print("VALIDATION FOLDS ONLY, TEST LOCKED\n")
    assert sorted(GROUP_OF) == sorted(MAIN_FEATURES) and len(GROUP_OF) == 20
    df = load_tv_table()
    assert_tv_only(df, "input_groups")
    feat = build_features(df)
    assert_no_leak(feat[MAIN_FEATURES])
    refs = score_frame(df, "d14", "clipped")
    folds = fold_table(DEFAULT_LAYOUT)
    blanks = feat.loc[feat["fit_row"], MAIN_FEATURES].isna().sum()
    print(f"scikit-learn {sklearn.__version__}; blanks in training fit rows (kept as blanks, trees route them): "
          + (", ".join(f"{k} {v:,}" for k, v in blanks[blanks > 0].items()) or "none"))

    variants = {"all 20 inputs": MAIN_FEATURES}
    for g, fs in GROUPS.items():
        variants[f"without {g}"] = [f for f in MAIN_FEATURES if f not in fs]

    preds: dict[str, list[pd.Series]] = {k: [] for k in list(variants) + ["mean_cf baseline", "one_split baseline"]}
    chosen = []
    for fr in folds.itertuples():
        for name, fs in variants.items():
            cf, info = run_fold(feat, fr, "hgb", fs)
            preds[name].append(cf)
            print(f"  fold {fr.fold} {name:<24} {len(fs):>2} inputs: max_depth={info['max_depth']}, loss={info['loss']}, "
                  f"max_iter={info['max_iter']}")
        preds["mean_cf baseline"].append(mean_cf(feat, fr))
        cf, best, inner = one_split(feat, fr)
        preds["one_split baseline"].append(cf)
        chosen.append(dict(fold=fr.fold, input=best, inner_val_nmae_pct=round(inner, 3)))

    idx = pd.concat(preds["all 20 inputs"]).index
    scored = refs.loc[idx].copy()
    scored["fold"] = pd.concat([pd.Series(fr.fold, index=p.index) for fr, p in zip(folds.itertuples(), preds["all 20 inputs"])])
    for name, ps in preds.items():
        s = pd.concat(ps)
        scored[name] = s.reindex(idx) * scored["capacity_mw"]
    scored = scored[scored["common"]]
    if len(scored) != 4508 or scored[list(preds)].isna().any().any():
        raise SystemExit(f"scored hours {len(scored)}, expected 4,508 with no blanks")

    saved = load_val()
    diff = (scored["all 20 inputs"] - saved.loc[scored.index, "hgb"]).abs().max()
    print(f"\nCheck: all-20-inputs variant against the saved out-of-fold HGB predictions, largest difference {diff:.6f} MW")
    if diff > 0.01:
        raise SystemExit("STOP: the all-20-inputs variant does not reproduce the saved predictions")

    season = scored["local_start"].dt.month.map(SEASON)
    full = metrics(scored, "all 20 inputs")["nmae_pct"]
    full_season = {s: metrics(scored[season == s], "all 20 inputs")["nmae_pct"] for s in SEASONS}
    rows = []
    for name in preds:
        m = metrics(scored, name)
        r = dict(variant=name, inputs=len(variants.get(name, [])) or (1 if name.startswith("one") else 0),
                 hours=len(scored), nmae_pct=m["nmae_pct"], skill_vs_persistence_d2=m["skill_vs_persistence_d2"],
                 change_vs_full_pts=m["nmae_pct"] - full)
        for k in [1, 2, 3, 4]:
            r[f"fold{k}_nmae_pct"] = metrics(scored[scored["fold"] == k], name)["nmae_pct"]
        for s in SEASONS:
            r[f"change_{s}_pts"] = metrics(scored[season == s], name)["nmae_pct"] - full_season[s]
        r["note"] = LABEL
        rows.append(r)
    pers = metrics(scored, "persistence_d2")
    rows.append(dict(variant="persistence D-2 (reference)", inputs=0, hours=len(scored), nmae_pct=pers["nmae_pct"],
                     skill_vs_persistence_d2=0.0, change_vs_full_pts=pers["nmae_pct"] - full,
                     **{f"fold{k}_nmae_pct": metrics(scored[scored["fold"] == k], "persistence_d2")["nmae_pct"] for k in [1, 2, 3, 4]},
                     **{f"change_{s}_pts": metrics(scored[season == s], "persistence_d2")["nmae_pct"] - full_season[s] for s in SEASONS},
                     note=LABEL))
    res = pd.DataFrame(rows)
    num = res.select_dtypes("number").columns
    res[num] = res[num].round(4)
    res.to_csv(OUT_GROUPS, index=False)

    print(f"\nPooled validation, {len(scored):,} common hours (D27), 4 folds (D29). Change = variant minus all 20 inputs, "
          "in points (positive: worse without it).")
    print(f"Season hours: " + ", ".join(f"{s} {int((season == s).sum()):,}" for s in SEASONS))
    show = res.copy()
    show["skill"] = show["skill_vs_persistence_d2"].map("{:.3f}".format)
    for c in ["nmae_pct", "fold1_nmae_pct", "fold2_nmae_pct", "fold3_nmae_pct", "fold4_nmae_pct"]:
        show[c] = show[c].map("{:.2f}".format)
    for c in ["change_vs_full_pts"] + [f"change_{s}_pts" for s in SEASONS]:
        show[c] = show[c].map("{:+.2f}".format)
    show = show.rename(columns={"nmae_pct": "nMAE %", "change_vs_full_pts": "change", "fold1_nmae_pct": "f1",
                                "fold2_nmae_pct": "f2", "fold3_nmae_pct": "f3", "fold4_nmae_pct": "f4",
                                **{f"change_{s}_pts": s for s in SEASONS}})
    with pd.option_context("display.width", 220):
        print(show[["variant", "inputs", "nMAE %", "f1", "f2", "f3", "f4", "skill", "change"] + SEASONS].to_string(index=False))

    print("\nOne-split tree baseline: input chosen on the inner split of each fold")
    for c in chosen:
        print(f"  fold {c['fold']}: {c['input']} (inner-validation nMAE {c['inner_val_nmae_pct']:.2f}%)")

    rank_rows = []
    for fr in folds.itertuples():
        m = fold_masks(feat["local_start"], fr)
        tr = m["train"] & feat["fit_row"]
        for f in MAIN_FEATURES:
            rank_rows.append(dict(fold=fr.fold, input=f, share=variance_removed(feat.loc[tr, f], feat.loc[tr, "cf"]),
                                  rows=int(tr.sum())))
    rr = pd.DataFrame(rank_rows)
    wide = rr.pivot(index="input", columns="fold", values="share")
    rank = pd.DataFrame({"input": wide.index, "group": [GROUP_OF[f] for f in wide.index],
                         "mean_share_variance_removed": wide.mean(axis=1).values,
                         **{f"fold{k}_share": wide[k].values for k in [1, 2, 3, 4]},
                         "blank_training_rows": [int(blanks[f]) for f in wide.index]})
    rank = rank.sort_values("mean_share_variance_removed", ascending=False).reset_index(drop=True)
    rank.insert(3, "rank", np.arange(1, len(rank) + 1))
    rank["note"] = LABEL
    num = rank.select_dtypes("float").columns
    rank[num] = rank[num].round(4)
    rank.to_csv(OUT_RANK, index=False)
    print("\nInput ranking: share of the capacity factor's variance removed by the best single split "
          "(one-split tree, min 40 rows per side), fold training fit rows, mean of 4 folds")
    print(f"  {'rank':>4}  {'input':<40}{'group':<15}{'mean':>7}  {'fold 1':>7}{'fold 2':>7}{'fold 3':>7}{'fold 4':>7}")
    for r in rank.itertuples():
        print(f"  {r.rank:>4}  {r.input:<40}{r.group:<15}{r.mean_share_variance_removed:>7.3f}  "
              f"{r.fold1_share:>7.3f}{r.fold2_share:>7.3f}{r.fold3_share:>7.3f}{r.fold4_share:>7.3f}")

    print(f"\nwritten: {OUT_GROUPS.relative_to(ROOT).as_posix()}, {OUT_RANK.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
