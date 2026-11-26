"""Brief 9, Task 3: day-block bootstrap of the nMAE gaps (post-hoc check, not a pre-registered test).

Run from the repo root:
    python -m src.evidence.bootstrap

Resamples Pacific dates (of the hour start) with replacement, 10,000 draws, seed 0, keeping all scored
hours of each drawn date, and recomputes pooled nMAE for every model on the same draw. Validation (4,508
out-of-fold hours, 374 days) and test (2,457 saved-prediction hours, 187 days) are bootstrapped
separately, each with a fresh generator seeded 0. Reads saved predictions only; nothing is refitted.

Pooled nMAE on a draw = sum over drawn dates (with repeats) of sum(|error| / capacity_mw) divided by the
number of hours in those dates, times 100. CAISO adjusted is scored against EIA plus curt_mwh (D27),
every other forecast against EIA.

Rows:
  model_nmae   each model's own nMAE, 95% interval (2.5th and 97.5th percentiles)
  difference   other model minus HGB, in points (positive: HGB lower), interval, share of draws HGB lower
  h2_margin    1.25 x CAISO adjusted minus HGB (positive: H2 secondary met), interval, share of draws met
  curtailment  CAISO as published minus HGB on not curtailed and on curtailed hours (D30 threshold),
               using the same date draws restricted to the hours of each group

Robustness version (block_days = 7): draws start dates with replacement among the calendar dates that
leave room for a full block, takes 7 consecutive Pacific calendar dates from each start (all scored hours
of each date; dates with no scored hours add nothing), and keeps drawing blocks until the number of scored
dates equals the original (374 validation, 187 test), cutting the last block short. 10,000 draws, seed 0.
Run only for: CAISO as published minus HGB (all, not curtailed, curtailed), persistence D-2 and ridge
minus HGB (all), and the H2 secondary margin. Weather spells last several days, so single-day draws can
understate the uncertainty; the 7-day version checks how much.

Writes reports/evidence_bootstrap.csv.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.evidence.common import LABEL, ROOT, curtailed, load_test, load_val, nmae, reproduce
from src.modeling.score_models import TARGET_FACTOR

OUT_CSV = ROOT / "reports" / "evidence_bootstrap.csv"
N_DRAWS, SEED, BLOCK = 10_000, 0, 7
MODELS = ["hgb", "caiso_published", "caiso_adjusted", "persistence_d2", "persistence_d1", "ridge", "climatology"]
LABELS = {"hgb": "HGB (our model)", "caiso_published": "CAISO as published", "caiso_adjusted": "CAISO adjusted",
          "persistence_d2": "Persistence D-2", "persistence_d1": "Persistence D-1 (comparison only)",
          "ridge": "Ridge", "climatology": "Climatology"}
VERSUS = ["caiso_published", "persistence_d2", "ridge", "caiso_adjusted"]


def draw_weights(n_days: int) -> np.ndarray:
    """(N_DRAWS, n_days) matrix: how many times each date is drawn in each draw."""
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n_days, size=(N_DRAWS, n_days))
    w = np.zeros((N_DRAWS, n_days), dtype=np.int32)
    np.add.at(w, (np.repeat(np.arange(N_DRAWS), n_days), idx.ravel()), 1)
    return w


def block_weights(days: pd.Index) -> np.ndarray:
    """(N_DRAWS, n_days) matrix for the 7-day-block bootstrap (see module docstring)."""
    n = len(days)
    cal = pd.date_range(days[0], days[-1], freq="D").date
    lookup = np.full(len(cal), -1)
    pos = {d: i for i, d in enumerate(days)}
    for i, d in enumerate(cal):
        lookup[i] = pos.get(d, -1)
    n_starts = len(cal) - BLOCK + 1
    k = 2 * int(np.ceil(n / BLOCK)) + 10
    rng = np.random.default_rng(SEED)
    w = np.zeros((N_DRAWS, n), dtype=np.int32)
    for r in range(N_DRAWS):
        starts = rng.integers(0, n_starts, size=k)
        idx = lookup[(starts[:, None] + np.arange(BLOCK)).ravel()]
        idx = idx[idx >= 0]
        if len(idx) < n:
            raise SystemExit("not enough blocks drawn")
        w[r] = np.bincount(idx[:n], minlength=n)
    return w


def per_day(df: pd.DataFrame, days: pd.Index, mask: pd.Series | None = None) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Per-date sums of |error| / capacity (each model) and hour counts, aligned to `days`."""
    g = df if mask is None else df[mask]
    date = g["local_start"].dt.date
    sums = {}
    for m in MODELS:
        a = g["actual_adjusted"] if m == "caiso_adjusted" else g["actual"]
        sums[m] = ((g[m] - a).abs() / g["capacity_mw"]).groupby(date).sum().reindex(days, fill_value=0.0).to_numpy()
    counts = date.groupby(date).size().reindex(days, fill_value=0).to_numpy()
    return sums, counts


