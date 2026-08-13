#!/usr/bin/env python3
"""Build the Oʻahu tile grid for Capitol Quest.

Reads real geodata and classifies every tile of a 224x176 grid
(~320m/tile) into JRPG overworld terrain:

  water_deep, water_shallow, sand, grass, field, forest,
  mountain, urban, urban_dense

plus overlay flags (rail viaduct) and landmark/station positions.

Inputs
  data/island_outline.geojson   Oʻahu coastline (from Mahele-Atlas)
  data/rail_line.geojson        Skyline rail alignment (from Revenue-Modeling-TOD)
  data/stations.geojson         19 rail stations
  ~/Revenue-Modeling-TOD/data/raw/road_centerlines.geojson
                                road density -> urban tiles (not copied into
                                repo; only the derived grid is committed)

Outputs
  build/map_grid.json           full grid for tools/render_map.py
  build/debug_map.png           top-down colored QA render
  site/map/oahu.json            runtime metadata (landmarks, sparkles, dims)
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- grid
# North-up isometric: screen-up must be geographic north, so the tile grid
# axes run diagonally across geography. With screen x = (c-r)*16 and
# y = (c+r)*8, the +c axis heads SE and the +r axis heads SW; then
# x ∝ east and y ∝ -north, i.e. the island renders in true map orientation.
COLS = ROWS = 288
LON_C, LAT_C = -157.965, 21.4825       # island bbox center
KM_PER_LON = 103.8                     # at ~21.4N
KM_PER_LAT = 110.9
TILE_KM = 0.32                         # ground spacing between tile centers
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


# ---------------------------------------------------------------- ridges
KOOLAU = [(-157.990, 21.620), (-157.945, 21.575), (-157.900, 21.520),
          (-157.865, 21.470), (-157.830, 21.420), (-157.800, 21.380),
          (-157.788, 21.350), (-157.760, 21.330), (-157.715, 21.318),
          (-157.670, 21.305)]
WAIANAE = [(-158.260, 21.555), (-158.225, 21.535), (-158.200, 21.520),
           (-158.145, 21.507), (-158.120, 21.470), (-158.105, 21.430),
           (-158.090, 21.390), (-158.075, 21.360)]

CRATERS = [  # (lon, lat, rim_inner_km, rim_outer_km)
    (-157.8055, 21.2620, 0.45, 1.00),   # Lēʻahi / Diamond Head
    (-157.6773, 21.2905, 0.30, 0.70),   # Koko Crater
    (-157.8457, 21.3066, 0.00, 0.38),   # Pūowaina / Punchbowl
]

# ag plateau bboxes (lon0, lat0, lon1, lat1)
FIELDS = [(-158.16, 21.42, -157.92, 21.62),
          (-158.12, 21.33, -157.99, 21.42)]   # Kunia / ʻEwa plain

# Honolulu urban core (dense towers allowed)
CORE = (-157.875, 21.270, -157.815, 21.320)

LANDMARKS = [
    # id, name, lon, lat, kind
    ("capitol", "Hawaiʻi State Capitol", -157.85736, 21.30737, "capitol"),
    ("iolani", "ʻIolani Palace", -157.85868, 21.30655, "poi"),
    ("honolulu", "Honolulu", -157.8630, 21.2930, "town"),
    ("waikiki", "Waikīkī", -157.8270, 21.2780, "town"),
    ("diamondhead", "Lēʻahi (Diamond Head)", -157.8055, 21.2600, "nature"),
    ("pearlharbor", "Pearl Harbor", -157.9600, 21.3550, "nature"),
    ("kaneohe", "Kāneʻohe", -157.8000, 21.4080, "town"),
    ("kailua", "Kailua", -157.7400, 21.3930, "town"),
    ("kapolei", "Kapolei", -158.0580, 21.3350, "town"),
    ("waianae", "Waiʻanae", -158.1850, 21.4470, "town"),
    ("wahiawa", "Wahiawā", -158.0240, 21.5030, "town"),
    ("haleiwa", "Haleʻiwa", -158.1030, 21.5930, "town"),
    ("koolau", "Koʻolau Range", -157.8650, 21.4700, "range"),
    ("waianaerange", "Waiʻanae Range", -158.1450, 21.4900, "range"),
]


def main():
    lon, lat = cell_center_lonlat()
    n = ROWS * COLS

    # ---- land / water
    outline = json.load(open(ROOT / "data" / "island_outline.geojson"))
    geom = outline["geometry"] if outline.get("type") == "Feature" else outline
    rings = rings_of(geom)
    print(f"outline: {len(rings)} rings")
    land = points_in_rings(lon, lat, rings)
    print(f"land tiles: {land.sum()} / {n}")

    tiles = np.full(n, WATER_DEEP, np.uint8)
    tiles[land] = GRASS
    landg_pre = land.reshape(ROWS, COLS)

    # ---- ridges -> mountain / forest (noise-modulated widths)
    noise = smooth_noise((ROWS, COLS)).ravel()
    d_koolau = dist_to_polyline_km(lon, lat, KOOLAU)
    d_waianae = dist_to_polyline_km(lon, lat, WAIANAE)
    wob = 0.55 + 0.9 * noise          # 0.55..1.45 width multiplier
    mountain = land & ((d_koolau < 1.8 * wob) | (d_waianae < 2.3 * wob))
    forest = land & ((d_koolau < 3.6 * wob) | (d_waianae < 4.2 * wob)) & ~mountain
    peak = land & ((d_koolau < 0.55) | (d_waianae < 0.7))
    for clon, clat, r_in, r_out in CRATERS:
        d = np.hypot((lon - clon) * KM_PER_LON, (lat - clat) * KM_PER_LAT)
        rim = land & (d >= r_in) & (d < r_out)
        mountain |= rim
        forest &= ~rim

    # ---- ag fields (noisy edges so the bbox doesn't read as a rectangle)
    field = np.zeros(n, bool)
    noise2 = smooth_noise((ROWS, COLS), seed=7).ravel()
    for x0, y0, x1, y1 in FIELDS:
        # distance to bbox edge in degrees, positive inside
        din = np.minimum.reduce([lon - x0, x1 - lon, lat - y0, y1 - lat])
        band = 0.018 * (0.4 + 1.2 * noise2)  # fuzzy shrink of the bbox rim
        field |= din > band - 0.018
    field &= land & ~mountain & ~forest

    # ---- urban from road density
    roads_path = Path.home() / "Revenue-Modeling-TOD/data/raw/road_centerlines.geojson"
    density = np.zeros((ROWS, COLS), np.float32)
    roads = json.load(open(roads_path))
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
                seg_km = math.hypot((x2 - x1) * KM_PER_LON, (y2 - y1) * KM_PER_LAT)
                k = max(1, int(seg_km / 0.08))
                ts = (np.arange(k) + 0.5) / k
                sx = x1 + ts * (x2 - x1)
                sy = y1 + ts * (y2 - y1)
                cf, rf = lonlat_to_cell(sx, sy)
                cc, rr = cf.astype(int), rf.astype(int)
                ok = (cc >= 0) & (cc < COLS) & (rr >= 0) & (rr < ROWS)
                np.add.at(density, (rr[ok], cc[ok]), 1.0)
    density = density.ravel()
    print(f"road density: max {density.max():.0f}, p90 {np.percentile(density[density>0], 90):.0f}")

    T_URBAN, T_DENSE = 20.0, 60.0
    urban = land & (density >= T_URBAN) & ~mountain
    # de-speckle: drop weak isolated tiles, fill surrounded gaps (2 passes)
    ug = urban.reshape(ROWS, COLS)
    dg = density.reshape(ROWS, COLS)
    for _ in range(2):
        nb = np.zeros((ROWS, COLS), np.int8)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr or dc:
                    nb += np.roll(np.roll(ug, dr, 0), dc, 1)
        ug = (ug & ((nb >= 3) | (dg >= 45))) | (~ug & (nb >= 6) & landg_pre)
    urban = ug.ravel() & land & ~mountain
    in_core = (lon >= CORE[0]) & (lon <= CORE[2]) & (lat >= CORE[1]) & (lat <= CORE[3])
    dense = urban & in_core & (density >= T_DENSE)
    # urban beats forest/field where roads are truly dense
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
    bay = ((lon >= -157.84) & (lon <= -157.75) &
           (lat >= 21.40) & (lat <= 21.51)).reshape(ROWS, COLS)
    shallow = ~landg & ((dist <= 2) | (bay & (dist <= 6)))
    mid = ~landg & ~shallow & ((dist <= 5) | (bay & (dist <= 9)))
    g[shallow & (g == WATER_DEEP)] = WATER_SHALLOW
    g[mid & (g == WATER_DEEP)] = WATER_MID

    tiles = g.ravel()

    # ---- mountain height field (graded toward the crest, noisy)
    closeness = np.maximum(1.0 - d_koolau / (1.8 * wob),
                           1.0 - d_waianae / (2.3 * wob))
    closeness = np.clip(closeness, 0.0, 1.0)
    hgrid = np.zeros(n, np.uint8)
    mmask = (tiles == MOUNTAIN)
    hgrid[mmask] = (4 + closeness[mmask] * 9 + noise[mmask] * 3).astype(np.uint8)
    pmask = (tiles == PEAK)
    hgrid[pmask] = (16 + noise[pmask] * 5).astype(np.uint8)
    # crater rims sit lower than the big ranges
    for clon, clat, r_in, r_out in CRATERS:
        d = np.hypot((lon - clon) * KM_PER_LON, (lat - clat) * KM_PER_LAT)
        rim = (d >= r_in) & (d < r_out) & mmask
        hgrid[rim] = 8

    # ---- rail: tile mask (gameplay) + smooth fractional paths (render)
    rail = np.zeros((ROWS, COLS), bool)
    rail_paths = []
    rl = json.load(open(ROOT / "data" / "rail_alignment.geojson"))
    feats = rl["features"] if rl.get("type") == "FeatureCollection" else [rl]
    for f in feats:
        gm = f["geometry"]
        lines = [gm["coordinates"]] if gm["type"] == "LineString" else \
                gm["coordinates"] if gm["type"] == "MultiLineString" else []
        for line in lines:
            arr = np.asarray(line, dtype=float)[:, :2]
            path = []
            for (x1, y1), (x2, y2) in zip(arr[:-1], arr[1:]):
                seg_km = math.hypot((x2 - x1) * KM_PER_LON, (y2 - y1) * KM_PER_LAT)
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
    st = json.load(open(ROOT / "data" / "stations.geojson"))
    stations = []
    for f in st["features"]:
        slon, slat = f["geometry"]["coordinates"][:2]
        c, r = lonlat_to_cell(slon, slat)
        stations.append({"name": f["properties"]["name"],
                         "col": int(c), "row": int(r)})

    # ---- landmarks -> tile coords
    lms = []
    for lid, name, llon, llat, kind in LANDMARKS:
        c, r = lonlat_to_cell(llon, llat)
        lms.append({"id": lid, "name": name, "kind": kind,
                    "col": round(c, 2), "row": round(r, 2)})

    # ---- outputs
    (ROOT / "build").mkdir(exist_ok=True)
    grid = tiles.reshape(ROWS, COLS)
    out = {
        "cols": COLS, "rows": ROWS,
        "tile_w": TILE_W, "tile_h": TILE_H,
        "center": [LON_C, LAT_C], "tile_km": TILE_KM,
        "names": NAMES,
        "tiles": [row.tolist() for row in grid],
        "heights": [row.tolist() for row in hgrid.reshape(ROWS, COLS)],
        "rail": [[int(c) for c in np.flatnonzero(rail[r])] for r in range(ROWS)],
        "rail_paths": rail_paths,
        "stations": stations,
        "landmarks": lms,
    }
    with open(ROOT / "build" / "map_grid.json", "w") as fh:
        json.dump(out, fh)
    print("wrote build/map_grid.json")

    # ---- debug render (top-down, 4px per tile)
    colors = np.array([
        [27, 78, 142], [63, 134, 184], [232, 210, 154], [87, 160, 74],
        [176, 150, 80], [47, 102, 49], [110, 100, 82], [200, 198, 190],
        [235, 235, 240], [72, 64, 52], [42, 100, 160],
    ], np.uint8)
    img = colors[grid]
    img[rail] = [255, 60, 120]
    im = Image.fromarray(img, "RGB").resize((COLS * 4, ROWS * 4), Image.NEAREST)
    im.save(ROOT / "build" / "debug_map.png")
    print("wrote build/debug_map.png")

    counts = {NAMES[i]: int((tiles == i).sum()) for i in range(len(NAMES))}
    print(counts)


if __name__ == "__main__":
    main()
