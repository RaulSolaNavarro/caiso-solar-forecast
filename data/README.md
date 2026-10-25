# Data folder

- `raw/` holds the source files exactly as downloaded, saved as CSV and committed to Git so every teammate starts from the same copy. Raúl runs the pulls (see `docs/DATA_PULL_BRIEF.md`) and logs each one in `raw/PULL_LOG.md`.
- `processed/` holds cleaned and merged tables (hourly, Pacific time, one row per hour). These are not committed. Each teammate builds their own in their preferred tool, so keep your cleaning in a notebook or script that someone else can re-run.

## Rules

1. Never edit a raw file by hand, and never overwrite one with cleaned data. Fix problems in code.
2. Keep timestamps in UTC in `raw/` and convert to Pacific time in the processing step.
3. Name raw files with the source and date range, for example `eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv`.
4. Do not commit `processed/` files, `raw/.cache/`, or API keys.
5. If you find a problem in a raw file, tell the team in the group chat and add a note to `raw/PULL_LOG.md` so the fix happens once, in the pull code.
