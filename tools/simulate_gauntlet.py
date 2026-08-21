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
    # session.json carries the ACTIONS and their skill scaling, the
    # calendar (recess weeks) and sine die — all of which the weekly
    # action policies below need. Read live, never hand-copied.
    session = json.loads((ROOT / "site/map/session.json").read_text())
    return chairs, rates.get("committees", {}), session


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
# PROFILES ARE WEEKLY ACTION POLICIES NOW (2026-08-21), not static meter
# values. They had to be: until the same day, a bill's support/influence
# were copied off the campaign's meters ONCE at agenda lock and never
# written again, so the old table's `engaged` (support 70, influence 55)
# and `insider` (40/85) described states no path through the game could
# produce. Agenda lock happens inside the creation funnel, before any
# event fx has run, so every campaign's bills really seeded at exactly
# 50/30 + tilt. The table was modelling the game as designed while the
# shipped game quietly delivered passive-with-pushes for everyone.
#
# Now the meters feed the bills every week (main.js billMeter), so the
# honest way to describe a player is by WHAT THEY DO each week. One
# action per week is the game's own cap (S.actionWeek === S.week), and
# `push` competes with the campaign-building moves for that one slot —
# which is the actual strategic choice the module asks the player to
# make, and was invisible in a static table.
#
# `passive` is the INVARIANT ANCHOR: it never acts, so its meters sit at
# 50/30 all session and every derived number matches the pre-rewrite
# game exactly. If its band moves, something is wrong.
#
# Action effects and their skill scaling are read LIVE from session.json
# (same rule as the gate maths: never hand-copy a number that ships).
PROFILES = {
    # never spends the weekly action at all
    "passive": {"plan": [], "skills": {}, "confSkill": 1},
    # works the chair whenever this bill can be pushed; nothing else
    "push": {"plan": ["push"],
             "skills": {"procedure": 3}, "confSkill": 1},
    # inside game: standing over turnout
    "lobby": {"plan": ["lobby"],
              "skills": {"talkstory": 3}, "confSkill": 2},
    # outside game: turnout over standing
    "rally": {"plan": ["rally"],
              "skills": {"mobilizing": 3}, "confSkill": 3},
    # the long organiser game — the deliberately unglamorous action
    "bench": {"plan": ["bench"],
              "skills": {"basebuilding": 3}, "confSkill": 4},
    # rotates the three levers, which is how the game reads as intended
    # and is the closest successor to the old "engaged"
    "balanced": {"plan": ["push", "lobby", "rally"],
                 "skills": {"procedure": 2, "talkstory": 2,
                            "mobilizing": 2}, "confSkill": 3},
}
# NB `push` is not "push and nothing else": a push needs a chair gate to
# push against, so on floor weeks and during the recess the policy falls
# through to the campaign-building action underneath. It is therefore the
# push-FIRST hybrid, and that it beats every rotation is the model's
# sharpest finding — the weekly action is one slot, and a week spent
# rallying during a committee window is a draw the bill never gets back.

# tax family -> (kind, hypothetical?) — kind is always "gain" (a revenue
# bill) in the current design, since priorities never reach a committee
FAMILIES = {
    "wealth": {"hypothetical": False},
    "income": {"hypothetical": False},
    "credit": {"hypothetical": True},
}


def scaled_fx(action, skills):
    """Port of main.js scaledFx(): an action's effects plus floor(skill /
    per) added onto whichever effect key each scale mod names."""
    fx = dict(action.get("effects") or {})
    for m in (action.get("scale") or {}).get("mods") or []:
        if m.get("from") != "skill":
            continue
        n = (skills.get(m.get("id"), 0)) // (m.get("per") or 1)
        if n:
            fx[m["on"]] = fx.get(m["on"], 0) + n
    return fx


