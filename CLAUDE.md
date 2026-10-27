# Project context for Claude Code

BUS 9430 team project: forecast hourly utility-scale solar output (MW) in the CAISO area one day ahead, using only information available before CAISO's 10 a.m. Pacific bid close. Read `README.md` for the problem, target variable, validation design and metrics.

## Rules

- Raw data lives in `data/raw/` as CSV and is committed so teammates can use it. Never edit a raw file by hand. Fix problems in code.
- Keep timestamps in UTC in raw files. Convert to Pacific in processing.
- Cleaned and merged tables go in `data/processed/`, which is not committed. Each teammate rebuilds their own.
- Never print, log or commit API keys. Keys live in `.env`.
- Do not choose model types before data exploration is done. Compare candidates on the same time-ordered folds.
- Split by time, never at random. The latest 20% of days is a locked test set. Do not tune on it.
- Never commit or push without Raúl's explicit OK in the current session. Before asking, show `git status`, the files and their sizes, the total size, and a proposed commit message. Work on a branch (not `main`), push the branch only, and let Raúl open the pull request.
- Raúl uses Windows and is new to Git and the terminal. Explain each step that changes anything in plain words.
- Write plain prose. No em dashes.

## Domain notes (keep these straight)

- **Power versus energy.** MW is power (a rate at one moment). MWh is energy (power over time). Our target is hourly solar output in MW, which is the average power in that hour, so for one hour it equals the MWh produced. Monthly totals in TWh (as in CAISO's renewables report) are energy and are not comparable to a MW peak. Example: 6.647 TWh in August 2026 is about 8,930 MW on average over 744 hours, against a peak near 24,000 MW.
- **Capacity figures disagree, and the cause is not known yet.** CAISO Key Statistics (July 2026) lists installed solar at 23,920 MW as of Aug 5, 2026 and a peak of 23,367 MW on Aug 3. CAISO's August 2026 renewables report lists a peak of 23,896 MW. Earlier CAISO material used about 23,000 MW (May 2026), and CAISO counts only fully commercial units and changed its method. Do not pick one. Report all of them next to the EIA 860M capacity and the EIA hourly peak, as the brief asks.
- **Growth.** CAISO installed solar was 12,049 MW in July 2019 and 23,920 MW in August 2026, so errors must be scaled by the capacity installed in that month. EIA statewide figures include rooftop solar and are not the same measure as CAISO's.
- **Bids.** A day-ahead bid is an offer of MW at a price for each hour of tomorrow. Solar owners base their quantity on a forecast. Misses are settled in the real-time market. Check CAISO's business practice manuals before stating bid detail in any deliverable.
- **Weather coverage.** Weather points are coordinates (the weather service returns the nearest model grid cell), not zip codes. What matters is a point near each solar plant, so the brief requires a capacity-coverage check.
- **Never state a number without a source.** If a figure is not in a file or a cited document, label it an estimate.

## Tasks

- Data pulls: follow `docs/DATA_PULL_BRIEF.md`.
- Plan and owners: the project plan lives in the team's Google Sheet. Ask before changing task scope.
