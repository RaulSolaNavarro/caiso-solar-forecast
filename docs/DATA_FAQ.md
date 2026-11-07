# Data FAQ

Questions and answers about the project's data: where it comes from, why we use it, what is wrong with it, and how to prepare it. Written for teammates who open the raw files in their own tools. Last reviewed: 2026-11-07.

This file grows. New questions go in the section where they belong (see "How to add a question" at the end). Column-by-column detail is in `docs/DATA_DICTIONARY.md`, code to load the files is in `docs/DATA_HOWTO.md`, and the pull-by-pull record of checks is in `data/raw/PULL_LOG.md`.

## How to read the evidence tags

Every claim carries a tag so you can tell a fact from an opinion.

| Tag | Meaning |
|---|---|
| **[Doc]** | Stated in the provider's own documentation (link given). |
| **[Checked]** | We tested it, in the data pull (`PULL_LOG.md`) or while writing this FAQ (dated). |
| **[Our call]** | A team or Raúl decision, or our recommendation. Open to change. |
| **[Unverified]** | We believe it but have not confirmed it. Do not quote it as fact. |

## Contents

| Section | Topic |
|---|---|
| 1 | Which datasets, from which sources |
| 2 | Why each dataset: what part of the analysis it serves |
| 3 | How we know these are the right sources, and what we passed over |
| 4 | Time frames and why |
| 5 | Data dictionary (summary; full version in `DATA_DICTIONARY.md`) |
| 6 | Issues, risks, limits and the decision log (D1 to D31) |
| 7 | Recommendations: nulls, encoding, data types, merging |

---

## 1. Which datasets, from which sources

### Q1.1 What did we pull, and where did each file come from?

Five sources, saved as eight data files plus 51 weather files in `data/raw/`. All were pulled on 2026-10-27 and 2026-10-28 with the scripts in `src/data_pull/`.

