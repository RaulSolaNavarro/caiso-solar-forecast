# Data how-to (Python and R)

How to load the project's raw files, take a first look, and line them up for analysis. Every code block on this page was run against the files on GitHub (`main`) on 2026-10-29 with Python 3.13 (pandas 3.0.5, and again with pandas 2.2.3) and R 4.3.3 (readr 2.1.5, dplyr 1.1.4, lubridate 1.9.3). If a block fails for you, tell the team in the group chat and note the error and your versions.

Read `docs/DATA_FAQ.md` for why the data looks the way it does, and `docs/DATA_DICTIONARY.md` for what each column means.

## 1. Pick your tools

You can use any tool. These are the ones we tested and recommend.

| Job | Recommended | Why |
|---|---|---|
| Python, everyday work | **Visual Studio Code** with the Python and Jupyter extensions | Free. Runs scripts and notebooks in one window, and has a built-in terminal and Git panel. Raúl uses it. |
| Python, notebooks only | **JupyterLab** (`pip install jupyterlab`, already in `requirements.txt`) | Good for charts and notes next to code. |
| R | **RStudio Desktop** (free, from Posit) | The standard R editor: console, script, plots and data viewer side by side. VS Code with the R extension also works. |
| No installs, just a look | **Google Colab** (Python) | Runs in a browser. Paste the "first lines" below and run. |
| Quick glance at a small file | **Excel** | Fine for `weather_locations.csv`. Do not use it to edit raw files. |

Notes on Excel: it can open the plain `.csv` files but not the `.csv.gz` ones until you unzip them, it turns text like `2024-01-01T00` into dates without asking, and it hides leading zeros and long numbers. Look, but do not save over a raw file. Raw files are never edited by hand (`data/README.md`, rule 1).

Notebooks (`.ipynb`) are good for exploring. When something works, move it into a script in `src/` so the team can re-run it.

## 2. Install what you need (once)

**Python** (from the repo folder; `requirements.txt` has everything):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Mac or Linux, activate with `source .venv/bin/activate`. If Windows blocks the activation script, run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` once in PowerShell. The code below needs only `pandas` and `matplotlib`. The blocks give the same counts in pandas 3.0.5 and 2.2.3 (text columns show as `str` in pandas 3 and `object` in pandas 2).

**R** (in the R console):

```r
install.packages(c("readr", "dplyr", "tidyr", "lubridate", "ggplot2"))
```

R 4.1 or later is needed for the `|>` pipe used below.

## 3. Python

### 3.1 The first lines

Seven lines that load the target variable, check it, and plot it. No clone, no key, no download step: the repo is public and the files are read straight from GitHub.

```python
import pandas as pd
import matplotlib.pyplot as plt

BASE = "https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/"
eia = pd.read_csv(BASE + "eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv", parse_dates=["period"])
eia.info(); print(eia.describe())
eia.set_index("period")["value"].resample("D").sum().plot(title="CISO solar, MWh per day"); plt.show()
```

You should see 24,480 rows, a `value` from -74 to 20,852, and a yearly wave: high in summer, low in winter. `period` is the UTC hour label (EIA's timing offset is covered in 3.4).

### 3.2 Load every dataset

The helper retries a failed download, because some reads from GitHub have been reset on the pull machine (FAQ Q6.19).

```python
import time

def read(name, tries=4, **kw):
    for i in range(tries):
        try:
            return pd.read_csv(BASE + name, **kw)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))

eia  = read("eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv")
dam  = read("caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz")        # .gz is read directly
act  = read("caiso_actual_solar_2024-01-01_2026-10-17.csv.gz")
loc  = read("weather_locations.csv")
wx   = read("openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g24_2024-03-08_2026-10-17.csv.gz")   # one of 51 points
cap  = read("eia860m_solar_ciso_capacity_by_month.csv", na_values=[" "], low_memory=False)   # blanks are single spaces
curt = read("caiso_curtailment_2024-01-01_2025-12-31.csv.gz")
rep  = read("caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz")

for name, d in dict(eia=eia, dam=dam, act=act, loc=loc, wx=wx, cap=cap, curt=curt, rep=rep).items():
    print(f"{name:5s} {d.shape}")
