"""Brief 9, Task 4b: error by day-2 cloud bucket, split by curtailment (post-hoc check, not a pre-registered test).

Run from the repo root:
    python -m src.evidence.cloud_by_curtailment

On the 4,508 validation hours (out-of-fold) and the 2,457 test hours (saved predictions), reports hours
and nMAE for HGB, CAISO as published and persistence D-2, by day-2 cloud bucket (the buckets of
score_models.py and reports/capstone3_nmae_by_cloud.csv) and by curtailment (D30 threshold, curt_mwh
above 1% of capacity_mw). Cells with fewer than 50 hours are flagged. cloud_cover_previous_day2 is in
both saved prediction files, so no join is needed. Reads saved predictions only.

Writes reports/evidence_cloud_by_curtailment.csv.
"""

from __future__ import annotations

import pandas as pd

from src.evidence.common import LABEL, ROOT, curtailed, load_test, load_val, nmae, reproduce
from src.modeling.score_models import CLOUD_LABELS
from src.processing.capstone2_numbers import CLOUD_BINS

OUT_CSV = ROOT / "reports" / "evidence_cloud_by_curtailment.csv"
CHECK_CSV = ROOT / "reports" / "capstone3_nmae_by_cloud.csv"
MODELS = {"hgb": "HGB", "caiso_published": "CAISO pub.", "persistence_d2": "Persist. D-2"}
MIN_HOURS = 50


def bucket(df: pd.DataFrame) -> pd.Series:
    if df["cloud_cover_previous_day2"].isna().any():
        raise SystemExit("cloud_cover_previous_day2 has blanks in scored hours")
    b = pd.cut(df["cloud_cover_previous_day2"], CLOUD_BINS, labels=CLOUD_LABELS).astype(str)
    if (b == "nan").any():
        raise SystemExit("a cloud value falls outside the buckets")
    return b


def table(df: pd.DataFrame, period: str) -> pd.DataFrame:
    b, cut = bucket(df), curtailed(df).map({False: "not curtailed", True: "curtailed"})
    rows = []
    for grp in ["not curtailed", "curtailed", "all"]:
        for c in CLOUD_LABELS:
            g = df[(b == c) & ((cut == grp) if grp != "all" else True)]
            for m in MODELS:
                rows.append(dict(period=period, curtailment=grp, cloud_d2=c, model=m, hours=len(g),
                                 nmae_pct=round(nmae(g, m), 4) if len(g) else None,
                                 under_50_hours=len(g) < MIN_HOURS, note=LABEL))
    return pd.DataFrame(rows)


def show(t: pd.DataFrame, title: str) -> None:
    print(f"\n{title}")
    print(f"  {'curtailment':<14}{'cloud %':<9}{'hours':>7}  " + "".join(f"{v:>13}" for v in MODELS.values()))
    for grp in ["not curtailed", "curtailed"]:
        for c in CLOUD_LABELS:
            s = t[(t["curtailment"] == grp) & (t["cloud_d2"] == c)].set_index("model")
            h = int(s["hours"].iloc[0])
            flag = "  <50 h" if h < MIN_HOURS else ""
            vals = "".join(f"{s.loc[m, 'nmae_pct']:>12.2f}%" if h else f"{'-':>13}" for m in MODELS)
            print(f"  {grp:<14}{c:<9}{h:>7,}  {vals}{flag}")


def main() -> None:
    reproduce()
    print("\n" + "=" * 100)
    print(f"Task 4b: nMAE by day-2 cloud bucket and curtailment ({LABEL})")
    v, t = load_val(), load_test()
    tv, tt = table(v, "validation"), table(t, "test")

    # cross-checks: the split cells add up to the unsplit bucket, and the test buckets match capstone3_nmae_by_cloud.csv
    for tab, n in [(tv, len(v)), (tt, len(t))]:
        hgb = tab[tab["model"] == "hgb"]
        split = hgb[hgb["curtailment"] != "all"].groupby("cloud_d2")["hours"].sum()
        whole = hgb[hgb["curtailment"] == "all"].set_index("cloud_d2")["hours"]
        if not split.equals(whole.loc[split.index]) or whole.sum() != n:
            raise SystemExit("bucket hours do not add up")
    ref = pd.read_csv(CHECK_CSV)
    mine = tt[tt["curtailment"] == "all"]
    m = ref.merge(mine, on=["model", "cloud_d2"], suffixes=("_ref", ""))
    if len(m) != len(ref) or (m["hours"] != m["hours_ref"]).any() or (m["nmae_pct"] - m["nmae_pct_ref"]).abs().max() > 0.01:
        raise SystemExit("test buckets do not match reports/capstone3_nmae_by_cloud.csv")
    print(f"Check: test bucket hours and nMAE match {CHECK_CSV.relative_to(ROOT).as_posix()} "
          f"(largest difference {(m['nmae_pct'] - m['nmae_pct_ref']).abs().max():.4f} points); "
          "split cells add up to each bucket.")

    show(tv, f"VALIDATION ({len(v):,} hours, out-of-fold)")
    show(tt, f"TEST ({len(t):,} hours, saved predictions from the one test run)")
    out = pd.concat([tv, tt], ignore_index=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nRows with curtailment = 'all' are the unsplit buckets, kept in the file for reference.")
    print(f"written: {OUT_CSV.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
