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

## Tasks

- Data pulls: follow `docs/DATA_PULL_BRIEF.md`.
- Plan and owners: the project plan lives in the team's Google Sheet. Ask before changing task scope.
