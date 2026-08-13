#!/usr/bin/env python3
"""Build the budget-overlay dataset from the Budget Primer pipeline.

Source: the Hawaiʻi Budget Primer project's enacted-budget extract
(HB1800 CD1, signed as Act 175 of 2026 — the FY2027 budget):
  ~/BudgetPrimerFinal/docs/js/departments_act175_fy2027.json
  ~/BudgetPrimerFinal/docs/js/summary_stats_act175_fy2027.json
A snapshot of both is kept in data/raw/ so this repo builds standalone;
pass --refresh to re-copy from the BudgetPrimerFinal working tree.

Output: site/map/budget.json — per-department totals with a
General / Federal / Other fund split, sorted descending.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIMER = Path.home() / "BudgetPrimerFinal" / "docs" / "js"
RAW = ROOT / "data" / "raw"
FILES = ["departments_act175_fy2027.json", "summary_stats_act175_fy2027.json"]

SHORT = {
    "HMS": "Human Services",
    "TRN": "Transportation",
    "BUF": "Budget & Finance",
    "EDN": "Education (DOE)",
    "HTH": "Health",
    "UOH": "University of Hawaiʻi",
    "BED": "Business & Economic Dev.",
    "LNR": "Land & Natural Resources",
    "LBR": "Labor & Industrial Relations",
    "AGS": "Accounting & General Services",
    "PSD": "Corrections & Rehabilitation",
    "AGR": "Agriculture & Biosecurity",
    "DEF": "Defense",
    "ATG": "Attorney General",
    "HHL": "Hawaiian Home Lands",
    "CCA": "Commerce & Consumer Affairs",
    "LAW": "Law Enforcement",
    "TAX": "Taxation",
    "HRD": "Human Resources",
    "COM": "County of Maui",
    "COH": "County of Hawaiʻi",
    "GOV": "Governor's Office",
    "CCH": "City & County of Honolulu",
    "LTG": "Lt. Governor's Office",
}


def main():
    if "--refresh" in sys.argv:
        for f in FILES:
            shutil.copy(PRIMER / f, RAW / f)
            print(f"refreshed {f} from BudgetPrimerFinal")
    for f in FILES:
        if not (RAW / f).exists():
            shutil.copy(PRIMER / f, RAW / f)
            print(f"snapshotted {f} from BudgetPrimerFinal")

    depts = json.load(open(RAW / FILES[0]))
    stats = json.load(open(RAW / FILES[1]))

    rows = []
    for d in depts:
        fb = d.get("fund_breakdown", {})
        total = d["total_budget"]
        gf = fb.get("General Funds", 0.0)
        fed = fb.get("Federal Funds", 0.0) + fb.get("Other Federal Funds", 0.0)
        other = max(0.0, total - gf - fed)
        rows.append({
            "code": d["code"],
            "short": SHORT.get(d["code"], d["name"]),
            "name": d["name"],
            "total": round(total),
            "op": round(d.get("operating_budget", 0.0)),
            "cip": round(d.get("capital_budget", 0.0)),
            "gf": round(gf),
            "fed": round(fed),
            "other": round(other),
            "positions": d.get("positions", 0),
            "desc": d.get("description", "")[:300],
        })
    rows.sort(key=lambda r: -r["total"])

    out = {
        "fy": stats.get("fiscal_year", 2027),
        "act": "Act 175 (2026) — enacted",
        "source": ("Hawaiʻi State Budget, FY2027 (HB1800 CD1, Act 175 of "
                   "2026), via the Hawaiʻi Budget Primer pipeline"),
        "total": round(stats["total_budget"]),
        "op": round(stats["operating_budget"]),
        "cip": round(stats["capital_budget"]),
        "gfTotal": round(stats["fund_breakdown"].get("General Funds", 0.0)),
        "departments": rows,
    }
    dst = ROOT / "site" / "map" / "budget.json"
    with open(dst, "w") as fh:
        json.dump(out, fh)
    print(f"wrote {dst.relative_to(ROOT)}: {len(rows)} departments, "
          f"${out['total']/1e9:.1f}B total")


if __name__ == "__main__":
    main()
