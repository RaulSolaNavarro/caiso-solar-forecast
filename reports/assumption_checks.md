# Timing assumption checks (Brief 5, FAQ Decision D32)

Run on 2026-11-07 with `python -m src.modeling.assumption_checks` (not part of the pipeline; it makes API calls). The frozen model, `final_test.py` and the test results were not touched, and the test set was not scored again. API use: 33 Open-Meteo calls (2 probe calls plus 31 in the script, under the 100-call budget) and 4 EIA monthly requests.

The rule being checked: the forecast for hour t of Pacific day D may use only information available at CAISO's bid close, 10:00 a.m. Pacific on day D-1 (D28).

## Check 1: the day-2 weather forecast is available by 10 a.m. on D-1

**Verdict: Verified with a limit.** Every one of the 15 sample hours traces back to a weather model run that started 06:00 UTC on D-1 or earlier, so the day-2 weather was ready well before the bid close; the limit is that we sampled 1 location, 15 hours and recent dates only, and 8 of the 15 matches are nearest rather than exact.

**What the documents say.** Open-Meteo's Previous Runs API (https://open-meteo.com/en/docs/previous-runs-api, read 2026-10-28 and 2026-11-07) defines `_previous_day2` as the value predicted 48 hours before the valid time. It does not say which model run supplies a given hour or when that run becomes available. A single run can be requested from the Single Runs API (`single-runs-api.open-meteo.com`, parameter `run=` with the UTC start time).

**How our files line up in time (step 1).** No time zone or hour-ending shift was found:

| File and line | What it does |
|---|---|
| `src/data_pull/openmeteo.py:102` `params = {..., "timezone": "UTC", ...}` | Requests every hour in UTC |
| `src/data_pull/openmeteo.py:117` `df = pd.DataFrame({"time_utc": h["time"]})` | Saves the API's time as returned, no shift |
| `src/processing/build_hourly_table.py:156-158` `t = pd.to_datetime(f["time_utc"], ..., utc=True)`; `set_index(pd.DatetimeIndex(t, name="hour_end_utc"))`; `if ... not v.index.equals(grid)` | Reads the time as UTC, uses it as the hour ending, and stops if it does not match the table's hourly calendar exactly |
| `src/processing/build_hourly_table.py:105` `return (index - pd.Timedelta(hours=1)).tz_convert(LOCAL_TZ)` | `local_start` = hour ending minus 1 hour, in Pacific time |
| `src/modeling/features.py:109-110` `for c in DAY2_WEATHER + [...]: out[c] = df[c]` | The model takes the weather columns as they are, no further shift |

So the row for Pacific hour 9 a.m. to 10 a.m. uses the weather value Open-Meteo labels 10 a.m. (in UTC). For radiation that label is the mean over the preceding hour, which is exactly that row's hour (PULL_LOG, source 3, checked against the sun). Cloud cover is, by our reading of the same note (only radiation is described as averaged), an instant value at the label, so it describes the end of the hour **[Unverified]**; that would be a half-hour offset, not a use of later information.

**What we ran (step 2).** Weather point c01 (35.00, -118.04), the point with the largest share of CISO solar capacity (13.6%). Pacific dates D: 2026-10-27, 2026-10-29, 2026-10-31, 2026-11-02 and 2026-11-04 (on both sides of the Nov 1 clock change). Hours starting 9 a.m., 1 p.m. and 5 p.m. Pacific. For each hour: `shortwave_radiation_previous_day2` and `cloud_cover_previous_day2` from the Previous Runs API, against the same hour from the 00, 06, 12 and 18 UTC runs on D-2 and the 00 and 06 UTC runs on D-1 (Single Runs API, `ecmwf_ifs025`). Every comparison is in `reports/assumption_checks_weather_runs.csv`; the match per hour is in `reports/assumption_checks_weather_match.csv`.

| D | Hour (Pacific) | Run behind `previous_day2` (UTC) | Match | Hours before valid time | Started by 06:00 UTC on D-1? |
|---|---|---|---|---|---|
| 2026-10-27 | 9 a.m. | Oct 25 18:00 or Oct 26 06:00 (identical) | exact | 47 or 35 | yes |
| 2026-10-27 | 1 p.m. | Oct 25 18:00 | exact | 51 | yes |
| 2026-10-27 | 5 p.m. | Oct 26 00:00 | exact | 49 | yes |
| 2026-10-29 | 9 a.m. | Oct 27 18:00 | exact | 47 | yes |
| 2026-10-29 | 1 p.m. | Oct 27 18:00 | nearest (GHI +16 W/m2) | 51 | yes |
| 2026-10-29 | 5 p.m. | Oct 28 00:00 | nearest (cloud -5 points) | 49 | yes |
| 2026-10-31 | 9 a.m. | Oct 29 18:00 | exact | 47 | yes |
| 2026-10-31 | 1 p.m. | Oct 29 18:00 | nearest (GHI -20 W/m2) | 51 | yes |
| 2026-10-31 | 5 p.m. | Oct 29 06:00 | nearest (GHI -1 W/m2) | 67 | yes |
| 2026-11-02 | 9 a.m. | Oct 31 18:00 | nearest (GHI +14 W/m2) | 48 | yes |
| 2026-11-02 | 1 p.m. | Oct 31 18:00 | nearest (GHI +13 W/m2) | 52 | yes |
| 2026-11-02 | 5 p.m. | Nov 1 00:00 | nearest (cloud -3 points) | 50 | yes |
| 2026-11-04 | 9 a.m. | Nov 2 18:00 | exact | 48 | yes |
| 2026-11-04 | 1 p.m. | Nov 2 18:00 | exact | 52 | yes |
| 2026-11-04 | 5 p.m. | all 6 runs identical (after sunset: GHI 0, same cloud) | exact | 44 to 66 | yes (uninformative) |

