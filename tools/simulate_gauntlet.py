#!/usr/bin/env python3
"""Monte Carlo the money-committee gauntlet — a REAL, re-runnable
version of the calibration table in DESIGN-11-bills-and-checks.md §8d.

That table (20,000 sessions/profile) was produced by a script that was
never committed. It has been silently going stale ever since: the
2026-08-13 per-bill support/influence rewrite invalidated it the same
day it shipped, and it was never re-run before this tool existed. This
script exists so that stops happening — every gate probability below is
read LIVE from the shipped JSON (site/map/chairs.json,
site/map/hearing_rates.json), not copied by hand, so it can never drift
from the game the way a hand-copied table did. Re-run it after any
change to gate math, hearing_rates.json, or the tax families in play.

WHAT CHANGED 2026-08-19 and why this exists now: priorities stopped
being bills (Advocate's call — "the initial investment priorities
determine how much revenue you have to make up, but the bill process is
centered on taxes"). Every bill in play is now a REVENUE measure, and
the only tax families that reach a committee are whatever
`policies.json` `revenue` actually tags — currently `wealth` (conveyance,
capgains) and `income` (wwcr). `credit` is simulated too, marked
HYPOTHETICAL, because it is the design doc's headline number ("credits
beat wealth taxes at every skill level") and is worth knowing whether
it would still hold if a credit-tagged revenue bill ever gets added.

THE SIMULATION MIRRORS main.js LINE FOR LINE, not the idealized
description in the design doc — including a quirk worth knowing about:
the `intro` stage is `gate: "auto"` and advances immediately, consuming
one week with NO roll (`continue`s past this bill for that week in
resolveBills). So a stage with `window = deadline - enteredWeek + 1`
gets `window` used in the hazard formula but only `window - 1` actual
rolls happen after the very first stage, because the auto-advance ate a
week. This is SHIPPED BEHAVIOR — h-fin's window computes as 4 but only
3 real weekly draws occur — and the simulator reproduces it exactly
rather than the corrected version, because the point is to measure the
game as it actually runs, not as it was meant to.

ONE ASSUMPTION THE ORIGINAL TABLE DIDN'T DOCUMENT: the conference gate
(`stages.conf`) rolls 2d6 + the campaign's basebuilding/mobilizing skill
(whichever is higher) vs DC 12, plus floor(S.metrics.influence / 30).
The original three-column profile (support/influence/pushes only) never
pinned down a skill LEVEL for that roll. This script adds one — see
PROFILES below — and documents it there rather than silently reusing
whatever the lost original assumed.

Usage:
    python3 tools/simulate_gauntlet.py                  # the full table
    python3 tools/simulate_gauntlet.py --sessions 5000   # faster, noisier
    python3 tools/simulate_gauntlet.py --family wealth --profile engaged -v
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- load
def load():
    chairs = json.loads((ROOT / "site/map/chairs.json").read_text())
    rates = json.loads((ROOT / "site/map/hearing_rates.json").read_text())
    return chairs, rates.get("committees", {})


# --------------------------------------------------------- family rate
def rate_for(committees, cmte, kind, tax):
    """Port of main.js rateFor(): the tax-family cell, falling back to
    the committee's all-tax-kind rate, then its overall rate."""
    r = committees.get(cmte)
    if not r:
        return 0.35
    types = r.get("types") or {}
    cell = types.get(tax)
    if cell and cell.get("rate") is not None:
        return cell["rate"]
    topic = r.get("topic_rate" if kind == "gain" else "approp_rate")
    if topic is not None:
        return topic
    return r.get("rate", 0.35) if r.get("rate") is not None else 0.35


def week_hazard(p, weeks_left):
    if weeks_left <= 1:
        return p
    return 1 - (1 - p) ** (1 / weeks_left)


# ------------------------------------------------------------- profile
# The three tiers from the design doc, PLUS a skill level for the
# conference roll (see the module docstring — the original three-column
# table never pinned one down). Chosen to track the tier's investment:
# passive never trained anything (floor, 1), engaged bought it up some
# (average, 3), insider is deep in the building (great, 5).
PROFILES = {
    "passive": {"support": 50, "influence": 30, "pushes": 0, "confSkill": 1},
    "engaged": {"support": 70, "influence": 55, "pushes": 4, "confSkill": 3},
    "insider": {"support": 40, "influence": 85, "pushes": 8, "confSkill": 5},
}

# tax family -> (kind, hypothetical?) — kind is always "gain" (a revenue
# bill) in the current design, since priorities never reach a committee
FAMILIES = {
    "wealth": {"hypothetical": False},
    "income": {"hypothetical": False},
    "credit": {"hypothetical": True},
}


