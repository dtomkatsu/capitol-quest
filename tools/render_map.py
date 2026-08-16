#!/usr/bin/env python3
"""Bake a Capitol Quest island overworld — modern 2D-JRPG pixel art.

v2 renderer: the ground is rendered in SCREEN SPACE at pixel resolution
instead of stamping per-tile diamonds:

  * coastline drawn from the real island polygon  -> smooth curves
  * water colored by distance-to-shore gradient bands with dithered edges
  * terrain boundaries jittered with smooth noise  -> organic borders
  * mountains are a continuous relief-shaded heightfield (displacement
    render with cliff faces), not stacked mesas
  * trees / plantation houses / towers are individually drawn outlined
    sprites with cast shadows, scattered per tile and depth-sorted

The tile grid from build_map.py still decides WHAT is where; it no longer
decides the shape of any edge. All geometry (grid size, center, scale,
bays, outline path) rides in build/map_grid_<slug>.json, written by
build_map.py from tools/islands.py.

Usage:
  python3 tools/render_map.py                 # Oʻahu
  python3 tools/render_map.py --island maui
  python3 tools/render_map.py --all

Outputs
  site/assets/map/<slug>_<i>.png  slices (each < 4096px)
  site/map/<slug>.json            runtime metadata
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

TILE_W, TILE_H = 32, 16
TOP_PAD = 64
MARGIN = 320
DEEP = "#1c5490"

(WATER_DEEP, WATER_SHALLOW, SAND, GRASS, FIELD, FOREST, MOUNTAIN, URBAN,
 URBAN_DENSE, PEAK, WATER_MID) = range(11)
LAND_IDS = [SAND, GRASS, FIELD, FOREST, MOUNTAIN, URBAN, URBAN_DENSE, PEAK]

# set per island in render_island() from the grid json (build_map.py)
GRID = 288
KM_PER_LON, KM_PER_LAT = 103.8, 110.9
LON_C, LAT_C = -157.965, 21.4825
TILE_KM = 0.32
K = TILE_KM * math.sqrt(2.0)


def hx(s):
    s = s.lstrip("#")
    return np.array([int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)],
                    np.float32)


def hx4(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


# ---------------------------------------------------------------- palette
#
# TWO STYLES, and the geometry is IDENTICAL between them.
#
# `--style pixel` is the original bright pixel-art look, kept intact as
# the ARCHIVE of what the map used to be (2026-08-15). It is archived as
# SOURCE, not as a folder of stale PNGs: re-run with `--style pixel
# --all` and the old map comes back byte-for-byte. Do not delete it.
#
# `--style painterly` (the default since 2026-08-15, user's call) is the
# CRPG look: oil-paint brush facets, softened sprite keylines, far less
# granular detail, and a final grade + faint vignette. It keeps the
# BRIGHT tropical palette — a muted earth-and-slate version was built
# first and rejected. The styles differ in treatment, not pigment.
#
# CRITICAL: a style may change COLOUR and DENSITY only. It must never
# change the crop window, the transform, W/H or any px coordinate —
# tax_flows, get_flows, world.json, landmarks and stations are all baked
# against those numbers, and a style that moved them would silently
# drift every downstream layer off the drawn geography.
STYLE = "painterly"

PIXEL_PAL = dict(
    deep="#1c5490",
    water=[(2, "#f2fbf7"),    # foam line
           (5, "#a8e6de"),    # shore glow
           (12, "#5cc6d2"),   # reef
           (26, "#3799c2"),   # lagoon
           (48, "#2a71ad"),   # mid
           (9999, "#1c5490")],
    sand_wet="#dcbf85", sand="#eedca6", grass="#68b054",
    field="#8cc063", field_row="#6ea24c",
    pine="#c08a54", pine_row="#a06a3c",       # pineapple red-soil field
    forest_floor="#3f7c42", lot="#7db35e",    # lot = village lawn
    street="#c3b9a2", asphalt="#a9a79c",      # asphalt = dense downtown
    rock_low="#5d8748", rock_high="#8b8b72", cliff="#463e2e",
)

# SAME bright tropical palette as pixel (2026-08-15, user's call — a
# dusty desaturated version was built first and rejected: "it should be
# bright"). The two styles differ in TREATMENT, not colour: painterly
# gets the oil-paint facets, softened sprite keylines, thinner sprite
# fields and the vignette; the pigments underneath stay Hawaiʻi's.
PAINTERLY_PAL = dict(PIXEL_PAL)


def use_style(name):
    """Rebind the palette globals for the chosen style.

    Everything downstream reads these module-level constants, so the
    swap happens once here rather than threading a palette object
    through every drawing routine.
    """
    global STYLE, DEEP, WATER_BANDS, GROUND_BASE
    global C_SAND_WET, C_SAND, C_GRASS, C_FIELD, C_FIELD_ROW
    global C_PINE, C_PINE_ROW, C_FOREST_FLOOR, C_LOT
    global C_STREET, C_ASPHALT, C_ROCK_LOW, C_ROCK_HIGH, C_CLIFF
    STYLE = name
    p = PIXEL_PAL if name == "pixel" else PAINTERLY_PAL
    DEEP = p["deep"]
    WATER_BANDS = [(d, hx(c)) for d, c in p["water"]]
    C_SAND_WET = hx(p["sand_wet"])
    C_SAND = hx(p["sand"])
    C_GRASS = hx(p["grass"])
    C_FIELD = hx(p["field"])
    C_FIELD_ROW = hx(p["field_row"])
    C_PINE = hx(p["pine"])
    C_PINE_ROW = hx(p["pine_row"])
    C_FOREST_FLOOR = hx(p["forest_floor"])
    C_LOT = hx(p["lot"])
    C_STREET = hx(p["street"])
    C_ASPHALT = hx(p["asphalt"])
    C_ROCK_LOW = hx(p["rock_low"])
    C_ROCK_HIGH = hx(p["rock_high"])
    C_CLIFF = hx(p["cliff"])
    GROUND_BASE = {
        SAND: C_SAND, GRASS: C_GRASS, FIELD: C_FIELD,
        FOREST: C_FOREST_FLOOR, MOUNTAIN: C_ROCK_LOW, URBAN: C_LOT,
        URBAN_DENSE: C_ASPHALT, PEAK: C_ROCK_LOW,
    }


use_style(STYLE)


# ---------------------------------------------------------------- helpers
def smooth_field(shape, cells, seed, lo=0.0, hi=1.0):
    """Smooth random field via PIL bilinear upscale of coarse noise."""
    rng = np.random.default_rng(seed)
    coarse = (rng.random((cells, cells)) * 255).astype(np.uint8)
    im = Image.fromarray(coarse, "L").resize((shape[1], shape[0]),
                                             Image.BILINEAR)
    z = np.asarray(im, np.float32) / 255.0
    return lo + z * (hi - lo)


def hash_noise(shape, seed):
    """Cheap per-pixel white noise in [0,1)."""
    rng = np.random.default_rng(seed)
    return rng.random(shape, dtype=np.float32)


def band_dist(mask_land, iters, scale=2):
    """Chebyshev distance INTO ~mask, computed at 1/scale res, bilinear up.
    Returns float32 array, pixels (full res)."""
    h, w = mask_land.shape
    small = np.asarray(
        Image.fromarray(mask_land.astype(np.uint8) * 255, "L")
        .resize((w // scale, h // scale), Image.BOX), np.float32) > 127
    dist = np.where(small, 0, 255).astype(np.uint8)
    cur = small.copy()
    # alternate 8- and 4-neighborhoods -> octagonal metric (round contours)
    nb8 = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
    nb4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for k in range(1, iters + 1):
        grow = cur.copy()
        for dr, dc in (nb8 if k % 2 else nb4):
            grow |= np.roll(np.roll(cur, dr, 0), dc, 1)
        newly = grow & (dist == 255)
        dist[newly] = k
        cur = grow
    dist[dist == 255] = iters          # smooth cap, no sentinel cliff
    dist_im = Image.fromarray(dist, "L").resize((w, h), Image.BILINEAR)
    return np.asarray(dist_im, np.float32) * scale


# ---------------------------------------------------------------- sprites
def _sp(w, h):
    return np.zeros((h, w, 4), np.uint8)


def _outline(img, color):
    """1px outline around opaque pixels (ignores translucent shadows).

    In painterly style the outline is BLENDED toward the sprite rather
    than stamped hard: a crisp dark keyline is the single strongest
    pixel-art cue, and leaving it in was what still made the painted
    map read as a tile game. The ring stays (it is what separates a
    tree from the ground behind it) but only as a soft contact shadow.
    """
    a = img[:, :, 3] >= 200
    edge = np.zeros_like(a)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            edge |= np.roll(np.roll(a, dr, 0), dc, 1)
    edge &= ~a
    if STYLE == "painterly":
        c = np.array(color, np.float32)
        c[3] *= 0.55
        img[edge] = c.astype(np.uint8)
    else:
        img[edge] = color


def _paint_sprite(spr):
    """Seat a sprite in the painted ground, in place.

    The sprite drawings are the original pixel-art set. In painterly
    mode they keep their COLOUR — a muting version was built first and
    rejected ("it should be bright") — and are only enriched a touch so
    they sit with the graded terrain instead of looking stickered on.
    Their integration is really done by two other things: the softened
    keyline in _outline(), and the oil-paint pass which runs over
    sprites and ground together at the end. Pixel style is verbatim.
    """
    if STYLE != "painterly":
        return spr
    rgb = spr[..., :3].astype(np.float32)
    lum = (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 +
           rgb[..., 2] * 0.114)[..., None]
    rgb = lum + (rgb - lum) * 1.12          # match the ground's lift
    spr[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return spr


def _shadow(img, cx, cy, rx, ry, alpha=75):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if 0 <= y < img.shape[0] and 0 <= x < img.shape[1]:
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    if img[y, x, 3] == 0:
                        img[y, x] = (30, 48, 30, alpha)


def spr_tree(rng, tall=False):
    w, h = 18, 22
    img = _sp(w, h)
    _shadow(img, 9, 19, 6, 2)
    dark, mid, lite = hx4("#2c5e33"), hx4("#3f8544"), hx4("#5cab55")
    trunk = hx4("#6d4a2b")
    cy = 9 if not tall else 8
    ry = 6 if not tall else 7
    rx = 6
    img[cy + ry - 1:19, 8:10] = trunk
    for y in range(cy - ry, cy + ry + 1):
        for x in range(9 - rx, 9 + rx + 1):
            d = ((x - 9) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1.0:
                img[y, x] = dark if d > 0.55 else mid
    for y in range(cy - ry, cy + 1):
        for x in range(9 - rx, 10):
            d = ((x - 7) / rx) ** 2 + ((y - cy + 2) / ry) ** 2
            if d <= 0.34:
                img[y, x] = lite
    _outline(img, hx4("#1e3d24"))
    return img


def spr_palm(rng):
    w, h = 22, 22
    img = _sp(w, h)
    _shadow(img, 11, 19, 6, 2, alpha=70)
    trunk = hx4("#96653a")
    trunk_dk = hx4("#7a4f2c")
    frond = hx4("#2e7c38")
    frond_lt = hx4("#58ac4e")
    # gently curved trunk
    for i in range(10):
        x = 9 + (i * i) // 30
        img[18 - i, x] = trunk
        img[18 - i, x + 1] = trunk_dk
    tx, ty = 11, 7
    # fronds as connected arcs (rise then droop)
    arcs = [[(-1, -1), (-2, -1), (-3, 0), (-4, 1), (-5, 2)],
            [(1, -1), (2, -1), (3, 0), (4, 1), (5, 2)],
            [(-1, -2), (-2, -3), (-3, -3)],
            [(1, -2), (2, -3), (3, -3)],
            [(0, -1), (0, -2), (-1, -3)],
            [(-2, 0), (-4, 0), (-6, 1)],
            [(2, 0), (4, 0), (6, 1)]]
    for arc in arcs:
        for j, (dx, dy) in enumerate(arc):
            c = frond_lt if j < 2 else frond
            img[ty + dy, tx + dx] = c
    img[ty, tx] = frond
    img[ty + 1, tx] = hx4("#6d4a2b")        # coconuts
    img[ty + 1, tx - 1] = hx4("#5d3f24")
    _outline(img, hx4("#1f4a26"))
    return img


WALLS = ["#f4ead2", "#adc096", "#e0cda6", "#a2c1b4", "#ecdcc6"]
ROOFS = ["#b65540", "#71935c", "#5a5e64", "#aeb8be", "#8f5246"]


def spr_house(rng):
    w, h = 22, 18
    img = _sp(w, h)
    _shadow(img, 11, 16, 8, 2)
    wall = hx4(rng.choice(WALLS))
    roof = hx4(rng.choice(ROOFS))
    roof_dk = tuple(max(0, v - 34) for v in roof[:3]) + (255,)
    roof_lt = tuple(min(255, v + 26) for v in roof[:3]) + (255,)
    wall_dk = tuple(max(0, v - 40) for v in wall[:3]) + (255,)
    # piers + floor line
    img[14, 4:18] = wall_dk
    for px in (5, 10, 16):
        img[15, px] = wall_dk
    # walls with shaded right side
    for y in range(10, 14):
        img[y, 4:15] = wall
        img[y, 15:18] = wall_dk
    img[10, 4:18] = wall_dk                     # lanai shade under eaves
    img[11:14, 10:12] = hx4("#41586e")          # door
    img[12, 6] = hx4("#41586e")
    img[12, 16] = hx4("#41586e")
    # hipped roof, deep eaves
    img[9, 2:20] = roof_dk
    img[8, 3:19] = roof
    img[7, 5:17] = roof
    img[6, 7:15] = roof_lt
    img[5, 9:13] = roof_lt
    _outline(img, hx4("#40342c"))
    return img


def spr_tower(rng):
    w, h = 16, 30
    img = _sp(w, h)
    _shadow(img, 8, 27, 6, 2)
    glass = rng.random() < 0.45
    body = hx4("#a9c6d4") if glass else hx4("#e2dccd")
    body_dk = hx4("#84a2b2") if glass else hx4("#b7b1a2")
    th = rng.randrange(16, 24)
    base = 26
    for y in range(th):
        img[base - y, 3:9] = body
        img[base - y, 9:13] = body_dk
    img[base - th, 3:13] = hx4("#8f9aa4")
    img[base - th - 1, 5:8] = hx4("#767f88")
    for y in range(base - th + 2, base - 1, 3):
        for x in range(4, 12, 3):
            img[y, x] = hx4("#f4f6cc") if rng.random() < .6 else hx4("#41586e")
    _outline(img, hx4("#39424c"))
    return img


# ---------------------------------------------------------------- main
def painterly_finish(canvas):
    """Turn the rendered canvas into a painting, in place, same size.

    The same treatment the event banners get (make_event_art.paintify),
    tuned for a map: a short oil-paint pass to break the per-pixel
    terrain into brush facets, a gentle desaturate + cool grade so the
    ground reads as pigment rather than tile colour, and a soft vignette
    so the island sits in the dark the way the reference boards do.

    MUST return the same W x H — every downstream layer is baked against
    these dimensions.
    """
    import cv2
    rgb = np.asarray(canvas.convert("RGB"), np.uint8)
    h, w = rgb.shape[:2]

    # 1. brush facets. Radius is judged against the OUTPUT, and the map
    #    is viewed far zoomed out now, so a small radius is enough — a
    #    big one turns whole neighbourhoods into single blobs.
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    painted = cv2.xphoto.oilPainting(bgr, 4, 1)
    painted = cv2.cvtColor(painted, cv2.COLOR_BGR2RGB).astype(np.float32)
    base = rgb.astype(np.float32)
    # not full strength: at 1.0 the coastline turns to mush and the
    # street grid stops reading as a grid at all
    out = base * (1.0 - 0.72) + painted * 0.72

    # 2. pigment grade. This BRIGHTENS — a desaturating, cool-shadowed
    #    version was built first and rejected (2026-08-15, user's call:
    #    "it should be bright"). Oil paint flattens toward the local
    #    mean, so without a lift the pass reads as dust. Saturation goes
    #    UP so the greens stay Hawaiʻi's, and the midtones lift.
    #
    #    NO VIGNETTE, and this is load-bearing: every island is a
    #    RECTANGLE composited onto a flat sea of `deep`, so any
    #    position-dependent darkening draws a visible box around each
    #    island at world zoom. A faint radial falloff was tried and had
    #    exactly that effect. Only per-pixel, position-INDEPENDENT
    #    grading is safe here.
    return Image.fromarray(
        np.clip(_grade(out), 0, 255).astype(np.uint8), "RGB")


def _grade(arr):
    """The painterly colour grade. Position-independent by design, and
    applied to BOTH the canvas and the `deep` swatch — the flat sea the
    scene paints behind the island rectangles has to land on the same
    colour the graded slice water does, or every island gets a visible
    rectangular halo where the two meet.

    (Explicit weighted sum, not `arr @ vec` — float32 matmul on an
    image this size trips BLAS overflow warnings.)
    """
    lum = (arr[..., 0] * 0.299 + arr[..., 1] * 0.587 +
           arr[..., 2] * 0.114)[..., None]
    out = lum + (arr - lum) * 1.16              # richer, not greyer
    return 255.0 * np.clip(out / 255.0, 0, 1) ** 0.94   # midtone lift


def graded_deep(hex_color):
    """`deep` after the same grade the slices get (painterly only)."""
    if STYLE != "painterly":
        return hex_color
    v = _grade(hx(hex_color)[None, None, :])[0, 0]
    return "#%02x%02x%02x" % tuple(int(round(c)) for c in
                                   np.clip(v, 0, 255))


def main():
    from islands import ISLANDS
    ap = argparse.ArgumentParser()
    ap.add_argument("--island", default="oahu", choices=sorted(ISLANDS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--style", default="painterly",
                    choices=("painterly", "pixel"),
                    help="painterly = the CRPG look (default); pixel = "
                         "the original bright pixel-art map, kept "
                         "reproducible as the archive of the old style")
    args = ap.parse_args()
    use_style(args.style)
    print(f"style: {args.style}")
    for slug in (list(ISLANDS) if args.all else [args.island]):
        render_island(slug)


def render_island(slug):
    grid_data = json.load(open(ROOT / "build" / f"map_grid_{slug}.json"))
    global GRID, KM_PER_LON, KM_PER_LAT, LON_C, LAT_C, TILE_KM, K
    GRID = grid_data["cols"]
    KM_PER_LON = grid_data["km_per_lon"]
    KM_PER_LAT = grid_data["km_per_lat"]
    LON_C, LAT_C = grid_data["center"]
    TILE_KM = grid_data["tile_km"]
    K = TILE_KM * math.sqrt(2.0)
    print(f"=== {slug}: grid {GRID}, {TILE_KM} km/tile ===")

    COLS, ROWS = grid_data["cols"], grid_data["rows"]
    tiles = np.array(grid_data["tiles"], np.uint8)
    theights = np.array(grid_data["heights"], np.float32)

    origin_x = (ROWS - 1) * 16

    # ---- crop window from land tiles (same rule as v1)
    land_rc = np.argwhere(np.isin(tiles, LAND_IDS))
    lx = (land_rc[:, 1] - land_rc[:, 0]) * 16 + origin_x
    ly = (land_rc[:, 1] + land_rc[:, 0]) * 8 + TOP_PAD
    FULL_W = (COLS + ROWS - 1) * 16 + 32
    FULL_H = (COLS + ROWS - 2) * 8 + 16 + TOP_PAD
    x0 = max(0, int(lx.min()) - MARGIN)
    y0 = max(0, int(ly.min()) - MARGIN // 2 - TOP_PAD)
    x1 = min(FULL_W, int(lx.max()) + 32 + MARGIN)
    y1 = min(FULL_H, int(ly.max()) + 16 + MARGIN // 2)
    W, H = x1 - x0, y1 - y0
    print(f"render window {W}x{H}")

    # ---- per-pixel grid coords (u,v) and geographic (E,N)
    xs = np.arange(W, dtype=np.float32) + x0
    ys = np.arange(H, dtype=np.float32) + y0
    XR = (xs[None, :] - origin_x) / 16.0
    YR = (ys[:, None] - TOP_PAD) / 8.0
    U = (XR + YR) / 2.0                        # (H,W) via broadcasting
    V = (YR - XR) / 2.0
    E = K * (U - V) / 2.0 + 0.0                # km east of center
    N = -K * ((U - GRID / 2) + (V - GRID / 2)) / 2.0
    lon = LON_C + (K * ((U - GRID / 2) - (V - GRID / 2)) / 2.0) / KM_PER_LON
    lat = LAT_C + N / KM_PER_LAT

    # ---- smooth land mask from the real coastline polygon
    outline = json.load(open(ROOT / grid_data["outline"]))
    geom = outline["geometry"] if outline.get("type") == "Feature" else outline
    if geom.get("type") == "FeatureCollection":
        feats = geom["features"]
        coords = []
        for f in feats:
            g = f["geometry"]
            coords += g["coordinates"] if g["type"] == "MultiPolygon" \
                else [g["coordinates"]]
        geom = {"type": "MultiPolygon", "coordinates": coords}
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else \
        [geom["coordinates"]]

    def ring_to_screen(ring):
        pts = []
        for p in ring:
            e = (p[0] - LON_C) * KM_PER_LON
            nn = (p[1] - LAT_C) * KM_PER_LAT
            u = (e - nn) / K + GRID / 2
            v = (-e - nn) / K + GRID / 2
            pts.append(((u - v) * 16 + origin_x - x0,
                        (u + v) * 8 + TOP_PAD - y0))
        return pts

    mask_im = Image.new("L", (W, H), 0)
    dr_mask = ImageDraw.Draw(mask_im)
    for poly in polys:
        dr_mask.polygon(ring_to_screen(poly[0]), fill=255)
        for hole in poly[1:]:
            dr_mask.polygon(ring_to_screen(hole), fill=0)
    land = np.asarray(mask_im, np.uint8) > 127
    print(f"land px: {land.sum()/1e6:.2f}M / {W*H/1e6:.1f}M")

    # ---- distance fields (smooth, in px)
    d_sea = band_dist(land, 34)        # distance into water from shore
    d_inl = band_dist(~land, 10)       # distance into land from shore

    # ---- terrain class per pixel, noise-jittered for organic borders
    ju = smooth_field((H, W), 160, seed=11, lo=-0.62, hi=0.62)
    jv = smooth_field((H, W), 160, seed=12, lo=-0.62, hi=0.62)
    ci = np.clip((U + ju).astype(np.int32), 0, GRID - 1)
    ri = np.clip((V + jv).astype(np.int32), 0, GRID - 1)
    cls = tiles[ri, ci]
    # the polygon land mask outranks the coarse tile grid: land pixels that
    # sampled a water class must still get a ground color
    waterish = np.isin(cls, [WATER_DEEP, WATER_SHALLOW, WATER_MID])
    cls[land & waterish & (d_inl < 12)] = SAND
    cls[land & waterish & (d_inl >= 12)] = GRASS

    # ---- heightfield (bilinear tile heights, px units)
    u0 = np.clip(np.floor(U - 0.5).astype(np.int32), 0, GRID - 2)
    v0 = np.clip(np.floor(V - 0.5).astype(np.int32), 0, GRID - 2)
    fu = np.clip(U - 0.5 - u0, 0, 1).astype(np.float32)
    fv = np.clip(V - 0.5 - v0, 0, 1).astype(np.float32)
    h00 = theights[v0, u0]
    h10 = theights[v0, u0 + 1]
    h01 = theights[v0 + 1, u0]
    h11 = theights[v0 + 1, u0 + 1]
    hpx = ((h00 * (1 - fu) * (1 - fv) + h10 * fu * (1 - fv) +
            h01 * (1 - fu) * fv + h11 * fu * fv) * 2.1)
    hpx += smooth_field((H, W), 220, seed=31, lo=-1.6, hi=1.6) * (hpx > 1)
    # broad blur so tile "tents" merge into smooth massifs (kills corduroy
    # artifacts in the hillshade)
    hs = Image.fromarray(hpx).resize((W // 5, H // 5), Image.BILINEAR) \
        .resize((W, H), Image.BILINEAR)
    hpx = np.asarray(hs, np.float32) * 1.15
    hpx *= land
    hpx[d_inl < 5] *= 0.25             # ease ranges into the sea
    hpx = np.maximum(hpx, 0).astype(np.float32)

    # ---- assemble ground color
    fine = hash_noise((H, W), 77)
    mottle = smooth_field((H, W), 46, seed=21, lo=-9, hi=9)

    col = np.zeros((H, W, 3), np.float32)

    # water bands (dither the band edges with fine noise). Reef-flat bays
    # (Kāneʻohe on Oʻahu, Molokaʻi's south reef) widen the bands via a
    # FEATHERED influence field (no bbox edges in the water).
    bay = np.zeros((H, W), np.float32)
    for bx0, by0, bx1, by1 in grid_data.get("bays", []):
        bay = np.maximum(bay, (np.clip((lon - bx0) / 0.025, 0, 1) *
                               np.clip((bx1 - lon) / 0.025, 0, 1) *
                               np.clip((lat - by0) / 0.025, 0, 1) *
                               np.clip((by1 - lat) / 0.025, 0, 1)))
    dw = (d_sea + (fine - 0.5) * 5.0) / (1.0 + 1.5 * bay)
    wcol = np.empty_like(col)
    wcol[:] = WATER_BANDS[-1][1]
    for lim, c in reversed(WATER_BANDS[:-1]):
        wcol[dw <= lim] = c
    # patch reefs texturing the bay lagoon
    patch = smooth_field((H, W), 130, seed=71)
    reefp = (bay > 0.35) & ~land & (dw > 6) & (dw < 40) & (patch > 0.62)
    wcol[reefp] = WATER_BANDS[2][1]
    wcol[reefp & (patch > 0.72)] = WATER_BANDS[1][1]
    # sparse wave dashes on open water
    dash = (hash_noise((H // 1, W // 8 + 1), 9)[:, (np.arange(W) // 8)]
            < 0.004) & (d_sea > 18) & ((np.arange(H) % 3 == 0)[:, None])
    wcol[dash] = hx("#4f8cc4")
    col[~land] = wcol[~land]

    # land base by class
    for cid, base in GROUND_BASE.items():
        m = land & (cls == cid)
        col[m] = base
    # class-independent touches
    gm = land & np.isin(cls, [GRASS, FIELD, FOREST, URBAN, MOUNTAIN, PEAK])
    col[gm] += mottle[gm][:, None]
    sp = land & (fine < 0.16)
    col[sp] -= 12
    sp2 = land & (fine > 0.86)
    col[sp2] += 10

    # crop rows in geographic space (continuous across tiles)
    rows_a = (np.floor((E + N) / 0.055).astype(np.int32) % 2 == 0)
    fieldm = land & (cls == FIELD)
    pine = smooth_field((H, W), 30, seed=41) > 0.72
    col[fieldm & pine] = C_PINE
    col[fieldm & pine & rows_a] = C_PINE_ROW
    col[fieldm & ~pine & rows_a] = C_FIELD_ROW

    # street lattice through towns (geographic grid, ~240m blocks)
    urbm = land & np.isin(cls, [URBAN, URBAN_DENSE])
    se = np.abs(E / 0.24 - np.round(E / 0.24)) * 0.24 < 0.014
    sn = np.abs(N / 0.24 - np.round(N / 0.24)) * 0.24 < 0.014
    col[urbm & (se | sn)] = C_STREET

    # beach band along every shore (overrides class), wet line at water edge
    beachw = 4.5 + smooth_field((H, W), 90, seed=51, lo=0, hi=3.5)
    bm = land & (d_inl < beachw) & (hpx < 4)
    col[bm] = C_SAND
    col[bm & ((fine < 0.2) | (d_inl < 1.8))] = C_SAND_WET
    ditherb = land & (d_inl >= beachw) & (d_inl < beachw + 2.5) & (fine < 0.5)
    col[ditherb] = C_SAND

    # mountain altitude blend + hillshade: verdant slopes, bare rock only
    # near the crests, mossy patches breaking the rock up
    mm = hpx > 1
    t = np.clip((hpx - 16) / 22.0, 0, 1)
    t *= 0.55 + 0.45 * smooth_field((H, W), 70, seed=61)
    tm = t[mm][:, None]
    col[mm] = col[mm] * (1 - tm) + C_ROCK_HIGH * tm
    gx = np.roll(hpx, 2, 1) - np.roll(hpx, -2, 1)
    gy = np.roll(hpx, 2, 0) - np.roll(hpx, -2, 0)
    shade = np.clip((gx * 0.7 + gy * 1.1) * 3.2, -34, 34)
    col[mm] += shade[mm][:, None]
    crag = mm & (fine > 0.945)
    col[crag] -= 20

    col = np.clip(col, 0, 255).astype(np.uint8)

    # ---- relief displacement render. Side pixels are shaded by how steep
    # the drop toward the viewer is: gentle slopes stay near the top color
    # (no contour terracing), sheer faces go dark cliff with striations.
    hint = np.rint(hpx).astype(np.int16)
    out = col.copy()
    stri = (hash_noise((1, W), 13)[0] * 26 - 13).astype(np.float32)
    stri += (np.sin(np.arange(W, dtype=np.float32) * 0.9) * 9.0)  # fluting
    for y in range(H):
        hr = hint[y]
        if not hr.any():
            continue
        hmax = int(hr.max())
        y2 = min(y + 2, H - 1)
        drop = np.clip(hr - hint[y2], 0, 12).astype(np.float32)
        s = np.clip((drop - 1.0) / 5.0, 0, 1)[:, None]
        base_top = col[y].astype(np.float32)
        d_mix = 0.10 + 0.62 * s
        side = base_top * (1 - d_mix) + C_CLIFF[None, :] * d_mix
        side += (stri[:, None] + (fine[y, :, None] * 12 - 6)) * s
        side = np.clip(side, 0, 255).astype(np.uint8)
        for k in range(hmax + 1):
            ty = y - k
            if ty < 0:
                break
            m_side = hr > k
            m_top = hr == k
            if k and m_side.any():
                out[ty, m_side] = side[m_side]
            if k and m_top.any():
                out[ty, m_top] = col[y, m_top]
    print("relief done")

    canvas = Image.fromarray(out, "RGB").convert("RGBA")

    # ---- object sprites, depth-sorted
    rng_global = random.Random(4)
    stamps = []

    def ground_y(px, py):
        xi = int(np.clip(px, 0, W - 1))
        yi = int(np.clip(py, 0, H - 1))
        return py - int(hint[yi, xi])

    for r in range(GRID):
        for c in range(GRID):
            t = tiles[r, c]
            if t not in (FOREST, URBAN, URBAN_DENSE, SAND):
                continue
            rng = random.Random(c * 7919 + r * 104729)
            bx = (c - r) * 16 + origin_x + 16 - x0
            by = (c + r) * 8 + TOP_PAD + 8 - y0
            if not (-40 < bx < W + 40 and -40 < by < H + 40):
                continue
            # painterly thins the stamp field out hard. The map is read
            # from much further away now (maxZoom dropped with the
            # restyle), and at that distance a dense field of 18px
            # sprites is not detail, it is noise that the oil-paint pass
            # then smears into a texture. Fewer, better-spaced objects
            # read as a painted settlement; a carpet of them does not.
            D = 0.45 if STYLE == "painterly" else 1.0
            if t == FOREST:
                lo, hi = (1, 3) if STYLE == "painterly" else (2, 4)
                for _ in range(rng.randrange(lo, hi)):
                    px = bx + rng.randrange(-14, 15)
                    py = by + rng.randrange(-7, 8)
                    stamps.append((py, px, spr_tree(rng,
                                                    tall=rng.random() < .3)))
            elif t == URBAN:
                if rng.random() < 0.8 * D:
                    px = bx + rng.randrange(-8, 9)
                    py = by + rng.randrange(-5, 6)
                    stamps.append((py, px, spr_house(rng)))
                if rng.random() < 0.3 * D:
                    px = bx + rng.randrange(-13, 14)
                    py = by + rng.randrange(-7, 8)
                    stamps.append((py, px, spr_tree(rng)))
            elif t == URBAN_DENSE:
                # downtown keeps its towers at full density in both
                # styles — the skyline IS the landmark, and thinning it
                # is what would actually cost the player information
                px = bx + rng.randrange(-7, 8)
                py = by + rng.randrange(-4, 5)
                stamps.append((py, px, spr_tower(rng)))
                if rng.random() < 0.5 * D:
                    stamps.append((py - 6, px + rng.choice((-12, 12)),
                                   spr_house(rng)))
            elif t == SAND:
                if rng.random() < 0.2 * D:
                    px = bx + rng.randrange(-8, 9)
                    py = by + rng.randrange(-4, 5)
                    xi = int(np.clip(px, 0, W - 1))
                    yi = int(np.clip(py, 0, H - 1))
                    if land[yi, xi]:        # never plant palms in the surf
                        stamps.append((py, px, spr_palm(rng)))

    stamps.sort(key=lambda s: s[0])
    for py, px, spr in stamps:
        im = Image.fromarray(_paint_sprite(spr), "RGBA")
        gy = ground_y(px, py)
        canvas.alpha_composite(im, (int(px - spr.shape[1] // 2),
                                    int(gy - spr.shape[0])))
    print(f"{len(stamps)} sprites stamped")

    # ---- rail viaduct ink
    d = ImageDraw.Draw(canvas)
    LIFT = 7
    for path in grid_data.get("rail_paths", []):
        pts = [((u - v) * 16 + origin_x + 16 - x0,
                (u + v) * 8 + TOP_PAD - y0) for u, v in path]
        acc = 0.0
        for (ax, ay), (bx2, by2) in zip(pts[:-1], pts[1:]):
            acc += ((bx2 - ax) ** 2 + (by2 - ay) ** 2) ** 0.5
            if acc >= 26:
                acc = 0.0
                d.line([(bx2, by2 - LIFT + 1), (bx2, by2 + 1)],
                       fill=(125, 131, 140, 255), width=2)
        # per-segment strokes: thick multi-point polylines grow "bowtie"
        # blobs at sharp joints (the alignment doubles back on itself)
        for (ax, ay), (bx2, by2) in zip(pts[:-1], pts[1:]):
            d.line([(ax, ay - LIFT), (bx2, by2 - LIFT)],
                   fill=(92, 98, 108, 255), width=4)
        for (ax, ay), (bx2, by2) in zip(pts[:-1], pts[1:]):
            d.line([(ax, ay - LIFT - 1), (bx2, by2 - LIFT - 1)],
                   fill=(216, 220, 226, 255), width=2)

    # ---- slices: minimal grid keeping every side < 4096 (old-mobile GL)
    out_dir = ROOT / "site" / "assets" / "map"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{slug}_*.png"):
        old.unlink()
    nx = max(1, math.ceil(W / 4000))
    ny = max(1, math.ceil(H / 4000))
    sw, sh = (W + nx - 1) // nx, (H + ny - 1) // ny
    assert sw < 4096 and sh < 4096, (sw, sh)
    slices = []
    # the painting pass runs on the WHOLE canvas before slicing — doing
    # it per slice would put a seam down every tile boundary, because
    # both the oil-paint kernel and the vignette are position-dependent
    rgb = (painterly_finish(canvas) if STYLE == "painterly"
           else canvas.convert("RGB"))
    i = 0
    for gy in range(ny):
        for gx in range(nx):
            sx, sy = gx * sw, gy * sh
            tile_im = rgb.crop((sx, sy, min(sx + sw, W), min(sy + sh, H)))
            f = f"{slug}_{i}.png"
            tile_im.save(out_dir / f, optimize=True)
            slices.append({"file": f, "x": sx, "y": sy,
                           "w": tile_im.width, "h": tile_im.height})
            i += 1

    # ---- runtime metadata
    def iso_center(c, r):
        return ((c - r) * 16 + origin_x + 16 - x0,
                (c + r) * 8 + TOP_PAD + 8 - y0)

    landmarks = []
    for lm in grid_data["landmarks"]:
        px, py = iso_center(lm["col"], lm["row"])
        landmarks.append({**lm, "px": round(px), "py": round(py)})
    stations = []
    for s in grid_data["stations"]:
        px, py = iso_center(s["col"], s["row"])
        stations.append({**s, "px": round(px), "py": round(py)})

    rngs = random.Random(5)
    sparkles = []
    wet = np.argwhere((tiles == WATER_DEEP) | (tiles == WATER_MID))
    for r, c in wet[rngs.sample(range(len(wet)), min(700, len(wet)))]:
        px, py = iso_center(int(c), int(r))
        if 0 <= px < W and 0 <= py < H:
            sparkles.append([px, py])

    home = next(lm for lm in grid_data["landmarks"]
                if lm["id"] == grid_data["home"])
    meta = {
        "island": slug, "name": grid_data["name"],
        # graded, so the flat sea behind the island rectangles matches
        # the graded water INSIDE them (see graded_deep)
        "w": W, "h": H, "deep": graded_deep(DEEP),
        # lon/lat -> map px for downstream layers (see build_tax_flows.py)
        "transform": {"grid": GRID, "originX": origin_x, "topPad": TOP_PAD,
                      "x0": x0, "y0": y0, "lonC": LON_C, "latC": LAT_C,
                      "kmPerLon": KM_PER_LON, "kmPerLat": KM_PER_LAT,
                      "K": K},
        "slices": slices,
        "landmarks": landmarks,
        "stations": stations,
        "sparkles": sparkles,
        "camera": {"home": [round(v) for v in
                            iso_center(home["col"], home["row"])]},
    }
    map_dir = ROOT / "site" / "map"
    map_dir.mkdir(parents=True, exist_ok=True)
    with open(map_dir / f"{slug}.json", "w") as fh:
        json.dump(meta, fh)
    sizes = [os.path.getsize(out_dir / s["file"]) for s in slices]
    print(f"wrote site/map/{slug}.json;",
          f"png total {sum(sizes)/1e6:.1f}MB")


if __name__ == "__main__":
    main()
