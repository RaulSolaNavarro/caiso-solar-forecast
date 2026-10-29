# CAISO Day-Ahead Solar Forecasting

Team project for BUS 9430, Business Analytics Project Management (Baruch College, Zicklin School of Business, Fall 2026).

## The business problem

California's grid operator, CAISO, plans tomorrow's power supply today. Bids close at 10:00 a.m. Pacific the day before, and the market results come out at about 1:00 p.m. Solar is a large share of that plan, and how much it delivers depends on tomorrow's weather.

If the solar forecast is too high, operators count on power that never arrives and buy backup at the last minute. If it is too low, they line up gas plants and reserves they do not need, and in spring they may have to curtail solar the grid cannot absorb. Every megawatt (MW) the forecast misses has to be covered by gas plants, batteries, or imports. A better day-ahead solar forecast shrinks that gap.

## What we forecast (the target variable)

Hourly utility-scale solar output in the CAISO area, in MW, as measured by the U.S. Energy Information Administration (EIA). It is how much power solar plants actually produce each hour. It is not electricity demand.

## Why solar output and not demand

Grid operators plan around net load, which is total demand minus wind and solar generation (EIA definition). CAISO already forecasts demand, and that is a separate problem. Solar is the weather-driven part of the equation, so it is where a better forecast changes the plan. We forecast the solar side and compare ourselves with CAISO's own day-ahead solar forecast.

CAISO is the balancing authority for about 80% of California's electricity demand. It operates the grid and the wholesale markets. It does not own power plants.

## Scope

- Solar generation only (utility-scale, so rooftop solar is mostly excluded from the hourly data)
- CAISO balancing area only (EIA respondent code `CISO`). The EIA CISO total includes some plants in Arizona and Nevada (about 2.8 GW of nameplate in September 2026).
- Day-ahead horizon only, using only information available before the 10:00 a.m. Pacific bid close
- Modeling window: 2024-03-08 to 2026-10-17 (954 days). EIA and CAISO data start on 2024-01-01, but the weather forecast archive has every variable for both forecast offsets only from 2024-03-08.

## Data

| Role | Source | What we use it for |
|---|---|---|
| Y (known outcome) | EIA Hourly Electric Grid Monitor, API v2 (respondent CISO, fuel SUN) | Actual hourly solar generation. Timestamps need an alignment rule (see Known limits). |
| X (inputs) | Open-Meteo Previous Runs API, model `ecmwf_ifs025`, 51 locations (41 grid points plus 10 plant-cluster points) | Weather forecasts made 1 and 2 days before each hour. The main model uses the day-2 forecast, which is published before the bid close. Day 1 is only a labeled comparison. Plan Task 6 sets the offset. |
| Benchmark | CAISO OASIS (report SLD_REN_FCST, market run DAM) | CAISO's day-ahead solar forecast by trading hub (NP15, SP15, ZP26), scored against Y, never used for training |
| Backup actuals | CAISO OASIS (same report, market run ACTUAL) | CAISO's own actual solar by hub. Used for the timing check and as a backup series. |
| Capacity | EIA Form 860M, monthly, 2024-01 to 2026-09 | CISO solar generators with nameplate capacity and location, used to normalize errors and to place weather points |
| Curtailment | CAISO Production and Curtailments workbooks (2024 to 2025) and Daily Renewable Report pages (2025-06 on) | Hours where solar was curtailed, so we can flag days when output is below what the sun could produce |

Open-Meteo data is licensed CC BY 4.0. Cite "Weather data by Open-Meteo.com" in any published report or deck.

Raw source files are saved in `data/raw/` and committed, so every teammate starts from the same copy. Cleaned and merged tables in `data/processed/` are not committed. See `data/README.md` for the file list and `data/raw/PULL_LOG.md` for how each file was pulled, the checks run, the gaps found and the open issues.

## Load the data in Python

Raw files are public on GitHub, so you can read them straight into pandas without cloning anything:

```python
import pandas as pd

BASE = "https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/"
df = pd.read_csv(BASE + "<file name>.csv")        # .csv.gz files read the same way
```

The exact file names, row counts and date ranges are listed in `data/README.md`. The links work once the data pull has been merged into `main`. From a local clone you can also use `src/load_data.py`, which reads from GitHub or from your local `data/raw/` folder. GitHub can take a few minutes to show a newly pushed file.

## Approach

We do not fix the model types in advance. The steps are:

1. Build two reference forecasts: persistence (same hour yesterday) as the floor to beat, and CAISO's own day-ahead forecast as the benchmark.
2. Explore and profile the data.
3. Choose candidate models based on what the data shows, then compare them on the same time-ordered validation folds.
4. Pick the final model on validation results and score it once on a locked test set.

