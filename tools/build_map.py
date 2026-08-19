#!/usr/bin/env python3
"""Build an island tile grid for Capitol Quest.

Classifies every tile of an island's grid (~320m/tile; larger on Maui and
Hawaiʻi — see tools/islands.py) into JRPG overworld terrain:

  water_deep, water_shallow, sand, grass, field, forest,
  mountain, urban, urban_dense

plus overlay flags (rail viaduct, Oʻahu only) and landmark/station
positions. All island-specific geography lives in tools/islands.py.

Usage:
  python3 tools/build_map.py                 # Oʻahu
  python3 tools/build_map.py --island maui
  python3 tools/build_map.py --all

Inputs (per island; see islands.py):
  outline geojson               real coastline polygon
  urban source                  "roads": ~/Revenue-Modeling-TOD road
                                centerlines -> density (Oʻahu)
                                "ua": data/urban_areas_hi.geojson (Census
                                2020 urban areas) + hand town spots
  data/rail_alignment.geojson   Skyline (Oʻahu only)
  data/stations.geojson

Outputs
  build/map_grid_<slug>.json    full grid for tools/render_map.py
  build/debug_map_<slug>.png    top-down colored QA render
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from islands import ISLANDS

def _load_geojson(path):
    """``json.load`` that transparently falls back to a sibling ``.gz``.

    Large source layers (e.g. the TOD repo's ``road_centerlines.geojson``) are
    stored gzipped to save disk; plain files win when both exist.
    """
    p = Path(path)
    if not p.exists():
        gz = p.with_name(p.name + ".gz")
        if gz.exists():
            with gzip.open(gz, "rt", encoding="utf-8") as fh:
                return json.load(fh)
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- grid
# North-up isometric: screen-up must be geographic north, so the tile grid
# axes run diagonally across geography. With screen x = (c-r)*16 and
# y = (c+r)*8, the +c axis heads SE and the +r axis heads SW; then
# x ∝ east and y ∝ -north, i.e. the island renders in true map orientation.
# These module globals are set per island in main().
COLS = ROWS = 288
LON_C, LAT_C = -157.965, 21.4825
KM_PER_LON = 103.8
KM_PER_LAT = 110.9
TILE_KM = 0.32
K = TILE_KM * math.sqrt(2.0)

TILE_W, TILE_H = 32, 16                # iso diamond, 2:1

# terrain ids (render order/priority handled in classify)
(WATER_DEEP, WATER_SHALLOW, SAND, GRASS, FIELD, FOREST, MOUNTAIN, URBAN,
 URBAN_DENSE, PEAK, WATER_MID) = range(11)
NAMES = ["water_deep", "water_shallow", "sand", "grass", "field",
         "forest", "mountain", "urban", "urban_dense", "peak", "water_mid"]


def smooth_noise(shape, seed=42, passes=6):
    """Seeded [0,1] noise, box-blurred smooth — for organic terrain edges."""
    rng = np.random.default_rng(seed)
    z = rng.random(shape, dtype=np.float32)
    for _ in range(passes):
        acc = np.zeros_like(z)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                acc += np.roll(np.roll(z, dr, 0), dc, 1)
        z = acc / 9.0
    z -= z.min()
    z /= z.max()
    return z


def lonlat_to_cell(lon, lat):
    e = (np.asarray(lon) - LON_C) * KM_PER_LON
    nn = (np.asarray(lat) - LAT_C) * KM_PER_LAT
    c = (e - nn) / K + COLS / 2
    r = (-e - nn) / K + ROWS / 2
    return c, r  # fractional


def cell_center_lonlat():
    cc, rr = np.meshgrid(np.arange(COLS) + 0.5, np.arange(ROWS) + 0.5)
    u = cc.ravel() - COLS / 2
    v = rr.ravel() - ROWS / 2
    e = K * (u - v) / 2.0
    nn = -K * (u + v) / 2.0
    lon = LON_C + e / KM_PER_LON
    lat = LAT_C + nn / KM_PER_LAT
    return lon, lat  # 1D length ROWS*COLS, row-major


# ------------------------------------------------- point in polygon
def rings_of(geom):
    if geom["type"] == "Polygon":
        return [np.asarray(r) for r in geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return [np.asarray(r) for poly in geom["coordinates"] for r in poly]
    raise ValueError(geom["type"])


def geom_of(gj):
    if gj.get("type") == "Feature":
        return gj["geometry"]
    if gj.get("type") == "FeatureCollection":
        feats = gj["features"]
        if len(feats) == 1:
            return feats[0]["geometry"]
        # merge into one MultiPolygon
        coords = []
        for f in feats:
            g = f["geometry"]
            coords += g["coordinates"] if g["type"] == "MultiPolygon" \
                else [g["coordinates"]]
        return {"type": "MultiPolygon", "coordinates": coords}
    return gj


def points_in_rings(px, py, rings):
    """Even-odd rule across all rings (holes handled automatically)."""
    try:
        from matplotlib.path import Path as MplPath
        inside = np.zeros(px.shape[0], bool)
        pts = np.column_stack([px, py])
        for ring in rings:
            inside ^= MplPath(ring[:, :2]).contains_points(pts)
        return inside
    except ImportError:
        pass
    inside = np.zeros(px.shape[0], bool)
    for ring in rings:
        x, y = ring[:, 0], ring[:, 1]
        n = len(ring) - 1
        for i in range(n):
            x1, y1, x2, y2 = x[i], y[i], x[i + 1], y[i + 1]
            if y1 == y2:
                continue
            m = (y1 > py) != (y2 > py)
            xin = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            inside[m] ^= px[m] < xin[m]
    return inside


# ------------------------------------------------- distance to polyline (km)
def dist_to_polyline_km(lon, lat, line):
    """lon/lat 1D arrays; line list of (lon,lat). Returns km distances."""
    px = lon * KM_PER_LON
    py = lat * KM_PER_LAT
    best = np.full(lon.shape[0], 1e9)
    pts = [(x * KM_PER_LON, y * KM_PER_LAT) for x, y in line]
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        abx, aby = bx - ax, by - ay
        ab2 = abx * abx + aby * aby
        t = ((px - ax) * abx + (py - ay) * aby) / ab2
        t = np.clip(t, 0.0, 1.0)
        dx = px - (ax + t * abx)
        dy = py - (ay + t * aby)
        best = np.minimum(best, np.hypot(dx, dy))
    return best


# ------------------------------------------------- urban sources
def density_from_roads(lon, lat):
    roads_path = Path.home() / \
        "Revenue-Modeling-TOD/data/raw/road_centerlines.geojson"
    density = np.zeros((ROWS, COLS), np.float32)
    roads = _load_geojson(roads_path)
    for f in roads["features"]:
        g = f["geometry"]
        if g is None:
            continue
        lines = [g["coordinates"]] if g["type"] == "LineString" else \
                g["coordinates"] if g["type"] == "MultiLineString" else []
        for line in lines:
            arr = np.asarray(line, dtype=float)[:, :2]
            if len(arr) < 2:
                continue
            # sample each segment every ~80m
            for (x1, y1), (x2, y2) in zip(arr[:-1], arr[1:]):
                seg_km = math.hypot((x2 - x1) * KM_PER_LON,
                                    (y2 - y1) * KM_PER_LAT)
                k = max(1, int(seg_km / 0.08))
                ts = (np.arange(k) + 0.5) / k
                sx = x1 + ts * (x2 - x1)
                sy = y1 + ts * (y2 - y1)
                cf, rf = lonlat_to_cell(sx, sy)
                cc, rr = cf.astype(int), rf.astype(int)
                ok = (cc >= 0) & (cc < COLS) & (rr >= 0) & (rr < ROWS)
                np.add.at(density, (rr[ok], cc[ok]), 1.0)
    return density


def urban_from_ua(lon, lat, towns):
    """Census urban-area polygons + hand town spots -> urban mask."""
    urban = np.zeros(lon.shape[0], bool)
    ua_path = ROOT / "data" / "urban_areas_hi.geojson"
    pad = 0.05
    x0, x1 = lon.min() - pad, lon.max() + pad
    y0, y1 = lat.min() - pad, lat.max() + pad
    ua = _load_geojson(ua_path)
    for f in ua["features"]:
        g = f["geometry"]
        rings = rings_of(g)
        # cheap bbox reject against this island's window
        bx = np.concatenate([r[:, 0] for r in rings])
        by = np.concatenate([r[:, 1] for r in rings])
        if bx.max() < x0 or bx.min() > x1 or by.max() < y0 or by.min() > y1:
            continue
        urban |= points_in_rings(lon, lat, rings)
    for tlon, tlat, r_km in towns:
        d = np.hypot((lon - tlon) * KM_PER_LON, (lat - tlat) * KM_PER_LAT)
        urban |= d <= r_km
    return urban


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--island", default="oahu", choices=sorted(ISLANDS))
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    slugs = list(ISLANDS) if args.all else [args.island]
    for slug in slugs:
        build_island(slug)


def build_island(slug):
    cfg = ISLANDS[slug]
    global COLS, ROWS, LON_C, LAT_C, KM_PER_LON, KM_PER_LAT, TILE_KM, K
    COLS = ROWS = cfg["grid"]
    LON_C, LAT_C = cfg["center"]
    KM_PER_LON = cfg["km_per_lon"]
    KM_PER_LAT = cfg["km_per_lat"]
    TILE_KM = cfg["tile_km"]
    K = TILE_KM * math.sqrt(2.0)
    print(f"=== {slug}: grid {COLS}, {TILE_KM} km/tile ===")

    lon, lat = cell_center_lonlat()
    n = ROWS * COLS

    # ---- land / water
    outline = _load_geojson(ROOT / cfg["outline"])
    rings = rings_of(geom_of(outline))
    print(f"outline: {len(rings)} rings")
    land = points_in_rings(lon, lat, rings)
    print(f"land tiles: {land.sum()} / {n}")

    tiles = np.full(n, WATER_DEEP, np.uint8)
    tiles[land] = GRASS
    landg_pre = land.reshape(ROWS, COLS)

    # ---- ridges -> mountain / forest (noise-modulated widths)
    noise = smooth_noise((ROWS, COLS)).ravel()
    wob = 0.55 + 0.9 * noise          # 0.55..1.45 width multiplier
    mountain = np.zeros(n, bool)
    forest_src = np.zeros(n, bool)
    peak = np.zeros(n, bool)
    closeness = np.zeros(n, np.float32)
    for pts, w_mtn, w_forest, w_peak, h_mult in cfg["ridges"]:
        d = dist_to_polyline_km(lon, lat, pts)
        mountain |= land & (d < w_mtn * wob)
        forest_src |= land & (d < w_forest * wob)
        peak |= land & (d < w_peak)
        closeness = np.maximum(
            closeness, np.clip(1.0 - d / (w_mtn * wob), 0.0, 1.0) * h_mult)
    forest = forest_src & ~mountain
    for clon, clat, r_in, r_out, _rim_h in cfg["craters"]:
        d = np.hypot((lon - clon) * KM_PER_LON, (lat - clat) * KM_PER_LAT)
        rim = land & (d >= r_in) & (d < r_out)
        mountain |= rim
        forest &= ~rim

    # ---- ag fields (noisy edges so the bbox doesn't read as a rectangle)
    field = np.zeros(n, bool)
    noise2 = smooth_noise((ROWS, COLS), seed=7).ravel()
    for x0, y0, x1, y1 in cfg["fields"]:
        # distance to bbox edge in degrees, positive inside
        din = np.minimum.reduce([lon - x0, x1 - lon, lat - y0, y1 - lat])
        band = 0.018 * (0.4 + 1.2 * noise2)  # fuzzy shrink of the bbox rim
        field |= din > band - 0.018
    field &= land & ~mountain & ~forest

    # ---- urban
    if cfg["urban"] == "roads":
        density = density_from_roads(lon, lat).ravel()
        print(f"road density: max {density.max():.0f}, "
              f"p90 {np.percentile(density[density > 0], 90):.0f}")
        T_URBAN, T_DENSE = 20.0, 60.0
        urban = land & (density >= T_URBAN) & ~mountain
        # de-speckle: drop weak isolated tiles, fill surrounded gaps
        ug = urban.reshape(ROWS, COLS)
        dg = density.reshape(ROWS, COLS)
        for _ in range(2):
            nb = np.zeros((ROWS, COLS), np.int8)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr or dc:
                        nb += np.roll(np.roll(ug, dr, 0), dc, 1)
            ug = (ug & ((nb >= 3) | (dg >= 45))) | \
                (~ug & (nb >= 6) & landg_pre)
        urban = ug.ravel() & land & ~mountain
        core = cfg["core"]
        in_core = (lon >= core[0]) & (lon <= core[2]) & \
            (lat >= core[1]) & (lat <= core[3])
        dense = urban & in_core & (density >= T_DENSE)
    else:
        urban = urban_from_ua(lon, lat, cfg["towns"]) & land & ~mountain
        dense = np.zeros(n, bool)
    print(f"urban tiles: {urban.sum()}")
    # urban beats forest/field where it is real
    forest &= ~urban
    field &= ~urban
    peak &= ~urban

    tiles[forest] = FOREST
    tiles[field] = FIELD
    tiles[mountain] = MOUNTAIN
    tiles[urban] = URBAN
    tiles[dense] = URBAN_DENSE
    tiles[peak & (tiles == MOUNTAIN)] = PEAK

    # ---- coast: sand rim + shallow water
    g = tiles.reshape(ROWS, COLS)
    landg = land.reshape(ROWS, COLS)
    watern = np.zeros_like(landg)
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        sh = np.roll(np.roll(~landg, dr, 0), dc, 1)
        watern |= sh
    coast = landg & watern & np.isin(g, [GRASS, FIELD, FOREST])
    g[coast] = SAND

    # graded water: chebyshev distance-to-land -> shallow ring then mid ring
    dist = np.where(landg, 0, 99).astype(np.int16)
    cur = landg.copy()
    for k in range(1, 10):
        grow = cur.copy()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                grow |= np.roll(np.roll(cur, dr, 0), dc, 1)
        newly = grow & (dist == 99)
        dist[newly] = k
        cur = grow
    bay = np.zeros(n, bool)
    for x0, y0, x1, y1 in cfg["bays_tiles"]:
        bay |= (lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1)
    bay = bay.reshape(ROWS, COLS)
    shallow = ~landg & ((dist <= 2) | (bay & (dist <= 6)))
    mid = ~landg & ~shallow & ((dist <= 5) | (bay & (dist <= 9)))
    g[shallow & (g == WATER_DEEP)] = WATER_SHALLOW
    g[mid & (g == WATER_DEEP)] = WATER_MID

    tiles = g.ravel()

    # ---- mountain height field (graded toward the crest, noisy)
    hgrid = np.zeros(n, np.float32)
    mmask = (tiles == MOUNTAIN)
    hgrid[mmask] = 4 + closeness[mmask] * 9 + noise[mmask] * 3
    pmask = (tiles == PEAK)
    hgrid[pmask] = 16 * np.maximum(1.0, closeness[pmask]) + noise[pmask] * 5
    # crater rims sit at their configured height
    for clon, clat, r_in, r_out, rim_h in cfg["craters"]:
        d = np.hypot((lon - clon) * KM_PER_LON, (lat - clat) * KM_PER_LAT)
        rim = (d >= r_in) & (d < r_out) & mmask
        hgrid[rim] = rim_h
    hgrid = hgrid.astype(np.uint8)

    # ---- rail: tile mask (gameplay) + smooth fractional paths (render)
    rail = np.zeros((ROWS, COLS), bool)
    rail_paths = []
    if cfg["rail"]:
        rl = _load_geojson(ROOT / "data" / "rail_alignment.geojson")
        feats = rl["features"] if rl.get("type") == "FeatureCollection" \
            else [rl]
        for f in feats:
            gm = f["geometry"]
            lines = [gm["coordinates"]] if gm["type"] == "LineString" else \
                    gm["coordinates"] if gm["type"] == "MultiLineString" else []
            for line in lines:
                arr = np.asarray(line, dtype=float)[:, :2]
                path = []
                for (x1, y1), (x2, y2) in zip(arr[:-1], arr[1:]):
                    seg_km = math.hypot((x2 - x1) * KM_PER_LON,
                                        (y2 - y1) * KM_PER_LAT)
                    k = max(1, int(seg_km / 0.05))
                    ts = np.linspace(0, 1, k + 1)
                    cf, rf = lonlat_to_cell(x1 + ts * (x2 - x1),
                                            y1 + ts * (y2 - y1))
                    cc, rr = cf.astype(int), rf.astype(int)
                    ok = (cc >= 0) & (cc < COLS) & (rr >= 0) & (rr < ROWS)
                    rail[rr[ok], cc[ok]] = True
                    path.extend([[round(float(u), 3), round(float(v), 3)]
                                 for u, v in zip(cf[ok], rf[ok])])
                if len(path) > 1:
                    # thin to ~every 4th sample; enough for smooth ink
                    rail_paths.append(path[::4] + [path[-1]])

    # ---- stations
    stations = []
    if cfg["rail"]:
        st = _load_geojson(ROOT / "data" / "stations.geojson")
        for f in st["features"]:
            slon, slat = f["geometry"]["coordinates"][:2]
            c, r = lonlat_to_cell(slon, slat)
            stations.append({"name": f["properties"]["name"],
                             "col": int(c), "row": int(r)})

    # ---- landmarks -> tile coords
    lms = []
    for lid, name, llon, llat, kind in cfg["landmarks"]:
        c, r = lonlat_to_cell(llon, llat)
        lms.append({"id": lid, "name": name, "kind": kind,
                    "col": round(c, 2), "row": round(r, 2)})

    # ---- outputs
    (ROOT / "build").mkdir(exist_ok=True)
    grid = tiles.reshape(ROWS, COLS)
    out = {
        "island": slug, "name": cfg["name"], "home": cfg["home"],
        "cols": COLS, "rows": ROWS,
        "tile_w": TILE_W, "tile_h": TILE_H,
        "center": [LON_C, LAT_C], "tile_km": TILE_KM,
        "km_per_lon": KM_PER_LON, "km_per_lat": KM_PER_LAT,
        "outline": cfg["outline"],
        "bays": cfg["bays"],
        "names": NAMES,
        "tiles": [row.tolist() for row in grid],
        "heights": [row.tolist() for row in hgrid.reshape(ROWS, COLS)],
        "rail": [[int(c) for c in np.flatnonzero(rail[r])]
                 for r in range(ROWS)],
        "rail_paths": rail_paths,
        "stations": stations,
        "landmarks": lms,
    }
    with open(ROOT / "build" / f"map_grid_{slug}.json", "w") as fh:
        json.dump(out, fh)
    print(f"wrote build/map_grid_{slug}.json")

    # ---- debug render (top-down, 4px per tile)
    colors = np.array([
        [27, 78, 142], [63, 134, 184], [232, 210, 154], [87, 160, 74],
        [176, 150, 80], [47, 102, 49], [110, 100, 82], [200, 198, 190],
        [235, 235, 240], [72, 64, 52], [42, 100, 160],
    ], np.uint8)
    img = colors[grid]
    img[rail] = [255, 60, 120]
    im = Image.fromarray(img, "RGB").resize((COLS * 4, ROWS * 4),
                                            Image.NEAREST)
    im.save(ROOT / "build" / f"debug_map_{slug}.png")
    print(f"wrote build/debug_map_{slug}.png")

    counts = {NAMES[i]: int((tiles == i).sum()) for i in range(len(NAMES))}
    print(counts)


if __name__ == "__main__":
    main()
