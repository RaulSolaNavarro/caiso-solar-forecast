# Data dictionary

One section per file in `data/raw/`. For each file: what one row is (the grain), the key, size, period, time zone and units, then every column. Last reviewed: 2026-10-29. Questions about why we use a file or what is wrong with it are in `docs/DATA_FAQ.md`.

## How to read this

**Type** is the language-neutral type of the value in the file: *text*, *integer*, *decimal*, *date text* (a date written as text), *timestamp text* (a time written as text). In pandas 3, text columns show as `str`; in pandas 2 and older they show as `object`. Convert timestamps as shown in `docs/DATA_HOWTO.md`.

**Basis** says where the description comes from:

| Code | Meaning |
|---|---|
| **Doc** | The provider's documentation (link in the section header). |
| **Pull** | Observed in the data pull or its checks (`data/raw/PULL_LOG.md`). |
| **Profile** | Measured on the committed file on 2026-10-29 while writing this dictionary. |
| **Inferred** | Our reading from the column name and values. Treat as a working assumption. |

Counts of nulls are for the file as committed. A count of 0 does not mean the file is complete: in most files, gaps are absent rows (see the FAQ, section 6).

## Files at a glance

| # | File | Grain (one row is) | Rows | Columns | Size on disk | Size uncompressed | Time reference |
|---|---|---|---|---|---|---|---|
| 1 | `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv` | one hour | 24,480 | 7 | 2,122,906 B | same | UTC label |
| 2 | `caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz` | one hub, one fuel, one hour | 146,706 | 14 | 1,300,951 B | 20.7 MB | UTC interval start and end |
| 3 | `caiso_actual_solar_2024-01-01_2026-10-17.csv.gz` | one hub, one fuel, one hour | 146,210 | 14 | 1,715,474 B | 22.9 MB | UTC interval start and end |
| 4 | `weather_locations.csv` | one weather point | 51 | 5 | 1,577 B | same | not applicable |
| 5 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_<location_id>_2024-03-08_2026-10-17.csv.gz` (51 files) | one hour at one point | 22,896 each | 26 | 558,175 to 594,130 B each | about 3.2 MB each | UTC |
| 6 | `eia860m_solar_ciso_capacity_by_month.csv` | one generator in one monthly file | 32,503 | 39 | 9,766,968 B | same | month of file |
| 7 | `caiso_curtailment_2024-01-01_2025-12-31.csv.gz` | one 5-minute interval with curtailment | 111,289 | 7 | 1,558,369 B | 15.0 MB | Pacific date and hour |
| 8 | `caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz` | one fuel, one hour, one day | 24,144 | 16 | 287,922 B | 3.1 MB | Pacific date and hour |
| 9 | `reference/california_boundary_ne10m.geojson` | one map feature (California) | 1 | not applicable | 44,555 B | same | not applicable |

Rough memory use when loaded in pandas 3 (measured 2026-10-29): EIA 9 MB, OASIS DAM 82 MB, OASIS ACTUAL 83 MB, 860M 55 MB, curtailment workbooks 32 MB, daily report 8 MB, one weather file 8 MB (all 51 about 420 MB). Use `usecols` and `float32` when you load many files.

All files are UTF-8 with `\n` line endings. Raw files are exactly as the source returned them; the pull added only the columns marked "added by pull".

---

## 1. EIA hourly solar generation

`eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv`

| Item | Value |
|---|---|
| Source | EIA Hourly Electric Grid Monitor, API v2: `https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/` (frequency hourly, respondent `CISO`, fuel `SUN`). https://www.eia.gov/electricity/930-content/about.html |
| Grain | One row per hour. |
| Key | `period` (unique, 24,480 values). |
| Period | 2024-01-01T00 to 2026-10-17T23, UTC label. |
| Expected rows | 24,504. Missing 24 (the Pacific day 2024-11-02). |
| Units | Megawatt-hours per hour, which equals average megawatts for that hour. |
| Pulled | 2026-10-27. |
| Timing warning | The label is about one hour later than the hour CAISO reports. Recommended rule: label L is the hour ending at L minus 1 hour (UTC). See FAQ Q6.1. |

| Column | Type | Meaning | Values and range | Nulls | Basis |
|---|---|---|---|---|---|
| `period` | timestamp text `YYYY-MM-DDTHH`, no time zone suffix | Hour label, in UTC. | 2024-01-01T00 to 2026-10-17T23 | 0 | Pull (route metadata "hourly (UTC)") |
| `respondent` | text | Balancing authority code. | always `CISO` | 0 | Doc |
| `respondent-name` | text | Balancing authority name. | always "California Independent System Operator" | 0 | Pull |
| `fueltype` | text | Energy source code. | always `SUN` | 0 | Doc |
| `type-name` | text | Energy source name. | always "Solar" | 0 | Pull |
| `value` | integer | Net solar generation in the hour: metered output of the units the balancing authority manages or can see. Rooftop solar is typically not included. | -74 to 20,852; median 559.5; 9,461 negative; 41 exactly zero | 0 | Doc (EIA-930 about page); ranges from Profile |
| `value-units` | text | Unit of `value`. | always "megawatthours" | 0 | Pull |

Notes: negative values occur at night (Q6.3). 255 deep-night hours show 100 to 413 MW (Q6.4). `value` is stored as a whole number.

---

## 2 and 3. CAISO OASIS day-ahead forecast and actual

`caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz` (market run DAM) and `caiso_actual_solar_2024-01-01_2026-10-17.csv.gz` (market run ACTUAL). Same 14 columns.

| Item | DAM | ACTUAL |
|---|---|---|
| Source | CAISO OASIS `SingleZip`, query `SLD_REN_FCST`, `market_run_id=DAM`, version 1. OASIS Interface Specification v5.1.2 (https://www.caiso.com/Documents/OASIS-InterfaceSpecification_v5_1_2Clean_Fall2017Release.pdf) | same, `market_run_id=ACTUAL` |
| Grain | One row per trading hub, fuel type and hour. | same |
| Key | `INTERVALSTARTTIME_GMT` + `TRADING_HUB` + `RENEWABLE_TYPE` (no duplicates) | same |
| Rows | 146,706 | 146,210 |
| First / last interval start (UTC) | 2023-12-31 08:00 / 2026-10-18 06:00 | same |
| Forecast timing | Day-ahead forecasts are posted daily before the Day-Ahead Market (Doc). | Actual production is posted the day after the operating day (Doc). |
| Units | MW per hour (average over the hour) | MW per hour |
| Pulled | 2026-10-27 (checked again 2026-10-28) | 2026-10-28 (re-pulled) |

| Column | Type | Meaning | Values and range | Nulls | Basis |
|---|---|---|---|---|---|
| `OPR_DT` | date text `YYYY-MM-DD` | Pacific operating date. | 2023-12-31 to 2026-10-17 | 0 | Pull; checked against UTC columns 2026-10-29 |
| `OPR_HR` | integer | Pacific clock hour ending in the operating day. 1 to 24; 25 only on the fall-back days (2024-11-03, 2025-11-02). On the five clock-change days it counts clock hours, not elapsed hours, so do not rebuild time from it. | 1 to 25 | 0 | Pull; Profile |
| `OPR_INTERVAL` | integer | Interval within the hour. Always 0 (hourly data). | 0 | 0 | Profile |
| `INTERVALSTARTTIME_GMT` | timestamp text `YYYY-MM-DDTHH:MM:SS-00:00` | Start of the hour, UTC. | 2023-12-31T08:00 to 2026-10-18T06:00 | 0 | Pull |
| `INTERVALENDTIME_GMT` | timestamp text, same format | End of the hour, UTC (start plus 1 hour). | | 0 | Pull |
| `TRADING_HUB` | text | CAISO trading hub the row belongs to. | `NP15`, `SP15`, `ZP26` in both files; `AVA_` in DAM only (from 2026-09-10 07:00 UTC, solar only, meaning unknown) | 0 | Doc for NP15, SP15, ZP26 (the spec also lists `ALL`, which is not in our files); Pull for `AVA_` |
| `RENEWABLE_TYPE` | text | Fuel type. The spec says Solar includes Solar PIRP and EIR resources. | `Solar`, `Wind` | 0 | Doc |
| `LABEL` | text | Series label. | DAM: "Renewable Forecast Day Ahead". ACTUAL: "Renewable Forecast Actual Generation" | 0 | Pull |
| `XML_DATA_ITEM` | text | OASIS data item name. | DAM: `RENEW_FCST_DA_MW`. ACTUAL: `RENEW_FCST_ACT_MW` | 0 | Doc (item names listed in the spec) |
| `MARKET_RUN_ID_POS` | integer | Position code of the market run in the response. | DAM 1, ACTUAL 3 | 0 | Profile; meaning Inferred |
| `RENEW_POS` | integer | Position code of the fuel type in the response. | DAM: Wind 1, Solar 2. ACTUAL: Wind 1, Solar 3 | 0 | Profile; meaning Inferred |
| `MW` | decimal | Forecast (DAM) or actual (ACTUAL) generation for the hub, fuel and hour, in MW. | DAM solar: 0 to 14,948.7 (SP15). ACTUAL solar: -307.9 to 14,570.0 (SP15) | 0 | Doc (data item names, MW); ranges from Profile |
| `MARKET_RUN_ID` | text | Market run. | `DAM` or `ACTUAL` | 0 | Pull |
| `GROUP` | integer | Counter OASIS assigns to blocks of rows in each response. Depends on the request, not the data. Not a key. | DAM 1 to 201; ACTUAL 6 to 102 | 0 | Pull |

### Rows per hub and fuel (within the file)

| Hub | Fuel | DAM rows | ACTUAL rows | Note |
|---|---|---|---|---|
| NP15 | Solar | 24,455 | 24,525 | |
| SP15 | Solar | 24,455 | 24,525 | |
| ZP26 | Solar | 24,455 | 24,525 | |
| NP15 | Wind | 24,455 | 24,524 | |
| SP15 | Wind | 24,455 | 24,524 | |
| ZP26 | Wind | 23,519 | 23,587 | Starts 2024-02-08 08:00 UTC |
| AVA_ | Solar | 912 | none | DAM only, from 2026-09-10 07:00 UTC |

Solar `MW` by hub (Profile, 2026-10-29):

| Hub | DAM mean | DAM max | ACTUAL mean | ACTUAL max | ACTUAL min |
|---|---|---|---|---|---|
| NP15 | 784.3 | 2,897.6 | 635.7 | 2,615.1 | -307.9 |
| SP15 | 4,473.9 | 14,948.7 | 4,046.8 | 14,570.0 | -99.6 |
| ZP26 | 880.7 | 3,082.8 | 757.2 | 2,966.9 | -33.3 |
| AVA_ | 5.2 | 18.3 | none | none | none |

Notes: DAM solar is exactly zero at night; ACTUAL solar is slightly negative at night. DAM is missing three whole Pacific days (2024-03-09, 2025-03-08, 2026-03-07). Some rows fall outside the UTC project range because whole Pacific days are kept.

---

## 4. Weather locations

`weather_locations.csv`. Built by `src/data_pull/weather_locations.py`.

| Item | Value |
|---|---|
| Grain | One row per weather point. |
| Key | `location_id` (unique). |
| Rows | 51: 41 grid points (`g01` to `g41`) and 10 cluster points (`c01` to `c10`). |
| Grid | Centers of 1 degree cells (latitudes 32.5 to 41.5, longitudes -124.5 to -114.5) that fall inside California, using the California feature of Natural Earth 1:10m Admin 1 v5.1.2 (`reference/california_boundary_ne10m.geojson`). |
| Cluster points | Chosen one at a time to bring the most still-uncovered CISO solar nameplate within 50 km of a point, until 95% was reached. |

| Column | Type | Meaning | Values and range | Nulls | Basis |
|---|---|---|---|---|---|
| `location_id` | text | Point ID. `g` = grid, `c` = cluster. | `g01` to `g41`, `c01` to `c10` | 0 | Pull |
| `latitude` | decimal | Requested latitude, degrees north. | 32.77 to 41.5 | 0 | Pull |
| `longitude` | decimal | Requested longitude, degrees east (negative is west). | -123.5 to -112.88 | 0 | Pull |
| `type` | text | Point type. | `grid` (41), `cluster` (10) | 0 | Pull |
| `caiso_solar_capacity_share` | decimal | Share of CISO solar nameplate (EIA 860M 2026-09 file, all CISO including Arizona and Nevada, PV and solar thermal, any status) whose nearest weather point is this one. Static: not updated by month. The 51 shares add to 1. | 0 to 0.1359 (c01); 12 grid points are 0; cluster points hold 58.16% in total | 0 | Pull |

Cluster points:

| ID | Latitude | Longitude | Area | Share |
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

---

## 5. Open-Meteo previous-runs weather forecasts

51 files, one per location: `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_<location_id>_2024-03-08_2026-10-17.csv.gz`.

| Item | Value |
|---|---|
| Source | Open-Meteo Previous Runs API, `https://previous-runs-api.open-meteo.com/v1/forecast`, model `ecmwf_ifs025`, `timezone=UTC`. https://open-meteo.com/en/docs/previous-runs-api |
| License | CC BY 4.0. Credit "Weather data by Open-Meteo.com". Free tier is non-commercial. |
| Grain | One row per hour at one location (one location per file). |
| Key | `time_utc` within a file; `location_id` + `time_utc` across files. |
| Rows | 22,896 per file (954 days x 24 hours), no missing hours, no duplicates. |
| Period | 2024-03-08T00:00 to 2026-10-17T23:00 UTC. |
| Pulled | 2026-10-28 (612 requests: 51 locations x 12 quarters). |
| Forecast offsets | `_previous_day1`: the value predicted 24 hours before the valid time. `_previous_day2`: 48 hours before. (Doc) |
| Radiation timing | Radiation variables are the mean of the preceding hour, so `time_utc` is the end of the hour. Temperature, humidity, wind and cloud cover are values at `time_utc`. Precipitation is the sum of the preceding hour. (Doc: https://open-meteo.com/en/docs) |

Identification columns (8):

| Column | Type | Meaning | Values and range | Nulls | Basis |
|---|---|---|---|---|---|
| `time_utc` | timestamp text `YYYY-MM-DDTHH:MM` | Valid time of the forecast, UTC. | 2024-03-08T00:00 to 2026-10-17T23:00 | 0 | Pull |
| `location_id` | text | Point ID, as in `weather_locations.csv`. | one value per file | 0 | Pull |
| `latitude` | decimal | Requested latitude. | constant per file | 0 | Pull |
| `longitude` | decimal | Requested longitude. | constant per file | 0 | Pull |
| `model` | text | Weather model. | always `ecmwf_ifs025` | 0 | Pull |
| `model_latitude` | decimal | Latitude of the model grid cell the API used, as returned. | constant per file | 0 | Pull |
| `model_longitude` | decimal | Longitude of that cell. | constant per file | 0 | Pull |
| `model_elevation` | decimal | Elevation of that cell in meters, as returned. | constant per file (g24: 93; c01: 769) | 0 | Pull; Profile |

Weather columns (18): each variable below appears twice, as `<variable>_previous_day1` and `<variable>_previous_day2`.

| Variable | Unit | Meaning | Range in g24 (Profile) | Basis |
|---|---|---|---|---|
| `cloud_cover` | % | Total cloud cover as an area fraction, at the valid time. | 0 to 100 | Doc |
| `shortwave_radiation` | W/m2 | Shortwave solar radiation (global horizontal) as the average of the preceding hour. | 0 to 1,026 | Doc |
| `direct_radiation` | W/m2 | Direct solar radiation on the horizontal plane, average of the preceding hour. | 0 to 782.4 | Doc |
| `diffuse_radiation` | W/m2 | Diffuse solar radiation, average of the preceding hour. | 0 to 402.1 | Doc |
| `direct_normal_irradiance` | W/m2 | Direct radiation on a plane perpendicular to the sun, average of the preceding hour. | 0 to 830.7 | Doc |
| `temperature_2m` | degrees C | Air temperature 2 m above ground, at the valid time. | -0.8 to 48.3 | Doc |
| `relative_humidity_2m` | % | Relative humidity 2 m above ground, at the valid time. | 5 to 100 | Doc |
| `wind_speed_10m` | km/h | Wind speed 10 m above ground, at the valid time. | 0 to 29.0 | Doc |
| `precipitation` | mm | Rain, showers and snow, sum of the preceding hour. | 0 to 5.3 | Doc |

Units are as returned by the API. Across all 51 files: shortwave radiation 0 to 1,108 W/m2 and temperature -21.0 to 50.8 degrees C (day 1).

Nulls: 129 in `cloud_cover_previous_day2` and 129 in `relative_humidity_2m_previous_day1` in every file (2026-04-17 15:00 to 2026-04-22 23:00 UTC). The other 16 columns have none. Because of these nulls, those two columns load as decimals and the others as integers or decimals depending on content; cast all to float.

Not available (all null in the archive, so not saved): `cloud_cover_low`, `cloud_cover_mid`, `cloud_cover_high`, `visibility`, `snow_depth`, `aerosol_optical_depth`, `dust`.

---

## 6. EIA Form 860M capacity by month

`eia860m_solar_ciso_capacity_by_month.csv`

| Item | Value |
|---|---|
| Source | EIA Form 860M, monthly generator inventory, sheet `Operating`. https://www.eia.gov/electricity/data/eia860m/ File pattern: `https://www.eia.gov/electricity/data/eia860m/archive/xls/{month}_generator{year}.xlsx` (the latest month has no `archive/`). |
| Selection | Balancing Authority Code `CISO` and Energy Source Code `SUN`. |
| Grain | One row per generator per monthly file. |
| Key | `file_month` + `Plant ID` + `Generator ID` (no duplicates). |
| Rows | 32,503 over 33 months (890 to 1,069 per month). |
| Period | `file_month` 2024-01 to 2026-09. 2026-10 not published when pulled. |
| Pulled | 2026-10-28. |
| Caveats | Preliminary figures (Doc). Plants under 1 MW combined nameplate are excluded (Doc). Includes Arizona and Nevada plants, out-of-service generators, and both PV and solar thermal. |

All cells are stored as the source text. **Blank cells contain a single space**, not an empty string (read with `na_values=[" "]`). Columns marked "(from 2025-10)" are absent in earlier monthly files, so they are truly empty before 2025-10 and a space after.

| Column | Type | Meaning | Values and range | Blanks | Basis |
|---|---|---|---|---|---|
| `file_month` | text `YYYY-MM` | Month of the 860M file the row came from. Added by pull. | 2024-01 to 2026-09 (33 values) | 0 | Pull |
| `Entity ID` | integer | EIA code of the owner or operator entity. | 414 distinct | 0 | Inferred |
| `Entity Name` | text | Name of that entity. | 429 distinct | 0 | Inferred |
| `Plant ID` | integer | EIA plant code. | 907 distinct | 0 | Inferred |
| `Plant Name` | text | Plant name. | 927 distinct | 0 | Inferred |
| `Google Map` | text | Link label from the Excel sheet (the link itself is lost). Always "Map". | constant | 0 | Profile |
| `Bing Map` | text | Same. | constant | 0 | Profile |
| `Plant State` | text | State of the plant. | CA 31,036 rows, AZ 741, NV 726 | 0 | Profile |
| `County` | text | County. | 48 distinct | 0 | Inferred |
| `Balancing Authority Code` | text | Balancing authority. | always `CISO` | 0 | Pull |
| `Sector` | text | EIA sector. | IPP Non-CHP 26,958; Electric Utility 1,846; Industrial Non-CHP 1,671; Commercial Non-CHP 1,428; Commercial CHP 404; IPP CHP 163; Industrial CHP 33 | 0 | Profile |
| `Generator ID` | text | Generator code within the plant. | 886 distinct | 0 | Inferred |
| `Unit Code` | text | Unit code. | always blank here | 32,503 | Profile |
| `Nameplate Capacity (MW)` | decimal | Highest output the generator can reach as set by its manufacturer. | 2026-09: 0.1 to 500 MW; median 3.0 | 0 | Doc (https://www.eia.gov/tools/faqs/faq.php?id=101&t=3) |
| `Net Summer Capacity (MW)` | decimal | Maximum load the generator can support in summer, typically set by a performance test, measured at the point of interconnection. | | 0 | Doc (same link) |
| `Net Winter Capacity (MW)` | decimal | Same, for winter. | | 0 | Doc (same link) |
| `Technology` | text | Technology. | Solar Photovoltaic 32,263 rows; Solar Thermal without Energy Storage 240 | 0 | Profile |
| `Energy Source Code` | text | Energy source. | always `SUN` | 0 | Pull |
| `Prime Mover Code` | text | Prime mover. | `PV` (photovoltaic), `ST` (steam turbine, solar thermal) | 0 | Profile; meanings Inferred |
| `Operating Month` | integer | Month the generator started operating. | 1 to 12 | 0 | Inferred |
| `Operating Year` | integer | Year the generator started operating. | 1990 to 2026 | 0 | Inferred |
| `Planned Retirement Month` | text | Planned retirement month. | blank in almost every row | mostly | Inferred |
| `Planned Retirement Year` | text | Planned retirement year. | blank for 32,397 rows; 2024, 2045, 2047, 2057 otherwise | 32,397 | Profile |
| `Status` | text | Operating status. | `(OP) Operating` 32,232; `(OS) Out of service and NOT expected to return to service in next calendar year` 242; `(OA) Out of service but expected to return to service in next calendar year` 29 | 0 | Profile |
| `Nameplate Energy Capacity (MWh)` | text | Energy capacity (storage). | always blank here | all | Profile |
| `DC Net Capacity (MW)` | decimal | DC-side net capacity. | 1,405 rows blank (all solar thermal and some PV) | 1,405 | Profile; meaning Inferred |
| `Planned Derate Year` | text | Planned capacity reduction, year. | blank | all | Profile |
| `Planned Derate Month` | text | Same, month. | blank | all | Profile |
| `Planned Derate of Summer Capacity (MW)` | text | Planned reduction of summer capacity. | blank or 0 | nearly all | Profile |
| `Planned Uprate Year` | text | Planned capacity increase, year. | blank or 2025 | nearly all | Profile |
| `Planned Uprate Month` | text | Same, month. | blank, 4 or 6 | nearly all | Profile |
| `Planned Uprate of Summer Capacity (MW)` | text | Planned increase of summer capacity. | blank, 0 or 0.5 | nearly all | Profile |
| `Latitude` | decimal | Plant latitude. | present in every row | 0 | Pull |
| `Longitude` | decimal | Plant longitude. | present in every row | 0 | Pull |
| `source_url` | text | URL of the monthly workbook. Added by pull. | 33 distinct | 0 | Pull |
| `Planned Repower Year` | text | (from 2025-10) planned repower, year. | blank | all | Profile |
| `Planned Repower Month` | text | (from 2025-10) same, month. | blank | all | Profile |
| `Other Modification Year` | text | (from 2025-10) other modification, year. | blank or 2025 | nearly all | Profile |
| `Other Modification Month` | text | (from 2025-10) same, month. | blank, 4 or 5 | nearly all | Profile |

Capacity by month (nameplate MW, all CISO solar): 20,546.9 in 2024-01 to 26,034.5 in 2026-09. The full month-by-month table with PV-only, California-only and net-summer figures is in `data/raw/PULL_LOG.md`, source 4. Always name the scope: all CISO (includes about 2.8 GW in Arizona and Nevada), PV only, or California only.

---

## 7. CAISO curtailment, 5-minute workbooks (2024 to 2025)

`caiso_curtailment_2024-01-01_2025-12-31.csv.gz`

| Item | Value |
|---|---|
| Source | CAISO Production and Curtailments Data: the 2024 workbook (`production-and-curtailments-data-2024.xlsx`) and the 2025 bulk workbook (`production-and-curtailments-data-june-december-2025.xlsx`, which despite its title covers all of 2025). https://www.caiso.com/library/production-curtailments-data |
| Grain | One row per 5-minute interval in which curtailment was observed. Intervals without curtailment are not listed. |
| Key | calendar part of `Date` + `Hour` + `Interval` + `Reason` (unique, checked 2026-10-29). |
| Rows | 111,289 (51,857 from 2024; 59,432 from 2025). |
| Period | 2024-01-01 to 2025-12-31 (Pacific dates). No rows on 2025-06-16 (missing data). |
| Units | MW over a 5-minute interval. Divide a sum of intervals by 12 to get MWh. |
| Pulled | 2026-10-28. |
| Caveat | The workbook `Read_me` says only intervals with a curtailment are listed, and calls the raw data "not considered operational or settlement quality data" (quoted in `PULL_LOG.md`). |

| Column | Type | Meaning | Values and range | Nulls | Basis |
|---|---|---|---|---|---|
| `Date` | text `YYYY-MM-DD HH:MM:SS` | Calendar date of the interval. The time of day (00:00, 07:00 or 08:00 by month) is an export artifact, not part of the interval. Use the first 10 characters. | 730 distinct dates | 0 | Pull (artifact reading Inferred) |
| `Hour` | integer | Hour of the day, 1 to 24, read as Pacific hour ending. | 1 to 24 | 0 | Pull (workbook layout); hour reading Inferred from the data |
| `Interval` | integer | Five-minute interval within the hour. | 1 to 12 | 0 | Pull (workbook layout) |
| `Wind Curtailment` | decimal | Wind curtailed in the interval, MW. Blank when none was listed for wind. | 0.5 to 1,246.5 | 62,571 | Pull (workbook layout); blank meaning Inferred |
| `Solar Curtailment` | decimal | Solar curtailed in the interval, MW. Blank when none was listed for solar. | 0.5 to 9,883.1 | 13,245 | Pull (workbook layout); blank meaning Inferred |
| `Reason` | text | Type of curtailment: Local or System. | Local 87,432; System 23,857 | 0 | Pull (workbook layout) |
| `source_file` | text | Workbook URL the row came from. Added by pull. | 2 distinct | 0 | Pull |

CAISO's definition: curtailment is the difference between actual production and the forecast when actual production is less than the forecast; amounts under 1 MW are filtered out (daily curtailment PDF, 2025-05-26). Both Local and System rows can exist for the same interval, so add them for a total.

---

## 8. CAISO curtailment, Daily Renewable Report (2025-06-01 on)

`caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz`

| Item | Value |
|---|---|
| Source | CAISO Daily Renewable Report, one HTML page per operating day: `https://www.caiso.com/documents/daily-renewable-report-{mon}-{dd}-{yyyy}.html` (for example `jun-02-2026`). The curtailment tab is built from data arrays inside the page. |
| Grain | One row per fuel (solar, wind), hour and operating day. |
| Key | `operating_date` + `hour` + `fuel` (no duplicates). |
| Rows | 24,144 (503 days x 24 hours x 2 fuels). |
| Period | 2025-06-01 to 2026-10-17 (Pacific operating dates). Missing: 2025-11-05 (page returns 404). |
| Pulled | 2026-10-28 |
| Caveat | The page always has 24 values per array, including on the 23-hour (2026-03-08) and 25-hour (2025-11-02) days. How CAISO maps them is unknown. |

| Column | Type | Meaning | Values and range | Nulls | Basis |
|---|---|---|---|---|---|
| `operating_date` | date text `YYYY-MM-DD` | Pacific operating date; equals the date in the page's chart code on all 503 days. | 2025-06-01 to 2026-10-17 | 0 | Pull |
| `hour` | integer | Position 1 to 24 in the page arrays, read as Pacific hour ending. | 1 to 24 | 0 | Pull; reading Inferred |
| `fuel` | text | Fuel type. | `solar`, `wind` | 0 | Pull |
| `econ_local_mwh`, `econ_local_max_mw` | decimal | Economic curtailment, local: hourly energy (MWh) and the hourly maximum (MW). | MWh 0 to 10,560; MW 0 to 11,290 | 0 | Pull; page labels |
| `econ_system_mwh`, `econ_system_max_mw` | decimal | Economic curtailment, system. | MWh 0 to 9,156; MW 0 to 10,840 | 0 | Pull; page labels |
| `ss_local_mwh`, `ss_local_max_mw` | decimal | Self Schedule Cut, local. | MWh 0 to 831.1; MW 0 to 898.3 | 0 | Pull; page labels |
| `ss_system_mwh`, `ss_system_max_mw` | decimal | Self Schedule Cut, system. | MWh 0 to 481.0; MW 0 to 496.6 | 0 | Pull; page labels |
| `oi_local_mwh`, `oi_local_max_mw` | decimal | Operator Instruction, local. | MWh 0 to 2,527; MW 0 to 2,636 | 0 | Pull; page labels |
| `oi_system_mwh`, `oi_system_max_mw` | decimal | Operator Instruction, system. | MWh 0 to 1,558; MW 0 to 3,056 | 0 | Pull; page labels |
| `source_url` | text | Page URL. Added by pull. | 503 distinct | 0 | Pull |

The six categories are the ones the page shows (Economic, Self Schedule Cut, Operator Instruction, each Local or System). CAISO's own definitions of each category were not retrieved. Total curtailed energy in an hour is the sum of the six `_mwh` columns. Totals over the whole file (Profile, 2026-10-29): about 5.87 million MWh of solar curtailment and 0.42 million MWh of wind, of which Economic Local is the largest part (4.83 million MWh solar). Values are stored exactly as the page prints them, some in scientific notation (for example `5e-09` and `7.974e-06`). Such tiny values look like floating-point noise rather than curtailment. **[Unverified]**

Overlap check with the workbooks (2025-06-01 to 2025-12-31, 214 days): hourly solar correlation 0.998376 with no shift; totals 961,000.4 MWh (workbook) and 966,399.0 MWh (report), of which 5,396.9 MWh is the single day 2025-06-16 missing from the workbook.

---

## 9. California boundary

`reference/california_boundary_ne10m.geojson`. One GeoJSON feature: the California polygon (`iso_3166_2` = US-CA) from Natural Earth 1:10m Admin 1 states and provinces, v5.1.2 (https://github.com/nvkelso/natural-earth-vector). Used to select grid points. Not a model input.

---

## Keeping this file current

When a file is re-pulled or a column changes: update the row counts and sizes in "Files at a glance", the affected table, and "Last reviewed". Then check `data/README.md` and `README.md` for the same numbers. If you add a new dataset, add a section in the same format and a row in FAQ section 1.
