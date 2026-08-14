# Capitol Quest — working notes

Educational isometric JRPG about Hawaiʻi state policymaking. Module 1:
taxes & the budget. Static site in `site/`, no build step for the frontend.

## Hard rules

- **North-up iso**: screen-up = geographic north. Grid axes are diagonal to
  geography — NEVER convert lon/lat to tiles by linear bbox scaling; always
  use `lonlat_to_cell()` / `cell_center_lonlat()` in `tools/build_map.py`.
- **Rebuild order**: `tools/build_map.py --island <slug>` →
  `tools/render_map.py --island <slug>` (or `--all`). Sprites:
  `tools/make_sprites.py`. The map is baked; editing `site/js/main.js` alone
  never changes terrain.
- **ONE world, all eight islands** at true geographic positions.
  `tools/build_world.py` composes the per-island bakes into a single
  41.8k×14.4k coordinate frame at the 0.32 km/tile reference scale and
  writes `site/map/world.json` (anchors, display scales, Capitol world
  px) + `overview.png` (1/12 stitch, the always-loaded zoomed-out
  backdrop). Hawaiʻi bakes at exactly 0.64 km/tile = 2× reference and
  displays at integer 2× — keep any future tile_km an INTEGER multiple
  of 0.32 (build_world asserts). Rebuild order for a terrain change:
  build_map → render_map → **build_world** → build_tax_flows +
  build_get_flows (flows carry world px).
- Per-island geography (grid, scale, ridgelines, craters, fields, towns,
  landmarks) lives in `tools/islands.py`; render reads geometry from
  `build/map_grid_<slug>.json`, NEVER from its own constants.
  Oʻahu regression rule: after touching the engine, rebuild oahu and
  diff `build/map_grid_oahu.json` tiles/heights against the committed
  bake — the refactor kept them byte-identical; keep it that way.
- **Downstream layers convert lon/lat to world px THROUGH the containing
  island's transform chain** (`tools/worldmath.py world_px()`: bake px ×
  scale + anchor) — never through the world frame directly, or points
  drift off the drawn geography (each island bake has its own kmPerLon).
- Neighbor-island coastlines: `data/coastlines/<slug>.geojson` (statewide
  GIS coast_n83, split by `tools/prep_islands_data.py`); urban =
  `data/urban_areas_hi.geojson` (Census 2020 UAs) + hand `towns` circles
  in islands.py for sub-UA settlements (Kaunakakai, Lānaʻi City …).
  Oʻahu keeps its Mahele-Atlas outline + road-density urban — untouched.
- Runtime: lazy island manager in `WorldScene` (`manageIslands` on a
  400ms timer) loads an island's slices/labels/sparkles when the camera
  is near and zoom > 0.06, and unloads + frees textures when far — the
  overview backdrop covers the gap. The "· Oʻahu ▾" title-chip menu is a
  camera fly-to (`flyTo`), NOT a scene switch. minZoom fits the whole
  chain and is recomputed on resize (`recomputeMinZoom` — the canvas can
  report 0×0 when booted hidden; never trust `scale.width` alone).
- **Slices must stay < 4096 px** per side (old-mobile GL limit kept for
  safety even though we render with Canvas): render_map asserts this.
- Phaser is vendored (`site/vendor/phaser.min.js`, v3.90.0, MIT). Do not
  swap to CDN.
- Canvas renderer on purpose (`type: Phaser.CANVAS` in main.js) — the world
  is one baked image; WebGL adds quirks (embedded webviews) for no gain.
- Cache-busting `?v=` params in `site/index.html` — the global pre-commit
  hook auto-bumps them on commit; don't bump by hand.

## Testing in the Claude Code Browser pane

The pane never fires rAF (runs hidden). Load with `?raf=mc` to enable the
dev shim in index.html, and drive the camera via `window.__game`:

```js
const s = window.__game.scene.getScene('world');
s.stopIntro(); s.cameras.main.setZoom(1.8);
s.cameras.main.centerOn(...s.meta.camera.capitol);
s.applyLabelScale();
```

Phantom pointer/wheel events happen in the pane (they cancel the intro
tween and can zoom randomly) — position the camera explicitly before
screenshots; not a game bug.

## Tax-flow layer (feature 1) — STATEWIDE

`tools/build_tax_flows.py` parses ALL county sections of DOTAX Table
A-14 (individual income tax by ZIP, TY2022 — headers "O'AHU" /
"MAUI COUNTY" …; STATE sections skipped) + Census ZCTA gazetteer →
`site/map/tax_flows.json` with WORLD px via worldmath.world_px().
Runtime `buildFlows()`/`update()` drifts gold motes along bezier paths
from every island into the Capitol (rate ∝ dollars, additive,
alpha ≤ 0.55). Neighbor-island crossings cap at MAX_DUR 60s so the
dollars-per-mote density stays honest without minutes-long flights;
mote screen size is constant down to z≈0.07, then fades to dust at
chain zoom (clamp cap 14).

