# Data FAQ

Questions and answers about the project's data: where it comes from, why we use it, what is wrong with it, and how to prepare it. Written for teammates who open the raw files in their own tools. Last reviewed: 2026-10-29.

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
| 6 | Issues, risks, limits and the decisions made while pulling |
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
| OASIS ACTUAL solar | **Backup target and timing check** | Used to find the one-hour offset in EIA timestamps. Falls back as the target if EIA turns out unusable (Task 2, "If something slips"). |
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
| EIA hourly | The API returns respondent name "California Independent System Operator" and fuel "Solar". **[Checked]** Hourly values track CAISO's own actual series very closely once the one-hour offset is applied (correlation 0.9981 to 0.9999 in January, March and July 2025; mean absolute difference 200 to 272 MW). **[Checked]** EIA describes the series as metered net generation reported by each balancing authority, and says rooftop solar is typically not included. **[Doc]** (https://www.eia.gov/electricity/930-content/about.html) |
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
- Why EIA's timestamps run one hour late against the sun (Q6.1).
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

Task 1 set January 2024 as the start date. The months before 2024-03-08 are still useful: the persistence baseline needs the day before the first modeled day (2024-03-07), and the EIA files give more winter data for checking the timing rule and the night values. **[Our call]** Apply the modeling window in processing. The raw files are not trimmed.

### Q4.4 Why end on 2026-10-17?

The pull brief fixed it as the last full day used. No further reason is recorded. **[Our call]** (Raúl to add one if there is one.)

### Q4.5 Why is the test set the latest 191 days?

The plan holds out the latest 20% of days. 20% of 954 days is 190.8, rounded to 191, which starts on 2026-04-10 and ends on 2026-10-17. The earlier 763 days are used for training and four rolling validation folds of about three months each, with at least a one-day gap. **[Our call]** (README, Task 1)

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

## 6. Issues, risks, limits and decisions made while pulling

Each entry says what we found, what we did, and where it stands. Counts come from `PULL_LOG.md` unless a date says otherwise. Nothing in a raw file was dropped, filled, shifted or converted.

### Target: EIA hourly solar

**Q6.1 Are EIA's timestamps wrong?** *Open, with a recommended rule.* EIA's page says hourly values use an hour-ending convention. **[Doc]** The data say otherwise: EIA label L matches the hour CAISO reports as ending at L minus 1 hour, in winter, summer, and on both sides of the March clock change. CAISO OASIS and Open-Meteo times line up with the sun; EIA's read about an hour late. **[Checked]** We did not find EIA documentation that explains this. The same shift in PST and PDT rules out a daylight saving error. Recommended rule: align EIA label L to the hour ending at L minus 1 hour in UTC, in processing only. **[Our call]** The team still has to confirm it.

**Q6.2 Are there missing hours?** Yes, 24 (0.10%): the whole Pacific day 2024-11-02 (2024-11-02 08:00 to 2024-11-03 07:00 UTC). A second request returned the same gap, so EIA does not have them. Not filled.

**Q6.3 Why are some values negative?** 9,461 of 24,480 rows (38.6%) are negative, all at night or near it, from -74 up to zero. The size grows over time. A likely cause is station use at the plants netted out of generation, **[Unverified]** and EIA says it publishes balancing authority data as reported without imputation. **[Doc]** Kept in the raw file.

**Q6.4 Why are some deep-night values positive?** 255 hours on 60 dates show more than 100 MW, up to 413 MW, when the sun is more than 12 degrees below the horizon at Westlands. They fall mostly in February to July 2024 (114 in May 2024) and stay roughly flat through the night, so they do not look like solar output. Cause unknown. "Deep night" was defined with the labels as given and must be rechecked once the timing rule is applied. Flag them in processing.

**Q6.5 Can EIA values change after we pulled them?** Yes. EIA says values can be revised after metering or telemetry issues. **[Doc]** The file is a 2026-10-27 snapshot. A later re-pull may differ, especially for the most recent days.