The exact matches point to the run that started about 47 to 52 hours before the valid time: the 18:00 UTC run on D-2 for morning and midday hours, the 00:00 UTC run on D-1 for late-afternoon hours. That fits "the latest run at or before 48 hours ahead". The nearest matches are small differences (up to 20 W/m2 and 5 points of cloud), possibly from how each API turns 3-hourly model steps into hourly values **[Unverified]**; every nearest run also started by 06:00 UTC on D-1.

**Pass rule (step 3).** The matching run started no later than 06:00 UTC on D-1. That leaves at least 11 hours before 10 a.m. Pacific (17:00 UTC in summer, 18:00 UTC in winter) for the run to be computed and published. The 11-hour allowance is Raúl's conservative choice, not an ECMWF publication fact. Result: 15 of 15 hours pass. By the arithmetic, the latest daylight hour of D (about 8 p.m. Pacific) is valid at about 03:00 to 04:00 UTC on D+1, so 48 hours earlier is about 03:00 to 04:00 UTC on D-1, and the latest run at or before that is the 00:00 UTC run of D-1, still inside the rule.

**Limits.** 1 location, 15 hours, recent dates only (Open-Meteo may have assembled older parts of the archive, 2024 and 2025, differently; not checked). 8 matches are nearest, not exact. The publication delay of each run was not measured.

## Check 2: EIA values from D-2 are out by 10 a.m. on D-1 and are not revised much

**Verdict: Verified with a limit.** Not one of 1,872 hourly values changed between our pull (Oct 27 and 28, 2026) and a fresh pull on Nov 7, 2026; the limit is that this cannot show how much values changed between EIA's first publication and our pull, and EIA's own note puts publication about 2 hours before the bid close, not more.

**What the documents say.** EIA, "About the EIA-930 data" (https://www.eia.gov/electricity/gridmonitor/about, read by Raúl on 2026-11-07): net generation by energy source for yesterday is typically available by 11:00 a.m. Eastern, which is 8:00 a.m. Pacific. EIA collects the previous day's data again at 7:00 a.m. the next day, and respondents correct historical values, so published values can change. Reading: D-2 values are normally out about 2 hours before the 10 a.m. Pacific close. That works but leaves little slack.

**What we ran.** The same EIA call as the original pull (`src/data_pull/eia_hourly.py`, route `electricity/rto/fuel-type-data`, CISO, SUN, hourly UTC) from 2026-08-01 to the latest complete UTC day, saved outside the repo, then compared label by label with `data/raw/eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv`.

| Measure | Value |
|---|---|
| Labels compared (2026-08-01 00 to 2026-10-17 23 UTC) | 1,872 |
| Labels in the raw file missing from the re-pull | 0 |
| Values that differ | 0 |
| Mean and largest absolute difference | 0 MW and 0 MW |
| As a share of `capacity_mw` (EIA 860M, all CISO) | 0% mean, 0% largest; largest daily mean 0% |
| New labels in the re-pull (after 2026-10-17) | 488, not compared |

The 5 largest differences are all 0 MW (`reports/assumption_checks_eia_top5.csv`); every Pacific day is in `reports/assumption_checks_eia_daily.csv`.

**Pass rule.** Mean absolute difference below 0.1% of capacity and no Pacific day with a mean absolute difference above 1% of capacity. Result: pass (0% and 0%).

**Limit.** This measures revisions between Oct 27 and Nov 7, 2026 only, on data that was already 10 or more days old when we first pulled it. EIA's API does not keep first-published values, so the change between first publication and our pull cannot be measured here. Publication time comes from EIA's note and was not measured.

**The model's EIA inputs stay inside D-2 (step 4).**

| File and line | What it does |
|---|---|
| `src/modeling/features.py:129` `out["cf_lag48"] = eia.reindex(idx - MIN_LAG_HOURS * HOUR).values / ...` | EIA at the hour ending exactly 48 hours before hour t's end |
| `src/modeling/features.py:131` `pac_day = (eia.index - HOUR).tz_convert(LOCAL_TZ).tz_localize(None).normalize()` | Each EIA hour is assigned to the Pacific date on which it starts |
| `src/modeling/features.py:132-133` `g = eia.groupby(pac_day).agg(["mean", "count"])`; `.where(g["count"] >= 20)` | Daily mean per Pacific date, kept only with at least 20 hours |
| `src/modeling/features.py:134-135` `d2 = ls...normalize() - pd.Timedelta(days=MIN_DAY_OFFSET)`; `daily_mw.reindex(d2)` | Each row of day D takes the mean of Pacific date D-2 (`MIN_DAY_OFFSET` = 2) |

Checked on all 19,904 EIA hours of the training and validation period: no hour grouped into a Pacific date ends after midnight at the end of that date (the latest ends exactly 24 hours after the date starts). So no hour of D-1 enters `cf_d2_daily`. For `cf_lag48`, the latest daylight hour of D (about 8 p.m. Pacific) uses the hour ending about 8 p.m. Pacific on D-2. Note: the last hours of a Pacific day D-2 (after 9 p.m. Pacific) fall on the next Eastern day, so they may not be in EIA's "yesterday" release at 8 a.m. Pacific on D-1; they are night hours with solar output near 0, so the effect on `cf_d2_daily` is small **[Unverified]**.

## Did the frozen model use anything not available at 10 a.m.?

Nothing found. Both checks support the D28 timing rule within the limits above. The frozen model and its one test run (D31) are unchanged.
