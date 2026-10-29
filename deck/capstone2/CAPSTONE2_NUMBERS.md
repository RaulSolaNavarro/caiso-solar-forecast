# Capstone 2 deck: where every number comes from

All numbers are from the merged hourly table (22,896 rows, 2024-03-08 to 2026-10-17) built from the raw files in `data/raw/` with the recipes in `docs/DATA_HOWTO.md`. Scores use daylight hours on training and validation days only (before 2026-04-10). The locked test block was not scored.

| Number on slides | Value | How it was computed |
|---|---|---|
| Period, days | 2024-03-08 to 2026-10-17, 954 days | Window where the day-2 weather forecast exists |
| Hourly rows | 22,896 | 954 days x 24 hours |
| Daylight hours | 11,733 | Sun elevation above 0 at the hour (pvlib) |
| Hours with a gap | 225 (<1%) | EIA 24 + CAISO forecast 72 + weather 129 missing hours |
| Capacity | 21.0 GW (Mar 2024) to 26.0 GW (Sep 2026), +24% | EIA 860M monthly, all CISO nameplate (includes about 2.8 GW in AZ and NV) |
| Summer vs winter peak | 17,400 vs 11,900 MW, +47% | Average EIA output by Pacific hour and season, training and validation days |
| Cloud effect | 68%, 57%, 52%, 41% of capacity | Mean midday (11 a.m. to 2 p.m. Pacific) output / capacity, by day-2 forecast cloud cover bucket (0-10, 10-30, 30-60, 60-100%); includes all seasons |
| Sunshine correlation | 0.87 | Correlation of day-2 forecast shortwave radiation with output / capacity over 9,188 daylight hours |
| Biggest one-day drop | 161 to 73 GWh (-55%), 2026-10-10 | Daily EIA sum, full days only |
| Turned-down solar | 7.6% overall; 24% in Apr 2026; 20% in Mar 2025 | Curtailed MWh / (curtailed + EIA output). Month boundaries in UTC; a Pacific-month recount differs by up to 0.4 points |
| Same as yesterday | 4.9% (6.1% using the two-days-ago value) | Mean absolute error / capacity, daylight hours |
| CAISO as published | 5.7%, bias +828 MW | Same metric, CAISO day-ahead (NP15+SP15+ZP26) vs EIA |
| CAISO adjusted | 3.7% | CAISO vs (EIA + curtailed MWh). Partly by construction, because CAISO defines curtailment against its own forecast |
| Target range | 4.6% to about 7% | 1.25 x 3.68% and 1.25 x 5.72% |
| Hours scored | 9,144 over 759 days | Daylight hours with EIA, CAISO and persistence values, before 2026-04-10 |
| Split | 763 training and validation days, 191 test days (2026-04-10 to 2026-10-17) | Latest 20% of days locked |
| Weather API use | about 6,500 of 10,000 daily calls | Pull log (6,455 weighted calls on 2026-10-28) |

Open decisions the numbers expose (also in the project plan risk register):
1. Which CAISO figure (5.7% or 3.7%) the 1.25x target uses.
2. Whether "same as yesterday" means D-1 (4.9%, uses afternoon information not available at 10 a.m.) or D-2 (6.1%, information-correct).
3. The EIA time alignment rule (hour ending UTC = EIA label minus one hour) to be confirmed.
4. How to treat small negative night values in EIA (about -40 MW).