### Benchmark and backup: CAISO OASIS

**Q6.6 What is the `AVA_` hub?** Unknown. It appears in the day-ahead file only, from 2026-09-10 07:00 UTC (912 rows, mean 5.2 MW, max 18.3 MW). The three-hub day-ahead total does not drop against ACTUAL after that date, so there is no sign that capacity moved into it. Kept in raw. Leave it out of the CAISO total until we know what it is. The OASIS spec v5.1.2 lists only NP15, SP15, ZP26 and ALL. **[Doc]**

**Q6.7 Which days are missing?** DAM has no data for three whole Pacific days, the day before each spring clock change: 2024-03-09, 2025-03-08 and 2026-03-07 (72 hours per hub, 0.29%). OASIS answers "no data" for them. ACTUAL misses 2 hours per solar hub (2024-02-27 19:00 UTC and 2024-08-31 18:00 UTC). Wind at ZP26 starts on 2024-02-08. Not filled.

**Q6.8 What else should I know about these two files?**

- **Extra rows.** Whole Pacific days are kept, so 80 rows (both files) fall before 2024-01-01 00:00 UTC and 49 (DAM) or 42 (ACTUAL) fall after 2026-10-17 23:00 UTC. Filter by the UTC range.
- **`GROUP` is not a key.** OASIS assigns it to blocks of rows in each response, so it changes with the request while every other column stays the same.
- **`OPR_HR` follows the local clock.** Checked 2026-10-29 against the UTC columns: it equals elapsed hours since Pacific midnight on all normal days, but on the five clock-change days in the data (2024-03-10, 2024-11-03, 2025-03-09, 2025-11-02, 2026-03-08) it counts clock hours, so 109 of 24,455 hour labels differ from the elapsed-hour reading. Always join on `INTERVALSTARTTIME_GMT` or `INTERVALENDTIME_GMT`, never rebuild time from `OPR_DT` and `OPR_HR`.
- **ACTUAL has negative night values**: 7,959 (NP15), 10,671 (SP15) and 9,901 (ZP26) hourly values. DAM solar has none.
- **DAM runs above ACTUAL in daylight.** In the two windows tested for the `AVA_` question, three-hub DAM minus ACTUAL averaged +929.5 MW (4 weeks before 2026-09-10) and +1,227.0 MW (after), and the same dates in 2025 gave +1,051.7 and +1,374.0 MW. This is not a full-period study. Keep it in mind when reading benchmark errors.

**Q6.9 Why do the capacity and peak figures disagree?** Unresolved, and no figure is chosen. For August 2026: EIA 860M CISO solar nameplate 25,812.8 MW (all CISO, including Arizona and Nevada), 23,134.4 MW (California only); CAISO installed solar 23,920 MW as of 2026-08-05; CAISO peaks 23,367 MW (2026-08-03) and 23,896 MW (August report); EIA hourly peak 20,852 MW; OASIS ACTUAL three-hub peak 19,616 MW. Possible reasons, none checked: CAISO counts only fully commercial units, CAISO peaks use shorter intervals than the hourly series, the CAISO peak includes output outside the three hubs or outside EIA's CISO series, and nameplate is not what a plant delivers at the grid connection. Rule: name the source and scope next to every capacity or peak figure. The full table is in `PULL_LOG.md`, source 4.

### Inputs: Open-Meteo

**Q6.10 What is a "previous day" value?** The forecast made about 24 hours (day 1) or 48 hours (day 2) before the hour it describes. **[Doc]** Use day 2 for the main model because it is available before the 10:00 a.m. Pacific bid close; a forecast issued later would make results look better than they could be in practice. Day 1 is a labeled comparison.

