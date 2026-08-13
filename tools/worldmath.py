"""Shared lon/lat -> world-px math for downstream layers.

Points must be converted THROUGH an island's own transform chain
(bake px × scale + anchor from world.json) — never through the world
frame directly — so they land exactly on the drawn geography (each
island bake uses its own kmPerLon). See tools/build_world.py.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_world():
    world = json.loads((ROOT / "site" / "map" / "world.json").read_text())
    metas = {e["slug"]:
             json.loads((ROOT / "site" / "map" /
                         f"{e['slug']}.json").read_text())
             for e in world["islands"]}
    return world, metas


def bake_px(tr, lon, lat):
    e = (lon - tr["lonC"]) * tr["kmPerLon"]
    nn = (lat - tr["latC"]) * tr["kmPerLat"]
    c = (e - nn) / tr["K"] + tr["grid"] / 2
    r = (-e - nn) / tr["K"] + tr["grid"] / 2
    return ((c - r) * 16 + tr["originX"] + 16 - tr["x0"],
            (c + r) * 8 + tr["topPad"] + 8 - tr["y0"])


def world_px(world, metas, lon, lat):
    """-> (island_slug, wx, wy) or None if the point is on no island map."""
    for e in world["islands"]:
        meta = metas[e["slug"]]
        px, py = bake_px(meta["transform"], lon, lat)
        if 0 <= px < meta["w"] and 0 <= py < meta["h"]:
            return (e["slug"],
                    round(e["anchor"][0] + px * e["scale"]),
                    round(e["anchor"][1] + py * e["scale"]))
    return None
