#!/usr/bin/env python3
"""Build the STATEWIDE GET (general excise tax) map layer.

WHAT THE DATA CAN AND CANNOT DO
-------------------------------
DOTAX publishes GET by *taxation district* only — Oʻahu, Maui, Hawaiʻi,
Kauaʻi (the Maui district covers Maui + Molokaʻi + Lānaʻi; Kauaʻi covers
Kauaʻi + Niʻihau). There is NO sub-island GET geography published
anywhere (unlike the income tax, which Table A-14 breaks out by ZIP). So:

  * MEASURED: each district's FY2025 GET liability — summed here from the
    twelve monthly "GE liabilities by district" reports; the statewide sum
    is checksummed against the June report's own FY2025 cumulative column.
    Also measured: the split by business activity (statewide).
  * MODELED: where within each district it comes from. This is an
    assumption, not a DOTAX figure, and the game labels it as such
    wherever it appears. Two bases (--basis):

      population (DEFAULT) — allocate each district's total by residents
        per ZIP (ACS 5-year) across that district's islands. GET is
        charged on virtually every transaction and passed through to
        customers; this says "everyone is paying, all the time."
      payroll — allocate by Census County Business Patterns annual
        payroll per ZIP (where businesses REMIT from). Truer to legal
        incidence, but it collapses everything onto the commercial cores.

    District totals are never reallocated across districts — only the
    within-district spread is modeled.

Inputs
  data/raw/ge_district/*.pdf    12 monthly DOTAX district reports (FY2025)
  data/raw/2020_Gaz_zcta_national.txt   ZCTA centroids
  Census ACS5 / CBP APIs (cached under data/raw/, fetched incrementally)

Output
  site/map/get_flows.json   world-px zips, district + statewide totals
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

import pdfplumber

from worldmath import load_world, world_px

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "raw" / "ge_district"
GAZ = ROOT / "data" / "raw" / "2020_Gaz_zcta_national.txt"
CBP_CACHE = ROOT / "data" / "raw" / "cbp_payroll.json"
POP_CACHE = ROOT / "data" / "raw" / "acs_population.json"
OUT = ROOT / "site" / "map" / "get_flows.json"

DISTRICTS = ["oahu", "maui", "hawaii", "kauai"]   # PDF column order
DISTRICT_ISLANDS = {
    "oahu": ["oahu"],
    "maui": ["maui", "molokai", "lanai", "kahoolawe"],
    "hawaii": ["hawaii"],
    "kauai": ["kauai", "niihau"],
}
ISLAND_DISTRICT = {i: d for d, isls in DISTRICT_ISLANDS.items()
                   for i in isls}

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
    """-> (district_amts[4], all_total, fy_cum_all, {activity: state_amt})

    Row columns: OAHU MAUI HAWAII KAUAI [UNKNOWN] ALL prev-yr-month
    FY-cum FY-prev pct. The regex needs >= 4 chars, so an UNKNOWN of 0
    never matches; when it is >= 1,000 it shifts everything right by one.
    """
    text = pdfplumber.open(path).pages[0].extract_text()
    acts, grand = {}, None
    for line in text.split("\n"):
        s = line.strip()
        nums = re.findall(r"[\d,]{4,}", s)
        if len(nums) < 5:
            continue
        vals = [int(n.replace(",", "")) for n in nums]
        off = 1 if len(vals) >= 9 else 0        # UNKNOWN column visible
        label = s[:s.find(nums[0])].strip()
        if label.startswith("GRAND TOTAL"):
            if grand is None:                 # first block = liabilities
                grand = (vals[0:4], vals[4 + off],
                         vals[6 + off] if len(vals) > 6 + off else None)
            continue
        if label.startswith("SUB-TOTAL") or not label:
            continue
        if grand is None and label:           # activity rows, first block
            acts[label] = acts.get(label, 0) + vals[4 + off]
    return grand[0], grand[1], grand[2], acts


def _key():
    return (Path.home() / ".census_api_key").read_text().strip()


def _fetch(cache_path, zips, url_fn, parse_rows, tag):
    """Incremental Census cache: fetch only zips missing from the cache.

    Two Census behaviours this has to survive, both hit live:

    * **A batch where NO zip has data returns HTTP 204 with an empty
      body**, not an empty JSON array. `json.load` on that raises
      "Expecting value: line 1 column 1", which reads exactly like a bad
      API key and is not one. Three real Hawaiʻi ZCTAs (96742, 96747,
      96774) have no CBP record at all, so this fired on every run.
    * A zip the API simply never returns must be REMEMBERED as absent.
      Caching only the hits meant those three counted as "missing"
      forever, so every run re-requested them and re-crashed. They are
      now written back as null and skipped next time.

    (A genuinely bad key is different again: HTTP 200 with an HTML
    "Invalid Key" body. That still raises here, which is correct — it
    IS an error — but the message now says which.)
    """
    out = json.load(open(cache_path)) if cache_path.exists() else {}
    missing = [z for z in zips if z not in out]
    for i in range(0, len(missing), 40):
        chunk = missing[i:i + 40]
        with urllib.request.urlopen(url_fn(",".join(chunk)), timeout=60) as fh:
            status = getattr(fh, "status", 200)
            body = fh.read()
        if status == 204 or not body.strip():
            continue                       # no data for any zip in chunk
        try:
            rows = json.loads(body)
        except json.JSONDecodeError:
            head = body[:120].decode("utf-8", "replace").strip()
            raise SystemExit(
                f"{tag}: Census returned non-JSON (HTTP {status}). This is "
                f"usually a bad/expired key in ~/.census_api_key — a bad "
                f"key answers 200 with HTML, not 401. Body starts: {head}")
        parse_rows(rows, out)
    # remember the misses too, or they are re-requested on every run
    for z in missing:
        out.setdefault(z, None)
    if missing:
        json.dump(out, open(cache_path, "w"))
        got = sum(1 for z in missing if out.get(z) is not None)
        print(f"fetched {tag} for {got}/{len(missing)} new zips "
              f"({len(missing) - got} have no record) -> cached")
    return out


def load_cbp(zips):
    return _fetch(
        CBP_CACHE, zips,
        lambda b: ("https://api.census.gov/data/2022/cbp?get=ESTAB,PAYANN"
                   f"&for=zipcode:{b}&NAICS2017=00&key={_key()}"),
        lambda rows, out: out.update(
            {z: {"estab": int(e), "payann": int(p)}
             for e, p, _n, z in rows[1:]}),
        "CBP payroll")


def load_pop(zips):
    return _fetch(
        POP_CACHE, zips,
        lambda b: ("https://api.census.gov/data/2022/acs/acs5"
                   "?get=B01003_001E"
                   f"&for=zip%20code%20tabulation%20area:{b}&key={_key()}"),
        lambda rows, out: out.update(
            {z: {"pop": int(p)} for p, z in rows[1:]}),
        "ACS population")


def main():
    # ---- measured: district GET, FY2025
    months = sorted(PDF_DIR.glob("*.pdf"))
    if len(months) != 12:
        raise SystemExit(f"expected 12 monthly reports, found {len(months)}")
    dist = {d: 0 for d in DISTRICTS}
    allsd = 0
    acts = {}
    fy_cum = None
    for p in months:
        damts, a, cum, ac = parse_month(p)
        for d, v in zip(DISTRICTS, damts):
            dist[d] += v
        allsd += a
        fy_cum = cum or fy_cum
        for k, v in ac.items():
            acts[k] = acts.get(k, 0) + v
    if fy_cum and abs(allsd - fy_cum) / fy_cum > 0.005:
        raise SystemExit(f"checksum FAIL: months sum {allsd:,} vs report "
                         f"cumulative {fy_cum:,}")
    dsum = sum(dist.values())
    if abs(dsum - allsd) / allsd > 0.005:
        raise SystemExit(f"district sum {dsum:,} != statewide {allsd:,}")
    print("FY2025 GET liability by district ($B): " +
          ", ".join(f"{d} {v/1e9:.3f}" for d, v in dist.items()) +
          f" — statewide ${allsd/1e9:.3f}B, checksum OK "
          f"(report cumulative ${fy_cum/1e9:.3f}B)")

    # ---- place every HI ZCTA on the world map
    world, metas = load_world()
    cent = {}
    with open(GAZ) as fh:
        next(fh)
        for line in fh:
            f = line.split("\t")
            if f[0].startswith("96"):
                cent[f[0]] = (float(f[6]), float(f[5]))
    on_map = {}
    for z, (lon, lat) in cent.items():
        hit = world_px(world, metas, lon, lat)
        if hit:
            on_map[z] = hit
    print(f"{len(on_map)} ZCTAs land on the eight-island world")

    basis = "payroll" if "--basis=payroll" in sys.argv else "population"
    # Both series ride along in the output as context, but only ONE is
    # the modelling basis. The basis series is REQUIRED — if it can't be
    # fetched the spread would be wrong and the build must stop. The
    # other is decorative, so a Census-side hiccup degrades it to zeros
    # instead of killing a build that never depended on it. (Before
    # this, a CBP outage broke the default population build outright.)
    def optional(loader, tag):
        try:
            return loader(sorted(on_map))
        except (SystemExit, OSError, ValueError) as e:
            print(f"warning: {tag} unavailable, writing zeros ({e})")
            return {}

    if basis == "payroll":
        cbp = load_cbp(sorted(on_map))
        pop = optional(load_pop, "ACS population")
    else:
        pop = load_pop(sorted(on_map))
        cbp = optional(load_cbp, "CBP payroll")
    # `or {}` — a cached zip with no Census record is stored as null
    raw = ({z: (cbp.get(z) or {}).get("payann", 0) for z in on_map}
           if basis == "payroll" else
           {z: (pop.get(z) or {}).get("pop", 0) for z in on_map})

    # ---- spread each district's measured total within its own islands
    zips = []
    for d in DISTRICTS:
        dz = [(z, on_map[z], raw[z]) for z in on_map
              if ISLAND_DISTRICT[on_map[z][0]] == d and raw[z] > 0]
        tot = sum(w for _, _, w in dz)
        if not tot:
            continue
        for z, (slug, px, py), w in sorted(dz, key=lambda t: -t[2]):
            amt = dist[d] * w / tot
            zips.append({"zip": z, "island": slug, "district": d,
                         "px": px, "py": py,
                         "share": round(amt / allsd, 6),
                         "getM": round(amt / 1e6, 2),
                         "pop": (pop.get(z) or {}).get("pop", 0),
                         "payann": (cbp.get(z) or {}).get("payann", 0)})
    zips.sort(key=lambda z: -z["getM"])
    print(f"{basis} basis: {len(zips)} zips; top: " +
          ", ".join(f"{z['zip']} ({z['island']}) ${z['getM']:.0f}M"
                    for z in zips[:4]))

    top_acts = sorted(acts.items(), key=lambda kv: -kv[1])
    out = {
        "fy": 2025,
        "total": allsd,
        "districts": dist,
        "basis": basis,
        "measured": ("GET liability by taxation district, FY2025, summed "
                     "from the 12 monthly DOTAX 'GE liabilities by "
                     "district' reports (statewide checksummed against "
                     "the June cumulative)"),
        "modeled": (
            "DOTAX publishes GET per district only — no sub-island "
            "geography exists. Each district's measured total is spread "
            "within its own islands by where people live (Census ACS "
            "5-year population by ZIP): GET is charged on nearly every "
            "transaction and passed through to customers, so residents "
            "everywhere pay it."
            if basis == "population" else
            "DOTAX publishes GET per district only — no sub-island "
            "geography exists. Each district's measured total is spread "
            "within its own islands by Census County Business Patterns "
            "(2022) annual payroll by ZIP — where businesses remit from, "
            "not where the buyers are."),
        "activities": [{"name": k, "amt": v,
                        "note": ACTIVITY_NOTE.get(k, "")}
                       for k, v in top_acts if v > 0],
        "zips": zips,
    }
    json.dump(out, open(OUT, "w"))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
