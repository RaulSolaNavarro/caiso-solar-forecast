# Project context for Claude Code

BUS 9430 team project: forecast hourly utility-scale solar output (MW) in the CAISO area one day ahead, using only information available before CAISO's 10 a.m. Pacific bid close. Read `README.md` for the problem, target variable, validation design and metrics. Read `data/raw/PULL_LOG.md` before using any raw file: it lists the checks, gaps and open issues for each source. `docs/DATA_FAQ.md` answers the common questions about the data (sources, time frames, limits, cleaning advice), `docs/DATA_DICTIONARY.md` describes every column, and `docs/DATA_HOWTO.md` has Python and R starter code. Keep them current when a file or a number changes.

## Rules

- Raw data lives in `data/raw/` (CSV and gzip CSV) and is committed so teammates can use it. Never edit a raw file by hand. Fix problems in code.
- Keep timestamps in UTC in raw files. Convert to Pacific in processing. Never shift a raw file to fix timing.
- Cleaned and merged tables go in `data/processed/`, which is not committed. Each teammate rebuilds their own.
- Never print, log or commit API keys. Keys live in `.env`.
- Do not choose model types before data exploration is done. Compare candidates on the same time-ordered folds.
- Split by time, never at random. Modeling window: 2024-03-08 to 2026-10-17 (954 days, set by the weather archive). The latest 20% (191 days, from 2026-04-10) is a locked test set. Do not tune on it.
- Never commit or push without Raúl's explicit OK in the current session. Before asking, show `git status`, the files and their sizes, the total size, and a proposed commit message. Work on a branch (not `main`), push the branch only, and let Raúl open the pull request.
- Raúl uses Windows and is new to Git and the terminal. Explain each step that changes anything in plain words.
- Write plain prose. No em dashes.

## Domain notes (keep these straight)

- **Power versus energy.** MW is power (a rate at one moment). MWh is energy (power over time). Our target is hourly solar output in MW, which is the average power in that hour, so for one hour it equals the MWh produced. Monthly totals in TWh (as in CAISO's renewables report) are energy and are not comparable to a MW peak. Example: 6.647 TWh in August 2026 is about 8,930 MW on average over 744 hours, against a peak near 24,000 MW.
- **Timestamps differ by source.** CAISO OASIS and Open-Meteo times line up with the sun. EIA label L holds the hour that CAISO reports as ending at L minus 1 hour (see PULL_LOG.md, source 2). Recommended rule, still the team's decision: align EIA label L to the hour ending at L minus 1 hour in UTC. Open-Meteo radiation is the mean of the preceding hour.
- **Capacity and peak figures disagree, and the cause is not known.** August 2026: EIA 860M CISO solar nameplate 25,813 MW (all CISO) and 23,134 MW (California only); CAISO Key Statistics (July 2026) installed solar 23,920 MW as of Aug 5 and a peak of 23,367 MW on Aug 3; CAISO's August 2026 renewables report peak 23,896 MW; EIA hourly peak 20,852 MW; OASIS ACTUAL three-hub peak 19,616 MW. Scope and interval length differ and are unchecked. Do not pick one. Name the source and scope next to every capacity or peak figure.
- **Growth.** EIA 860M CISO solar nameplate grew from 20,547 MW (2024-01) to 26,035 MW (2026-09), about 27%. CAISO's own figures were 12,049 MW in July 2019 and 23,920 MW in August 2026. Scale errors by the capacity of the same month and the same scope as the target. The 860M list of CISO solar plants includes about 2.8 GW in Arizona and Nevada (2,778 MW nameplate, 2026-09). We assume the EIA hourly CISO series covers them too, which is not verified. Monthly 860M figures are preliminary, and the 2026-10 file is not published.
- **Bids.** A day-ahead bid is an offer of MW at a price for each hour of tomorrow. Solar owners base their quantity on a forecast. Misses are settled in the real-time market. Check CAISO's business practice manuals before stating bid detail in any deliverable.
- **Weather coverage.** Weather points are coordinates (the weather service returns the nearest model grid cell), not zip codes. There are 51 locations: 41 grid points and 10 cluster points chosen so that 95.8% of CISO solar nameplate is within 50 km of a point (September 2026). `weather_locations.csv` has a static capacity share per point.
- **Curtailment.** CAISO defines it as the shortfall of actual production against its own forecast, so it may include forecast error (our reading of the definition). EIA output is measured after curtailment.
- **Never state a number without a source.** If a figure is not in a file or a cited document, label it an estimate.

## Tasks

- Data pulls are done. How they were run, what they found and what is still open is in `data/raw/PULL_LOG.md`. To re-run: `python -m src.data_pull.run_all --start 2024-01-01 --end 2026-10-17` (needs the EIA key in `.env`).
- Plan and owners: the project plan lives in the team's Google Sheet. Ask before changing task scope.
