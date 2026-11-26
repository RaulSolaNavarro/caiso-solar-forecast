"""Brief 9, Task 2b: fitting graph on the inner split of the final window (training and validation rows only;
post-hoc check, not a pre-registered test).

Run from the repo root:
    python -m src.evidence.fitting_graph

Inner fit 2024-03-08 to 2026-01-22, inner validation 2026-01-24 to 2026-04-09 (reports/final_model_spec.md),
selected with final_test.final_masks (importing it does not run the test). One HistGradientBoostingRegressor
with the frozen depth and loss (max_depth 5, absolute_error, the rest HGB_FIXED) is fitted with 400 trees, and
staged_predict gives nMAE on the inner-fit rows and the inner-validation rows after each tree. Without early
stopping, the first 86 trees are the same as in a fit stopped at 86, so the value at 86 must reproduce the
spec's inner-validation nMAE (4.452%).

Writes reports/evidence_fitting_graph.csv and deck/capstone3/figures/evidence_fitting_graph.png.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.evidence.common import LABEL as NOTE
from src.evidence.diagnostics import WHITE, fig_axes, save
from src.modeling.capstone3_figures import COLOR, GRID, INK, INK2, style
from src.modeling.features import MAIN_FEATURES, assert_no_leak, assert_tv_only, build_features, load_tv_table
from src.modeling.final_test import final_masks
from src.modeling.models import hgb_model, nmae

N_TREES, FROZEN_TREES, SPEC_INNER_NMAE = 400, 86, 4.452
DEPTH, LOSS = 5, "absolute_error"


def main() -> None:
    print(f"Task 2b: fitting graph ({NOTE}); training and validation rows only\n")
    df = load_tv_table()
    assert_tv_only(df, "fitting_graph")
    feat = build_features(df)
    assert_no_leak(feat[MAIN_FEATURES])
    m = final_masks(feat["local_start"])
    fit = feat["fit_row"]
    i_fit, i_val = m["inner_fit"] & fit, m["inner_val"] & fit
    if (int(i_fit.sum()), int(i_val.sum())) != (8319, 858):
        raise SystemExit(f"inner rows {int(i_fit.sum())} and {int(i_val.sum())}, expected 8,319 and 858 (spec)")
    X, y = feat[MAIN_FEATURES], feat["cf"]
    model = hgb_model(dict(max_depth=DEPTH, loss=LOSS, max_iter=N_TREES)).fit(X[i_fit], y[i_fit])
    tr = [nmae(np.clip(p, 0, 1), y[i_fit].values) * 100 for p in model.staged_predict(X[i_fit])]
    va = [nmae(np.clip(p, 0, 1), y[i_val].values) * 100 for p in model.staged_predict(X[i_val])]
    d = pd.DataFrame({"trees": np.arange(1, N_TREES + 1), "inner_fit_nmae_pct": tr, "inner_val_nmae_pct": va})
    at86 = d.loc[FROZEN_TREES - 1, "inner_val_nmae_pct"]
    best = int(d["inner_val_nmae_pct"].idxmin()) + 1
    print(f"inner fit 2024-03-08 to {m['dates'][3]} ({int(i_fit.sum()):,} rows), "
          f"inner validation {m['dates'][2]} to 2026-04-09 ({int(i_val.sum()):,} rows); max_depth {DEPTH}, {LOSS}")
    print(f"check: inner-validation nMAE at {FROZEN_TREES} trees {at86:.3f}% (spec {SPEC_INNER_NMAE}%); "
          f"lowest at {best} trees")
    if abs(at86 - SPEC_INNER_NMAE) > 0.0005 + 0.001 or best != FROZEN_TREES:
        raise SystemExit("STOP: the fitting graph does not reproduce the spec")

    print(f"\n  {'trees':>6}{'inner fit':>12}{'inner validation':>19}{'gap':>8}")
    for t in (1, 10, 20, 40, 60, 86, 120, 150, 200, 300, 400):
        r = d.loc[t - 1]
        print(f"  {t:>6}{r.inner_fit_nmae_pct:>11.2f}%{r.inner_val_nmae_pct:>18.2f}%{r.inner_val_nmae_pct - r.inner_fit_nmae_pct:>+8.2f}")

    fig, ax = fig_axes()
    style(ax)
    ax.plot(d["trees"], d["inner_fit_nmae_pct"], color=COLOR["hgb"], linewidth=3, linestyle="--",
            label="Days the model learned from (inner fit, 2024-03-08 to 2026-01-22)")
    ax.plot(d["trees"], d["inner_val_nmae_pct"], color=COLOR["hgb"], linewidth=3,
            label="Days it did not see (inner validation, 2026-01-24 to 2026-04-09)")
    ax.axvline(FROZEN_TREES, color=INK2, linewidth=1.5, linestyle=":")
    ax.plot(FROZEN_TREES, at86, "o", color=COLOR["hgb"], markersize=11, markeredgecolor=WHITE, markeredgewidth=2, zorder=5)
    ax.annotate(f"86 trees, the frozen model: {at86:.2f}% on unseen days", (FROZEN_TREES, at86), xytext=(16, 28),
                textcoords="offset points", fontsize=17, color=INK)
    ax.set_xlabel("Number of trees")
    ax.set_ylabel("nMAE (% of installed solar)")
    ax.set_xlim(0, N_TREES)
    ax.set_ylim(0, 18)
    ax.legend(frameon=False, loc="upper right")
    fig.subplots_adjust(top=0.95, bottom=0.15)
    fig.text(0.02, 0.01, "Frozen depth and loss (depth 5, absolute error); trees after 86 keep improving the learned days "
             "but not the unseen ones. Training and validation days only; no test data.", fontsize=14, color=INK2)
    save(fig, "evidence_fitting_graph", d.round(4))


if __name__ == "__main__":
    main()
