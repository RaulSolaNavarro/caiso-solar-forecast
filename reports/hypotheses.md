# Pre-registered hypotheses for the locked test set

Written on 2026-11-07, before any test row was read by a model. The validation verdicts come from `reports/model_results_validation.csv` (4 folds of FAQ Decision D29, 4,508 daylight hours on 374 days, the D27 common hours). The test verdicts are filled in once, after the single run of `python -m src.modeling.final_test --final-test`. No hypothesis or threshold changes after that run, and a "not supported" verdict stays as it is.

HGB is the gradient-boosted tree model carried forward (D30). nMAE is the mean absolute error divided by EIA 860M monthly nameplate, all CISO, in %. Persistence D-2 repeats EIA output from 48 hours earlier.

| ID | Hypothesis | Test (pass rule) | Validation number | Validation verdict | Test verdict |
|---|---|---|---|---|---|
| H1 | Weather adds value | HGB RMSE skill score vs persistence D-2 at least 0.30 | 0.473 | Supported | **Supported**: 0.403 |
| H2 | Close to the pros | Primary: HGB nMAE at most 1.25 x CAISO as published. Secondary: at most 1.25 x CAISO adjusted, which is partly circular (D27, Task A check). Supported if both hold, partly supported if only the primary holds | 4.02% vs 5.63% (primary, met in all 4 folds); 4.02% vs 3.44% (secondary, met only in fold 2) | Partly supported | **Partly supported**: primary met, 4.43% vs 7.32% (1.25 x 5.85%); secondary missed, 4.4348% vs 4.4294% (1.25 x 3.5435%), by 0.005 points |
| H3 | Trees beat the simple model | Validation: HGB nMAE below ridge's pooled and in at least 3 of 4 folds. Test: below ridge's pooled | 4.02% vs 4.70% pooled; lower in 4 of 4 folds (4.60 vs 5.07, 3.12 vs 3.96, 3.91 vs 4.50, 4.47 vs 5.29) | Supported | **Supported**: 4.43% vs 5.21% pooled |
| H4 | Clouds are where the error lives | HGB nMAE in the 60 to 100% day-2 cloud bucket higher than in the 0 to 10% bucket (direction only; size reported) | 4.43% vs 3.74% (+0.69 points) | Supported | **Supported**: 5.90% vs 3.80% (+2.10 points) |
| H5 | It shrinks the reserve | HGB P95 overshoot at least 20% below persistence D-2 | 2,033 MW vs 4,169 MW (-51.2%) | Supported | **Supported**: 3,557 MW vs 4,638 MW (-23.3%) |

## H4 context: nMAE by day-2 cloud cover, validation (pooled)

| Day-2 cloud cover | Hours | Persistence D-2 | CAISO as published | HGB |
|---|---|---|---|---|
| 0 to 10% | 2,540 | 4.99% | 4.26% | 3.74% |
| 10 to 30% | 899 | 7.03% | 5.18% | 4.30% |
| 30 to 60% | 663 | 9.02% | 4.50% | 4.49% |
| 60 to 100% | 406 | 11.81% | 4.59% | 4.43% |

## H4 context: nMAE by day-2 cloud cover, test

From the single test run (`reports/final_results_test.csv`, 2,457 hours on 187 days, Pacific dates 2026-04-10 to 2026-10-17, code version `c242a1c`).

| Day-2 cloud cover | Hours | Persistence D-2 | CAISO as published | HGB |
|---|---|---|---|---|
| 0 to 10% | 1,364 | 5.78% | 4.80% | 3.80% |
| 10 to 30% | 621 | 8.46% | 6.64% | 5.21% |
| 30 to 60% | 339 | 8.39% | 7.38% | 4.98% |
| 60 to 100% | 133 | 14.10% | 9.05% | 5.90% |

## Notes

- The test set (Pacific dates 2026-04-10 to 2026-10-17) has no winter, and spring and summer dominate it. The validation folds show HGB's lead over CAISO as published comes mostly from spring and curtailed hours (D30), so the test result may favor HGB more than a full year would.
- On the test hours the targets are recomputed from CAISO's own scores on those same hours.
- Plain reading of each test, for the deck: H1 "the model beats repeating the output from 2 days earlier by a clear margin"; H2 "the model's error is within a quarter of CAISO's own"; H3 "the tree model beats the straight-line model"; H4 "cloudy days are harder"; H5 "the worst over-forecasts are much smaller, so less backup is needed".