def push_bonus(G, influence):
    """Port of main.js pushBonus(): the weekly chair push scales with the
    influence behind it. ONE-SIDED: `base` IS the old flat 0.15 and the
    steps only add, counted from the influence baseline — scaling from
    zero instead made a tilted family's push pay LESS than it used
    to."""
    p = G.get("push") or {}
    base = p.get("base", 0.15)
    step = p.get("step", 0.05)
    per = p.get("per", 30)
    frm = p.get("from", G.get("influenceBaseline", 30))
    cap = p.get("cap", 0.30)
    return min(cap, base + step * max(0, (influence - frm) // per))


def dil_factor(G, sup):
    """Port of main.js dilFactor(): graduated, not a cliff."""
    dil = G.get("dilution") or {}
    fl = dil.get("floor", 45)
    full = dil.get("full", 15)
    cut = dil.get("cut", 0.85)
    if sup >= fl:
        return 1.0
    t = min(1.0, (fl - sup) / max(1, fl - full))
    return 1 - (1 - cut) * t


def simulate_one(chairs, committees, session, family, profile, rng):
    """One bill, one session. NOTE THE SCOPE: this models a ONE-BILL
    campaign. The floor-calendar support burn is charged once per WEEK in
    the game however many bills missed, so for a one-bill agenda "per
    week" and "per bill" coincide exactly; a six-bill package burns the
    same 2 support but on more weeks, so a big agenda bleeds support
    somewhat faster than this models. Per-bill odds are unaffected."""
    G = chairs["gate"]
    stages = chairs["stages"]
    route = chairs["routes"]["gain"]
    actions = session.get("actions") or {}
    tilt = G["familyTilt"].get(family, G["familyTilt"]["_default"])
    recess_weeks = {c.get("week") for c in session.get("calendar", [])
                    if c.get("recess")}
    sine_die = session.get("sineDieWeek", 16)

    # THE CAMPAIGN's meters — the bill reads through these every week now
    support = 50.0
    influence = 30.0
    skills = dict(profile["skills"])
    earned_influence = 0          # what the player bought FOR THIS BILL
    plan = profile["plan"]
    plan_i = 0

    def b_sup():
        return max(0, min(100, support + tilt.get("support", 0)))

    def b_inf():
        return max(0, min(100, influence + tilt.get("influence", 0)
                          + earned_influence))

    stage_i = 0
    entered_week = 1
    week = 1
    amt_scale = 1.0
    pushed_week = -99

    while True:
        # ---- the player's weekly action, taken BEFORE the week is
        # advanced, exactly as the hub works: you act, then end the turn
        recess = (week + 1) in recess_weeks
        act = None
        if plan:
            act = plan[plan_i % len(plan)]
            # `push` needs a chair gate to push against and is closed
            # during the recess (w6 grants rally/bench and withholds it)
            if act == "push":
                sid_now = route[stage_i]
                if recess or stages[sid_now]["gate"] != "chair":
                    act = "lobby" if "lobby" in actions else None
            elif recess and act == "lobby":
                # the building is shut; the district is not
                act = "rally" if "rally" in actions else None
        if act == "push":
            earned_influence += G.get("pushInfluence", 4)
            pushed_week = week
            skills["procedure"] = min(6, skills.get("procedure", 0) + 0)
            plan_i += 1
        elif act:
            fx = scaled_fx(actions[act], skills)
            support = max(0, min(100, support + fx.get("support", 0)))
            influence = max(0, min(100, influence + fx.get("influence", 0)))
            plan_i += 1

        week += 1
        if week > sine_die + 1:      # matches the S.week > sineDieWeek guard
            return "unresolved", amt_scale, support, influence

        # ---- weekUpkeep(): influence decays toward its baseline, every
        # week including the recess, downward only
        base_inf = G.get("influenceBaseline", 30)
        dec = G.get("influenceDecay", 1)
        if dec > 0 and influence > base_inf:
            influence = max(base_inf, influence - dec)

        sid = route[stage_i]
        st = stages[sid]

        if st["gate"] == "auto":
            stage_i += 1
            entered_week = week
            if stage_i >= len(route):
                return "enacted", amt_scale, support, influence
            continue

        window = max(1, st["deadline"] - entered_week + 1)

        # THE RECESS: every gate is skipped except `auto`, and the window
        # does NOT stretch to compensate — one draw the bill never gets
        if week in recess_weeks:
            if week >= st["deadline"]:
                return "dead:" + st["gate"], amt_scale, support, influence
            continue

        if st["gate"] == "chair":
            chair = chairs["chairs"][sid]
            cmte = chair["committee"]
            p = rate_for(committees, cmte, "gain", family)
            p += G["championed"]
            p += chair["disposition"] / G["dispositionDiv"]
            p += b_inf() / G["influenceDiv"]
            # align(): matches main.js exactly, read from the chair's
            # OWN stance rather than assumed — both money chairs are
            # "hold" today (align() always 0), but a future edit to
            # chairs.json must not silently desync this simulator
            stance = chair.get("stance", "hold")
            # kind is always "gain" here, so (kind === "raise") in the JS
            # collapses to (stance == "raise")
            aligned = 0 if stance == "hold" else \
                (1 if stance == "raise" else -1)
            if aligned > 0:
                p += b_sup() / G["supportDiv"]
            # introEdge(): rapport enters ZERO-CENTRED on introBaseline;
            # no profile here models working the relationship, so this
            # is exactly 0 — the documented "baseline" behavior
            # the push bought above is live for THIS week's roll only,
            # and scales with the influence behind it
            if week - pushed_week <= 1:
                p += push_bonus(G, b_inf())
            p = max(0.02, min(0.95, p))
            hz = week_hazard(p, window)
            moved = rng.random() < hz
            if moved:
                f = dil_factor(G, b_sup())
                if f < 1:
                    amt_scale = max(G["dilution"]["min"], amt_scale * f)
        elif st["gate"] == "conf":
            # 2d6 + skill vs DC, snake eyes always fail, boxcars always
            # succeed — same as rollCheck() in main.js. The influence mod
            # reads THIS BILL's number (2026-08-21); it used to read the
            # campaign's global one, the last gate that still did.
            d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
            s = d1 + d2
            bonus = profile["confSkill"] + (b_inf() // 30)
            ok = True if s == 12 else False if s == 2 else \
                (s + bonus >= G["confDC"])
            if not ok:
                amt_scale = 0.5
            moved = True
        else:                                          # floor
            p = G["floorBase"] + b_sup() / G["floorSupportDiv"] + \
                b_inf() / G["floorInfluenceDiv"]
            p = max(0.05, min(0.95, p))
            hz = week_hazard(p, window)
            moved = rng.random() < hz
            if not moved:
                # the base spent a week on a vote that was never called
                support = max(0, support - G.get("floorMissSupport", 2))
            if not moved and week >= st["deadline"]:
                return "dead:" + st["gate"], amt_scale, support, influence

        if moved:
            stage_i += 1
            entered_week = week
            if stage_i >= len(route):
                return "enacted", amt_scale, support, influence
        elif week >= st["deadline"]:
            return "dead:" + st["gate"], amt_scale, support, influence


def meter_trajectory(chairs, session, profile):
    """Where a policy's meters stand at sine die with no bill in play —
    the ceiling each weekly action can actually build toward, which is
    the number the old static profiles were guessing at. Deterministic:
    actions and decay carry no randomness."""
    G = chairs["gate"]
    actions = session.get("actions") or {}
    recess_weeks = {c.get("week") for c in session.get("calendar", [])
                    if c.get("recess")}
    support, influence = 50.0, 30.0
    skills = dict(profile["skills"])
    plan, plan_i = profile["plan"], 0
    for week in range(1, session.get("sineDieWeek", 16)):
        act = plan[plan_i % len(plan)] if plan else None
        if act == "push":                       # buys bill odds, not meters
            act = None if (week + 1) in recess_weeks else "lobby"
        if act and act in actions:
            fx = scaled_fx(actions[act], skills)
            support = max(0, min(100, support + fx.get("support", 0)))
            influence = max(0, min(100, influence + fx.get("influence", 0)))
        if plan:
            plan_i += 1
        base_inf = G.get("influenceBaseline", 30)
        dec = G.get("influenceDecay", 1)
        if dec > 0 and influence > base_inf:
            influence = max(base_inf, influence - dec)
    return support, influence


def run(chairs, committees, session, family, profile_name, n, seed=0):
    rng = random.Random(seed)
    profile = PROFILES[profile_name]
    enacted = 0
    total_scale = 0.0
    end_sup = end_inf = 0.0
    diluted = 0
    causes = {}
    for _ in range(n):
        status, scale, sup, inf = simulate_one(
            chairs, committees, session, family, profile, rng)
        end_sup += sup
        end_inf += inf
        causes[status] = causes.get(status, 0) + 1
        if status == "enacted":
            enacted += 1
            total_scale += scale
            if scale < 1:
                diluted += 1
    return {
        "enact_rate": enacted / n,
        "avg_scale_when_enacted": (total_scale / enacted) if enacted else None,
        "diluted_share": (diluted / enacted) if enacted else None,
        "end_support": end_sup / n,
        "end_influence": end_inf / n,
        "causes": causes,
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

    chairs, committees, session = load()
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
            r = run(chairs, committees, session, fam, prof,
                    a.sessions, a.seed)
            cell = f"{r['enact_rate']*100:.1f}%"
            if a.verbose and r["avg_scale_when_enacted"] is not None:
                cell += f" (×{r['avg_scale_when_enacted']:.2f})"
            row += cell.ljust(16)
        print(row)

    # what each policy's weekly actions actually do to the campaign's
    # meters. The old table NAMED meter values as inputs; nothing could
    # reach them, so the reachable numbers are output now. Reported at
    # SINE DIE and with no bill in play, deliberately: sampling them
    # when the bill resolved would be dominated by the bills that die
    # at h-fin in week 5, which is a reading of when campaigns end
    # rather than of what a policy can build.
    print("\nwhat each policy BUILDS by sine die (no bill in play):")
    print("  policy".ljust(12) + "support".ljust(10) + "influence")
    for prof in profiles:
        sup, inf = meter_trajectory(chairs, session, PROFILES[prof])
        print("  " + prof.ljust(10) + f"{sup:5.1f}" + " " * 5 + f"{inf:5.1f}")

    if any(FAMILIES[f]["hypothetical"] for f in families):
        print("\n(hyp) = no revenue measure of this family exists in "
              "policies.json yet; simulated as if one did, at the "
              "family's measured hearing-rate cells.")


if __name__ == "__main__":
    main()
