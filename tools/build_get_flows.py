#!/usr/bin/env python3
"""Build the GET (general excise tax) map layer for Capitol Quest.

WHAT THE DATA CAN AND CANNOT DO
-------------------------------
DOTAX publishes GET by *taxation district* only — and there are four
districts: Oʻahu, Maui, Hawaiʻi, Kauaʻi. Oʻahu is a single number. There
is NO sub-island GET geography published anywhere (unlike the income tax,
which Table A-14 breaks out by ZIP). So:

  * MEASURED: Oʻahu's FY2025 GET liability, $2.90B — summed here from the
    twelve monthly "GE liabilities by district" reports and checksummed
    against the June report's own FY2025 cumulative column. Also measured:
    the split by business activity (retailing, hotel rentals, ...).
  * MODELED: where on the island it comes from. We distribute the island
    total across ZIP codes in proportion to Census County Business
    Patterns annual payroll by ZIP (2022) — i.e. where the paid business
    activity actually is. This is an assumption, not a DOTAX figure, and
    the game labels it as such wherever it appears.

Inputs
  data/raw/ge_district/*.pdf    12 monthly DOTAX district reports (FY2025)
  data/raw/2020_Gaz_zcta_national.txt   ZCTA centroids
  Census CBP API (cached to data/raw/cbp_payroll.json)

Output
  site/map/get_flows.json
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "raw" / "ge_district"
GAZ = ROOT / "data" / "raw" / "2020_Gaz_zcta_national.txt"
CBP_CACHE = ROOT / "data" / "raw" / "cbp_payroll.json"
META = ROOT / "site" / "map" / "oahu.json"
OUT = ROOT / "site" / "map" / "get_flows.json"

ACTIVITY_NOTE = {
    "Retailing": "shops, restaurants and bars",
    "Services": "professional, medical and personal services",
    "Contracting": "construction",
    "Hotel Rentals": "hotel and resort room revenue",
    "All Other Rentals": "commercial and residential rents",
    "Wholesaling": "wholesale trade (taxed at 0.5%)",
    "Interest & All Others": "interest and miscellaneous income",
    "Use (4%)": "goods imported from unlicensed sellers",
    "Commissions": "sales commissions",
    "Theater, Amuse., Radio, etc.": "theaters, amusements, broadcasting",
}


def parse_month(path):
    """-> (oahu_total, all_total, fy_cum_all, {activity: oahu_amt})"""
    text = pdfplumber.open(path).pages[0].extract_text()
    acts, grand = {}, None
    for line in text.split("\n"):
        s = line.strip()
        nums = re.findall(r"[\d,]{4,}", s)
        if len(nums) < 5:
            continue
        vals = [int(n.replace(",", "")) for n in nums]
        label = s[:s.find(nums[0])].strip()
        if label.startswith("GRAND TOTAL"):
            if grand is None:                 # first block = liabilities
                grand = (vals[0], vals[4], vals[6] if len(vals) > 6 else None)
            continue
        if label.startswith("SUB-TOTAL") or not label:
            continue
        if grand is None and label:           # activity rows, first block
            acts[label] = acts.get(label, 0) + vals[0]
    return grand[0], grand[1], grand[2], acts


def load_cbp(zips):
    if CBP_CACHE.exists():
        return json.load(open(CBP_CACHE))
    key = (Path.home() / ".census_api_key").read_text().strip()
    out = {}
    for i in range(0, len(zips), 40):
        batch = ",".join(zips[i:i + 40])
        url = ("https://api.census.gov/data/2022/cbp?get=ESTAB,PAYANN"
               f"&for=zipcode:{batch}&NAICS2017=00&key={key}")
        with urllib.request.urlopen(url, timeout=60) as fh:
            rows = json.load(fh)
        for estab, pay, _n, z in rows[1:]:
            out[z] = {"estab": int(estab), "payann": int(pay)}
    json.dump(out, open(CBP_CACHE, "w"))
    print(f"fetched CBP payroll for {len(out)} zips -> cached")
    return out


def main():
    # ---- measured: Oʻahu GET, FY2025
    months = sorted(PDF_DIR.glob("*.pdf"))
    if len(months) != 12:
        raise SystemExit(f"expected 12 monthly reports, found {len(months)}")
    oahu = allsd = 0
    acts = {}
    fy_cum = None
    for p in months:
        o, a, cum, ac = parse_month(p)
        oahu += o
        allsd += a
        fy_cum = cum or fy_cum
        for k, v in ac.items():
            acts[k] = acts.get(k, 0) + v
    if fy_cum and abs(allsd - fy_cum) / fy_cum > 0.005:
        raise SystemExit(f"checksum FAIL: months sum {allsd:,} vs report "
                         f"cumulative {fy_cum:,}")
    print(f"FY2025 GET liability: Oʻahu ${oahu/1e9:.3f}B of statewide "
          f"${allsd/1e9:.3f}B ({100*oahu/allsd:.1f}%) — checksum OK "
          f"(report cumulative ${fy_cum/1e9:.3f}B)")

    # ---- modeled: spread by Census business payroll
    meta = json.load(open(META))
    tr = meta["transform"]

    def lonlat_to_px(lon, lat):
        e = (lon - tr["lonC"]) * tr["kmPerLon"]
        nn = (lat - tr["latC"]) * tr["kmPerLat"]
        c = (e - nn) / tr["K"] + tr["grid"] / 2
        r = (-e - nn) / tr["K"] + tr["grid"] / 2
        return (round((c - r) * 16 + tr["originX"] + 16 - tr["x0"]),
                round((c + r) * 8 + tr["topPad"] + 8 - tr["y0"]))

    cent = {}
    with open(GAZ) as fh:
        next(fh)
        for line in fh:
            f = line.split("\t")
            if f[0].startswith("96"):
                cent[f[0]] = (float(f[6]), float(f[5]))
    on_map = {}
    for z, (lon, lat) in cent.items():
        px, py = lonlat_to_px(lon, lat)
        if 0 <= px < meta["w"] and 0 <= py < meta["h"]:
            on_map[z] = (px, py)
    print(f"{len(on_map)} ZCTAs land inside the Oʻahu map window")

    cbp = load_cbp(sorted(on_map))
    weighted = [(z, on_map[z], cbp[z]["payann"], cbp[z]["estab"])
                for z in on_map if cbp.get(z, {}).get("payann", 0) > 0]
    tot_pay = sum(w[2] for w in weighted)
    zips = []
    for z, (px, py), pay, est in sorted(weighted, key=lambda w: -w[2]):
        zips.append({"zip": z, "px": px, "py": py,
                     "share": round(pay / tot_pay, 6),
                     "getM": round(oahu * pay / tot_pay / 1e6, 2),
                     "estab": est})
    print(f"payroll basis: {len(zips)} zips, ${tot_pay/1e6:,.0f}M annual "
          f"payroll; top: " +
          ", ".join(f"{z['zip']} {100*z['share']:.0f}%" for z in zips[:4]))

    top_acts = sorted(acts.items(), key=lambda kv: -kv[1])
    out = {
        "fy": 2025,
        "island": "Oʻahu",
        "oahuTotal": oahu,
        "stateTotal": allsd,
        "oahuShare": round(oahu / allsd, 4),
        "measured": ("Oʻahu district GET liability, FY2025, summed from the "
                     "12 monthly DOTAX 'GE liabilities by district' reports"),
        "modeled": ("DOTAX publishes GET only island-wide — no sub-island "
                    "geography exists. The spread across the island is "
                    "modeled from Census County Business Patterns (2022) "
                    "annual payroll by ZIP code."),
        "activities": [{"name": k, "amt": v,
                        "note": ACTIVITY_NOTE.get(k, "")}
                       for k, v in top_acts if v > 0],
        "zips": zips,
    }
    json.dump(out, open(OUT, "w"))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
