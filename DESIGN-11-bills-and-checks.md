# Feature 11 — Bills through the gauntlet, chairs, and skill checks

Design draft (2026-08-13). **Steps 1 and 2 are now built** — skills and
the check engine, then chairs, the gauntlet and the obituary. Sections 4
(chamber blocs / real floor votes) and 6 (the thought cabinet) are still
design only. This extends the feature-10 session framework; it does not
replace it.

**The teaching point:** most bills don't lose votes — they never get a
vote. One side of this fight has to win at every veto point; the other
only has to win at one, and it employs people to work all of them. The
player learns this by watching bills die quietly on the calendar.

**How the player is scored:** two numbers at Sine Die — **revenue
raised** ($K/yr enacted) and **priorities funded** ($K/yr enacted) —
plus whether the second is covered by the first. There is NO separate
"how much of the bill survived" stat: a bill that gets watered down in
conference simply carries a smaller dollar amount into the same two
totals. Dilution is expressed in dollars, because dollars are what the
game is about.

---

## 0. Revision (2026-08-19) — module 1 is a revenue game

**Superseded by this section: §8's scoring formula and the framing (not
the data) of §8c/§8d below.** They are kept, not deleted — same
convention as the "STALE" labels elsewhere in this doc — because the
decision history and the measured tables are both still true; only the
description of what's a BILL changed.

**The change** (Advocate's call — "the initial investment priorities
determine how much revenue you have to make up, but the bill process is
centered on taxes"): the `priorities` half of the creation package
(`policies.json` `kind: "cost"`) is no longer legislation. Picking a
priority sets a PRICE — `targetK()`, the sum of every chosen priority's
`amt` — and stops there; it never becomes an `S.bills[]` entry and never
touches a chair, a deadline, or a roll. `startBills()` now skips
anything whose `kind` isn't `"gain"`. Only the `revenue` half is carried
through the gauntlet.

The session therefore asks exactly one question — **can you raise what
you promised** — and every gate in §8b–§8d is now a gate a TAX bill
faces, full stop. There used to be two kinds of bill in the gauntlet
(`"cost"` and `"gain"`, both routed identically per §8b); there is now
only one.

**§8's scoring formula is corrected below** (it still describes
`prioritiesFunded` as a sum over *enacted* `"cost"` bills, which no
longer exist). **§8c's table and §8d's calibration numbers are still
real measured/simulated data and are NOT wrong** — but their framing
assumed wealth, GET and credit bills all competed for the same
committee calendar, which is no longer true. Only `wealth` (conveyance,
capgains) and `income` (wwcr) are LIVE families in `policies.json`
`revenue` today. `credit` — the design's headline contrast ("credits
beat wealth taxes") — is currently a PRIORITY, not a bill, so that
comparison is unreachable in play. It isn't deleted from this doc,
because it's the argument for adding a credit-tagged revenue measure
later; §8d below re-simulates it as HYPOTHETICAL for exactly that
reason. `get` never had a bill either (`get-half` was removed
2026-08-15) — this just means one thing that was already true (GET) now
has company (credit).

