"""Weather locations for source 3: a 1-degree grid clipped to the California boundary.

The boundary is the California feature (iso_3166_2 = US-CA) of Natural Earth 1:10m
Admin 1 states and provinces, version v5.1.2. The full Natural Earth file is downloaded
to data/raw/.cache/naturalearth/ (not committed); only the California extract is saved to
data/raw/reference/california_boundary_ne10m.geojson.

Grid points sit at the centres of 1-degree cells (latitudes 32.5, 33.5, ..., longitudes
-124.5, -123.5, ...). A point is kept if it falls inside any California polygon (mainland or
island).

Cluster points (CLUSTER_POINTS) were chosen on 2026-10-28 from the EIA 860M CISO solar plants
(source 4, file month 2026-09, all CISO including Arizona and Nevada, weighted by nameplate):
one at a time, each at the location that brought the most still-uncovered nameplate within
50 km of a weather point, until 95% was within 50 km in both 2024-01 and 2026-09. Approved by
Raúl as "option B". See data/raw/PULL_LOG.md.

caiso_solar_capacity_share is each point's share of CISO solar nameplate in the 860M file for
SHARE_MONTH whose nearest weather point it is. It is static: computed for that one month and
not updated as plants are added.

Run from the repo root:
    .venv\\Scripts\\python -m src.data_pull.weather_locations
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath

from src.data_pull.common import CACHE_DIR, RAW_DIR, get_logger, http_get, write_bytes_atomic, write_csv

NE_VERSION = "v5.1.2"
NE_URL = (f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{NE_VERSION}/"
          "geojson/ne_10m_admin_1_states_provinces.geojson")
NE_CACHE = CACHE_DIR / "naturalearth" / f"ne_10m_admin_1_states_provinces_{NE_VERSION}.geojson"
CA_FILE = RAW_DIR / "reference" / "california_boundary_ne10m.geojson"
LOCATIONS_FILE = RAW_DIR / "weather_locations.csv"
CAPACITY_FILE = RAW_DIR / "eia860m_solar_ciso_capacity_by_month.csv"
STEP = 1.0
SHARE_MONTH = "2026-09"
CLUSTER_POINTS = [  # (location_id, latitude, longitude, area)
    ("c01", 35.00, -118.04, "Kern, Los Angeles CA (Antelope Valley, Mojave)"),
    ("c02", 33.66, -114.74, "Riverside CA (Blythe, Desert Center)"),
    ("c03", 32.77, -115.78, "Imperial, San Diego CA (Imperial Valley)"),
    ("c04", 34.96, -117.13, "San Bernardino CA (Daggett, Hinkley)"),
    ("c05", 36.07, -119.56, "Kings, Tulare CA"),
    ("c06", 32.97, -113.49, "Yuma AZ"),
    ("c07", 33.34, -112.88, "Maricopa AZ"),
    ("c08", 35.46, -119.19, "Kern, Tulare CA (southern San Joaquin)"),
    ("c09", 37.36, -120.72, "Merced, Stanislaus CA"),
    ("c10", 35.78, -114.97, "Clark NV, San Bernardino CA"),
]
log = get_logger("weather_locations")


def california_feature() -> dict:
    """The California boundary as a GeoJSON Feature, from the extract or (first run) from Natural Earth."""
    if CA_FILE.exists():
        return json.loads(CA_FILE.read_text(encoding="utf-8"))["features"][0]
    if not NE_CACHE.exists():
        write_bytes_atomic(http_get(NE_URL, logger=log).content, NE_CACHE)
        log.info("downloaded %s", NE_CACHE.name)
    ne = json.loads(NE_CACHE.read_text(encoding="utf-8"))
    ca = [f for f in ne["features"] if f["properties"].get("iso_3166_2") == "US-CA"]
    if len(ca) != 1:
        raise RuntimeError(f"expected one US-CA feature in Natural Earth, found {len(ca)}")
    feat = {"type": "Feature",
            "properties": {k: ca[0]["properties"].get(k) for k in ("name", "iso_3166_2", "adm0_a3", "ne_id")}
            | {"source": f"Natural Earth 1:10m Admin 1 states and provinces, {NE_VERSION}", "source_url": NE_URL},
            "geometry": ca[0]["geometry"]}
    out = {"type": "FeatureCollection", "features": [feat]}
    write_bytes_atomic((json.dumps(out, separators=(",", ":")) + "\n").encode("utf-8"), CA_FILE)
    log.info("wrote California extract %s", CA_FILE)
    return feat


def inside(geometry: dict, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """True where (lon, lat) falls inside the (Multi)Polygon: inside an outer ring and not in its holes."""
    polys = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    pts = np.column_stack([lon, lat])
    result = np.zeros(len(pts), dtype=bool)
    for rings in polys:
        hit = MplPath(np.asarray(rings[0])).contains_points(pts)
        for hole in rings[1:]:
            hit &= ~MplPath(np.asarray(hole)).contains_points(pts)
        result |= hit
    return result


def grid_points(feature: dict) -> pd.DataFrame:
    coords = np.vstack([np.asarray(r) for p in (feature["geometry"]["coordinates"]
                        if feature["geometry"]["type"] == "MultiPolygon" else [feature["geometry"]["coordinates"]])
                        for r in p])
    lon_min, lat_min = coords.min(axis=0)
    lon_max, lat_max = coords.max(axis=0)
    lats = np.arange(np.floor(lat_min) + STEP / 2, lat_max, STEP)
    lons = np.arange(np.floor(lon_min) + STEP / 2, lon_max, STEP)
    lo, la = np.meshgrid(lons, lats)
    lo, la = lo.ravel().round(4), la.ravel().round(4)
    keep = inside(feature["geometry"], lo, la)
    df = pd.DataFrame({"latitude": la[keep], "longitude": lo[keep]}).sort_values(
        ["latitude", "longitude"], ascending=[False, True], ignore_index=True)
    df.insert(0, "location_id", [f"g{i + 1:02d}" for i in range(len(df))])
    df["type"] = "grid"
    df["caiso_solar_capacity_share"] = ""  # filled after EIA 860M (source 4)
    log.info("grid: %d candidate points in the bounding box, %d inside California", len(lo), len(df))
    return df


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def capacity_shares(locs: pd.DataFrame) -> pd.Series:
    """Share of CISO solar nameplate (860M, SHARE_MONTH) nearest to each location."""
    cap = pd.read_csv(CAPACITY_FILE, dtype=str, keep_default_na=False)
    cap = cap[cap.file_month == SHARE_MONTH]
    if cap.empty:
        log.warning("no 860M rows for %s; capacity shares left blank", SHARE_MONTH)
        return pd.Series("", index=locs.index)
    plants = pd.DataFrame({"plant": cap["Plant ID"],
                           "lat": pd.to_numeric(cap["Latitude"]), "lon": pd.to_numeric(cap["Longitude"]),
                           "mw": pd.to_numeric(cap["Nameplate Capacity (MW)"])})
    plants = plants.groupby("plant").agg(lat=("lat", "first"), lon=("lon", "first"), mw=("mw", "sum"))
    d = haversine_km(plants.lat.values[:, None], plants.lon.values[:, None],
                     locs.latitude.values[None, :], locs.longitude.values[None, :])
    plants["nearest"] = locs.location_id.values[d.argmin(axis=1)]
    share = plants.groupby("nearest").mw.sum() / plants.mw.sum()
    return locs.location_id.map(share).fillna(0.0).round(6)


def build() -> Path:
    feat = california_feature()
    locs = grid_points(feat)
    clusters = pd.DataFrame([{"location_id": i, "latitude": la, "longitude": lo, "type": "cluster"}
                             for i, la, lo, _ in CLUSTER_POINTS])
    locs = pd.concat([locs, clusters], ignore_index=True)
    if CAPACITY_FILE.exists():
        locs["caiso_solar_capacity_share"] = capacity_shares(locs)
        log.info("capacity shares from %s, file month %s", CAPACITY_FILE.name, SHARE_MONTH)
    write_csv(locs, LOCATIONS_FILE)
    log.info("wrote %s (%d points: %d grid, %d cluster)", LOCATIONS_FILE, len(locs),
             (locs.type == "grid").sum(), (locs.type == "cluster").sum())
    return LOCATIONS_FILE


if __name__ == "__main__":
    build()
