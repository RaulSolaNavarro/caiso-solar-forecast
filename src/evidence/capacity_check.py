"""Brief 9, Task 1b: is capacity_mw a stand-in for the date? (training and validation rows only;
post-hoc check, not a pre-registered test)

Run from the repo root:
    python -m src.evidence.capacity_check

For each D29 fold: (a) the share of scored validation hours (D27 common hours) whose capacity_mw is above
the highest capacity_mw in the fold's training fit rows; (b) the Pearson correlation between capacity_mw
and the calendar date (Pacific date of the hour start, as a day number) within the fold's training fit rows.
A tree can only split capacity_mw at values it saw in training, so validation hours above the training
maximum all land on the same side of every capacity split.

Writes reports/evidence_capacity_check.csv.
"""

from __future__ import annotations

import pandas as pd

from src.evidence.common import LABEL
from src.modeling.features import assert_tv_only, build_features, load_tv_table
from src.modeling.folds import DEFAULT_LAYOUT, fold_masks, fold_table
from src.processing.build_hourly_table import ROOT
from src.processing.score_references import score_frame

OUT_CSV = ROOT / "reports" / "evidence_capacity_check.csv"


def main() -> None:
    print(f"Task 1b: capacity_mw against the date ({LABEL}); training and validation rows only\n")
    df = load_tv_table()
    assert_tv_only(df, "capacity_check")
    feat = build_features(df)
    common = score_frame(df, "d14", "clipped")["common"]
    day = (feat["local_start"].dt.tz_localize(None).dt.normalize() - pd.Timestamp("1970-01-01")).dt.days
    rows = []
    for fr in fold_table(DEFAULT_LAYOUT).itertuples():
        m = fold_masks(feat["local_start"], fr)
        tr = m["train"] & feat["fit_row"]
        val = m["val"] & feat["daylight"] & common
        cap_tr, cap_v = feat.loc[tr, "capacity_mw"], feat.loc[val, "capacity_mw"]
        top = cap_tr.max()
        rows.append(dict(fold=fr.fold, train_start=fr.train_start, train_end=fr.train_end, train_fit_rows=int(tr.sum()),
                         val_start=fr.val_start, val_end=fr.val_end, val_hours=int(val.sum()),
                         train_capacity_min_mw=cap_tr.min(), train_capacity_max_mw=top,
                         val_capacity_min_mw=cap_v.min(), val_capacity_max_mw=cap_v.max(),
                         share_val_above_train_max_pct=round((cap_v > top).mean() * 100, 2),
                         corr_capacity_vs_date_train=round(cap_tr.corr(day[tr]), 4), note=LABEL))
    t = pd.DataFrame(rows)
    if t["val_hours"].sum() != 4508:
        raise SystemExit(f"validation hours add to {t['val_hours'].sum()}, expected 4,508")
    t.to_csv(OUT_CSV, index=False)
    for r in t.itertuples():
        print(f"Fold {r.fold} (training {r.train_start} to {r.train_end}, {r.train_fit_rows:,} fit rows; "
              f"validation {r.val_start} to {r.val_end}, {r.val_hours:,} scored hours)")
        print(f"  training capacity {r.train_capacity_min_mw:,.0f} to {r.train_capacity_max_mw:,.0f} MW; "
              f"validation capacity {r.val_capacity_min_mw:,.0f} to {r.val_capacity_max_mw:,.0f} MW")
        print(f"  (a) {r.share_val_above_train_max_pct:.1f}% of validation hours have more capacity than any training hour")
        print(f"  (b) correlation of capacity with the date in the training rows: {r.corr_capacity_vs_date_train:.3f}")
    print("\nCapacity is EIA 860M monthly nameplate, all CISO (D18, D19).")
    print(f"written: {OUT_CSV.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
