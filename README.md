# CAISO Day-Ahead Solar Forecasting

Team project for BUS 9430, Business Analytics Project Management (Baruch College, Zicklin School of Business, Fall 2026).

## The goal

We build a model that forecasts hourly utility-scale solar output on the CAISO grid one day ahead and test it against CAISO's own day-ahead forecast. We then translate the forecast errors into megawatts of backup power (gas, batteries, imports) that grid operators would need to line up, to show what a better forecast is worth.

## Why it matters

CAISO commits to tomorrow's power plan today. Bids close at 10:00 a.m. Pacific the day before, and the market results come out in the afternoon. If the solar forecast is too high, operators count on power that never arrives and buy expensive backup at the last minute. If it is too low, they may line up more gas plants than they need. A more accurate forecast means the right amount of backup is lined up a day ahead.

CAISO is the balancing authority for about 80% of California's electricity demand. It operates the grid and the wholesale markets. It does not own power plants.

## Scope

- Solar generation only (utility-scale, so rooftop solar is mostly excluded from the hourly data)
- CAISO balancing area only (EIA respondent code `CISO`)
- Day-ahead horizon only
- Data from January 2024 onward (set by the weather forecast archive)

## Data

| Role | Source | What we use it for |
|---|---|---|
| Y (known outcome) | EIA Hourly Electric Grid Monitor, API v2 | Actual hourly solar generation for CISO |
| X (inputs) | Open-Meteo Previous Runs API | Weather forecasts issued the day before (cloud cover, sunlight, temperature) |
| Benchmark | CAISO OASIS (report SLD_REN_FCST) | CAISO's day-ahead solar forecast, scored against Y, never used for training |
| Optional | NLR (formerly NREL) NSRDB, EIA Form 860M, pvlib | Historical sunlight checks, installed capacity, clear-sky values |

Open-Meteo data is licensed CC BY 4.0. Cite "Weather data by Open-Meteo.com" in any published report or deck.

Raw and processed data files are not committed. See `data/README.md`.

## Models

We compare four forecasts on the same hours:

| Forecast | Type | Role |
|---|---|---|
| Persistence (same hour yesterday) | Baseline | The floor to beat |
| Linear regression | Parametric, supervised | Simple, explainable model |
| Random forest or gradient-boosted trees | Non-parametric, supervised | Flexible model |
| CAISO day-ahead forecast | Not ours | The benchmark |

We train on earlier months and test on later months (a time-based split) so the models never see the answers they are graded on.

## Success metrics

- Normalized MAE (MAE divided by installed solar capacity, daylight hours only)
- RMSE skill score vs persistence: 1 minus (model RMSE / persistence RMSE)
- P95 overshoot in MW: the forecast-minus-actual overshoot exceeded in only 5% of daylight hours
- MAPE, reported only on hours above 5% of capacity

Targets are starting points and get rechecked once we have model results. See `docs/` for the full memo.

## Repo layout

```
data/raw/         Downloaded source files (not committed)
data/processed/   Cleaned, merged tables (not committed)
notebooks/        Exploration and model experiments
src/              Reusable code: data pulls, features, models, scoring
reports/figures/  Charts for the deck and final report
docs/             Project plan, Task 1 memo, Task 2 data source list
deck/             Capstone presentation decks
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

## Milestones

| Date | Milestone |
|---|---|
| Oct 13 | Capstone 1: Issue Selection and Plan |
| Nov 16 | Capstone 2 |
| Dec 14 | Capstone 3 |

## Known limits

- The weather forecast archive starts in January 2024, so seasonal coverage is short.
- EIA generation is measured after curtailment, so on curtailed days the recorded output is lower than what the sun could have produced. We flag those days.
- EIA timestamps are in UTC and are converted to Pacific time before matching.
