# Capstone 3 deck: where every number comes from

Written 2026-11-07, after the one test run (`python -m src.modeling.final_test --final-test`, code version `c242a1c`, frozen spec `reports/final_model_spec.md`). Test numbers come from `reports/final_results_test.csv` (2,457 daylight hours on 187 days, Pacific dates 2026-04-10 to 2026-10-17, the D27 common hours). Validation numbers come from `reports/model_results_validation.csv` (4,508 hours on 374 days, the folds of FAQ Decision D29). Errors are divided by EIA 860M monthly nameplate, all CISO (D18, D19). Our model is the gradient-boosted tree model (HGB, D30). The test set was scored once.

## Headline

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| Our model's error, test | 4.43% (4.4348%) | `final_results_test.csv`, model `hgb`, metric `nmae_pct`, group `all` | Average miss as a share of installed solar, daylight hours only. Spring and summer only: the test half-year has no winter |
| CAISO's error, test | 5.85% | same file, `caiso_published` | CAISO forecasts output before curtailment; EIA measures it after, so part of CAISO's miss is solar that was turned down, not a weather miss |
| Target: 1.25 x CAISO as published | 7.32% | 1.25 x 5.8532 | The primary target (D27 check: CAISO adjusted is partly circular) |
| CAISO adjusted for curtailment, test | 3.54% | `caiso_adjusted` | Partly circular: CAISO measures curtailment against its own forecast, so adding it back removes much of CAISO's error by construction |
| 1.25 x CAISO adjusted | 4.43% (4.4294%) | 1.25 x 3.5435 | Our model misses it by 0.005 points. Report it as missed; do not round it into a pass |
| Same as 2 days ago, test | 7.27% | `persistence_d2` | The fair simple forecast: everything it uses is known before the 10 a.m. bid close |
| Same as yesterday, test | 5.51% | `persistence_d1` | Uses output from after the bid close, so no bidder could use it. Comparison only |
| Ridge (straight-line model), test | 5.21% | `ridge` | Dropped in validation (D30); shown for H3 |
| Climatology (monthly average day), test | 6.17% | `climatology` | A floor that uses no weather |
| Skill vs same as 2 days ago | 0.40 (0.4025) | `hgb`, `skill_vs_persistence_d2` | 1 minus our RMSE / its RMSE; 0.30 was the target |
| Skill vs CAISO as published | 0.30 (0.303) | `hgb`, `skill_vs_caiso_published` | Same curtailment caveat as CAISO's error |
| Bias, test | +494 MW (validation -186 MW) | `hgb`, `bias_mw` | We forecast too high on average in the test half-year, most in April and May 2026 (+1,009 and +1,223 MW), when curtailment was 24.0% and 20.7% of solar (`reports/capstone2_numbers_corrected.md`) |
| MAPE, test | 10.2% | `hgb`, `mape_pct` | Only hours above 5% of capacity. Not used to rank |
| Hours and days scored | 2,457 hours, 187 days | `final_test.py` output | Daylight, outside the 129-hour weather gap (D17), with every reference forecast present (D27) |

## The 5 hypotheses (`reports/hypotheses.md`)

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| H1 weather adds value | Supported: skill 0.40 (target 0.30; validation 0.47) | `hgb`, `skill_vs_persistence_d2` | Smaller margin than in validation |
| H2 close to the pros | Partly supported: 4.43% vs 7.32% (met); vs 4.43% adjusted (missed by 0.005 points) | `nmae_pct` of `hgb`, `caiso_published`, `caiso_adjusted` | Same verdict as validation |
| H3 trees beat the straight line | Supported: 4.43% vs 5.21% | `hgb`, `ridge` | |
| H4 clouds are where the error lives | Supported: 5.90% at 60-100% cloud vs 3.80% at 0-10% (+2.10 points) | groups `cloud_d2=60-100`, `cloud_d2=0-10` | Only 133 test hours in the cloudiest bucket |
| H5 it shrinks the reserve | Supported: P95 overshoot 3,557 MW vs 4,638 MW, -23.3% (target -20%) | `hgb`, `p95_overshoot_mw`, `p95_vs_persistence_d2_pct` | Validation showed -51.2%; the test margin is much smaller |