## Validation

The data is split in time order, in whole days, so models never see the answers they are graded on. Every model and both reference forecasts use the same window (2024-03-08 to 2026-10-17) so their scores compare.

- The latest 20% of days (191 days, 2026-04-10 to 2026-10-17) is the locked test set. It has no winter.
- The earlier 80% is used for training and for four rolling validation folds of about three months each, with a gap of at least one day between training and validation.

## Success metrics

- Normalized MAE (MAE divided by installed solar capacity, daylight hours only), target at most 1.25 times CAISO's own error
- RMSE skill score vs persistence: 1 minus (model RMSE / persistence RMSE), target at least 0.30
- P95 overshoot in MW: the forecast-minus-actual overshoot exceeded in only 5% of daylight hours, target at least 20% below persistence
- MAPE, reported only on hours above 5% of capacity

Targets are starting points and get rechecked once the baseline exists. See `docs/` for the full memo.

## Repo layout

```
data/raw/         Raw source files, exactly as pulled (committed). PULL_LOG.md documents every pull.
data/processed/   Cleaned, merged tables (not committed)
notebooks/        Exploration and model experiments
src/              Reusable code: data pulls (src/data_pull/), features, models, scoring
reports/figures/  Charts for the deck and final report
docs/             Task 1 memo, Task 2 data source list, data pull brief (the project plan lives in the team's Google Sheet)
deck/             Capstone presentation decks (HTML versions; the slides sent to the professor are PowerPoint or Google Slides)
```

## Setup

```bash
git clone <this repo's URL>
cd caiso-solar-forecast
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then paste your own API keys into .env
```

Only whoever re-runs the data pulls needs the free EIA API key (`python -m src.data_pull.run_all --start 2024-01-01 --end 2026-10-17`). Never commit `.env`. Teammates who only analyze the files in `data/raw/` can skip the `.env` step.

## Team workflow

1. Pull before you start: `git pull`.
2. Work on a branch for anything bigger than a typo: `git checkout -b your-name/short-topic`.
3. Commit small and often with a clear message.
4. Open a pull request and have one teammate look at it before merging into `main`.
5. Do not commit processed data, API keys, or large binaries. The raw files in `data/raw/` are the exception.

## Presentation rules

- Send slides to the professor as PowerPoint or Google Slides, never PDF.
- Slide numbers sit at the bottom right of every slide.
- Explain the business problem and the target variable before anything else.

## Milestones

| Date | Milestone |
|---|---|
| Oct 19 | Capstone 1: Issue Selection and Plan (complete) |
| Nov 16 | Capstone 2: Data Understanding and Preparation |
| Dec 14 | Capstone 3: Models and Results |

## Known limits

Details and counts for each item are in `data/raw/PULL_LOG.md`.

- **Short history.** Weather forecasts start on 2024-03-08, so the modeling window is 954 days. January and February appear twice, and other months two or three times.
- **No winter in the test period.** Winter accuracy is checked only in validation.
- **EIA timestamps.** EIA label L holds the hour that CAISO reports as ending at L minus 1 hour (hourly correlation 0.998 to 0.9999 in January, March and July 2025). CAISO OASIS and Open-Meteo times match the sun. The recommended rule, still the team's decision, is to align EIA label L to the hour ending at L minus 1 hour in UTC. Raw files are never shifted. All raw timestamps are UTC and are converted to Pacific time in processing.
- **Missing data, none filled.** EIA is missing one Pacific day (2024-11-02, 24 hours). CAISO's day-ahead forecast has no data for three days (2024-03-09, 2025-03-08, 2026-03-07). Open-Meteo has a 129-hour gap (2026-04-17 15:00 to 2026-04-22 23:00 UTC) in two columns, `cloud_cover_previous_day2` and `relative_humidity_2m_previous_day1`, inside the test period. The curtailment workbook has no rows for 2025-06-16, and the daily report page for 2025-11-05 does not exist. EIA 860M has no file for 2026-10 yet.
- **Night values.** EIA solar output is slightly negative at night and some hours at deep night show 100 to 413 MW. They stay in the raw file. Decide in processing.
- **Capacity and peak figures disagree across sources.** EIA 860M, CAISO's published statistics, the EIA hourly peak and the OASIS ACTUAL peak differ by several thousand MW in August 2026, and the reasons are not verified. Always name the source and scope next to a capacity or peak figure.
- **Curtailment.** EIA generation is measured after curtailment, so on curtailed days the recorded output is lower than what the sun could have produced. CAISO defines curtailment as the shortfall of actual production against its own forecast, so the series includes forecast error. We flag those days.
- **Bid-close timing.** Weather forecasts must be published before the bid close. A forecast issued later would make results look better than they could be in practice.
