#!/usr/bin/env python3
"""Build the revenue-mix dataset: FY2027 PROJECTED general-fund taxes.

The money-in drill shows the taxes that fill the 💰 General-funds node of
the FY2027 budget, so the mix must be the FY2027 projection, not FY2025
actuals (the old DOTAX Table 1.8 version of this tool is in git history).

Sources (both in data/raw/):
  fy27supp_revenue_basis.pdf — "Tables Indicating the Basis for Revenue
    Estimates", FY27 Executive Supplemental Budget, B&F, Dec 2025.
    p2: Tax Research & Planning's line-item allocation of the Council on
    Revenues 2025-09-04 forecast (general fund, by tax type, $ thousands).
    p3: county GET surcharge estimates (context — never general fund).
    https://budget.hawaii.gov/wp-content/uploads/2025/12/04.-Tables-Indicating-the-Basis-for-Revenue-Estimates-FY-27-SUPP.xApH_.pdf
  cor_gf_2026-05-21.pdf — Council on Revenues report to the Governor,
    May 21 2026 meeting: the LATEST official general-fund forecast
    (FY2027 +1.0% on a raised FY2026 base).
    https://files.hawaii.gov/tax/useful/cor/2026-05-21-GF%20Rpt2-GOV_Final.pdf

Method (mirrors TRPO's own): take the Dec-2025 by-type allocation and
scale every line to the Council's May-2026 FY2027 total, so the mix keeps
TRPO's structure while the total is the current forecast. Both parses are
checksummed against printed totals; the scaled sum must land on the COR
total within rounding.

Output: site/map/revenue.json ($ thousands, general fund only).
Context amounts for the footnote ride along: GF nontax revenue and
special-fund taxes from the companion "State Receipt and Revenue Plans"
FY27 SUPP doc (pp. 3, 8 — constants below with their printed values).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
BASIS_PDF = ROOT / "data" / "raw" / "fy27supp_revenue_basis.pdf"
COR_PDF = ROOT / "data" / "raw" / "cor_gf_2026-05-21.pdf"
OUT = ROOT / "site" / "map" / "revenue.json"

# FY27 numeric-column index on the basis p2 rows:
# BASE FY2024, FY2025, FY2026, FY2027, ... -> index 3
FY27_COL = 3

# "State Receipt and Revenue Plans" FY27 SUPP (Dec 2025), for the footnote:
# p3 general-fund financial plan, FY27 nontax revenues $875.8M; p8 special
# revenue funds, FY27 taxes total $1,064,442K (fuel, rental cars, vehicle
# weight, Honolulu rail surcharge share, UI, ...). Both $ thousands here.
GF_NONTAX = 875_800
SPECIAL_FUND_TAXES = 1_064_442

# short label + who-pays explainer, keyed by the TRPO row name
LABELS = {
    "General Excise and Use Tax":
        ("General excise & use (GET)",
         "4% (plus the counties' 0.5% surcharge) on nearly every "
         "transaction — everyone pays it at the register"),
    "Individual Income Tax":
        ("Individual income tax",
         "Tax on residents' income — the gold streams on the map. "
         "Shrinking as the 2024 income-tax cuts phase in"),
    "Transient Accommodations Tax":
        ("Transient accommodations (TAT)",
         "11% on hotel and vacation-rental stays (10.25% + the 2026 "
         "climate fee) — mostly visitors; this is the general fund's "
         "share"),
    "Inheritance and Estate Tax":
        ("Estate tax",
         "Tax on large estates — spiky from year to year"),
    "Corporate Income Tax":
        ("Corporate income tax",
         "Tax on corporation profits"),
    "Tax on Insurance Premiums":
        ("Insurance premiums tax",
         "Levy on insurers, paid in lieu of GET"),
    "Public Service Company Tax":
        ("Public service companies",
         "Utilities pay this instead of GET"),
    "Conveyance Tax":
        ("Conveyance tax",
         "On real-estate sales, graduated by price — the general fund's "
         "share"),
    "Tax on Banks and Other Financial Corps.":
        ("Banks & financial corporations",
         "Franchise tax banks pay instead of the corporate income tax"),
    "Cigarette and Tobacco Tax":
        ("Tobacco tax",
         "Per-pack cigarette excises — fading as smoking declines"),
    "Liquor Tax":
        ("Liquor tax",
         "Per-gallon excises on alcohol"),
    "Miscellaneous Taxes":
        ("All other taxes & fees",
         "Penalties and interest, license fees, and small allocations "
         "from other taxes"),
}


def _nums(line: str) -> list[int]:
    """All $-thousand figures on a row, in order."""
    return [int(n.replace(",", ""))
            for n in re.findall(r"\$?\s*([\d]{1,3}(?:,\d{3})+|\d{4,})", line)]


def parse_trpo_basis():
    """p2 of the basis doc: by-type FY2027 allocation + printed GF total."""
    with pdfplumber.open(BASIS_PDF) as pdf:
        page = next(p for p in pdf.pages
                    if "ESTIMATES OF GENERAL FUND TAX REVENUE"
                    in (p.extract_text() or ""))
        text = page.extract_text()
    rows, total = {}, None
    for line in text.split("\n"):
        line = line.strip()
        name = next((k for k in LABELS if line.startswith(k)), None)
        if name:
            rows[name] = _nums(line)[FY27_COL]
        elif line.startswith("GENERAL FUND TOTAL"):
            total = _nums(line)[FY27_COL]
    if total is None or len(rows) != len(LABELS):
        raise SystemExit(f"basis parse: {len(rows)}/{len(LABELS)} rows, "
                         f"total={total}")
    s = sum(rows.values())
    if abs(s - total) / total > 0.001:
        raise SystemExit(f"basis checksum FAIL: {s:,} vs printed {total:,}")
    print(f"TRPO FY27 allocation OK: {len(rows)} types, "
          f"${s/1e6:,.3f}B == printed ${total/1e6:,.3f}B")
    return rows, total


def parse_county_surcharge():
    """p3 of the basis doc: FY2027 total county GET surcharge collections."""
    with pdfplumber.open(BASIS_PDF) as pdf:
        page = next(p for p in pdf.pages
                    if "ESTIMATES OF COUNTY SURCHARGE REVENUE"
                    in (p.extract_text() or ""))
        text = page.extract_text()
    for line in text.split("\n"):
        if line.strip().startswith("Total County Surcharge Collections"):
            return _nums(line)[1]          # columns start at FY2026
    raise SystemExit("county surcharge row not found")


def parse_cor():
    """COR 2026-05-21 report: FY2026/FY2027 general-fund tax revenues."""
    with pdfplumber.open(COR_PDF) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    fy = {}
    for m in re.finditer(r"^(20\d\d)\s+\$([\d,]+)\s+(-?\d+\.\d)%",
                         text, re.M):
        fy[int(m.group(1))] = int(m.group(2).replace(",", ""))
    if 2026 not in fy or 2027 not in fy:
        raise SystemExit(f"COR table parse failed: {sorted(fy)}")
    growth = 100 * (fy[2027] / fy[2026] - 1)
    if abs(growth - 1.0) > 0.15:           # letter says FY27 = +1.0%
        raise SystemExit(f"COR sanity FAIL: FY27 growth {growth:.2f}%")
    print(f"COR 2026-05-21: FY26 ${fy[2026]/1e6:,.3f}B → "
          f"FY27 ${fy[2027]/1e6:,.3f}B (+{growth:.1f}%)")
    return fy


def main():
    rows, plan_total = parse_trpo_basis()
    cor = parse_cor()
    surcharge = parse_county_surcharge()

    # rescale the Dec-2025 line items onto the May-2026 Council total
    scale = cor[2027] / plan_total
    named = []
    for name, amt in rows.items():
        short, who = LABELS[name]
        stream = ("income" if short.startswith("Individual income")
                  else "get" if short.startswith("General excise")
                  else None)
        named.append({"name": short, "who": who,
                      "amt": round(amt * scale), "stream": stream})
    named.sort(key=lambda r: -r["amt"])
    total = sum(r["amt"] for r in named)
    if abs(total - cor[2027]) > 50:        # rounding only
        raise SystemExit(f"scaled sum {total:,} != COR {cor[2027]:,}")

    out = {
        "fy": 2027,
        "projected": True,
        "unit": "thousands",
        "total": total,
        "gf_nontax": GF_NONTAX,
        "county_surcharge": surcharge,
        "special_fund_taxes": SPECIAL_FUND_TAXES,
        "cor": {"meeting": "2026-05-21", "fy2026": cor[2026],
                "growth_pct": 1.0},
        "plan_total": plan_total,
        "source": ("Council on Revenues forecast (May 21, 2026), allocated "
                   "by tax type per the Dept. of Budget & Finance FY27 "
                   "Executive Supplemental revenue estimates (Dec 2025, "
                   f"scaled ×{scale:.4f})"),
        "taxes": named,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(named)} categories, "
          f"${total/1e6:.3f}B projected GF taxes FY2027 "
          f"(plan ${plan_total/1e6:.3f}B × {scale:.4f})")


if __name__ == "__main__":
    main()
