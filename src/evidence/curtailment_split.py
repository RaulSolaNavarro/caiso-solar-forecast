"""Brief 9, Task 4: results with and without curtailed hours (post-hoc check, not a pre-registered test).

Run from the repo root:
    python -m src.evidence.curtailment_split

Splits the scored hours by the D30 threshold (curtailed: curt_mwh above 1% of capacity_mw) on the
4,508 validation hours (out-of-fold predictions) and the 2,457 test hours (saved test predictions).
Reads saved predictions only; no model is fitted or rescored. Each forecast is scored against its own
actual as in D27 and score_models.py: CAISO adjusted against EIA plus curt_mwh, every other forecast
against EIA. curt_mwh is already in both prediction files, so no join is needed.

Writes reports/evidence_curtailment_split.csv.
"""

from __future__ import annotations

import pandas as pd

from src.evidence.common import LABEL, MODELS, ROOT, curtailed, load_test, load_val, reproduce
from src.modeling.score_models import CURT_SHARE, metrics

OUT_CSV = ROOT / "reports" / "evidence_curtailment_split.csv"
GROUPS = {False: "not curtailed", True: "curtailed"}


def split_table(df: pd.DataFrame, period: str) -> pd.DataFrame:
    cut = curtailed(df)
    rows = []
    for flag, name in [(None, "all")] + list(GROUPS.items()):
        g = df if flag is None else df[cut == flag]
        for model, label in MODELS.items():
            m = metrics(g, model)
            rows.append(dict(period=period, group=name, model=model, model_label=label, hours=len(g),
                             days=g["local_start"].dt.date.nunique(),
                             nmae_pct=round(float(m["nmae_pct"]), 4), bias_mw=round(float(m["bias_mw"]), 1),
                             actual="EIA + curt_mwh" if model == "caiso_adjusted" else "EIA",
                             note=LABEL))
    return pd.DataFrame(rows)


def show(t: pd.DataFrame, period: str) -> None:
    s = t[t["group"] != "all"]
    hours = s.groupby("group", sort=False)["hours"].first()
    print(f"\n{period.upper()}: curtailed means curt_mwh above {CURT_SHARE:.0%} of capacity_mw (D30)")
    for metric, fmt, unit in [("nmae_pct", "{:.2f}", "nMAE, % of capacity"), ("bias_mw", "{:+,.0f}", "bias, MW (forecast minus actual)")]:
        p = s.pivot(index="group", columns="model_label", values=metric).loc[list(GROUPS.values()), list(MODELS.values())]
        p = p.map(fmt.format)
        p.index = [f"{g} ({hours[g]:,} h)" for g in p.index]
        print(f"\n  {unit}")
        with pd.option_context("display.width", 200):
            print("  " + p.to_string().replace("\n", "\n  "))


def main() -> None:
    reproduce()
    print("\n" + "=" * 100)
    print(f"Task 4: results with and without curtailed hours ({LABEL})")
    v, t = load_val(), load_test()
    tv, tt = split_table(v, "validation"), split_table(t, "test")
    for tab, n in [(tv, 4508), (tt, 2457)]:
        parts = tab[(tab["model"] == "hgb") & (tab["group"] != "all")]["hours"].sum()
        if parts != n:
            raise SystemExit(f"split hours add to {parts}, expected {n}")
    show(tv, "validation (out-of-fold, 4 folds)")
    show(tt, "test (saved predictions from the one test run)")
    out = pd.concat([tv, tt], ignore_index=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nCAISO adjusted is scored against EIA plus curt_mwh (D27); every other forecast against EIA.")
    print(f"written: {OUT_CSV.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