```

Expected output:

| Name | Shape (rows, columns) |
|---|---|
| `eia` | (24480, 7) |
| `dam` | (146706, 14) |
| `act` | (146210, 14) |
| `loc` | (51, 5) |
| `wx` | (22896, 26) |
| `cap` | (32503, 39) |
| `curt` | (111289, 7) |
| `rep` | (24144, 16) |

To read from a clone instead of GitHub (faster, works offline), run from the repo folder and use the local folder as the base:

```python
BASE = "data/raw/"          # run from the repo root; then use read() exactly as above
```

`src/load_data.py` does the same with `read_raw("<file>", source="local")`. The first read from GitHub is slower than local, and a newly pushed file can take a few minutes to appear.

### 3.3 A first look at each dataset

```python
# EIA: gaps, negatives, and the shape of an average day
full = pd.date_range("2024-01-01 00:00", "2026-10-17 23:00", freq="h")
print("missing hours:", len(full.difference(pd.to_datetime(eia["period"], format="%Y-%m-%dT%H"))))   # 24
print("negative hours:", (eia["value"] < 0).sum())                                                    # 9461
t = pd.to_datetime(eia["period"], format="%Y-%m-%dT%H").dt.tz_localize("UTC")
print(eia.groupby(t.dt.tz_convert("America/Los_Angeles").dt.hour)["value"].mean().round(0))           # average MWh by Pacific hour of EIA's label, before the timing rule

# CAISO day-ahead: one row per hub, fuel and hour
print(dam.groupby(["TRADING_HUB", "RENEWABLE_TYPE"]).size())

# Weather: where are the nulls, and what are the ranges?
print(wx.isna().sum()[lambda s: s > 0])         # the 129-hour gap in two columns
print(wx.describe().T[["min", "max"]].round(1))

# Capacity: total nameplate MW by monthly file (all CISO solar, includes AZ and NV)
print(cap.groupby("file_month")["Nameplate Capacity (MW)"].sum().round(1).tail(3))                    # 25812.8 at 2026-08, 26034.5 at 2026-09

# Curtailment workbooks: solar MWh by month (5-minute MW divided by 12)
curt["date"] = pd.to_datetime(curt["Date"].str[:10])
print((curt.groupby(curt["date"].dt.to_period("M"))["Solar Curtailment"].sum() / 12).round(0).head())
```

### 3.4 Put the files on one clock, then merge

The key is **hour ending, in UTC**. EIA's label is shifted by the recommended rule (EIA label L is the hour ending at L minus 1 hour; this is the team's working rule, not yet final, FAQ Q6.1). OASIS has the end time in `INTERVALENDTIME_GMT`. Open-Meteo's `time_utc` is already the end of the hour for radiation.

This block builds one hourly table: EIA actuals, CAISO's day-ahead total, and the capacity-weighted average of the day-2 weather forecasts.

```python
# 1. Target, on the hour-ending clock
eia = pd.read_csv(BASE + "eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv", usecols=["period", "value"])
eia["hour_end_utc"] = pd.to_datetime(eia["period"], format="%Y-%m-%dT%H", utc=True) - pd.Timedelta(hours=1)
eia = eia.set_index("hour_end_utc")[["value"]].rename(columns={"value": "eia_mw"})

# 2. CAISO day-ahead forecast: Solar only, the three hubs summed, kept only if all three are present
dam = pd.read_csv(BASE + "caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz",
                  usecols=["INTERVALENDTIME_GMT", "TRADING_HUB", "RENEWABLE_TYPE", "MW"])
dam = dam[(dam["RENEWABLE_TYPE"] == "Solar") & dam["TRADING_HUB"].isin(["NP15", "SP15", "ZP26"])].copy()
dam["hour_end_utc"] = pd.to_datetime(dam["INTERVALENDTIME_GMT"], utc=True)
dam = dam.groupby(["hour_end_utc", "TRADING_HUB"])["MW"].sum().unstack()
dam = dam.sum(axis=1, min_count=3).rename("caiso_dam_mw").to_frame()

