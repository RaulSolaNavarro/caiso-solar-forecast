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
| Value size | 2.83 points, about 3.0 TWh and $117 million a year | `reserve_test.csv`, `value_sizing`: (7.268 - 4.435) x 1.06 TWh and x $41.3 million per point | From `deck/capstone2/CAPSTONE2_NUMBERS.md` ($39 per MWh, CAISO's 2025 average day-ahead price, D33). A size, not a savings promise |

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

## Evidence checks (post-hoc)

Added 2026-11-26 (Brief 9, FAQ Decision D34). Every number here is a post-hoc check, not a pre-registered test. Validation numbers use the 4,508 validation hours (out-of-fold); test numbers come from the saved predictions of the one test run. No model was refitted or scored on test, and no verdict changed. Code: `src/evidence/`. Curtailed means `curt_mwh` above 1% of `capacity_mw` (D30). Charts: `deck/capstone3/figures/evidence_*.png`.

| Number on slides | Value | Where it comes from | Plain caveat |
|---|---|---|---|
| Our error vs CAISO, hours without curtailment | Validation 3.58% vs 2.97% (2,344 h); test 3.59% vs 3.31% (929 h) | `reports/evidence_curtailment_split.csv` | CAISO is more accurate when no solar is turned down |
| Our error vs CAISO, curtailed hours | Validation 4.51% vs 6.17% (2,164 h); test 4.95% vs 7.40% (1,528 h) | same | Our whole lead over CAISO comes from these hours; CAISO forecasts before curtailment and EIA measures after |
| Share of hours curtailed | Test 62% (1,528 of 2,457); validation 48% (2,164 of 4,508) | same | The test lead leans more on curtailed hours than the validation lead |
| Our bias on test, by curtailment | +508 MW without, +486 MW with curtailment | same | The test over-forecast is not explained by curtailment alone; cause unknown (D31) |
| Cloud and curtailment together | Curtailed: we beat CAISO in all 8 cells. Not curtailed: CAISO wins 6 of 8, 1 tie, we win 1 (test, 60 to 100% cloud, 68 h) | `reports/evidence_cloud_by_curtailment.csv` | 4 cloud buckets x 2 periods; smallest cell 65 hours |
| Clear days without curtailment | Ours vs CAISO: validation 3.09% vs 2.33%; test 2.42% vs 2.08% | same | CAISO's strongest ground |
| Our lead over CAISO, test, 95% interval | +1.42 points; +0.86 to +2.00 (single days), +0.43 to +2.54 (7-day blocks) | `reports/evidence_bootstrap.csv` | Day-block bootstrap, 10,000 draws, seed 0. Clearly above zero either way |
| Our lead over CAISO, validation, 95% interval | +0.48 points; +0.11 to +0.87 (single days), -0.14 to +0.98 (7-day blocks) | same | Not clearly above zero once neighboring days stay together (ours lower in 91.9% of 7-day draws) |
| Lead over CAISO by curtailment, test, 95% interval | Not curtailed -0.27 (-0.69 to +0.11); curtailed +2.45 (+1.66 to +3.26), single days | same | 7-day blocks: -0.61 to +0.15 and +0.98 to +3.96 |
| H2 secondary margin, test, 95% interval | -0.005 points; -0.53 to +0.50 (single days), -0.86 to +0.85 (7-day blocks); met in 51.1% and 54.4% of draws | same | The miss is not distinguishable from zero; a pass by that margin would not be either. Verdict stays "partly supported" by the pre-registered rule |
| Lead over same as 2 days ago, test, 95% interval | +2.83 points; +2.10 to +3.61 (single days), +1.93 to +3.77 (7-day blocks) | same | |
| Errors with 95% intervals, test | Ours 4.43% (3.97 to 4.92); CAISO 5.85% (5.06 to 6.67); CAISO adjusted 3.54% (3.25 to 3.85); same as 2 days ago 7.27% (6.46 to 8.11) | same | Single-day draws |
| Cost of removing day-2 weather | +2.07 points (6.09% vs 4.02%); skill falls from 0.47 to 0.13 | `reports/evidence_input_groups.csv` | Validation folds only; each variant retuned on every fold |
| Cost of removing time and sun, recent output | +0.44 and +0.19 points | same | Recent output hurts slightly in fall (-0.17) |
| Effect of removing capacity | -0.31 points (3.72% vs 4.02%), better in all 4 seasons and 3 of 4 folds | same | The frozen model keeps it; this is a next step, not a change |
| Capacity stands in for the date | 95.0% to 97.1% of validation hours above the training maximum; correlation with the date 0.93 to 0.98 | `reports/evidence_capacity_check.csv` | Checked on validation folds. Whether it adds to the +494 MW test bias is only a possibility, not checked |
| Simple baselines (Chapter 7) | Training-mean capacity factor 18.96%; one-split tree on the best input 10.39% | `reports/evidence_input_groups.csv` | Both far worse than same as 2 days ago (6.60%) |
| Most informative single inputs | Day-2 direct normal irradiance 0.707, direct radiation 0.705, sunshine (GHI) 0.699 of variance removed | `reports/evidence_input_ranking.csv` | One split on one input; cloud cover ranks 16th alone but weather as a group matters most |
| Training, validation and test error | 3.07%, 4.02%, 4.43% | `reports/evidence_fit_gap.csv` | Training is the frozen settings refit on 9,187 rows, in-sample; validation is the pooled fold models |
| Fitting graph | Unseen-day error lowest at 86 trees (4.45%); 4.73% at 400 trees while learned-day error falls to 2.30% | `reports/evidence_fitting_graph.csv`, `evidence_fitting_graph.png` | Inner split of the final window; no test data |
| Fold spread | Ours 3.12% to 4.60% (sd 0.67); CAISO 2.67% to 6.20% (sd 1.62); ours lower than CAISO in 2 of 4 folds | `reports/evidence_fold_spread.csv` | We lead in the spring and winter folds; CAISO in summer and fall |
| Error by hour, test | Our bias positive in every hour (+219 to +793 MW); we beat CAISO from 7 a.m. to 5 p.m. | `reports/evidence_error_by_hour.csv`, `evidence_error_by_hour.png` | CAISO is better at 6 a.m., 6 p.m. and 7 p.m. |
| Backup against coverage | Ours needs less than same as 2 days ago from 76% coverage up; at 50%: 230 vs 0 MW; at 95%: 3,630 vs 4,790 MW | `reports/evidence_backup_curve.csv`, `evidence_backup_curve.png` | Today's fleet: 860M nameplate 2026-09, all CISO. The 90, 95 and 99% points equal `reserve_test.csv` |