## Money overlay = one panel, two radial tabs (features 2a + 3)

Budget and revenue share ONE overlay (`#money-overlay`, `MoneyPanel` in
main.js) with two tabs. "↓ Money in" is two screens deep: it LANDS on
the funding mix (3 nodes — General 💰 / Federal 🦅 / Other 🧰, FY2027
means of financing computed from budget.json) and the pulsing General
node drills into the FY2027 projected general-fund tax mix (12 nodes,
"← Funding mix" to go back; the tab always re-lands on the mix). "↑ Money out" is the 24
department nodes. Motes drift node→hub on money-in views, hub→node on
money-out. Both toolbar buttons remain and deep-link to their tab.
`buildRadialFlow()` is the shared component: Capitol sprite at the hub,
nodes on an ellipse (r ∝ √total, dollar amount as a second label line,
optional emoji icon inside circles with r ≥ 6.5, optional onClick +
.drill pulse, `scatter` spreads beads on few-spoke views), density ∝
dollars via the same Σ(rate × duration) normalisation as the map
streams. targetMotes keeps DOLLARS-PER-MOTE EQUAL across views (110 ⇒
sources 110, taxes ~43) — the sparser tax view is the teaching point
(federal funds + bonds spend on top of state taxes); don't "fix" it.
Animation gating is `offsetParent !== null` on the map div — hiding via
overlay/tab/sub-view/List all no-op the rAF loop. The ▤ List toggles
keep the bar views — don't delete them, they carry the precise numbers.
Budget nodes are labeled by DOTAX/budget CODE (HMS, TRN, EDN…); tax
nodes by the SHORT/ICON maps in `buildRevenue()`, whose keys must match
revenue.json tax names exactly (fallback: first word, no icon).

## Session overlay — turns + trait voices (feature 10)

`SessionPanel` in main.js + `site/map/session.json` (ALL content is
data: characters, calendar, dialogues, actions — write content there,
not in JS). One turn = one week; state in localStorage `cq-session`.
Rules that must survive edits:
- Every dialogue node, event and action carries trait `voices`
  (PROGRESSIVE/CONSERVATIVE chime-ins) — that's the Disco identity.
- Revenue effects (`revenueK`, $ thousands/yr) flow into the budget
  scoreboard via `PolicyPanel.setExternal(S.metrics.revenueK)` — call
  it after EVERY metric change and once on boot, or the chip drifts.
- One action per week (`S.actionWeek === S.week` gate); week 0 has no
  action — its move is locking the ≤3-bill agenda (`S.agendaLocked`).
- The weekly overlay auto-pops only while the week's event is
  unplayed; generic weeks cycle `genericEvents` by `(week-2) % n`.
- Characters are FICTIONAL — never use real legislators' names.
- Dialogue text is escaped (`esc()`) — keep it that way; content JSON
  is not trusted HTML.

## Policies overlay + budget scoreboard (feature 8)