# 3. Weather: 51 points, averaged with the capacity shares (12 points have share 0 and drop out)
loc = pd.read_csv(BASE + "weather_locations.csv")
frames = []
for lid, share in zip(loc["location_id"], loc["caiso_solar_capacity_share"]):
    if share == 0:
        continue
    f = read(f"openmeteo/openmeteo_prev_runs_ecmwf_ifs025_{lid}_2024-03-08_2026-10-17.csv.gz")
    f["w"] = share
    frames.append(f)
wx = pd.concat(frames, ignore_index=True)
cols = [c for c in wx.columns if c.endswith("_previous_day2")]     # the day-2 forecasts
num = wx[cols].mul(wx["w"], axis=0).groupby(wx["time_utc"]).sum()
den = wx[cols].notna().mul(wx["w"], axis=0).groupby(wx["time_utc"]).sum()
wxavg = num / den
wxavg.index = pd.to_datetime(wxavg.index, utc=True)
wxavg.index.name = "hour_end_utc"

# 4. Join and add Pacific time
df = eia.join(dam, how="inner").join(wxavg, how="inner")
df["pacific"] = df.index.tz_convert("America/Los_Angeles")
print(df.shape)                                                      # (22799, 12); the hour is the index
print(df["eia_mw"].corr(df["shortwave_radiation_previous_day2"]))    # about 0.93
```

Expected: 22,799 rows (12 columns, with the hour as the index; in R the hour is a 13th column) between 2024-03-08 and 2026-10-17. That is the 22,895 hours the sources share, minus 24 hours EIA lacks and 72 hours the day-ahead file lacks. The one column with gaps is `cloud_cover_previous_day2` (129 nulls). The static capacity shares are the 2026-09 values and are only approximate for 2024 (FAQ Q7.5).

Two traps this block avoids: it joins on the UTC end time, not on `OPR_DT` and `OPR_HR` (those follow the local clock and break on clock-change days), and it averages weather over the points with the same weights for every hour.

## 4. R

### 4.1 The first lines

```r
library(readr)
library(dplyr)
library(lubridate)
library(ggplot2)
BASE <- "https://raw.githubusercontent.com/RaulSolaNavarro/caiso-solar-forecast/main/data/raw/"
eia <- read_csv(paste0(BASE, "eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv"), col_types = cols(period = col_datetime("%Y-%m-%dT%H"), value = col_double(), .default = col_character()))
glimpse(eia); summary(eia$value)
eia |> group_by(day = as_date(period)) |> summarise(mwh = sum(value)) |> ggplot(aes(day, mwh)) + geom_line() + labs(title = "CISO solar, MWh per day")
```

Same result as in Python: 24,480 rows, `value` from -74 to 20,852. The `col_types` argument is there on purpose: it reads `period` as a UTC date-time and keeps the text columns as text. Leave it out and `readr` guesses, which also works here but can change between versions.

### 4.2 Load every dataset

```r
read <- function(name, tries = 4, ...) {
  for (i in seq_len(tries)) {
    out <- tryCatch(read_csv(paste0(BASE, name), show_col_types = FALSE, ...), error = function(e) NULL)
    if (!is.null(out)) return(out)
    Sys.sleep(5 * i)
  }
  stop("could not read ", name)
}

eia  <- read("eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv")
dam  <- read("caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz")          # .gz is read directly
act  <- read("caiso_actual_solar_2024-01-01_2026-10-17.csv.gz")
loc  <- read("weather_locations.csv")
wx   <- read("openmeteo/openmeteo_prev_runs_ecmwf_ifs025_g24_2024-03-08_2026-10-17.csv.gz")   # one of 51 points
cap  <- read("eia860m_solar_ciso_capacity_by_month.csv", col_types = cols(.default = col_character()))  # all text; convert what you need
curt <- read("caiso_curtailment_2024-01-01_2025-12-31.csv.gz")
rep  <- read("caiso_curtailment_daily_report_2025-06-01_2026-10-17.csv.gz")