def simulate_one(chairs, committees, family, profile, rng):
    G = chairs["gate"]
    stages = chairs["stages"]
    route = chairs["routes"]["gain"]
    tilt = G["familyTilt"].get(family, G["familyTilt"]["_default"])

    support = max(0, min(100, profile["support"] + tilt.get("support", 0)))
    influence = max(0, min(100, profile["influence"] + tilt.get("influence", 0)))
    global_influence = profile["influence"]     # S.metrics.influence — NOT
                                                 # the per-bill number; the
                                                 # conf-gate mod reads this
    pushes_left = profile["pushes"]

    stage_i = 0
    entered_week = 1
    week = 1
    amt_scale = 1.0

    while True:
        week += 1
        if week > 17:            # matches the S.week > sineDieWeek guard
            return "unresolved", amt_scale
        sid = route[stage_i]
        st = stages[sid]

        if st["gate"] == "auto":
            stage_i += 1
            entered_week = week
            if stage_i >= len(route):
                return "enacted", amt_scale
            continue

        window = max(1, st["deadline"] - entered_week + 1)

        if st["gate"] == "chair":
            chair = chairs["chairs"][sid]
            cmte = chair["committee"]
            p = rate_for(committees, cmte, "gain", family)
            p += G["championed"]
            p += chair["disposition"] / G["dispositionDiv"]
            p += influence / G["influenceDiv"]
            # align(): matches main.js exactly, read from the chair's
            # OWN stance rather than assumed — both money chairs are
            # "hold" today (align() always 0), but a future edit to
            # chairs.json must not silently desync this simulator
            stance = chair.get("stance", "hold")
            # kind is always "gain" here, so (kind === "raise") in the JS
            # collapses to (stance == "raise")
            aligned = 0 if stance == "hold" else                 (1 if stance == "raise" else -1)
            if aligned > 0:
                p += support / G["supportDiv"]
            # introEdge(): rapport enters ZERO-CENTRED on introBaseline;
            # no profile here models working the relationship, so this
            # is exactly 0 — the documented "baseline" behavior
            pushed_this_week = False
            if pushes_left > 0 and week <= st["deadline"]:
                p_try = p + G["actionBonus"]
                pushed_this_week = True
            else:
                p_try = p
            p_try = max(0.02, min(0.95, p_try))
            hz = week_hazard(p_try, window)
            moved = rng.random() < hz
            if moved and pushed_this_week:
                pushes_left -= 1
                influence = max(0, min(100, influence + G["pushInfluence"]))
            if moved:
                dil = G["dilution"]
                if support < dil["floor"]:
                    amt_scale = max(dil["min"], amt_scale * dil["cut"])
        elif st["gate"] == "conf":
            # 2d6 + skill vs DC, snake eyes always fail, boxcars always
            # succeed — same as rollCheck() in main.js
            d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
            s = d1 + d2
            bonus = profile["confSkill"] + (global_influence // 30)
            ok = True if s == 12 else False if s == 2 else \
                (s + bonus >= G["confDC"])
            if not ok:
                amt_scale = 0.5
            moved = True
        else:                                          # floor
            p = G["floorBase"] + support / G["floorSupportDiv"] + \
                influence / G["floorInfluenceDiv"]
            p = max(0.05, min(0.95, p))
            hz = week_hazard(p, window)
            moved = rng.random() < hz
            if not moved and week >= st["deadline"]:
                return "dead", amt_scale

        if moved:
            stage_i += 1
            entered_week = week
            if stage_i >= len(route):
                return "enacted", amt_scale
        elif week >= st["deadline"]:
            return "dead", amt_scale


def run(chairs, committees, family, profile_name, n, seed=0):
    rng = random.Random(seed)
    profile = PROFILES[profile_name]
    enacted = 0
    total_scale = 0.0
    for _ in range(n):
        status, scale = simulate_one(chairs, committees, family, profile, rng)
        if status == "enacted":
            enacted += 1
            total_scale += scale
    return {
        "enact_rate": enacted / n,
        "avg_scale_when_enacted": (total_scale / enacted) if enacted else None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions", type=int, default=20000)
    ap.add_argument("--family", choices=list(FAMILIES), default=None)
    ap.add_argument("--profile", choices=list(PROFILES), default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-v", "--verbose", action="store_true",
        help="show avg amtScale on enactment too, not just the rate")
    a = ap.parse_args()

    chairs, committees = load()
    families = [a.family] if a.family else list(FAMILIES)
    profiles = [a.profile] if a.profile else list(PROFILES)

    print(f"{a.sessions} sessions/cell, seed {a.seed}\n")
    header = "profile".ljust(10) + "".join(
        (f + (" (hyp)" if FAMILIES[f]["hypothetical"] else "")).ljust(16)
        for f in families)
    print(header)
    for prof in profiles:
        row = prof.ljust(10)
        for fam in families:
            r = run(chairs, committees, fam, prof, a.sessions, a.seed)
            cell = f"{r['enact_rate']*100:.1f}%"
            if a.verbose and r["avg_scale_when_enacted"] is not None:
                cell += f" (×{r['avg_scale_when_enacted']:.2f})"
            row += cell.ljust(16)
        print(row)

    if any(FAMILIES[f]["hypothetical"] for f in families):
        print("\n(hyp) = no revenue measure of this family exists in "
              "policies.json yet; simulated as if one did, at the "
              "family's measured hearing-rate cells.")


if __name__ == "__main__":
    main()
