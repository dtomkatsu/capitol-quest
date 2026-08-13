#!/usr/bin/env python3
"""Compose the eight island bakes into ONE world.

The runtime world is a single continuous north-up iso coordinate frame at
the 0.32 km/tile reference scale (REF_TILE). Every island's baked canvas
is placed at its true geographic position; an island baked at
tile_km = 0.64 (Hawaiʻi) displays at integer 2× so it occupies its true
footprint with crisp pixel doubling.

World-frame math mirrors build_map.py: for a point at (lon, lat),
  e  = (lon - LON_W) * KM_PER_LON_W        # km east of the world center
  nn = (lat - LAT_W) * KM_PER_LAT          # km north
  world_x = 32 * e / K_REF + X0
  world_y = -16 * nn / K_REF + Y0
Anchors are chosen so each island's own CENTER lands exactly at its
world-frame position; the ~1% kmPerLon difference between an island's
local frame and the world frame is invisible at island scale. Downstream
layers must convert lon/lat to world px THROUGH an island's own transform
chain (bake px × scale + anchor — see world_px() in build_tax_flows.py),
never through the world frame directly, so points land exactly on the
drawn geography.

Outputs
  site/map/world.json            world dims, per-island anchor/scale,
                                 Capitol world position
  site/assets/map/overview.png   1/12-scale stitch of all bakes — the
                                 always-loaded zoomed-out backdrop
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image

from islands import ISLANDS, ORDER

ROOT = Path(__file__).resolve().parent.parent

REF_TILE = 0.32
K_REF = REF_TILE * math.sqrt(2.0)
LON_W, LAT_W = -157.5, 20.6            # mid-chain
KM_PER_LON_W = 104.0
KM_PER_LAT = 110.9
PAD = 400                              # world-edge padding, ref px
OV = 12                                # overview downscale factor
DEEP = "#1c5490"


def world_xy_raw(lon, lat):
    e = (lon - LON_W) * KM_PER_LON_W
    nn = (lat - LAT_W) * KM_PER_LAT
    return 32.0 * e / K_REF, -16.0 * nn / K_REF


def bake_px(tr, lon, lat):
    """lon/lat -> baked-canvas px via an island's own transform block."""
    e = (lon - tr["lonC"]) * tr["kmPerLon"]
    nn = (lat - tr["latC"]) * tr["kmPerLat"]
    c = (e - nn) / tr["K"] + tr["grid"] / 2
    r = (-e - nn) / tr["K"] + tr["grid"] / 2
    return ((c - r) * 16 + tr["originX"] + 16 - tr["x0"],
            (c + r) * 8 + tr["topPad"] + 8 - tr["y0"])


def main():
    metas = {s: json.loads((ROOT / "site" / "map" / f"{s}.json").read_text())
             for s in ORDER}

    # raw anchors (world frame, before shifting into positive coords)
    entries = []
    for slug in ORDER:
        meta = metas[slug]
        tr = meta["transform"]
        scale = tr["K"] / K_REF
        assert abs(scale - round(scale)) < 1e-9, \
            f"{slug}: tile_km must be an integer multiple of {REF_TILE}"
        scale = int(round(scale))
        wx, wy = world_xy_raw(tr["lonC"], tr["latC"])
        bx, by = bake_px(tr, tr["lonC"], tr["latC"])
        entries.append({
            "slug": slug, "name": meta["name"], "scale": scale,
            "w": meta["w"], "h": meta["h"],
            "ax": wx - bx * scale, "ay": wy - by * scale,
        })

    x0 = min(e["ax"] for e in entries) - PAD
    y0 = min(e["ay"] for e in entries) - PAD
    x1 = max(e["ax"] + e["w"] * e["scale"] for e in entries) + PAD
    y1 = max(e["ay"] + e["h"] * e["scale"] for e in entries) + PAD
    W, H = int(math.ceil(x1 - x0)), int(math.ceil(y1 - y0))
    for e in entries:
        e["anchor"] = [round(e["ax"] - x0), round(e["ay"] - y0)]
        del e["ax"], e["ay"]
    print(f"world {W}x{H} ref px ({W*REF_TILE/math.sqrt(2)/16:.0f} km wide)")

    # Capitol world position via the Oʻahu chain
    oahu = next(e for e in entries if e["slug"] == "oahu")
    cap = next(lm for lm in metas["oahu"]["landmarks"]
               if lm["id"] == "capitol")
    capitol = [round(oahu["anchor"][0] + cap["px"] * oahu["scale"]),
               round(oahu["anchor"][1] + cap["py"] * oahu["scale"])]

    # island rects double as fly-to targets and label spots
    world = {
        "w": W, "h": H, "deep": DEEP,
        "ref_tile_km": REF_TILE,
        "frame": {"lonW": LON_W, "latW": LAT_W,
                  "kmPerLonW": KM_PER_LON_W, "kmPerLat": KM_PER_LAT,
                  "K": K_REF, "x0": round(x0, 1), "y0": round(y0, 1)},
        "capitol": capitol,
        "overview": {"file": "overview.png", "scale": OV},
        "islands": entries,
    }
    out = ROOT / "site" / "map" / "world.json"
    out.write_text(json.dumps(world))
    print(f"wrote {out.relative_to(ROOT)}: capitol at {capitol}")

    # ---- overview stitch (1/OV scale, BOX filter = area average)
    ov = Image.new("RGB", (math.ceil(W / OV), math.ceil(H / OV)),
                   tuple(int(DEEP[i:i + 2], 16) for i in (1, 3, 5)))
    for e in entries:
        meta = metas[e["slug"]]
        full = Image.new("RGB", (meta["w"], meta["h"]))
        for s in meta["slices"]:
            im = Image.open(ROOT / "site" / "assets" / "map" / s["file"])
            full.paste(im, (s["x"], s["y"]))
        tw = max(1, round(meta["w"] * e["scale"] / OV))
        th = max(1, round(meta["h"] * e["scale"] / OV))
        ov.paste(full.resize((tw, th), Image.BOX),
                 (round(e["anchor"][0] / OV), round(e["anchor"][1] / OV)))
    ov_path = ROOT / "site" / "assets" / "map" / "overview.png"
    ov.save(ov_path, optimize=True)
    print(f"wrote overview.png {ov.width}x{ov.height} "
          f"({ov_path.stat().st_size/1e6:.1f}MB)")


if __name__ == "__main__":
    main()
