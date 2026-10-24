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
- CAISO balancing area only (EIA respondent code `CISO`)
- Day-ahead horizon only, using only information available before the 10:00 a.m. Pacific bid close
- Data from January 2024 onward (set by the weather forecast archive)

## Data

| Role | Source | What we use it for |
|---|---|---|
| Y (known outcome) | EIA Hourly Electric Grid Monitor, API v2 | Actual hourly solar generation for CISO |
| X (inputs) | Open-Meteo Previous Runs API | Weather forecasts published before the bid close (cloud cover, sunlight, temperature). The forecast offset is set in plan Task 6. |
| Benchmark | CAISO OASIS (report SLD_REN_FCST) | CAISO's day-ahead solar forecast, scored against Y, never used for training |
| Capacity | EIA Form 860M | Installed solar capacity, used to normalize errors |
| Optional | NLR (formerly NREL) NSRDB, CAISO curtailment files, pvlib | Historical sunlight checks, curtailed hours, clear-sky values |

Open-Meteo data is licensed CC BY 4.0. Cite "Weather data by Open-Meteo.com" in any published report or deck.

Raw and processed data files are not committed. See `data/README.md`.

## Approach

We do not fix the model types in advance. The steps are:

1. Build two reference forecasts: persistence (same hour yesterday) as the floor to beat, and CAISO's own day-ahead forecast as the benchmark.
2. Explore and profile the data.
3. Choose candidate models based on what the data shows, then compare them on the same time-ordered validation folds.
4. Pick the final model on validation results and score it once on a locked test set.

## Validation

The data is split in time order, in whole days, so models never see the answers they are graded on.

- The latest 20% of days (about late March to mid-October 2026) is the locked test set. It has no winter.
- The earlier 80% is used for training and for four rolling validation folds of about three months each, with a gap of at least one day between training and validation.

## Success metrics

- Normalized MAE (MAE divided by installed solar capacity, daylight hours only), target at most 1.25 times CAISO's own error
- RMSE skill score vs persistence: 1 minus (model RMSE / persistence RMSE), target at least 0.30
- P95 overshoot in MW: the forecast-minus-actual overshoot exceeded in only 5% of daylight hours, target at least 20% below persistence
- MAPE, reported only on hours above 5% of capacity

Targets are starting points and get rechecked once the baseline exists. See `docs/` for the full memo.

## Repo layout

```
data/raw/         Downloaded source files (not committed)
data/processed/   Cleaned, merged tables (not committed)
notebooks/        Exploration and model experiments
src/              Reusable code: data pulls, features, models, scoring
reports/figures/  Charts for the deck and final report
docs/             Project plan, Task 1 memo, Task 2 data source list
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

Each teammate requests their own free EIA API key. Never commit `.env`.

## Team workflow

1. Pull before you start: `git pull`.
2. Work on a branch for anything bigger than a typo: `git checkout -b your-name/short-topic`.
3. Commit small and often with a clear message.
4. Open a pull request and have one teammate look at it before merging into `main`.
5. Do not commit data files, API keys, or large binaries.

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

- The weather forecast archive starts in January 2024, so seasonal coverage is short and each calendar month appears only two to three times.
- The final test period has no winter, so winter accuracy is checked only in validation.
- EIA generation is measured after curtailment, so on curtailed days the recorded output is lower than what the sun could have produced. We flag those days.
- Weather forecasts must be published before the bid close. A forecast issued later would make results look better than they could be in practice.
- EIA timestamps are in UTC and are converted to Pacific time before matching.
