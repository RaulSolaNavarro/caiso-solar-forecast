# Data pull brief (for Claude Code)

Owner: Raúl. This file tells Claude Code what to pull, how to save it, and how to check it. Read `README.md` and `CLAUDE.md` first.

## Start prompt (paste into Claude Code from the repo root)

> Read CLAUDE.md, README.md and docs/DATA_PULL_BRIEF.md. Do the data pull as the brief describes, one source at a time, in the order listed. Test each source on January 2024 first, show me the check results, and wait for my OK before the full pull. Do not commit or push. Stop and ask me at any point listed under "Stop and ask".

## Goal

Download five raw sources for the CAISO day-ahead solar forecasting project and save each as a CSV in `data/raw/`. Teammates will open these CSVs in their own tools for cleanup, EDA and modeling, so the raw files must be exact, documented and reproducible.

## Fixed settings

- Start date: 2024-01-01.
- End date: 2026-10-17 (last full day we use). If a source has nothing for the last few days, keep what exists and record the real last date in the pull log.
- Time zone: keep every timestamp in UTC in raw files. Convert to Pacific only in later processing.
- No cleaning in raw files. Do not drop, fill, rename values, convert units or fix outliers. Add columns only for the pull date and source URL if useful.
- API keys come from `.env` (`EIA_API_KEY`, optional `NLR_API_KEY`). Never print, log or commit a key.

## Sources, in order

### 1. EIA hourly solar generation (the target variable)

- API v2: `https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/`
- Filters: frequency hourly, respondent `CISO`, fuel type `SUN`, field `value`, sorted by `period` ascending.
- Pages hold at most 5,000 rows, so paginate with `offset` and `length`. Periods arrive in UTC.
- File: `data/raw/eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv`. Keep all returned columns (period, respondent, fueltype, value, value-units).
- Check the API docs for the exact route and parameter names before coding. Fix anything that differs from this brief and note it in the pull log.

### 2. CAISO day-ahead solar forecast (benchmark, never used for training)

- CAISO OASIS SingleZip API, report `SLD_REN_FCST`, `market_run_id=DAM`, CSV result format.
- Requests are limited to about one month of data and the server throttles fast callers. Pull month by month, wait at least 5 seconds between calls, and retry on 429 or timeout.
- Keep the by-hub rows (trading hub, renewable type, hour, MW). Do not sum hubs or drop wind in the raw file.
- File: `data/raw/caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv`.
- Optional: also pull `market_run_id=ACTUAL` for the same report, if it exists, as a backup target (risk 1 in the plan). Save it as a separate file.
- Check the OASIS docs for the current parameter format and column names, and confirm which columns hold UTC.

### 3. Open-Meteo weather forecasts (model inputs)

- Previous Runs API: `https://previous-runs-api.open-meteo.com/v1/forecast`. Read the docs page first: `https://open-meteo.com/en/docs/previous-runs-api`.
- Pull both the day-1 and the day-2 offsets (the `_previous_day1` and `_previous_day2` variable suffixes) so the team can compare them when agreeing the timing rule (plan task 6). Do not choose between them in the raw file.
- Variables to start with: `cloud_cover`, `shortwave_radiation`, `direct_radiation`, `diffuse_radiation`, `direct_normal_irradiance`, `temperature_2m`. Add `relative_humidity_2m` and `wind_speed_10m` only if the docs show them with previous-day history.
- Request `timezone=UTC` so timestamps match the other files.
- Model: use one model for the whole period. Prefer `ecmwf_ifs025` if the docs show its previous-runs history starts on or before 2024-01-01, otherwise `best_match`. Never mix models across dates. Record the choice and why in the pull log.
- Locations: start wide and cover all of California, then narrow later with data. Build a grid of points about 1 degree apart (roughly 100 km) and keep the points that fall inside the California boundary (use a states boundary file such as Natural Earth or Census, do not hand-draw it). Add up to 6 extra points at the capacity-weighted centers of the largest utility-scale solar clusters from the EIA 860M data (source 4), because solar plants are concentrated in a few desert and valley areas that a coarse grid can miss. Save every point to `data/raw/weather_locations.csv` with `location_id`, latitude, longitude, type (`grid` or `cluster`), and, once source 4 is pulled, the share of CAISO solar capacity nearest to that point. That share is what lets us narrow the list later without guessing. If 860M coordinates are missing, use these approximate cluster points instead and say so: Westlands, Fresno County (36.4, -120.1); Kern County (35.0, -118.2); Mojave Desert, San Bernardino County (35.3, -115.5); Desert Center and Blythe, Riverside County (33.8, -115.2); Imperial Valley (32.9, -115.6).
- Budget the calls before starting. With about 45 to 50 locations, three years of hourly data and two offsets, the free-tier daily limit may take several days to clear. Work out the request count, pull in chunks (one location and one quarter per request), cache each chunk on disk so a re-run skips finished chunks, pace the requests, and tell me the expected duration before the full pull.
- Files: one file per location, `data/raw/openmeteo/openmeteo_prev_runs_<location_id>_2024-01-01_2026-10-17.csv.gz` (gzip-compressed CSV, which pandas, R and Excel-compatible tools read directly), with columns `time_utc`, `location_id`, `latitude`, `longitude`, then the weather columns. Keep all variable and offset columns. Compression keeps the repo small, since about 50 uncompressed files would add well over 100 MB to Git.