## Clouds (chart `nmae_by_cloud.png`, data `reports/capstone3_nmae_by_cloud.csv`)

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| Our error by day-2 cloud cover | 3.80%, 5.21%, 4.98%, 5.90% (0-10, 10-30, 30-60, 60-100%) | `final_results_test.csv`, groups `cloud_d2=` | Cloud cover is the forecast known before the bid, not the observed sky. Hours: 1,364, 621, 339, 133 |
| CAISO's error by cloud | 4.80%, 6.64%, 7.38%, 9.05% | same | |
| Same as 2 days ago by cloud | 5.78%, 8.46%, 8.39%, 14.10% | same | |
| Rise from clear to cloudy | ours +2.1, CAISO +4.3, same as 2 days ago +8.3 points | 60-100 minus 0-10 | |

## Months (chart `nmae_by_month.png`, data `reports/capstone3_nmae_by_month.csv`)

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| Our error by test month | Apr 5.9, May 6.5, Jun 4.3, Jul 3.8, Aug 3.4, Sep 3.5, Oct 3.7% | `final_results_test.csv`, groups `month=` | April starts on Apr 10 and October ends on Oct 17 |
| Our error, winter months (validation) | Dec 2025 4.2, Jan 2026 3.8, Feb 2026 4.9% | `model_results_validation.csv`, `pooled`, `month=` | Winter was checked only in validation. March 2025 has only 3 validation days (36 hours) |
| Spring is hardest | Spring test 6.34% vs validation 4.95% | `test_vs_validation.csv`, `season=spring` | Curtailment in April and May 2026 was much higher than a year earlier (24.0% and 20.7% vs 13.2% and 6.6%) |

## Reserve (chart `reserve_p95.png`; `src/modeling/reserve.py`, `reports/reserve_test.csv`)

All MW for today's fleet use the share of capacity times EIA 860M nameplate 2026-09, all CISO, 26,034.5 MW.

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| Backup to cover 95 of 100 daylight hours, our model | about 3,630 MW (13.9% of capacity) | `reserve_test.csv`, `hgb`, `all`, `P95`, `mw_today_fleet` | Over-forecast counts any hour where actual EIA output came in below the forecast, including hours when solar was curtailed and backup was not needed |
| Same, same as 2 days ago | about 4,790 MW (18.4%) | `persistence_d2` | |
| Same, CAISO as published | about 5,890 MW (22.6%) | `caiso_published` | Overstated most, because CAISO forecasts before curtailment. Spring alone: 7,770 MW |
| 90 and 99 of 100 hours, our model | about 2,650 MW and 5,740 MW | `P90`, `P99` | The 99 figure rests on about 25 hours |
| Value size | 2.83 points, about 3.0 TWh and $122 million a year | `reserve_test.csv`, `value_sizing`: (7.268 - 4.435) x 1.06 TWh and x $43 million per point | From `deck/capstone2/CAPSTONE2_NUMBERS.md` ($41 per MWh, CAISO's 2024 average day-ahead price). A size, not a savings promise |

## Sample days (chart `sample_days.png`, data `reports/capstone3_sample_days.csv`)

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| Clear day | Jun 29, 2026: cloud 2%, our error 2.7% | `capstone3_figures.sample_days` | Median-error day among test days with average day-2 cloud 0-10%. Not hand-picked |
| Partly cloudy day | Sep 23, 2026: cloud 17%, our error 4.5% | same | Median-error day, 10-60% cloud |
| Cloudy day | Apr 25, 2026: cloud 80%, our error 4.5% | same | Median-error day, above 60% cloud |

## Test against validation (`reports/test_vs_validation.csv`, `python -m src.modeling.test_vs_validation`)

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| Our error, validation vs test | 4.02% vs 4.43% (+0.41 points) | pooled `nmae_pct` | Below the 0.5-point flag |
| CAISO as published, validation vs test | 4.51% vs 5.85% (+1.35) | same | Spring 2026: 12.1% |
| Same as 2 days ago, validation vs test | 6.60% vs 7.27% (+0.67) | same | Summer 2026 was harder for it than summer 2025 (6.51% vs 3.67%) |
| Comparisons above 0.5 points | 141 of 231 | `above_0_5` | Many are small groups (single hours or months) |
