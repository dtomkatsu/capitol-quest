"""Shared access to the baked DEM (see tools/build_elevation.py).

Pixel-aligned with the rainfall raster — same affine, same sampling
maths — so build_map and render_map read BOTH physical fields the same
way. Elevation drives what the mountains ARE (heights, sea cliffs,
alpine rock, where a sand beach can exist); rainfall drives what colour
the ground is. Between the two, the terrain stops being art direction.

`height_units()` is the ONE curve from metres to the renderer's height
units (the relief displacer's row-lift px, pre its own 2.1×): a power
law, because a linear scale must choose between a flat Koʻolau and a
Mauna Kea that lifts off the canvas. 0.082·m^0.78 keeps the Koʻolau
crest (~960 m) at the ~16 units the map already drew it at, and lands
Mauna Kea (4207 m) at ~56 — towering, but attached to the island.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PNG = ROOT / "data" / "elevation_m.png"
HDR = ROOT / "data" / "elevation_m.json"

_A = None
_H = None


def reload():
    global _A, _H
    _H = json.loads(HDR.read_text())
    _A = np.asarray(Image.open(PNG), np.float32)
    return _A, _H


def _ensure():
    if _A is None:
        if not PNG.exists():
            raise SystemExit(
                "data/elevation_m.png missing — run "
                "`python3 tools/build_elevation.py` first")
        reload()
    return _A, _H


def sample(lon, lat):
    """Bilinear elevation (m) at lon/lat arrays; 0 outside the grid."""
    a, h = _ensure()
    lon = np.asarray(lon, np.float32)
    lat = np.asarray(lat, np.float32)
    x = (lon - h["lon0"]) / h["dlon"]
    y = (lat - h["lat0"]) / h["dlat"]
    inside = (x >= 0) & (x <= h["w"] - 1) & (y >= 0) & (y <= h["h"] - 1)
    xc = np.clip(x, 0, h["w"] - 1.001)
    yc = np.clip(y, 0, h["h"] - 1.001)
    x0 = xc.astype(np.int32)
    y0 = yc.astype(np.int32)
    fx = xc - x0
    fy = yc - y0
    v = (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy) +
         a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)
    return np.where(inside, v, 0.0).astype(np.float32)


def height_units(elev_m):
    """metres -> renderer height units (see module docstring)."""
    e = np.maximum(np.asarray(elev_m, np.float32), 0.0)
    return 0.082 * np.power(e, 0.78)


# where a SAND BEACH can physically exist: the shore is depositional
# only where the land behind it is low — under a pali or on a lava
# bench the coast is rock. Metres of elevation a short way inland is a
# clean proxy the 250 m grid actually resolves.
BEACH_MAX_M = 24.0


def beachable(elev_m):
    """Bool/float mask: low enough ground for a sand shore."""
    return np.asarray(elev_m, np.float32) < BEACH_MAX_M
