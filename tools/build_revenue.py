#!/usr/bin/env python3
"""Build the revenue-mix dataset from the DOTAX annual report.

Source: Department of Taxation Annual Report FY2024-25,
Table 1.8 — Tax Collections (all tax types, $ thousands):
  data/raw/25annrpt.pdf
  (from https://files.hawaii.gov/tax/stats/stats/annual/25annrpt.pdf)

The extracted text splits the first digit off numbers ("$ 4 ,630,396");
parsing strips whitespace inside the number region and the result is
checksummed against the table's printed TOTAL (must agree within 0.1%).

Output: site/map/revenue.json — collections by tax type, FY2025, with
short labels and one-line "who pays it" explainers, plus the FY2025
distribution split (general fund / counties / special funds) from §1.1.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "raw" / "25annrpt.pdf"
OUT = ROOT / "site" / "map" / "revenue.json"

# short label + who-pays explainer, keyed by a normalized row-name prefix
LABELS = {
    "General Excise and Use":
        ("General excise & use (GET)",
         "4% (4.5% with the Oʻahu surcharge) on nearly every transaction — "
         "everyone pays it at the register"),
    "Income - Individuals":
        ("Individual income tax",
         "Tax on residents' income — the gold streams on the map"),
    "Trans. Accom. Tax":
        ("Transient accommodations (TAT)",
         "10.25% on hotel and vacation-rental stays — mostly visitors"),
    "County Surcharge":
        ("County GET surcharge",
         "0.5% GET add-on collected for the counties — funds rail on Oʻahu"),
    "Inheritance and Estate":
        ("Estate tax",
         "Tax on large estates — spiky from year to year"),
    "Income - Corporations":
        ("Corporate income tax",
         "Tax on corporation profits"),
    "Employment Security Contributions":
        ("Unemployment insurance",
         "Employer contributions to the unemployment trust fund"),
    "Insurance Premiums":
        ("Insurance premiums tax",
         "Levy on insurers, paid in lieu of GET"),
    "Fuel":
        ("Fuel taxes",
         "Per-gallon taxes at the pump — fund the highways"),
    "Public Service Companies":
        ("Public service companies",
         "Utilities pay this instead of GET"),
    "Motor Vehicle Tax and Fees":
        ("Motor vehicle tax & fees",
         "State registration weight tax and fees"),
    "Rental Vehicle Tax and Fees":
        ("Rental vehicle surcharge",
         "$8/day on rental cars — mostly visitors"),
    "Conveyance":
        ("Conveyance tax",
         "On real-estate sales, graduated by price"),
    "Tobacco and Licenses":
        ("Tobacco tax",
         "Per-pack cigarette and tobacco excises"),
    "Liquor and Permits":
        ("Liquor tax",
         "Per-gallon excises on alcohol"),
}
# folded into "All other taxes & fees"
OTHER = ["Banks - Financial Corps.", "Environmental Response",
         "Trans. Accom. Fees", "All Others"]

# §1.1 distribution of the FY2025 total (in $ thousands)
DISTRIBUTION = {"general_fund": 9974000, "counties": 653000,
                "special_funds": 829200}


def parse_table():
    with pdfplumber.open(PDF) as pdf:
        page = next(p for p in pdf.pages
                    if "TABLE 1.8 - TAX COLLECTIONS"
                    in (p.extract_text() or ""))
        text = page.extract_text()
    rows, total = [], None
    pat = re.compile(r"^([A-Za-z][A-Za-z\s\-.,&']+?)\s+\$?\s*"
                     r"([\d][\d\s,]*)\s+(\d+\.\d\d)\s")
    for line in text.split("\n"):
        m = pat.match(line.strip())
        if not m:
            continue
        name = re.sub(r"\s+\d+(, \d+)?$", "", m.group(1).strip())
        amt = int(re.sub(r"[\s,]", "", m.group(2)))
        if name.upper().startswith("TOTAL"):
            total = amt
            continue
        rows.append((name, amt))
    if total is None:
        raise SystemExit("TOTAL row not found")
    s = sum(a for _, a in rows)
    if abs(s - total) / total > 0.001:
        raise SystemExit(f"checksum FAIL: rows sum {s:,} vs total {total:,}")
    print(f"parsed {len(rows)} rows, checksum OK: ${s/1e6:,.2f}B == printed "
          f"${total/1e6:,.2f}B")
    return rows, total


def main():
    rows, total = parse_table()
    named, other = [], 0
    for name, amt in rows:
        if any(name.startswith(o) for o in OTHER):
            other += amt
            continue
        hit = next((v for k, v in LABELS.items() if name.startswith(k)), None)
        if hit is None:
            print(f"  (unmapped row folded into other: {name} ${amt/1e3:.0f}M)")
            other += amt
            continue
        short, who = hit
        stream = ("income" if short.startswith("Individual income")
                  else "get" if short.startswith("General excise")
                  else None)
        named.append({"name": short, "who": who, "amt": amt,
                      "stream": stream})
    named.append({"name": "All other taxes & fees",
                  "who": "Financial corporations, environmental response "
                         "($1.05/barrel on petroleum), licenses and fees",
                  "amt": other, "stream": None})
    named.sort(key=lambda r: -r["amt"])

    out = {
        "fy": 2025,
        "unit": "thousands",
        "total": total,
        "distribution": DISTRIBUTION,
        "source": ("DOTAX Annual Report FY2024-25, Table 1.8 "
                   "(cash collections, all funds)"),
        "taxes": named,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(named)} categories, "
          f"${total/1e6:.2f}B FY2025")


if __name__ == "__main__":
    main()
