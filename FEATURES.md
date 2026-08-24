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
  - ✅ 2026-08-22 first cut: `CapitolScene` (main.js) — the GALLERY
    RING above the rotunda (user's call: the view is the gallery/
    railing area), baked by `tools/render_capitol.py` as a 2.5-D iso
    cutaway: a NARROW low-gallery balcony one storey above the
    chamber level, railings at the open well, the sun patch and a
    generic floor medallion below (never Sato's copyrighted Aquarius
    composition), the chambers' flared lava drums at courtyard level only (the cones
    are NOT visible from the balconies — galleries wrap around them),
    chamber-gallery + committee doors, open hallway mouths and
    recessed elevator lobbies branching deeper into the building
    (single-level walls — "just rotunda and the floor you're on",
    user's call), exit stairs makai. Tapping the overworld Capitol enters; hotspots carry
    the educational text. The dollar-coin NPC quest still to come.
- A dollar-coin NPC walks the player through: collected → general fund →
  executive budget request → legislative appropriation → governor's veto
  pen → department. JRPG dialogue boxes throughout.

## 5. Player character & guide

- Walkable sprite on the overworld (8-dir, collision from the land/urban
  masks already baked in build/map_grid.json); a guide character (mōʻī
  ʻiʻiwi bird?) who narrates and marks quest targets.

**SCOPED 2026-08-22 — walk the CAPITOL INTERIOR first** (the overworld
variant is a later reuse: at km-scale tiles the interior sprite is 2px,
it needs its own mini-sprite). The player controls THE ADVOCATE walking
the gallery ring in `CapitolScene`.

**A. The character.** Androgynous by construction (design settled
2026-08-22 after two concept rounds):
- Silhouette rules: shoulders ≈ hips, no waist pinch, no broad-shoulder
  V — those two cues are what gender a silhouette. Head:height ≈ 1:3.6
  (the banner-crowd proportion rules apply here too).
- Aloha business casual, i.e. what people actually wear in that
  building: muted teal short-sleeve aloha shirt with a 2–3px scatter
  print, charcoal slacks, brown shoes. SHORT-CROP dark hair (user's
  call — the collar-length low tie of round 1 is out).
- NO lei (user's call, round 2) — the sprite carries no gold accent;
  the one-gold-accent rule stays a glyph/portrait rule, not a sprite
  rule.
- VAGUE FACIAL DETAILS (user's call — a documented exception to the
  faceless-campaign rule, which still binds portraits and glyphs).
  Four concept rounds taught what "elegant" means at an 8px face:
  - SCULPT IN VALUE PLANES, never draw features. The children's-
    drawing read = symmetric dot-features floating on a flat oval.
    One key light (upper-left, same as the body) builds three zones —
    lit left (G), mid (F), core shadow right (E→D) — and the
    features are small disruptions INSIDE the zones: eyes sunk in a
    socket band (the shadow-side eye barely implied), a nose-bridge
    light, a cheekbone catch, an off-centre 2px mouth, a jaw that
    TAPERS through two rows to a narrow chin, the neck in the jaw's
    cast shadow. A swept asymmetric fringe, not a symmetric cap.
  - Eyes at LOW contrast (a warm dark ~2 stops under skin base),
    never black — full-contrast eye px are the button-eye doll fail.
  - Proportion: hair crop 4 rows, face 6-7 — a 5/5 split read as a
    helmet on a squashed face.
- "Higher-def" rendering, not bigger canvas (26×42): hue-shifted
  3-tone ramps (shadows cool, lights warm), SLOPED shoulders and
  tapered sleeves and rounded shoes (the 90° box corners were half
  the ugly-edge read), and a soft 55%-alpha keyline — the map-sprite
  convention; an opaque dilation halo was the other half of the ugly
  edge.
- Scale: door leaves are 46px, so the standing figure is ~40px in
  scene px. Author at native 1× and judge readability at the SNAPPED
  0.5 game zoom, per the interior render-quality rules.
- Sheet: `tools/make_player.py` (procedural, like every other asset) →
  `site/assets/sprites/player.png`. Two DRAWN facings (toward-camera
  SE, away NE) × horizontal mirror = 4 iso directions; idle + 4-frame
  walk (contact–pass–contact–pass) each = 20 frames, ~8 fps.

**B. Occlusion overlay (the one renderer change).** The room is one
baked PNG, but the well railings, rail pots, corner planters, makai cut
stubs and stair cheeks all stand NEARER the camera than walkway ground
behind them. `render_capitol.py` gains a second output,
`capitol_over.png` — transparent, occluders only — drawn from the SAME
geometry in the same bake. Runtime: base at depth 0, player 50, overlay
100. Floor reflections stay in the BASE (they are floor). All three
files ride the one `CAP_V`.

**C. Navigation — geometry, not a mask.** The walkable ring is pure
math: invert the (linear) iso transform screen→(u,v); walkable iff
`A_IN + m < max(|u|,|v|) < A_OUT − m`, minus planter/pot circles, plus
the stairs mouth (which is the walk-out exit). Constants ship in a
`nav` block in capitol.json — same-geometry-one-source, no mask file.
Collision = reject step, with axis-slide so walls feel smooth.

**D. Controls.** WASD/arrows 8-dir + tap-to-walk (clamp target to the
ring, walk straight, slide around corners — no A* for a convex ring).
Proximity ≤ ~48px lights a hotspot's marker and Space/tap interacts;
direct hotspot taps keep working (touch must not regress). Exit: walk
onto the stairs mouth, or Esc as today.

**E. Order of work.** (1) make_player.py sheet — half the effort and
all the art risk, iterate at 4× crops; (2) overlay split + nav block +
CAP_V bump; (3) CapitolScene input/move/collide/anim/depth; (4)
proximity affordance + stairs exit; (5) pane pass (`?raf=mc`, drive
with synthetic keys, MutationObserver-style patience on anims).
Known risks: readability at the snapped zoom; androgyny drifting in
the side/walk frames (re-check shoulders≈hips every frame); the
overlay double-drawing floor pixels (it must carry only what stands).

- LATER, on this framework: the §4 dollar-coin guide NPC (same nav +
  occlusion), other balcony NPCs, the overworld mini-sprite.

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
Rhetoric, Talk Story, Grassroots) allocated 5 points at week 0 in the
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
Leadership rolls the referral. Conference dilutes via a Grassroots
check, which shows up as fewer dollars rather than a separate stat. Sine Die
reports revenue raised / priorities funded plus an obituary that reveals
the chair disposition the player never got to see.

Rates are per TAX FAMILY, because the building does not treat tax bills
alike: pooled 2025–26 it noticed **43% of tax-credit measures and 25% of
measures taxing wealth**, and at House Finance specifically 32% vs 24%.
`policies.json` items carry a `tax` family; the bill tooltip cites the
measured cell and says so out loud when a thin cell borrowed a broader
rate.

**Step 3 shipped (2026-08-13) — the campaign reframe:** the player is
**The Advocate** — one identity, leading a campaign from outside the
building. No seat, no vote, no floor minute, no co-signing: members
carry the bills, the player runs the coalition and the argument
(session.json content rewritten to match; the Opening Day floor minute
became the campaign's press slot on the makai steps). Skills are
chosen at week 0 (5 points) and **honed by doing** — each action
trains the skill it exercises (rally → Rhetoric, work the building →
Talk Story, pushing a bill → Procedure); two uses buy a pip. Every
round the campaign receives an **intel report** whose accuracy is
gated per facet by skills: Whip Count prices the chairs (hallway
rumor that can be off by a band → honest band → exact live odds plus
the chair's disposition), Procedure reads the clock (deadline
warnings before they're a week out), Fiscal Acumen puts the measured
hearing rate in print. The bill ledger's live odds are gated by the
same Whip tiers; the measured base rate stays public. The information
asymmetry IS the teaching: the paid lobbyist starts every session at
whip-sheet tier. (An earlier `campaign.json` sketch — two identities,
voice picks, a capital wallet — was superseded by these decisions and
deleted.) Also fixed: the push action's +15 scheduling bonus was
checked against the post-increment week and never actually landed on
the roll; it does now, and is cleared once consumed.

**Step 4 shipped (2026-08-13) — Backbone retired, Grassroots added:**
the six skills now split clean 2 wonk (Fiscal Acumen, Procedure) / 2
organizer (Rhetoric, Grassroots) / 2 bridge (Talk Story, Whip Count) —
Backbone never fit either pole and is gone. **Grassroots** is coalition
capacity: how many people you can actually turn out. It governs the
conference-committee hold-firm check (public pressure is what keeps a
deal from being quietly cut — the same job Backbone used to do) and the
"say it on the record" dare to Grange, and it has a second, direct
hook: `session.json` actions can now carry a `scale.mods` block (same
`{from, per}` shape as check mods) that boosts the SAME action's
effects by a skill — Grassroots turns one rally into a bigger, cheaper
one (more Public Support per point, less Political Influence spent),
rather than a different action becoming available. Rally now trains
Grassroots, not Rhetoric — the rotunda-and-signs flavor was always a
turnout skill, not a message one.

**Step 5 shipped (2026-08-13) — per-bill support/influence, distinct
failure modes:** the two opinion meters stopped being one shared pool
that every bill drew from. Each bill now gets its OWN support and
influence, seeded at introduction from the campaign's current numbers
plus a small editorial tilt by tax family (`chairs.json`
`gate.familyTilt`) — a wealth-tax bill starts more popular and less
connected than a GET bill drawing on the same coalition, because they
draw on different bases. From there the two numbers diverge per bill
(pushing a bill raises THAT bill's influence; `gate.pushInfluence`).
This makes the two failure modes the design always implied actually
distinct: low influence still kills a bill outright (**never heard**,
unchanged), but low support now does its own thing — the moment a bill
clears a chair gate, if its support is under `gate.dilution.floor` it
comes out smaller (`gate.dilution.cut`), separate from and stacking
with conference dilution. A bill can now limp out of committee already
thin, which is a different death spiral than never being heard at all,
and the ledger shows both numbers once Whip Count clears the same
tiers that gate the odds badge (`meterNote`).

**Known follow-up:** the §8d calibration table in
`DESIGN-11-bills-and-checks.md` was run against the OLD shared-pool
model and is now stale — re-run needed before citing those numbers
again.

**Step 6 shipped (2026-08-13) — the Disco Elysium visual pass:** the
dialogue stopped looking like a HUD and started looking like a book.
Dialogue renders into `.sd-scene`, a dark serif reader inset in the
bright JRPG panel: speakers are `NAME – line` inline (not a header
block above the text), continuation lines hang under the TEXT so the
colored names form a clean left column, the role sits dimmed and
italic after the name, and choices are numbered in signal red. The
player's chosen line reads back as `YOU – …` in pale blue; authored
`reply` text stays unattributed prose (`.sd-narr`) because that
content is a mix of spoken answers and pure narration, and putting a
character's name on narration would be a lie.

Skill voices now take their color from their POLE rather than all
being one gold — the pole palette (`.p-wonk` blue / `.p-bridge`
magenta / `.p-organizer` red-orange) is shared by the voices, the
check metadata, and the character sheet, so a color means the same
thing everywhere. The skill sheet became a Disco-style character
sheet: skills grouped in columns under the campaign function they
serve (labels/order from `session.json` `poles`, so grouping is
content, not code), each group in its own color, and the level shown
as a NUMERAL in a bordered box rather than a row of dots — it reads at
a glance and doesn't imply the cap is a progress bar you're meant to
fill. Mid-practice skills show a half-filled box.

Two rules worth keeping: HUD elements that render *inside* a scene
(`.sd-fx`, `.sd-done`, `.sd-roll`) must set the sans stack explicitly
or they inherit the dialogue serif; and the pole-color fallback lives
on `.sk-sheet` (the parent) — declaring it on `.sk-col` puts it at
equal specificity with `.p-*` and later source order silently paints
the whole sheet gold.

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
  with every layer on. (2026-08-21: motes are short COMETS — a tapered
  tail rotated to the path tangent — same alpha budget and speeds; the
  tail buys legibility, not brightness.)
- The ONE sanctioned exception is the "✦ Streams" highlight toggle
  (OFF by default, persisted in `cq-flow-hi`): faint route ribbons that
  fade out before the hub (still no arrows), breathing source glints,
  a soft arrival pulse, motes at alpha ≤ 0.68 and ~1.5× density. It is
  a teaching view the player opts into, never the resting state.
- Every number on screen traces to a named public source, cited in the
  layer's HUD chip tooltip and in this file.
- Layers are individually toggleable and default to the least busy mix
  (inflows ON, everything else OFF until visited).