| # | Dataset | File in `data/raw/` | Provider and entry point |
|---|---|---|---|
| 1 | Actual hourly solar generation (the target) | `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv` | U.S. Energy Information Administration (EIA), Hourly Electric Grid Monitor, API v2, route `electricity/rto/fuel-type-data`, respondent `CISO`, fuel `SUN`. https://www.eia.gov/opendata/ |
| 2 | CAISO day-ahead solar forecast (the benchmark) | `caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz` | CAISO OASIS, report `SLD_REN_FCST`, market run `DAM`. https://oasis.caiso.com |
| 3 | CAISO actual solar (backup target and timing check) | `caiso_actual_solar_2024-01-01_2026-10-17.csv.gz` | CAISO OASIS, same report, market run `ACTUAL`. |
| 4 | Weather forecasts (model inputs), 51 locations | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_<location_id>_2024-03-08_2026-10-17.csv.gz` | Open-Meteo Previous Runs API, model `ecmwf_ifs025`. https://open-meteo.com/en/docs/previous-runs-api |
| 5 | Weather locations | `weather_locations.csv` | Built by us. California boundary from Natural Earth 1:10m v5.1.2 (`reference/california_boundary_ne10m.geojson`); capacity shares from dataset 6. |
| 6 | Installed solar capacity by month | `eia860m_solar_ciso_capacity_by_month.csv` | EIA Form 860M, monthly generator inventory, 2024-01 to 2026-09. https://www.eia.gov/electricity/data/eia860m/ |
| 7 | Curtailment, 5-minute workbooks, 2024 to 2025 | `caiso_curtailment_2024-01-01_2025-12-31.csv.gz` | CAISO Production and Curtailments Data workbooks. https://www.caiso.com/library/production-curtailments-data |
| 8 | Curtailment, hourly daily report, 2025-06-01 on | `caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz` | CAISO Daily Renewable Report, one HTML page per day. |

The file sizes, row counts and exact GitHub links are in `data/README.md`.

### Q1.2 What did we look at but not pull?

- **NSRDB (NLR, formerly NREL).** Listed in the Task 2 memo for clear-sky and observed irradiance. The pull brief covers five sources and does not include it. Clear-sky checks used the open-source `pvlib` library instead, which Task 2 names as the fallback. **[Doc]** (Task 2) **[Checked]** (`PULL_LOG.md`)
- **Kaggle plant-level solar dataset.** Listed in Task 2 as a code-testing backup only. It is not CAISO data and is not used.
- **CAISO Key Statistics and the monthly renewables reports.** Used only for reference numbers (installed capacity and peaks) in the capacity comparison. No file was built from them.

### Q1.3 Which licenses and credits apply?

Open-Meteo data is CC BY 4.0 and the free tier is for non-commercial use. Any report or deck that shows weather data must say "Weather data by Open-Meteo.com". **[Doc]** (Open-Meteo terms) EIA and CAISO data are public. Cite each source by name and the pull date in the final report (Task 2 access plan, step 6).

---

## 2. Why each dataset: what part of the analysis it serves

### Q2.1 What is each dataset for?

| Dataset | Role | Used for |
|---|---|---|
| EIA hourly solar | **Y**, the known outcome | The number we forecast and the number every model is scored against. Also the base for the persistence baseline (same hour yesterday). |
| OASIS DAM solar | **Benchmark** | Scored against Y, never used for training. The success target "nMAE at most 1.25 times CAISO's" needs it. |
| OASIS ACTUAL solar | **Backup target and timing check** | Used to find the offset in EIA timestamps (1 hour until 2025-12-02, none after; Decision D14). Falls back as the target if EIA turns out unusable (Task 2, "If something slips"). |
| Open-Meteo weather | **X**, the inputs | Forecasts of cloud, radiation, temperature, humidity, wind and rain as they stood one and two days before each hour. The main model uses day 2, which is published before the 10:00 a.m. Pacific bid close. Day 1 is a labeled comparison only (plan Task 6 sets the offset). |
| `weather_locations.csv` | Weather point list | Which 51 points we pulled, and each point's share of CISO solar capacity, so the list can be narrowed or weighted. |
| EIA 860M | **Scaling and placement** | Divides errors by installed capacity (the nMAE definition), shows how much capacity grew over the window, and gives plant coordinates that decided where weather points go. |
| Curtailment files | **Flags** | Mark hours when solar was turned down, so the output was lower than the sun allowed. Used to report results with and without those hours (Task 1, assumptions). |

### Q2.2 Why do we need capacity at all?

Installed solar grew a lot over the window: EIA 860M CISO solar nameplate went from 20,546.9 MW (2024-01) to 26,034.5 MW (2026-09), about 27%. **[Checked]** (`PULL_LOG.md`, source 4) A fixed MW error means less in a bigger fleet, so the success metric divides by capacity of the same month and the same scope as the target. Without it, later months would look better than earlier ones for reasons unrelated to the model.

### Q2.3 Why pull the curtailment files if we do not forecast curtailment?

EIA generation is measured after curtailment, so on a curtailed day it sits below what the sun could have produced. A model that learns from those hours learns a lower ceiling than the weather supports, and it is scored against a lower number than it was predicting. Flagging the hours lets us report results with and without them. **[Doc]** (Task 1)

---

## 3. How we know these are the right sources, and what we passed over

### Q3.1 How do we know each source measures what we think it does?

| Source | Evidence |
|---|---|
| EIA hourly | The API returns respondent name "California Independent System Operator" and fuel "Solar". **[Checked]** Hourly values track CAISO's own actual series very closely once aligned with Decision D14 (correlation 0.9981 to 0.9999 in January, March and July 2025, all before the 2025-12-02 break, mean absolute difference 200 to 272 MW; 0.9978 for 2024-03-08 to 2025-11-25 and 0.9977 for 2025-12-06 to 2026-10-17, checked 2026-11-07). **[Checked]** EIA describes the series as metered net generation reported by each balancing authority, and says rooftop solar is typically not included. **[Doc]** (https://www.eia.gov/electricity/930-content/about.html) |
| OASIS DAM and ACTUAL | OASIS is CAISO's public data portal. The report `SLD_REN_FCST` and the hubs NP15, SP15 and ZP26 are listed in the OASIS Interface Specification v5.1.2. **[Doc]** DAM solar is exactly zero at night, and ACTUAL follows EIA closely. **[Checked]** |
| Open-Meteo | `_previous_dayN` is documented as the value predicted N x 24 hours before the valid time. **[Doc]** Radiation is zero when the sun is more than 10 degrees below the horizon, and shortwave radiation matches clear-sky timing from `pvlib` (correlation 0.975 to 0.999). **[Checked]** Ranges are plausible (shortwave radiation up to 1,108 W/m2; temperature -21.0 to 50.8 degrees C). **[Checked]** |
| EIA 860M | EIA's official monthly generator inventory. We keep rows with Balancing Authority Code `CISO` and Energy Source Code `SUN`. All 33 months were found, with no duplicate generators and no blank coordinates or nameplate. **[Checked]** It does not agree with CAISO's own capacity and peak figures (see Q6.9). |
| Curtailment | CAISO's own publications. The 2024 to 2025 workbooks and the daily report pages agree hour by hour over 214 overlap days (solar correlation 0.998; 213 of 214 days within 1 MWh or 1% of the day's curtailment). **[Checked]** |

### Q3.2 Why EIA as the target and not CAISO's own actual series?

The README, Task 1 and Task 2 name EIA's hourly solar series as the target. What the documents show in its favor: a documented federal API, and history back to 2019-01-01 for this route. **[Doc]** (route metadata, `PULL_LOG.md`) Whether the team weighed it against OASIS ACTUAL beyond Task 2's fallback plan is not recorded. The OASIS ACTUAL series is kept as a backup. Its night values are slightly negative, as EIA's are, and it covers only three trading hubs.

### Q3.3 What alternatives did we consider, and why not?

| Need | Alternative | Why we did not use it |
|---|---|---|
| Target | EIA region `CAL` (wider California) | Task 2: it is a wider region than the CAISO balancing area. **[Doc]** |
| Target | EIA `local-hourly` route (Pacific time) | Same series in local time. We keep UTC so daylight saving days do not create 23 and 25 hour days. **[Our call]** |
| Target | OASIS ACTUAL | Kept as backup, see Q3.2. |
| Benchmark | Any other forecast | The business question compares against CAISO's own day-ahead forecast (Task 1). No other forecast is in the plan. **[Our call]** |
| Weather model | `best_match` | In California it returns HRRR for day 1 and GFS for day 2, which mixes models. **[Checked]** |
| Weather model | `ncep_hrrr_conus`, `gfs025` | HRRR has no day 2. `gfs025` returned no previous-runs data in the probe. **[Checked]** |
| Weather model | Observed weather | The first plan used observed weather as a stand-in. A forecast archive lets the model see what a forecaster would have seen. **[Doc]** (Task 1) |
| Irradiance | NSRDB | See Q1.2. |
| Capacity | CAISO Key Statistics | One number per month in a PDF, no plant list, no coordinates. Used as a cross-check only. **[Our call]** |
| Capacity | Annual EIA-860 | Final, but yearly. We need monthly growth and coordinates. EIA calls 860M figures preliminary. **[Doc]** (https://www.eia.gov/electricity/data/eia860m/) |
| Curtailment 2025-06 on | CAISO's daily Wind and Solar Curtailment PDF | Exists for 2025-05-26 but returned 404 for the 2026 dates tried. **[Checked]** |

### Q3.4 What do we still not know about source quality?

- Which of EIA, OASIS ACTUAL, or CAISO's own published peaks is "right" for solar output. They differ by thousands of MW in August 2026 (Q6.9).
- Why EIA's timestamps ran 1 hour late against the sun until 2025-12-02 and match hour ending after it, and the exact hour of the change (Q6.1, Decision D14).
- What the `AVA_` hub in the day-ahead file represents (Q6.6).

---

## 4. Time frames and why

### Q4.1 What dates does each file cover?

| Dataset | First | Last | Notes |
|---|---|---|---|
| EIA hourly | 2024-01-01 00:00 UTC | 2026-10-17 23:00 UTC | 24 hours missing (2024-11-02 Pacific day). |
| OASIS DAM and ACTUAL | 2023-12-31 08:00 UTC | 2026-10-18 06:00 UTC | Whole Pacific operating days 2023-12-31 to 2026-10-17, so a few rows fall outside the UTC range. |
| Open-Meteo | 2024-03-08 00:00 UTC | 2026-10-17 23:00 UTC | 22,896 hours (954 days) per file. |
| EIA 860M | 2024-01 | 2026-09 | 2026-10 not published when pulled (next release 2026-11-24 per EIA). |
| Curtailment workbooks | 2024-01-01 | 2025-12-31 | Pacific dates. |
| Curtailment daily report | 2025-06-01 | 2026-10-17 | Pacific operating dates. |

### Q4.2 Why does the modeling window start on 2024-03-08?

Weather is the limit. The Open-Meteo previous-runs archive for `ecmwf_ifs025` starts in early 2024, and the last variable to start is day-2 radiation at 2024-03-07 17:00 UTC. 2024-03-08 is the first full UTC day on which all nine variables have data for both offsets. **[Checked]** (`PULL_LOG.md`, source 3) Open-Meteo says most models are archived from January 2024. **[Doc]** The weather files and every model start on 2024-03-08, so models and the two reference forecasts are scored on the same days.

### Q4.3 Why do the EIA and CAISO files start earlier, on 2024-01-01?

Task 1 set January 2024 as the start date, and the extra months are useful outside the model window: the persistence baseline needs the day before the first modeled day, and the timing test used January 2025 (inside the window) but benefits from more months to choose from. **[Our call]** Apply the modeling window in processing. The raw files are not trimmed.

### Q4.4 Why end on 2026-10-17?

The end date was set by when we pulled the data (2026-10-27 and 2026-10-28), and the pull brief fixed 2026-10-17 as the last full day used. From there we looked back as far as the sources allowed; the most constrained source, the weather forecast archive, starts on 2024-03-08 (Q4.2). **[Our call]** (Raúl, 2026-11-07) We keep it: moving it would move the locked test set and every file and score before the Nov 16 deadline. EIA can revise its newest values (Q6.5), so the last days may shift slightly in a later pull. See Decision D25.

### Q4.5 Why is the test set the latest 191 days?

The plan holds out the latest 20% of days. 20% of 954 days is 190.8, rounded to 191, which starts on 2026-04-10 and ends on 2026-10-17. The earlier 763 days are used for training and four rolling validation folds of about three months each, with at least a one-day gap. **[Our call]** (README, Task 1)

The fold dates are fixed in Decision D29, which replaces the dates in D24: validation blocks 2025-03-29 to 2025-06-27, 2025-06-28 to 2025-09-26, 2025-09-27 to 2025-12-26 (91 days each) and 2025-12-27 to 2026-04-09 (104 days), so the whole latest winter sits in one fold. Training for each block uses all days from 2024-03-08 and stops 1 whole day before the block starts. **[Our call]** The table is in `reports/folds.csv`.

Two consequences: the test period has **no winter**, and it contains the 129-hour weather gap in April 2026 (Q6.12). Winter accuracy is judged only in validation.

### Q4.6 Why not go further back than 2024?

EIA hourly data for this route goes back to 2019-01-01, **[Doc]** (route metadata), but the weather forecast archive does not, and a model needs both. Pre-2024 data would also need older capacity files. A one-off comparison with July 2019 capacity is in `PULL_LOG.md` and is not in any data file.

### Q4.7 How much history is that, season by season?

Months March to October appear three times in the window, November and December twice, January and February twice. Seasonal patterns are therefore learned from two or three examples each. **[Checked]** (README)

---

## 5. Data dictionary

### Q5.1 Where is the full dictionary?

In `docs/DATA_DICTIONARY.md`. It gives, for every file, the grain (what one row is), key, row count, size, period, time zone, units, and every column with its type, meaning, range or allowed values, null count, and where the description comes from.

### Q5.2 What is the grain of each file, in one view?

| File | One row is | Rows | Size on disk | Key |
|---|---|---|---|---|
| EIA hourly | one hour | 24,480 | 2.12 MB | `period` |
| OASIS DAM | one hub, one fuel type, one hour | 146,706 | 1.30 MB (gzip) | `INTERVALSTARTTIME_GMT` + `TRADING_HUB` + `RENEWABLE_TYPE` |
| OASIS ACTUAL | same | 146,210 | 1.72 MB (gzip) | same |
| Open-Meteo (each of 51 files) | one hour at one location | 22,896 | 0.56 to 0.59 MB (gzip) | `time_utc` (one location per file) |
| Weather locations | one weather point | 51 | 1.6 KB | `location_id` |
| EIA 860M | one generator in one monthly file | 32,503 | 9.77 MB | `file_month` + `Plant ID` + `Generator ID` |
| Curtailment workbooks | one 5-minute interval with curtailment | 111,289 | 1.56 MB (gzip) | `Date` (calendar part) + `Hour` + `Interval` + `Reason` (checked unique, 2026-10-29) |
| Curtailment daily report | one fuel, one hour, one day | 24,144 | 0.29 MB (gzip) | `operating_date` + `hour` + `fuel` |

The weather files together are 29.3 MB gzip (164.9 MB uncompressed). **[Checked]** (`PULL_LOG.md`)

---

## 6. Issues, risks, limits and the decision log

Each entry says what we found, what we did, and where it stands. Counts come from `PULL_LOG.md` unless a date says otherwise. Nothing in a raw file was dropped, filled, shifted or converted. The decisions are collected in the "Decision log" at the end of this section (D1 to D31).

### Target: EIA hourly solar

**Q6.1 Are EIA's timestamps wrong?** *Decided: Decision D14.* EIA's page says hourly values use an hour-ending convention. **[Doc]** The data agree only from 2025-12-02 on. Before that, EIA label L holds the hour CAISO reports as ending at L minus 1 hour, in winter, summer and on both sides of the March clock change; the same shift in PST and PDT rules out a daylight saving error. From about 22:00 UTC on 2025-12-02, label L is the hour ending at L, as documented. CAISO OASIS and Open-Meteo times line up with the sun throughout. **[Checked]** (2026-11-07, `src/checks/eia_timing_check.py`) We found no EIA note about either the offset or the change. The earlier "L minus 1 hour for everything" rule came from sample months in 2025, all before the change, and is replaced. Rule: for a label before 2025-12-02 22:00 UTC the hour ending is L minus 1 hour; from that label on it is L. The hour ending 2025-12-02 21:00 UTC then has no EIA value and stays missing. Apply it in processing only. **[Our call]** Still open: why EIA changed, and the exact hour of the change.

**Q6.2 Are there missing hours?** Yes, 24 (0.10%): the whole Pacific day 2024-11-02 (2024-11-02 08:00 to 2024-11-03 07:00 UTC). A second request returned the same gap, so EIA does not have them. Not filled.

**Q6.3 Why are some values negative?** 9,461 of 24,480 rows (38.6%) are negative, all at night or near it, from -74 up to zero. The size grows over time. A likely cause is station use at the plants netted out of generation, **[Unverified]** and EIA says it publishes balancing authority data as reported without imputation. **[Doc]** Kept in the raw file. In processing they are set to 0 in the modeling copy, with the original kept in its own column (Decision D15).

**Q6.4 Why are some deep-night values positive?** 255 hours on 60 dates show more than 100 MW, up to 413 MW, when the sun is more than 12 degrees below the horizon at Westlands. They fall mostly in February to July 2024 (114 in May 2024) and stay roughly flat through the night, so they do not look like solar output. Cause unknown. "Deep night" was defined with the labels as given. Rechecked after the timing rule (Decision D14) on 2026-11-07: they remain, 351 hours on 65 UTC dates inside the modeling window with the sun below -12 degrees at the middle of the hour at the capacity-weighted centre, still mostly March to July 2024 (167 in May 2024). An earlier count of 373 included 22 hours before the window. **[Checked]** They are flagged and dropped from training (Decision D16).

**Q6.5 Can EIA values change after we pulled them?** Yes. EIA says values can be revised after metering or telemetry issues. **[Doc]** The file is a 2026-10-27 snapshot. A later re-pull may differ, especially for the most recent days.

### Benchmark and backup: CAISO OASIS

**Q6.6 What is the `AVA_` hub?** Unknown. It appears in the day-ahead file only, from 2026-09-10 07:00 UTC (912 rows, mean 5.2 MW, max 18.3 MW). The three-hub day-ahead total does not drop against ACTUAL after that date, so there is no sign that capacity moved into it. Kept in raw. Leave it out of the CAISO total until we know what it is (Decision D21). The OASIS spec v5.1.2 lists only NP15, SP15, ZP26 and ALL. **[Doc]**

**Q6.7 Which days are missing?** DAM has no data for three whole Pacific days, the day before each spring clock change: 2024-03-09, 2025-03-08 and 2026-03-07 (72 hours per hub, 0.29%). OASIS answers "no data" for them. ACTUAL misses 2 hours per solar hub (2024-02-27 19:00 UTC and 2024-08-31 18:00 UTC). Wind at ZP26 starts on 2024-02-08. Not filled.

**Q6.8 What else should I know about these two files?**

- **Extra rows.** Whole Pacific days are kept, so 80 rows (both files) fall before 2024-01-01 00:00 UTC and 49 (DAM) or 42 (ACTUAL) fall after 2026-10-17 23:00 UTC. Filter by the UTC range.
- **`GROUP` is not a key.** OASIS assigns it to blocks of rows in each response, so it changes with the request while every other column stays the same.
- **`OPR_HR` follows the local clock.** Checked 2026-10-29 against the UTC columns: it equals elapsed hours since Pacific midnight on all normal days, but on the five clock-change days in the data (2024-03-10, 2024-11-03, 2025-03-09, 2025-11-02, 2026-03-08) it counts clock hours, so 109 of 24,455 hour labels differ from the elapsed-hour reading. Always join on `INTERVALSTARTTIME_GMT` or `INTERVALENDTIME_GMT`, never rebuild time from `OPR_DT` and `OPR_HR`.
- **ACTUAL has negative night values**: 7,959 (NP15), 10,671 (SP15) and 9,901 (ZP26) hourly values. DAM solar has none.
- **DAM runs above ACTUAL in daylight.** In the two windows tested for the `AVA_` question, three-hub DAM minus ACTUAL averaged +929.5 MW (4 weeks before 2026-09-10) and +1,227.0 MW (after), and the same dates in 2025 gave +1,051.7 and +1,374.0 MW. This is not a full-period study. Keep it in mind when reading benchmark errors.

**Q6.9 Why do the capacity and peak figures disagree?** The cause is unresolved. For scoring, the team uses EIA 860M monthly nameplate, all CISO (EIA's code for the CAISO balancing area), as the divisor, with a California-only score reported once as a check (Decisions D18 and D19). That is a choice of divisor, not a finding that this figure is "right". For August 2026: EIA 860M CISO solar nameplate 25,812.8 MW (all CISO, including Arizona and Nevada), 23,134.4 MW (California only); CAISO installed solar 23,920 MW as of 2026-08-05; CAISO peaks 23,367 MW (2026-08-03) and 23,896 MW (August report); EIA hourly peak 20,852 MW; OASIS ACTUAL three-hub peak 19,616 MW. Possible reasons, none checked: CAISO counts only fully commercial units, CAISO peaks use shorter intervals than the hourly series, the CAISO peak includes output outside the three hubs or outside EIA's CISO series, and nameplate is not what a plant delivers at the grid connection. Rule: name the source and scope next to every capacity or peak figure. The full table is in `PULL_LOG.md`, source 4.

### Inputs: Open-Meteo

**Q6.10 What is a "previous day" value?** The forecast made about 24 hours (day 1) or 48 hours (day 2) before the hour it describes. **[Doc]** Use day 2 for the main model because it is available before the 10:00 a.m. Pacific bid close; a forecast issued later would make results look better than they could be in practice. Day 1 is a labeled comparison.

**Q6.11 What did the weather pull skip?** Nine variables came back with data for both offsets. These came back empty (all null) and were not saved: `cloud_cover_low`, `cloud_cover_mid`, `cloud_cover_high`, `visibility`, `snow_depth`, `aerosol_optical_depth`, `dust`. **[Checked]** Aerosol and smoke signals are therefore not available from this source.

**Q6.12 Is anything missing in the weather files?** Yes. 129 hours (2026-04-17 15:00 to 2026-04-22 23:00 UTC) are null in two columns, `cloud_cover_previous_day2` and `relative_humidity_2m_previous_day1`, in all 51 files. The other offset of each variable has values. A repeat request returned the same nulls, so the gap is in Open-Meteo's archive. Not filled. It falls inside the test period. The gap is 0.56% of the 22,896 hours. These hours are dropped for every model and the benchmark, with a `wx_gap` flag column (Decision D17).

**Q6.13 How well do 51 points cover the plants?** 95.8% of CISO solar nameplate is within 50 km of a point (2026-09, all CISO) and 97.0% for California only. The 41 grid points alone reached only 54.4% within 50 km, so Raúl approved 10 cluster points on 2026-10-28. Largest plants still more than 50 km away are ATLAS Solar V and VI (Arizona, 300 MW, 68 km), Pastoria Solar (Kern, 105 MW, 61 km) and Sunshine Valley Solar (Nevada, 104 MW, 90 km). Five San Diego plants (12.8 MW in 2026-09) are more than 100 km from any point; no 11th point was added. 12 of the 41 grid points have a capacity share of zero.

**Q6.14 Is a point the same as a model grid cell?** No. The API returns the nearest cell of the ECMWF 0.25 degree model. Each of our 51 points maps to its own cell. The largest distance from a requested grid point to its cell is 22.0 km (April 2024 test) and cluster points are 3.5 to 15.0 km from theirs. **[Checked]**

**Q6.15 Could the model change underneath the archive?** Weather centers update their models from time to time, which could shift the character of a "previous day" series across the window. We did not check for this. **[Unverified]**

**Q6.16 What are the rate limits?** Free tier: 600 calls a minute, 5,000 an hour, 10,000 a day, non-commercial. **[Doc]** The full pull cost 6,255.5 weighted calls; with tests, 6,455.1 on 2026-10-28. Re-running every location in one day is possible but leaves little room.

### Capacity: EIA 860M

**Q6.17 What are the limits of the capacity file?**

- Preliminary figures, corrected in later monthly files without notice. **[Doc]**
- Plants under 1 MW of combined nameplate are excluded. **[Doc]** (EIA page and file notes) That "may represent a significant portion of capacity for solar photovoltaic generation" (file note).
- Includes Arizona and Nevada plants that sit in the CISO balancing area: 1,946.9 MW in 2024-01, 2,778.4 MW in 2026-09. It is not verified that the EIA hourly CISO series covers them too.
- Includes out-of-service generators (status OS or OA). Both PV and solar thermal are kept; use the `Technology` column to separate them.
- Columns change: from the 2025-10 file there are four more (37 columns instead of 33), blank for earlier months.
- 111 small California generators (56.7 MW) leave the list in 2024-07 and do not return.
- Monthly totals are not always increasing (for example 2025-02 to 2025-03).
- No 2026-10 file yet.
- Blank cells in the file hold a single space, not an empty string (Q7.2).

### Curtailment

**Q6.18 What are the limits of the curtailment files?**

- CAISO defines curtailment as the difference between actual production and its forecast when actual production is less than the forecast, and filters amounts under 1 MW. **[Doc]** (daily curtailment PDF, 2025-05-26) So a curtailment series may include forecast error. This is our reading of the definition.
- Workbooks list only intervals with curtailment, in 5-minute MW. The raw data is "not considered operational or settlement quality data." **[Doc]** (workbook `Read_me`)
- CAISO stopped publishing the production report on 2025-06-01. **[Doc]** (CAISO page) From then on the daily report pages are the only source we found.
- Missing: the workbook has no rows for 2025-06-16 (the daily report shows 5,396.9 MWh of solar curtailment that day, so it is missing data, not a quiet day); the daily report page for 2025-11-05 does not exist.
- `Hour` is read as Pacific hour ending (1 to 24). CAISO documentation for this was not found; the reading is inferred from the data (solar curtailment sits in hours 7 to 19). **[Unverified]**
- The workbook `Date` carries an inconsistent time of day (07:00, 08:00 or 00:00) by month. Use the calendar part only.
- The daily report always has 24 values, including the 23 and 25 hour days (2025-11-02, 2026-03-08). How CAISO maps them is unknown. On 2025-11-02, the one clock-change day both files cover, the workbook and the report agree position by position with no shift (1,644.2 and 1,644.4 MWh; total absolute difference 0.2 MWh; curtailment only in positions 7 to 17). **[Checked]** (2026-11-07) That shows the 2 files use the same positions, not how the positions map to clock hours, because no curtailment fell near the repeated hour. The 5 clock-change days are flagged and left out of the hourly curtailment flags (Decision D22).

### Operations

**Q6.19 Why did Python fail to read some files from GitHub?** Some reads of the daily-report file failed with `WinError 10054` (connection reset) during the secure handshake. The fourth try worked, and the Windows web client downloaded the same file without error. Cause not determined; Norton's HTTPS scanning on the pull machine is one possibility (since removed). Wrap URL reads in a retry, or use a local copy. See `DATA_HOWTO.md`.

**Q6.20 Is any API key in the repo?** No. Keys live in `.env`, which is not committed, and every log line passes through `redact()`. Only whoever re-runs the pulls needs the EIA key.

### Decision log

D1 to D13 were made while pulling the data (2026-10-27 and 2026-10-28) and are written only from what `PULL_LOG.md`, `docs/DATA_PULL_BRIEF.md`, Q3.3 and `src/data_pull/` record. Where those files do not record the options or their pros and cons, the entry says so. D14 to D25 are processing decisions the team agreed on 2026-11-07 (Raúl). D26 and D27 were written down with the processing scripts in `src/processing/` on the same day (Raúl). D28 to D30 were made with the modeling code in `src/modeling/` on 2026-11-07 (Raúl), on training and validation days only. D31 records the frozen model and the one test run (2026-11-07). Every entry has the same 5 headings.

| ID | Decision | Date | Link |
|---|---|---|---|
| D1 | OASIS, weather and curtailment files end in `.csv.gz`, not `.csv` | 2026-10-27 and 2026-10-28 | [D1](#d1-compressed-file-names) |
| D2 | 860M file saved as plain `.csv` | 2026-10-28 | [D2](#d2-860m-file-format) |
| D3 | Curtailment in 2 files (workbooks and daily report) | 2026-10-28 | [D3](#d3-two-curtailment-files) |
| D4 | OASIS requests by Pacific operating day; keep every returned row | 2026-10-27 | [D4](#d4-oasis-request-windows) |
| D5 | ACTUAL re-pulled with half-month windows starting 1 operating day early | 2026-10-28 | [D5](#d5-actual-re-pull) |
| D6 | Weather model `ecmwf_ifs025` for both offsets and all dates | 2026-10-28 | [D6](#d6-weather-model) |
| D7 | Weather window 2024-03-08 to 2026-10-17 | 2026-10-28 | [D7](#d7-weather-window) |
| D8 | 51 weather points: 41 grid + 10 cluster ("option B") | 2026-10-28 | [D8](#d8-weather-points) |
| D9 | Static capacity share per weather point, from the 2026-09 860M file | 2026-10-28 | [D9](#d9-static-capacity-share) |
| D10 | `AVA_` rows kept in the raw file | 2026-10-28 | [D10](#d10-ava_-kept-in-raw) |
| D11 | EIA timing: recommended rule only, no raw file shifted (superseded by D14) | 2026-10-28 | [D11](#d11-eia-timing-at-pull-time) |
| D12 | No missing data filled in any raw file | throughout | [D12](#d12-no-filling-in-raw-files) |
| D13 | No extra weather point for San Diego plants beyond 100 km | 2026-10-28 | [D13](#d13-san-diego-plants-beyond-100-km) |
| D14 | EIA timestamp alignment: shift labels back 1 hour only before 2025-12-02 22:00 UTC | 2026-11-07 | [D14](#d14-eia-timestamp-alignment) |
| D15 | Negative EIA night values set to 0 in the modeling copy | 2026-11-07 | [D15](#d15-negative-night-values-in-eia) |
| D16 | Positive deep-night EIA values flagged, then dropped from training | 2026-11-07 | [D16](#d16-positive-deep-night-values-in-eia) |
| D17 | 129-hour weather gap dropped for every model and the benchmark | 2026-11-07 | [D17](#d17-the-129-hour-weather-gap) |
| D18 | Capacity scope: all CISO | 2026-11-07 | [D18](#d18-capacity-scope) |
| D19 | Capacity divisor: EIA 860M monthly nameplate | 2026-11-07 | [D19](#d19-capacity-and-peak-figures-disagree) |
| D20 | Daylight: sun above the horizon at mid-hour, capacity-weighted centre | 2026-11-07 | [D20](#d20-definition-of-daylight) |
| D21 | `AVA_` left out of the CAISO total | 2026-11-07 | [D21](#d21-the-ava_-hub-in-the-caiso-day-ahead-file) |
| D22 | 5 clock-change days left out of the hourly curtailment flags | 2026-11-07 | [D22](#d22-23-hour-and-25-hour-clock-change-days) |
| D23 | One processed hourly table on a full UTC calendar | 2026-11-07 | [D23](#d23-one-processed-hourly-table) |
| D24 | Validation folds: the last 4 blocks of 91 days before the test set (dates replaced by D29) | 2026-11-07 | [D24](#d24-validation-fold-dates) |
| D25 | Window end date stays 2026-10-17 | 2026-11-07 | [D25](#d25-the-window-end-date) |
| D26 | Curtailment: workbook to 2025-12-31 (except 2025-06-16), daily report for the rest | 2026-11-07 | [D26](#d26-which-curtailment-file-for-which-dates) |
| D27 | Scoring: normalized MAE, 4 reference forecasts, one common set of hours | 2026-11-07 | [D27](#d27-scoring-definitions) |
| D28 | Model features and the 10 a.m. rule: day-2 weather, EIA lags of 48 h or more | 2026-11-07 | [D28](#d28-model-features-and-the-10-am-rule) |
| D29 | Validation folds: 4 blocks, the last one Dec 27 to Apr 9 so winter is one fold | 2026-11-07 | [D29](#d29-validation-folds) |
| D30 | Model families: gradient-boosted trees carried forward, ridge dropped | 2026-11-07 | [D30](#d30-model-families-kept-and-dropped) |
| D31 | Frozen model and the one test run | 2026-11-07 | [D31](#d31-frozen-model-and-the-one-test-run) |

#### D1 Compressed file names

**What issue did we identify?**
The pull brief named every output file `.csv`. Uncompressed, the OASIS files would be 20.7 MB (DAM) and 23.0 MB (ACTUAL), and the 51 weather files 164.9 MB. **[Checked]** (`PULL_LOG.md`, sources 2 and 3)

**How did we identify it?**
File sizes measured during the pull. The brief itself asked for gzip CSV for the weather files, because about 50 uncompressed files "would add well over 100 MB to Git". **[Doc]** (`DATA_PULL_BRIEF.md`, source 3)

**Why is it an issue?**
The raw files are committed so teammates can use them, and the brief's stop rule is any file above 50 MB or more than 100 MB of new files in total. **[Doc]** (`DATA_PULL_BRIEF.md`, "Stop and ask")

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
OASIS, weather and curtailment files are gzip-compressed CSV ending in `.csv.gz` (Raúl, 2026-10-27 for OASIS, 2026-10-28 for curtailment). pandas and R read them directly. Compressed sizes: 1.30 MB (DAM), 1.72 MB (ACTUAL), 29.3 MB (51 weather files). **[Checked]** (`PULL_LOG.md`)

#### D2 860M file format

**What issue did we identify?**
Choosing the format of the EIA 860M capacity file, 9.8 MB as plain CSV. **[Checked]** (`PULL_LOG.md`, source 4)

**How did we identify it?**
Not recorded at the time.

**Why is it an issue?**
Not recorded at the time.

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
Plain `.csv` (Raúl, 2026-10-28). **[Doc]** (`PULL_LOG.md`, source 4)

#### D3 Two curtailment files

**What issue did we identify?**
CAISO stopped publishing the production and curtailments report on 2025-06-01. **[Doc]** (CAISO page) The replacement, the Daily Renewable Report pages, gives hourly MWh in 6 categories (Economic, Self Schedule Cut, Operator Instruction; each Local or System). The workbooks give 5-minute MW with a `Reason` of Local or System. **[Checked]** (`PULL_LOG.md`, source 5)

**How did we identify it?**
Reading the CAISO production and curtailments page and both sources during the pull (2026-10-28).

**Why is it an issue?**
The two sources differ in grain and categories, and the raw files must keep values as published, with no conversion (`DATA_PULL_BRIEF.md`, "Fixed settings").

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
Two files, `caiso_curtailment_2024-01-01_2025-12-31.csv.gz` (workbooks) and `caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz` (daily report) (Raúl, 2026-10-28). They agree hour by hour over the 214 overlap days (solar correlation 0.998). **[Checked]** (`PULL_LOG.md`, source 5)

#### D4 OASIS request windows

**What issue did we identify?**
OASIS limits a request to 31 days and counts the limit in Pacific operating days. A window from UTC midnight to UTC midnight touched 32 operating days and failed with error 1004. **[Checked]** (`PULL_LOG.md`, source 2)

**How did we identify it?**
The error during the January 2024 test pull (2026-10-27).

**Why is it an issue?**
Requests failed, and every UTC hour from 2024-01-01 00:00 to 2026-10-17 23:00 had to be covered.

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
Each request runs from Pacific midnight to Pacific midnight, starting with operating day 2023-12-31, and every row OASIS returned is kept (Raúl's decision): 80 rows (both files) before 2024-01-01 00:00 UTC and 49 (DAM) or 42 (ACTUAL) after 2026-10-17 23:00 UTC. Apply the UTC range in processing. **[Checked]** (`PULL_LOG.md`, source 2)

#### D5 ACTUAL re-pull

**What issue did we identify?**
The first ACTUAL pull, in monthly windows, missed 13 hours per solar hub, and 11 of them were caused by the request windows: when an ACTUAL request starts at Pacific midnight in winter (08:00 UTC), OASIS leaves out that first hour. **[Checked]** (`PULL_LOG.md`, source 2)

**How did we identify it?**
A test: operating days 2025-02-28 to 2025-03-01 returned 2025-03-01 08:00 UTC, while operating day 2025-03-01 alone did not.

**Why is it an issue?**
ACTUAL is the backup target and the timing check for EIA, so hours lost to the request method would leave false gaps.

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
ACTUAL was re-pulled with half-month windows that start 1 operating day early; the extra day is dropped when the file is built (Raúl, 2026-10-28). Result: 69 rows added, 0 removed, every shared row identical except `GROUP`; 2 real gaps per solar hub remain. DAM was not re-pulled, as it has no such gaps. **[Checked]** (`PULL_LOG.md`, source 2)

#### D6 Weather model

**What issue did we identify?**
The brief asks for one weather model for the whole period and both offsets: `ecmwf_ifs025` if its previous-runs history starts on or before 2024-01-01, otherwise `best_match`. **[Doc]** (`DATA_PULL_BRIEF.md`, source 3) No model has previous-runs data for 2024-01-01. **[Checked]** (`PULL_LOG.md`, source 3)

**How did we identify it?**
Probes at point g24 (36.5, -119.5) for 4 models, and a comparison of `best_match` with the single models. **[Checked]** (`PULL_LOG.md`, source 3)

**Why is it an issue?**
Mixing models across dates or offsets would change what a weather column means partway through the data.

**What are our options?**
The probes and Q3.3 record what each model offered. Pros and cons beyond these facts were not recorded at the time.
- Option A `ecmwf_ifs025`. Pros: one model with both day 1 and day 2. Cons: radiation starts only on 2024-03-06 (day 1) and 2024-03-07 (day 2).
- Option B `best_match`. Pros: data from 2024-01-19. Cons: in California it gives HRRR for day 1 and GFS for day 2, which mixes models.
- Option C `ncep_hrrr_conus`. Pros: day 1 from 2024-01-19. Cons: no day 2.
- Option D `gfs025`. Pros: not recorded. Cons: returned no previous-runs data in the probe.

**Which course of action will we use?**
Option A, `ecmwf_ifs025` for both offsets and all dates (Raúl, 2026-10-28). The model name is in every weather file name and in a `model` column.

#### D7 Weather window

**What issue did we identify?**
Each weather variable starts on a different date in the `ecmwf_ifs025` previous-runs archive. The last to start is day-2 radiation, at 2024-03-07 17:00 UTC. **[Checked]** (`PULL_LOG.md`, source 3)

**How did we identify it?**
First valid hour per variable, checked at g01 and g41 on 2026-10-28.

**Why is it an issue?**
A model can only train and be scored on hours where all its inputs exist. Starting earlier would mean blank columns for the first weeks.

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
2024-03-08 to 2026-10-17, the first full UTC day on which all 9 variables have data for both offsets (Raúl, 2026-10-28). This sets the modeling window (954 days) and the test set start (2026-04-10). See Q4.2 and Decision D25 for the end date.

#### D8 Weather points

**What issue did we identify?**
The 41 grid points alone put only 54.4% of CISO solar nameplate within 50 km of a point (2026-09, all CISO), against the brief's 95% goal. **[Checked]** (`PULL_LOG.md`, source 4)

**How did we identify it?**
The coverage check the brief requires: distance from each 860M solar plant to its nearest weather point.

**Why is it an issue?**
Weather far from the plants describes the wrong sky. The brief says to add points near uncovered plants if less than 95% of capacity is within 50 km. **[Doc]** (`DATA_PULL_BRIEF.md`, source 3)

**What are our options?**
These are the options recorded in `PULL_LOG.md`. Further pros and cons were not recorded at the time.
- Option A: 6 cluster points at the centres of the 6 largest clusters, as in the brief. Pros: within the brief's "up to 6". Cons: reached only 84.0% to 87.8% within 50 km.
- Option B: 10 cluster points, each placed where it brought the most uncovered nameplate within 50 km. Pros: reaches 95.8% (2026-09, all CISO). Cons: more points than the brief's 6.

**Which course of action will we use?**
Option B, 41 grid + 10 cluster points (Raúl, 2026-10-28). See Q6.13.

#### D9 Static capacity share

**What issue did we identify?**
Each weather point needs a share of CISO solar capacity so the list can be narrowed or weighted. The brief asks for it. **[Doc]** (`DATA_PULL_BRIEF.md`, source 3)

**How did we identify it?**
Building `weather_locations.csv` after the 860M pull (2026-10-28).

**Why is it an issue?**
Capacity grew about 27% over the window (Q2.2), so a share fixed at one month fits earlier months only roughly.

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
Static shares from the 2026-09 860M file, all CISO, PV and solar thermal, any status. Each point's share is the nameplate whose nearest weather point it is. **[Checked]** (`PULL_LOG.md`, source 4) Q7.5 notes that the shares apply to 2024 only roughly.

#### D10 AVA_ kept in raw

**What issue did we identify?**
A 4th hub label, `AVA_`, appears in the day-ahead file only, from 2026-09-10 07:00 UTC (912 rows). **[Checked]** (`PULL_LOG.md`, source 2)

**How did we identify it?**
The per-hub row counts in the pull checks, then the `AVA_` check (2026-10-28).

**Why is it an issue?**
Its meaning is unknown, and the raw files must keep every returned row (`DATA_PULL_BRIEF.md`, "Fixed settings").

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
Kept in the raw file (Raúl, 2026-10-28). How to treat it in processing is Decision D21.

#### D11 EIA timing at pull time

**What issue did we identify?**
EIA's labels looked about 1 hour later than hour ending against the sun and against CAISO ACTUAL. **[Checked]** (`PULL_LOG.md`, sources 1 and 2)

**How did we identify it?**
Correlation with `pvlib` clear-sky radiation (January and July 2024), then cross-correlation with CAISO ACTUAL in January, March and July 2025. **[Checked]** (`PULL_LOG.md`, source 2)

**Why is it an issue?**
A target on the wrong hour misaligns it with the weather inputs.

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
At the time: a recommended rule, EIA label L is the hour ending at L minus 1 hour, applied in processing only, and no raw file shifted (Raúl, 2026-10-28). **Superseded by Decision D14**, because the offset ends on 2025-12-02, after the months tested.

#### D12 No filling in raw files

**What issue did we identify?**
Every source has gaps: EIA (24 hours), DAM (3 days), ACTUAL (2 hours per hub), weather (129 hours in 2 columns), curtailment (2025-06-16 in the workbook, 2025-11-05 in the daily report). **[Checked]** (`PULL_LOG.md`)

**How did we identify it?**
The row-count and null checks in every pull.

**Why is it an issue?**
The brief forbids cleaning raw files (no drop, fill, rename, unit change or outlier fix). **[Doc]** (`DATA_PULL_BRIEF.md`, "Fixed settings") Filled values would look like data.

**What are our options?**
Not recorded at the time.

**Which course of action will we use?**
Nothing is filled in any raw file. Gaps are handled in processing (Q7.1, Decisions D17 and D23).

#### D13 San Diego plants beyond 100 km

**What issue did we identify?**
5 San Diego plants, 12.8 MW in 2026-09 (about 0.05% of CISO solar nameplate), are more than 100 km from any weather point. **[Checked]** (`PULL_LOG.md`, source 4)

**How did we identify it?**
The coverage check; the brief asks to list every plant farther than 100 km. **[Doc]** (`DATA_PULL_BRIEF.md`, source 3)

**Why is it an issue?**
Their weather is described by a point more than 100 km away.

**What are our options?**
The log records that an 11th point was considered and not added. Pros and cons were not recorded at the time.
- Option A: add an 11th weather point.
- Option B: no extra point.

**Which course of action will we use?**
Option B, no extra point (Raúl, 2026-10-28). Coverage stays at 95.8% within 50 km (2026-09, all CISO).

#### D14 EIA timestamp alignment

This replaces the earlier "L minus 1 hour for everything" rule (D11).

**What issue did we identify?**
EIA's hourly solar labels do not match the sun for most of the history, and the offset changes on 2025-12-02.

**How did we identify it?**
We compared EIA with CAISO actual solar (NP15 + SP15 + ZP26, whose times match the sun) day by day, and with astronomical solar noon. Script: `src/checks/eia_timing_check.py`. **[Checked]** (2026-11-07)
- The centre of each day's curve, EIA minus CAISO, over 1,016 days with both series: the monthly median is 1.00 to 1.09 hours from 2024-01 to 2025-11 and -0.00 to 0.03 hours from 2025-12 to 2026-10. Daily: 1.03 on 2025-12-01, 0.50 on 2025-12-02, 0.03 on 2025-12-03.
- Gap to solar noon at longitude -119.5, labels read as hour ending: before 2025-11-25, EIA +0.83 h and CAISO -0.20 h; after 2025-12-05, EIA -0.17 h and CAISO -0.19 h.
- Hour by hour, the fit is best with the switch at the label 2025-12-02 22:00 UTC. Any switch from 18:00 to 00:00 UTC fits almost as well (mean absolute difference 187 to 190 MW over 2025-11-28 to 2025-12-07, against 210 MW or more outside that range), because the afternoon values are flat, so the exact hour is not sharp.

EIA's page says labels are hour ending. **[Doc]** We found no EIA note about the change. The earlier rule came from sample months in 2025, which all sit before the break.

**Why is it an issue?**
The model learns "weather at hour X gives solar at hour X". Output falls steeply at sunset: in June to August 2026 the median day's largest 2-hour fall was 13,012 MW **[Checked]** (2026-11-07, D14 rule), so a 1-hour slip distorts the ramps and every error. Normalized MAE (Decision D27), in the order persistence D-1, persistence D-2, CAISO as published, CAISO adjusted:
- Training and validation, common hours: 4.9%, 6.1%, 4.7% and 2.7% under D14 (9,083 hours); 4.9%, 6.1%, 5.7% and 3.7% under the old rule (9,086 hours).
- Test period, reference forecasts only, after dropping the 74 weather-gap daylight hours (D17): 5.5%, 7.3%, 5.9% and 3.5% under D14 (2,457 hours); 5.4%, 7.1%, 13.1% and 10.4% under the old rule (2,456 hours).

**[Checked]** (2026-11-07, `src/processing/score_references.py`; `reports/reference_scores.csv` and `reports/reference_scores_test.csv`) An earlier version of these figures kept the 74 weather-gap hours in the test period (13.3% and 6.0% for CAISO as published) and 9,130 hours in training and validation. A blanket shift would be wrong for about 320 days, including the whole test period.

**What are our options?**
- Option A: shift all labels back 1 hour. Pros: simple, right for 2024-03-08 to 2025-12-02. Cons: wrong from 2025-12-03 on, including the whole test set. Correlation with CAISO falls from 0.9978 (2024-03-08 to 2025-11-25) to 0.8071 (2025-12-06 to 2026-10-17). **[Checked]**
- Option B: shift only labels before 2025-12-02 22:00 UTC. Pros: right in both periods (0.9978 and 0.9977). **[Checked]** Cons: depends on the exact break hour, the cause is unknown, and it leaves a 1-hour hole at the switch.
- Option C: trust EIA's documented label everywhere. Pros: matches the documentation. Cons: wrong for about 635 days.
- Option D: use CAISO actual solar as the target. Pros: its timing matches the sun. Cons: only 3 areas, negative night values too, and the plan and README name EIA.

**Which course of action will we use?**
Option B. **[Our call]** For a label L before 2025-12-02 22:00 UTC, the hour ending is L minus 1 hour; from that label on, the hour ending is L. The hour ending 2025-12-02 21:00 UTC then has no EIA value and stays missing (not filled). Raw files are never shifted. Open: why EIA changed, and the exact break hour.

```python
SWITCH = pd.Timestamp("2025-12-02 22:00", tz="UTC")
lab = pd.to_datetime(e["period"], format="%Y-%m-%dT%H", utc=True)
e["hour_end_utc"] = lab.where(lab >= SWITCH, lab - pd.Timedelta(hours=1))
```

#### D15 Negative night values in EIA

**What issue did we identify?**
9,461 of 24,480 rows (38.6%) are negative, from -74 MW up to 0, all at night or near it, and their size grows over time.

**How did we identify it?**
The pull checks (`PULL_LOG.md`, source 1) and Q6.3. **[Checked]**

**Why is it an issue?**
Solar cannot make negative power. A likely cause is plant own use netted out of output. **[Unverified]** Negative values distort averages and what a model learns at night. Scoring uses daylight hours only, but training sees every hour, and scoring night hours would make scores look better.

**What are our options?**
- Option A: set them to 0 in the modeling copy and keep the original in a separate column. Pros: simple and physically sensible. Cons: relies on the unverified explanation and hides the growth trend.
- Option B: leave them as they are. Pros: no change. Cons: the model sees impossible values.
- Option C: drop all night hours from training. Pros: the model sees only daylight. Cons: loses information, needs the daylight rule (D20), and the dawn and dusk hours are edge cases.

**Which course of action will we use?**
Option A, with the same treatment for the target and the benchmark. The original value is kept in its own column. **[Our call]**

#### D16 Positive deep-night values in EIA

**What issue did we identify?**
At pull time, 255 hours on 60 dates showed 100 to 413 MW while the sun was more than 12 degrees below the horizon at Westlands, mostly February to July 2024 (114 in May 2024) and roughly flat through the night. Cause unknown. **[Checked]** (`PULL_LOG.md`, source 1)

**How did we identify it?**
The pull checks and Q6.4. They were found with the labels as given, so they were rechecked after D14 (2026-11-07, `src/checks/eia_timing_check.py`). **[Checked]**
- Pull-time definition (Westlands, sun below -12 degrees at the label and at the label minus 2 hours, labels as given): 255 hours on 60 dates, reproduced.
- After D14, inside the modeling window (hour ending 2024-03-08 00:00 to 2026-10-17 23:00 UTC), EIA above 100 MW with the sun below -12 degrees at the middle of the hour at the capacity-weighted centre (34.79, -117.46): **351 hours on 65 UTC dates**, up to 455 MW. 329 of them are in March to July 2024 (167 in May 2024), 14 in October and November 2024, and 8 spread over 2025 and 2026. Counted by Pacific date it is 76 dates, because one Pacific night crosses Pacific midnight and so spans 2 Pacific dates but 1 UTC date. **[Checked]** (2026-11-07, `src/processing/build_hourly_table.py`)
- An earlier count, 373 hours on 72 UTC dates, covered the whole EIA file and included 22 hours in February 2024, before the window.
- Stricter variant, the whole hour (start and end) below -12 degrees at the same centre: 296 hours on 60 UTC dates in the window, up to 413 MW (313 hours on 66 UTC dates over the whole file).

The count rises rather than falls after D14 because the new definition tests one hour, where the pull-time one required the sun to be down over a 2-hour span.

**Why is it an issue?**
They do not look like solar output, so they could teach the model false patterns or inflate errors.

**What are our options?**
- Option A: flag them. Pros: nothing lost, and the decision stays open. Cons: still in the data.
- Option B: drop them (about 1% of rows). Pros: removes suspect values. Cons: may drop real data.
- Option C: set them to 0. Pros: simple. Cons: hides a possible data problem.

**Which course of action will we use?**
Option A first, then the rule set in advance: if they remain after D14, drop them from training and say so in the report. They remain (351 hours in the window), so they are flagged and dropped from training. **[Our call]** In processing, `src/processing/build_hourly_table.py` sets the column `eia_deep_night_flag` and drops nothing; the model code drops the flagged hours from training. They are never daylight hours, so they never enter the scores.

#### D17 The 129-hour weather gap

**What issue did we identify?**
129 hours (2026-04-17 15:00 to 2026-04-22 23:00 UTC) are null in `cloud_cover_previous_day2` and `relative_humidity_2m_previous_day1` in all 51 files. The gap is inside the test period, and the main model uses day-2 cloud cover.

**How did we identify it?**
The pull checks and Q6.12. A repeat request returned the same nulls, so the gap is in Open-Meteo's archive. **[Checked]**

**Why is it an issue?**
Some models cannot take blanks, and if models are scored on different hours the comparison is unfair.

**What are our options?**
- Option A: drop those hours for every model and the benchmark. Pros: fair, and invents nothing. Cons: loses about 5.4 of the 191 test days (2.8%).
- Option B: use a model that accepts blanks. Pros: keeps the hours. Cons: behavior on those hours is a guess, only some models can do it, and models are no longer comparable.
- Option C: fill with the day-1 forecast. Pros: keeps the hours. Cons: day 1 is issued after the 10 a.m. bid close, so it leaks future information.

**Which course of action will we use?**
Option A. Add a `wx_gap` flag column and report the number of scored hours. **[Our call]** In processing, `src/processing/build_hourly_table.py` sets `wx_gap` (129 hours, 74 of them daylight) and leaves those hours out of `scorable`; `src/processing/score_references.py` reports the hours scored.

#### D18 Capacity scope

**What issue did we identify?**
The 860M plant list for CISO includes plants in Arizona and Nevada: 1,946.9 MW in 2024-01 and 2,778.4 MW in 2026-09. August 2026 nameplate is 25,812.8 MW for all CISO and 23,134.4 MW for California only. It is not verified whether the EIA hourly CISO series includes those plants.

**How did we identify it?**
`PULL_LOG.md` source 4 and the 860M file grouped by `Plant State`. **[Checked]**

**Why is it an issue?**
Capacity is the divisor of our error score. A 1,250 MW average miss is 4.8% of 25,813 MW and 5.4% of 23,134 MW (illustration), so the choice can decide whether we meet the 1.25 times goal.

**What are our options?**
- Option A: all CISO. Pros: matches the target's name, the benchmark, and the weather capacity shares, which were built this way. Cons: may include plants that are not in the target.
- Option B: California only. Pros: matches the "California" framing. Cons: if the target includes Arizona and Nevada output, scores look too big.
- Option C: show both. Pros: shows how much the choice matters. Cons: more clutter.

**Which course of action will we use?**
Option A. Name the scope on every chart and table, and report the California-only score once as a check. **[Our call]**

#### D19 Capacity and peak figures disagree

**What issue did we identify?**
For August 2026, the capacity and peak figures range widely. Nameplate: EIA 860M all CISO 25,812.8 MW, California only 23,134.4 MW; CAISO installed solar 23,920 MW (2026-08-05). Peaks: CAISO 23,367 MW (2026-08-03) and 23,896 MW (August report), EIA hourly 20,852 MW, OASIS ACTUAL 3-hub 19,616 MW.

**How did we identify it?**
`PULL_LOG.md` source 4 and Q6.9. **[Checked]**

**Why is it an issue?**
Mixing sources makes slides contradict each other and shifts scores. Possible causes, none checked **[Unverified]**: CAISO counts only fully commercial units, CAISO peaks use shorter intervals, CAISO peaks include output outside the 3 hubs or outside EIA's CISO series, and nameplate is not delivered power.

**What are our options?**
- Option A: EIA 860M monthly nameplate as the divisor. Pros: monthly, plant level, with coordinates. Cons: nameplate overstates delivered power.
- Option B: CAISO's capacity figures. Pros: official. Cons: 1 number a month in a PDF, with no plant list.
- Option C: the highest observed output as capacity. Pros: avoids definitions. Cons: depends on weather and curtailment.

**Which course of action will we use?**
Option A. Name the source and scope next to every capacity or peak figure. The cause of the disagreement stays an open item. **[Our call]**

#### D20 Definition of daylight

**What issue did we identify?**
The success metrics use daylight hours only, and nobody had fixed what daylight means.

**How did we identify it?**
The README metrics and Q7.3. The Capstone 2 deck numbers used one definition (11,733 daylight hours in the window, `notebooks/Raul_EDA_v2.ipynb`); the FAQ only suggested options.

**Why is it an issue?**
Different cutoffs give different scores for the same model. Night hours are easy (solar is 0), so counting them flatters scores and breaks the comparison with CAISO.

**What are our options?**
- Option A: forecast sunshine above a small threshold. Pros: already in the data. Cons: depends on a forecast, with fuzzy edges.
- Option B: sun above the horizon, computed with `pvlib`. Pros: exact and independent of weather. Cons: one point for the whole state, and dim edge hours stay in.
- Option C: hours where actual solar exceeds some MW. Pros: easy. Cons: uses the answer to pick the hours, which biases the test.

**Which course of action will we use?**
Option B. Daylight means sun elevation above 0 degrees at the middle of the hour (hour ending minus 30 minutes), at the capacity-weighted centre of the weather points with a positive capacity share in `weather_locations.csv` (34.79, -117.46). The same hours score the benchmark and every model. **[Our call]** In processing, `src/processing/build_hourly_table.py` writes the columns `sun_elev` and `daylight` (11,733 daylight hours in the window).

#### D21 The AVA_ hub in the CAISO day-ahead file

**What issue did we identify?**
A 4th label, `AVA_`, appears only in the day-ahead file, from 2026-09-10 07:00 UTC: 912 rows, mean 5.2 MW, max 18.3 MW. The OASIS spec v5.1.2 lists only NP15, SP15, ZP26 and ALL.

**How did we identify it?**
The pull checks and Q6.6. **[Checked]** **[Doc]**

**Why is it an issue?**
Adding it could double count, or add something the actual file does not contain. It is tiny (about 5 MW against peaks above 19,000 MW) and sits in the last weeks of the test period.

**What are our options?**
- Option A: leave it out of the CAISO total. Pros: consistent with the 3 areas in ACTUAL. Cons: a tiny underestimate if it is real.
- Option B: include it. Pros: complete, if it is real. Cons: we would add a number we do not understand.

**Which course of action will we use?**
Option A. It stays in the raw file (D10). Ask CAISO or check the OASIS documentation; open item. **[Our call]**

#### D22 23-hour and 25-hour clock-change days

**What issue did we identify?**
The CAISO daily curtailment report always lists 24 values, also on the 5 clock-change days in our data (2024-03-10, 2024-11-03, 2025-03-09, 2025-11-02, 2026-03-08). How CAISO maps the 24 positions on those days is unknown.

**How did we identify it?**
The pull checks, Q6.18 and Q6.8. **[Checked]** Cross-check on 2025-11-02, the one clock-change day both curtailment files cover (2026-11-07, `src/checks/eia_timing_check.py`): the workbook (5-minute MW summed over intervals and both reasons, divided by 12) and the report (sum of the 6 `<category>_mwh` columns) line up position by position with no shift. Day totals 1,644.2 and 1,644.4 MWh, total absolute difference 0.2 MWh; correlation 1.000 with no shift and 0.31 with a 1-hour shift either way. Curtailment fell only in positions 7 to 17, far from the repeated 01:00 hour, so this shows the 2 files use the same positions but not how CAISO maps them to clock hours. **[Checked]**

**Why is it an issue?**
Curtailment hours could land in the wrong hour on 5 of 954 days (0.5%).

**What are our options?**
- Option A: flag those 5 days and leave them out of the hourly curtailment flags. Pros: avoids wrong hours. Cons: loses 5 days of flags.
- Option B: guess a mapping. Pros: keeps the days. Cons: errors we cannot see.
- Option C: accept the error. Pros: no work. Cons: silent errors.

**Which course of action will we use?**
Option A. **[Our call]** The mapping stays an open item.

#### D23 One processed hourly table

**What issue did we identify?**
The sources use different clocks and grain: hourly, 5-minute and daily; UTC and Pacific; hour ending and hour starting; 3 areas; 51 weather files.

**How did we identify it?**
The pull checks, Q7.5, and the merged-table build for the Capstone 2 numbers.

**Why is it an issue?**
A join that silently drops or duplicates rows, or shifts an hour, gives wrong results with no error.

**What are our options?**
- Option A: build 1 calendar of every UTC hour in the window (22,896 rows) and left join each source onto it. Pros: gaps show as blanks, and everyone has the same rows. Cons: more work up front.
- Option B: inner join the files. Pros: quick. Cons: any gap silently removes that hour.
- Option C: each teammate builds their own. Pros: independence. Cons: different tables, different results.

**Which course of action will we use?**
Option A, as one re-runnable script. Check the row count (22,896) after every join and report blanks per source. Expected: 24 EIA hours (Q6.2), plus 1 at the D14 switch (hour ending 2025-12-02 21:00 UTC); 72 DAM hours (Q6.7); 129 weather hours (Q6.12). Save to `data/processed/` as Parquet (not committed). **[Our call]** In processing, `src/processing/build_hourly_table.py` asserts 22,896 rows after the calendar and after every join, stops with an error if a join changes the count, and writes blanks per column to `data/processed/build_report.txt`. On 2026-11-07 every count matched: 25 EIA, 72 day-ahead, 129 weather, 226 hours with any gap. **[Checked]**

#### D24 Validation fold dates

**What issue did we identify?**
The 763 practice days are split into 4 rolling folds of about 3 months, but the exact dates were not written down.

**How did we identify it?**
The README validation section and Q4.5.

**Why is it an issue?**
Without fixed dates each teammate cuts differently, scores are not comparable, and the claim "winter is tested in practice" cannot be checked.

**What are our options?**
- Option A: the last 4 three-month blocks before the test set. Pros: simple, recent, realistic. Cons: only 2 contain winter, and the earliest 12 months are only ever training data.
- Option B: spread the folds evenly over all 763 days. Pros: every season is validated. Cons: early folds train on very little.
- Option C: fewer, longer folds. Pros: more validation days per fold. Cons: fewer comparisons.

**Which course of action will we use?**
Option A. Validation blocks of 91 days each: 2025-04-11 to 2025-07-10, 2025-07-11 to 2025-10-09, 2025-10-10 to 2026-01-08, and 2026-01-09 to 2026-04-09. Training uses all earlier days and stops at least 1 day before each block starts. Winter days (December to February): 39 of 91 in block 3, 51 of 91 in block 4. **[Our call]** (the exact boundaries are derived from the rule and not yet reviewed day by day) **The dates are replaced by Decision D29** (2026-11-07), because winter was split between 2 blocks.

#### D25 The window end date

**What issue did we identify?**
The end date, 2026-10-17, had no recorded reason (Q4.4).

**How did we identify it?**
Raúl, 2026-11-07: the end date was set by when we pulled the data (2026-10-27 and 2026-10-28). From there we looked back as far as the sources allowed, which the most constrained source set: the weather forecast archive starts on 2024-03-08.

**Why is it an issue?**
A reviewer will ask. EIA can also revise its newest values (Q6.5), so the last days may shift slightly.

**What are our options?**
- Option A: keep 2026-10-17. Pros: no rework, and the test set stays locked. Cons: the newest 2 to 3 weeks are not used.
- Option B: re-pull to a later date. Pros: 2 to 3 more weeks of data. Cons: moves the test set, and all files and scores must be rebuilt before the Nov 16 deadline.
- Option C: end earlier. Pros: more settled EIA values. Cons: less data, with no benefit for the deadline.

**Which course of action will we use?**
Option A. Q4.4 gives the reason. **[Our call]**

#### D26 Which curtailment file for which dates

**What issue did we identify?**
Hourly curtailment comes from 2 files that overlap from 2025-06-01 to 2025-12-31: the workbooks (5-minute MW, only curtailed intervals listed, 2024-01-01 to 2025-12-31) and the daily report (hourly MWh in 6 categories, 2025-06-01 to 2026-10-17). Each has a missing day: the workbook has no rows for 2025-06-16, and the daily report page for 2025-11-05 does not exist. **[Checked]** (`PULL_LOG.md`, source 5; Q6.18)

**How did we identify it?**
Decision D3 and Q6.18, then building the hourly table (2026-11-07).

**Why is it an issue?**
Adding both files would double count the overlap, and either file alone leaves months uncovered. The 2 files also differ in grain, so the hourly series must say which file each date comes from.

**What are our options?**
- Option A: workbook only. Pros: 5-minute detail, one format. Cons: ends on 2025-12-31, so the whole of 2026 (including the test period) has no curtailment; lacks 2025-06-16.
- Option B: daily report only. Pros: one format. Cons: starts on 2025-06-01, so 2024-01-01 to 2025-05-31 has no curtailment; lacks 2025-11-05.
- Option C: split by date. The workbook for 2024-01-01 to 2025-12-31 except 2025-06-16; the daily report for 2025-06-16 and from 2026-01-01. Pros: every date covered. The 2 files agree hour by hour over the 214 overlap days (solar correlation 0.998). **[Checked]** (`PULL_LOG.md`, source 5) Cons: the source changes on 2026-01-01, inside the validation period.

**Which course of action will we use?**
Option C (Raúl, 2026-11-07). **[Our call]** Workbook: sum `Solar Curtailment` MW over the 5-minute intervals and both reasons per Pacific date and `Hour`, then divide by 12 to get MWh. Daily report: `fuel` = solar, sum of the 6 `*_mwh` columns. `Hour` is read as Pacific hour ending (Q6.18, **[Unverified]**) and converted to the UTC hour ending. Hours with no row are 0, because the workbook lists only curtailed intervals. On the 5 clock-change days the value is null and `curt_excluded` is True (D22). In processing: columns `curt_mwh` and `curt_excluded` in `src/processing/build_hourly_table.py`.

#### D27 Scoring definitions

**What issue did we identify?**
The reference scores in the Capstone 2 deck and in later scratch code used slightly different hours. Scores that use different hours, divisors or targets cannot be compared.

**How did we identify it?**
Rebuilding the Capstone 2 scores in `src/processing/score_references.py` (2026-11-07). On training and validation days under D14, CAISO as published scores 4.69% on the common hours (9,083) and 4.73% when only CAISO adjusted drops the clock-change hours (9,130). On the test period, keeping or dropping the 74 weather-gap daylight hours moves CAISO as published from 6.04% to 5.85%. **[Checked]** (`reports/reference_scores.csv`, `reports/reference_scores_test.csv`)

**Why is it an issue?**
The project goal is a score relative to CAISO (1.25 times CAISO's error), so every model and every reference must use the same metric on the same hours.

**What are our options?**
- Which hours. Option A: one common set of hours for all 4 references. Pros: a fair comparison. Cons: loses about 47 daylight hours on the clock-change days, where curtailment is null (D22). Option B: each reference keeps every hour it can be scored on (only CAISO adjusted drops the clock-change hours). Pros: matches the earlier scratch numbers. Cons: the 4 scores use different hours.
- Which persistence. Option D-1: EIA at the same hour 24 hours earlier. Pros: usually more accurate. Cons: the bid closes at 10 a.m. Pacific on the day before delivery, so the afternoon hours of that day are not yet known; D-1 uses information a bidder does not have. Option D-2: EIA at the same hour 48 hours earlier. Pros: every hour of that day is over before the bid closes, so it respects the 10 a.m. rule. Cons: less accurate. Whether EIA has already published those values by 10 a.m. was not checked. **[Unverified]**

**Which course of action will we use?**
**[Our call]** (Raúl, 2026-11-07)
- Metric: normalized MAE, the mean over the scored hours of |forecast - actual| divided by `capacity_mw` of that hour (EIA 860M monthly nameplate, all CISO, D18 and D19), in %. Bias (forecast minus actual, MW) is reported alongside. The California-only divisor is reported once as a check (D18).
- Actual: `eia_mw`, with negatives set to 0 (D15). Scores with EIA as published are reported as a variant; they move by 0.01 points or less.
- The 4 reference forecasts: persistence D-1, persistence D-2, CAISO day-ahead as published (NP15 + SP15 + ZP26) against EIA, and CAISO day-ahead against EIA plus `curt_mwh` (adjusted). Persistence uses the same clipped EIA series. D-2 is the fair persistence for the 10 a.m. rule; D-1 is shown for comparison.
- Hours: `daylight` (D20), with EIA, CAISO day-ahead and both persistence values present, outside `wx_gap` (D17) and with `curt_mwh` not null (D22). This common set is the headline, the same hours for all 4 references and for every model. The per-reference set (Option B) is kept only as a comparison with the earlier scratch numbers.
- Periods: training and validation are Pacific dates (of the hour start) before 2026-04-10. The test period is scored for reference forecasts only, behind the `--with-test` flag, into a separate file. Models are never scored on it before the final evaluation.

Is CAISO adjusted circular? **[Checked]** (2026-11-07, the 4,508 scored validation hours of D29) We compared `curt_mwh` with CAISO's excess over EIA, max(`caiso_dam_mw` minus `eia_mw`, 0). Over all hours the correlation is 0.83, but `curt_mwh` is within 10% of the excess in only 9.4% of hours. In curtailed hours (`curt_mwh` above 1% of `capacity_mw`, 2,164 hours) the correlation is 0.89, curtailment adds up to 104% of the excess, and the median ratio is 0.97; within 10% hour by hour is still only 16.7%. In the other 2,344 hours the correlation is 0.00 and curtailment is 12% of the excess. By month the correlation is 0.81 to 0.94 in February to June 2025 and 2026 and 0.08 to 0.18 in July to September 2025 and November 2025 to January 2026. In hours with `curt_mwh` above 5% of capacity (777), CAISO's nMAE is 11.75% against EIA and 2.77% against EIA plus `curt_mwh`. Reading: when curtailment is large it matches CAISO's own over-forecast in total, so adding it back removes most of CAISO's error in exactly those hours. CAISO adjusted is therefore partly circular, and CAISO as published is the headline comparison. The match is not hour-exact, possibly because CAISO measures curtailment against a forecast other than the day-ahead one **[Unverified]**.

#### D28 Model features and the 10 a.m. rule

**What issue did we identify?**
A day-ahead bid for every hour of Pacific day D closes at 10:00 a.m. Pacific on day D-1. A model that uses anything known only after that time would score better in validation than it could in a real bid.

**How did we identify it?**
The README business problem, Q6.10 and D27 (persistence D-2), then the modeling brief (`briefs/03_modeling_brief.md`). The CAISO day-ahead results come out at about 1:00 p.m. on D-1 (README, business problem), after the bid close.

**Why is it an issue?**
EIA output at t minus 24 h falls after the bid close for afternoon and evening hours. Day-1 weather forecasts are issued about 24 hours ahead, also too late. CAISO's own day-ahead forecast is published after the close and is our benchmark.

**What are our options?**
- Option A: day-2 weather, calendar and sun geometry for hour t, `capacity_mw`, and EIA only at t minus 48 h or earlier (or daily values that end with Pacific day D-2). Pros: respects the rule. Cons: weaker inputs.
- Option B: add day-1 weather and EIA at t minus 24 h. Pros: more accurate. Cons: breaks the rule.
- Option C: add CAISO's day-ahead forecast as an input. Pros: a strong input. Cons: published after the close, and it is the benchmark we are scored against.

**Which course of action will we use?**
Option A (Raúl, 2026-11-07). **[Our call]** `src/modeling/features.py` builds 20 features from `hourly_table.parquet` after dropping test rows:
- Day-2 weather (9): cloud cover, shortwave (GHI), direct, diffuse, direct normal, temperature, humidity, wind, precipitation; plus `csi_previous_day2` = day-2 GHI / clear-sky GHI (blank when clear-sky GHI is under 20 W/m2).
- Calendar and sun (7): Pacific hour of the hour start, hour as sine and cosine, day of year as sine and cosine, `sun_elev` (D20), and pvlib Ineichen clear-sky GHI at the same centre point and mid-hour.
- Capacity (1): `capacity_mw` (EIA 860M monthly nameplate, all CISO).
- EIA (2): `cf_lag48`, EIA at hour ending t minus 48 h divided by `capacity_mw` of hour t (times capacity it equals persistence D-2 exactly, **[Checked]**); `cf_d2_daily`, the mean EIA capacity factor over all hours of Pacific day D-2 (at least 20 hours present).

Lag rule: hourly EIA lags are 48 h or more; daily EIA features end with Pacific day D-2 (for the first hour of D that is 24 h after the last hour used, which the rule allows because D-2 ends before the bid close). `assert_no_leak` fails on a shorter lag, on a column not in the feature list, or on a `*_previous_day1` column outside the labeled comparison. Left out: EIA at t minus 24 h, `caiso_dam_mw`, lags of `curt_mwh` and of OASIS ACTUAL (publication time unknown).

Target: capacity factor `eia_mw / capacity_mw` (D15), predictions clipped to 0 to 1 and multiplied back by `capacity_mw`. Fit rows: daylight, EIA present, `wx_gap` False, `eia_deep_night_flag` False (D16, D17): 9,190 hours. Ridge fills blanks with the median of the training rows of each fold; the trees take blanks as they are.

Day-1 comparison (labeled, never the main model): day-2 cloud cover, GHI and `csi` swapped for their day-1 versions. It moves the gradient-boosted trees from 4.02% to 3.87% pooled validation nMAE (D30), so the 10 a.m. rule costs about 0.15 points. **[Checked]** (2026-11-07, `src/modeling/score_models.py`)

Two assumptions are not verified **[Unverified]**: (1) the day-2 weather forecast for every hour of D is issued before 10 a.m. Pacific on D-1; for late-evening hours of D the run behind the day-2 value may be published later, and Open-Meteo's run times were not checked. (2) EIA has published the D-2 hourly values by 10 a.m. Pacific on D-1 (as in D27).

#### D29 Validation folds

**What issue did we identify?**
The fold dates in D24 split the latest winter between 2 blocks (39 winter days in block 3, 51 in block 4), and the modeling brief asks for one fold that covers Dec 27 to Mar 27, so winter is checked in one piece (risk register item 13). The test set has no winter.

**How did we identify it?**
Comparing D24 with the brief, then building the fold tables with `src/modeling/folds.py` (2026-11-07).

**Why is it an issue?**
A winter error split across 2 folds is harder to read, and the test set cannot show it.

**What are our options?**
All options: training from 2024-03-08, 1 whole gap day, then the validation block; expanding window.
- Option A (`d24`): the D24 blocks. Pros: already recorded, 4 x 91 days. Cons: winter split.
- Option B (`winter91`): 4 blocks of 91 days ending 2026-03-27. Pros: Dec 27 to Mar 27 is one fold. Cons: 2026-03-28 to 2026-04-09 (13 days) never validated.
- Option C (`winter104`): as B, but the last block runs to 2026-04-09 (104 days). Pros: winter in one fold, and every recent day validated. Cons: one block longer than about 91 days.

**Which course of action will we use?**
Option C (Raúl, 2026-11-07). **[Our call]** It replaces the D24 dates. Inner split for tuning: the last 10% of each training window after its own 1-day gap (ridge alpha, tree settings and early stopping). The validation block is never used to tune. `folds.py` asserts that training never overlaps its own validation days, that each gap is a whole day, and that no fold reaches 2026-04-10.

| Fold | Training | Gap day | Validation | Days | Dec to Feb days | Inner split from |
|---|---|---|---|---|---|---|
| 1 | 2024-03-08 to 2025-03-27 (385 d) | 2025-03-28 | 2025-03-29 to 2025-06-27 | 91 | 0 | 2025-02-18 (38 d) |
| 2 | 2024-03-08 to 2025-06-26 (476 d) | 2025-06-27 | 2025-06-28 to 2025-09-26 | 91 | 0 | 2025-05-10 (48 d) |
| 3 | 2024-03-08 to 2025-09-25 (567 d) | 2025-09-26 | 2025-09-27 to 2025-12-26 | 91 | 26 | 2025-07-31 (57 d) |
| 4 | 2024-03-08 to 2025-12-25 (658 d) | 2025-12-26 | 2025-12-27 to 2026-04-09 | 104 | 64 | 2025-10-21 (66 d) |

Pacific dates of the hour start. Written to `reports/folds.csv`. Scored hours (D27 common set): 1,231, 1,212, 951 and 1,114; 4,508 in all on 374 days.

#### D30 Model families kept and dropped

**What issue did we identify?**
The README leaves model types open until the data is explored (Approach, step 3). Candidates must be compared on the same folds and hours, and the reason for keeping or dropping each must be written down.

**How did we identify it?**
The modeling brief and `src/modeling/score_models.py` on the D29 folds, D27 common hours, training and validation days only (2026-11-07). **[Checked]**

**Why is it an issue?**
Choosing a model on the test set, or on hours that differ between models, would make the final score look better than it is.

**What are our options?**
Pooled validation, 4,508 hours. nMAE targets on these hours: 1.25 x CAISO adjusted = 3.44%, 1.25 x CAISO as published = 5.63%. Skill is 1 minus RMSE / RMSE of persistence D-2.
- Climatology (mean capacity factor by month and hour): nMAE 6.58%, skill 0.069, P95 overshoot +15.5% against persistence D-2. Pros: no weather needed. Cons: no better than persistence D-2 (6.60%).
- Ridge (standardized, alpha on the inner split): nMAE 4.70%, skill 0.391, P95 overshoot -36.7%. Pros: simple, fast. Cons: worse than the trees in all 4 folds (5.07, 3.96, 4.50, 5.29% against 4.60, 3.12, 3.91, 4.47%); the chosen alpha jumps from 0.01 to 100 between folds.
- Gradient-boosted trees (`HistGradientBoostingRegressor`, depth 3 or 5, squared or absolute loss, iterations by early stopping on the inner split): nMAE 4.02%, skill 0.473, P95 overshoot -51.2% and undershoot -45.8% against persistence D-2, bias -186 MW. Pros: best of the candidates in every fold. Cons: misses 1.25 x CAISO adjusted.
- References: persistence D-2 6.60%, CAISO as published 4.51%, CAISO adjusted 2.75%; persistence D-1 5.44% (comparison only).

**Which course of action will we use?**
Carry the gradient-boosted trees forward (Raúl, 2026-11-07). **[Our call]** Drop ridge as a candidate but keep it in the result tables. Keep climatology as a floor. Against the 4 README targets the trees pass 3: nMAE within 1.25 x CAISO as published (all 4 folds), skill at least 0.30, P95 overshoot at least 20% below persistence D-2. They fail nMAE within 1.25 x CAISO adjusted (pooled 4.02% against 3.44%; within it only in fold 2). Part of CAISO adjusted's lead is by construction, since CAISO measures curtailment against its own forecast (D27).

How to read the result **[Checked]**: the lead over CAISO as published comes from spring and curtailed hours. By season, CAISO as published against the trees: spring 7.46% and 4.95%, summer 2.89% and 3.04%, fall 3.63% and 3.82%, winter 3.50% and 4.30%. In hours without curtailment (`curt_mwh` at most 1% of `capacity_mw`, 2,344 hours) CAISO scores 2.97% and the trees 3.58%; in curtailed hours (2,164) CAISO 6.17% and the trees 4.51%, against EIA. CAISO forecasts output before curtailment and EIA measures it after, so the trees partly learn curtailment rather than better weather. The 1% threshold is used because `curt_mwh` is above 0 in 94% of scored hours (open item).

`reports/model_results_validation.csv` holds every score by model, fold, month, season, Pacific hour, day-2 cloud cover and curtailment. Per-hour predictions are in `data/processed/oof_predictions.parquet` (not committed). When D30 was made, the test set had not been scored by any model.

Note: the frozen model and its one test run are in Decision D31.

#### D31 Frozen model and the one test run

**What issue did we identify?**
The model chosen on validation (D30) had to be scored once on the locked test set (Pacific dates 2026-04-10 to 2026-10-17), with the model, the settings and the pass rules fixed before any test row was read, so the result could not be tuned to the test.

**How did we identify it?**
The README validation plan, D27 and the final-test brief (`briefs/04_final_test_brief.md`).

**Why is it an issue?**
Choosing or adjusting anything after seeing test results would make the reported score look better than a real day-ahead forecast would do.

**What are our options?**
- Option A: freeze the model, the settings and 5 hypotheses with pass rules, commit them, then run the test once and report whatever comes out. Pros: an honest, final number. Cons: no second chance if something goes wrong.
- Option B: run the test, then adjust. Pros: a better-looking number. Cons: the number no longer measures the future.

**Which course of action will we use?**
Option A (Raúl, 2026-11-07). **[Our call]** Frozen in commit `c242a1c` on branch `raul/final-test`: `reports/final_model_spec.md` (HGB refit on all 763 training and validation days, 9,187 fit rows; settings chosen on the inner split of the last 76 days: depth 5, absolute-error loss, 86 iterations; seed 0) and `reports/hypotheses.md`. `src/modeling/final_test.py` refuses a second run, uncommitted frozen files, or settings that differ from the frozen ones. The test ran once, on 2026-11-07, without errors. **[Checked]**

Result, 2,457 test hours on 187 days (`reports/final_results_test.csv`): our model 4.43% nMAE, CAISO as published 5.85%, CAISO adjusted 3.54%, persistence D-2 7.27%, persistence D-1 5.51%, ridge 5.21%, climatology 6.17%. The 4 reference scores match the earlier reference-only test scores (D14). Verdicts: H1 supported (skill 0.40), H2 partly supported (4.43% against 7.32%, met; against 1.25 x CAISO adjusted 4.4294%, missed by 0.005 points), H3 supported, H4 supported (5.90% against 3.80%), H5 supported (P95 overshoot 23.3% below persistence D-2).

Surprises **[Checked]**: (1) The model over-forecasts on test (bias +494 MW, against -186 MW in validation), most in April and May 2026 (+1,009 and +1,223 MW), when curtailment was 24.0% and 20.7% of solar against 13.2% and 6.6% a year earlier. Our model's spring error rose from 4.95% to 6.34%. Why the bias also appears in hours without curtailment (+508 MW) is not known **[Unverified]**. (2) The reserve gain shrank: P95 overshoot 23.3% below persistence D-2 on test, against 51.2% in validation. (3) CAISO as published did much worse on test than in validation (5.85% against 4.51%; 12.1% in spring), again in curtailed months. (4) Our pooled error moved by only 0.41 points, but 141 of 231 comparisons by group move by more than 0.5 points (`reports/test_vs_validation.csv`). Reserve estimate: `src/modeling/reserve.py` and `reports/reserve_test.csv`; deck numbers: `deck/capstone3/CAPSTONE3_NUMBERS.md`.

### Open items

| Item | Status | Needed from |
|---|---|---|
| EIA alignment rule (Q6.1) | Decided: D14 | |
| Why EIA changed its labeling around 2025-12-02 | Open | EIA documentation, Raúl |
| The exact hour of the EIA change (best fit 22:00 UTC; 18:00 to 00:00 fit almost as well) | Open | Team |
| Negative EIA night values (Q6.3) | Decided: D15 | |
| Deep-night positive EIA values (Q6.4) | Decided: D16 (recount done, dropped from training); cause still unknown | |
| Weather gap (Q6.12) | Decided: D17 | |
| Capacity scope and divisor | Decided: D18, D19 | |
| Why capacity and peak figures disagree (Q6.9) | Open | Raúl |
| What `AVA_` is (Q6.6) | Treatment decided (D21); meaning open | Raúl, CAISO documentation |
| How CAISO maps 24 report positions on 23 and 25 hour days | Treatment decided (D22); mapping open | Raúl |
| Definition of daylight | Decided: D20 | |
| Validation fold dates | Decided: D29 (replaces the D24 dates); table in `reports/folds.csv` | |
| Are day-2 weather forecasts issued before 10 a.m. Pacific on D-1 for every hour of D? | Assumed in D28; Open-Meteo run times not checked | Team |
| Are EIA's D-2 hourly values published by 10 a.m. Pacific on D-1? | Assumed in D27 and D28; not checked | Team |
| Is `curt_mwh` above 0 in nearly every daylight hour real? (94% of scored validation hours; every scored hour from 2026-01, when the source switches to the daily report) | Breakdowns use a 1% of capacity threshold (D30); cause open | Team |

---

## 7. Recommendations: nulls, encoding, data types, merging

These are recommendations, not rules. **[Our call]** Put your choices in your notebook or script so others can re-run them, and tell the team in the group chat if you change a default. Raw files stay untouched.

### Q7.1 How should I treat missing data?

First, separate **missing rows** from **null cells**. Only the weather files and the 860M file have null cells. In every other file, gaps are rows that are absent, so a null count of zero does not mean complete.

1. **Build a full hourly calendar** for your window (UTC), then join each dataset to it. Count what is missing after the join.
2. **Do not fill the target.** Leave EIA gaps (2024-11-02) as missing and drop those hours from training and scoring, for every model and for the benchmark, so all are scored on the same hours.
3. **Weather gap (129 hours).** Keep `NaN`, add a `wx_gap` flag column, and drop those hours for every model and the benchmark (Decision D17). Do not fill them from the other offset, because day 1 and day 2 are different forecasts and day 1 comes after the bid close.
4. **EIA switch hour.** Under Decision D14 the hour ending 2025-12-02 21:00 UTC has no EIA value. Leave it missing, like the other EIA gaps.
5. **DAM missing days.** Drop the three days from benchmark scoring (and from any comparison with the model), or score the model on the same reduced set.
6. **Curtailment.** In the workbook, a blank `Solar Curtailment` means no solar curtailment was listed for that interval (our reading of "only intervals with a curtailment are listed"). Fill with 0 only after you have built the full 5-minute or hourly grid, and never for 2025-06-16, which is missing data. In the daily report, 0 means zero. Leave the 5 clock-change days out of the hourly curtailment flags (Decision D22).
7. **860M blanks** are single spaces (Q7.2). Treat them as null.

### Q7.2 How should I read the files so blanks and types come out right?

- **860M:** read with `na_values=[" "]` in pandas. In R, `readr` trims blanks by default. Without this, `DC Net Capacity (MW)` and the planned-year columns load as text.
- **Open-Meteo:** a column with a gap loads as decimal (`18.0`), one without as integer (`18`). Cast all weather columns to float so every location has the same types.
- **Timestamps:** convert text to timestamps with the time zone set to UTC at read time (see the code in `DATA_HOWTO.md`). Do not leave them as text, and do not let a tool guess a Pacific zone.
- **Curtailment `Date`:** keep only the first 10 characters (the calendar date).
- **Counts and codes:** `OPR_HR`, `Hour` and `Interval` are integers that identify a position in a day, not quantities to average.

### Q7.3 How should I handle negative and odd values?

- **Negative night values** (EIA, ACTUAL): set them to 0 in the modeling copy and keep the original in a separate column, for both the target and the benchmark (Decision D15). The likely cause, station use, is unverified (Q6.3).
- **Positive deep-night values** (EIA): flag them after applying the timing rule (Decision D14), then drop them from training and say so in the report (Decision D16, Q6.4). Do not drop them silently.
- **Night hours in scoring:** the success metrics use daylight hours only. Daylight means sun elevation above 0 degrees at the middle of the hour at the capacity-weighted centre of the weather points, computed with `pvlib` (Decision D20). The same hours score the benchmark and every model.
- **Outliers:** none were removed. Check extreme values against capacity before you drop anything.

### Q7.4 How should I encode categories and time?

- **Constant columns** carry no information and can be dropped in your processed tables: in EIA (`respondent`, `respondent-name`, `fueltype`, `type-name`, `value-units`), in OASIS (`OPR_INTERVAL`, `LABEL`, `XML_DATA_ITEM`, `MARKET_RUN_ID_POS`, `MARKET_RUN_ID`) and in 860M (`Google Map`, `Bing Map`, `Balancing Authority Code`, `Energy Source Code`, `Unit Code`, `Nameplate Energy Capacity (MWh)`). Drop `GROUP` as well; it is not data.
- **Low-cardinality text** (`TRADING_HUB`, `RENEWABLE_TYPE`, `Reason`, `fuel`, `Technology`, `Status`, `Plant State`, `Sector`): store as categories. For a model that needs numbers, use one-hot encoding. Do not label-encode them as 1, 2, 3.
- **Location:** do not use `location_id` as a number. Use latitude and longitude, or the capacity share, or aggregate the 51 points into one series (Q7.5).
- **Time features:** build them from **Pacific** time, since demand, sun and behavior follow the local clock: hour of day, day of year, month. For cycles, use sine and cosine pairs. Solar elevation or clear-sky radiation from `pvlib` is usually a stronger feature than the clock.
- **Scale:** tree models do not need scaling. Linear and neural models do; fit the scaler on training days only.

### Q7.5 How should I merge the datasets?

The rule is: **one key, hour ending in UTC.** Convert every file to it first, then join.

| Dataset | Hour-ending UTC key |
|---|---|
| EIA | `period` as UTC, minus 1 hour for labels before 2025-12-02 22:00 UTC, unchanged from that label on (Decision D14, Q6.1) |
| OASIS DAM and ACTUAL | `INTERVALENDTIME_GMT` |
| Open-Meteo | `time_utc` (radiation is the mean of the hour before this time, **[Doc]**) |

With that key, EIA correlates best with the capacity-weighted day-2 shortwave radiation with no shift (0.9439, against 0.9041 and 0.8977 when one series is moved one hour in either direction; window 2024-03-08 to 2026-10-17). **[Checked]** (2026-11-07, `src/checks/eia_timing_check.py`, same method as the earlier 0.9276, which used the old "minus 1 hour everywhere" rule)

Other steps:

1. **OASIS to one CAISO solar series.** Keep `RENEWABLE_TYPE` = Solar and hubs NP15, SP15, ZP26. Sum the three per hour and keep the hour only if all three are present. Leave out `AVA_` and wind.
2. **Weather to one series.** Either keep per-location features (good for tree models, but 51 x 18 columns), or average the points weighted by `caiso_solar_capacity_share` (points with zero share drop out). The shares are static (2026-09, all CISO) and apply to 2024 only roughly.
3. **Capacity to hours.** Use EIA 860M monthly nameplate, all CISO, for everything (Decisions D18 and D19), name the source and scope in every chart, and join each hour to the capacity of its own month with `file_month`. 2026-10 has no file: carry the 2026-09 value forward and say so.
4. **Curtailment to hours.** Workbook: group by calendar date and `Hour`, sum MW across the intervals and both `Reason` values (Local and System can both appear in one interval), divide by 12 to get MWh. Daily report: sum the six `<category>_mwh` columns. Convert Pacific date and hour to UTC from the local clock reading (midnight plus `Hour`), and do not trust the five clock-change days without checking.
5. **Check after every join.** Row count before and after, number of unmatched keys, and the date range. A join that silently drops rows is the most common error here. The team builds one table on a full calendar of 22,896 UTC hours with left joins (Decision D23).
6. **Window.** Filter to 2024-03-08 to 2026-10-17 only after the joins, and keep the test set (from 2026-04-10) out of any tuning.

### Q7.6 What file formats should I save to?

Save processed tables to `data/processed/` as Parquet (small, keeps types and time zones) or CSV. The folder is not committed. Keep the cleaning in a script or notebook someone else can re-run.

---

## How to add a question

1. Pick the section (1 to 7) the question belongs to. Do not add sections; the seven are fixed.
2. Give it the next number in that section (for example Q6.21) and a heading that is the question in plain words.
3. Answer in a few sentences. Put a tag on every claim: **[Doc]**, **[Checked]**, **[Our call]** or **[Unverified]**. For **[Doc]**, give the link. For **[Checked]**, give the date or the `PULL_LOG.md` section.
4. If the answer changes a number elsewhere (a row count, a date range, a gap), change it there too: `README.md`, `data/README.md`, `DATA_DICTIONARY.md`.
5. If the question reveals a new problem, add a row to "Open items" in section 6 and a line to `PULL_LOG.md`.
6. Update "Last reviewed" at the top, work on a branch, and open a pull request.

Template:

```
### Q<section>.<n> <the question>

<Short answer.> **[tag]** <Detail, with numbers and their source.>
```

## Questions waiting for an answer

Add questions you cannot answer here, with your name and the date. Whoever finds the answer moves it into the right section.

| Date | Asked by | Question |
|---|---|---|
| | | |