for (n in c("eia", "dam", "act", "loc", "wx", "cap", "curt", "rep")) cat(sprintf("%-5s %s\n", n, paste(dim(get(n)), collapse = " x ")))
```

Expected shapes are the same as in the Python table in 3.2. To read from a clone, set `BASE <- "data/raw/"` (run from the repo folder, or open the project in RStudio).

`readr` turns blank cells into `NA` and trims spaces, so the 860M file's single-space blanks become `NA` without extra work. Reading `cap` as text is safest because several columns mix numbers and blanks; convert with `as.numeric()` where you need numbers, for example `cap |> mutate(nameplate = as.numeric(`Nameplate Capacity (MW)`))`.

### 4.3 A first look at each dataset

```r
# EIA: gaps, negatives, average day
full <- seq(ymd_h("2024-01-01 00", tz = "UTC"), ymd_h("2026-10-17 23", tz = "UTC"), by = "hour")
cat("missing hours:", length(setdiff(as.numeric(full), as.numeric(eia$period))), "\n")      # 24
cat("negative hours:", sum(eia$value < 0), "\n")                                             # 9461
eia |> mutate(hr = hour(with_tz(period, "America/Los_Angeles"))) |> group_by(hr) |> summarise(mean_mwh = round(mean(value))) |> print(n = 24)

# CAISO day-ahead
dam |> count(TRADING_HUB, RENEWABLE_TYPE)

# Weather: nulls and ranges
colSums(is.na(wx))[colSums(is.na(wx)) > 0]                                                   # the 129-hour gap
summary(wx$shortwave_radiation_previous_day2)

# Capacity: total nameplate MW by monthly file
cap |> mutate(mw = as.numeric(`Nameplate Capacity (MW)`)) |> group_by(file_month) |> summarise(total_mw = round(sum(mw), 1)) |> tail(3)

# Curtailment workbooks: solar MWh by month (5-minute MW divided by 12)
curt |> mutate(month = format(as_date(substr(Date, 1, 10)), "%Y-%m")) |> group_by(month) |> summarise(solar_mwh = round(sum(`Solar Curtailment`, na.rm = TRUE) / 12)) |> head()
```

### 4.4 Put the files on one clock, then merge

Same steps and same result as 3.4.

```r
library(tidyr)

# 1. Target, on the hour-ending clock
eia <- read_csv(paste0(BASE, "eia_ciso_solar_hourly_2024-01-01_2026-10-17.csv"), show_col_types = FALSE,
                col_types = cols_only(period = col_datetime("%Y-%m-%dT%H"), value = col_double())) |>
  transmute(hour_end_utc = period - hours(1), eia_mw = value)

# 2. CAISO day-ahead forecast: Solar only, the three hubs summed, kept only if all three are present
dam <- read_csv(paste0(BASE, "caiso_dam_solar_forecast_2024-01-01_2026-10-17.csv.gz"), show_col_types = FALSE,
                col_types = cols_only(INTERVALENDTIME_GMT = col_character(), TRADING_HUB = col_character(),
                                      RENEWABLE_TYPE = col_character(), MW = col_double())) |>
  filter(RENEWABLE_TYPE == "Solar", TRADING_HUB %in% c("NP15", "SP15", "ZP26")) |>
  mutate(hour_end_utc = ymd_hms(INTERVALENDTIME_GMT, tz = "UTC")) |>
  group_by(hour_end_utc) |>
  summarise(n_hubs = n(), caiso_dam_mw = sum(MW), .groups = "drop") |>
  filter(n_hubs == 3) |> select(-n_hubs)

# 3. Weather: points with a capacity share, averaged with those shares
loc <- read_csv(paste0(BASE, "weather_locations.csv"), show_col_types = FALSE) |> filter(caiso_solar_capacity_share > 0)
wx <- lapply(seq_len(nrow(loc)), function(i)
  read(sprintf("openmeteo/openmeteo_prev_runs_ecmwf_ifs025_%s_2024-03-08_2026-10-17.csv.gz", loc$location_id[i]),
       col_types = cols(time_utc = col_datetime("%Y-%m-%dT%H:%M"), .default = col_double(),
                        location_id = col_character(), model = col_character())) |>
    mutate(w = loc$caiso_solar_capacity_share[i])) |> bind_rows()
wxavg <- wx |> group_by(hour_end_utc = time_utc) |>
  summarise(across(ends_with("_previous_day2"), ~ weighted.mean(.x, w, na.rm = TRUE)), .groups = "drop")

# 4. Join and add Pacific time
df <- eia |> inner_join(dam, by = "hour_end_utc") |> inner_join(wxavg, by = "hour_end_utc") |>
  mutate(pacific = with_tz(hour_end_utc, "America/Los_Angeles"))
