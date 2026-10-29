"""Source 3: Open-Meteo Previous Runs API, weather forecasts made 1 and 2 days before each hour.

One model for the whole period and both offsets: ecmwf_ifs025 (Raúl, 2026-10-28). Its
previous-runs archive has radiation for both offsets from 2024-03-08 (first full UTC day), so
no request goes earlier than that, whatever --start says.

Requests are one location and one calendar quarter each. Each JSON response is cached in
data/raw/.cache/openmeteo/<model>/, so a re-run skips finished chunks. Open-Meteo counts a
request with more than 10 variables or more than 14 days as several calls (fractionally);
a ledger of these weighted calls (data/raw/.cache/openmeteo/call_ledger.csv) keeps the pull
under the free-tier limits across runs. On HTTP 429 the request waits and retries.

Output: one gzip CSV per location,
data/raw/openmeteo/openmeteo_prev_runs_<model>_<location_id>_<start>_<end>.csv.gz, with
time_utc, location_id, latitude, longitude (the requested point), model, model_latitude,
model_longitude, model_elevation (the grid cell the API used), then the weather columns.
Radiation is the mean over the preceding hour (Open-Meteo docs; checked against the sun).

Run from the repo root:
    .venv\\Scripts\\python -m src.data_pull.openmeteo --start 2024-03-08 --end 2026-10-17
"""
import argparse
import json
import time
from pathlib import Path

import pandas as pd

from src.data_pull.common import (CACHE_DIR, RAW_DIR, PullError, add_date_args, get_logger, http_get,
                                  write_bytes_atomic, write_csv)

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODEL = "ecmwf_ifs025"
MODEL_START = "2024-03-08"  # first full UTC day with radiation for both offsets in this model
VARIABLES = ["cloud_cover", "shortwave_radiation", "direct_radiation", "diffuse_radiation",
             "direct_normal_irradiance", "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
             "precipitation"]
OFFSETS = (1, 2)
HOURLY = [f"{v}_previous_day{d}" for v in VARIABLES for d in OFFSETS]
# Free tier: 600 / minute, 5,000 / hour, 10,000 / day. Stay below each with a margin.
LIMITS = {60: 500, 3600: 4500, 86400: 9500}
CACHE = CACHE_DIR / "openmeteo" / MODEL
LEDGER = CACHE_DIR / "openmeteo" / "call_ledger.csv"
OUT_DIR = RAW_DIR / "openmeteo"
LOCATIONS = RAW_DIR / "weather_locations.csv"
log = get_logger("openmeteo")


def weight(n_vars: int, days: int) -> float:
    """Open-Meteo's weighted call count for one location (pricing page, read 2026-10-28)."""
    return max(1.0, n_vars / 10) * max(1.0, days / 14)


def quarters(start: pd.Timestamp, end: pd.Timestamp):
    d = start
    while d <= end:
        q_end = min(d + pd.offsets.QuarterEnd(0), end)
        yield d, q_end
        d = q_end + pd.Timedelta(days=1)