**No cap on either creation step any more** (same day, same user's
call: "allow users to choose as many investment priorities as they
want, same for the tax options"). §8d's calibration was run at ONE bill
per session (a single family in isolation), which is unaffected by the
cap removal — the numbers below are still valid PER-BILL odds. What the
cap removal changes is how many bills a real session fields at once (up
to 6 now, was ≤3 shared across both steps), which the design doc never
modeled as a joint distribution and still doesn't; treat §8d as
per-bill enact rates, not session-total ones.

**A REAL SIMULATOR now exists**: `tools/simulate_gauntlet.py`. The
original §8d table was produced by a script that was never committed —
it went stale the same day it shipped (the 2026-08-13 per-bill
support/influence rewrite) and was never re-run before this tool
existed. The new script reads `chairs.json` and `hearing_rates.json`
LIVE rather than hand-copying numbers, so it can't drift from the
shipped game the way the old table did. Re-run it after any change to
gate math or the tax families in play:

```bash
python3 tools/simulate_gauntlet.py               # the full table
python3 tools/simulate_gauntlet.py --sessions 5000 --family wealth -v
```

---

## 1. Metrics: two currencies, different physics

The two opinion meters stop being halves of one bar.

| | key | label | how it moves | what it does |
|---|---|---|---|---|
| 👪 | `support` | **Public Support** | costs your one weekly action to build; **decays 1–2/week** if unfed | converts to leverage only at hearings and floor votes |
| 🏛️ | `influence` | **Political Influence** | built by working the building (which costs you support); **does not decay** | applies continuously to every scheduling decision |

Support is a stock you spend at specific moments. Influence is a rate
that applies every single week, everywhere, whether or not you're
paying attention. That asymmetry *is* the lesson — don't balance them
to 50/50, and don't let the UI imply you should.

Starting values: `support: 50`, `influence: 30`. You start with the
public and without the building.

**Save migration:** the existing `metrics.wealthy` becomes
`metrics.influence` and `metrics.families` becomes `metrics.support`.
Migrate on load (`if (m.wealthy != null && m.influence == null)
m.influence = m.wealthy`) — renaming a key without migrating silently
wipes an in-progress campaign, same trap as policy ids.

---

## 2. Skills (new) — `session.json` → `skills`

Six skills, Disco-style, each the voice of a way of doing this job.
Every skill also gets a `voice` so it can chime in on dialogue like the
existing PROGRESSIVE / CONSERVATIVE traits.

```json
"skills": {
  "fiscal":    { "name": "Fiscal Acumen", "icon": "📊",
                 "desc": "Revenue estimates, fiscal notes, and whether the number on the page is real." },
  "procedure": { "name": "Procedure",     "icon": "📜",
                 "desc": "Referrals, deadlines, decking, and what the rules let you get away with." },
  "whip":      { "name": "Whip Count",    "icon": "🗳️",
                 "desc": "Who votes yes, who votes yes only if it doesn't matter." },
  "rhetoric":  { "name": "Rhetoric",      "icon": "🎙️",
                 "desc": "Hearings, cameras, and the sentence people repeat afterward." },
  "talkstory": { "name": "Talk Story",    "icon": "🌺",
                 "desc": "Reading the room. Trust built slowly and spent quickly." },
  "grassroots":{ "name": "Grassroots",    "icon": "✊",
                 "desc": "Coalition capacity — how many people you actually turn out, and how fast." }
}
```

Superseded 2026-08-13: Backbone is retired (see Decisions below). Two
wonk (Fiscal, Procedure), two organizer (Rhetoric, Grassroots), two
bridge (Talk Story, Whip Count).

Player skills live in save state: every skill starts at **1**, and week 0
distributes **5 points** (creation cap 4, hard cap 6). Thoughts grant +1s
later.

---

## 3. Skill checks on dialogue choices

2d6 + skill + modifiers vs a difficulty class. Snake eyes always fail,
boxcars always succeed, so odds clamp to 2.8%–97.2% — nothing is ever
certain in either direction.

**Odds table** (P of rolling ≥ N on 2d6, before the doubles rule):

| need | ≤2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P | 97.2 | 97.2 | 91.7 | 83.3 | 72.2 | 58.3 | 41.7 | 27.8 | 16.7 | 8.3 | 2.8 |

DC ladder: 6 trivial · 8 easy · 10 medium · 12 challenging ·
14 formidable · 16 legendary.

**Choice schema** (choices with no `check` behave exactly as today —
full back-compat with the existing dialogue content):

```json
{
  "label": "Ask him to calendar the bill before the lateral.",
  "check": {
    "skill": "procedure",
    "dc": 12,
    "type": "red",
    "mods": [
      { "from": "influence",  "per": 25 },
      { "from": "chair",      "id": "h-fin", "per": 30 },
      { "from": "flag",       "id": "owes-you-one", "add": 2 },
      { "from": "skill",      "id": "talkstory", "per": 3 }
    ]
  },
  "success": {
    "reply": "He doesn't say yes. He says 'send me the fiscal note by Thursday,' which is yes.",
    "effects": { "influence": -2 },
    "bill": { "id": "cap-gains", "act": "schedule" },
    "voices": [ { "t": "PROG", "text": "…" } ]
  },
  "failure": {
    "reply": "'It's a busy calendar this year.' He is already looking at the door.",
    "effects": { "influence": -4 },
    "chair": { "id": "h-fin", "disposition": -8 },
    "goto": "fonoti-brushoff"
  }
}
```

- `type: "white"` — retryable once something changes (you raised the
  skill, moved the chair, passed a week). `type: "red"` — one shot,
  permanently logged in `S.checks`. Bill-critical asks should be red;
  that's what makes them hurt.
- `mods` entries are `{from, per}` (value ÷ per, floored) or
  `{from, add}` (flat). `from` ∈ `influence | support | chair | skill |
  flag | thought`.
- **Failure must go somewhere.** Every red check needs a `failure`
  branch with its own content — a failed check that just says "nothing
  happens" wastes the best storytelling moment the mechanic offers.

**UI:** the choice button shows the skill, the DC and the live odds —
`📜 Procedure · Challenging · 64%` — computed at render time so the
player can *see* their influence buying down the difficulty. That
visibility is half the teaching.

---

## 4. Chambers and blocs — `session.json` → `chambers`

Do NOT model 51 + 25 individuals. Model blocs, because that's how the
building actually behaves, and it keeps floor votes legible.

```json
"chambers": {
  "house": {
    "name": "House", "seats": 51, "majority": 26,
    "blocs": [
      { "id": "h-prog",  "name": "Progressive caucus",   "seats": 13, "stance": "raise", "sway": 0.15 },
      { "id": "h-lead",  "name": "Leadership bloc",      "seats": 16, "stance": "hold",  "sway": 0.45 },
      { "id": "h-rural", "name": "Neighbor-island bloc", "seats":  9, "stance": "hold",  "sway": 0.60 },
      { "id": "h-biz",   "name": "Business Democrats",   "seats":  9, "stance": "cut",   "sway": 0.30 },
      { "id": "h-min",   "name": "Minority caucus",      "seats":  4, "stance": "cut",   "sway": 0.10 }
    ]
  },
  "senate": {
    "name": "Senate", "seats": 25, "majority": 13,
    "blocs": [
      { "id": "s-prog",  "name": "Progressive caucus",   "seats":  6, "stance": "raise", "sway": 0.15 },
      { "id": "s-lead",  "name": "Leadership bloc",      "seats":  9, "stance": "hold",  "sway": 0.40 },
      { "id": "s-rural", "name": "Neighbor-island bloc", "seats":  5, "stance": "hold",  "sway": 0.55 },
      { "id": "s-biz",   "name": "Business caucus",      "seats":  5, "stance": "cut",   "sway": 0.35 }
    ]
  }
}
```

The two chambers are deliberately composed differently — a bill that
sails in one and stalls in the other is a thing most players have never
considered, and crossover is where they find out.

`sway` is how movable the bloc is (0 = ideological, 1 = weathervane).
**Swayable blocs are moved by influence more cheaply than by support** —
they're the ones lobbyists actually work, and the player will notice.

**Floor vote resolution** — per bloc, yes-probability:

```
align  = stance vs bill kind        raise:+1  hold:0  cut:−1   (flip for cost bills)
base   = 0.5 + 0.28 × align
p      = base + sway × (support/100 × 0.30 + influence/100 × 0.45 − 0.25)
yes    = seats × clamp(p, 0.05, 0.95)      // fractional seats, rounded
```

Note the coefficients: influence outweighs support 0.45 : 0.30 inside
the building. That's not cynicism, it's the mechanic doing its job.

---

## 5. Chairs — `session.json` → `chairs`

The choke points. Four named chairs, all fictional; two of them are
already characters in the game.

```json
"chairs": {
  "h-sub":  { "name": "Rep. Dana Kealoha",  "chamber": "house",  "committee": "Economic Development",
              "gates": "subject", "stance": "hold",  "disposition": 0,  "char": null },
  "h-fin":  { "name": "Rep. Ellis Fonoti",  "chamber": "house",  "committee": "Finance",
              "gates": "money",   "stance": "hold",  "disposition": -5, "char": "fonoti" },
  "s-sub":  { "name": "Sen. Iwalani Souza", "chamber": "senate", "committee": "Commerce",
              "gates": "subject", "stance": "cut",   "disposition": -10, "char": null },
  "s-ways": { "name": "Sen. Roy Kamaka",    "chamber": "senate", "committee": "Ways and Means",
              "gates": "money",   "stance": "hold",  "disposition": 0,  "char": null }
}
```

`disposition` is −100…100, **hidden by default**. A Talk Story or Whip
Count check reveals it ("he'll hear it, he just won't pass it"). Hidden
disposition is the information asymmetry: the lobbyist already knows
this number and you don't.

Disposition moves via dialogue checks, the weekly action, and events.

---

## 6. The gauntlet — `session.json` → `route`

Stage list for a House-origin bill. Deadlines are the weeks already on
the calendar, which is why they're the *right* deadlines.

```json
"route": {
  "house": [
    { "id": "intro",     "label": "Introduction",          "gate": "auto",  "week": 1 },
    { "id": "h-subject", "label": "House subject cmte",    "gate": "chair", "chair": "h-sub",  "deadline": 4 },
    { "id": "h-money",   "label": "House Finance",         "gate": "chair", "chair": "h-fin",  "deadline": 5 },
    { "id": "h-floor",   "label": "House third reading",   "gate": "vote",  "chamber": "house","deadline": 8 },
    { "id": "s-subject", "label": "Senate subject cmte",   "gate": "chair", "chair": "s-sub",  "deadline": 10 },
    { "id": "s-money",   "label": "Ways and Means",        "gate": "chair", "chair": "s-ways", "deadline": 11 },
    { "id": "s-floor",   "label": "Senate third reading",  "gate": "vote",  "chamber": "senate","deadline": 13 },
    { "id": "conf",      "label": "Conference committee",  "gate": "conf",  "deadline": 15 },
    { "id": "final",     "label": "Final reading",         "gate": "vote",  "chamber": "both", "deadline": 16 }
  ],
  "senate": [ "…mirror image…" ]
}
```

**Gate resolution, run once per week inside `advanceWeek()`:**

- `chair` — roll to get scheduled. If the deadline week passes without
  advancing, the bill is **dead with no vote**. Cause of death:
  `"never heard"`. This is the single most important line of code in
  the feature.

  **The baseline is now measured, not invented.** `Legislative-Research-Tool`
  (`testimony measures rates`) reconstructs referral → hearing → report
  from the Legislature's own static artifacts. Session 2026, House side,
  exact counts — see `data/raw/hearing_rates_*_2026.json`:

  | | referred | heard | rate |
  |---|---|---|---|
  | All measures | 3,475 | — | **53.4%** |
  | **House Finance** | 876 | 343 | **39.2%** |
  | Consumer Protection & Commerce | 263 | 105 | 39.9% |
  | Judiciary & Hawaiian Affairs | 564 | 239 | 42.4% |
  | Transportation | 131 | 118 | 90.1% |
  | *Revenue measures at Finance* | 90 | 37 | **41.1%** |

  The money committee is both the busiest gate (876 referrals, 4× any
  other) and the hardest one (39.2%, the lowest of any committee with
  real volume). That is the game's whole thesis arriving as a measured
  fact, and it should be the tooltip on the Finance gate.

  ```
  p = 0.39                                    // House Finance, measured 2026
    + disposition / 250                       // ±0.40, editorial
    + influence   / 260                       // up to +0.38
    + support × align / 500                   // up to +0.20, only if aligned
    + 0.15 if you spent this week's action on this bill
    − 0.12 per committee already passed this stage-block (fatigue)
  ```

  Keep the measured base rate and the editorial deltas as separate
  terms, and cite the base in the UI. A player who asks "is it really
  that hard?" should be able to reach the real number.

  **Known gap:** the Senate publishes no referral sheets, so there is no
  honest Senate-side denominator yet — Ways and Means cannot be given a
  measured rate the way Finance can. Senate referrals live in the
  chamber journal. Until that is parsed, either mirror the House rate
  and SAY it is mirrored, or hold the Senate gates as editorial.

- `vote` — bloc math from §4 vs `majority`.
- `conf` — both money chairs must agree. Disagreement offers the player
  a choice: **accept a scaled amount** (`amtScale` 0.5 or 0.25) or hold
  firm and roll a Grassroots check to keep it whole, with death on
  failure. This is where dilution enters, and it enters as dollars.

**Referral as a weapon:** a bill can be referred to *two* committees
instead of one (leadership's call, not the player's) — the doubled gate
is the quiet kill. Surface it in week 1 as a visible, unfair-feeling
event.

---

## 7. Bill state — save shape in `localStorage: cq-session`

```json
"bills": {
  "cap-gains": {
    "id": "cap-gains",
    "kind": "gain",
    "amtK": 98000,
    "amtScale": 1.0,
    "origin": "house",
    "route": ["intro", "h-subject", "h-money", "h-floor", "…"],
    "stage": 2,
    "status": "alive",
    "enteredWeek": 3,
    "history": [
      { "week": 2, "stage": "h-subject", "result": "heard",  "p": 0.41, "roll": 0.22 },
      { "week": 3, "stage": "h-money",   "result": "waiting" }
    ],
    "death": null
  }
}
```

`status` ∈ `alive | enacted | dead`. `death` is
`{ week, stage, cause }` where cause ∈ `never heard | voted down |
died in conference | ran out of clock`.

**The obituary is the payload.** At Sine Die, show every dead bill with
where and how it died, and — for anything killed by a chair — the
disposition number the player never saw. "Your $98M capital gains bill
died on March 4. It was never scheduled for a hearing. Rep. Fonoti's
disposition toward it was −34." That single screen teaches more than
sixteen weeks of meters.

---

## 8. Scoring at Sine Die

**Corrected 2026-08-19 — see §0.** `prioritiesFunded` used to be a sum
over enacted `"cost"` bills; priorities are not bills any more, so it's
now the flat commitment set at creation (`targetK()` in main.js):

```
revenueRaised   = Σ  amtK × amtScale   over enacted bills of kind "gain"
prioritiesFunded= Σ  amt               over every chosen S.agenda item of kind "cost"   (targetK)
covered         = revenueRaised ≥ prioritiesFunded
```

`prioritiesFunded` is fixed the moment the creation funnel locks — it
cannot move again for the rest of the session, unlike `revenueRaised`,
which only grows (or stays flat) as bills enact. The hub-level version
of this (`gapHtml()`) is the running scoreboard; this is just its value
at Sine Die.

Both flow into the existing FY2027 scoreboard through
`PolicyPanel.setExternal` — same chip, same numbers, no parallel
bookkeeping. No survival/strength stat exists anywhere.

---

## 8b. Scope: the two money committees

Module 1 routes every bill through **House Finance** and **Senate Ways
and Means** and nothing else:

```
intro → h-fin (w5) → h-floor (w8) → s-wam (w11) → s-floor (w13) → conf (w15) → final (w16)
```

Every bill with a dollar figure goes through both. They take more
referrals than any other committee in their chamber (876 and 936 in
2026, roughly double the next busiest) and they hand back the two lowest
hearing rates. Subject-matter committees add gates without adding a new
idea, so they are out of scope; the leadership referral roll
(`singleReferral`) that could add or skip one is parked with them.

## 8c. Rates are per TAX FAMILY

Pooled 2025–26, hearing rate by kind of tax bill:

| family | rate | n |
|---|---|---|
| Taxes on wealth (capital gains, conveyance, REIT, estate, top brackets) | 25.0% | 80 |
| Tobacco / alcohol / carbon | 27.8% | 18 |
| Income tax generally | 30.0% | 20 |
| General excise | 31.2% | 64 |
| Exemptions & deductions | 31.9% | 91 |
| **Tax credits and rebates** | **43.4%** | 274 |
| Tourism / TAT | 64.9% | 37 |
| Administration & conformity | 66.7% | 6 |

At House Finance alone: credits 32% (n=87), wealth 24% (n=21), GET 20%
(n=15). A bill that hands money out through the tax code is heard
roughly twice as often as one that takes money from wealth — that is
the module's argument, and it is measured, not asserted.

Two honesty rules ride along: a thin (committee, family) cell falls back
to the committee's all-tax rate and records `basis`, and the bill
tooltip says so in words. And **Senate measures are classified on title
alone** — the Senate publishes no description for un-heard measures, and
borrowing hearing-notice descriptions would classify heard bills better
than unheard ones and inflate every rate.

## 8d. Calibration (20,000 sessions per profile, two-committee route)

**SUPERSEDED 2026-08-19 — kept for the invariants, not the numbers.**
This table was hand-produced by a script that was never committed; it
went stale the same day it shipped (the per-bill support/influence
rewrite, 2026-08-13) and was never re-run before now. It also modeled a
world where wealth, GET and credit bills all competed for the same
committee calendar — GET has had no bill since `get-half` was removed
(2026-08-15) and credit has had none since priorities stopped being
bills (2026-08-19, §0).

| profile | wealth tax | GET | credit |
|---|---|---|---|
| passive (sup 50, inf 30, 0 pushes) | 5.0% | 4.6% | 9.2% |
| engaged (sup 70, inf 55, 4 pushes) | 20.3% | 19.3% | 31.3% |
| insider (sup 40, inf 85, 8 pushes) | 30.5% | 29.9% | 45.1% |

**RE-RUN 2026-08-19 with `tools/simulate_gauntlet.py`** (see §0 — a
real, re-runnable simulator now exists; it reads `chairs.json` and
`hearing_rates.json` live, so this table can't drift from the shipped
game the way the one above did). 20,000 sessions/cell, one bill per
session (a single family in isolation — see §0 on why that's still
right for a per-bill rate even with the bill-count cap removed):

```
$ python3 tools/simulate_gauntlet.py --sessions 20000 -v
profile   wealth          income          credit (hyp)
passive   3.3% (×0.58)    4.2% (×0.57)    11.3% (×0.58)
engaged   21.2% (×0.71)   23.7% (×0.71)   44.5% (×0.70)
insider   28.6% (×0.91)   30.9% (×0.91)   62.9% (×0.92)
```

`wealth` and `income` are the two LIVE families (conveyance/capgains,
wwcr). `credit` is HYPOTHETICAL — no credit-tagged revenue measure
exists in `policies.json` today, since `ctc` and `retitc` are
priorities now — simulated at the family's real measured cells to show
what restoring it would look like. The `(×N)` is the average `amtScale`
an enacted bill carries — how much conference dilution and the
support-floor cut typically take, separate from whether it enacts at
all.

Four things this has to keep doing, or the model has drifted (all
checked directly against this run, not eyeballed):
- **Never-heard dominates every profile** (the thesis) — verified
  separately by cause: 75–87% of every profile's deaths are "never
  heard" against the two live families, floor votes a distant second.
- **Credits beat wealth taxes at every skill level** (the design's
  headline contrast) — holds, and by MORE than the old table's ~1.5×:
  now 3.4× at passive, 2.1× at engaged, 2.2× at insider. Explainable,
  not a bug: it compounds through TWO gates (FIN credit 36% vs wealth
  26%, WAM credit 33% vs wealth 13%), so a ~1.4–2.6× single-gate edge
  becomes a bigger one after both committees. Still unreachable in
  play (§0) — this is the argument for eventually shipping it.
- **The insider outperforms the passive player** (the asymmetry) —
  holds, monotonically, in every family.
- **Passive rarely passes anything** (3–4%) — holds. The old phrase
  "engaged lands roughly one bill of three" assumed a fixed 3-bill
  package that no longer exists (no cap, §0); read this table as
  PER-BILL odds instead — an engaged player fielding N tax bills should
  expect roughly N × 0.21–0.24 of them enacted, independently.

## 9. Build order

1. Skills + the check engine + odds on dialogue buttons. Playable and
   fun on its own, touches no bill logic.
2. Chairs + `chair` gates + death by never-heard + the obituary screen.
   This is the feature's whole thesis; ship it second, not last.
3. Chambers, blocs, floor votes, crossover.
4. Conference, `amtScale`, the Grassroots-or-fold choice.
5. Thought cabinet as reputation, feeding checks and dispositions.

## Decisions (2026-08-13) — the campaign reframe

- **The player is not a legislator.** One identity — **The Advocate**,
  leading a campaign from outside the building. Members carry the
  bills; the player runs the coalition and the argument. This resolves
  the "which chamber" question below: neither.
- **Skills**: chosen at week 0 (5 points, as shipped) and honed by the
  actions taken — each action trains the skill it exercises, two uses
  per pip (`skillStart.honeEvery`).
- **Intel every round**, accuracy gated per facet by skills: Whip
  Count → live chair odds (rumor with deliberate noise → band →
  exact + disposition), Procedure → deadline warnings, Fiscal Acumen →
  the measured rate in print. Ledger odds gated by the same tiers;
  measured base rates stay public.
- The `campaign.json` sketch (Organizer/Wonk identities, voice picks,
  capital wallet, 7-stage turns) is superseded and deleted; its intel
  bands live on in session.json.

## Decisions (2026-08-13) — skills retooled: wonk / organizer / bridge

- **Backbone never fit a lane and is retired.** The six skills are now
  a clean 2/2/2: wonk (Fiscal Acumen, Procedure), organizer (Rhetoric,
  **Grassroots**, new), bridge (Talk Story, Whip Count — reworded to
  make clear both work either direction, not just "inside" skills that
  happened to be useful outside). session.json `skills.*.pole` records
  this; nothing reads it yet — it's grouping metadata for a future
  week-0 UI pass, not wired into any mechanic.
- **Grassroots is coalition capacity** — how many people you can
  actually turn out. It took over both of Backbone's jobs (the
  conference hold-firm check, the "testify on the record" dare to
  Grange) because "does the deal survive a chair's pen" was always
  really "is there still outside pressure in the room" — a Grassroots
  question, not a generic resilience stat.
