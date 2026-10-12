# Data folder

Data files are not committed to Git. Each teammate rebuilds them by running the pull scripts in `src/`.

- `raw/` holds files exactly as downloaded from each source.
- `processed/` holds cleaned and merged tables (hourly, Pacific time, one row per hour).

## Rules

1. Keep timestamps in UTC in `raw/` and convert to Pacific time in the processing step.
2. Name raw files with the source and date range, for example `eia_ciso_solar_2024-01-01_2026-09-30.csv`.
3. Never edit a raw file by hand. Fix problems in code so anyone can reproduce the result.