def _ledger() -> list[tuple[float, float]]:
    if not LEDGER.exists():
        return []
    rows = [l.split(",") for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [(float(t), float(w)) for t, w in rows]


def _record(w: float) -> None:
    now = time.time()
    keep = [(t, x) for t, x in _ledger() if now - t < 86400] + [(now, w)]
    write_bytes_atomic("".join(f"{t:.3f},{x:.4f}\n" for t, x in keep).encode("utf-8"), LEDGER)


def wait_for_budget(w: float) -> None:
    """Sleep until a request of weight w fits under every limit."""
    while True:
        now = time.time()
        led = _ledger()
        waits = []
        for window, cap in LIMITS.items():
            inside = sorted((t, x) for t, x in led if now - t < window)
            used = sum(x for _, x in inside)
            if used + w > cap:
                # wait until enough old calls leave the window
                free, need = 0.0, used + w - cap
                for t, x in inside:
                    free += x
                    if free >= need:
                        waits.append(t + window - now + 1)
                        break
        if not waits:
            return
        pause = max(waits)
        log.info("call budget: waiting %.0f s", pause)
        time.sleep(min(pause, 600))


def fetch(lat: float, lon: float, a: pd.Timestamp, b: pd.Timestamp) -> dict:
    w = weight(len(HOURLY), (b - a).days + 1)
    wait_for_budget(w)
    params = {"latitude": lat, "longitude": lon, "models": MODEL, "timezone": "UTC",
              "start_date": f"{a:%Y-%m-%d}", "end_date": f"{b:%Y-%m-%d}", "hourly": ",".join(HOURLY)}
    _record(w)  # count the call before sending, so a crash never under-counts
    r = http_get(URL, params=params, logger=log, retries=8, backoff=60)
    j = r.json()
    if j.get("error") or "hourly" not in j:
        raise PullError(f"Open-Meteo error for {lat},{lon} {a:%Y-%m-%d}..{b:%Y-%m-%d}: {j.get('reason')}")
    missing = [k for k in HOURLY if k not in j["hourly"]]
    if missing:
        raise PullError(f"Open-Meteo response lacks columns {missing}")
    return j


def to_frame(j: dict, loc: pd.Series) -> pd.DataFrame:
    h = j["hourly"]
    df = pd.DataFrame({"time_utc": h["time"]})
    df["location_id"] = loc.location_id
    df["latitude"] = loc.latitude
    df["longitude"] = loc.longitude
    df["model"] = MODEL
    df["model_latitude"] = j.get("latitude")
    df["model_longitude"] = j.get("longitude")
    df["model_elevation"] = j.get("elevation")
    for k in HOURLY:
        # object dtype keeps each value as the API sent it (an integer stays "18", not "18.0",
        # even when the column has nulls); nulls are written as empty cells
        df[k] = pd.Series(h[k], dtype=object)
    return df


def pull(start: str, end: str, out_dir: Path, ids: list[str] | None = None) -> list[Path]:
    a0 = max(pd.Timestamp(start), pd.Timestamp(MODEL_START))
    b0 = pd.Timestamp(end)
    if a0 != pd.Timestamp(start):
        log.info("start moved from %s to %s (first full day of %s previous-runs radiation)", start, MODEL_START, MODEL)
    locs = pd.read_csv(LOCATIONS, dtype={"location_id": str})
    if ids:
        locs = locs[locs.location_id.isin(ids)]
    CACHE.mkdir(parents=True, exist_ok=True)
    paths = []
    for _, loc in locs.iterrows():
        parts, units = [], None
        for a, b in quarters(a0, b0):
            f = CACHE / f"{loc.location_id}_{a:%Y-%m-%d}_{b:%Y-%m-%d}.json"
            if f.exists():
                j = json.loads(f.read_text(encoding="utf-8"))
            else:
                j = fetch(loc.latitude, loc.longitude, a, b)
                write_bytes_atomic(json.dumps(j).encode("utf-8"), f)
                log.info("fetched %s %s..%s", loc.location_id, f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}")
                time.sleep(1)
            units = j.get("hourly_units", units)
            parts.append(to_frame(j, loc))
        out = pd.concat(parts, ignore_index=True)
        path = out_dir / f"openmeteo_prev_runs_{MODEL}_{loc.location_id}_{a0:%Y-%m-%d}_{b0:%Y-%m-%d}.csv.gz"
        write_csv(out, path)
        paths.append(path)
        log.info("wrote %s: %d rows", path.name, len(out))
    if units:
        write_bytes_atomic(json.dumps(units, indent=1).encode("utf-8"), CACHE / "hourly_units.json")
    return paths


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_date_args(p)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR, help="folder for the per-location files")
    p.add_argument("--ids", nargs="+", help="only these location_id values (default: all in weather_locations.csv)")
    a = p.parse_args()
    pull(a.start, a.end, a.out_dir, a.ids)
