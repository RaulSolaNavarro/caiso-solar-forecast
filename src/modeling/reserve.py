"""Reserve estimate from the one test run (Brief 4, Task C step 3).

Run from the repo root, after final_test --final-test has run (it reads its saved predictions; it never
refits or rescores a model):
    python -m src.modeling.reserve

Overshoot = forecast minus actual EIA output when positive (solar comes in under the forecast), 0
otherwise, over every scored daylight test hour (D27 common hours, 2,457). The P90, P95 and P99 of
overshoot are the MW of backup that would have covered 90, 95 and 99 of 100 daylight hours.

Each is shown 3 ways: MW on the test hours; as a share of that hour's capacity_mw; and that share times
the EIA 860M nameplate of 2026-09, all CISO, to express it for today's fleet.

Value sizing (from deck/capstone2/CAPSTONE2_NUMBERS.md): 1 point of nMAE is about 1.06 TWh a year and
about $43 million at $41 per MWh. The nMAE gap between persistence D-2 and HGB on the test hours times
those figures is a size, not a savings promise.

Writes reports/reserve_test.csv.
"""

from __future__ import annotations

import pandas as pd

from src.processing.build_hourly_table import PROCESSED, ROOT, capacity_by_month

PRED = PROCESSED / "test_predictions.parquet"
RESULTS = ROOT / "reports" / "final_results_test.csv"
OUT_CSV = ROOT / "reports" / "reserve_test.csv"
MODELS = {"hgb": "HGB (our model)", "persistence_d2": "Persistence D-2", "caiso_published": "CAISO as published"}
QUANTILES = {"P90": 0.90, "P95": 0.95, "P99": 0.99}
SEASON = {4: "spring", 5: "spring", 6: "summer", 7: "summer", 8: "summer", 9: "fall", 10: "fall"}
FLEET_MONTH = "2026-09"
TWH_PER_POINT, MUSD_PER_POINT, USD_PER_MWH = 1.06, 43, 41      # CAPSTONE2_NUMBERS.md, "Solar miss" rows


def fleet_mw() -> float:
    all_ciso, _ = capacity_by_month()
    return float(all_ciso.loc[FLEET_MONTH])


def reserve_table(scored: pd.DataFrame, fleet: float) -> pd.DataFrame:
    rows = []
    season = scored["local_start"].dt.month.map(SEASON)
    for model, label in MODELS.items():
        over = (scored[model] - scored["actual"]).clip(lower=0)
        share = over / scored["capacity_mw"]
        for grp, mask in [("all", pd.Series(True, index=scored.index))] + [(s, season == s) for s in ["spring", "summer", "fall"]]:
            for qn, q in QUANTILES.items():
                mw, sh = over[mask].quantile(q), share[mask].quantile(q)
                cover = int(round(q * 100))
                where = "" if grp == "all" else f" in {grp}"
                rows.append(dict(
                    model=model, season=grp, quantile=qn, hours=int(mask.sum()), overshoot_mw_test=round(mw, 0),
                    share_of_capacity_pct=round(sh * 100, 2), mw_today_fleet=round(sh * fleet, -1),
                    sentence=(f"{label}: hold about {round(sh * fleet, -1):,.0f} MW of backup to cover {cover} of 100 "
                              f"daylight hours{where} ({sh * 100:.1f}% of capacity; EIA 860M nameplate {FLEET_MONTH}, "
                              f"all CISO, {fleet:,.1f} MW)")))
    return pd.DataFrame(rows)


def main() -> None:
    if not PRED.exists():
        raise SystemExit(f"{PRED} not found: it is written by the one test run (final_test --final-test)")
    pred = pd.read_parquet(PRED)
    scored = pred[pred["common"]]
    fleet = fleet_mw()
    t = reserve_table(scored, fleet)

    res = pd.read_csv(RESULTS)
    nmae = lambda m: float(res[(res["model"] == m) & (res["metric"] == "nmae_pct") & (res["group"] == "all")]["value"].iloc[0])
    gap = nmae("persistence_d2") - nmae("hgb")
    sizing = pd.DataFrame([dict(model="value_sizing", season="all", quantile="", hours=len(scored),
                                overshoot_mw_test=None, share_of_capacity_pct=round(gap, 2), mw_today_fleet=None,
                                sentence=(f"nMAE gap persistence D-2 minus HGB on the test hours: {gap:.2f} points, about "
                                          f"{gap * TWH_PER_POINT:.1f} TWh and ${gap * MUSD_PER_POINT:,.0f} million a year "
                                          f"at ${USD_PER_MWH} per MWh: a size, not a savings promise"))])
    out = pd.concat([t, sizing], ignore_index=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    print(f"Reserve from the one test run: {len(scored):,} scored daylight hours, Pacific dates "
          f"{scored['local_start'].min():%Y-%m-%d} to {scored['local_start'].max():%Y-%m-%d}")
    print(f"Today's fleet: EIA 860M nameplate {FLEET_MONTH}, all CISO = {fleet:,.1f} MW\n")
    with pd.option_context("display.width", 200):
        print(t.drop(columns="sentence").to_string(index=False))
    print("\nIn plain words (all daylight test hours):")
    for s in t[t["season"] == "all"]["sentence"]:
        print("  " + s)
    print("\n" + sizing["sentence"].iloc[0])
    print(f"\nwritten: {OUT_CSV.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