**Q6.11 What did the weather pull skip?** Nine variables came back with data for both offsets. These came back empty (all null) and were not saved: `cloud_cover_low`, `cloud_cover_mid`, `cloud_cover_high`, `visibility`, `snow_depth`, `aerosol_optical_depth`, `dust`. **[Checked]** Aerosol and smoke signals are therefore not available from this source.

**Q6.12 Is anything missing in the weather files?** Yes. 129 hours (2026-04-17 15:00 to 2026-04-22 23:00 UTC) are null in two columns, `cloud_cover_previous_day2` and `relative_humidity_2m_previous_day1`, in all 51 files. The other offset of each variable has values. A repeat request returned the same nulls, so the gap is in Open-Meteo's archive. Not filled. It falls inside the test period. The gap is 0.56% of the 22,896 hours.

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
- The daily report always has 24 values, including the 23 and 25 hour days (2025-11-02, 2026-03-08). How CAISO maps them is unknown.

### Operations

**Q6.19 Why did Python fail to read some files from GitHub?** Some reads of the daily-report file failed with `WinError 10054` (connection reset) during the secure handshake. The fourth try worked, and the Windows web client downloaded the same file without error. Cause not determined; Norton's HTTPS scanning on the pull machine is one possibility (since removed). Wrap URL reads in a retry, or use a local copy. See `DATA_HOWTO.md`.

**Q6.20 Is any API key in the repo?** No. Keys live in `.env`, which is not committed, and every log line passes through `redact()`. Only whoever re-runs the pulls needs the EIA key.

### Decisions made while pulling

| Decision | Choice | Date |
|---|---|---|
| Compressed file names | OASIS, weather and curtailment files end in `.csv.gz`, not `.csv` | 2026-10-27 and 2026-10-28 |
| 860M file | Plain `.csv` | 2026-10-28 |
| Curtailment | Two files (workbooks and daily report) because granularity and categories differ | 2026-10-28 |
| OASIS windows | Pacific operating days (31-day limit counts them); keep every returned row | 2026-10-27 |
| ACTUAL re-pull | Half-month windows starting one operating day early, to avoid the omitted first hour | 2026-10-28 |
| Weather model | `ecmwf_ifs025` for both offsets and all dates | 2026-10-28 |
| Weather window | 2024-03-08 to 2026-10-17 | 2026-10-28 |
| Weather points | 41 grid + 10 cluster points ("option B") | 2026-10-28 |
| Capacity share | Static, from the 2026-09 860M file | 2026-10-28 |
| `AVA_` | Kept in raw | 2026-10-28 |
| EIA timing | Recommended rule only; no raw file shifted | 2026-10-28 |
| Missing data | None filled anywhere | throughout |
| San Diego plants beyond 100 km | No extra weather point | 2026-10-28 |

### Open items

| Item | Needed from |
|---|---|
| Confirm the EIA alignment rule (Q6.1) | Team |
| Decide how to treat negative and deep-night EIA values (Q6.3, Q6.4) | Team |
| Decide how to treat the weather gap (Q6.12) | Team |
| What `AVA_` is (Q6.6) | Raúl, CAISO documentation |
| Why capacity and peak figures disagree (Q6.9) | Raúl |
| How CAISO maps 24 report positions on 23 and 25 hour days | Raúl |

---

## 7. Recommendations: nulls, encoding, data types, merging

These are recommendations, not rules. **[Our call]** Put your choices in your notebook or script so others can re-run them, and tell the team in the group chat if you change a default. Raw files stay untouched.

### Q7.1 How should I treat missing data?

First, separate **missing rows** from **null cells**. Only the weather files and the 860M file have null cells. In every other file, gaps are rows that are absent, so a null count of zero does not mean complete.