dim(df)                                                          # 22799 x 13
cor(df$eia_mw, df$shortwave_radiation_previous_day2)             # about 0.93
```

## 5. First questions to ask the data

A short list to start your own exploration. Each one can be answered with the code above.

1. **Shape of a day.** Plot average solar output by Pacific hour for each month. Where does the curve peak, and how does it move between December and July?
2. **Shape of a year.** Plot daily total output. How big is the gap between a clear and a cloudy day in the same month?
3. **Gaps.** Which hours or days are absent in each file (FAQ section 6)? Do any fall in the test period?
4. **Night values.** How many negative and deep-night positive EIA values are there per month, before and after the timing rule?
5. **CAISO vs EIA.** Compare the day-ahead total with EIA by day and by hour. Is CAISO high or low on average, and when is it worst?
6. **Weather vs output.** How well do shortwave radiation and cloud cover (day 2) explain output? Compare the day-1 and day-2 columns.
7. **Capacity.** How does output per MW of capacity change over 2024 to 2026?
8. **Curtailment.** In which months and hours is solar curtailed, and how large is it next to output?
9. **Baseline.** Build persistence (same hour yesterday) and score it with the project metrics. This is the floor to beat.

Keep the test period (from 2026-04-10) out of every exploration that leads to a modeling choice.

## 6. Pitfalls

| Pitfall | What to do |
|---|---|
| Joining on text timestamps | Convert to UTC date-times first. The three sources write times in three formats (`2024-01-01T00`, `2023-12-31T08:00:00-00:00`, `2024-03-08T00:00`). |
| EIA label read as hour ending | Apply the working rule (label L is the hour ending at L minus 1 hour) in processing, never in the raw file. |
| Rebuilding time from `OPR_DT` and `OPR_HR` | Use the UTC columns. `OPR_HR` follows the local clock and breaks on clock-change days. |
| Counting a missing row as zero | Absent rows are not zeros. Build a full hourly calendar and look at what is missing. |
| Summing OASIS hubs blindly | Keep Solar, hubs NP15, SP15, ZP26 only, and require all three. Leave out `AVA_` and wind. |
| Mixing capacity scopes | Pick all CISO, PV only or California only, and say which in every chart. |
| Using the 860M file unchanged | Blanks are single spaces; read with `na_values=[" "]` (Python). Select one scope before you sum. |
| Treating curtailment `Date` as a timestamp | Its time of day is an export artifact. Use the first 10 characters. |
| Loading all 51 weather files at once | About 420 MB in pandas. Load only the columns you need (`usecols`) and cast to `float32`, or average the points as in 3.4. |
| Tuning on the test period | The latest 191 days (from 2026-04-10) are locked. |
| Editing a raw file | Never. Fix problems in code and describe them in your notebook or in `PULL_LOG.md`. |
| Forgetting credit | Reports and slides that use weather must say "Weather data by Open-Meteo.com". |

## 7. If a download fails

- **Connection reset (`WinError 10054`) or timeouts from Python.** Wait a few seconds and retry; the `read()` helpers above do this. This happened to Raúl's machine on some GitHub reads while a browser download of the same file worked. The cause was not found. If it keeps happening, clone the repo and read `data/raw/` locally.
- **A certificate error behind antivirus or a company proxy.** Some security software re-signs web traffic with its own certificate, which Python does not trust. Install `truststore` (`pip install truststore`) and add `import truststore; truststore.inject_into_ssl()` before your first read. Do not turn certificate checking off.
- **404 on a file.** Check the exact name in `data/README.md`. Names are case-sensitive.
- **The newest file is not on GitHub yet.** GitHub can take a few minutes after a merge.

## 8. Where to save your work

| What | Where |
|---|---|
| Exploration notebooks | `notebooks/` (name them `yourname_topic.ipynb`) |
| Reusable code | `src/` |
| Cleaned and merged tables | `data/processed/` (not committed; every teammate rebuilds their own) |
| Charts for slides or the report | `reports/figures/` |

Work on a branch (`git checkout -b your-name/topic`), commit small, and open a pull request. Never commit API keys or processed data.
