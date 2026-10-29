# Raw data pull log

One section per source, following `docs/DATA_PULL_BRIEF.md`. All timestamps in raw files are UTC. Raw files are saved exactly as the source returned them: nothing is dropped, filled, shifted or converted.

Pulls are run by Raúl with the scripts in `src/data_pull/`. Run them from the repo root, for example `.venv\Scripts\python -m src.data_pull.eia_hourly --start 2024-01-01 --end 2026-10-17`.

## Setup notes (all sources)

- **HTTPS behind antivirus.** Norton Antivirus on the pull machine re-signs HTTPS traffic with its own root certificate ("Norton Web/Mail Shield Root"). Python's default certificate list does not include it, so requests failed with `CERTIFICATE_VERIFY_FAILED`. `src/data_pull/common.py` now uses the `truststore` package, which makes Python use the Windows certificate store. Certificate checking stays on. Teammates without Norton are not affected.
- **API key redaction.** Every log line, network error and uncaught crash report passes through `redact()` in `common.py`, which replaces the key with `***`. Tested on 2026-10-27 by forcing three errors with the real key attached (unreachable host, wrong EIA route, direct log of the key). The key did not appear in the console or in the log file. Run logs are written to `data/raw/.cache/logs/` (not committed).

## 1. EIA hourly solar generation (target variable)

| Item | Value |
|---|---|
| File | `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv` |
| Endpoint | `https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/` |
| Parameters | `frequency=hourly`, `data[0]=value`, `facets[respondent][]=CISO`, `facets[fueltype][]=SUN`, `start=YYYY-MM-DDT00`, `end=YYYY-MM-DDT23`, `sort[0][column]=period`, `sort[0][direction]=asc`, `offset`, `length=5000` |
| Requests | One per calendar month (34 months; every month fits in one page) |
| Date pulled | 2026-10-27 |
| Script | `src/data_pull/eia_hourly.py` (monthly cache in `data/raw/.cache/eia/`) |
| Rows | 24,480 (expected 24,504) |
| First / last timestamp (UTC) | 2024-01-01 00:00 / 2026-10-17 23:00 |
| Columns | `period`, `respondent`, `respondent-name`, `fueltype`, `type-name`, `value`, `value-units` |

**Differences from the brief**

- The API returns two extra descriptive columns, `respondent-name` ("California Independent System Operator") and `type-name` ("Solar"). Kept, as the brief says to keep all returned columns.
- `value-units` is "megawatthours", not MW. For one hour, MWh produced equals average MW, so the numbers are the target as defined in the README. Units are not converted.
- Route metadata (checked 2026-10-27) labels this frequency "hourly (UTC)", with data from 2019-01-01T00 onward. The route also offers `local-hourly`, which is not used.

**Check table**

| Check | Result |
|---|---|
| 1. Rows / expected | 24,480 / 24,504 |
| 1. Missing hours | 24 (0.10%), listed below |
| 2. Duplicate timestamps | 0 |
| 3. First / last timestamp (UTC) | 2024-01-01 00:00 / 2026-10-17 23:00 (matches requested range) |
| 4. Night / midday | Deep-night hours: median -45, 85% negative. Midday labels (UTC 19 to 22): min 97, median 14,812, max 20,852, none at or below zero. See open issue on timing. |
| 5. Nulls | 0 in every column |
| 5. `value` min / median / max | -74 / 559.5 / 20,852 |
| 5. `value` negative values | 9,461 of 24,480 rows |
| 6. File size | 2.12 MB (2,122,906 bytes); about 0.12 MB if gzip-compressed. UTF-8, `\n` line endings |

**Known gaps**

- 2024-11-02 08:00 UTC through 2024-11-03 07:00 UTC (24 hours) are missing. This is one full Pacific day, 2 November 2024 (PDT), the day before daylight saving time ended. A second request for 2024-11-01T20 to 2024-11-03T12 on 2026-10-27 returned the same gap, so the hours are absent from EIA, not lost in paging. Not filled.

**Negative night values (kept as is)**

- 9,461 rows are negative, all in night or near-night hours, from -74 to just below zero. Their size grows over time (monthly minimum about -55 to -60 in 2024, down to -74 in August 2026). A likely cause is plants' own overnight station use being netted out of generation. This is not confirmed. They stay in the raw file. Whether to set them to zero is a processing decision for the team.

**Positive values at deep night (kept as is)**

- 255 hours on 60 dates show more than 100 MW (up to 413 MW) when the sun is more than 12 degrees below the horizon at Westlands (36.4, -120.1), at both the label time and two hours before it. They fall in February to July 2024 (114 in May 2024), plus 9 in October 2024 and 1 in May 2025, and stay roughly flat through the night. They do not look like solar output. Cause unknown. Flag them in processing.
- These "deep night" hours were defined using the EIA `period` labels as given (sun position checked at the label time and at the label minus 2 hours). They must be rechecked once the timing offset is known.

**Open issue: timestamps appear about one hour later than "hour ending"**

- No timestamps were shifted. The raw file keeps EIA's `period` exactly as returned.
- Test (2026-10-27): hourly values were correlated with pvlib clear-sky GHI, averaged over the brief's five approximate cluster points (not capacity-weighted), at offsets of -180 to +180 minutes in 15-minute steps. Reading label L as the hour from L-1h to L ("hour ending"), the best fit is 60 minutes earlier, meaning label L behaves like the hour from L-2h to L-1h.
  - January 2024: best offset -60 min, correlation 0.917 (0.858 at hour ending).
  - July 2024: best offset -60 min, correlation 0.957 (0.915 at hour ending).
- Example: on 2024-01-15 the sun sets around 17:10 Pacific, yet EIA's `local-hourly` row `2024-01-15T18-08` shows 1,199 MW.
- The shift is the same in winter (PST) and summer (PDT), so it is not a daylight saving error.
- No EIA documentation confirming or explaining this has been found yet.
- Next step (agreed with Raúl, 2026-10-27): when CAISO OASIS is pulled (source 2), also pull the `ACTUAL` series if it exists. Cross-correlate EIA with it at hourly lags from -3 to +3, separately for a winter month, a summer month and a month around a daylight saving change. Report the best lag for each month and which series were compared.
- Result (2026-10-28): see "Timing test: EIA vs CAISO ACTUAL vs the sun" under source 2. In every month tested, EIA label L matches the CAISO ACTUAL hour that ended at L minus 1 hour, and CAISO ACTUAL lines up with the sun while EIA is about one hour late. Still open: no timestamps shifted; the team decides the alignment rule in processing.
- **Recommended rule (open issue, Raúl 2026-10-28): EIA label L = the hour ending at L minus 1 hour** (that is, the hour from L-2h to L-1h UTC). Apply it in processing only. No raw file is shifted.

## 2. CAISO OASIS wind and solar forecast (benchmark) and ACTUAL (backup target)

| Item | Value |
|---|---|
| Files | `caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz` and `caiso_actual_solar_2024-01-01_2026-10-17.csv.gz` |
| Endpoint | `https://oasis.caiso.com/oasisapi/SingleZip` |
| Parameters | `queryname=SLD_REN_FCST`, `market_run_id=DAM` or `ACTUAL`, `version=1`, `resultformat=6` (CSV in a ZIP), `startdatetime` and `enddatetime` at Pacific midnight in UTC, e.g. `20240101T08:00-0000` |
| Requests | DAM: one per calendar month of operating days (35). ACTUAL: half months (1-15, 16-end), each requested from one operating day earlier (2 to 17 days per request, 69 requests); the extra day is dropped when the file is built. At least 5 s apart. Windows that return error 1000 are re-requested one day at a time. |
| Date pulled | DAM 2026-10-27 (re-verified 2026-10-28 after an abrupt PC restart, see below). ACTUAL re-pulled 2026-10-28 with overlapping windows (see "ACTUAL re-pull") |
| Script | `src/data_pull/caiso_oasis.py` (cache in `data/raw/.cache/oasis/DAM/` and `data/raw/.cache/oasis/ACTUAL_overlap/`, no-data days in `data/raw/.cache/oasis/nodata_days.csv`; the old monthly ACTUAL cache in `data/raw/.cache/oasis/ACTUAL/` is no longer used) |
| Operating days covered | 2023-12-31 to 2026-10-17 (Pacific). First / last interval start: 2023-12-31 08:00 / 2026-10-18 06:00 UTC in both files |
| Rows | DAM 146,706; ACTUAL 146,210 |
| Columns (both) | `OPR_DT`, `OPR_HR`, `OPR_INTERVAL`, `INTERVALSTARTTIME_GMT`, `INTERVALENDTIME_GMT`, `TRADING_HUB`, `RENEWABLE_TYPE`, `LABEL`, `XML_DATA_ITEM`, `MARKET_RUN_ID_POS`, `RENEW_POS`, `MW`, `MARKET_RUN_ID`, `GROUP` |

