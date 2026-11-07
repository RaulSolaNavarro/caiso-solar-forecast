"""Validation folds for the training and validation days (FAQ Decision D29).

Run from the repo root:
    python -m src.modeling.folds                    prints every layout, writes the chosen one
    python -m src.modeling.folds --layout d24       write a different layout to reports/folds.csv

Training and validation days are the Pacific dates of the hour start from 2024-03-08 to 2026-04-09
(763 full days). The window's first 8 hours fall on Pacific date 2024-03-07; they are left out of
every fold so each fold uses whole days.

Each fold: training is every day from 2024-03-08 up to its end, then 1 whole gap day that neither
trains nor validates, then a validation block of about 91 days (expanding window). Inside each
training window, the last 10% of training days (after their own 1-day gap) is the inner split: early
stopping for the gradient-boosted trees and the alpha choice for ridge. The validation block is never
used to tune.
"""

from __future__ import annotations

import argparse

import pandas as pd

from src.processing.build_hourly_table import ROOT, TEST_START

OUT_CSV = ROOT / "reports" / "folds.csv"
FIRST_DAY = pd.Timestamp("2024-03-08")
LAST_DAY = pd.Timestamp("2026-04-09")                    # last Pacific date before the test set
TEST_DAY = TEST_START.tz_localize(None)                  # 2026-04-10
GAP_DAYS = 1
INNER_SHARE = 0.10

# Validation blocks (first day, last day), Pacific dates
LAYOUTS = {
    # FAQ D24 as recorded: the last 4 blocks of 91 days. Winter is split between folds 3 and 4.
    "d24": [("2025-04-11", "2025-07-10"), ("2025-07-11", "2025-10-09"),
            ("2025-10-10", "2026-01-08"), ("2026-01-09", "2026-04-09")],
    # 4 blocks of 91 days with fold 4 = Dec 27 to Mar 27; the last 13 days (2026-03-28 to 04-09) are not validated
    "winter91": [("2025-03-29", "2025-06-27"), ("2025-06-28", "2025-09-26"),
                 ("2025-09-27", "2025-12-26"), ("2025-12-27", "2026-03-27")],
    # As winter91, but fold 4 runs on to 2026-04-09 (104 days) so every recent day is validated
    "winter104": [("2025-03-29", "2025-06-27"), ("2025-06-28", "2025-09-26"),
                  ("2025-09-27", "2025-12-26"), ("2025-12-27", "2026-04-09")],
}
DEFAULT_LAYOUT = "winter104"


def months_covered(start: pd.Timestamp, end: pd.Timestamp) -> str:
    days = pd.date_range(start, end, freq="D")
    counts = days.to_period("M").value_counts().sort_index()
    return ", ".join(f"{p} ({n})" for p, n in counts.items())


def fold_table(layout: str = DEFAULT_LAYOUT) -> pd.DataFrame:
    rows = []
    for k, (vs, ve) in enumerate(LAYOUTS[layout], 1):
        vs, ve = pd.Timestamp(vs), pd.Timestamp(ve)
        gap_day = vs - pd.Timedelta(days=GAP_DAYS)
        te = gap_day - pd.Timedelta(days=1)
        train_days = (te - FIRST_DAY).days + 1
        inner_days = max(1, round(train_days * INNER_SHARE))
        inner_start = te - pd.Timedelta(days=inner_days - 1)
        val_days = pd.date_range(vs, ve, freq="D")
        rows.append(dict(
            fold=k, train_start=FIRST_DAY.date(), train_end=te.date(), train_days=train_days,
            gap_start=gap_day.date(), gap_end=(vs - pd.Timedelta(days=1)).date(), gap_days=GAP_DAYS,
            val_start=vs.date(), val_end=ve.date(), val_days=len(val_days),
            winter_val_days=int(val_days.month.isin([12, 1, 2]).sum()),
            inner_fit_end=(inner_start - pd.Timedelta(days=GAP_DAYS + 1)).date(),
            inner_val_start=inner_start.date(), inner_val_days=inner_days,
            months_covered=months_covered(vs, ve)))
    t = pd.DataFrame(rows)
    check_folds(t)
    return t


def check_folds(t: pd.DataFrame) -> None:
    """No fold trains on its own validation days, gap days are whole, nothing touches the test period."""
    for r in t.itertuples():
        ts, te, vs, ve = (pd.Timestamp(x) for x in (r.train_start, r.train_end, r.val_start, r.val_end))
        assert ts >= FIRST_DAY and ve <= LAST_DAY and ve < TEST_DAY, f"fold {r.fold} outside 2024-03-08..2026-04-09"
        assert (vs - te).days - 1 >= GAP_DAYS, f"fold {r.fold}: less than {GAP_DAYS} whole gap day"
        assert te < vs, f"fold {r.fold}: training overlaps validation"
        assert pd.Timestamp(r.inner_fit_end) < pd.Timestamp(r.inner_val_start) <= te
    v = t[["val_start", "val_end"]].apply(pd.to_datetime)
    assert (v["val_start"].iloc[1:].values > v["val_end"].iloc[:-1].values).all(), "validation blocks overlap"


def fold_masks(local_start: pd.Series, fold_row) -> dict[str, pd.Series]:
    """Boolean row masks (train, inner_fit, inner_val, val) by Pacific date of the hour start."""
    if (local_start >= TEST_START).any():
        raise AssertionError("test-period rows reached fold_masks; the test set is locked")
    day = local_start.dt.tz_localize(None).dt.normalize()
    d = lambda x: pd.Timestamp(x)
    between = lambda a, b: (day >= d(a)) & (day <= d(b))
    return {"train": between(fold_row.train_start, fold_row.train_end),
            "inner_fit": between(fold_row.train_start, fold_row.inner_fit_end),
            "inner_val": between(fold_row.inner_val_start, fold_row.train_end),
            "val": between(fold_row.val_start, fold_row.val_end)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--layout", choices=list(LAYOUTS), default=DEFAULT_LAYOUT)
    args = ap.parse_args()
    cols = ["fold", "train_start", "train_end", "train_days", "gap_start", "val_start", "val_end", "val_days",
            "winter_val_days", "inner_val_start", "inner_val_days"]
    with pd.option_context("display.width", 220, "display.max_colwidth", 120):
        for name in LAYOUTS:
            t = fold_table(name)
            used = t["val_days"].sum()
            print(f"=== layout {name}{' (default)' if name == DEFAULT_LAYOUT else ''}: "
                  f"{used} validation days, {int(t['winter_val_days'].sum())} of them in Dec to Feb")
            print(t[cols].to_string(index=False))
            print(t[["fold", "months_covered"]].to_string(index=False), "\n")
    t = fold_table(args.layout)
    t.insert(0, "layout", args.layout)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT_CSV, index=False)
    print(f"written: {OUT_CSV.relative_to(ROOT).as_posix()} (layout {args.layout})")


if __name__ == "__main__":
    main()
