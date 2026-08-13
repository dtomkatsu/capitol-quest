#!/usr/bin/env python3
"""Build the STATEWIDE income-tax inflow layer from DOTAX records.

Source: DOTAX "Hawaiʻi Individual Income Tax Statistics" (tax year 2022),
Table A-14 — selected data from resident tax returns BY ZIP CODE:
number of returns, Hawaiʻi AGI, and tax liability (after credits).
  data/raw/2022indinc_tables.xlsx
  (from https://files.hawaii.gov/tax/stats/stats/indinc/2022indinc_tables.xlsx)

All county sections are parsed (Oʻahu, Maui County, Hawaiʻi, Kauaʻi);
STATE total sections are skipped. Every ZIP is placed geometrically: its
Census-gazetteer centroid is run through worldmath.world_px(), which maps
it through the containing island's bake transform onto the one-world
canvas — so streams land exactly on the drawn geography of all eight
islands. PO-box-only zips (no ZCTA) fall back to the mean location of
the located zips in the same DOTAX "geographic area"; if none exists,
they're dropped (logged).

Output: site/map/tax_flows.json — per-zip tax liability with WORLD px,
ready for the runtime flow layer (motes arc from every island into the
Capitol).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import openpyxl

from worldmath import load_world, world_px

ROOT = Path(__file__).resolve().parent.parent

XLSX = ROOT / "data" / "raw" / "2022indinc_tables.xlsx"
GAZ = ROOT / "data" / "raw" / "2020_Gaz_zcta_national.txt"
OUT = ROOT / "site" / "map" / "tax_flows.json"

SHEETS = ["A14-1", "A14-2", "A14-3", "A14-4"]
# section headers look like "O'AHU", "O'AHU (CONT.)", "MAUI COUNTY", ...


def parse_a14():
    """Yield (zip, area, returns, tax_after_credits_million), all counties."""
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    in_state_section = False
    rows = []
    for name in SHEETS:
        for row in wb[name].iter_rows(values_only=True):
            zipc, area = row[0], row[1]
            if zipc is None and isinstance(area, str) and row[2] is None:
                label = area.strip().upper().replace("‘", "'") \
                    .replace("ʻ", "'")
                if "COUNTY" in label or "O'AHU" in label or "STATE" in label:
                    in_state_section = label.startswith("STATE")
                continue
            if in_state_section or zipc is None:
                continue
            z = str(zipc).strip()[:5]
            if not z.isdigit():
                continue
            returns = row[2]
            tax_m = row[14]            # tax liability AFTER credits, $M
            if returns is None or tax_m is None:
                continue
            rows.append((z, str(area).strip(), int(returns), float(tax_m)))
    return rows


def load_centroids():
    cent = {}
    with open(GAZ) as fh:
        next(fh)
        for line in fh:
            parts = line.split("\t")
            z = parts[0].strip()
            if z.startswith("96"):
                cent[z] = (float(parts[6]), float(parts[5]))  # lon, lat
    return cent


def main():
    world, metas = load_world()
    rows = parse_a14()
    cent = load_centroids()
    print(f"A-14 rows (all counties): {len(rows)}")

    # area fallback for PO-box zips: mean of located zips in the same area
    area_pts = defaultdict(list)
    for z, area, _, _ in rows:
        if z in cent:
            area_pts[area].append(cent[z])

    zips, dropped = [], []
    per_island = defaultdict(float)
    for z, area, returns, tax_m in rows:
        if tax_m <= 0:
            continue
        if z in cent:
            lon, lat = cent[z]
        elif area_pts[area]:
            pts = area_pts[area]
            lon = sum(p[0] for p in pts) / len(pts)
            lat = sum(p[1] for p in pts) / len(pts)
        else:
            dropped.append(z)
            continue
        hit = world_px(world, metas, lon, lat)
        if hit is None:
            dropped.append(z + " (off-map)")
            continue
        slug, px, py = hit
        per_island[slug] += tax_m
        zips.append({"zip": z, "area": area, "island": slug,
                     "returns": returns, "taxM": round(tax_m, 3),
                     "px": px, "py": py})

    total = sum(z["taxM"] for z in zips)
    print(f"kept {len(zips)} zips, total ${total/1000:.2f}B; "
          f"dropped: {dropped}")
    for slug, amt in sorted(per_island.items(), key=lambda kv: -kv[1]):
        print(f"  {slug:10s} ${amt:7.0f}M")

    out = {
        "source": ("DOTAX, Hawaiʻi Individual Income Tax Statistics, "
                   "Tax Year 2022, Table A-14"),
        "measure": "resident individual income tax liability after credits",
        "year": 2022,
        "totalM": round(total, 1),
        "islands": {k: round(v, 1) for k, v in per_island.items()},
        "zips": sorted(zips, key=lambda z: -z["taxM"]),
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
