# Data folder

- `raw/` holds the source files exactly as downloaded, saved as CSV (some gzip-compressed, `.csv.gz`) and committed to Git so every teammate starts from the same copy. Raúl runs the pulls (see `docs/DATA_PULL_BRIEF.md` and `src/data_pull/`) and logs each one in `raw/PULL_LOG.md`.
- Questions about the data? Read `../docs/DATA_FAQ.md` (sources, time frames, limits, cleaning advice), `../docs/DATA_DICTIONARY.md` (every file and column) and `../docs/DATA_HOWTO.md` (Python and R starter code).
- `processed/` holds cleaned and merged tables (hourly, Pacific time, one row per hour). These are not committed. Each teammate builds their own in their preferred tool, so keep your cleaning in a notebook or script that someone else can re-run.

## Rules

1. Never edit a raw file by hand, and never overwrite one with cleaned data. Fix problems in code.
2. Keep timestamps in UTC in `raw/` and convert to Pacific time in the processing step. Exception: the two curtailment files come from CAISO with Pacific operating dates and hours (hour ending 1 to 24); see `raw/PULL_LOG.md`.
3. Name raw files with the source and date range, for example `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv`.
4. Do not commit `processed/` files, `raw/.cache/`, or API keys.
5. If you find a problem in a raw file, tell the team in the group chat and add a note to `raw/PULL_LOG.md` so the fix happens once, in the pull code.

## Before you use the files

Read `raw/PULL_LOG.md` first. Points that change how the files are matched:

- **EIA timestamps (open issue).** EIA's hourly label L carries the hour that CAISO reports as ending at L minus 1 hour. Recommended rule for processing: EIA label L = the hour ending at L minus 1 hour (UTC). No raw file is shifted.
- **Weather starts later.** Open-Meteo previous-runs data (`ecmwf_ifs025`) starts on 2024-03-08, so models that use weather run from 2024-03-08. The locked test set is about 2026-04-10 to 2026-10-17.
- **Weather radiation** is the mean over the hour before `time_utc` (Open-Meteo documentation, checked against the sun).
- **Known gaps**: EIA misses 2024-11-02 (Pacific day); OASIS DAM misses the day before each spring DST change; weather misses `cloud_cover_previous_day2` and `relative_humidity_2m_previous_day1` from 2026-04-17 15:00 to 2026-04-22 23:00 UTC; curtailment misses 2025-06-16 (workbook) and 2025-11-05 (daily report). None is filled.

## Files in `raw/`

The raw GitHub URLs below point to `main`, like `BASE` in the root `README.md`. To read a file from a branch that is not merged yet, replace `main` with the branch name. GitHub can take a few minutes to show a newly pushed file. Sizes are on-disk sizes; `.csv.gz` files are gzip-compressed.

| File | Source | Rows | Date range | Size | Raw GitHub URL |
|---|---|---|---|---|---|
| `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv` | 1. EIA hourly solar, CISO (UTC `period`) | 24,480 | 2024-01-01T00 to 2026-10-17T23 | 2.12 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv |
| `caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz` | 2. CAISO OASIS SLD_REN_FCST, DAM (UTC interval start) | 146,706 | 2023-12-31T08:00:00-00:00 to 2026-10-18T06:00:00-00:00 | 1.30 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz |
| `caiso_actual_solar_2024-01-01_2026-10-17.csv.gz` | 2. CAISO OASIS SLD_REN_FCST, ACTUAL (UTC interval start) | 146,210 | 2023-12-31T08:00:00-00:00 to 2026-10-18T06:00:00-00:00 | 1.72 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/caiso_actual_solar_2024-01-01_2026-10-17.csv.gz |
| `eia860m_solar_ciso_capacity_by_month.csv` | 4. EIA 860M, CISO solar generators (`file_month`) | 32,503 | 2024-01 to 2026-09 | 9.77 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/eia860m_solar_ciso_capacity_by_month.csv |
| `weather_locations.csv` | 3. Weather points: 41 grid + 10 cluster | 51 |  | 1.6 KB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/weather_locations.csv |
| `reference/california_boundary_ne10m.geojson` | 3. California boundary, Natural Earth 1:10m v5.1.2 | 1 feature |  | 44.6 KB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/reference/california_boundary_ne10m.geojson |
| `caiso_curtailment_2024-01-01_2025-12-31.csv.gz` | 5. CAISO curtailment workbooks, 5-minute (Pacific date) | 111,289 | 2024-01-01 to 2025-12-31 | 1.56 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/caiso_curtailment_2024-01-01_2025-12-31.csv.gz |
| `caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz` | 5. CAISO Daily Renewable Report, hourly (Pacific operating date) | 24,144 | 2025-06-01 to 2026-10-17 | 0.29 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz |
| `PULL_LOG.md` | Pull log: endpoints, parameters, checks, gaps, decisions | | | 56.8 KB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/PULL_LOG.md |

### Weather files (`raw/openmeteo/`, 51 files)

Each file has `time_utc`, `location_id`, `latitude`, `longitude`, `model`, `model_latitude`, `model_longitude`, `model_elevation`, then 9 variables for day 1 and day 2 (`<variable>_previous_day1`, `<variable>_previous_day2`). Point coordinates and capacity shares are in `weather_locations.csv`.