### 4. EIA Form 860M installed capacity

- Monthly generator inventory: `https://www.eia.gov/electricity/data/eia860m/` (the archive page lists past months).
- Download the monthly file for every month from 2024-01 to the latest, and read the Operating sheet (and the Retired sheet if needed).
- Keep rows for solar photovoltaic generators in the CAISO area. Use the balancing authority code column if present. If it is missing, use California plants and say so in the log.
- File: `data/raw/eia860m_solar_ciso_capacity_by_month.csv`, one row per generator per monthly file, with a `file_month` column, nameplate and net summer capacity, operating month and year, state, county, latitude and longitude.
- If the per-month archive files are not all available, rebuild monthly capacity from the latest file's operating dates and the retired list, and write exactly what was rebuilt in the log.

### 5. Curtailment flags

- CAISO's Production and Curtailments Data page: `https://www.caiso.com/library/production-curtailments-data`. Earlier research found the report runs through December 2025 and stopped publishing after that.
- Pull everything available from 2024-01-01 and save it as `data/raw/caiso_curtailment_<first>_<last>.csv`.
- For 2026, look for a replacement source (CAISO Today's Outlook, OASIS reports, or another official page). Report what exists and what does not. Do not estimate curtailment and do not invent a series.

## Code layout

- Scripts go in `src/data_pull/` (one module per source plus a small `run_all.py`). Each takes `--start` and `--end`, skips work already on disk, and is safe to re-run.
- Put shared helpers (retry, paging, logging) in `src/data_pull/common.py`.
- Add any new package to `requirements.txt`.
- Add `data/raw/PULL_LOG.md` with one section per source: URL or endpoint, date pulled, parameters, row count, first and last timestamp, known gaps, and anything that differed from this brief.

## Checks before reporting each source

1. Row count against the expected count (for hourly sources: days times 24, minus known gaps). List missing hours.
2. No duplicate timestamps (per location or hub where relevant).
3. Timestamps are UTC and the first and last rows match the requested range.
4. Solar values are zero or near zero at night and positive at midday (sanity check on the time zone).
5. Null counts per column, minimum, maximum and median of the main value columns.
6. File size. Show it with the other results.

Print a short check table for each source and paste the same table into `PULL_LOG.md`.

## Stop and ask

- Any single file would be larger than 50 MB, or the new files to commit total more than 100 MB.
- A source needs a login, a paid plan or a key that is not in `.env`.
- The API docs show a different route, parameter or limit that changes the plan.
- More than 1% of expected hours are missing from any source.
- The Open-Meteo model needs a choice you are not sure about, or the grid and boundary step does not give a sensible set of California points.
- You are about to commit, push, delete a file or change anything outside `src/data_pull/`, `data/raw/`, `requirements.txt` and `docs/`.

## Done means

All five sources saved and checked, `PULL_LOG.md` complete, scripts re-run cleanly from an empty `data/raw/` for one month as a test, and a short summary for Raúl with the row counts, the date coverage and every open issue. Raúl commits and pushes.
