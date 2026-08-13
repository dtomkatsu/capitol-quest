#!/usr/bin/env python3
"""Prepare neighbor-island geodata: coastlines + urban footprints.

Inputs (downloaded once, not committed — pass their paths):
  coast_n83.shp   Hawaiʻi Statewide GIS coastline (UTM 4N NAD83)
                  https://files.hawaii.gov/dbedt/op/gis/data/coast_n83.shp.zip
  cb_2020_us_ua20_500k.shp   Census 2020 urban areas, 1:500k cartographic
                  https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_ua20_500k.zip

Outputs (committed):
  data/coastlines/<slug>.geojson   MultiPolygon per island, WGS84
  data/urban_areas_hi.geojson      Hawaiʻi urban-area polygons, WGS84

Oʻahu keeps its existing higher-detail outline (data/island_outline.geojson
from Mahele-Atlas) and its road-density urban source; this script only
serves the other seven islands.

Usage:
  python3 tools/prep_islands_data.py <coast.shp> <ua.shp>
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent

# island bounding boxes, WGS84 (lon0, lat0, lon1, lat1)
BBOXES = {
    "niihau": (-160.29, 21.75, -159.99, 22.03),
    "kauai": (-159.81, 21.84, -159.27, 22.25),
    "molokai": (-157.34, 21.03, -156.69, 21.26),
    "lanai": (-157.08, 20.71, -156.78, 20.99),
    "kahoolawe": (-156.72, 20.47, -156.52, 20.62),
    "maui": (-156.71, 20.56, -155.96, 21.05),
    "hawaii": (-156.12, 18.88, -154.74, 20.29),
}
MIN_KM2 = 0.5      # drop offshore islets below this (sub-tile anyway)


def main():
    coast_shp, ua_shp = sys.argv[1], sys.argv[2]

    coast = gpd.read_file(coast_shp).to_crs(4326)
    parts = coast.explode(index_parts=False).reset_index(drop=True)
    # polygon area in km² via equal-area projection
    km2 = parts.to_crs(6933).geometry.area / 1e6
    out_dir = ROOT / "data" / "coastlines"
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, (x0, y0, x1, y1) in BBOXES.items():
        c = parts.geometry.centroid
        m = (c.x >= x0) & (c.x <= x1) & (c.y >= y0) & (c.y <= y1) & \
            (km2 >= MIN_KM2)
        sel = parts[m]
        if sel.empty:
            raise SystemExit(f"no polygons for {slug}")
        merged = gpd.GeoSeries([sel.union_all()], crs=4326)
        merged.to_file(out_dir / f"{slug}.geojson", driver="GeoJSON")
        print(f"{slug}: {m.sum()} polygons, "
              f"{km2[m].sum():.0f} km² -> coastlines/{slug}.geojson")

    ua = gpd.read_file(ua_shp)
    hi = ua[ua["NAME20"].str.endswith(", HI")].to_crs(4326)
    hi[["NAME20", "geometry"]].to_file(
        ROOT / "data" / "urban_areas_hi.geojson", driver="GeoJSON")
    print(f"urban areas: {len(hi)} -> data/urban_areas_hi.geojson")
    for n in sorted(hi["NAME20"]):
        print("  ", n)


if __name__ == "__main__":
    main()
