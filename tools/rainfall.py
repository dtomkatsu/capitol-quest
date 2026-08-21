"""Shared access to the baked Rainfall Atlas raster.

`tools/build_rainfall.py` writes `data/rainfall_mm.png` (16-bit, mm/yr)
+ its affine header; both `build_map.py` (what grows where) and
`render_map.py` (what colour it is) read the field through here, so the
tile classification and the painted ground can never disagree about
whether a place is wet.

The ramps live here for the same reason. `wetness()` is the ONE curve
that says how dry counts as dry: it is logarithmic because rainfall in
Hawaiʻi spans a factor of forty and a linear ramp would put Kīhei
(280 mm) and Honolulu (900 mm) in the same bucket at the dry end while
spending most of its range separating shades of rainforest nobody can
tell apart.

Islands outside atlas coverage (Niʻihau) fall back to the `rain_mm`
constant in tools/islands.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PNG = ROOT / "data" / "rainfall_mm.png"
HDR = ROOT / "data" / "rainfall_mm.json"

_A = None          # mm/yr, float32 (h, w)
_H = None          # header dict

# ramp stops, mm/yr. DRY sits just under the driest inhabited leeward
# coasts (Kawaihae 254, Kīhei 280) so they land at 0; WET at Hilo's
# 3674 mm so the windward side saturates. LUSH_* adds the last touch of
# depth for the true rainforest (Koʻolau crest, Hāna, Kohala windward).
DRY_MM = 300.0
WET_MM = 3000.0
LUSH_LO = 2200.0
LUSH_HI = 5000.0


def reload():
    """(Re)read the baked raster. Safe to call repeatedly."""
    global _A, _H
    _H = json.loads(HDR.read_text())
    _A = np.asarray(Image.open(PNG), np.float32)
    return _A, _H


def _ensure():
    if _A is None:
        if not PNG.exists():
            raise SystemExit(
                "data/rainfall_mm.png missing — run "
                "`python3 tools/build_rainfall.py` first")
        reload()
    return _A, _H


def covers(lon, lat):
    """Bool mask: inside the atlas grid (Niʻihau is not)."""
    a, h = _ensure()
    x = (np.asarray(lon) - h["lon0"]) / h["dlon"]
    y = (np.asarray(lat) - h["lat0"]) / h["dlat"]
    return (x >= 0) & (x <= h["w"] - 1) & (y >= 0) & (y <= h["h"] - 1)


def sample(lon, lat, default=np.nan):
    """Bilinear mean-annual rainfall, mm/yr, at lon/lat arrays.

    Points outside the atlas grid get `default` — pass the island's
    modelled `rain_mm` for Niʻihau.
    """
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
    return np.where(inside, v, default).astype(np.float32)


def sample_grid(cfg, lon, lat):
    """`sample()` with an island config's out-of-coverage fallback."""
    return sample(lon, lat, default=float(cfg.get("rain_mm", 1200)))


def wetness(rain_mm):
    """mm/yr -> 0 (leeward desert) … 1 (windward wet), log ramp."""
    r = np.maximum(np.asarray(rain_mm, np.float32), 1.0)
    w = (np.log(r) - np.log(DRY_MM)) / (np.log(WET_MM) - np.log(DRY_MM))
    return np.clip(w, 0.0, 1.0)


def lushness(rain_mm):
    """0 … 1 over the rainforest end only — the extra depth of green
    that separates Hāna and the Koʻolau crest from ordinary wet."""
    r = np.asarray(rain_mm, np.float32)
    return np.clip((r - LUSH_LO) / (LUSH_HI - LUSH_LO), 0.0, 1.0)
