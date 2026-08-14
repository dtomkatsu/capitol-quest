# Capitol Quest — feature scope

Module 1: **Taxes & the Budget.** The overworld map is the stage; features
layer onto it. Ordered by build sequence — each is small enough to ship
alone and each teaches one true thing about how Hawaiʻi's money works.

## 1. Tax inflows by ZIP — ✅ shipped

**The teaching point:** the state's money comes from people, everywhere on
the island — and it physically concentrates into one building.

- Data: DOTAX *Hawaiʻi Individual Income Tax Statistics* (TY2022),
  Table A-14 — resident tax liability after credits, by ZIP code.
  Pipeline: `tools/build_tax_flows.py` → `site/map/tax_flows.json`
  (53 Oʻahu zips, ≈$1.78B; PO-box zips fall back to their DOTAX
  "geographic area" centroid; Census 2020 ZCTA gazetteer for locations).
- Visual: quiet gold motes drifting along curved paths from each ZIP into
  the Capitol; spawn rate ∝ dollars, additive blend, low alpha, ~42 px/s.
  No lines, no arrows — the streams read as ambient light. HUD chip
  toggles the layer; Capitol dialogue cites the real total.
- Honesty note: individual income tax is the piece DOTAX publishes by ZIP.
  It is ~30% of general-fund revenue; GET (the biggest source) is only
  published by taxation district — see feature 2.

## 1b. HUD toolbar & budget overlay — ✅ shipped

**The teaching point:** here's the whole pot — $24.8B — and who gets it.

- Data: enacted FY2027 budget (HB1800 CD1 / Act 175 of 2026) by
  department, snapshotted from the Budget Primer pipeline
  (`~/BudgetPrimerFinal/docs/js/departments_act175_fy2027.json`).
  `tools/build_budget.py` (use `--refresh` to re-snapshot) →
  `site/map/budget.json`.
