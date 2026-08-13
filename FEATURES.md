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
pays at the register — income tax (the map streams) is only 29%.

- Data: DOTAX Annual Report FY2024-25, Table 1.8 (all tax types, cash
  collections). `tools/build_revenue.py` parses the PDF table with a
  checksum against the printed $11.46B total → `site/map/revenue.json`.
- UI: second toolbar button (coin-stack icon) → panel: $11.5B hero with
  the general-fund/counties/special-funds split, 16 tax categories as
  single-hue bars, the income-tax row highlighted gold + ★ ("shown as
  streams on the map"), hover explains who pays each tax.

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

## 3. Outflows: where the money goes

- Data: enacted budget by department (already parsed in the
  BudgetPrimerFinal repo — fy_comparison / report_data pipelines).
- Visual: reverse streams (cool white-blue) from the Capitol out to icon
  landmarks: schools (DOE), UH Mānoa, hospitals (Med-QUEST), roads (DOT),
  parks (DLNR). Same unobtrusive language as inflows. Toggling "in" vs
  "out" is the first interactive lesson: revenue vs appropriation.

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

## Visual language rules (all features)

- Flows are ambient, never diagrammatic: motes, not arrows; alpha < 0.6;
  additive blend; calm speeds (< 60 px/s). The map must stay readable
  with every layer on.
- Every number on screen traces to a named public source, cited in the
  layer's HUD chip tooltip and in this file.
- Layers are individually toggleable and default to the least busy mix
  (inflows ON, everything else OFF until visited).
