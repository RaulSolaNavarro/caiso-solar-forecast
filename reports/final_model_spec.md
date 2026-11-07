# Final model specification

Frozen before the test run.

Written on 2026-11-07, before any test row was read by a model. The test run is `python -m src.modeling.final_test --final-test`, once (Brief 4, Task C). That script refuses to run if this file, `reports/hypotheses.md`, `src/modeling/` or `src/processing/` has uncommitted changes, if the settings chosen on the inner split differ from the frozen ones below, or if `reports/final_results_test.csv` already exists.

## Code version

Built on commit `0ba3b40` (branch `raul/modeling-validation`, the Brief 3 code). Frozen in the commit on branch `raul/final-test` that adds this file, `reports/hypotheses.md` and `src/modeling/final_test.py`. The test run prints the commit it ran on.

## Model

- Family: gradient-boosted regression trees, scikit-learn `HistGradientBoostingRegressor` (FAQ Decision D30).
- Target: capacity factor, `eia_mw / capacity_mw` (EIA hourly CISO solar with negatives set to 0, D15; EIA 860M monthly nameplate, all CISO, D18 and D19). The prediction is clipped to 0 to 1 and multiplied by `capacity_mw` to give MW.
- Training rows: every fit row on Pacific dates 2024-03-08 to 2026-04-09 (763 days, 9,187 hours): daylight (D20), EIA present, outside `wx_gap` (D17), `eia_deep_night_flag` False (D16).

## Features (D28, the 10 a.m. rule)

20 features, all known before 10:00 a.m. Pacific on the day before delivery:

1. Day-2 weather (capacity-weighted mean over the 39 weather points with a share above 0): `cloud_cover_previous_day2`, `shortwave_radiation_previous_day2`, `direct_radiation_previous_day2`, `diffuse_radiation_previous_day2`, `direct_normal_irradiance_previous_day2`, `temperature_2m_previous_day2`, `relative_humidity_2m_previous_day2`, `wind_speed_10m_previous_day2`, `precipitation_previous_day2`.
2. `csi_previous_day2`: day-2 GHI / clear-sky GHI, blank when clear-sky GHI is under 20 W/m2.
3. Calendar and sun: `hour` (Pacific hour of the hour start), `hour_sin`, `hour_cos`, `doy_sin`, `doy_cos`, `sun_elev`, `clearsky_ghi` (pvlib Ineichen at the capacity-weighted centre, mid-hour).
4. `capacity_mw`.
5. EIA: `cf_lag48` (EIA at hour ending t minus 48 h / `capacity_mw` of hour t) and `cf_d2_daily` (mean EIA capacity factor of Pacific day D-2).

`assert_no_leak` runs before every fit. Two timing assumptions are unverified and recorded in D28: day-2 weather issued before the bid close for every hour, and EIA's D-2 values published by then.

## Tuning

- Inner split: the last 10% of the 763 training and validation days, 76 days from 2026-01-24 to 2026-04-09 (858 fit rows), after a 1-day gap (2026-01-23). Inner fit: 2024-03-08 to 2026-01-22 (8,319 fit rows).
- Grid (in `src/modeling/models.py`): `max_depth` 3 or 5, `loss` squared error or absolute error; fixed `learning_rate` 0.05, `max_leaf_nodes` 15, `min_samples_leaf` 40, `l2_regularization` 1.0, up to 1,500 iterations. Each grid point is fitted on the inner fit days. The iteration count with the lowest inner-validation nMAE is kept (early stopping on the last 10% of days).
- Inner-validation nMAE: depth 3 squared 4.692% at 156 iterations, depth 3 absolute 4.504% at 182, depth 5 squared 4.479% at 91, depth 5 absolute 4.452% at 86.
- **Chosen: `max_depth` 5, `loss` absolute error, 86 iterations.** Refit with these on all 9,187 training rows.
- Random seed: 0 (`random_state=0`; the fit uses no random split).

## Comparison forecasts in the test run

Ridge (alpha 100, chosen on the same inner split; dropped in D30 but scored for H3), climatology (mean capacity factor by month and hour over the training rows), persistence D-2 and D-1, CAISO day-ahead as published and adjusted (D27). CAISO as published is the headline comparison; CAISO adjusted is partly circular (D27, Task A check).

## Test hours

Pacific dates 2026-04-10 to 2026-10-17, D27 common hours: daylight, EIA, CAISO day-ahead and both persistence values present, outside the 129-hour weather gap (D17), `curt_mwh` not null. Same metrics as validation (`src/modeling/score_models.py`), plus P95 undershoot.