1. **Build a full hourly calendar** for your window (UTC), then join each dataset to it. Count what is missing after the join.
2. **Do not fill the target.** Leave EIA gaps (2024-11-02) as missing and drop those hours from training and scoring, for every model and for the benchmark, so all are scored on the same hours.
3. **Weather gap (129 hours).** Keep `NaN`. Options: drop those hours for every model (0.56% of hours), or use a method that accepts missing values. Do not fill them from the other offset without a flag, because day 1 and day 2 are different forecasts. Add a flag column such as `wx_gap`.
4. **DAM missing days.** Drop the three days from benchmark scoring (and from any comparison with the model), or score the model on the same reduced set.
5. **Curtailment.** In the workbook, a blank `Solar Curtailment` means no solar curtailment was listed for that interval (our reading of "only intervals with a curtailment are listed"). Fill with 0 only after you have built the full 5-minute or hourly grid, and never for 2025-06-16, which is missing data. In the daily report, 0 means zero.
6. **860M blanks** are single spaces (Q7.2). Treat them as null.

### Q7.2 How should I read the files so blanks and types come out right?

- **860M:** read with `na_values=[" "]` in pandas. In R, `readr` trims blanks by default. Without this, `DC Net Capacity (MW)` and the planned-year columns load as text.
- **Open-Meteo:** a column with a gap loads as decimal (`18.0`), one without as integer (`18`). Cast all weather columns to float so every location has the same types.
- **Timestamps:** convert text to timestamps with the time zone set to UTC at read time (see the code in `DATA_HOWTO.md`). Do not leave them as text, and do not let a tool guess a Pacific zone.
- **Curtailment `Date`:** keep only the first 10 characters (the calendar date).
- **Counts and codes:** `OPR_HR`, `Hour` and `Interval` are integers that identify a position in a day, not quantities to average.

### Q7.3 How should I handle negative and odd values?

- **Negative night values** (EIA, ACTUAL): a common choice is to set them to zero for modeling, since they are station use, not production (Q6.3, unverified). Keep the original in a separate column, and do the same for both the target and the benchmark.
- **Positive deep-night values** (EIA): flag them after applying the timing rule (Q6.4). Do not drop them silently.
- **Night hours in scoring:** the success metrics use daylight hours only. Define daylight once (for example, `shortwave_radiation_previous_day2` above a small threshold, or solar elevation from `pvlib`) and share the definition.
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
| EIA | `period` as UTC, minus 1 hour (the recommended alignment rule, Q6.1) |
| OASIS DAM and ACTUAL | `INTERVALENDTIME_GMT` |
| Open-Meteo | `time_utc` (radiation is the mean of the hour before this time, **[Doc]**) |

With that key, EIA correlates best with the capacity-weighted day-2 shortwave radiation with no shift (0.9276, against 0.9183 and 0.8553 when the weather is moved one hour in either direction; window 2024-03-08 to 2026-10-17, checked 2026-10-29), which supports the rule.

Other steps:

1. **OASIS to one CAISO solar series.** Keep `RENEWABLE_TYPE` = Solar and hubs NP15, SP15, ZP26. Sum the three per hour and keep the hour only if all three are present. Leave out `AVA_` and wind.
2. **Weather to one series.** Either keep per-location features (good for tree models, but 51 x 18 columns), or average the points weighted by `caiso_solar_capacity_share` (points with zero share drop out). The shares are static (2026-09, all CISO) and apply to 2024 only roughly.
3. **Capacity to hours.** Pick one scope and use it for everything (all CISO, or California only), name it in every chart, and join each hour to the capacity of its own month with `file_month`. 2026-10 has no file: carry the 2026-09 value forward and say so.
4. **Curtailment to hours.** Workbook: group by calendar date and `Hour`, sum MW across the intervals and both `Reason` values (Local and System can both appear in one interval), divide by 12 to get MWh. Daily report: sum the six `<category>_mwh` columns. Convert Pacific date and hour to UTC from the local clock reading (midnight plus `Hour`), and do not trust the five clock-change days without checking.
5. **Check after every join.** Row count before and after, number of unmatched keys, and the date range. A join that silently drops rows is the most common error here.
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