**Differences from the brief**

- **File names end in `.csv.gz`, not `.csv`** (Raúl's decision, 2026-10-27). They are gzip-compressed CSV, read directly by `pandas.read_csv`. Uncompressed they would be 20.7 MB (DAM) and 23.0 MB (ACTUAL).
- **Requests use Pacific operating days.** OASIS counts its 31-day limit in Pacific operating days (error 1004 when a UTC-midnight window touched 32 operating days). Each request runs from Pacific midnight to Pacific midnight. To cover every UTC hour from 2024-01-01 00:00 to 2026-10-17 23:00, operating day 2023-12-31 is included.
- **Every row OASIS returned for operating days 2023-12-31 to 2026-10-17 is kept** (Raúl's decision), including 80 rows (both files) before 2024-01-01 00:00 UTC and 49 DAM / 42 ACTUAL rows after 2026-10-17 23:00 UTC. Apply the UTC range in processing. For ACTUAL, the extra operating day at the start of each overlapping window is not kept (it duplicates the previous window).
- **`GROUP` depends on the request, not the data.** It is a counter OASIS assigns to blocks of rows within each response. The old monthly ACTUAL build and the new overlapping build give different `GROUP` values for every row while all other columns match. Kept as returned; do not use it as a key.
- `ACTUAL` exists as a `market_run_id` for this report, labelled "Renewable Forecast Actual Generation" (`RENEW_FCST_ACT_MW`).
- Reference: CAISO OASIS Interface Specification v5.1.2 (Fall 2017) lists SLD_REN_FCST data items and the hubs NP15, SP15, ZP26. UTC columns are `INTERVALSTARTTIME_GMT` and `INTERVALENDTIME_GMT` (all intervals are 1 hour). `OPR_DT` and `OPR_HR` are the Pacific operating day and hour ending (1 to 24, 25 on the fall-back day).

**Series in the files (rows per hub and type)**

| Hub | Type | DAM rows | ACTUAL rows | Notes |
|---|---|---|---|---|
| NP15 | Solar | 24,455 | 24,525 | |
| SP15 | Solar | 24,455 | 24,525 | |
| ZP26 | Solar | 24,455 | 24,525 | |
| NP15 | Wind | 24,455 | 24,524 | |
| SP15 | Wind | 24,455 | 24,524 | |
| ZP26 | Wind | 23,519 | 23,587 | Starts 2024-02-08 08:00 UTC in both files (not a gap) |
| AVA_ | Solar | 912 | none | DAM only, starts 2026-09-10 07:00 UTC. A new hub; meaning not yet checked. Kept in raw (Raúl, 2026-10-28). Not part of the three-hub CAISO solar total used below; see "AVA_ check" |

**Check table (within the UTC range 2024-01-01 00:00 to 2026-10-17 23:00, 24,504 hours per series)**

| Check | DAM | ACTUAL |
|---|---|---|
| 1. Missing hours, each solar hub | 72 (0.29%), identical across NP15, SP15, ZP26 | 2 (0.01%), identical across hubs |
| 1. Missing days | 3 full operating days: 2024-03-09, 2025-03-08, 2026-03-07 | None |
| 2. Duplicate timestamps per hub and type | 0 | 0 |
| 3. Timestamps | UTC, all intervals 1 hour | UTC, all intervals 1 hour |
| 4. Night / midday (solar) | Night exactly 0 | Night slightly negative; midday positive |
| 5. Nulls / non-numeric MW | 0 / 0 | 0 / 0 |
| 5. Solar MW max (NP15 / SP15 / ZP26) | 2,897.6 / 14,948.7 / 3,082.8 | 2,615.1 / 14,570.0 / 2,966.9 |
| 5. Solar negatives (NP15 / SP15 / ZP26) | 0 / 0 / 0 | 7,959 / 10,671 / 9,901 |
| 6. File size | 1.30 MB gzip (1,300,951 bytes) | 1.72 MB gzip (1,715,474 bytes) |

**Known gaps**

- **DAM: the operating day before each spring daylight saving change has no data** (2024-03-09, 2025-03-08, 2026-03-07; DST began 2024-03-10, 2025-03-09, 2026-03-08). OASIS returns error 1000 ("No data returned") for those days, and for any window that contains them, so those three months were fetched one day at a time. Not filled.
- **ACTUAL: 2 missing hours per solar hub, both real gaps at CAISO:** 2024-02-27 19:00 UTC (mid-window) and 2024-08-31 18:00 UTC (absent also in a wider window, tested 2026-10-28). Wind hubs NP15 and SP15 miss 3 hours each. Not filled.
- **ZP26 Wind** starts on 2024-02-08 08:00 UTC, so it lacks 920 hours before that. Its totals are 992 missing in DAM (920 + the 72 DST-eve hours) and 924 in ACTUAL (920 + 4).

**ACTUAL re-pull (2026-10-28, Raúl's decision).** The first ACTUAL pull (monthly windows) was missing 13 hours per solar hub, and 11 of them were artifacts of the request windows: when an ACTUAL request starts at Pacific midnight in winter (08:00 UTC), OASIS omits that first hour. Test: operating days 2025-02-28 to 2025-03-01 returned 2025-03-01 08:00 UTC (NP15 solar 11.97 MW), while operating day 2025-03-01 alone did not. ACTUAL was re-pulled with half-month windows that start one operating day early. DAM was not re-pulled (it has no such gaps). Verification:

| Check | Result |
|---|---|
| Rows | 146,210 = 146,141 (first pull) + 69 added |
| Added rows | 69, all hour ending 1, at 08:00 UTC on 2023-12-31 (5), 2024-01-01 (5), 2024-02-01 (5), 2024-03-01, 2024-12-01, 2025-01-01, 2025-02-01, 2025-03-01, 2025-12-01, 2026-01-01, 2026-02-01, 2026-03-01 (6 each; 5 before ZP26 Wind started) |
| Rows removed vs first pull | 0 |
| Rows in both pulls | 146,141; `MW` and every other column identical except `GROUP` (request-dependent, see above) |
| Missing solar hours remaining | 2 per hub (the real gaps above) |
| Duplicates (hub, type, interval start) | 0 |
| Overlap days dropped | 9,706 rows. 9,591 are identical (same key and `MW`) to the rows kept from the previous window, 0 differ, and 115 are operating day 2023-12-30 (before the first kept day) |
| Request lengths | 2 to 17 operating days (under the 31-day limit) |
| Atomic writes | No temporary files left; every cache file and the final file are written to a temporary file and renamed |

The timing test below was run on the first ACTUAL pull. All rows it used are unchanged in the re-pull, so its results stand.

**Restart check (2026-10-28).** The PC restarted abruptly after the pull. The pull had already finished (both files written, exit code 0); the restart interrupted only a read-only analysis. Verified afterwards: both `.csv.gz` files decompress fully (gzip CRC checked) and have the rows, columns and first and last timestamps above; all 70 monthly cache files are readable, end with a newline and contain every expected operating day; no zero-byte files and no leftover temporary files; `nodata_days.csv` has 3 lines and no duplicates. Nothing was re-pulled. Since then, every cache write goes to a temporary file that is renamed only when complete, and `nodata_days.csv` is rewritten the same way without duplicates. A re-run with a full cache made no requests and rebuilt both files with identical row counts.

**Timing test: EIA vs CAISO ACTUAL vs the sun (2026-10-28)**

Series compared: EIA `value` (file 1, `period` as given) against CAISO ACTUAL solar summed over NP15, SP15 and ZP26 (only hours with all three hubs; every hour qualified). Lag k means EIA label L is paired with the CAISO interval ending at L + k hours; k = 0 would make EIA's label "hour ending".

| Month | Best lag | Corr at best | MAE at best (MW) | Corr at k = 0 | Corr at k = -2 |
|---|---|---|---|---|---|
| January 2025 | -1 | 0.9999 | 200 | 0.9115 | 0.9187 |
| March 2025, whole month | -1 | 0.9981 | 236 | 0.9157 | 0.9268 |
| March 2025, 1 to 8 (PST) | -1 | 0.9955 | 274 | 0.9102 | 0.9305 |
| March 2025, 10 to 31 (PDT) | -1 | 0.9998 | 211 | 0.9196 | 0.9271 |
| July 2025 | -1 | 0.9999 | 272 | 0.9371 | 0.9428 |

Against the sun (pvlib clear-sky GHI, Ineichen model, at the brief's five approximate cluster points; best shift in 15-minute steps; negative means the series behaves like an earlier hour than its timestamps say):

| Month | EIA (label read as hour ending) | CAISO ACTUAL (stated interval) | Production centre vs clear-sky centre, EIA / CAISO (min) |
|---|---|---|---|
| January 2025 | -45 to -60 min | 0 to +15 min | +57.9 / -1.1 |
| March 2025, 1 to 8 (PST) | -45 to -60 min | 0 to +30 min | +47.2 / -9.8 |
| March 2025, 10 to 31 (PDT) | -45 to -60 min | 0 to +15 min | +54.4 / -4.4 |
| July 2025 | -45 to -60 min | 0 to +15 min | +57.0 / -1.9 |

Reading: EIA label L carries the hour CAISO reports as ending at L minus 1 hour (starting at L minus 2 hours), in winter, summer and on both sides of the March DST change. CAISO ACTUAL's stated intervals line up with the sun; EIA's labels read as hour ending are about one hour late. The values are close but not identical (MAE 200 to 270 MW at the best lag; only 26% of January 2025 hours agree within 1 MW), so EIA is not a plain copy of this OASIS series. No timestamps were shifted in any raw file.

**AVA_ check (2026-10-28).** Question: after `AVA_` appears in DAM on 2026-09-10, does the DAM total of NP15 + SP15 + ZP26 solar drop relative to the ACTUAL total of the same three hubs? Daylight hours are hours with ACTUAL above 500 MW. Difference = DAM minus ACTUAL.

| Period | Daylight hours | Mean difference (MW) | DAM / ACTUAL (energy) |
|---|---|---|---|
| 2026-08-13 07:00 to 2026-09-10 06:00 UTC (4 weeks before) | 356 | +929.5 | 1.0705 |
| 2026-09-10 07:00 to 2026-10-18 06:00 UTC (after) | 438 | +1,227.0 | 1.0971 |
| Same dates in 2025, before | | +1,051.7 | 1.0866 |
| Same dates in 2025, after | | +1,374.0 | 1.1194 |

The three-hub DAM total does not drop relative to ACTUAL after 2026-09-10; the gap widens, by about as much as it widened over the same dates in 2025, when `AVA_` did not exist. `AVA_` itself is small (DAM mean 5.2 MW, max 18.3 MW since 2026-09-10). No sign that capacity moved out of the three hubs into `AVA_`. What `AVA_` represents is still unknown.

## 3. Open-Meteo previous-runs weather forecasts

Status 2026-10-28: full pull done for 51 locations (41 grid + 10 cluster), 2024-03-08 to 2026-10-17. See "Full pull" at the end of this section.

**Model and window (Raúl's decision, 2026-10-28)**

- Model `ecmwf_ifs025` for both `_previous_day1` and `_previous_day2`, for the whole period. The model name is in every file name (`openmeteo_prev_runs_ecmwf_ifs025_<location_id>_<start>_<end>.csv.gz`) and in a `model` column. `best_match` was not used: in California it gives HRRR for day 1 and GFS for day 2, which mixes models.
- Window: **2024-03-08 to 2026-10-17**. It starts on 2024-03-08 because that is the first full UTC day on which every variable has data for both offsets in this model's previous-runs archive. The last variable to start is day 2 radiation, at 2024-03-07 17:00 UTC. The script never requests earlier dates (`MODEL_START` in `src/data_pull/openmeteo.py`).
- First valid hour per variable (UTC; checked 2026-10-28 at g01 (41.5, -123.5) and g41 (33.5, -115.5), identical at both, no nulls after the first valid hour through 2024-03-31):

| Variable | Day 1 first valid hour | Day 2 first valid hour |
|---|---|---|
| `precipitation` | 2024-02-03 22:00 | 2024-02-04 22:00 |
| `cloud_cover` | 2024-02-04 00:00 | 2024-02-05 00:00 |
| `temperature_2m` | 2024-02-04 00:00 | 2024-02-05 00:00 |
| `wind_speed_10m` | 2024-02-04 00:00 | 2024-02-05 00:00 |
| `relative_humidity_2m` | 2024-02-29 18:00 | 2024-03-01 18:00 |
| `shortwave_radiation` | 2024-03-06 17:00 | 2024-03-07 17:00 |
| `direct_radiation` | 2024-03-06 17:00 | 2024-03-07 17:00 |
| `diffuse_radiation` | 2024-03-06 17:00 | 2024-03-07 17:00 |
| `direct_normal_irradiance` | 2024-03-06 17:00 | 2024-03-07 17:00 |

**Note for the whole project: the weather archive starts later than the other sources.** EIA (source 1) and CAISO OASIS (source 2) start on 2024-01-01; the weather inputs start on 2024-03-08. Any model that uses weather can only train and be scored from 2024-03-08. With the window 2024-03-08 to 2026-10-17 (954 days), the latest 20% of days (191 days) starts on about **2026-04-10**, so the locked test set shifts to about 2026-04-10 to 2026-10-17. Raúl will update README.md.

**Locations (grid only so far)**

- Boundary: California feature (`iso_3166_2` = US-CA) of Natural Earth 1:10m Admin 1 states and provinces, v5.1.2, from `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_1_states_provinces.geojson`. Only the California extract is saved: `data/raw/reference/california_boundary_ne10m.geojson` (44,555 bytes). The full file (40.7 MB) stays in `data/raw/.cache/naturalearth/` and is not committed.
- Grid: centres of 1-degree cells (latitudes 32.5 to 41.5, longitudes -124.5 to -114.5); 110 candidates in the bounding box, **41 inside California**, saved to `data/raw/weather_locations.csv` (`g01` to `g41`). Script: `src/data_pull/weather_locations.py`.
- Gaps to cover with cluster points and the coverage check: no grid point south of 33.5 N (the border runs just north of 32.5 N, so Imperial Valley and San Diego have none), and 34.5 N is the only row reaching -114.5 (the Blythe area at 33.5 N, -114.5 is on the Arizona side).

**Documentation (`https://open-meteo.com/en/docs/previous-runs-api`, read 2026-10-28)**

- `_previous_dayN` returns the value predicted N x 24 hours before the valid time. "Most models are archived from January 2024."
- Timestamps: "Solar radiation is averaged over the past hour. Use instant for radiation at the indicated time." With `timezone=UTC` the API returns GMT, `utc_offset_seconds` 0.
- Free tier (pricing and terms pages): 600 calls per minute, 5,000 per hour, 10,000 per day (300,000 per month listed, not enforced yet); non-commercial use only. A request with more than 10 variables or more than 2 weeks for one location counts as several calls, fractionally (15 variables over 2 weeks = 1.5 calls). The pricing page says historical, climate, ensemble and satellite APIs need a paid plan; previous-runs requests without a key returned data in the probes below.

**Probes (point g24, 36.5, -119.5; no files saved)**

- No previous-runs data exists for 2024-01-01 in either model, so the January 2024 test could not be run as planned. First non-null hour (UTC):

| Model | Day 1 | Day 2 |
|---|---|---|
| `ecmwf_ifs025` | temperature and cloud cover 2024-02-04 00:00; radiation 2024-03-06 17:00 | temperature and cloud cover 2024-02-05 00:00; radiation 2024-03-07 17:00 |
| `best_match` | 2024-01-19 12:00 | 2024-01-20 12:00 |
| `ncep_hrrr_conus` | 2024-01-19 18:00 | none |
| `gfs025` | none | none |

- At this point `best_match` day 1 equals `gfs_seamless` and `ncep_hrrr_conus` exactly (2024-07-01 to 14 and 2026-10-01 to 14). HRRR has no day 2, so `best_match` mixes HRRR (day 1) with GFS (day 2).
- Variables with data for both offsets (2025-01-01 to 14): `cloud_cover`, `shortwave_radiation`, `direct_radiation`, `diffuse_radiation`, `direct_normal_irradiance`, `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `precipitation`, `shortwave_radiation_instant` (both models); `snowfall` (`best_match` only). All null in both models: `cloud_cover_low`, `cloud_cover_mid`, `cloud_cover_high`, `visibility`, `snow_depth`, `aerosol_optical_depth`, `dust`. Unknown variable names return null columns rather than an error.
- Radiation timing vs the sun (pvlib clear-sky GHI, 2025-01 and 2025-07): `shortwave_radiation` day 1 and day 2 match best at 0 minutes shift when read as the mean of the preceding hour (correlation 0.975 to 0.999; production centre within 8 minutes of clear sky); `shortwave_radiation_instant` matches best at 0 minutes as an instantaneous value. This agrees with the documentation.

**April 2024 test (2026-10-28, 41 grid points, `ecmwf_ifs025`)**

- Script: `src/data_pull/openmeteo.py`. One request per location per calendar quarter, 18 hourly columns (9 variables x 2 offsets), `timezone=UTC`. Each JSON response is cached in `data/raw/.cache/openmeteo/ecmwf_ifs025/` (atomic writes). A ledger of weighted calls (`data/raw/.cache/openmeteo/call_ledger.csv`) keeps the pull under 500 per minute, 4,500 per hour and 9,500 per day across runs; on HTTP 429 the request waits 60 s, then 120 s, and so on.
- Columns: `time_utc`, `location_id`, `latitude`, `longitude` (requested point), `model`, `model_latitude`, `model_longitude`, `model_elevation` (as returned by the API), then the 18 weather columns. The three `model_` columns are an addition to the brief's column list; they are values the API returns.
- Units (as returned): cloud cover and relative humidity %, radiation W/m², temperature °C, wind speed km/h, precipitation mm.

| Check | Result |
|---|---|
| 1. Rows | 720 in each of 41 files (30 days x 24 hours) |
| 1. Missing hours | 0 in every file |
| 2. Duplicate timestamps | 0 in every file |
| 3. First / last `time_utc` | 2024-04-01T00:00 / 2024-04-30T23:00 (UTC) |
| Day 1 and day 2 columns | All 18 present in every file |
| 4. Night / day | Every radiation column is 0 when the sun is more than 10 degrees below the horizon; shortwave radiation max 1,095 W/m² (day 1) |
| 5. Nulls | 0 in all 18 weather columns (29,520 cells each) |
| 5. Ranges (day 1) | cloud cover 0 to 100; temperature -20.2 to 37.0 °C; relative humidity 5 to 100; wind 0 to 51.9 km/h; precipitation 0 to 4.8 mm |
| 6. File size | 18,369 to 20,830 bytes per file; 813,674 bytes for 41 files (gzip; 4.19 MB uncompressed) |
| Grid cells | 41 distinct; largest distance from requested point to returned cell 22.0 km |
| Calls | 41 requests, 158.1 weighted calls; no 429, no budget waits |

**Full pull (2026-10-28, approved by Raúl after the cluster points and coverage check; see source 4)**

| Item | Value |
|---|---|
| Files | 51, `data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_<location_id>_2024-03-08_2026-10-17.csv.gz` (g01 to g41, c01 to c10) |
| Requests | 612 (51 locations x 12 calendar quarters), 2026-10-28 18:09:58 to 19:15:49 UTC |
| Weighted calls | 6,255.5 for the full pull (Open-Meteo's counting); highest in any 60-minute window 4,497.9, in any 60-second window 339.2. The call ledger paused 19 times to stay under the hourly limit. No HTTP 429, no retries, no errors. All probes and tests on 2026-10-28 together with the full pull: 665 requests, 6,455.1 weighted calls (free tier: 10,000 per day) |

| Check | Result |
|---|---|
| 1. Rows | 22,896 in every file (954 days x 24 hours) |
| 1. Missing hours | 0 in every file |
| 2. Duplicate timestamps | 0 in every file |
| 3. First / last `time_utc` | 2024-03-08T00:00 / 2026-10-17T23:00 in every file |
| Columns | All 18 weather columns (9 variables x day 1 and day 2) in every file; `model` is `ecmwf_ifs025` throughout; each file has one constant model grid cell; 51 distinct cells |
| 4. Night / day | `shortwave_radiation_previous_day1` is 0 whenever the sun is more than 10 degrees below the horizon (all files) |
| 5. Nulls | 0 in 16 of the 18 weather columns. **129 in `cloud_cover_previous_day2` and 129 in `relative_humidity_2m_previous_day1` in every file**, see below |
| 5. Ranges, all files (day 1) | shortwave radiation 0 to 1,108 W/m²; temperature -21.0 to 50.8 °C |
| 6. Size | 558,175 to 594,130 bytes per file; **29,276,060 bytes (29.3 MB) for 51 files** (gzip); 164.9 MB uncompressed |

**Rebuild from cache (2026-10-28).** The first build wrote whole-number values as `18.0` in the two columns that contain the April 2026 gap (`cloud_cover_previous_day2`, `relative_humidity_2m_previous_day1`), because pandas turns a column with blanks into decimals; the API sends them as whole numbers (`18`). `src/data_pull/openmeteo.py` now keeps each value exactly as the API sent it, and the 51 files were rebuilt from the cached responses (no API calls). Values are unchanged; only the text form of those two columns changed. The checks above were rerun on the rebuilt files with the same results.

**Known gap: 2026-04-17 15:00 to 2026-04-22 23:00 UTC (129 hours), `cloud_cover_previous_day2` and `relative_humidity_2m_previous_day1` only.** The same hours are null in all 51 files, and the other offset of each variable (`cloud_cover_previous_day1`, `relative_humidity_2m_previous_day2`) has values for those hours. A second request for 2026-04-16 to 2026-04-23 at g24 on 2026-10-28 returned the same nulls, so the gap is in Open-Meteo's archive, not in the pull. Not filled. It falls inside the locked test period (from about 2026-04-10).

## 4. EIA Form 860M installed capacity

| Item | Value |
|---|---|
| File | `eia860m_solar_ciso_capacity_by_month.csv` (plain CSV, Raúl's decision) |
| Date pulled | 2026-10-28 |
| Months | 2024-01 to 2026-09 (33 monthly files). **2026-10: not published** (see below) |
| Rows | 32,503 (one per generator per monthly file) |
| Size | 9,766,968 bytes (9.8 MB), UTF-8, `\n` line endings |
| Page | `https://www.eia.gov/electricity/data/eia860m/` (read 2026-10-28) |
| File URL pattern | Archived months: `https://www.eia.gov/electricity/data/eia860m/archive/xls/{month}_generator{year}.xlsx` (month in lower case, e.g. `january_generator2024.xlsx`). The latest month is at `https://www.eia.gov/electricity/data/eia860m/xls/{month}_generator{year}.xlsx` (no `archive/`) |
| Latest month available | **September 2026** (released 2026-10-23; next release 2026-11-24 per the page) |
| Months after the latest | **October 2026 has no file yet.** EIA answers with a web page, not a 404; the script detects that the reply is not an Excel file, logs the month as not published and adds no rows. Nothing is estimated for it |
| Script | `src/data_pull/eia860m.py` (workbooks cached in `data/raw/.cache/eia860m/xlsx/`, not committed) |
| Sheet used | `Operating` (header row found by its first cell `Entity ID`; the title row, blank row and the closing NOTES row are not generators and drop out with the filter). Other sheets: Planned, Retired, Canceled or Postponed, and three Puerto Rico sheets, not used |
| Selection | `Balancing Authority Code` = `CISO` and `Energy Source Code` = `SUN` |
| Output columns | `file_month`, every column of the Operating sheet as text, `source_url` |

- **Column changes over time.** From the 2025-10 file on, the Operating sheet has four more columns (37 instead of 33): `Planned Repower Year`, `Planned Repower Month`, `Other Modification Year`, `Other Modification Month`. In the combined file they are blank for 2024-01 to 2025-09, whose files lack them.
- **The 860M notes say generators at plants under 1 MW are excluded**, which "may represent a significant portion of capacity for ... solar photovoltaic generation."
- **The page says monthly capacities are preliminary estimates** that may be corrected in later monthly files without notice; the final inventory is the annual EIA-860.
- **Technologies under CISO + SUN:** Solar Photovoltaic (prime mover PV) and Solar Thermal without Energy Storage (prime mover ST: Genesis, Ivanpah 1 to 3, Mojave Solar in 2026-09). Both are kept, with the `Technology` column.
- **Status:** the Operating sheet includes out-of-service generators: 32 with status OS in 2024-01 (16.0 MW nameplate), 3 OS and 2 OA in 2026-09. Kept, with the `Status` column.
- **Location:** latitude and longitude present for every CISO solar row in every month (2024-01 to 2026-09). 42 generators (1,946.9 MW nameplate) in 2024-01 and 47 (2,778.4 MW) in 2026-09 are in Arizona and Nevada, outside California.
- **Capacity measures:** `Nameplate Capacity (MW)`, `Net Summer Capacity (MW)`, `Net Winter Capacity (MW)`, `DC Net Capacity (MW)` (blank for 43 to 51 rows, including all solar thermal).
- **California solar under other balancing authorities** (2024-01: LDWP 746.9 MW, IID 406.4, BANC 325.7, PACW 7.5) is not selected.

**Checks (every month, 2024-01 to 2026-09)**

| Check | Result |
|---|---|
| Months with a file | 33 of 33 requested (2026-10 not requested in the final run; tested separately, not published) |
| Rows per month | 890 (2024-07) to 1,069 (2026-09) |
| Duplicate (Plant ID, Generator ID) within a month | 0 in every month |
| Latitude / longitude blank | 0 in every month |
| Nameplate / net summer blank | 0 in every month |
| DC net capacity blank | 43 to 51 rows per month (includes all solar thermal) |

- **Drop of 111 generators in 2024-07.** Rows fall from 994 (2024-06) to 890 (2024-07). 111 California generators of 0.5 to 1.1 MW (56.7 MW nameplate in total, many named "Solar Photovoltaic Project #NN" in San Bernardino County) leave the Operating sheet in the 2024-07 file and do not return. 109 of them are on the 2024-07 Retired sheet with retirement month 2023-12; the other 2 were not found there. Nameplate still rises that month (21,329.2 to 21,493.6 MW) because of new plants.
- **Monthly totals are not always increasing** (for example 2025-02 to 2025-03 and 2025-05 to 2025-06 fall slightly). EIA states that monthly figures are preliminary and corrected without notice; the cause of each change was not checked.

**Monthly CISO solar capacity, nameplate MW (net summer for all solar in the last column).** All solar = every CISO `SUN` row (PV and solar thermal, any status). PV only = `Technology` "Solar Photovoltaic". California only = `Plant State` CA, all solar technologies.

| Month | Generators | All solar | PV only | California only | Outside California (AZ, NV) | All solar, net summer |
|---|---|---|---|---|---|---|
| 2024-01 | 973 | 20,546.9 | 19,532.1 | 18,600.0 | 1,946.9 | 20,300.4 |
| 2024-02 | 977 | 20,602.1 | 19,587.3 | 18,602.7 | 1,999.4 | 20,356.0 |
| 2024-03 | 983 | 20,975.8 | 19,961.0 | 18,976.4 | 1,999.4 | 20,826.1 |
| 2024-04 | 988 | 20,993.8 | 19,979.0 | 18,994.4 | 1,999.4 | 20,843.3 |
| 2024-05 | 991 | 21,123.7 | 20,108.9 | 19,124.3 | 1,999.4 | 20,974.2 |
| 2024-06 | 994 | 21,329.2 | 20,314.4 | 19,329.8 | 1,999.4 | 21,179.7 |
| 2024-07 | 890 | 21,493.6 | 20,478.8 | 19,494.2 | 1,999.4 | 21,344.9 |
| 2024-08 | 897 | 21,507.8 | 20,493.0 | 19,508.4 | 1,999.4 | 21,359.1 |
| 2024-09 | 902 | 21,526.6 | 20,511.8 | 19,527.2 | 1,999.4 | 21,377.9 |
| 2024-10 | 907 | 21,598.8 | 20,676.0 | 19,599.4 | 1,999.4 | 21,454.1 |
| 2024-11 | 920 | 21,797.0 | 20,874.2 | 19,622.6 | 2,174.4 | 21,652.3 |
| 2024-12 | 931 | 22,788.3 | 21,865.5 | 20,313.9 | 2,474.4 | 22,643.6 |
| 2025-01 | 944 | 23,020.0 | 22,097.2 | 20,545.6 | 2,474.4 | 22,874.6 |
| 2025-02 | 951 | 23,485.0 | 22,562.2 | 21,006.6 | 2,478.4 | 23,335.1 |
| 2025-03 | 962 | 23,360.3 | 22,437.5 | 20,885.9 | 2,474.4 | 23,208.3 |
| 2025-04 | 972 | 23,616.6 | 22,693.8 | 21,142.2 | 2,474.4 | 23,464.6 |
| 2025-05 | 978 | 23,730.6 | 22,807.8 | 21,252.2 | 2,478.4 | 23,578.6 |
| 2025-06 | 981 | 23,633.8 | 22,711.0 | 21,155.4 | 2,478.4 | 23,483.5 |
| 2025-07 | 989 | 23,799.2 | 22,876.4 | 21,320.8 | 2,478.4 | 23,649.0 |
| 2025-08 | 996 | 24,164.4 | 23,241.6 | 21,686.0 | 2,478.4 | 24,011.3 |
| 2025-09 | 996 | 24,167.5 | 23,244.7 | 21,689.1 | 2,478.4 | 24,014.6 |
| 2025-10 | 1,004 | 24,184.7 | 23,261.9 | 21,706.3 | 2,478.4 | 24,030.7 |
| 2025-11 | 1,010 | 24,352.0 | 23,429.2 | 21,873.6 | 2,478.4 | 24,198.0 |
| 2025-12 | 1,012 | 24,854.5 | 23,931.7 | 22,376.1 | 2,478.4 | 24,700.5 |
| 2026-01 | 1,016 | 24,865.6 | 23,942.8 | 22,387.2 | 2,478.4 | 24,711.4 |
| 2026-02 | 1,019 | 24,944.9 | 24,022.1 | 22,466.5 | 2,478.4 | 24,759.9 |
| 2026-03 | 1,024 | 24,951.8 | 24,029.0 | 22,473.4 | 2,478.4 | 24,769.6 |
| 2026-04 | 1,028 | 24,964.9 | 24,042.1 | 22,486.5 | 2,478.4 | 24,782.6 |
| 2026-05 | 1,035 | 25,140.2 | 24,217.4 | 22,661.8 | 2,478.4 | 24,957.4 |
| 2026-06 | 1,046 | 25,164.5 | 24,241.7 | 22,686.1 | 2,478.4 | 24,981.7 |
| 2026-07 | 1,056 | 25,809.5 | 24,886.7 | 23,131.1 | 2,678.4 | 25,625.3 |
| 2026-08 | 1,062 | 25,812.8 | 24,890.0 | 23,134.4 | 2,678.4 | 25,631.5 |
| 2026-09 | 1,069 | 26,034.5 | 25,111.7 | 23,256.1 | 2,778.4 | 25,852.2 |
| 2026-10 | not published | | | | | |

**Capacity versus peak, as reported to Raúl on 2026-10-28.** No figure is chosen as correct.

| Figure | MW | Source | Scope |
|---|---|---|---|
| 860M CISO solar, nameplate, 2026-08 | 25,812.8 | EIA 860M August 2026 file (this pull) | Generators with BA code CISO and energy source SUN, PV and solar thermal, any status, CA + AZ + NV; plants under 1 MW excluded by EIA |
| 860M CISO solar, net summer, 2026-08 | 25,631.5 | same | same |
| 860M CISO solar, PV only, nameplate, 2026-08 | 24,890.0 | same | same, PV only |
| 860M CISO solar, California only, nameplate, 2026-08 | 23,134.4 | same | same, `Plant State` CA only |
| CAISO installed solar, as of 2026-08-05 | 23,920 | CAISO Key Statistics, July 2026 (figure as given in CLAUDE.md, not re-checked) | CAISO counts only fully commercial units and changed its method (CLAUDE.md) |
| CAISO solar peak, 2026-08-03 | 23,367 | CAISO Key Statistics, July 2026 (as given in CLAUDE.md) | CAISO's own measurement; interval length not checked |
| CAISO solar peak, August 2026 | 23,896 | CAISO August 2026 Monthly Renewables Performance Report (as given in CLAUDE.md) | same |
| EIA hourly solar peak, August 2026 | 20,852 | EIA hourly file (source 1), label 2026-08-19T19 | Respondent CISO, fuel SUN, hourly |
| CAISO OASIS ACTUAL solar peak, August 2026 | 19,616 | OASIS ACTUAL file (source 2), interval starting 2026-08-03 19:00 UTC | Sum of NP15, SP15, ZP26 solar, hourly |

Differences (August 2026): 860M nameplate minus CAISO installed = +1,892.8 MW; 860M net summer minus CAISO installed = +1,711.5 MW; 860M California only minus CAISO installed = -785.6 MW. CAISO peaks minus EIA hourly peak = +2,515 MW (23,367) and +3,044 MW (23,896); minus OASIS ACTUAL peak = +3,751 MW and +4,280 MW. EIA hourly peak / 860M nameplate = 0.81.

January 2024 for reference: 860M all solar nameplate 20,546.9 MW, net summer 20,300.4 MW; EIA hourly peak 12,576 MW (label 2024-01-29T23); OASIS ACTUAL three-hub peak 11,867 MW (interval starting 2024-01-29 21:00 UTC).

Possible explanations, **all unverified**: CAISO's installed figure may count only fully commercial units while 860M lists every operating generator, including partly built hybrids; CAISO's peaks may be shorter intervals (for example 5-minute) than the hourly EIA and OASIS values; CAISO's peak may include output that is not in the three OASIS hubs or in EIA's CISO series; and 860M lists nameplate, which a plant may not reach at the grid connection. None of these has been checked against CAISO or EIA documentation.

**One-off comparison with July 2019 (log only; not in the data file).** File `https://www.eia.gov/electricity/data/eia860m/archive/xls/july_generator2019.xlsx` (downloaded 2026-10-28; its column order differs from the 2024 to 2026 files and it has no DC capacity column).

| July 2019 860M, CISO solar | Generators | Nameplate MW | Net summer MW |
|---|---|---|---|
| All solar (PV + solar thermal) | 731 | 12,325.8 | 12,211.7 |
| PV only | 716 | 11,031.9 | 10,927.7 |
| Solar thermal | 15 | 1,293.9 | 1,284.0 |
| California only | 705 | 11,172.5 | 11,058.4 |
| PV, California only | 690 | 9,878.6 | 9,774.4 |
| CAISO installed solar, July 2019 (CAISO Monthly Stats, June 2019, as given in CLAUDE.md) | | 12,049 | |

Differences: all-solar nameplate +276.8 MW, net summer +162.7 MW, California only -876.5 MW, PV only -1,017.1 MW against 12,049. 21 generators in Nevada and 5 in Arizona.

**Capacity coverage of the weather points (2026-10-28).** Plants are the CISO solar generators grouped by `Plant ID`, weighted by nameplate, including Arizona and Nevada. Distance is great-circle distance from each plant to the nearest weather point.

Grid only (41 points):

| Month | Scope | Nameplate MW | Within 25 km | Within 50 km | Within 100 km | Farthest plant (km) |
|---|---|---|---|---|---|---|
| 2024-01 | California only | 18,600.0 | 12.8% | 61.2% | 99.9% | 111.6 |
| 2024-01 | All CISO | 20,546.9 | 12.8% | 56.6% | 93.7% | 203.3 |
| 2026-09 | California only | 23,256.1 | 14.0% | 59.7% | 99.9% | 111.6 |
| 2026-09 | All CISO | 26,034.5 | 13.5% | 54.4% | 91.8% | 203.3 |

The grid alone is well under the brief's 95% within 50 km. Six cluster points at the centres of the six largest clusters (plants grouped so that none is more than 100 km from another) reached only 84.0% to 87.8% within 50 km. **Raúl approved 10 cluster points ("option B", 2026-10-28)**, more than the brief's 6. They were chosen one at a time, each at the location that brought the most still-uncovered nameplate within 50 km of a weather point, until all CISO reached 95% within 50 km in both 2024-01 and 2026-09. They are in `weather_locations.csv` with `type` = `cluster` and are defined in `CLUSTER_POINTS` in `src/data_pull/weather_locations.py`.

| ID | Latitude | Longitude | Area | Capacity share |
|---|---|---|---|---|
| c01 | 35.00 | -118.04 | Kern, Los Angeles CA (Antelope Valley, Mojave) | 13.59% |
| c02 | 33.66 | -114.74 | Riverside CA (Blythe, Desert Center) | 7.60% |
| c03 | 32.77 | -115.78 | Imperial, San Diego CA (Imperial Valley) | 6.62% |
| c04 | 34.96 | -117.13 | San Bernardino CA (Daggett, Hinkley) | 5.87% |
| c05 | 36.07 | -119.56 | Kings, Tulare CA | 8.77% |
| c06 | 32.97 | -113.49 | Yuma AZ | 5.10% |
| c07 | 33.34 | -112.88 | Maricopa AZ | 3.01% |
| c08 | 35.46 | -119.19 | Kern, Tulare CA (southern San Joaquin) | 4.74% |
| c09 | 37.36 | -120.72 | Merced, Stanislaus CA | 1.70% |
| c10 | 35.78 | -114.97 | Clark NV, San Bernardino CA | 1.17% |

**`caiso_solar_capacity_share` is static.** For every one of the 51 points it is the share of CISO solar nameplate in the 860M file for **2026-09** (all CISO, including Arizona and Nevada; PV and solar thermal; any status) whose nearest weather point is that point. It is not updated month by month. Cluster points together hold 58.16%, grid points 41.84% (29 of the 41 grid points have a share above zero); the 51 shares add up to 1.

Final coverage, 51 points (41 grid + 10 cluster):

| Month | Scope | Nameplate MW | Within 25 km | Within 50 km | Within 100 km | Farthest plant (km) |
|---|---|---|---|---|---|---|
| 2024-01 | California only | 18,600.0 | 39.2% | 97.4% | 100.0% | 111.6 |
| 2024-01 | All CISO | 20,546.9 | 44.4% | 97.2% | 100.0% | 111.6 |
| 2026-09 | California only | 23,256.1 | 40.1% | 97.0% | 99.9% | 111.6 |
| 2026-09 | All CISO | 26,034.5 | 44.9% | 95.8% | 100.0% | 111.6 |

Largest plants still more than 50 km from a point (2026-09; 4.2% of nameplate in total): ATLAS Solar V and VI (La Paz AZ, 300 MW, about 68 km), Pastoria Solar (Kern CA, 105 MW, 61 km), Sunshine Valley Solar (Nye NV, 104 MW, 90 km).

**Open item: San Diego plants more than 100 km from any weather point** (no 11th point added, Raúl's decision 2026-10-28):

| Plant ID | Plant | County | Nameplate MW | Distance (km) | Nearest point | In 2024-01 | In 2026-09 |
|---|---|---|---|---|---|---|---|
| 61843 | SeaWorld Aquatica | San Diego | 1.1 | 111.6 | g39 | yes | yes |
| 62242 | County of San Diego SBRC | San Diego | 1.3 | 104.2 | g39 | yes | yes |
| 64028 | San Diego - EMDF at San Diego | San Diego | 2.9 | 108.5 | g40 | yes | yes |
| 67170 | Amazon SAN3 Solar Project | San Diego | 4.6 | 110.3 | c03 | no | yes |
| 69730 | Amazon - SAN5 | San Diego | 2.9 | 109.5 | c03 | no | yes |

Total 5.3 MW (3 plants) in 2024-01 and 12.8 MW (5 plants) in 2026-09, about 0.05% of CISO solar nameplate.

**Model grid cells (checked 2026-10-28).** Each location was requested once from Open-Meteo (`ecmwf_ifs025`); the 41 grid points from the April 2024 test responses, the 10 cluster points with a one-day request. All 51 locations map to **51 distinct model grid cells**; no two share a cell. The closest two cells are those of g28 and c08, 22.6 km apart. Cluster points are 3.5 to 15.0 km from their cells.

## 5. Curtailment

| Item | Value |
|---|---|
| Files | `caiso_curtailment_2024-01-01_2025-12-31.csv.gz` (workbooks) and `caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz` (Daily Renewable Report pages) |
| Name change | **Both files end in `.csv.gz`, not `.csv`** as in the brief's pattern `caiso_curtailment_<first>_<last>.csv` (Raúl's decision, 2026-10-28). Two files instead of one, because the granularity and categories differ (Raúl's decision) |
| Date pulled | 2026-10-28 |
| Script | `src/data_pull/caiso_curtailment.py` (workbooks cached in `data/raw/.cache/curtailment/xlsx/`, pages in `data/raw/.cache/curtailment/html/`, per-day parse status in `data/raw/.cache/curtailment/report_status.csv`) |
| Workbook file | 111,289 rows: 51,857 from the 2024 workbook, 59,432 from the 2025 bulk workbook. Columns `Date`, `Hour`, `Interval`, `Wind Curtailment`, `Solar Curtailment`, `Reason` exactly as stored, plus `source_file`. The 2025 file's empty column G and its note column `CAISO Public` (one note in one row, quoted below) are not data and are not copied. 1,558,369 bytes |
| Report file | 24,144 rows (503 days x 24 hours x 2 fuels). Columns `operating_date`, `hour` (position 1 to 24 in the page arrays), `fuel` (solar, wind), then for each category `econ_local`, `econ_system`, `ss_local`, `ss_system`, `oi_local`, `oi_system` the hourly MWh (`<category>_mwh`) and hourly maximum MW (`<category>_max_mw`) as text exactly as in the page, then `source_url`. 287,922 bytes |
| Pages | 504 requested (2025-06-01 to 2026-10-17), at least 2 seconds apart; 503 parsed; **1 missing: 2025-11-05** (HTTP 404 on two requests, while 2025-11-04 and 2025-11-06 exist). 0.2% of pages, under Raúl's 2% stop line. No HTTP 403 or 429 |

**Sources by period**

| Period | Source | URL | What it holds |
|---|---|---|---|
| 2024-01-01 to 2024-12-31 | Production and Curtailments Data 2024 | `https://www.caiso.com/documents/production-and-curtailments-data-2024.xlsx` (22,596,818 bytes, posted 2025-01-22) | Sheets `Read_me`, `Production`, `Curtailments`. Curtailments: 51,857 rows, columns `Date`, `Hour`, `Interval`, `Wind Curtailment`, `Solar Curtailment`, `Reason` (Local or System); 5-minute MW; only intervals with curtailment are listed; rows on all 366 dates |
| 2025-01-01 to 2025-05-31 | Production and Curtailments Data 2025 | `https://www.caiso.com/documents/production-and-curtailments-data-2025.xlsx` (21,271,763 bytes, posted 2026-01-07) | Same layout. Curtailments sheet ends on 2025-05-31 (25,848 rows) |
| 2025-01-01 to 2025-12-31 | "Production and Curtailments Data - June-December 2025" | `https://www.caiso.com/documents/production-and-curtailments-data-june-december-2025.xlsx` (2,543,639 bytes, posted 2026-02-13) | One sheet, `Curtailments`, same columns. Despite the title it covers all of 2025 (59,432 rows, 2025-01-01 to 2025-12-31). Note in the file: "We are publishing this as a one time bulk upload. Please refer to the Daily Renewable Report in the future for 5 minute curtailment data." Its January to May 2025 rows are identical to the 2025 file above (25,848 rows, solar difference 0.000) |
| 2025-06-01 onward | Daily Renewable Report, one HTML page per operating day | `https://www.caiso.com/documents/daily-renewable-report-{mon}-{dd}-{yyyy}.html` (e.g. `jun-02-2026`) | Curtailment tab built from data arrays in the page script: hourly MWh by fuel (solar, wind) and six categories (Economic, Self Schedule Cut, Operator Instruction; each Local or System); hourly maximum MW; in later pages also 5-minute values (all VER, not split by fuel). First page found: 2025-06-01 (2025-05-31 and earlier: HTTP 404). Pages exist through at least 2026-10-26 |

The production and curtailments page (`https://www.caiso.com/library/production-curtailments-data`, read 2026-10-28) says: "As of 6/1/2025 the ISO is no longer publishing this report" and "There is no longer a comprehensive production data report available", pointing to the daily renewables reports and Today's Outlook. The daily "Wind and Solar Curtailment" PDF (`wind-solar-real-time-dispatch-curtailment-report-{mon}-{dd}-{yyyy}.pdf`) exists for 2025-05-26 but returns 404 for the 2026 dates tried; not needed.

**Test findings**

- Definition (daily curtailment PDF, 2025-05-26): "Curtailment is defined as the difference between actual production and the forecast when actual production is less than the forecast"; amounts under 1 MW are filtered out. The workbooks' `Read_me`: 5-minute MW, "only intervals in which a curtailment was observed are listed", raw data "not considered operational or settlement quality data".
- `Date` in the workbooks carries an inconsistent time of day by month: 08:00 or 07:00 in 2024; 08:00 (January), 07:00 (March, April) and 00:00 (other months) in the 2025 bulk file. Read as an export artifact (unverified); the calendar date with `Hour` (1 to 24) and `Interval` (1 to 12) identifies the interval.
- 2025-06-16 has no rows in the 2025 bulk file; see the overlap check below (it is missing data, not a day without curtailment).
- Daily Renewable Report vs 2025 bulk file, 2025-07-15: hourly solar curtailment matches hour by hour with no shift (2,864.0 vs 2,863.4 MWh for the day; total absolute difference 0.7 MWh); wind 65.2 vs 65.2 MWh. The HTML's 24 values follow the same `Hour` 1 to 24 as the workbook (solar curtailed in hours 7 to 20 on a July day, consistent with Pacific hour ending). The chart code starts the axis at `Date.UTC(yyyy, m, d)`; reading it as a charting convention, not UTC data, is unverified.
- The HTML format changes over time: arrays are plain lists in some pages (2025-07-15, 2026-06-02) and `JSON.parse([...])` strings in others (2025-10-01); 5-minute arrays are absent in the 2025-07-15 page.

**Full-pull checks**

| Check | Workbook file | Report file |
|---|---|---|
| Rows | 111,289 | 24,144 |
| Days covered | 2024-01-01 to 2025-12-31; rows on 730 of 731 days | 503 of 504 days (2025-06-01 to 2026-10-17) |
| Days without data | **2025-06-16** (no rows; the only such day in 2024 and 2025) | **2025-11-05** (page not published) |
| Values per array | not applicable (5-minute rows) | **24 in every one of the 24 arrays on all 503 days**, including the DST days 2025-11-02 and 2026-03-08. No day failed this check |
| Page date check | not applicable | The date in each page's chart code equals the requested day on all 503 days |
| Page formats | not applicable | Solar arrays as `JSON.parse` strings on 153 days (from 2025-07-17), as plain lists on 350 days, mixed through 2026-10-17; both parsed |
| `Hour` values | 1 to 24; never 25 | positions 1 to 24 |
| Size | 1,558,369 bytes (gzip) | 287,922 bytes (gzip) |

**Overlap check, 2025-06-01 to 2025-12-31 (214 days).** Workbook 5-minute MW converted to hourly MWh as the sum of the listed intervals divided by 12 (intervals not listed count as 0). Report hourly MWh is the sum of the six categories. Compared hour by hour for each day.

| | Solar | Wind |
|---|---|---|
| Total, workbook / report (MWh) | 961,000.4 / 966,399.0 | 62,956.9 / 64,052.6 |
| Correlation of hourly values, no shift | 0.998376 | 0.993683 |
| Correlation with the workbook shifted by -1 / +1 hour | 0.878049 / 0.878052 | 0.819157 / 0.818536 |
| Days whose hourly differences add up to at most 1 MWh | 202 of 214 | 210 of 214 |
| Days within 1 MWh or 1% of the day's curtailment | 213 of 214 | 211 of 214 |
| Largest single-hour difference, apart from the days below | 0.5 MWh | 0.4 MWh |

- **2025-06-16: the workbook has no rows, but the report shows 5,396.9 MWh of solar and 1,094.3 MWh of wind curtailment** (largest hour 1,231.0 MWh solar). So a day without rows in the workbook is missing data, not a day without curtailment. This one day accounts for 5,396.9 of the 5,398.6 MWh difference in solar totals.
- **2025-11-05: the report page is missing**, while the workbook has curtailment that day.
- On every other overlap day the two sources agree to within 3.3 MWh a day for solar.

**Hour reading: Pacific hour ending.** In both files `Hour` 1 to 24 is read as the Pacific operating hour ending (hour 15 = 14:00 to 15:00 Pacific). Evidence: solar curtailment sits in hours 7 to 19 (99.9% of solar MWh in both files; workbook 2024 to 2025: hours 8 to 19 above 0.1%, peak hour 15; report: hours 7 to 19, peak hour 15) and is 0.000% in hours 1 to 5 and 22 to 24. That fits Pacific midday and afternoon, not UTC (in UTC the same sunlight would fall around hours 15 to 24 and 0 to 2). The workbook and report agree hour for hour with no shift (above). CAISO's documentation of this convention for these two products was not found; the reading is inferred from the data.

**Daylight saving days (23 and 25 hours).** Spring-forward days have 23 Pacific hours (2024-03-10, 2025-03-09, 2026-03-08) and fall-back days have 25 (2024-11-03, 2025-11-02). The workbook never uses `Hour` 25; on these four days in 2024 and 2025 its rows are only in hours 7 to 18 (curtailment is daytime), so no curtailed interval falls on the repeated or skipped hour. The report always has 24 values, also on 2025-11-02 (25 hours) and 2026-03-08 (23 hours); how CAISO maps 24 positions onto those days was not determined. Treat hours on those two report days with care in processing.

**Note in the 2025 bulk workbook (column `CAISO Public`, row 2):** "Note: We are publishing this as a one time bulk upload. Please refer to the Daily Renewable Report in the future for 5 minute curtailment data."

## Final check table (all files, 2026-10-28)

| File | Rows | First / last | Missing | Duplicates | Nulls in main values | Size (bytes) |
|---|---|---|---|---|---|---|
| `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv` | 24,480 | 2024-01-01T00 / 2026-10-17T23 (UTC) | 24 hours (2024-11-02 Pacific day; 0.10%) | 0 | 0 | 2,122,906 |
| `caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz` | 146,706 | 2023-12-31 08:00 / 2026-10-18 06:00 (UTC interval start) | 3 operating days (day before each spring DST change; 0.29% per solar hub) | 0 per hub and type | 0 | 1,300,951 |
| `caiso_actual_solar_2024-01-01_2026-10-17.csv.gz` | 146,210 | 2023-12-31 08:00 / 2026-10-18 06:00 (UTC interval start) | 2 hours per solar hub (0.01%) | 0 per hub and type | 0 | 1,715,474 |
| `eia860m_solar_ciso_capacity_by_month.csv` | 32,503 | 2024-01 / 2026-09 (`file_month`) | 2026-10 not published | 0 per month | 0 (nameplate, net summer, latitude, longitude) | 9,766,968 |
| `weather_locations.csv` | 51 | (41 grid, 10 cluster) | none | 0 | 0 | 1,577 |
| `reference/california_boundary_ne10m.geojson` | 1 feature | | | | | 44,555 |
| `openmeteo/` (51 files) | 22,896 each | 2024-03-08T00:00 / 2026-10-17T23:00 (UTC) | 0 hours | 0 | 129 hours in 2 of 18 columns (archive gap, 2026-04-17 to 2026-04-22) | 29,276,060 in total |
| `caiso_curtailment_2024-01-01_2025-12-31.csv.gz` | 111,289 | 2024-01-01 / 2025-12-31 (Pacific date) | 1 day without rows (2025-06-16, missing data) | 0 | not applicable (only curtailed intervals listed) | 1,558,369 |
| `caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz` | 24,144 | 2025-06-01 / 2026-10-17 (Pacific operating date) | 1 day (2025-11-05, page not published) | 0 | 0 | 287,922 |

All files are UTF-8 with `\n` line endings. No single file is above 50 MB (largest: 9.8 MB). The 860M Excel workbooks (about 400 MB), Open-Meteo responses, OASIS and EIA monthly pieces, curtailment workbooks and HTML pages stay in `data/raw/.cache/` (not committed).

## Reproducibility test (2026-10-28)

`src/data_pull/run_all.py` was run for one month, 2025-07-01 to 2025-07-31, with `DATA_RAW_DIR` pointing to a new empty folder (outside the repo), so every source was downloaded again from scratch. It finished without errors (one expected warning: no 860M rows for 2026-09, so capacity shares were left blank in that test's `weather_locations.csv`). Its output was compared with the main files for the same period:

| Source | Rows compared | Identical |
|---|---|---|
| EIA hourly | 744 | yes, all columns |
| OASIS DAM | 4,608 | yes, all columns except `GROUP` (request-dependent counter, see source 2) |
| OASIS ACTUAL | 4,608 | yes, all columns except `GROUP` |
| EIA 860M (2025-07) | 989 | yes, all columns |
| Weather locations | 51 | yes (IDs, coordinates, type) |
| Open-Meteo (51 files, July 2025) | 744 each | yes, all 51 files (after the rebuild described in source 3) |
| Curtailment workbook (2025) | 59,432 | yes, all columns |
| Curtailment daily report (July 2025) | 1,488 | yes, all columns |

The first attempt of this test stopped at once on a missing import in `src/data_pull/weather_locations.py` (fixed); it downloaded nothing.

## Still open after this pull

- EIA timing offset (source 1): recommended rule EIA label L = hour ending at L minus 1 hour; not applied in raw files.
- San Diego plants more than 100 km from a weather point (source 4, coverage): 5 plants, 12.8 MW.
- What the `AVA_` hub in DAM represents (source 2).
- CAISO capacity and peak figures versus 860M and the hourly peaks (source 4): no figure chosen.
- Positive EIA values at deep night in 2024 (source 1), to recheck once the timing rule is applied.
- How CAISO maps 24 report positions onto the 23-hour and 25-hour days (source 5).

## Pandas-by-URL test (2026-10-29)

After commit `c75bdbe` was pushed to branch `raul/data-pulls`, one file from each source was read with `pandas.read_csv` from the branch URL `https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/raul/data-pulls/data/raw/<file>`.

| Source | File | Rows read by URL | Rows in this log | Match |
|---|---|---|---|---|
| 1. EIA hourly | `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv` | 24,480 | 24,480 | yes |
| 2. OASIS DAM | `caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz` | 146,706 | 146,706 | yes |
| 2. OASIS ACTUAL | `caiso_actual_solar_2024-01-01_2026-10-17.csv.gz` | 146,210 | 146,210 | yes |
| 3. Open-Meteo (g24) | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g24_2024-03-08_2026-10-17.csv.gz` | 22,896 | 22,896 | yes |
| 3. Weather locations | `weather_locations.csv` | 51 | 51 | yes |
| 4. EIA 860M | `eia860m_solar_ciso_capacity_by_month.csv` | 32,503 | 32,503 | yes |
| 5. Curtailment workbooks | `caiso_curtailment_2024-01-01_2025-12-31.csv.gz` | 111,289 | 111,289 | yes |
| 5. Curtailment daily reports | `caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz` | 24,144 | 24,144 | yes (fourth read) |

The daily-report file needed retries: its first three reads failed with a connection reset (`WinError 10054`) during the secure-connection handshake, before any data arrived, and the fourth read succeeded (in a retry loop with 30 seconds between tries, it was that loop's second try). In the same minutes, Python reads of other files from the branch were reset too, while the Windows web client downloaded this file without error (HTTP 200, 287,922 bytes) and `git ls-tree` showed it in the pushed branch at that size. The cause was not determined; Norton's HTTPS scanning on the pull machine is one possibility (unverified).
