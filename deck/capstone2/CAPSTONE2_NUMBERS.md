# Capstone 2 deck: where every number comes from

Updated 2026-11-07 for the corrected EIA timing rule (FAQ Decision D14) and the scoring definitions (D27). All numbers come from the processed hourly table (22,896 rows, 2024-03-08 to 2026-10-17), built by `python -m src.processing.build_hourly_table`. The full old-against-new comparison, with how each number was computed and its caveats, is in `reports/capstone2_numbers_corrected.md` (`python -m src.processing.capstone2_numbers`). Chart data is in `reports/deck_chart_data.csv` (`python -m src.processing.deck_chart_data`). Scores use daylight hours on training and validation days only (before 2026-04-10). The locked test block was not scored, and no model was scored on it.

| Number on slides | Value | How it was computed |
|---|---|---|
| Period, days | 2024-03-08 to 2026-10-17, 954 days | Window where the day-2 weather forecast exists |
| Hourly rows | 22,896 | 954 days x 24 hours |
| Daylight hours | 11,733 | Sun elevation above 0 at the middle of the hour (pvlib), at the capacity-weighted centre of the weather points (D20) |
| Hours with a gap | 226 (<1%) | EIA 25 (24 missing hours plus the 1 hour at the alignment switch) + CAISO forecast 72 + weather 129. The earlier 225 was an addition slip |
| Capacity | 21.0 GW (Mar 2024) to 26.0 GW (Sep 2026), +24% | EIA 860M monthly, all CISO nameplate (includes about 2.8 GW in AZ and NV) |
| Summer vs winter peak | 16,900 vs 11,900 MW, +42% | Mean EIA output by Pacific hour and season, training and validation days only. The earlier 17,400 vs 11,900 (+47%) used all days, including the test period, and the old timing rule |
| Cloud effect | 68%, 57%, 52%, 41% of capacity | Mean output / capacity for hours starting 10 a.m. to 12 p.m. Pacific, by day-2 forecast cloud cover bucket (0-10, 10-30, 30-60, 60-100%), all seasons; 2,285 hours |
| Sunshine correlation | 0.88 | Correlation of day-2 forecast shortwave radiation with output / capacity over 9,190 daylight hours |
| Biggest one-day drop | 133 to 55 GWh (-59%), 2026-03-31 | Daily EIA sum, full days only, training and validation days only. The earlier 161 to 73 GWh on 2026-10-10 is in the test period |
| Turned-down solar | 7.5% overall; 24% in Apr 2026; 19% in Mar 2025 | Curtailed MWh / (curtailed + EIA output), Pacific months, the 5 clock-change days left out of both parts (D22). Includes test-period months, so it is a description, not a model score |
| Same as yesterday | 4.9% (6.1% using the two-days-ago value) | Mean absolute error / capacity, daylight hours, same hours for all 4 references (D27) |
| CAISO as published | 4.7%, bias +777 MW | Same metric, CAISO day-ahead (NP15+SP15+ZP26) vs EIA |
| CAISO adjusted | 2.7% | CAISO vs (EIA + curtailed MWh). Partly by construction, because CAISO defines curtailment against its own forecast |
| Target range | 3.4% to 5.9% | 1.25 x 2.73% and 1.25 x 4.68% |
| Hours scored | 9,083 over 754 days | Daylight hours with EIA, CAISO, both persistence values and curtailment present, outside the weather gap, before 2026-04-10 |
| Split | 763 training and validation days, 191 test days (2026-04-10 to 2026-10-17) | Latest 20% of days locked |
| Weather API use | about 6,500 of 10,000 daily calls | Pull log (6,455 weighted calls on 2026-10-28) |

What changed since the first version of this file, and why: the EIA hour labels run one hour late until 2025-12-02, not for the whole period, so the single 1-hour shift used for the first deck was wrong after that date (D14). That moves CAISO as published from 5.7% to 4.7% and CAISO adjusted from 3.7% to 2.7%, and so the target range. The peaks and the biggest one-day drop now use training and validation days only, because the test set is locked. Same as yesterday (4.9%, 6.1%), the cloud buckets, the capacity growth and the day counts did not change.

Decisions that were open in the first version:
1. Which CAISO figure (4.7% or 2.7%) the 1.25x target uses. Still open. The deck shows both and the range 3.4% to 5.9%.
2. Whether "same as yesterday" means D-1 (4.9%) or D-2 (6.1%). Settled in D27: D-2 is the fair one for the 10 a.m. rule, D-1 is shown for comparison.
3. The EIA time alignment rule. Settled in D14: labels before 2025-12-02 22:00 UTC are moved back 1 hour, later labels are used as they are. Why EIA changed its labels is not known.
4. Small negative night values in EIA. Settled in D15: set to 0 in the modeling copy, the original kept in its own column.

6-minute deck (7 slides, Capstone 2 scope only): it shows no scores, no 1.25x target and no model results. The two charts on slide 5 are made by `python -m src.processing.deck_figures` from `reports/deck_chart_data.csv` and saved in `deck/capstone2/figures/`. The picture on slide 2 is from `docs/solar-primer.html`. New wording on slides 3 to 7 uses numbers already in the table above, plus these:

| Number on slides | Value | How it was computed |
|---|---|---|
| Odd night hours flagged | 351 | `eia_deep_night_flag`: EIA above 100 MW with the sun more than 12 degrees below the horizon (D16) |
| Negative night values | down to -74 MW | Set to 0 in the modeling copy `eia_mw`, original kept in `eia_mw_raw` (D15) |
| Weather outage hours | 129 | `wx_gap`: day-2 cloud cover blank, all in April 2026 |
| Correlation after the timing fix | 0.998 | EIA solar against CAISO's own actual solar (D14) |
| History length | 2.6 years | 954 days / 365 |
| Weather sources | 51 spots | `data/raw/weather_locations.csv` |