- **Actions can scale by skill, not just train it.** `session.json`
  actions gained an optional `scale.mods` block — the identical
  `{from, per}` shape as check mods, applied to the action's own
  effects via `modOf` (`scaledFx` in main.js). Rally uses it: Grassroots
  adds Public Support per point and reduces the Political Influence
  cost per point, so a skilled organizer's rally is the SAME action
  landing bigger and cheaper, not a different, better action unlocking.
  Deterministic, not a check — the weekly action stays the one
  guaranteed move a player can plan around; RNG stays reserved for
  dialogue checks. Rally's `trains` moved from Rhetoric to Grassroots
  to match (the rotunda-and-signs flavor was always turnout, not
  message-craft).

## Decisions (2026-08-13) — per-bill support/influence, distinct failure modes

- **One shared pool was hiding the lesson.** With `S.metrics.support`/
  `.influence` feeding every bill's odds, support and influence just
  added into the SAME probability — nothing forced a player to need
  both. Each bill now carries its own `support`/`influence`, seeded at
  introduction from the campaign's numbers plus a small tax-family tilt
  (`chairs.json` `gate.familyTilt`, editorial — same standard as
  `championed`: named, small, a judgment call, not survey data). A
  wealth-tax bill starts more popular and less connected than a GET
  bill drawn from the same coalition at the same moment; that gap is
  the honest version of "wealth taxes are hard" — not that voters
  dislike them (they generally don't), but that the opposition is
  concentrated and present at every gate while support is diffuse.
- **Two failure modes, not one.** Low influence still kills a bill
  outright — never heard, unchanged, that stays the thesis. Low support
  now does something ELSE: the moment a bill clears a chair gate,
  support under `gate.dilution.floor` shrinks `amtScale` right there
  (`gate.dilution.cut`, floored at `gate.dilution.min` so dilution alone
  never zeroes a bill) — separate from, and stacking with, conference
  dilution. A bill can limp out of committee already thin. That's the
  "heard, but gutted" mode a shared pool couldn't express.
- **Pushing got sharper.** `push` already targeted one live bill; it now
  also raises THAT bill's own influence (`gate.pushInfluence`), on top
  of the existing one-week odds bonus — the inside-game move you were
  already taking finally moves the number it should move.
- **The ledger can now say why, not just how likely.** `meterNote`
  surfaces a bill's own support/influence at the same Whip Count tiers
  that already gate the odds badge — a struggling bill now reads as
  either "no one downtown will hear it" or "it'll get through thin,"
  which are different problems with different fixes.
- **Cost:** the §8d calibration table is invalidated (flagged above,
  not yet re-run). Save migration is handled (`migrateBills()`,
  boot-time) — old saves' `S.bills[i]` had no `support`/`influence`
  keys, which would have gone `undefined` in the odds formulas and
  silently become `NaN` (`Math.random() < NaN` is always false — bills
  would never be heard again, quietly). Backfilled from current
  campaign numbers + the same family tilt as a fresh seed.

## Open questions

- ~~Which chamber is the player in?~~ Resolved above: the player is
  not a member of either.
- ~~Does the player carry all 3 bills through, or can they abandon one
  to concentrate influence?~~ Moot as asked (2026-08-19, §0): there is
  no 3-bill package and no cap, so "carry all N through" is just
  whatever the player picked at creation. The real question survives in
  a different shape — can the player DROP a live bill mid-session to
  concentrate influence on the rest? Nothing in `resolveBills` currently
  offers that; every bill in `S.bills` rides the gauntlet until it
  enacts or dies on its own. Worth another pass if abandoning turns out
  to be a real skill players want.
- Should skill points also come from events, or only week 0 + thoughts?
