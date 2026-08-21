#!/usr/bin/env python3
"""Bake a real DEM of the island chain for the map pipeline.

The mountains were hand-modeled (ridge polylines + distance falloff),
which puts them in the right PLACE but gives every range the same
tent-shaped anatomy. The real islands don't look like that: the Koʻolau
is a knife-edged pali with one gentle side, Haleakalā is a whale-backed
shield with a hole in the top, and Mauna Loa is fifty kilometres of
2-degree slope. This tool replaces the model with measurement.

Source
  Terrain Tiles on AWS (open data, no auth) — "terrarium" encoding,
  a global DEM mosaic (SRTM et al.) served as 256px web-mercator PNGs:
    https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png
    elevation_m = R*256 + G + B/256 - 32768
  z=10 (~140 m/px at this latitude) more than covers the 250 m target.

Output — the SAME grid convention (and exact affine) as the rainfall
raster, so the two fields are pixel-aligned and share sampling code:
  data/elevation_m.png    16-bit grayscale, metres (ocean clipped to 0)
  data/elevation_m.json   affine + provenance header

Raw tiles cache in data/raw/elevation/ (gitignored); only tiles whose
bounds intersect an island bbox are fetched (~30 of the ~250 covering
the full frame — the rest are open ocean).

Usage:
  python3 tools/build_elevation.py            # fetch missing, then bake
  python3 tools/build_elevation.py --refresh  # re-download tiles
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "elevation"
OUT_PNG = ROOT / "data" / "elevation_m.png"
OUT_HDR = ROOT / "data" / "elevation_m.json"

Z = 10
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

# match data/rainfall_mm.json exactly — one grid, two fields
RF_HDR = ROOT / "data" / "rainfall_mm.json"

# island bboxes (prep_islands_data.py's, plus Oʻahu/Niʻihau), padded a
# touch so coastal cells never sit on a missing tile
BBOXES = [
    (-160.29, 21.75, -159.99, 22.03),   # niihau
    (-159.81, 21.84, -159.27, 22.25),   # kauai
    (-158.32, 21.20, -157.60, 21.78),   # oahu
    (-157.34, 21.03, -156.69, 21.26),   # molokai
    (-157.08, 20.71, -156.78, 20.99),   # lanai
    (-156.72, 20.47, -156.52, 20.62),   # kahoolawe
    (-156.71, 20.56, -155.96, 21.05),   # maui
    (-156.12, 18.88, -154.74, 20.29),   # hawaii
]
PAD = 0.03

QA = [
    ("Mauna Kea summit", -155.4681, 19.8206, 3900, 4210),
    ("Mauna Loa summit", -155.6054, 19.4756, 3900, 4172),
    ("Haleakalā summit", -156.2533, 20.7097, 2850, 3060),
    ("Waiʻaleʻale", -159.4983, 22.0722, 1400, 1600),
    ("Kaʻala (Oʻahu high pt)", -158.1445, 21.5069, 1100, 1230),
    # a knife-edge summit loses ~7% to the z10 sampling — the floor is
    # set accordingly (Kōnāhuanui is 960 m; the grid reads ~894)
    ("Koʻolau crest (Kōnāhuanui)", -157.7876, 21.3565, 800, 970),
    ("Honolulu waterfront", -157.8583, 21.3069, 0, 30),
    ("Puʻu Moaulanui, Kahoʻolawe", -156.5723, 20.5605, 380, 460),
]


def tile_of(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    yr = math.radians(lat)
    y = (1.0 - math.log(math.tan(yr) + 1.0 / math.cos(yr)) / math.pi) / 2 * n
    return x, y


def wanted_tiles():
    tiles = set()
    for x0, y0, x1, y1 in BBOXES:
        ax, ay1 = tile_of(x0 - PAD, y0 - PAD, Z)   # south -> larger y
        bx, ay0 = tile_of(x1 + PAD, y1 + PAD, Z)
        for tx in range(int(ax), int(bx) + 1):
            for ty in range(int(ay0), int(ay1) + 1):
                tiles.add((tx, ty))
    return sorted(tiles)


def fetch(refresh=False):
    RAW.mkdir(parents=True, exist_ok=True)
    tiles = wanted_tiles()
    todo = [(x, y) for x, y in tiles
            if refresh or not (RAW / f"z{Z}_{x}_{y}.png").exists()]
    if todo:
        print(f"fetching {len(todo)}/{len(tiles)} terrarium tiles (z{Z})…")
    for i, (x, y) in enumerate(todo):
        p = RAW / f"z{Z}_{x}_{y}.png"
        with urllib.request.urlopen(URL.format(z=Z, x=x, y=y),
                                    timeout=60) as r:
            p.write_bytes(r.read())
        if i % 10 == 9:
            print(f"  {i + 1}/{len(todo)}")
            time.sleep(0.2)           # be polite to the open bucket
    return tiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    tiles = fetch(args.refresh)

    rf = json.loads(RF_HDR.read_text())
    W, H = rf["w"], rf["h"]
    lon0, lat0 = rf["lon0"], rf["lat0"]
    dlon, dlat = rf["dlon"], rf["dlat"]

    # mosaic the fetched tiles into one sparse mercator frame
    xs = [t[0] for t in tiles]
    ys = [t[1] for t in tiles]
    tx0, ty0 = min(xs), min(ys)
    mw = (max(xs) - tx0 + 1) * 256
    mh = (max(ys) - ty0 + 1) * 256
    mos = np.full((mh, mw), -32768.0, np.float32)
    for x, y in tiles:
        p = RAW / f"z{Z}_{x}_{y}.png"
        a = np.asarray(Image.open(p).convert("RGB"), np.float32)
        elev = a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0
        mos[(y - ty0) * 256:(y - ty0 + 1) * 256,
            (x - tx0) * 256:(x - tx0 + 1) * 256] = elev
    print(f"mosaic {mw}x{mh} from {len(tiles)} tiles")

    # sample the WGS84 grid (bilinear in mercator px)
    lons = lon0 + dlon * np.arange(W, dtype=np.float64)
    lats = lat0 + dlat * np.arange(H, dtype=np.float64)
    n = 2.0 ** Z
    px = (lons + 180.0) / 360.0 * n - tx0            # tile units
    lr = np.radians(lats)
    py = (1.0 - np.log(np.tan(lr) + 1.0 / np.cos(lr)) / math.pi) / 2 * n - ty0
    px = px * 256.0 - 0.5
    py = py * 256.0 - 0.5
    x0 = np.clip(np.floor(px).astype(np.int64), 0, mw - 2)
    y0 = np.clip(np.floor(py).astype(np.int64), 0, mh - 2)
    fx = np.clip(px - x0, 0, 1).astype(np.float32)[None, :]
    fy = np.clip(py - y0, 0, 1).astype(np.float32)[:, None]
    X0 = x0[None, :]
    Y0 = y0[:, None]
    v = (mos[Y0, X0] * (1 - fx) * (1 - fy) + mos[Y0, X0 + 1] * fx * (1 - fy) +
         mos[Y0 + 1, X0] * (1 - fx) * fy + mos[Y0 + 1, X0 + 1] * fx * fy)
    # un-fetched ocean tiles read as -32768; everything below sea level
    # (real bathymetry included) clamps to 0 — the map never needs it
    elev = np.clip(v, 0, 65535).astype(np.uint16)
    land = elev > 0
    print(f"grid {W}x{H}, {land.sum()/1e3:.0f}k cells above sea level, "
          f"max {elev.max()} m")

    Image.fromarray(elev, "I;16").save(OUT_PNG, optimize=True)
    OUT_HDR.write_text(json.dumps({
        "units": "m",
        "variable": "elevation above sea level (below-sea clipped to 0)",
        "source": f"Terrain Tiles on AWS (terrarium z{Z}), "
                  "https://registry.opendata.aws/terrain-tiles/",
        "w": W, "h": H,
        "lon0": lon0, "lat0": lat0, "dlon": dlon, "dlat": dlat,
        "note": "pixel-aligned with data/rainfall_mm.png",
    }, indent=1))
    print(f"wrote {OUT_PNG.relative_to(ROOT)} "
          f"({OUT_PNG.stat().st_size/1e6:.1f}MB) + "
          f"{OUT_HDR.relative_to(ROOT)}")

    import elevation
    elevation.reload()
    bad = 0
    for name, lon, lat, lo, hi in QA:
        got = float(elevation.sample(np.array([lon]), np.array([lat]))[0])
        ok = lo <= got <= hi
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {name:28s} {got:6.0f} m "
              f"expect {lo}–{hi}")
    if bad:
        raise SystemExit(f"{bad} QA point(s) out of range")


if __name__ == "__main__":
    main()