- UI: top-center toolbar (first button: pixel bar-graph "Budget") opens a
  JRPG panel: hero total, then 24 departments as horizontal bars stacked
  General / Federal / Other funds (palette validated for CVD on the navy
  surface: #b98a2e / #3987e5 / #199e70), shares, hover tooltips,
  source + Budget-&-Finance footnote. Toolbar gains one button per
  future feature (revenue mix, layers, quests).

## 2a. Revenue mix panel — ✅ shipped

**The teaching point:** most state revenue is the excise tax everyone
pays at the register — income tax (the map streams) is under a third,
and falling as the 2024 income-tax cuts phase in.

- Data (re-based 2026-08-13): **FY2027 PROJECTED general-fund taxes**,
  so the drill matches the FY2027 budget one screen up (the FY2025
  DOTAX Table 1.8 all-funds version is in git history).
  `tools/build_revenue.py` parses the by-type allocation in B&F's FY27
  Executive Supplemental "Tables Indicating the Basis for Revenue
  Estimates" (Dec 2025, checksummed vs the printed $9.695B) and scales
  every line onto the Council on Revenues 2026-05-21 forecast total
  ($9.822B, FY27 +1.0%) → `site/map/revenue.json`. County-surcharge,
  special-fund-tax and GF-nontax context amounts ride along for the
  hero/footnote.
- UI (redesigned 2026-08-13): now the **"Money in" tab of the combined
  money overlay**, two screens deep. It lands on the **funding mix** —
  General 💰 / Federal 🦅 / Other 🧰 nodes (FY2027 means of financing)
  flowing into the Capitol — and tapping the pulsing General node
  drills into the **tax mix**: 12 tax nodes ringed around the Capitol
  (r ∝ √amount, dollar amount under each label, emoji badges on the
  major sources 🛒💵🏨🏰🏢), motes drifting **inward**. Gold motes =
  income tax, teal = GET (matching the two island streams), green =
  every other tax. Hover/tap a node for the amount, share and who-pays
  text; "← Funding mix" backs out; a **List** toggle keeps the precise
  bar view (★ on the two map-drawn taxes). Dollars-per-mote matches the
  budget tab, so the tax view reads sparser than the $24.8B budget view
  on purpose.

## 2b. The GET map layer — ✅ shipped

**The teaching point:** the tax everyone pays at the register is the
biggest stream on the map — teal outnumbers gold, because it should.

**What the data can and cannot do** (checked before building):
- DOTAX publishes GET by *taxation district* only, and there are four:
  Oʻahu, Maui, Hawaiʻi, Kauaʻi. **Oʻahu is a single number — there is no
  sub-island GET geography published anywhere.** (Income tax is the
  exception: Table A-14 breaks it out by ZIP.)
- MEASURED: Oʻahu FY2025 GET liability **$2.903B** (63.8% of the $4.552B
  statewide), summed from the 12 monthly "GE liabilities by district"
  reports and checksummed against the June report's own FY2025
  cumulative column. Also measured: the split by business activity
  (retailing $1.24B, services $567M, contracting $375M, hotel rentals
  $129M, …).
- MODELED: the spread across the island. **Basis: population** (Census
  ACS 5-year residents per ZIP; `tools/build_get_flows.py --basis=payroll`
  switches it). See the note below — the choice of basis is a real
  editorial decision, not a technicality.
- The distinction is surfaced in the UI, not buried: the GET chip's
  tooltip states the measured-vs-modeled split, and the revenue panel
  footnote says GET is spread by payroll because DOTAX publishes it
  island-wide only.

### NOTE — choosing the modeled basis (decided 2026-08-13)

Because no measured sub-island GET geography exists, *whatever* basis we
pick is an argument, and the two candidates tell opposite stories:

| Basis | What it answers | What the map looks like |
|---|---|---|
| **population** (chosen) | who *bears* the tax — GET is charged on nearly every transaction and passed through to customers | teal rises evenly across the island: ʻEwa 8%, Waipahu 7%, Salt Lake 6%, Kāneʻohe 6%, Mililani 5%… |
| payroll (CBP) | who *remits* it — the legal incidence is on the business | ~50% of the island collapses onto downtown 96813 (24%) + airport 96819 (17%), reading as "Honolulu pays for everything" |

Population wins because the lesson of this layer is that **everyone pays
GET, everywhere, every day** — the regressive-by-design fact that makes
GET politically distinct from the income tax. The payroll view is still
one flag away and is the honest choice if the question is ever "where do
businesses remit from" (e.g. a future GET-remittance or TOD module).

Both are modeled, neither is a DOTAX figure, and the UI says so. Retain
this note: a future contributor who "fixes" the basis without reading it
will silently change the argument the map is making.

**Visual:** teal motes, same calm language as the gold. Both streams
share one mote pool; each stream's **steady-state mote count** is
proportional to real dollars (GET:income = 1.6:1), so relative density
is an honest encoding. Normalising uses the *weighted* mean path
duration — GET's weight sits downtown on short paths, and an unweighted
mean silently under-draws it. Independent toggle chips per stream.

## 3. Outflows: Capitol → departments (budget overlay redesign) — ✅ shipped

**The teaching point:** the money doesn't stop at the Capitol. It flows
back out to 24 departments — and the *kind* of money differs by
department, which is why some agencies feel federal budget fights and
others feel state ones.

- Data: already in hand — `site/map/budget.json` (FY2027 enacted, Act
  175, from the Budget Primer pipeline), with per-department General /
  Federal / Other fund splits.
- Visual: the Budget overlay becomes a **radial mini-map** instead of a
  bar list. The Capitol pixel sprite sits at the center; the 24
  departments ring it, node size ∝ total budget, department code (HMS,
  TRN, EDN…) as the standing label. Money **flows outward** from the
  Capitol to each department as motes along faint spokes — reusing the
  map's mote language, so inflow and outflow read as one system.
- The flows carry the fund mix: **gold motes = general funds, blue =
  federal, green = other**, each sub-stream's density ∝ its dollars. So
  Human Services visibly runs blue (federal Medicaid match),
  Education runs gold, Transportation green (special funds). The lesson
  is in the motion, not a legend.
- Hovering/tapping a node reveals that department's numbers; a
  **List** toggle keeps the precise bar view (nothing is lost).
- 2026-08-13: budget + revenue merged into ONE overlay (`#money-overlay`)
  with two tabs — "↓ Money in · Taxes" (revenue, motes inward) and
  "↑ Money out · Budget" (motes outward) — sharing `buildRadialFlow()`.
  Both toolbar buttons remain and open the overlay on their tab.
- Later: promote this to the overworld itself — department landmarks
  (schools, UH Mānoa, hospitals, harbors) receiving the same streams.

## 4. Enter the Capitol: follow-a-dollar quest

- Interior scene (new Phaser scene, single painted room): the rotunda,
  House & Senate chamber doors, Finance/Ways & Means committee rooms.
- A dollar-coin NPC walks the player through: collected → general fund →
  executive budget request → legislative appropriation → governor's veto
  pen → department. JRPG dialogue boxes throughout.

## 5. Player character & guide

- Walkable sprite on the overworld (8-dir, collision from the land/urban
  masks already baked in build/map_grid.json); a guide character (mōʻī
  ʻiʻiwi bird?) who narrates and marks quest targets.

## 6. Rail stations & the TOD property-tax story

- The 19 Skyline stations become interactive stops (data already in
  site/map/oahu.json); teaches the county-vs-state split: property tax is
  COUNTY money, GET surcharge funds rail — with real figures from the
  Revenue-Modeling-TOD project.

## 7. Session timeline mini-game

- A bill's journey through the 60-day session as a JRPG "quest log":
  introduction → committees → crossover → conference → governor.
  Data: real deadlines from the legislative calendar.

## 8. Policies: the core loop — ✅ shipped (first cut, 2026-08-13)

**The teaching point:** budgets are choices. Priorities cost money, the
legislature has to raise the revenue to pay for them — and *who pays* is
part of the choice.

- Data: `site/map/policies.json`, hand-curated with a per-item source
  (amt = $ thousands/yr, FY2027 scale). Priorities: universal free
  school meals ($33M — Appleseed/DOE projected-participation co-payment
  cost), state child tax credit ($185M — $650 × ~284K keiki, modeled).
  Revenue: GET +0.5pt ($586M — FY27 GF GET projection ÷ 8), conveyance
  modernization ($75M), capital gains as ordinary income ($110M),
  worldwide combined reporting ($85M) — Budget Primer tax-fairness /
  ITEP numbers.
- UI: third toolbar button (**Policies**) → overlay with 🎯 Priorities
  and 💵 Raise revenue tabs; each row = name + who-pays line + ±$/yr
  price tag + Enact/repeal toggle (row tooltip = source). Enacted
  choices persist in localStorage (`cq-policies`).
- **Budget scoreboard** (bottom-right chip): FY2027 total; hover
  tooltip splits operating vs capital (Act 175). Priorities subtract
  from the total, revenue policies add, and a red/green delta line says
  why. Tapping the chip opens the Policies overlay.
- Next: consequences (what happens when the general fund runs dry),
  department-level effects on the money-out map, quest hooks.

## 9. One world: all eight islands, statewide streams — ✅ shipped (2026-08-13)

**The teaching point:** the whole state's taxes converge on one
building. Zoom out and the archipelago is one map; gold and teal motes
cross the channels from Hilo, Kahului and Līhuʻe into the Capitol.

- Engine is config-driven: `tools/islands.py` holds each island's grid,
  scale, real-crest ridgelines (Haleakalā with its crater, Mauna Kea /
  Mauna Loa with Mokuʻāweoweo, Kīlauea's caldera, Waiʻaleʻale, Nā Pali,
  Kamakou, Lānaʻihale …), plantation fields, reef-flat bays (Molokaʻi's
  south reef), towns and landmarks. Coastlines are the real statewide-GIS
  polygons; urban tiles come from Census 2020 urban areas plus hand town
  spots for sub-UA settlements. Oʻahu's bake is byte-identical to the
  single-island engine's.
- **One continuous world** (`tools/build_world.py`): every bake is
  anchored at its true position in a 41.8k×14.4k frame at 0.32 km/tile;
  Hawaiʻi bakes at 0.64 and displays at crisp integer 2×. A 1/12-scale
  stitched `overview.png` carries the zoomed-out view; detailed slices
  lazy-load as the camera approaches and unload (textures freed) when it
  leaves — that's what keeps mobile texture memory sane. The island menu
  flies the camera; the intro dives from the whole chain into the
  Capitol.
- **Statewide tax streams**: income tax now uses ALL A-14 county
  sections (121 ZIPs, $2.53B TY2022 — Oʻahu $1.78B, Maui $310M, Hawaiʻi
  $288M, Kauaʻi $137M…); GET uses all four districts' measured FY2025
  totals ($4.552B — Oʻahu $2.903B, Maui $714M, Hawaiʻi $626M, Kauaʻi
  $310M), each spread within its own district by population. ZIP world
  positions go through each island's transform chain (worldmath.py), so
  streams rise exactly from the drawn towns.
- Next: per-island stories (county budgets, the TAT), Molokini, quest
  hooks on neighbor islands.

## 10. The session: turns, dialogues, trait voices — ✅ framework shipped (2026-08-13)

**The teaching point:** a session is sixteen weeks of choices under a
clock. Disco-Elysium-style: your inner voices argue about taxes while
the calendar eats your options.

- **Turns**: one turn = one week. Week 0 is the week before session —
  pick up to 3 bills from policies.json to introduce; that agenda IS
  your session. Weeks 1–16 run Opening Day → laterals → crossovers →
  conference → Sine Die, then interim. Each week: an event dialogue
  pops (auto-opens when unplayed), unlimited "talk story" with
  characters, and exactly ONE action (📣 rally / 🤝 work the building).
- **Traits** chime in on every event, dialogue and action:
  PROGRESSIVE (Pro-Tax) in warm rose, CONSERVATIVE (Anti-Tax) in cool
  steel — DE-style interjections with distinct voices. More traits and
  the thought cabinet bolt on next.
- **Metrics**: Revenue ($K/yr — wired into the same FY2027 budget
  scoreboard as policy bills via `PolicyPanel.setExternal`), Working
  Families and The Wealthy & Businesses (0–100 opinion meters with
  bars). Every choice shows its deltas inline.
- **Content is data**: `site/map/session.json` — characters (fictional:
  Nālani Chun, Rep. Fonoti, Curtis Grange, Malia Reyes), calendar,
  scripted weeks (0, 1, 16) + a generic-event cycle (forecast rumor,
  emergency appropriation, hostile op-ed, testimony day, caucus
  potluck), repeatable default talks. Dialogue nodes support goto
  chains. State persists in localStorage `cq-session` ("Restart
  session" in the overlay footer, double-tap armed).
- The Session toolbar tab tracks the week (W0…) and reopens the
  overlay any time.
- Next: feature 11 below.

## 11. Bills through the gauntlet, chairs, skill checks — 🚧 step 1 shipped (2026-08-13)

**Shipped:** six skills (Fiscal Acumen, Procedure, Whip Count,
Rhetoric, Talk Story, Backbone) allocated 5 points at week 0 in the
session hub; a 2d6 + skill + mods check engine with live odds printed
on the choice button; white (retryable when the bonus improves) vs red
(one shot) checks; roll reveals that show their arithmetic; skill
voices that chime in alongside PROGRESSIVE/CONSERVATIVE. The two
opinion meters became **Public Support** and **Political Influence**
(old saves migrate). Checked choices live in `session.json` on
`w1-fonoti`, `w1-grange`, `ev-forecast`, `ev-oped`, `talk-malia`.

**Step 2 shipped (2026-08-13):** bills are tokens moving through the
calendar's real deadlines; the two MONEY committees gate them — House
Finance and Senate Ways and Means, the busiest and hardest committees in
the building — with one fictional chair each;
a bill that is never scheduled dies with `never heard` — no vote, no
record. Scheduling odds start from MEASURED hearing rates
(`site/map/hearing_rates.json`, generated by the Legislative Research
Tool from referral sheets + chamber journals + hearing notices) and add
editorial terms on top; the bill row's tooltip shows the real number.
Leadership rolls the referral. Conference dilutes via a Backbone check,
which shows up as fewer dollars rather than a separate stat. Sine Die
reports revenue raised / priorities funded plus an obituary that reveals
the chair disposition the player never got to see.

Rates are per TAX FAMILY, because the building does not treat tax bills
alike: pooled 2025–26 it noticed **43% of tax-credit measures and 25% of
measures taxing wealth**, and at House Finance specifically 32% vs 24%.
`policies.json` items carry a `tax` family; the bill tooltip cites the
measured cell and says so out loud when a thin cell borrowed a broader
rate.

**Still design-only:** subject-matter committees (out of scope on
purpose), chamber blocs and real floor votes (floor stages are a
placeholder probability today), the thought cabinet.

**The teaching point:** most bills don't lose votes — they never get a
vote. Bills become tokens moving through the calendar's real deadlines
(laterals, crossovers, conference); committee chairs decide whether
they're ever scheduled; dialogue choices roll 2d6 + skill against a
DC with the odds shown on the button. The two opinion meters become two
currencies with different physics — Public Support (spent at hearings
and votes, decays) and Political Influence (applies to every scheduling
decision, doesn't decay). Scored at Sine Die on revenue raised and
priorities funded; a diluted bill just carries fewer dollars.

Full schema draft: `DESIGN-11-bills-and-checks.md`.

## Visual language rules (all features)

- Flows are ambient, never diagrammatic: motes, not arrows; alpha < 0.6;
  additive blend; calm speeds (< 60 px/s). The map must stay readable
  with every layer on.
- Every number on screen traces to a named public source, cited in the
  layer's HUD chip tooltip and in this file.
- Layers are individually toggleable and default to the least busy mix
  (inflows ON, everything else OFF until visited).