| Location | File | Rows | Date range (UTC) | Size | Raw GitHub URL |
|---|---|---|---|---|---|
| g01 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g01_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g01_2024-03-08_2026-10-17.csv.gz |
| g02 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g02_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.59 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g02_2024-03-08_2026-10-17.csv.gz |
| g03 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g03_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.59 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g03_2024-03-08_2026-10-17.csv.gz |
| g04 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g04_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.59 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g04_2024-03-08_2026-10-17.csv.gz |
| g05 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g05_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g05_2024-03-08_2026-10-17.csv.gz |
| g06 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g06_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g06_2024-03-08_2026-10-17.csv.gz |
| g07 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g07_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.59 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g07_2024-03-08_2026-10-17.csv.gz |
| g08 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g08_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.59 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g08_2024-03-08_2026-10-17.csv.gz |
| g09 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g09_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g09_2024-03-08_2026-10-17.csv.gz |
| g10 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g10_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g10_2024-03-08_2026-10-17.csv.gz |
| g11 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g11_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g11_2024-03-08_2026-10-17.csv.gz |
| g12 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g12_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.59 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g12_2024-03-08_2026-10-17.csv.gz |
| g13 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g13_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g13_2024-03-08_2026-10-17.csv.gz |
| g14 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g14_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g14_2024-03-08_2026-10-17.csv.gz |
| g15 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g15_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g15_2024-03-08_2026-10-17.csv.gz |
| g16 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g16_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.59 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g16_2024-03-08_2026-10-17.csv.gz |
| g17 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g17_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g17_2024-03-08_2026-10-17.csv.gz |
| g18 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g18_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g18_2024-03-08_2026-10-17.csv.gz |
| g19 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g19_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g19_2024-03-08_2026-10-17.csv.gz |
| g20 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g20_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g20_2024-03-08_2026-10-17.csv.gz |
| g21 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g21_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g21_2024-03-08_2026-10-17.csv.gz |
| g22 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g22_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g22_2024-03-08_2026-10-17.csv.gz |
| g23 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g23_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g23_2024-03-08_2026-10-17.csv.gz |
| g24 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g24_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g24_2024-03-08_2026-10-17.csv.gz |
| g25 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g25_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g25_2024-03-08_2026-10-17.csv.gz |
| g26 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g26_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.56 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g26_2024-03-08_2026-10-17.csv.gz |
| g27 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g27_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g27_2024-03-08_2026-10-17.csv.gz |
| g28 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g28_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g28_2024-03-08_2026-10-17.csv.gz |
| g29 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g29_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.56 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g29_2024-03-08_2026-10-17.csv.gz |
| g30 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g30_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.56 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g30_2024-03-08_2026-10-17.csv.gz |
| g31 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g31_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.56 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g31_2024-03-08_2026-10-17.csv.gz |
| g32 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g32_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g32_2024-03-08_2026-10-17.csv.gz |
| g33 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g33_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g33_2024-03-08_2026-10-17.csv.gz |
| g34 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g34_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g34_2024-03-08_2026-10-17.csv.gz |
| g35 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g35_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g35_2024-03-08_2026-10-17.csv.gz |
| g36 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g36_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g36_2024-03-08_2026-10-17.csv.gz |
| g37 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g37_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.56 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g37_2024-03-08_2026-10-17.csv.gz |
| g38 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g38_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g38_2024-03-08_2026-10-17.csv.gz |
| g39 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g39_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g39_2024-03-08_2026-10-17.csv.gz |
| g40 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g40_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g40_2024-03-08_2026-10-17.csv.gz |
| g41 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g41_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g41_2024-03-08_2026-10-17.csv.gz |
| c01 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c01_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c01_2024-03-08_2026-10-17.csv.gz |
| c02 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c02_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c02_2024-03-08_2026-10-17.csv.gz |
| c03 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c03_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c03_2024-03-08_2026-10-17.csv.gz |
| c04 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c04_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c04_2024-03-08_2026-10-17.csv.gz |
| c05 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c05_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c05_2024-03-08_2026-10-17.csv.gz |
| c06 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c06_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c06_2024-03-08_2026-10-17.csv.gz |
| c07 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c07_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c07_2024-03-08_2026-10-17.csv.gz |
| c08 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c08_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c08_2024-03-08_2026-10-17.csv.gz |
| c09 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c09_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.58 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c09_2024-03-08_2026-10-17.csv.gz |
| c10 | `openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c10_2024-03-08_2026-10-17.csv.gz` | 22,896 | 2024-03-08T00:00 to 2026-10-17T23:00 | 0.57 MB | https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/openmeteo/openmeteo_prev_runs_ecmwf_ifs025_c10_2024-03-08_2026-10-17.csv.gz |

Total for all 60 files: 46.1 MB (46,131,562 bytes).

## Load the files in Python

The repo is public, so pandas can read any file straight from GitHub. pandas reads `.csv.gz` directly (it detects gzip from the ending).

```python
import pandas as pd

BRANCH = "main"   # use your branch name to read files from a branch that is not merged yet
BASE = f"https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/{BRANCH}/data/raw/"

eia = pd.read_csv(BASE + "eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv")
dam = pd.read_csv(BASE + "caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz")
cap = pd.read_csv(BASE + "eia860m_solar_ciso_capacity_by_month.csv")
wx = pd.read_csv(BASE + "openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g24_2024-03-08_2026-10-17.csv.gz")
curt = pd.read_csv(BASE + "caiso_curtailment_2024-01-01_2025-12-31.csv.gz")
```

From a local clone, `src/load_data.py` does the same: `read_raw("<file name>")` reads from `main` on GitHub (`branch="<branch name>"` reads another branch), and `read_raw("<file name>", source="local")` reads your `data/raw/` folder.