def interval(x: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(x, [2.5, 97.5])
    return float(lo), float(hi)


def run(df: pd.DataFrame, period: str, block: int = 1) -> pd.DataFrame:
    days = pd.Index(sorted(df["local_start"].dt.date.unique()))
    w = draw_weights(len(days)) if block == 1 else block_weights(days)
    note = LABEL if block == 1 else f"{LABEL}; block of {block} days"
    base = dict(period=period, block_days=block, draws=N_DRAWS, seed=SEED, days=len(days), note=note)
    rows = []

    sums, counts = per_day(df, days)
    hours = w @ counts
    boot = {m: (w @ sums[m]) / hours * 100 for m in MODELS}
    obs = {m: nmae(df, m) for m in MODELS}
    for m in MODELS if block == 1 else []:
        if abs(obs[m] - sums[m].sum() / counts.sum() * 100) > 1e-9:
            raise SystemExit(f"per-day sums do not reproduce nMAE for {m}")
        lo, hi = interval(boot[m])
        rows.append(dict(**base, subset="all", kind="model_nmae", comparison=LABELS[m], hours=len(df),
                         observed=obs[m], ci_low=lo, ci_high=hi, share_hgb_lower=None))
    for m in VERSUS if block == 1 else ["caiso_published", "persistence_d2", "ridge"]:
        d = boot[m] - boot["hgb"]
        lo, hi = interval(d)
        rows.append(dict(**base, subset="all", kind="difference", comparison=f"{LABELS[m]} minus HGB", hours=len(df),
                         observed=obs[m] - obs["hgb"], ci_low=lo, ci_high=hi, share_hgb_lower=float((d > 0).mean())))
    d = TARGET_FACTOR * boot["caiso_adjusted"] - boot["hgb"]
    lo, hi = interval(d)
    rows.append(dict(**base, subset="all", kind="h2_margin", comparison="1.25 x CAISO adjusted minus HGB (positive: met)",
                     hours=len(df), observed=TARGET_FACTOR * obs["caiso_adjusted"] - obs["hgb"], ci_low=lo, ci_high=hi,
                     share_hgb_lower=float((d > 0).mean())))

    cut = curtailed(df)
    for name, mask in [("not curtailed", ~cut), ("curtailed", cut)]:
        s, c = per_day(df, days, mask)
        h = w @ c
        if (h == 0).any():
            raise SystemExit(f"a draw has no {name} hours")
        b_h, b_c = (w @ s["hgb"]) / h * 100, (w @ s["caiso_published"]) / h * 100
        d = b_c - b_h
        lo, hi = interval(d)
        g = df[mask]
        rows.append(dict(**base, subset=name, kind="curtailment", comparison="CAISO as published minus HGB",
                         hours=len(g), observed=nmae(g, "caiso_published") - nmae(g, "hgb"), ci_low=lo, ci_high=hi,
                         share_hgb_lower=float((d > 0).mean())))
        for m, b in [("hgb", b_h), ("caiso_published", b_c)] if block == 1 else []:
            lo, hi = interval(b)
            rows.append(dict(**base, subset=name, kind="model_nmae", comparison=LABELS[m], hours=len(g),
                             observed=nmae(g, m), ci_low=lo, ci_high=hi, share_hgb_lower=None))
    return pd.DataFrame(rows)


def show(t: pd.DataFrame, title: str) -> None:
    print(f"\n{title}: {t['days'].iloc[0]} Pacific dates, {N_DRAWS:,} draws, seed {SEED}")
    for kind, head in [("model_nmae", "Each model's nMAE (%)"), ("difference", "Gaps, other model minus HGB (points)"),
                       ("h2_margin", "H2 secondary margin (points)"), ("curtailment", "By curtailment (points)")]:
        s = t[t["kind"] == kind]
        if kind == "model_nmae":
            s = s[s["subset"] == "all"]
        print(f"\n  {head}")
        for r in s.itertuples():
            name = r.comparison if r.subset == "all" else f"{r.comparison}, {r.subset} ({r.hours:,} h)"
            share = "" if pd.isna(r.share_hgb_lower) else f"   HGB lower in {r.share_hgb_lower:6.1%} of draws"
            if kind == "h2_margin":
                share = f"   met in {r.share_hgb_lower:6.1%} of draws"
            fmt = "{:+.4f}" if kind == "h2_margin" else ("{:.2f}" if kind == "model_nmae" else "{:+.2f}")
            print(f"    {name:<62} {fmt.format(r.observed):>8}   95% [{fmt.format(r.ci_low)}, {fmt.format(r.ci_high)}]{share}")


def compare(single: pd.DataFrame, blocks: pd.DataFrame) -> None:
    key = ["period", "subset", "kind", "comparison"]
    m = blocks.merge(single, on=key, suffixes=("_7", "_1"))
    print(f"\nSingle-day against {BLOCK}-day-block intervals ({LABEL}); points, other model minus HGB")
    print(f"  {'period':<11}{'row':<52}{'observed':>9}   {'1-day 95% interval':>20} {'share':>6}   {'7-day 95% interval':>20} {'share':>6}  width x")
    for r in m.itertuples():
        name = r.comparison.replace(" (positive: met)", "") + ("" if r.subset == "all" else f", {r.subset}")
        f = "{:+.3f}"
        i1 = f"[{f.format(r.ci_low_1)}, {f.format(r.ci_high_1)}]"
        i7 = f"[{f.format(r.ci_low_7)}, {f.format(r.ci_high_7)}]"
        wx = (r.ci_high_7 - r.ci_low_7) / (r.ci_high_1 - r.ci_low_1)
        print(f"  {r.period:<11}{name:<52}{f.format(r.observed_1):>9}   {i1:>20} {r.share_hgb_lower_1:>6.1%}   "
              f"{i7:>20} {r.share_hgb_lower_7:>6.1%}  {wx:5.2f}")
    print("  share: draws in which HGB is lower (H2 row: draws in which the secondary target is met)")


def main() -> None:
    reproduce()
    print("\n" + "=" * 110)
    print(f"Task 3: day-block bootstrap ({LABEL})")
    v, t = load_val(), load_test()
    tv, tt = run(v, "validation"), run(t, "test")
    show(tv, "VALIDATION (out-of-fold, 4,508 hours)")
    show(tt, "TEST (saved predictions from the one test run, 2,457 hours)")
    bv, bt = run(v, "validation", BLOCK), run(t, "test", BLOCK)
    single, blocks = pd.concat([tv, tt], ignore_index=True), pd.concat([bv, bt], ignore_index=True)
    compare(single, blocks)
    out = pd.concat([single, blocks], ignore_index=True)
    for c in ["observed", "ci_low", "ci_high"]:
        out[c] = out[c].round(4)
    out["share_hgb_lower"] = out["share_hgb_lower"].round(4)
    cols = ["period", "block_days", "subset", "kind", "comparison", "hours", "days", "observed", "ci_low", "ci_high",
            "share_hgb_lower", "draws", "seed", "note"]
    out[cols].to_csv(OUT_CSV, index=False)
    print("\nshare_hgb_lower for the h2_margin row is the share of draws in which the secondary target is met.")
    print(f"written: {OUT_CSV.relative_to(ROOT).as_posix()} (block_days 1 = single days, {BLOCK} = blocks of {BLOCK} days)")


if __name__ == "__main__":
    main()