`PolicyPanel` in main.js must init AFTER MoneyPanel: it registers extra
pointerdown listeners on tb-budget/tb-revenue (to close itself), and
same-element listeners run in registration order — MoneyPanel's
stopPropagation only stops bubbling, not those. `site/map/policies.json`
is HAND-CURATED editorial data ($ thousands/yr, FY2027 scale): every
item needs a defensible `amt` and a `src` line (shown as the row
tooltip). Priorities spend from the FY2027 budget scoreboard
(#fund-chip, bottom right — tooltip splits operating vs capital);
revenue policies add to it. Enacted ids persist in localStorage
`cq-policies`; unknown ids are dropped on load, so RENAMING an id
silently repeals it for existing players. The GET half-point amt is the
FY27 GF GET projection ÷ 8 — recompute it whenever revenue.json
re-bases.

## Revenue-mix layer (feature 2a) — FY2027 projected, general fund only

`tools/build_revenue.py` builds the FY2027 PROJECTED general-fund tax
mix so the money-in drill matches the FY2027 budget year (the FY2025
DOTAX Table 1.8 all-funds version is in git history). Sources in
data/raw/: `fy27supp_revenue_basis.pdf` (B&F FY27 Executive
Supplemental, Dec 2025 — TRPO's by-type allocation of the COR 2025-09-04
forecast, checksummed vs the printed $9.695B) and
`cor_gf_2026-05-21.pdf` (Council on Revenues, latest forecast: FY27
$9.822B, +1.0%). Line items are scaled onto the COR total — TRPO's own
method — and the scaled sum must land on it within rounding ($50K).
County-surcharge / special-fund-tax / GF-nontax context amounts ride
along for the hero + footnote; they are NOT general fund — never add
them into `total`. Next COR meeting is 2026-09-03: when the new report
posts, drop the PDF in data/raw/, update COR_PDF + the growth sanity
check, re-run.

## GET layer (feature 2b) — measured vs modeled, STATEWIDE

**GET has NO sub-island geography.** DOTAX publishes it by taxation
district only — Oʻahu / Maui (= Maui+Molokaʻi+Lānaʻi) / Hawaiʻi / Kauaʻi
(= Kauaʻi+Niʻihau). `tools/build_get_flows.py` sums the 12 monthly
district PDFs for real FY2025 totals per district (statewide $4.552B
checksummed vs the June cumulative; Oʻahu $2.903B) and then MODELS the
spread WITHIN each district — district totals are never reallocated
across districts. Never present the spread as a DOTAX figure — the chip
tooltip and revenue footnote must keep saying which half is measured.
PDF quirk: the UNKNOWN district column is 0 and invisible to the number
regex; when ≥1,000 it shifts columns (the `off` guard in parse_month).

**Basis = population** (ACS5 by ZIP), NOT payroll. `--basis=payroll`
switches to the CBP remittance view. This is an editorial decision with a
rationale table in FEATURES.md ("NOTE — choosing the modeled basis"):
population says everyone pays GET everywhere (the point of the layer);
payroll collapses half the island onto downtown + the airport. Read that
note before changing it. (CBP sector-level PAYANN is suppressed at ZIP
level — only the all-sector "00" total is usable.)

Flow density rule: steady-state motes = Σ(rate × duration), so stream
rates normalise by the WEIGHTED mean duration. Using an unweighted mean
under-draws GET (its weight is downtown on short paths) and silently
breaks the dollars-to-density encoding.

## Data lineage

- **Budget data is explicitly DOWNSTREAM of ~/BudgetPrimerFinal**: the
  Act 175 extracts (departments + summary stats) are snapshotted into
  data/raw/ by `tools/sync_primer.py`, which rebuilds budget.json. A
  post-commit hook inside BudgetPrimerFinal (`.git/hooks/post-commit`,
  installed by `sync_primer.py --install-hook`, chained by the global
  ~/.config/git-hooks dispatcher) re-runs the sync with `--commit`
  whenever a commit there touches those extracts — updates flow here
  automatically. Hooks aren't tracked: re-run `--install-hook` if
  BudgetPrimerFinal is ever recloned. Log: ~/.config/capitol-quest-sync.log.
- `data/island_outline.geojson` ← ~/Mahele-Atlas (Oʻahu coastline)
- `data/rail_alignment.geojson`, `data/stations.geojson` ← ~/Revenue-Modeling-TOD
- Road density reads `~/Revenue-Modeling-TOD/data/raw/road_centerlines.geojson`
  directly (40 MB, NOT copied into this repo). Only derived tiles are
  committed. If that repo moves, update the path in build_map.py.

## Renderer v2 (render_map.py) — modern look, screen-space ground

The ground is rendered per PIXEL, not per tile: coastline filled from the
real island polygon (smooth curves), water colored by distance-to-shore
bands (octagonal-metric dilation, distances CAPPED not sentineled — a 255
sentinel leaves a visible contour), terrain-class boundaries jittered with
smooth noise, mountains a blurred heightfield with displacement relief
(side pixels shaded by slope steepness — flat side-shading terraces into
contour lines), and trees/houses/towers as outlined sprites with cast
shadows, depth-sorted. Gotchas learned the hard way:
- land pixels can sample a WATER class from the coarse tile grid (polygon
  outranks grid) — they MUST be remapped to sand/grass or they render
  pure black
- PIL thick multi-point polylines grow "bowtie" blobs at sharp joints
  (the rail alignment doubles back) — stroke rail per-segment
- _outline must ignore translucent shadow pixels (alpha >= 200 test)

## Terrain classification (build_map.py)

water deep/mid/shallow (chebyshev dist-to-land rings; wider reef in
Kāneʻohe Bay) · sand rim + palms · grass · field (two crop palettes) ·
forest · mountain/peak (hand ridgelines + noise widths, graded heights
toward crest) · urban (road density ≥ 20, de-speckled) · urban_dense
(density ≥ 60 inside the downtown core bbox). Craters: Lēʻahi, Koko,
Pūowaina. Rail: tile mask for gameplay + smooth fractional paths for ink.
