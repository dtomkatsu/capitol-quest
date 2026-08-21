#!/usr/bin/env python3
"""Bake the Rainfall Atlas of Hawaiʻi into one compact raster for the map.

Hawaiʻi's greenness is not decoration — it is the single most legible
fact of the islands' geography: Waiʻaleʻale takes ~10 m of rain a year
while Kawaihae, 300 km away, takes 25 cm. Painting the whole chain the
same tropical green is the map telling a lie the player can check out a
car window. This tool turns the measured field into something the bake
can read.

Source
  Rainfall Atlas of Hawaiʻi — mean annual rainfall, 250 m grid
  Giambelluca, T.W., Q. Chen, A.G. Frazier, J.P. Price, Y.-L. Chen,
  P.-S. Chu, J.K. Eischeid, and D.M. Delparte, 2013: Online Rainfall
  Atlas of Hawaiʻi. Bull. Amer. Meteor. Soc. 94, 313-316.
  https://www.hawaii.edu/climate-data-portal/rainfall-atlas/
  Grid: StateRFGrids_mm.zip -> staterf_mmann (WGS84, 0.00225°, mm/yr)

The download (14 MB of ESRI ADF) stays OUT of git, exactly like the TOD
road centerlines: `data/raw/rainfall/` is gitignored and this script
re-fetches it on demand. What IS committed is the small derived raster
this writes:

  data/rainfall_mm.png     16-bit grayscale, value = mm/yr
  data/rainfall_mm.json    affine + provenance header

Ocean cells carry no atlas value; they are filled from the nearest land
cell so that a sample anywhere near a coastline is stable (the renderer
samples per PIXEL, and its coastline is the real polygon, not the atlas
land mask — without the fill every shore would flicker to zero).

NOT COVERED: Niʻihau (the atlas grid stops at lon -159.816). Islands
outside coverage fall back to `rain_mm` in tools/islands.py — see
tools/rainfall.py.

Usage:
  python3 tools/build_rainfall.py            # fetch if missing, then bake
  python3 tools/build_rainfall.py --refresh  # re-download the atlas grid
"""

from __future__ import annotations

import argparse
import json
import subprocess
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "rainfall"
GRID = RAW / "staterf_mmann"
ZIP_URL = ("https://atlas.uhtapis.org/rainfall/assets/files/GISLayers/"
           "StateRFGrids_mm.zip")
ZIP_PATH = RAW / "StateRFGrids_mm.zip"

OUT_PNG = ROOT / "data" / "rainfall_mm.png"
OUT_HDR = ROOT / "data" / "rainfall_mm.json"

# QA points, printed every build and checked against the published atlas
# (values in the atlas's own units, inches, in the comment).
QA = [
    ("Waiʻaleʻale, Kauaʻi", -159.4983, 22.0722, 9000, 11000),   # ~390 in
    ("Mānoa, Oʻahu", -157.8083, 21.3156, 1600, 3200),           # ~85 in
    ("Waiʻanae town, Oʻahu", -158.1850, 21.4470, 350, 800),      # ~21 in
    ("Kīhei, Maui", -156.4450, 20.7650, 200, 450),               # ~11 in
    ("Hilo, Hawaiʻi", -155.0900, 19.7200, 3000, 4200),           # ~145 in
    ("Kawaihae, Hawaiʻi", -155.8300, 20.0300, 180, 400),         # ~10 in
    ("Mauna Kea summit", -155.4700, 19.8200, 150, 400),          # ~8 in
    ("Kahoʻolawe", -156.6200, 20.5450, 250, 700),                # ~16 in
]


def fetch(refresh=False):
    RAW.mkdir(parents=True, exist_ok=True)
    if GRID.exists() and not refresh:
        return
    if not ZIP_PATH.exists() or refresh:
        print(f"downloading {ZIP_URL} …")
        subprocess.run(["curl", "-sSL", "--max-time", "600",
                        "-o", str(ZIP_PATH), ZIP_URL], check=True)
    with zipfile.ZipFile(ZIP_PATH) as z:
        names = [n for n in z.namelist()
                 if n.startswith(("staterf_mmann/", "info/"))]
        z.extractall(RAW, names)
    print(f"extracted {GRID.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-download the atlas grid")
    args = ap.parse_args()
    fetch(args.refresh)

    import rasterio
    from scipy import ndimage

    src = rasterio.open(GRID)
    if str(src.crs).upper() != "EPSG:4326":
        raise SystemExit(f"expected WGS84, got {src.crs}")
    a = src.read(1)
    t = src.transform
    valid = np.isfinite(a) & (a > -1e30) & (a < 1e6)
    print(f"atlas {src.width}x{src.height} @ {t.a:.5f}°, "
          f"{valid.sum()/1e3:.0f}k valid cells "
          f"({100*valid.mean():.1f}% — the rest is ocean)")
    v = a[valid]
    print(f"range {v.min():.0f}–{v.max():.0f} mm/yr, mean {v.mean():.0f}")

    # ---- nearest-land fill so coastal samples never fall into the hole
    _, idx = ndimage.distance_transform_edt(~valid, return_indices=True)
    filled = a[tuple(idx)]
    filled = np.clip(np.rint(filled), 0, 65535).astype(np.uint16)

    Image.fromarray(filled, "I;16").save(OUT_PNG, optimize=True)
    hdr = {
        "units": "mm/yr",
        "variable": "mean annual rainfall",
        "source": "Rainfall Atlas of Hawaiʻi (Giambelluca et al. 2013), "
                  "staterf_mmann, 250 m",
        "url": ZIP_URL,
        "note": "ocean cells filled from the nearest land cell; "
                "Niʻihau is outside atlas coverage (see islands.py "
                "rain_mm)",
        "w": src.width, "h": src.height,
        # cell CENTER of pixel (x, y): lon0 + x*dlon, lat0 + y*dlat
        "lon0": t.c + t.a / 2, "lat0": t.f + t.e / 2,
        "dlon": t.a, "dlat": t.e,
    }
    OUT_HDR.write_text(json.dumps(hdr, indent=1))
    print(f"wrote {OUT_PNG.relative_to(ROOT)} "
          f"({OUT_PNG.stat().st_size/1e6:.1f}MB) + "
          f"{OUT_HDR.relative_to(ROOT)}")

    # ---- QA against the published atlas
    import rainfall
    rainfall.reload()
    bad = 0
    for name, lon, lat, lo, hi in QA:
        got = float(rainfall.sample(np.array([lon]), np.array([lat]))[0])
        ok = lo <= got <= hi
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {name:24s} {got:6.0f} mm "
              f"({got/25.4:5.1f} in) expect {lo}–{hi}")
    if bad:
        raise SystemExit(f"{bad} QA point(s) out of range")


if __name__ == "__main__":
    main()
