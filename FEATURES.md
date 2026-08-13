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

## 2. The GET layer & "who pays what" — next

- Data: DOTAX annual report (Liquid fuel/GET/TAT collections by taxation
  district); DOTAX GE/Use monthly. Oʻahu = 1st district.
- Visual: a second flow color (teal) emanating diffusely from towns
  (weighted by road-density urban mask, since GET has no sub-district
  geography); a toggleable "revenue mix" panel: GET vs income tax vs TAT
  with real shares.
- Teaching point: most state revenue is the excise tax everyone pays at
  the register — not just income tax.

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
