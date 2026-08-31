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
  never changes terrain. Both steps read `data/rainfall_mm.png` AND
  `data/elevation_m.png` (committed; regenerate with
  `tools/build_rainfall.py` / `tools/build_elevation.py` only to
  refresh the source downloads — see the Rainfall and Elevation
  sections).
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
  bake — a pure refactor must keep them byte-identical. (The 2026-08-21
  rainfall gate was a deliberate terrain change: 616 Oʻahu tiles moved
  forest→grass/field, heights untouched; transform/landmarks/camera/
  sparkles verified identical across all eight islands, flows rebuilt
  with no diff.)
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
- rot.js (`site/vendor/rot.min.js`, v2.2.1, BSD-3-Clause) and a Phaser 3
  isometric plugin (`site/vendor/phaser3-plugin-isometric.js`, v0.0.7,
  MIT) are also vendored — see "Vendored: rot.js + Phaser iso plugin"
  at the end of this file before using either. `window.PhaserIso`'s
  actual export surface is `{default: IsoPlugin, IsoPhysics}` (verified
  in the pane) — `IsoSprite`/`Point3`/`Cube` are NOT exposed as
  separate globals, only reachable through `IsoPlugin`'s
  `scene.add.isoSprite(...)` factory once it's registered.
- Canvas renderer on purpose (`type: Phaser.CANVAS` in main.js) — the world
  is one baked image; WebGL adds quirks (embedded webviews) for no gain.
- Cache-busting `?v=` params in `site/index.html` — the global pre-commit
  hook auto-bumps them on commit; don't bump by hand.

## Testing in the Claude Code Browser pane

The pane never fires rAF (runs hidden). Load with `?raf=mc` to enable the
dev shim in index.html, and drive the camera via `window.__game`:

```js
const s = window.__game.scene.getScene('world');
s.stopIntro(); s.cameras.main.setZoom(1.3);   // maxZoom is 1.35
s.cameras.main.centerOn(...s.meta.camera.capitol);
s.applyLabelScale();
```

Phantom pointer/wheel events happen in the pane (they cancel the intro
tween and can zoom randomly) — position the camera explicitly before
screenshots; not a game bug.

## The canvas renders at DEVICE resolution (2026-08-28)

From "how can the sprite art be made to look higher-quality?" — and the
biggest answer was not about the art at all. Phaser 3 dropped
`resolution`, so a canvas sized from `window.innerWidth` gets a backing
store in CSS px and the browser blows it up by devicePixelRatio; with
`image-rendering: pixelated` on `#game canvas` that is a hard 2x2 block
duplication. **Measured before the change on a dpr-2 display: backing
store 1280x720 inside a 2560x1440 physical area** — every baked room,
marker and label at half the pixels the screen can draw.

The fix is the standard Phaser HiDPI recipe: `Scale.NONE`, game size in
DEVICE px, `zoom: 1 / DPR` so Phaser sets the canvas CSS box back to the
CSS size. Verified after: backing 2560x1440, CSS box 1280x720, camera
zoom exactly 2x its old value — **framing pixel-identical, drawn from
four times the samples**. `scale.displayScale` comes out at DPR, which
is what keeps pointer input landing on the right hotspot with no
conversion of our own (checked by tapping the hallway legislator).

**THE RULE THIS BUYS, AND EVERYTHING IN main.js NOW OBEYS IT: camera
zoom is DEVICE px per world px, so it reads DPR x higher than the
numbers every threshold in that file was calibrated against.** Anywhere
a zoom is COMPARED to a hand-tuned constant, or divides one to hold a
size steady on screen, go through **`zCss()`**. That is why not one of
the calibrated numbers had to be re-tuned — `maxZoom` 1.35, the label
visibility bands, `2.2 / zoom` line widths, the mote scale, the flow
hit radius, the `log2(zoom) * 3` ribbon bucket and the rooms' 1.6
ceiling are all still the CSS-space numbers they always were, just
multiplied by DPR or read through zCss at the point of use.

Things that are NOT simply "multiply by DPR", each of which was a real
bug in draft:

- **Text is the half that actually buys sharpness.** Phaser rasterises
  a Text object's glyphs at `fontSize`, so a label left at 13px on a
  device-px canvas is rasterised at 13 and then magnified. Fonts,
  stroke and tracking are authored in CSS px and set at `DPR x` that;
  `applyLabelScale` / `fit` divide the DPR back out of the world-space
  scale, so physical size is unchanged and only resolution moves.
- **The MARKER is the opposite** and must NOT get the `/ DPR`. It is a
  fixed-resolution sprite (16x20), not rasterised type, so its scale is
  the CSS-space one unchanged or it comes out half size. (Making the
  marker itself sharper means re-baking it bigger in make_sprites.py —
  not done.)
- **A Phaser pointer written into a DOM style needs `/ DPR`.** Exactly
  one place does that: the flow tooltip in `updateHover`, which
  compares `ptr.x` against `window.innerWidth`. Without it the tip
  tracks at double the cursor's distance from the top-left and flips at
  the wrong edge — off-screen on the right half of the map.
  `getDistance() > 8` drag slop is the same class of thing.
- **DPR IS A `let`, NOT A CONST**, and freezing it would be a
  regression: the code this replaced read `window.devicePixelRatio`
  fresh inside `fit()` every time. It changes on a move to another
  display and, far more commonly, on **browser zoom**, which is
  implemented as exactly this. `watchDpr()` re-arms a media query
  pinned to the current value; `relabelForDpr` re-derives type from the
  stashed `_cssSize` (never a multiply by the ratio, which would
  accumulate rounding across zoom steps); and **WorldScene has to carry
  its camera zoom by the ratio** because it is wherever the player put
  it — a room recomputes zoom from the viewport in `fit()` and needs
  none of that.
- **`syncSize()` must ALSO detect a DPR move, and this is load-bearing,
  not belt-and-braces.** A page can run before it has a box — a
  background tab, an embedded webview, **the Browser pane** — and in
  that state this browser reports `devicePixelRatio` as **0**, not as
  its eventual value. The media query then gets armed against a density
  that was never real and never fires, and the game sits at the
  fallback DPR of 1 for the whole session. Gaining a layout is a
  resize, so checking there covers it. Same hidden-boot hazard as
  `viewSize()` and `centerTimeline()`.
- **`Scale.NONE` does not follow the window, so a ResizeObserver on
  `#game` is required.** RESIZE re-measured the parent every step,
  which quietly covered the 0x0-at-`load` case; a `window.resize`
  listener alone does not, and the canvas stays 0x0 forever. Caught in
  the pane, which does precisely this.

Pane-testing trap, hit again here and worth restating: the script tag
is `js/main.js?v=<token>`, so `fetch('js/main.js', {cache:'reload'})`
refetches a DIFFERENT url and the versioned one is still served from
cache. Refetch the exact `src` off `document.scripts`, then reload —
several probes' worth of confusing results came from measuring stale
code.

Not changed, and still the ceiling on the room art: the hallway's
`view` rect is 818x519 scene px filling 2560x1440 device px, a **2.77x
magnification**. Anti-aliasing cannot invent detail at that ratio, so
the remaining lever is authored resolution — and every painter is
written in scene px with hardcoded literals, which is the same wall the
`SS 2 -> 1` note below runs into.

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
money-out. **ONE toolbar button (`tb-budget`) is the only door**, and it
lands on "↑ Money out"; the tabs carry the player to money-in. The
separate `tb-revenue` button was removed 2026-08-15 (user's call) as a
duplicate entrance to the same overlay — don't re-add it. Anything that
wired listeners onto both ids (PolicyPanel's close-on-open loop,
SessionPanel's) now lists tb-budget alone.
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

## Session overlay — turns + skill voices (feature 10)

`SessionPanel` in main.js + `site/map/session.json` (ALL content is
data: characters, calendar, dialogues, actions — write content there,
not in JS). One turn = one week; state in localStorage `cq-session`.
Rules that must survive edits:
- **The player is THE ADVOCATE — one identity, leading a campaign from
  OUTSIDE the building.** No seat, no vote, no floor minute, no
  co-signing: members carry the bills ("your introducers"), the player
  runs the coalition and the argument. Content must NEVER hand the
  player a legislator's powers; the pre-2026-08-13 draft that framed
  the player as a member is gone, as is `campaign.json` (a two-identity
  Organizer/Wonk + voice-picks + capital-wallet sketch, deleted —
  superseded by these decisions; its intel bands moved into
  session.json).
- **Creation is its OWN screen and it comes FIRST** — renderSelect
  (skSelectHtml + GLYPH in main.js, `.sk-select`/`.creating` CSS), the
  Disco archetype-screen treatment: glyph cards, nothing else visible,
  a CONTINUE plate (`.sk-begin`) disabled until every point is spent.
  "Its own screen" means the session overlay's OWN CHROME disappears
  too, not just the hub content below it — a `.creating` class on
  `#session-overlay` (added by renderSelect, removed by renderHub and
  showDialogue) hides the "The Campaign · Week N" title chip, the
  close X, the week/timeline/metrics header and the footer caption via
  CSS, and the panel goes borderless and full-bleed on a near-opaque
  ground. A version that only cleared `#sess-body` still had the week
  chip and header showing through — that's a section of the hub, not a
  screen; don't regress to that.
  The gate is ONE early bail at the top of renderHub (`skillPts > 0 &&
  !agendaLocked` → renderSelect) — every entry point (boot auto-open,
  Session tab, HUD timeline, turn chip) already funnels through
  renderHub, so don't add per-entry checks; don't remove the bail
  thinking it's redundant, it IS the whole flow. Card bumps re-render
  the select screen preserving scrollTop. The compact `.sk-sheet` now
  lives on the Instincts toolbar tab (see the 2026-08-15 bullets
  below), not on the weekly hub.
  Glyphs are inline SVG, duotone: body in the pole color via
  currentColor, ONE gold #f2c14e accent each (the trend line, the
  maze's goal dot, the root-tip leader nodes). No faces, same as the
  banners. Policy Brain also carries a faint currentColor BRAIN outline
  behind the bars (`.g-brain`, opacity ~.18) — the thought under the
  numbers; keep it an outline, never solid, or it becomes the subject.
  **The glyphs are ALIVE on the select screen** (2026-08-15, user's
  call): each moving part carries a `g-*` class and loops via CSS
  scoped to `.skc-art` (GLYPH renders nowhere else). One motion per
  glyph, slow — six cards run at once, so anything fast is a slot
  machine. Brain pulses / bars breathe / trend line & maze redraw
  (`gl-redraw`) / rays glint / typing dots bounce / sound arcs push /
  roots regrow, nodes glint. Rules that must survive edits:
  - **Draw-loop strokes carry `pathLength="100"`** so the one shared
    `stroke-dasharray: 100` fits every path; a new drawn part needs the
    attribute or its dash math is garbage.
  - **Keyframe 0% is the resting DRAWN state** and stagger uses
    NEGATIVE delays — a hidden document freezes the animation clock at
    currentTime 0, and a loop that opens on "invisible" screenshots as
    a missing limb. Redraw loops retract-then-redraw (never cut) so 0%
    and 100% are the same frame and the loop is seamless.
  - **Hold ≫ transition** in `gl-redraw`/`gl-root` (~68%/62% hold): at
    45% transition the Procedure card looked half-built half the time,
    because the maze IS that card's whole drawing.
  - **`gl-wave` animates transform only** — the middle arc carries its
    own `opacity` attribute for depth, and a CSS opacity animation
    would override the attribute and flatten it.
  - Reduced motion: one `.skc-art svg *` line in the media block kills
    all of it; resting attribute states are the complete drawing.
  - The pane screenshots these at random phases (fronting restarts the
    clock) — verify with `getAnimations()` + sampled `dashoffset`, not
    by eye.
  **The cards DEAL from a center stack on entrance** (2026-08-15,
  user's call — `.skc-grid.deal` in CSS, added in `renderSelect`).
  Rules that must survive edits:
  - **Entrance vs re-render is decided by what was on stage BEFORE the
    render**: `entering = !body.querySelector(".skc-grid")`. Boot, the
    hub funnel and the ag-skills back plate arrive with no grid and
    deal; a bump/drop/reset rebuilds an existing grid and must NOT —
    replaying the deal on every + press is unbearable. Don't replace
    this with a call-site flag; every caller already routes through
    renderSelect and the DOM check can't drift out of sync.
  - **`both` fill + positive delays IS the stack**: every card holds
    its gathered from-state until its turn to fly (that's the deck),
    first card z-highest. The per-seat from-state is a `--deal-from`
    custom property read by one shared keyframe, so the 640px 2-column
    grid only re-aims the travel instead of redeclaring the animation.
  - The class is stripped on a wall clock (`DEAL_MS`, must stay above
    max delay .35s + duration .55s) — frozen-clock rule; a hidden tab
    would otherwise hold the hand stacked forever.
  - The deal rules sit AFTER the corridor block in the stylesheet ON
    PURPOSE: same elements as `cr-rise`, and the deal must win the
    cascade when the screen arrives via screenSwap.
  - Timer-based probes in the pane RACE (hidden-tab setTimeout clamps
    to ~1s) — verify the deal with a MutationObserver on `#sess-body`,
    which is not throttled.
  Layout is a FIXED 3-column grid (`repeat(3, 1fr)`, 2 under 640px),
  not `auto-fill` — the screen is full-bleed now, so a viewport-tracked
  column count gave a ragged 5+1 on a wide monitor instead of the
  intended 3+3 (one row per pole, wonk over organizer). The `--pole`
  fallback must live on `.skc-grid`, not `.skc` (equal specificity
  with `.p-*`, so a default on the card wins by source order and
  paints every card gold — same trap documented at `.sk-sheet`). Every
  `.skc` needs `min-width: 0` — grid items default to auto-sized by
  their content, and without it a long description forces its column
  past the track and overflows the grid horizontally; hit this once on
  a 375px phone. CONTINUE is `position: sticky; bottom: 0` inside the
  scrolling `#sess-body`, so a short viewport scrolls cards under a
  reachable button instead of pushing it off the fold. The whole card
  is a tap target, not just the + box.
  **The screen is fully REVERSIBLE (2026-08-15, user's call)** — it was
  a one-way ratchet, so a misclick meant living with it for a whole
  session. Three pieces, all in `skSelectHtml`/`renderSelect`:
  - **A `−` button (`.skdn`) beside the `+`**, floored at
    `skillStart.base` (never below where everyone starts), refunding the
    point. Its handler MUST `stopPropagation` — it is a child of the
    card, whose own pointerdown is +1, so without it lowering a skill
    instantly re-raises it. The wiring loop must NOT `continue` past a
    capped card the way the old one did (`if (!up || up.disabled)
    continue`) or `−` is dead exactly where it is most needed: on a
    maxed skill. Wire `−` and `+` independently.
  - **A rank word (`.skc-rank`) between the pole name and the value** —
    the level in plain language, because a bare "3" means nothing until
    you know the ladder runs to 6. Names live in session.json
    `skillStart.ranks`, INDEXED BY THE VALUE, with a fallback list in
    main.js for old data. The list must cover 0…`cap`. Content goes in
    the JSON, not the JS. **"Average" is the MIDDLE of the ladder, not
    the floor** (re-based 2026-08-15, user's call): 1 Very weak,
    2 Weak, 3 Average, 4 Good, 5 Great, 6 Formidable. Everyone starts
    at 1 and buys up; 5 and 6 are only reachable by honing. Keep both
    lists in step — a JSON edit alone leaves the JS fallback lying.
  - **A quiet `↺ Reset` plate** beside the point chip (`.sk-reset`,
    `#sk-reset`) — back to all-base, all points refunded. Disabled while
    nothing is spent so it never offers a no-op. Deliberately understated:
    CONTINUE is the only loud button on this screen.
  The hub's legacy `.sk-row` spend path (an old save with unspent points)
  still has no `−`; it shares neither markup nor CSS with these cards.
- **Skills are chosen at week 1 (Opening Day) and honed by doing**
  (`train()` in main.js): every action names the skill it exercises
  (session.json `trains`; the bill-push action exercises Procedure)
  and `skillStart.honeEvery` uses buy one pip, up to the cap. This is
  the only repeatable growth after week 1 — one-off event grants still
  ride `fx.skill`.
- **The six skills** (session.json `skills`, ids are stable, only
  `name`/`pole`/`desc` are display): Policy Brain (`fiscal` — id kept
  from its 2026-08-13 name to avoid touching every reference),
  Procedure, Educator (wonk); Talk Story, Mobilizing, Base Building
  (organizer). **Bridge pole is now empty (0)** — Rhetoric was cut
  2026-08-14 into Talk Story's organizer slot, then Whip Count was
  retired the same day and its chair-odds intel gate (`intel.odds`)
  folded into Talk Story too, at the same thresholds (band=3/exact=5).
  Talk Story now single-handedly carries the "reading a person" remit
  Bridge used to split across two skills — its own description folds
  in Whip Count's ("who's really with you"). `poles.bridge` stays
  defined in session.json but unused; `renderHub` already skips empty
  poles so nothing renders a dead column. Pole split is 3/3/0, not the
  old clean 2/2/2. Any dialogue `check.skill` or `voices[].t` that
  points at a dead skill id silently disappears (`voiceHtml` no-ops on
  an unknown id) — repoint, don't delete.
- **Mobilizing vs Base Building is load-bearing, not flavor**
  (split out of Grassroots 2026-08-14, the McAlevey distinction).
  Mobilizing activates the already-convinced — spiky, breadth; it
  scales and is trained by the rally, and carries the `ev-testimony`
  pack-the-room check. Base Building grows the coalition and develops
  leaders — slow, durability; it carries the Grange on-the-record dare
  and is trained by **Build the bench**, the deliberately unglamorous
  action whose immediate support tick is the smallest in the game ON
  PURPOSE (its payoff is the endgame, not the week). Never re-merge
  them, and never raise bench's effect to match the rally's — the
  whole teaching is that turnout and durability are bought separately.
- **The conference roll takes the BETTER of the two organizing halves**
  (`resolveBills`, the `conf` gate). It is automatic, the player never
  opts into it, and a miss halves the bill — so keying it on one half
  alone would drop a player who invested in the other from ~58% to
  ~17% through no fault of their own and quietly move the
  simulation-calibrated enact-rate bands. Conference is still ABOUT
  durability; that is why Base Building carries the Grange dare, which
  the player does choose.
- **Only 3 of 6 skills have an action that trains them** (rally →
  Mobilizing, bench → Base Building, lobby → Talk Story, plus the
  bill-push → Procedure). Policy Brain and Educator can only be bought
  at week 1 or granted by `fx.skill`. Known gap: the action roster, not
  the skill list, is the bottleneck.
- **The weekly intel report is skill-gated per FACET** (session.json
  `intel`, rendered by `intelHtml`): Talk Story prices the chairs
  (below `band` = hallway rumor whose band may be off by one, seeded
  per week+bill — wrong ON PURPOSE, don't "fix" the noise; at `band` =
  honest band; at `exact` = live % + chair disposition — this was Whip
  Count's job until it was retired 2026-08-14), Procedure reads the
  clock (deadline warnings before they're a week out), Policy Brain
  puts the measured hearing rate in print. The bill ledger's live odds
  are gated by the SAME Talk Story tiers (`bstatFor`) or intel is
  decorative — but the measured base rate in the row tooltip stays
  reachable by everyone, because it is public data.
- Every dialogue node, event and action carries `voices` — the SIX
  SKILLS chime in, colored by their pole (`voiceHtml` in main.js,
  `v.t` = a skill id from `data.skills`). Retired 2026-08-14: the
  PROGRESSIVE/CONSERVATIVE trait system (`data.traits`, `v-prog`/
  `v-cons` CSS) — it read as the player having a preassigned ideology
  rather than the player's own instincts arguing with each other. The
  Disco identity is now carried by skill voices alone.
- **A character with a `card` gets a PORTRAIT RAIL, attached to the
  window** (`charCardHtml` + `PORTRAIT` in main.js, `.sd-scene.has-card`
  in style.css; rebuilt 2026-08-18, user's call: "attach the portrait to
  the window the way Disco Elysium does it"). A tall 3:4 portrait flush
  against the panel's left frame, held for the whole conversation, with
  the transcript and the choices in a column beside it. It replaced a
  wide dossier plate pinned ABOVE the text, which made it a header — the
  eye cleared it once and never came back, so the character stopped
  being present the moment you started reading. Rules:
  - **THE PORTRAIT ARRIVES WITH THE PERSON AND NOT ONE BEAT EARLIER**
    (2026-08-18, user's call — "if there's an event beforehand, I don't
    want the portrait to show until the time is right"). Two halves:
    - `showCard` only fires on a node whose `speaker` IS that
      character, so a scene opening on narration (w2-kawaguchi waits in
      a breezeway before his door opens) shows no portrait at all. A
      node with no `speaker` leaves the card alone in BOTH directions —
      it does not raise one, and it does not drop the one that is up,
      because you are still standing in front of the same person while
      the prose describes the room.
    - **The beats already on screen move OUT of the rail's column**,
      into `.sd-pre` — a full-width row above the rail (grid row 1;
      the rail starts at row 2). Without this the whole scene reflowed
      the instant he appeared and the breezeway, text and banner both,
      ended up sitting beside his portrait retroactively. He was not
      there yet; the transcript must not say he was. Only the FIRST
      card in a scene splits; a later swap keeps the rail as-is.
    - Consequences to keep in step: `agePast()` must grey both boxes,
      `hush` must dim both, `.sd-pre:empty` collapses (the common case
      — most talks open with the character already speaking), and the
      `.sd-art` left-bleed kill is scoped to `> .sd-log` so a banner in
      `.sd-pre` still bleeds both ways. The rail's left bleed lives on
      `.sd-card`'s own negative margin and NOT on the scene's
      padding-left, or `.sd-pre`'s banner overflows the panel.
  - **Layout is CSS-only and gated to >=900px.** `showCard()` adds
    `has-card` to the SCENE (the grid has to be declared on the parent);
    narrow screens keep the horizontal plate, which is the right shape
    when there is no room for a column, so a rail change cannot break
    the phone. Scenes with no speaker card — most of them — are
    untouched by any of it.
  - **The rail is sticky at `top: 0`, so anything past the bottom of
    `#sess-body` is not below the fold, it is permanently invisible.**
    The column is 180px (portrait 240, whole rail ~430) because the body
    is only ~450px on a 1000x800 laptop. Widening it, or adding a field,
    means re-checking the rail's total height against the SHORTEST
    supported body — that is also why `.cc-note` is dropped here (the
    quote carries it, the same call the 560px breakpoint makes) and why
    `.cc-quote` is line-clamped.
  - **`.sd-art` gives up its LEFT bleed inside a rail scene.** The
    banner's `margin: 10px -18px` is written for a full-width column and
    otherwise walks under the portrait.
  - **A card may carry a `photo` instead of an `art` drawing**
    (2026-08-19, user's call: "replace the Kawaguchi headshot with the
    real one of him, but cropped"). `tools/make_portrait_art.py` cuts a
    3:4 crop out of the character's OWN banner photograph and gives it
    the banner treatment step for step (mild oil brush, grade, grain,
    vignette, adaptive palette) → `site/assets/portraits/<id>.png`;
    `charCardHtml`'s `portraitHtml` renders it as an `<img>` and
    `.cc-art.cc-photo` drops the drawing's gradient ground. Kawaguchi is
    the first. Rules:
    - It is a crop of the SAME source the banner is cut from, so the
      rail and the banner cannot drift into two different men. Never
      source a portrait from a second photograph.
    - **It is painted HARDER than the banner** — 6 @ 0.85 against the
      banner's 4 @ 0.55 (2026-08-19, user's call: "I want the face
      cards to have the painterly effect"). A banner is a whole room
      that heavy brushwork would eat; the portrait is one head at
      180px, where the brush is the only thing between "game art" and
      "photo pasted into the UI". 0.55 and 0.72 both still read as a
      filtered photograph at rail size. 0.85 is also the threshold
      where DITHERING TURNS OFF (and grain drops to 1), resolved from
      the strength exactly as `from_photo` does it and for the same
      reason — flat painted regions plus Floyd-Steinberg is noise for
      no gain.
    - **`--soften` here is a brush on the face, not a redaction.** The
      banner's face pass dissolves identity; this one is smaller
      relative to the face (radius 18 on a ~304px face, against the
      banner's 7 on a ~88px face) so the features read as painted, not
      erased. The rail portrait IS the identification — a dossier
      headshot with its face dissolved is a redaction.
    - The `art` key STAYS on a card that gains a `photo` — it is the
      fallback, and the drawing is still what any character without a
      photograph gets.
    - The portrait's own `?v=` (`PORTRAIT_V` in main.js) is by hand:
      the pre-commit hook only rewrites tokens inside HTML.
  - DRAWN PORTRAITS ARE FACELESS, as ever — the photo route above is a
    documented exception for a named external actor who already appears
    photographically in a banner, not a repeal. Bigger makes the rule
    HARDER:
    at 180px a plain circle-on-a-dome is the universal avatar icon. The
    drawing earns its size with a CHAIR BACK behind the shoulders (the
    single element that breaks the avatar read — do not remove it to
    "simplify"), an ellipse head and a drawn neck, two lit windows that
    motivate the rim light, and the desk CUTTING the figure. The rim is
    white at .34, not a tinted light: the silhouette is already a pale
    blue, and the first pass's #f4f1e8 at .2 was invisible at display
    size. Still ONE gold accent, still the nameplate.
- **Named dialogue speakers are the two EXTERNAL actors** — Kawaguchi
  (House money chair) and Grange (lobbyist), people the player
  negotiates or contends with — **plus the player's own two
  introducers**, Rep. X and Sen. X (see the introducers section below;
  a bill carries a member's name in the real world, so they are the one
  documented exception to the faceless-campaign rule). A further
  character, **Souza** (Senate money chair), is named but never speaks
  and has no talk slot: `w4-souza` is entirely his scheduler, his
  committee members and a closed door. That asymmetry is the content, not an omission — House
  money you can catch in a breezeway, Senate money you cannot — so do
  not "finish" him by adding a talk-souza. Both chairs are ALSO named
  in `chairs.json` (`h-fin`, `s-wam`, linked back by `char`); renaming
  one means renaming both files. The player's OWN campaign is
  deliberately faceless, per the same 2026-08-14 change that retired
  the traits: Nālani Chun ("your policy director") and Malia Reyes
  ("your field organizer") are gone from `characters`. A dialogue node
  with no `speaker` key renders as unattributed narration (`sd-narr`,
  same treatment as a choice's `reply` text) instead of a named
  character's line — that's how the campaign's own staff/coalition now
  "speaks": as narrative injection ("the coalition wants to know...",
  a note on a whiteboard), never as an individual. Their old weekly
  Talk-story slots survive as faceless entries keyed `office` (was
  `nalani`, dialogue `talk-office`, was `talk-nalani`) and `coalition`
  (was `malia`, dialogue `talk-coalition`, was `talk-malia`) — `office`
  covers procedural/status flavor, `coalition` covers turnout/base
  flavor. If a new event or talk needs a speaker, ask: is this an
  external actor (name it) or the player's own campaign (leave
  `speaker` unset)?
- **Event banner art** comes from `tools/make_event_art.py` →
  `site/assets/events/<id>.png` (1920x960), shown when a dialogue (or a
  single node) carries an `art` key. **Every shipped banner's exact
  build command lives in `data/raw/events/BANNERS.md` — add a line when
  you ship one.** The args are not recoverable from the PNG, and
  reconstructing them once (2026-08-18) cost a brute-force search over
  `--center` plus an analytic fit of the `--soften` ellipse against a
  diff map. TWO routes, and the first is the one to reach for:
  - **`--photo PATH` — a real photograph. THIS IS THE PRIMARY ROUTE.**
    Sources live in `data/raw/events/`. The pipeline letterboxes it,
    pulls it a few percent toward the overlay palette, and quantizes
    with dithering so it carries the same limited palette and grain as
    everything else. Procedural code can place geometry exactly but
    cannot PAINT; a photo brings real materials, real light and a real
    crowd for free. Getting the crowd to read cost four procedural
    passes and still lost to a photograph.
    - Workflow that produced w1-opening: photo of the real rotunda →
      an image model (Gemini) asked to **add** a motion-blurred crowd
      while changing nothing else → `--photo`. Ask for a narrow EDIT
      of a real photo, never a repaint: style words ("painterly",
      "Disco Elysium", "warm gold") make the model reinterpret the
      scene and invent things — it turned the wood doors yellow. Keep
      the prompt photographic ("documentary", "natural daylight") and
      let the game's look come from the quantize step, which is CODE
      and therefore identical across all ~20 banners.
    - `--center` picks the surviving band (a 4:3 source keeps only
      ~46% of its height at 2.9:1), `--grade` how far toward the
      palette. Keep `--grade` small: the point of a photo is realism,
      and pushing hard toward navy/gold just reinvents the
      stylisation that made the procedural version look wrong.
    - **`--paint RADIUS` gives a mild painterly finish** (needs
      `opencv-contrib-python-headless` — see README). It runs
      `cv2.xphoto.oilPainting`, but the brush radius has to be judged
      relative to the OUTPUT, not the source: a radius of 4–8 is
      invisible on a 2400px photo and only reads once applied at ~2x
      the 640-wide output and then resized down (`paintify()`).
    - **`--paint-strength` is the mildness dial, NOT radius.** Default
      0.55 with radius 4, which is the intended house look: strokes
      soften the image while photographic detail still shows through.
      Dropping the radius instead just makes the strokes small and
      busy, which reads as a noisy photo rather than a gentle painting.
      Full strength at radius 8 flattens everything into poster paint —
      it was tried and is far too extreme for this.
    - **`--soften X0,Y0,X1,Y1` for a named character's FACE.** Four
      fractions of the SOURCE photo (mapped through the crop in code,
      so it survives a later `--center` change). It gives that ellipse
      a heavier pass of the SAME brush, feathered in. Reach for it when
      the "no faces in focus" rule can't be met by turning the
      character away — Kawaguchi has to be looking at the player.
      Do NOT blur instead: blur reads as a redaction bar and eats the
      head/shoulder silhouette, the same failure the w1 crowd hit.
      `--soften-strength` must stay BELOW 1 (default 0.6): composited
      at full opacity the brush doesn't soften the features, it deletes
      them, and a blank oval is more uncanny than the sharp face was.
      Radius 6 @ 0.65 over the face INTERIOR (brow to chin, inside the
      hairline — not the head outline) is the worked example, on
      `w2-finance-office`.
    - **A flat, discoloured PATCH in the source gets repaired in the
      source, never chased downstream** (`tools/depatch_photo.py`;
      recipe and the raw original in BANNERS.md). The office photo
      carried a low-chroma oval on the wall that the 96-colour palette
      turned into a grey splotch — 160 and 220 colours and every
      quantizer PIL has still showed it, because the patch was really
      in the photograph.
    - **A near-monochrome photo needs `--colors 96`, not the 32
      default.** An adaptive 32-colour palette on a room that is 90%
      brown wood spends every entry on browns, so smooth wall gradients
      posterize into blotches that read as artifacts, and the one
      saturated object in frame (an aloha shirt) goes grey. Both w2
      banners ship at 96. 32 is only right for a photo whose colours
      are already spread out.
    - A FULLY painted image (strength ≥ 0.85) has flat colour regions
      that dithering would muddy back toward "filtered photo", so it
      switches to no-dither + a 96-colour palette. A mild blend still
      has photographic gradients that NEED dithering to survive a small
      palette, so it keeps the normal 32-colour `COLORS` + dither.
      That is why grade/colors/dither/noise all default to `None` in
      `from_photo` and resolve from the strength rather than sharing
      one constant.
  - **Three numbers decide whether a banner is SEEN, and they are
    coupled** (all three re-set 2026-08-18, from "the images in the
    narrative are very short, too short"). Change one and re-derive the
    others; changing one alone is why the previous settings drifted
    into a thin, soft, mostly-scrolled-away strip:
    1. **Ratio — `W, H` in make_event_art.py, now 2:1 (was 2.9:1).**
       Sets how much of a PHOTOGRAPH survives the letterbox: a 4:3
       source keeps 46% of its height at 2.9:1 and 67% at 2:1. This is
       the "how much of the picture exists at all" dial.
    2. **Resolution — `DISPLAY`, now 6 (1920 wide; was 4 / 1280 and
       3 / 960 on 2026-08-28, 2 / 640 before that).** The column is ~986px at the session panel's
       1040px width, so 640 was being upscaled 1.54x by the browser and
       reading soft. **MEASURE `.sd-art`'s rendered width in DEVICE
       PIXELS, not CSS pixels** — that is the correction of 2026-08-28,
       and 960 was chosen under the mistake: it matched the column to
       ~3% in CSS px, but an `<img>` rasterises into device px, so on a
       dpr-2 display the "matched" file was upscaled 2.05x and read
       exactly as soft as the 640 it replaced. (Same unit error as the
       game canvas, fixed the same day — see the DPR section below.) It
       also undercut the DITHER, which only reads as grain at 1:1.
       **DISPLAY ALONE IS A LIE ABOVE THE PIPELINE'S OWN RESOLUTION.**
       The procedural route draws at `W * S` and the photo route
       brushes at `PAINT_W`; ship past either and you are handing the
       browser more pixels without more picture. So 1920 was reached by
       moving all three together — DISPLAY 6, S 12, PAINT_W 1920.
       - **`S` IS AN ANTI-ALIASING BUDGET AND MUST STAY ABOVE
         DISPLAY.** `S / DISPLAY` IS the downsample ratio, so at
         `S == DISPLAY` the resize is a no-op and the procedural route
         ships raw aliased polygons. That is exactly what happened,
         unnoticed, in the intermediate DISPLAY 4 state where it met
         S = 4; no shipped banner regressed only because all three take
         the --photo route, whose AA comes from downsampling a 2816px
         source. Keep `S >= 2 * DISPLAY` (now 12 vs 6).
       - **RAISING `PAINT_W` RESCALES EVERY RECORDED RADIUS, and that
         is the whole cost of this change.** A radius is only meaningful
         against the width the brush runs at, so holding the brush at
         the same DISPLAY size means scaling every recipe by
         1920/1280 = 1.5: `--paint 4` -> 6, `--soften-radius 7` -> 11.
         Strengths are unitless and did not move. **Measured, not
         assumed**: with the dither blurred away (it is per-pixel noise
         added AFTER the brush, so it contaminates any raw gradient
         measure), the rescaled bake's structure function tracks the
         old one to within 1% at every lag from 2 to 32 px, while a
         1920 bake left at `--paint 4` runs 7-8% higher at short lags —
         a visibly finer, busier brush. Re-run that comparison if
         PAINT_W moves again; eyeballing will not catch it.
       Net on a 1280px window the browser upscale went **1.74x -> 1.30x
       -> 1.04x**; `PAINT_W` stays deliberately NOT tied to DISPLAY, so
       an output-size change on its own still needs no recipe edits.
    3. **On-screen height — `.sd-art { max-height }` in style.css, now
       `min(43vh - 119px, 271px)`.** The odd expression is the point:
       the banner competes with the TRANSCRIPT, not the window, and
       #sess-body is `min(86vh, 780px) - ~238px` of header. A flat vh
       was two different things at two window sizes — too small on a
       laptop, 80% of the body on a big monitor.
    …and a fourth thing that is not a number: **settle() was scrolling
    every freshly-arrived banner off the top**, because `offsetTop` in
    this panel is relative to `.ovl-panel` (the nearest positioned
    ancestor) while `scrollTop` is measured from `#sess-body` — every
    beat was scrolled ~191px too far. It now reads positions off
    getBoundingClientRect, holds ~2/3 of a new banner on screen, and
    yields that to a `PEEK` of the choice strip on a short window so a
    scene never opens as a picture with no visible options. It also
    re-settles once on the image's `load`: a not-yet-decoded `<img>`
    measures 0 tall, so on a COLD load every scroll sum was computed
    against a banner that was not there yet. That last one is why this
    looked fine while clicking around with a warm cache.
  - **`--scene <id>` — procedural.** For subjects with no usable
    photograph. Full control of composition, no painterly rendering.
    `opening_day` is the worked example; the notes below are what it
    cost to learn.
  - **Work from a reference either way.** Invented compositions failed
    three times (a flat balcony elevation that read as a motel; a
    one-point shaft that read as a bullseye; an exterior-at-dawn that
    was a perfectly nice picture of the wrong thing).
  - **Value separation carries a procedural scene, not
    draughtsmanship** — the repeated LIGHT rail / DARK recess
    alternation plus shaded side walls against a lit far wall. Detail
    beyond that turns to noise.
  - **Disco Elysium's lighting logic, not its brushwork** — one
    motivated source, deep shadow, coloured bounce. Oil-paint texture
    does not survive translation to pixels; directional light does.
    Palette is locked to the overlay's own tokens.
  - **Crowds are the hard part, and three things make them read.**
    Cost several passes to find, so don't undo them casually:
    1. **Resolution.** At true architectural scale a person is half a
       storey. Showing a whole four-storey courtyard at 320px puts
       them at ~12px with a 2px head — unreadable at any shading. So
       banners resolve to 640 natively, and a crowded scene CROPS
       CLOSER than its reference (three bands, not five).
    2. **Draw order.** Railings are repainted OVER the crowd layer, so
       what survives is heads and torsos above a rail. That reads as a
       person instantly; a whole tiny free-standing body reads as a
       bottle, and a rail lined with them reads as a shelf of bottles.
    3. **Silhouette.** Head ~45% of shoulder width, tapering to the
       legs, nearer 1:3 than 1:2. A wide blob with a bulb on top is a
       bowling pin. Jitter size and footing per figure; a level row of
       identical ones is the other half of the shelf problem.
    Blur is only a whisker (~0.16x supersample). "Vague" has to come
    from anonymity, not smearing — at this size blur destroys the
    head/shoulder separation doing all the work. Also: figures in an
    open light well are lit from ABOVE, so heads and shoulders must
    catch light; dark figures on dark recesses are invisible.
  - **Brightness.** The reference is a bright daylit space. It is easy
    to stack directional shading + a downward gradient + edge grading
    + the `finish()` vignette until the whole thing reads as a
    dungeon. They compound — tune them together, not one at a time.
  - Frame edges are graded down (`side_g`) so the near ends of the
    side walls, which perspective makes enormous, don't outweigh the
    centre.
  - **Designed at 320x160, SHIPPED at 1280x640.** Resolving natively
    (rather than rendering 320 and upscaling) is what lets a figure
    exist at all — see the crowd note above. `.sd-art` deliberately
    does NOT set `image-rendering: pixelated`: the file is resampled
    to fit the column, and pixelated turns a resample into dropped
    rows where the default filter just softens them. Don't "fix"
    either half alone. (The old form of this bullet said 640x220 from
    a 320x110 design and called the resample "about a percent" — all
    three numbers were stale by 2026-08-28; the ratio went 2:1 on
    08-18 and DISPLAY has moved twice since.)
  - **`.sd-art` clamps to `max-height: 32vh` with `object-fit: cover`.**
    Clamping against the viewport (rather than shipping a shorter file)
    lets a tall window show the whole composition and a short one crop
    to the middle. 32vh is a balance point worth not nudging blind: the
    banner is ~219px tall in a 615px column, so it shows UNCROPPED from
    about 700px of viewport upward and only trims below that. 26vh
    cropped even tall windows and read as a squat letterbox; 38vh
    stopped clamping at all and pushed the dialogue clean off the panel
    on short ones.
  - The `art` id is slug-filtered in `showDialogue`, not `esc()`'d —
    `esc()` leaves quotes alone, which is fine for text but would
    break out of an attribute.
- Revenue effects (`revenueK`, $ thousands/yr) flow into the budget
  scoreboard via `PolicyPanel.setExternal(S.metrics.revenueK)` — call
  it after EVERY metric change and once on boot, or the chip drifts.
- **Talk story and actions are OPENINGS the week's event grants — NOT
  a weekly allowance** (changed 2026-08-15, user's call). Nothing is
  owed to the player: an unplayed event means a hub with no talk rows
  and no action rows at all. An event dialogue carries
  `unlocks: {talks: {charId: dialogueId}, actions: [actionId]}`, applied
  once when the event completes (`runEvent` → `grantUnlocks`); a
  CHOICE may also carry `effects.unlock` in the same shape, so how a
  scene goes decides which doors open. Action id `"push"` opens the
  work-the-chair rows. A calendar entry may still hard-wire `talks` /
  `actions` for a scripted week, merged on top of the event's grants.
  Rules that must survive edits:
  - `S.unlocks` is `{week, talks, actions}` and is PER-WEEK — a stale
    `week` reads as nothing open, so advancing the turn closes every
    door automatically. Don't add a "carry over unused openings" path;
    an opening expiring is the mechanic.
  - `data.talkDefaults` is GONE, and `calFor` no longer falls back to
    it. Week 1's old calendar `talks` moved into `w1-opening.unlocks`.
  - Every generic event must grant SOMETHING or its week is dead air.
    `renderHub` prints an explicit "the week didn't open any doors"
    caption when an event grants nothing, so a bare week reads as a
    closed building rather than a broken render.
  - The ONE-action-per-week cap still applies on top
    (`S.actionWeek === S.week`); openings decide WHICH moves exist,
    the cap decides how many you spend.
  **RESTARTING lands on the creation funnel, exactly like boot.** The
  footer's "Restart session" used to call `runEvent()` directly, which
  walked straight past SELECT INSTINCTS and the bill package into week
  1's narrative with a default character nobody chose (fixed
  2026-08-19, user's call). It now mirrors boot's branch — `renderHub()`
  when the week's calendar carries `agenda` and it isn't locked, else
  `runEvent()` — so the two doors into a fresh campaign cannot drift.
  Per the funnel rule, that is a call to renderHub and NOT a test for
  the screens themselves; its early bail owns that decision.
  There is no week 0 — the session starts at week 1 (Opening Day),
  whose calendar entry carries `agenda: true` so the same turn also
  locks the bill agenda (`S.agendaLocked`) that lined-up members
  will introduce.
- **MODULE 1 IS A REVENUE GAME** (2026-08-19, user's call: "the initial
  investment priorities determine how much revenue you have to make up,
  but the bill process is centered on taxes"). The priorities are a
  COMMITMENT, not legislation: picking them sets the price the campaign
  has to cover and they never enter the gauntlet. `startBills` skips
  anything whose `kind` is not `gain`, so only revenue measures are
  carried, heard, diluted and killed. The session therefore asks ONE
  question — can you raise what you promised — and every chair,
  deadline and roll is about a tax measure, which is the half of the
  building this module actually teaches.
  - **`targetK()` and `raisedK()` are DERIVED, never stored.**
    `S.agenda` already holds every pick and `S.bills` every outcome; a
    stored target would be a third copy free to drift from both.
  - **`gapHtml()` is the scoreboard** and sits at the TOP of the ledger
    (and of the pre-ledger restatement), because it is the session's
    whole question. It reads honestly at both ends: nothing enacted
    says so rather than showing a 0% bar, and overshooting says
    "raised more than you promised" instead of clamping to 100%.
  - **Locking needs BOTH halves** — at least one tax bill (or there is
    no campaign) and at least one priority (or there is nothing the
    money is FOR). The no-priority message names step 1 explicitly
    (`◂ Choose a priority…`), the one case where the button you are
    looking at is blocked by a screen behind you.
  - **Known consequence: the credit-vs-wealth teaching is currently
    unreachable in play.** The design doc's calibration says a tax
    CREDIT passes ~1.5x as often as a wealth tax, but both
    `credit`-tagged measures (`ctc`, `retitc`) are PRIORITIES now, so
    the only families that reach a committee are `wealth` (conveyance,
    capgains) and `income` (wwcr). The credit cells in
    hearing_rates.json are measured data and stay; restoring the
    comparison means adding a credit-tagged REVENUE measure to
    policies.json, the same way the `get` family sat dormant after
    get-half was removed.
- **Creation is a TWO-screen funnel** (2026-08-15): SELECT INSTINCTS
  (`renderSelect`) then the bill package (`renderAgendaSelect`) — both
  full-bleed `.creating` screens in the same archetype-screen language
  (stencil title plate, glyph cards, one `.sk-begin` plate out). The
  hub NEVER shows an agenda picker any more. The gate is the single
  early bail at the top of renderHub (`!agendaLocked` → skillPts > 0 ?
  select : agenda); every entry point funnels through renderHub, so
  don't add per-entry checks. Agenda cards color by direction: raise =
  gold, invest = green (`.agc` `--pc`), glyphs from SYM by policy id.
  - **The package screen is itself TWO STEPS** (same day, user's call):
    step 1 "Choose your priorities" (policies.json `priorities` — ufsm,
    ctc, retitc), step 2 "Choose how to pay" (`revenue`), with a
    numbered step rail (`.ag-rail`, clickable), the policy's `who` case
    ON the card in the reader serif (`.agc-desc` — tooltips don't exist
    on touch), a sticky running tally of picks (`.ag-tally`) and a
    back/forward nav plate. **There is NO CAP on either step**
    (2026-08-19, user's call: "allow users to choose as many investment
    priorities as they want, same for the tax options"). It was ≤3
    SHARED across both steps, so step 2 could open with the budget
    already spent — that scarcity was carrying the module's argument,
    and the argument now has to come from the tally and the gauntlet
    instead: take all six and you watch six bills go through the money
    committees and find out what that costs in weeks and support. The
    floor stays (at least one bill, or there is no campaign), and if a
    cap ever returns it must still be SHARED across the steps rather
    than one per step. NB the simulation-calibrated enact-rate bands in
    the design doc were run against a 3-bill agenda: per-bill odds are
    untouched by this, but a 6-bill package naturally enacts more in
    absolute terms.
    `agendaStep` is view state, deliberately NOT in S: a reload lands
    on step 1 with picks intact rather than resuming a half-wizard.
    The mobile `.agc-art` flattening MUST stay after the base rule —
    a media query adds no specificity, and a copy placed earlier in
    the file silently lost on source order (found live 2026-08-15).
  - **The funnel is a CORRIDOR and it runs BOTH WAYS** (2026-08-15,
    user's call). Step 1's nav slot carries `#ag-skills` ("◂ Instincts")
    where step 2 carries `#ag-back` ("◂ Priorities"), so there is always
    a way back out — before this, the instinct picks were unreachable
    the moment you pressed Continue. `#ag-skills` calls `renderSelect`
    DIRECTLY, not through `renderHub`, whose bail would bounce straight
    back to the agenda (skillPts is 0 by then).
  - **Moving between creation screens SLIDES** (`screenSwap` in
    main.js, `.cr-*` keyframes in CSS). Four things must not regress:
    - **Only navigation calls `screenSwap`.** A skill bump or a policy
      pick re-renders by calling `renderSelect()`/`renderAgendaSelect()`
      directly. Putting the animation inside the renderers would replay
      a ~470ms slide on every `+` press.
    - **The classes go on `#sess-body`'s CHILDREN, never the scroller.**
      Both renderers do `body.innerHTML = …`, which throws the children
      away — so a class cannot survive into the next render and re-fire.
      A class on the scroller itself would, and would need cleanup.
    - **Strip `cr-in-*` before adding `cr-out-*`.** `swapping` only
      guards the outgoing half, so a quick second click arrives with the
      in-class still on; the in-rules sit LATER in the stylesheet and
      would win the `animation` shorthand, sliding the screen in again
      instead of out.
    - **The arrival is force-landed on a wall clock** (`CR_LAND`), same
      reason as `countTo`: a hidden document FREEZES the animation clock
      (playState "running", currentTime stuck at 0) and `both` fill
      would hold the screen at its `from` keyframe — opacity 0. Click
      Continue, switch tabs, come back to a blank screen. `CR_LAND` must
      stay above the longest card stagger + duration (.25s + .38s).
      This is also why the Browser pane can't verify the motion itself:
      `document.hidden` is true there, so assert on the classes and on
      the landed state instead.
  - `retitc` (renewable energy credit expansion) is a MODELED number
    (~$42M/yr, storage add-on + refundability), not a fiscal note —
    its `src` says so; replace when a real note exists. Tagged
    `credit`, so it rides the tax-credit hearing-rate cell.
  - **`get-half` (raise the GET by half a point) was REMOVED**
    2026-08-15 (user's call) — from policies.json and from the game.
    No bill uses the `get` tax family now; `chairs.json`
    `gate.familyTilt.get` and the `get` cells in hearing_rates.json
    stay (they are the measured/editorial tables, not a bill list) and
    the `cart` drawing stays in `SYM`, so a GET measure can come back
    without rebuilding any of it. Unknown enacted ids are already
    dropped on load and `startBills` skips unknown agenda ids, so an
    in-flight save keeps a get-half bill it already introduced.
- **The instincts sheet is NOT on the week hub** (2026-08-15, user's
  call): it has its own toolbar tab (`#tb-instincts` → `renderSheet`,
  toggling via `body.dataset.view === "sheet"`), and the hub only shows
  the sheet when points are actually spendable (an old save with
  unspent points). The "The Advocate" identity card was removed from
  the hub the same day (`data.identity` is now only used by the footer
  copy). During creation, tb-instincts routes back through renderHub so
  the funnel stays the only door.
- **Custom symbols, not stock emoji** (2026-08-15): `SYM`/`sym(id)` at
  the top of main.js is a monoline 24×24 inline-SVG set drawn in
  `currentColor`, so a glyph takes the color of the row, pole or metric
  it sits in (`.sym` in CSS sizes it off the font). Skills, characters,
  actions, policies (keyed by policy id), metrics and the HUD all route
  through it; the `icon` keys still in session.json / policies.json are
  only the fallback for anything unmapped. Add new drawings to `SYM` —
  never paste an emoji into main.js.
- The weekly overlay auto-pops only while the week's narrative is
  unplayed; generic weeks cycle `genericEvents` by `(week-2) % n`.
  **Pinning does NOT shift the cycle** — the index is a pure function
  of `w`, so pinning a week simply DROPS the generic that would have
  landed there; it still appears wherever else the modulo puts it.
  (An older note here claimed pinning shifts. It does not, and never
  did in `calFor`.) Adding or removing a generic re-derives everything.
  As of 2026-08-19 weeks 1–6, 8, 11, 13, 15 and 16 are scripted, which
  leaves five generic weeks — 7, 9, 10, 12, 14 — against six generics,
  so **exactly one always sits out**. Which one is decided entirely by
  the ORDER of `genericEvents`: those weeks take indices 5, 1, 2, 4, 0,
  so index 3 never plays, and `ev-potluck` is parked there deliberately
  (lightest scene, only one not tied to the module's argument).
  **Re-derive that list after pinning or unpinning any week** — the
  failure is silent, and before the 2026-08-19 pass the back half of
  the session was five verbatim reruns of weeks 5–9.
- **`pre` runs a scene BEFORE the week's own event** (calendar `pre`,
  tracked in `S.preDone`, NOT `S.eventDone`). The two lists are separate
  on purpose: the player can close the panel between the two scenes, and
  marking them together replays the first every time they reopen it.
  `eventPending(cal)` is the one predicate that asks about the pair, and
  every gate that decides whether to pop the panel must call it rather
  than testing `cal.event` — there are five such gates.
- **A calendar entry is not automatically a milestone.** `milestone:
  false` keeps it off both timeline strips (`milestones()` filters for
  both `renderTimeline` and `renderProgress`) so an entry can carry week
  data — a `pre`, a recess flag — without claiming a tick. The 940px
  inner width is what stops labels colliding and it is already carrying
  twelve; week 7 uses this.
- **THE MANDATORY RECESS IS WEEK 6** (Const. art. III, sec. 10: at least
  five days, somewhere between the 20th and 40th legislative day, with
  the dates fixed by concurrent resolution, not the constitution).
  Anchored to real practice — the 2025 session opened Jan 15 and
  recessed Feb 20–26, which against `sessionStart` 2027-01-20 is exactly
  this week. Three rules:
  - The calendar entry carries `recess: true`, and `resolveBills` skips
    **every** gate that week except `auto`. A chair-only skip fires on
    NOTHING — by week 6 anything that cleared House Finance (deadline 5)
    is at `h-floor`, a `floor` gate, and anything still at `h-fin` is
    already dead — so the recess would cost the player nothing at all.
    This was written wrong once; don't rewrite it that way.
  - **No deadline moves to compensate, and `window` must never be
    extended.** `window` is fixed at `deadline - enteredWeek + 1` when
    the bill enters the stage, so a skipped week is simply one draw the
    bill never gets. That IS the lesson; "fixing" it deletes the week.
  - It is NOT `noAction`. Sine Die's flag closes everything; the recess
    closes the CAPITOL and leaves the district open, which falls out of
    `unlocks` for free — `w6-recess` grants `rally`/`bench` and
    withholds `push`, and opens no chair's door. The building being
    empty is the content.
  "Floor Votes" slid from week 6 to week 7 to make room, and
  "Crossover Eve" was dropped (it and "First Crossover" named one beat).
- **A single event can move the FY2027 bottom line.** `w7-storm` (a Kona
  low, pinned as week 7's `pre`) books −$600,000K of state disaster
  share through the ordinary `revenueK` channel, ~15× `ev-emergency`'s
  clinic rescue. It kills no bill — it re-prices the session by moving
  the number the campaign has to cover. `applyFx` therefore calls
  `syncScore()`, NOT `setExternal(revenueK)`: the bare form dropped every
  enacted bill's contribution off the chip until the next `resolveBills`
  put it back, which is survivable at ±$4M and not at $600M.
- **The scripted opening is weeks 1–5, and it is a chain.** Opening Day
  (the caucus; `kawaguchi-date` is available here too, via the optional
  `talk-kawaguchi` → `w1-kawaguchi` talk) → **week 2 `w2-yamamoto`, the
  courtesy call with the co-chair** (`yamamoto-open` — 2026-08-19, user's
  call: the week-2 meeting belongs to Yamamoto, not Kawaguchi) →
  **week 3 `w3-federal`, the HR1 safety-net briefing** → week 4 failing
  to reach Souza (`w4-souza`), where `yamamoto-open` is worth +3 on the
  hallway roll (58% → 92% at the same skills) → **week 5 `w5-decking`,
  THE KAWAGUCHI MEETING**, moved here from week 2 on 2026-08-19 so it
  lands on decking day itself rather than three weeks before anything is
  at stake; sets `souza-intro`, spent in `w8-crossover` and `w11-wam`.
  Flags are the only cross-week memory the engine has — there is no
  node-level `req`/`if`, so a past choice can change a later scene ONLY
  as a `{"from": "flag"}` check mod. Write for that.
  **Don't let `souza-intro` and `yamamoto-open` collapse into each
  other.** They look like the same mechanic (a flag from an early
  meeting, worth +2/+3 on a later red check) because they ARE the same
  shape, deliberately — but they run on different clocks: `yamamoto-open`
  is set at week 2 and spent at week 4; `souza-intro` is set at week 5
  and spent at weeks 8 and 11. Wiring either one to the wrong week's
  check makes that week roll a flag that cannot exist yet, which is
  exactly the bug this note exists to prevent re-introducing.
- **The player's own bills are not heard until week 5** (`h-fin`
  deadline in chairs.json) — nothing in weeks 1–4 may be written as
  though a hearing on them has happened or been scheduled, other than
  the February 14th date Kawaguchi may name in w1.
- **Real calendar dates**: `data.sessionStart` (session.json, the 3rd
  Wednesday in January) anchors week 1; `dateRangeFor(w)` in main.js
  derives every other week's date range by +7 days, no per-week dates
  stored. A mini timeline (`renderTimeline`, `#sess-timeline`) plots
  `data.calendar`'s milestones (First Lateral, Crossover, Conference,
  Sine Die…) across the session and marks the current week — keep
  `data.calendar` as the single source of both the intel/deadline copy
  and the timeline's waypoints, don't fork a second milestone list.
  **The strip is now BEHIND A TAP, and a compact progress bar rides the
  panel's top band beside the week plate** (2026-08-19, user's call:
  "move the timeline to the top of the event card, to the right of the
  week indicator"). `#sess-progress` — same renderer and same CSS as the
  HUD chip, see the shared-bar note below — sits at the top right of the
  panel; tapping it toggles `.tl-open` on `#session-overlay`, which
  displays the full `#sess-timeline` strip underneath. Rules:
  - **The bar is ABSOLUTELY positioned against `.ovl-panel`, not laid
    out in a flex row with the plate.** The plate's width is a function
    of the week's TITLE (measured: 303px on "First Hearings", 363px on
    "Money Committee Week"), so a bar taking the remaining slack would
    re-space its milestone ticks every week, and one pinned to the
    narrowest case would waste ~60px on most weeks. Anchored to the
    panel's right edge it is the same object every week and clears both
    the plate and the close button. Under 760px there is no room beside
    the plate at all and it becomes an ordinary first row of
    `#sess-head` — with an explicit `width: 100%`, because a `<button>`
    is inline-block and `auto` collapses the flex track to nothing
    (seen live).
  - **It lives INSIDE `#sess-head`** so `.creating` hides it for free
    with the rest of the session chrome, and so it costs no vertical
    space: it rides the same 30px band the head already reserves for
    the out-of-flow plate. With the strip closed, the head went from
    134px to 43px — ~91px handed back to the transcript.
  - **`centerTimeline`'s hidden-box bail is now load-bearing on every
    closed render**, not just on boot: a `display:none` scroll box
    reports clientWidth 0. The toggle must re-run it on open (it does,
    on a rAF) or the strip opens parked at scrollLeft 0 instead of on
    the current week.
  - The 1040px panel width and the strip's fixed 940px inner both STAY.
    They are what make all eleven milestones legible when it is open;
    the tap changed when you see the strip, not how wide it needs to be.
  - The toggle's pointerdown must `stopPropagation`, same as the
    milestone buttons — the overlay's backdrop handler would otherwise
    read the tap as a click-outside and close the panel.
  **ONE renderer and ONE stylesheet block serve BOTH progress bars** —
  `renderProgress(el, verb)` in main.js (the HUD chip is
  `renderHudTimeline`, a one-line wrapper) and the `.htl` class in CSS.
  They are two readings of the same calendar; a second copy of that
  arithmetic or those internals is a second chance for them to
  disagree. Only the CHROME differs (the HUD chip is a plate on the map;
  the panel's bar is quiet, no border, .72 opacity, because the gold
  masthead two inches away is already the loud object in that corner)
  and the chrome lives entirely in the stylesheet.
  Rebuilt 2026-08-15; four things must not regress:
  - **The session panel is WIDER than the other overlays on purpose**
    (`#session-overlay .ovl-panel`, 1040px vs the shared 680px). The
    strip is a fixed 940px — that width is what keeps twelve milestone
    labels from colliding (measured again after the recess was added
    2026-08-19: no overlap on either row) — so at 680px only ~634px of it was ever on
    screen and everything past Second Lateral sat in scroll the player
    had no reason to know existed. 1040 − 40px panel padding − 32px
    strip inset clears 940, so a normal window shows Opening Day
    through Sine Die at once. Narrow windows fall back to scrolling,
    which is why the 940px floor and the centering logic both stay.
    The strip also needs its horizontal inset: the first and last dots
    sit at 0% and 100% and are translated −50%, so their labels
    overhang the track and "Opening Day" gets shaved without it.
  - Structure is a scrolling strip (`.stl-scroll`, fixed 940px inner)
    and nothing else. **The readout line (`.stl-read`, "Opening Day /
    Week 1 · Jan 20–26, 2027 · this week") was removed 2026-08-15**
    (user's call) to give the dialogue back its vertical space — the
    masthead above already names the current week and its dates, so the
    readout was a second answer to a question already answered. The
    labels ARE the readout now. If milestone detail ever comes back it
    still must not be a floating popover (an `overflow-x` box slices
    it) nor `title=` (unstyled, slow, nonexistent on touch). Milestones
    stay `<button>`s: hover/focus highlights one, tap pins it, tap again
    releases (touch has no hover). Their pointerdown MUST
    stopPropagation or the overlay's backdrop handler closes the panel.
  - **At rest exactly ONE label is drawn** — `.cur-stage`, the latest
    milestone at or before the current week (on a milestone week that
    is the current dot; between milestones it is the phase you are
    still inside, so week 7 reads "Recess"). Twelve labels at
    once is a wall nobody reads, and the masthead already answers "where
    am I". The rest fade in together on `:hover` or on `.reveal`, which
    a tap anywhere on the strip toggles — that class exists purely so a
    phone can read the calendar, since touch has no hover. Animate
    OPACITY only: `.edge-l`/`.edge-r` override `transform` to anchor the
    end labels, so a transform-based reveal fights them.
  - The scroll box needs real vertical PADDING. The old
    `overflow-y: hidden` on a 46px inner clipped the outer edge of
    every label and the glow ring on the current dot.
  - **Centering must bail while the overlay is hidden.** `renderHead`
    runs on boot, and a `display:none` scroll box reports `clientWidth`
    0 (just padding), so the centering math wrote a nonsense
    `scrollLeft` that then stuck — the current week's label sat
    half-clipped off the left edge. `centerTimeline()` bails under
    40px and is re-run from `openOverlay()`; same class of bug as the
    hidden-boot 0×0 canvas in WorldScene. Also set `scrollLeft`
    directly rather than `scrollIntoView`, which scrolls the overlay
    (nearest scrollable ancestor) and yanks the whole panel.
- **`esc()` is for TEXT; attributes need `escA()`.** esc() deliberately
  leaves quotes alone, and this content is full of dialogue in
  quotation marks — interpolating it into a `title=` breaks straight
  out of the attribute. Hit live 2026-08-15 on the introducer strip
  (chairs.json `voice` opens with a double quote) and it sprayed junk
  attributes across the element. Every attribute interpolation goes
  through escA.
- Characters are FICTIONAL — never use real legislators' names.
- Dialogue text is escaped (`esc()`) — keep it that way; content JSON
  is not trusted HTML.
- **Metric keys are `support` / `influence`** (Public Support,
  Political Influence). They are NOT two halves of one bar: support is
  a stock spent at hearings and votes, influence is a rate applied to
  every scheduling decision — never render them as a balance. The
  pre-2026-08-13 keys were `families` / `wealthy`; the load-time
  migration in `SessionPanel` must stay, or old saves reset.
- **A bill's support/influence are DERIVED, never stored** (2026-08-21,
  superseding the 2026-08-13 per-bill split — full write-up in
  DESIGN-11 §8e). `billMeter(b, key)` =
  `clamp(S.metrics[key] + b.tilt[key] + b.earned[key])`; a bill stores
  ONLY `tilt` (editorial, by tax family, `chairs.json`
  `gate.familyTilt`) and `earned` (what the player bought for that bill
  — currently just the push). Rules:
  - **Never reintroduce an absolute `b.support`/`b.influence`.** They
    existed until 08-21 and were written exactly once, at agenda lock,
    which happens inside the creation funnel BEFORE any fx can run. So
    every campaign's bills sat at 50/30 + tilt forever, the HUD meters
    touched no bill's odds after week 1, and `gate.dilution` was
    unreachable dead code. Same rule as `targetK()`/`raisedK()`.
  - **The calibration invariant is that a PASSIVE campaign sits at
    50/30 all session**, so every derived term returns exactly its
    pre-rewrite value and the simulator's passive band is unmoved.
    Anything new that touches these meters must preserve that — check
    it with `tools/simulate_gauntlet.py`, whose `passive` profile
    exists as the anchor.
  - `chairOdds`/`floorOdds`/`conf` all read the BILL's numbers. That
    split is what makes low-influence (never heard) and low-support
    (heard but diluted) genuinely different failure modes instead of
    both feeding one probability — and **support still must not make a
    hearing easier unless the chair is aligned**; it does its work at
    the dilution step.
  - Old saves are converted by `migrateBills()` at boot (two
    generations: no keys at all, or absolute keys). It recovers
    `earned.influence` exactly by counting pushes in `S.log`. Without
    it every odds formula goes `NaN` and `Math.random() < NaN` is
    always false, so bills silently stop being heard forever.
- **The two meters have different physics, and it is now IN THE CODE**
  (2026-08-21). Support is a STOCK that gets spent: a week where a vote
  was expected and never called costs 2 (`gate.floorMissSupport`,
  charged once per week however many bills missed), and content can
  stake it as an ANTE. Influence is a RATE that decays 1/week toward
  `gate.influenceBaseline` 30, downward only. **This REVERSED
  DESIGN-11 §1**, which said support decays and influence doesn't —
  neither had ever been built, so nothing decayed and nothing was
  spent. Don't "restore" the old table without reading §1's note.
- **A checked choice's own `effects` block is an ANTE** — paid on
  commit, win or lose, on top of the outcome block. An UNCHECKED
  choice is unaffected (there `effects` IS the outcome, and
  `out === c`, so the `roll &&` guard is what stops a double-apply).
  It applies inside `finish()`, never at pick time — the documented
  rule that no metric may move before the verdict is stamped still
  binds — and it is printed on the button beside the odds, because an
  unadvertised charge is not a decision.
- **The push scales with the influence behind it** (`gate.push`), and
  it is ONE-SIDED: `base` IS the old flat 0.15 and steps only ever add,
  counted from the baseline. A first draft scaled from zero and looked
  right at campaign influence 30 — until the family tilt is
  remembered, at which point a wealth bill (−10) fell into the first
  bucket and its push quietly paid 0.10. Caught in play, not in the
  maths. Never let a reward for standing take something from a player
  who has none.
- **Skill checks** (feature 11 step 1): 2d6 + skill + mods vs DC, with
  snake eyes/boxcars overriding. Odds are printed ON the choice button
  — that visibility is the teaching, don't hide it. WHITE checks reopen
  only when the bonus improves; RED checks are spent forever
  (`S.checks`). Every checked choice needs BOTH `success` and
  `failure` content — a failure that says nothing wastes the mechanic.
  Choices with no `check` key must keep working unchanged.

## Your two introducers (2026-08-15)

The Advocate has no seat, so two members carry the package. Rules:

- **One per chamber, and who is on point is DERIVED from the stage's
  chamber** (`chairs.json` `stages.*.chamber` → `carrierFor()`), never
  stored per bill: every module-1 bill runs the same House-first route,
  so a per-bill introducer field would be duplicated state that drifts.
  House carries intro/h-fin/h-floor, Senate carries s-wam/s-floor;
  `conf`/`final` are `"both"` and answer with whichever rapport is
  higher (both members are in the room by then).
- **Names are PLACEHOLDERS** — Rep. X / Sen. X, in chairs.json
  `introducers` with `char` links to session.json `characters`
  (`rep-x`, `sen-x`), exactly the way chairs link. Renaming one means
  renaming both files.
- **They are the ONLY named characters on the player's own side.** The
  faceless-campaign rule (2026-08-14) covers staff and coalition, not
  legislators: a bill carries a member's name in the real world and
  pretending otherwise would teach the wrong thing.
- **Rapport (0-100) enters the odds ZERO-CENTRED on
  `gate.introBaseline`**: `(rapport - baseline) / div`, added in
  `chairOdds` (`introDiv` 400 → ±0.125) and `floorOdds`
  (`introFloorDiv` 500 → ±0.10). At the starting value the term is
  exactly 0, so the simulation-calibrated enact-rate bands still hold
  for a player who never works the relationship — only the swing is
  new. NEVER simplify this to a plain `rapport/div` term: that pays
  out at baseline and silently re-tunes every band in the design doc.
  `floorOdds(bill, sid)` needs the stage id — a call without it drops
  the carrier's floor edge silently.
- Effects author as `"rapport": {"house": n, "senate": n}` in any
  dialogue `effects` block (`applyFx`). State is `S.intro`, seeded by
  `seedIntroducers()` from chairs.json, so old saves land at baseline.
- Content: the Opening Day handoff (`w1-opening` node `carriers`),
  `talk-rep` / `talk-sen`, and the generic event `ev-introducer` (a
  leadership squeeze on the member, not a favour — rapport buys someone
  absorbing risk for you). Adding `ev-introducer` made genericEvents 6,
  which reshuffles the `(week-2) % n` rotation; all six still appear in
  weeks 4-15 — re-check that if the list changes again.
- UI: `introStrip()` under the bill ledger (rapport bar + how many
  bills each is carrying right now) and a "carried by …" clause on
  every live bill row.

## Legible failure: movement report + post-mortem (2026-08-15)

The gauntlet used to resolve invisibly — a bill went from "alive" to a
struck-through "never heard" with no account. Now:

- **`chairOddsParts()` is the one source of both the number and its
  explanation** — it itemises measured floor + every editorial term and
  `chairOdds()` is a thin wrapper. Never fork a second breakdown; the
  post-mortem can only stay honest if it reads the same parts list the
  roll used.
- **`resolveBills` keeps the DRAW, not just the verdict**: a miss with
  `draw < hazard × gate.nearFactor` (1.6) records a `near` event —
  "the chair pulled the file and put it back" — the only time the
  player ever feels how close "never heard" ran.
- **`S.moves` = {week, list}** of serialisable movement records
  (heard/near/diluted/conf/enacted/dead), rendered by `movesHtml()` at
  the TOP of the hub for one week ("Since you ended the week"), then
  dropped.
- **Death snapshots its odds** (`b.death.odds` = the `chairOddsParts`
  output at the moment of death, plus rolls count and whether it was
  ever pushed). `postMortem()` renders it: measured floor with n and
  sessions, each term signed, the final %, and ONE counterfactual line
  naming the biggest unpulled lever (never worked the chair → the
  action's +15; low influence → the influence lesson; worked it anyway
  → "that is the ordinary outcome here"). Snapshot at death, never
  recompute — the campaign's numbers move on and a recompute would lie.
  In the ledger it sits behind a "Why it died ▸" toggle; sine die
  renders it open.

## Dialogue reader = running transcript (2026-08-15)

`showDialogue` no longer replaces content — beats accumulate in
`.sd-log`, and on every advance `agePast()` marks all prior beats
`.sd-past` (opacity + grayscale on the WHOLE beat, so colored names dim
with their text — the one bright block is always "now"). Choices live
in `.sd-play` under the log: they are UI, not transcript; the picked
one re-enters the log as YOUR line. Banner art appends as a beat once
per distinct image (`shownArt`), so a node-level override (w2's
office) lands mid-scene; only a transcript-opening image bleeds to the
top edge (`.sd-beat:first-child` rule). `settle()` pins the view to
the top of the newest beat rather than the bottom of the log, so a
long beat reads from its start. Continue is deliberately a QUIET
plate — gold CTAs are reserved for real spends (End Week, Act).

## Animation pass, phase 1 (2026-08-15)

All CSS keyframes + class toggles; the only JS sequencing is the staged
roll. Rules that must survive edits:

- **The staged roll**: picking a checked choice appends the card in
  `.rolling` ("the dice are out", choice strip EMPTIED so nothing is
  clickable). Since 2026-08-15 the
  reveal is a POP-OUT TRAY (`popTray` in main.js, `.sd-tray` in CSS)
  centered over the whole panel: a veil dims the scene, a card pops
  with the skill name, two real 3×3 pip dice tumbling, the DC line,
  then dice slam down staggered, the arithmetic ticks in, and the
  verdict stamps SUCCESS/FAILURE in verdict color.
  **The dice are 3D CSS CUBES since 2026-08-21** (user's call: "i want
  the dice to look like they're actually rolling" — the flat square
  flickering its face every 75ms never read as a roll): `.tdie` is a
  perspective stage, `.tcube` carries six `pipHtml` faces (opposites
  sum to 7), CSS spins each cube on a different dominant axis/period
  in the air, and at T_TUMBLE `setFace` sets the cube's INLINE
  transform to the rolled face (+ a full extra turn each axis) so the
  `.landed` transition reads as the roll decelerating in. Rules:
  - **JS owns the landed face via inline style** — a frozen animation
    clock in a hidden tab costs only the tumble, never the result.
    `popTray` adds `.landed` BEFORE calling setFace, or the transform
    lands while the spin animation still owns the property.
  - **The landed override needs BOTH grouped selectors** (`.sd-tray
    .tdie:last-child .tcube`'s spin rule counts four classes; a plain
    three-class `.landed .tcube` loses to it and die 2 never stops
    spinning — hit in verification, die showed identity forever).
  - **No grouping properties on/above the dice** (filter,
    overflow:hidden, opacity) — they flatten preserve-3d; that is why
    `.jack .tray-card` lost its overflow:hidden (the burst self-clips
    with border-radius) and the ground shadow is a flat `::after`
    sibling, not a drop-shadow filter.
  - The 75ms interval survives as SOUND only (`SFX.dieTick`); the
    faces no longer swap. `.tray-dice` gap must stay ≥ ~24px — a
    rotated cube overhangs its box ~12px a side and the dice
    interpenetrate below that.
  - Reduced motion: `.tcube` is in BOTH escape hatches (animation and
    transition) — resting state is the correct face by inline style. The inline card is
  still rendered and settles into the transcript as the RECEIPT — the
  tray is theatre on top, the receipt is the record you scroll back to.
  Sequencing rules that must survive edits:
  - **The receipt settles and the scene washes AT the tray's stamp**
    (popTray's `onLand`), not when the tray leaves — the transcript
    must never lag the announcement. `finish()` (effects + outcome
    beat) runs at `onGone`, after the tray is out. **Effects still
    apply only after the verdict is shown** — the metric cards sit
    above the scene, and a support tick landing before the stamp
    spoils the verdict.
  - **JS timers own the tray's state machine; CSS owns only the look.**
    Nothing may hang off `animationend` — a hidden document freezes the
    animation clock, and the tray would squat over the game forever.
    All steps are parallel absolute setTimeouts; `kill()` is idempotent,
    force-lands `onLand` if it hasn't run, and a 4s backstop guarantees
    removal + `finish()` even if a step is missed. Never make finish()
    reachable only through the happy path.
  - **The tray never takes input** (`pointer-events: none`): the choice
    strip is already empty, and a tray that outlives its timers must
    not be able to trap the player.
  - Mounted on `.ovl-panel` (position: relative), NOT `.sd-scene`, so
    it centers on the panel and ignores the transcript's scroll.
  - **`T_HOLD` is the dwell AFTER the stamp, and it is the number that
    decides whether the roll is readable**: 2200ms since 2026-08-18
    (user's call — "the pop-outs close immediately once fail or success
    shows"). It was 560, which with the 300ms fade gave under a second
    to take in the verdict AND the arithmetic under it, and read as the
    tray slamming shut on the result rather than presenting it. Judge
    this against the STAMP, not against mount: the tray is alive for
    `T_TUMBLE + T_STAMP` (1200ms) before a verdict exists, and nobody
    is reading during the tumble.
  - Boxcars = `.jack` (gold burst on the tray card at stamp time),
    snake eyes = `.snake` (card shake); both hold an extra 700ms.
    Red checks (`r-red`) tint the tray card in the danger color.
  - In the pane, verify with a MutationObserver on the panel (mount →
    landed → verdict → out → removed) — timer clamping stretches the
    timeline and screenshots always miss the window.
- **Reduced motion is a real path, not a CSS afterthought**: the JS
  checks `prefers-reduced-motion` at pick time and resolves instantly
  (old behavior), and one CSS media block kills every animation. Any
  new animation goes in that block too. Autoplay tests use this path
  (override matchMedia) so they don't race the tumble.
- Voices stagger in via inline `animation-delay` from `voiceHtml`
  (~110ms apart) — the instincts pipe up one after another.
- One-shot pulses only in content: the near-miss card gets a single
  amber heartbeat, `hone` fx text one glint. The only loop anywhere is
  the honing pip's slow glint in the hub — the READER never loops
  (the grey-past/bright-now contrast needs stillness).

Phase 2 (same day):
- **`renderMetrics()` builds the three meters ONCE and updates them in
  place** (`#sess-metrics[data-built]`). The old version rebuilt the
  innerHTML on every renderHead, which is why bars snapped and numbers
  could never count — a freshly inserted element has no previous width
  to transition from. Changed values count up (`countTo`), bars slide,
  and the card flashes `bump-up`/`bump-down`, so an fx line in the
  dialogue and the scoreboard above it read as one system. Do not go
  back to re-rendering this block.
  **The card is COMPACT as of 2026-08-15** (user's call — the header was
  eating the reader): each `.metc` is a 2-column grid,
  `minmax(0,1fr) auto`, so the label eyebrow and the value share one
  baseline row instead of stacking, and the bar spans both columns
  underneath. `.sym` stays absolutely positioned and out of the grid.
  The label needs `minmax(0, …)` (not plain `1fr`) or its `nowrap`
  min-content width pushes the value off the card. Together with the
  removed timeline readout, the tighter `#sess-head`/`#sess-foot`
  margins and the removed footer paragraph, this hands ~90px back to
  `#sess-body` — measured 136px → 228px of dialogue on a 560px-tall
  window. Don't re-stack the label over the value.
- **The session footer is the reset link and NOTHING else** (2026-08-15,
  user's call). The paragraph explaining The Advocate, the turn
  structure, the FY2027 scoreboard and the fictional cast was removed —
  it was a wall of text on every single week. `data.identity` in
  session.json is now read by nothing. The "characters are fictional"
  disclaimer went with it; the content rule (never use real
  legislators' names) is unchanged and still binding.
- **`countTo` force-lands its final value on a wall-clock timer** as
  well as rAF: rAF does not fire in a hidden tab and a meter frozen on
  its OLD number is worse than no animation.
- Red checks: hover heartbeats (`red-dread`), and committing one adds
  `.hush` to the scene so the transcript drops to 12% while the dice
  are out — cleared with the wash. White checks get neither.
- Post-mortem rows cascade via `:nth-child` delays; `countPm()` runs
  the final percentage up whenever a card becomes visible (both the
  death card and the ledger toggle). `display:none → block` restarts
  the CSS cascade for free.
- `.mv-row.enacted` gets its own class + one gold sweep — becoming law
  looked identical to a committee hearing before.
- Panel bookends: `.leaving` (240ms) before the week beat, `.arriving`
  on open — but ONLY when the overlay was actually closed, or every
  re-render would re-animate the frame.
- **Your STANDING is ambient on the map** (`#hud-standing`,
  `renderHudStanding`; 2026-08-18, user's call: "show public opinion,
  influence and money outside the overlay, in a very subdued way"). Two
  hairline meters at the top of the bottom-left column, so that column
  reads standing → time left → the verb.
  - **TWO meters, not three: money is deliberately NOT here.**
    `#fund-chip` already folds the campaign's revenue into the FY2027
    figure and its surplus/deficit line (`updateChip` ←
    `PolicyPanel.external`), so a second money number on the same screen
    only asks the player to reconcile two headline figures. If money
    ever needs to read louder, make that balance line louder — do not
    add a third row here.
  - **SUBDUED means NO CHIP.** Every other HUD element is a plate with a
    2px white border and an outline; this has no background, no border,
    no shadow, and rides at .58 opacity until hovered. It sits directly
    above End Turn, the screen's primary verb, and anything with chrome
    competes with it. The overlay scrim (`.ovl`, z-index 30 over the
    HUD's 10) already dims it while a panel is open — no extra rule, and
    no `:has()` dependency.
  - **Three meters, three hues, and the hues MEAN something.** Support
    used to share revenue's gold; that was survivable on the labelled
    overlay cards but not here, where two of two rows would have matched.
    Support is now `#e8795c` — the ORGANIZER pole, "the street and the
    mic", which is exactly what public support is — against influence's
    blue (a step from the wonk pole) and revenue's gold. Pick any future
    meter's colour from that logic, not from what is free.
  - **Row shape mirrors `.metc`** (name + value on one line, bar spanning
    under) so the HUD cluster and the overlay card read as one object
    seen twice. It also fixes an alignment trap: with label and bar on
    ONE line each row is its own grid, so "SUPPORT" and "INFLUENCE" size
    their own first column and the bars start at different x.
  - **The trend is measured from `S.weekBase`**, snapshotted at the top
    of `advanceWeek()` BEFORE `resolveBills()` — so the arrow the player
    reads on the map right after ending a turn is the one the gauntlet
    just moved. Empty when nothing changed: a quiet week should read as
    quiet, not as a row of zeroes. Old saves seed it at today's values so
    an in-progress campaign opens showing no trend rather than inventing
    a swing nobody caused.
  - **Built ONCE and updated in place** (`data-built`) — same lesson as
    `renderMetrics` and `renderHudTimeline`.
  - **No bump/flash on purpose.** Support and influence almost only move
    INSIDE the overlay, where this sits behind the scrim, so a flash
    would fire unseen; the overlay's cards already own that job and the
    trend arrow covers the turn beat better than a flash could.
  - Bars stay on mobile (user's call) — the ≤600px block only tightens
    type and width.
- **The HUD chip is a PROGRESS BAR, not a dot strip** (2026-08-15,
  user's call — `renderHudTimeline` → `renderProgress`, `#hud-timeline`;
  since 2026-08-19 the session panel has one too, see the calendar
  section above — same renderer, same `.htl` styles, different chrome). At 168px the old
  nine 5px milestone dots read as lint. Milestones survive as faint
  ticks IN the track (inset and dim on purpose — full-height bright
  bars read as segment dividers chopping the run into chapters, the
  opposite of a continuous progress read), with a bright leading-edge
  cap and a "3/16" readout. The overlay's full strip is still where you
  READ the calendar; this answers "how much session is left" and is a
  tap into the overlay. **Built ONCE and updated in place**
  (`data-built`), the same lesson as `renderMetrics`: replacing the
  innerHTML gives the fill no previous width to transition from, so it
  would snap on every week instead of sliding.
- **The CHARACTER CARD** (2026-08-15, user's call): a Disco-style
  profile plate pinned at the top of any scene its character speaks in
  — portrait, name, office, a couple of short reads on how they
  operate, and their own words. Kawaguchi is the first and currently
  only one. Rules:
  - **DRAWN PORTRAITS ARE FACELESS**, the same house rule as the skill
    glyphs: a silhouette at a committee desk, a collar, a nameplate. No
    features, ever. Drawings live in the `PORTRAIT` map in main.js,
    named by the card's `art` key. A card may instead carry a `photo` —
    see the portrait-rail section above.
  - **ONE gold accent per drawing**, like the skill glyphs. Kawaguchi's
    is the desk nameplate — a chair IS his nameplate. A gavel was drawn
    and cut: it collided with the desk edge at small size and made two
    accents.
  - **The quote is NOT stored in session.json.** `chairVoiceFor()`
    reads it live from chairs.json `voice` via the chair whose `char`
    points back at the character id, so a chair's own words can never
    drift between the two files. (`CH` is declared later in the same
    closure but only ever READ at call time — that is fine, and is why
    the lookup is a function rather than a precomputed map.)
  - The card follows whoever is SPEAKING, and a node with no speaker
    leaves it alone — you are still standing in front of the same
    person while the prose describes the hallway.
  - It is `position: sticky` inside the scene, not a first beat: the
    point is that they stay in front of you for the whole conversation.
    Under 560px the `note` is hidden and the quote carries it.
  - Only characters with a `card` block get one, so an incidental
    speaker never gets a dossier. Adding one to session.json REQUIRES
    bumping `map/session.json?v=` in main.js by hand — the pre-commit
    cache-bump hook only rewrites `?v=` inside HTML, and a stale cached
    session.json silently renders no card at all (hit live).
- **Dialogue body type is 16.5px / 1.68** (raised from 14.5 / 1.6 on
  2026-08-15, user's call). This is a reading game and the transcript
  is the whole interface. `.sd-who`, `.sd-role` and the choice buttons
  were scaled with it — if the body size changes again, move those too
  or the reader goes out of proportion.
- **ONE masthead, in the panel's top-left corner** (2026-08-15, user's
  call). The overlay used to stack two headers that said the same
  thing: the `.ovl-title` chip ("The Campaign · Week N") riding the top
  border, and a separate `#sess-week` row inside naming the week again.
  Now a single plate lives in the chip slot carrying the stamped week
  numeral, the week's title and its phase + real dates. `#sess-week` is
  GONE from index.html and renderHead — don't reintroduce a second
  header row. Notes:
  - It is `.ovl-title.mast`, i.e. it OVERRIDES the chip rather than
    living in flow, so it inherits the corner position for free and the
    money/policy overlays keep the plain chip.
  - Being out of flow, `#session-overlay #sess-head` must RESERVE the
    height the plate reaches into the panel (30px, 24px under 560px) or
    the timeline slides under it. Net it still costs ~43px less than the
    old chip + masthead row, so the dialogue gained space.
  - The plate carries a resting `rotate(-.7deg)`, so the week-arrival
    stagger gives it its own `wk-rise-mast` keyframe — the shared
    `wk-rise` interpolates through an unrotated matrix and the plate
    visibly straightens as it lands.
  - Under 560px the type steps down AND the tracking tightens: the DATE
    must fit whole, an ellipsised "Feb 2, 2…" is worse than no date.
- **An instinct CHIMING IN is a card, not a left rule** (2026-08-15,
  user's call). `.sd-voice.v-skill` used to be a left accent bar in the
  pole colour — the same device the bill rows, the meters and the
  post-mortem all use, so the one element meant to INTERRUPT the reader
  read as another list item. Now: a soft pole-tinted wash fading out to
  the right over a dark ground, a hairline border in the same pole, and
  the skill's name as a solid nameplate badge (dark ink on the pole
  colour, pill radius) instead of coloured text. **No left accent
  anywhere on it** — the tint and the badge carry the pole. The badge
  replaces the hanging indent and the `.sd-dash` separator (hidden in
  CSS), and voices enter from the LEFT (`sd-chime`) rather than rising,
  because they arrive across the column. Pole colours still come from
  `.p-wonk` / `.p-bridge` / `.p-organizer` via `--pole`.
- **TWO overlay entrances, and the split is editorial** (2026-08-15,
  user's call). Reopening the panel you just closed is furniture and
  keeps the modest 260ms `.arriving` rise. A WEEK ARRIVING is an event
  and gets `.wk-open` (`weekArrive()` in main.js, `#session-overlay.wk-open`
  rules in CSS): the scrim fades up from transparent, the panel rises
  further and slower, one low-opacity sheen crosses it, and title /
  week plate / timeline / meters / `#sess-body` / footer stagger in
  behind the frame at 60–320ms. Rules:
  - **`openOverlay(week)` takes the flag; only TWO call sites pass
    `true`** — the boot pop and all three branches of `openWeek()`.
    Everything else (Session tab, Instincts tab, HUD timeline, the
    week-1 turn-chip agenda bail) stays ordinary. Putting the
    ceremonial entrance on every open makes the Session tab feel like
    an occasion and the actual week feel like nothing.
  - `weekArrive()` **removes `.arriving` first** — both classes animate
    `.ovl-panel` and would fight over the `animation` shorthand.
  - **`WK_IN` force-lands it on a wall clock**, same rule as
    `screenSwap` and `countTo`: a hidden document freezes the animation
    clock and `both` fill would hold the entire overlay at opacity 0 —
    open the game in a background tab and come back to nothing. Keep
    `WK_IN` above the longest child delay + duration (.32s + .44s).
  - The sheen is an `::after` on the panel: absolutely positioned (so it
    stays out of the panel's flex flow), radius-matched (so it doesn't
    square off the corners), `pointer-events: none`, and killed outright
    under reduced motion so it can't park itself across the panel.
  - Under `.creating` the head/title/footer are `display: none`, so a
    fresh boot animates only the panel and `#sess-body`. That is
    correct, not a gap.
- **Every `b` rule under `.bill-row .shname` uses the CHILD combinator.**
  The post-mortem renders inside that `<small>`, so descendant
  selectors reached its whole odds ledger and repainted it in the
  dead-bill colours (found live: every term rendered grey-blue, then
  red). Three rules were fixed; keep the `>` if you touch them.

## UI chrome: tokens, and the plate idiom retired (2026-08-28)

From "the color scheme for the ui (gold and blue) doesn't look good
anymore … more sleek and modern". **The hues were not the problem**, and
that is the finding the whole change rests on: gold and blue both
survive, re-roled. What dated the UI was four STRUCTURAL cues, and both
hues being used as large FILLS rather than accents:

  a 2-3px PURE WHITE border with a second `outline` ring behind it (11),
  a flat two-stop royal blue `#2a3f9e -> #16246b` used as a SURFACE (6),
  `text-shadow: 1px 1px 0 #000` (12),
  `box-shadow: 0 Npx 0` — a hard offset with no blur (6).

All four are now at zero. Swap the hues and keep the cues and it would
still have looked like 2003; that is why this was scoped as retiring an
idiom, not as a recolour.

**The modern language already existed in this repo and was quarantined.**
The cinema pass (`#session-overlay`) and the creation screens were
already doing near-black grounds, gold as a low-alpha hairline, soft
ambient shadows. The work was promoting that outward to the HUD, the
toolbar and the money/policy overlays — not inventing a third style.

### Tier 1 — the token layer, and how to change it safely

`:root` at the top of style.css. Before it existed the sheet carried the
accent gold as a literal **48 times** and the muted blue 24, across 4,300
lines, so there was no way to tell a deliberate one-off from a copy of
the house colour, and every restyle was a find-and-replace.

- **Named by ROLE, not by hue**, because the hues are expected to move
  and the roles are not. `--plate-*` still means "the game's own chrome
  surface" even though that surface stopped being a plate.
- **The semantic group is load-bearing meaning and must survive any
  repaint**: `--support` is the organizer pole, `--influence` the wonk
  pole (see the HUD-standing note), plus gain/cost/good/bad/danger.
- **`#fff` and `#000` are deliberately NOT tokenised** — ~34 uses that
  are plain black and white rather than palette. A token earns its place
  by being shared; one used once is just a rename.
- **THE GATE, and re-run it for any edit here: resolving every token
  back to its literal must reproduce the previous file BYTE FOR BYTE.**
  That is what makes "this changes no pixels" a fact rather than a hope,
  and it is checkable offline in seconds — far stronger than a screenshot
  diff, which this game's animated DOM cannot give you cleanly (the flow
  motes and the deal-animation classes differ run to run; a computed-
  style dump was tried first and drowned in that noise).

### Tier 2 — what replaced the plate

- **Floating chrome is glass**: `--plate-hi/-lo` are translucent now and
  pair with a `backdrop-filter`. **Modal panels stay OPAQUE** — a blurred
  backdrop under 600px of prose is expensive and reads as mush.
- **Gold is an accent, with exactly two exceptions that are FILLED**:
  End Turn (`#turn-chip`) and the session hub's End Week
  (`.sh-week-end`) — the same primary verb in two places. Giving every
  chip a plate is precisely what stopped the one that matters from
  reading as a call to action.
  - Consequence that bit once: `#turn-chip`'s two child labels were pale
    blue and pale gold, written for a dark plate, and went invisible the
    moment the chip became gold. Its pending-event dot had to deepen to
    `#a8321f` for the same reason. **Anything nested inside a filled
    accent needs its own contrast check** — the parent rule cannot do it.
- **`.ovl-title` and `#dialog-name` became TYPE**, not gold plates
  clipped onto a border. The panel already has an edge; a second framed
  object riding on that edge was two frames for one thing.
- **`.ovl-tabs` became a segmented control**, which is what mutually
  exclusive views of one panel actually are.
- **The session panel's own skin was included**, even though it belongs
  to Tier 3 (reconciling the overlays). `#session-overlay` overrides
  `.ovl-panel`, so leaving it would have shipped a royal-blue panel next
  to neutral ones — worse than either end state. The lit-surface
  treatment and the film grain are kept; only the hue moved.
- **The masthead keeps its plate, and only it.** `.ovl-title.mast` is
  meant to read as a stamped physical object — it carries the resting
  `rotate(-.7deg)` and its own `wk-rise-mast` keyframe for that reason.
  It shed the royal-blue ground and the 4px hard offset, which are the
  cues; the idea survives.
- **The `.prow.on .pgo` gold fill is deliberate and stays**: an enacted
  policy is a state worth finding at a glance, and that is what a fill
  is for.
- **`--text-lift` exists because `#hud-standing` has no plate** (a
  documented decision — a plate there would compete with End Turn), so
  type over the map still needs a shadow to stay legible. It is a soft
  one; the hard 1px outline it replaces was the loudest dated cue in the
  sheet. Don't just delete a text-shadow over the map.
- The HUD-standing note itself was rewritten: its whole rationale is
  stated as a CONTRAST with the plate idiom, so retiring the plates
  would have made it a lie.

`site/dev-ui.html` is the before/after record — same dev-harness
convention as `dev-parallax.html`, self-contained, imports nothing from
style.css. Both columns are hardcoded, so it stays truthful as the sheet
moves on.

### Tier 4 — the type pass

The last loud cue after tiers 1-2: `font-weight: 800` paired with
letter-spacing in **~20 distinct, non-scaling PX values** (1px, 1.4px,
1.6px, 2px, 2.2px, 3px, 4px ...) on uppercase micro-labels ranging from
8px to 19px. `font-weight: 800` dropped from 51 uses to 13.

**Three EM-based tiers replace the scatter, and EM (not px) is the
whole fix**: `letter-spacing` in `em` is relative to the element's OWN
font-size, so one number reads as coherent tracking across many sizes
where a flat px value cannot — a gap sized for an 8px badge is
invisible at 19px, and one sized for 19px is a picket fence at 8px.
Smaller caps need proportionally MORE tracking to stay legible; bigger
caps need much LESS or they look gappy — which is why there are three
tiers, not one token:

  `--w-label: 650` / `--track-micro: .16em`  — <=10.5px eyebrows, badges
  `--w-label: 650` / `--track-label: .10em`  — 11-14px chrome labels/buttons
  `--w-title: 700` / `--track-title: .04em`  — >=15px card/panel headline names

**Explicitly NOT touched, and why — the same "not everything loud is a
bug" judgment tier 2 made for the masthead:**
- The dice-tray / roll theatre (`.tray-skill`, `.tray-dc`, `.tray-stamp`,
  `.sd-roll .die`, `.sd-roll .sd-spec`) — a documented dramatic beat.
  Flattening it would be a regression, not a fix.
- `.sk-title` — the creation screen's own stencil-plate title
  ("no webfont, so lean on ... letterspacing"), not chrome.
- The masthead's stamped week numeral (`.mast-no b`) — same stamped-
  object logic the tray shares.
- Small numeral/glyph badges with no letter-spacing at all (`skpip`,
  `skup`/`skdn`, `ag-num`, `agc-pick`) — a bold single digit in a tiny
  circle is a legibility choice, not the shouting this pass targets.
- Anything tier 2 already shipped (`.ovl-title`, `#dialog-name`,
  `#turn-chip`, `.sh-week-end`) — re-touching would just create a
  second disagreement with itself.

**One doc/code mismatch surfaced and got fixed as part of this, not
separately**: `.sd-done` ("Continue") is documented as *"a quiet
full-width plate ... gold stays reserved for real spends"*, but it
shipped at weight 800 / 2.2px tracking — the single loudest combination
in the sheet. The label tier is also the fix for that.

**Numeric readouts** (`.metc .mv`, `#fund-chip .fc-amt/.fc-bal`,
`#hud-standing .hs-v/.hs-t`, `.agc-amt`, `.sh-row .shtag`,
`.bill-row .bstat`, `.htl .htl-read`, `.prow .ptag`) got a lighter
touch: 800 -> 700 only, no tracking involved (none carry
letter-spacing) — just the same default weight making every number in
the game maximum-bold.

**Mechanical hazard worth recording, because it cost two failed runs**:
several of these selectors have a `@media (max-width: 560px)` duplicate
that resizes them for mobile (`.mast-t b`, `.mast-t small`,
`#hud-standing .hs-l`) or a second base-level rule that only adds one
property (`.sd-card .cc-name` (a `font-size` clamp), `#sess-metrics
.metc .mv`, `#fund-chip .fc-amt`, `#hud-standing .hs-v`). A NAIVE
`str.count()` on the selector text both **over-counts** (`.ag-lbl {` is
also a substring of `.ag-step.now .ag-lbl {`, a longer, unrelated
selector) and, separately, an end-of-rule search for the literal string
`"\n}"` **fails silently** inside an indented `@media` block, where the
real closing brace is `"\n  }"` — it keeps scanning into the NEXT
rule's body instead of stopping, and edits the wrong text. The working
tool anchors matches to `^[ \t]*` + the selector (real occurrences
only) and finds the close brace with `\n[ \t]*\}` (indent-agnostic).
Re-use that pattern, not `str.count`/`str.index`, for any future sweep
across this file.

## UI sound (2026-08-19)

`site/js/sfx.js` — `window.SFX`, loaded before main.js. Every sound is
SYNTHESISED at runtime with Web Audio; there are no audio files in the
repo. Same bargain as the map, the banners and the glyphs: the asset is
code, so a change is a diff. It also wins on LATENCY, which is the
thing that actually matters for a click — a decoded sample cannot beat
an oscillator starting on the same turn of the event loop. Swapping in
a CC0 sample pack later means replacing the bodies of `SFX.*` and
touching no call site.

- **Serious CRPG, not arcade.** The first pass was rejected outright
  ("I don't want cartoony sounds, more serious RPG-like"), and the
  three things that made it cartoony are now house rules in the file:
  a rising major arpeggio for success and falling notes for failure
  (MELODY — a tune played at the player is a mobile game congratulating
  them); a PITCH LADDER transposing the instinct click by the skill's
  rank, so spending points walked up a scale (the coin-collect sound);
  and SQUARE WAVES, which are chiptune however they are enveloped.
  Everything is now a STRUCK OBJECT: noise through a resonant bandpass
  for the material, sine partials at INHARMONIC ratios for the body
  (consonant ratios read as a chord, i.e. as music), one pitched event
  per call, and a master lowpass at 5.2kHz over the lot.
- **Tune by MEASUREMENT.** "Cartoony" is mostly spectral centroid and
  decay length, both readable from the page: patch
  `AudioNode.prototype.connect` to tee whatever connects to
  `ctx.destination` into an AnalyserNode, then integrate an
  AMPLITUDE-WEIGHTED centroid over the whole event across several takes
  — a single-frame centroid at the peak is far too noisy to compare,
  because a 46ms FFT window lands on the transient for one sound and on
  the body for the next. That pass caught two bugs the code looked fine
  for: everything was ~12dB too quiet, and FAILURE was coming out
  BRIGHTER than success (2458Hz vs 1626Hz). The shipped table is in the
  file; **the ORDER matters more than any single number** — inside the
  click family brightness and tail length both fall with the WEIGHT of
  the act (pip up 793Hz/33ms → pip down 678 → commit to a line 513 →
  end the week 344Hz/165ms), failure (328Hz) is the dullest thing in
  the game, and the dice (1097Hz) are the brightest because they are
  the only object actually clattering.
- **A LOWPASS transient is what makes a click sound low** (2026-08-19,
  second tuning pass: "still a bit too high pitched, I want more of a
  clicky sound"). Dropping every resonance an octave was NOT the fix on
  its own. A bandpass at the Q near 1 that a click wants passes a wide
  skirt of top end, that skirt reads as hiss, and hiss is what keeps a
  low click sounding high; moving that one layer to a lowpass took the
  pip from 1285Hz to 793Hz with nothing else changed. `strike()` takes
  a `type` for exactly this: bandpass for a RESONANCE (the body of a
  struck thing), lowpass for a TRANSIENT (the contact itself).
- **Ending the week is the click family's big brother, not a fanfare**
  (`SFX.week`, fired inside `advanceWeek()` and not on the button, so
  it catches both doors — the End Turn chip and the hub's `#sess-next`
  — and so the sine-die and `beating` guards above it keep a press that
  does nothing silent). It stays SHORT at 165ms because the week beat
  that follows is a 1.6s camera move into silence, and a sound still
  ringing over the start of that blurs the punctuation.
- **The context is created LAZILY, inside a pointerdown.** Building it
  at load leaves it "suspended" under the autoplay policy and swallows
  the first click of the session; `resume()` runs on every call because
  a backgrounded tab can suspend it again.
- **A sound fires only where the value ACTUALLY moved** — after the
  guard, never before. A capped instinct and one at the floor are both
  still live tap targets, so clicking on entry would click at a player
  who changed nothing, which is worse than silence.
- The tumble plays ONE tick per cycle of the 75ms interval, not one per
  die: two transients 0ms apart phase into a single louder click and
  the dice stop sounding like two objects.
- **Mute is `#sfx-chip` in the title plate, not the toolbar** — the
  four toolbar buttons are DOORS into panels and a fifth that is a
  preference would misread as a fifth panel. State persists in
  localStorage `cq-sfx`; muted means the graph is never built, not that
  the gain is zero. Its glyph is DRAWN, not an emoji (same rule as
  `SYM`), and the muted state is a quieter icon rather than a slash — a
  slash at 13px is mush.

## Map jobs A + B: the week beat (2026-08-15)

Ending a turn runs THROUGH the map: overlay drops, the camera makes
one slow move (`WorldScene.weekBeat`, ~1.6s + a 450ms held breath) to
wherever the new week happens, then the week opens. The map is the
CLOCK between turns, not scenery behind a panel.

- Target = the incoming event's `at` key (session.json): absent →
  Capitol; `{island}` → frame the island (ev-emergency → Hawaiʻi);
  `{island, px:[x,y]}` → a point in that island's BAKE pixels through
  anchor+scale — the same transform chain as landmarks, never world px.
  Most events correctly have NO address: the campaign happens at the
  Capitol. Give one only when the scene genuinely is elsewhere.
- **The ritual must never strand the game**: `weekBeat` wraps
  everything in try/onDone-once, and a 4s `setTimeout` fallback fires
  even if the tween clock is throttled in a hidden tab. `beating`
  gates `advanceWeek` re-entry (the turn chip is live during the move).
- After the beat the week ALWAYS opens the overlay (report, event, or
  hub) — the rhythm is close → travel → open, every turn.

## The gauntlet: chairs, bills, base rates (feature 11 step 2)

Bills are TOKENS that move through the real calendar, and the thing that
kills them is a chair never scheduling a hearing — `cause: "never heard"`,
no vote, no record. Rules that must survive edits:

- **SCOPE: the two MONEY committees only** — House Finance and Senate Ways
  and Means (`intro → h-fin → h-floor → s-wam → s-floor → conf → final`).
  Since 2026-08-19 every bill in play is a REVENUE bill (see the
  revenue-game bullet above — priorities set the target and are never
  introduced), so the money committees are not merely the hardest gates
  a bill happens to face, they are the only ones it could face.
  Every bill with a dollar figure goes through both; they take more
  referrals than any other committee (876 and 936 in 2026) and hand back
  the two lowest hearing rates in their chambers. Subject-matter committees
  are deliberately out of scope — if they return, restore the
  `singleReferral` leadership roll with them (chairs.json explains).

- **`site/map/hearing_rates.json` is MEASURED and generated — never hand
  edit it, and never paste rates into chairs.json.** Regenerate with:
  `cd ~/repos/Legislative-Research-Tool && .venv/bin/python -m testimony
  measures export --out ~/capitol-quest/site/map/hearing_rates.json`
  (it reconstructs referral → hearing → report from the Legislature's own
  referral sheets, chamber journals and hearing notices). Capitol Quest is
  DOWNSTREAM of that repo, same as budget data is downstream of
  BudgetPrimerFinal.
- `site/map/chairs.json` is EDITORIAL: fictional chairs, dispositions,
  route, deadlines. The two halves stay in separate files so the measured
  number can be shown honestly in the bill tooltip.
- **The rate depends on the KIND of tax bill.** `policies.json` items carry
  a `tax` family (wealth / credit / get / income / exemption / tourism /
  sin / admin) and the gate reads that committee's cell for that family:
  Finance noticed 32% of tax credits and 24% of wealth-tax measures. Never
  collapse them back to one revenue rate — that difference IS the module's
  argument. Note the child tax credit is tagged `credit`, not an
  appropriation: it is a tax expenditure and the building treats it like
  one.
- **Thin cells are borrowed, and the tooltip must say so.** Every rate
  carries `basis`; when it is not `"type"` the bill tooltip explains that
  the number is the committee's all-tax-bill rate, not a measured rate for
  that family. Do not simplify that sentence away.
- **`gate.championed` is the ONLY deliberate adjustment to a measured
  number** (+0.12). It exists because the base rate covers every measure
  referred — including thousands nobody carries — while the player's three
  bills have their introducer working them. Keep it named, keep it small,
  and never fold it into the base.
- **The measured rate is a WINDOW probability, not a weekly one.** It is
  converted to a per-week hazard (`weekHazard`) using the window fixed at
  stage ENTRY. Re-deriving the window from weeks-remaining sums a harmonic
  series and silently makes every gate easier than measured.
- Leadership rolls `singleReferral` at introduction — the player never
  chooses their referral, which is the point.
- **Calibrated by simulation, and the simulator is REAL and
  re-runnable** (`tools/simulate_gauntlet.py`, added 2026-08-19 — the
  original table was hand-produced by a script that was never
  committed and had been stale since 2026-08-13). It reads
  `chairs.json`/`hearing_rates.json`/`session.json` LIVE, so it can't
  drift from the shipped game by hand-copying. Re-run after any change
  to gate math, the meters, or the tax families in `policies.json`
  `revenue`; full numbers and the invariants they must keep are in the
  design doc §8d/§8e/§0.
  **Profiles are WEEKLY ACTION POLICIES, not static meter values**
  (2026-08-21) — the old `engaged` (support 70) and `insider` (40/85)
  named states no path through the game could reach, which is the bug
  §8e fixed. Current (20k sessions/cell, per-bill, wealth): passive
  2.4%, rally 3.5%, bench 3.8%, lobby 4.5%, balanced 6.4%, push-first
  10.1%; "never heard" causes 76-90% of deaths in every policy; the
  credit-vs-wealth contrast holds at 2.9-4.1× but stays HYPOTHETICAL
  (no credit-tagged revenue bill exists to show it).
  **`passive` is the invariant anchor** — it never acts, so its meters
  never leave 50/30 and its band must not move when the meter maths
  changes. If it does, something is wrong. (It reads 2.4% against the
  08-19 table's 3.3% for two reasons that were measured, not guessed:
  the 08-19 simulator never modelled the mandatory recess at all
  (~0.7pp — a fidelity gap in the TOOL, not a change to the game), and
  the new floor-calendar support burn (~0.2pp). With both removed it
  reproduces 3.35% exactly.)
  If a change moves any of this a lot, that is a finding to explain,
  not a number to quietly paper over.

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
silently repeals it for existing players. (`get-half`, whose amt was the
FY27 GF GET projection ÷ 8, was removed 2026-08-15 — see the creation
funnel section. Nothing in policies.json is derived from revenue.json
any more, so a COR re-base no longer forces a recompute here.)

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

**Census fetch gotchas** (all hit live 2026-08-15, fixed in `_fetch`):
- **A batch where no zip has data returns HTTP 204 with an EMPTY BODY**,
  not an empty JSON array — `json.load` on it raises "Expecting value:
  line 1 column 1", which looks exactly like a bad API key and is not.
  Three real Hawaiʻi ZCTAs (96742, 96747, 96774) have no CBP record, so
  this broke every single build.
- **Misses must be cached too.** Caching only the hits left those three
  permanently "missing", so every run re-requested and re-crashed. They
  are written back as null now; consumers use `(d.get(z) or {})`.
- **A bad key is a different failure**: HTTP 200 with an HTML body. That
  still raises, but the message now names the likely cause.
- **Only the BASIS series is required.** Both pop and payroll ride in
  the output as context, but the non-basis one degrades to zeros on a
  Census hiccup rather than killing the build — a CBP outage used to
  break the default population build, which never reads CBP.

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

## Map art style — painterly (default) vs pixel (archived)

`render_map.py --style {painterly,pixel}`, painterly since 2026-08-15
(user's call: Disco/CRPG board, not a tile game).

- **`--style pixel` IS the archive of the old look, and it is archived
  as SOURCE, not as a folder of stale PNGs.** `python3
  tools/render_map.py --style pixel --all` brings the original bright
  pixel-art map back exactly. Don't delete the branch.
- **A style may change COLOUR and DENSITY only — never geometry.** The
  crop window, transform, W/H and every px coordinate must be identical
  between styles, because tax_flows / get_flows / world.json / landmarks
  / stations are all baked against those numbers. This was verified
  after the restyle: all eight islands' `transform`, `w`, `h`,
  `landmarks` and `camera` came out byte-identical, and rebuilding
  tax_flows + world produced **no diff**. That is why a pure restyle
  does NOT require the flow rebuild the terrain-change rule demands.
- **The palette is the SAME bright tropical set in both styles.** A
  muted earth-and-slate painterly palette was built first and rejected
  ("it should be bright"). `PAINTERLY_PAL = dict(PIXEL_PAL)`. The
  styles differ in TREATMENT: oil-paint facets (`cv2.xphoto.oilPainting`
  at 0.72 blend — full strength turns the coastline to mush), a
  saturation + midtone lift, softened sprite keylines (`_outline` drops
  the hard keyline to 55% alpha — a crisp dark outline is the single
  strongest pixel-art cue), and a thinned sprite field (`D = 0.45`;
  downtown towers stay at full density, they ARE the landmark).
- **NO VIGNETTE, and this is load-bearing.** Every island is a
  RECTANGLE composited onto a flat sea, so any position-dependent
  darkening draws a visible box around each island at world zoom. A
  faint radial falloff was tried and did exactly that. Only per-pixel,
  position-independent grading is safe.
- **The sea colour has ONE source now.** It used to exist in three
  places and each one that disagreed drew island-shaped rectangles at
  world zoom (all three hit live, in order): the baked slice water,
  `build_world.py`'s overview fill, and `DEEP_BLUE` in main.js.
  render_map exports the graded value (`graded_deep()`) into every
  `<slug>.json`; build_world READS it (`deep_from(metas)`); main.js
  reads `world.deep` at runtime and `DEEP_BLUE` is now only the
  pre-load fallback. That last step matters for the ARCHIVE — the
  constant cannot be right for both styles at once, since pixel bakes
  `#1c5490` and painterly `#185ba0`. Verified by baking `--style pixel`
  end to end and sampling the canvas: exact match, no boxes.
- **`MAP_V` in main.js is the ONE cache token for the whole bake** —
  tile PNGs, overview.png, world.json and every `<slug>.json`. They come
  out of the same run and are only valid as a SET; a world.json paired
  with last bake's tiles is exactly the mismatch that spent three
  rounds looking like a rendering bug. After re-baking, raise that ONE
  number. (The pre-commit hook only rewrites `?v=` inside HTML, so
  anything loaded from JS is by hand. Content JSON — session, policies,
  chairs — keeps its own token; it changes on a different clock.)
- **maxZoom is 1.35** (was 4). The old ceiling walked the camera up to
  individual 18px sprites, which is where a baked map stops being a
  painting and starts being a texture. The intro tween reads the
  ceiling (`Math.min(1.7, this.maxZoom)`) rather than carrying its own
  number — a hardcoded 1.7 sailed straight past it.

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

## Rainfall — measured dryness (2026-08-21, user's call: "drier areas
## should not look really green")

The single most legible fact of Hawaiʻi's geography is the wet/dry
divide, and it is DATA now, not art direction:

- `tools/build_rainfall.py` fetches the **Rainfall Atlas of Hawaiʻi**
  (Giambelluca et al. 2013) statewide 250 m mean-annual grid
  (`StateRFGrids_mm.zip`, ESRI ADF — needs rasterio) into
  `data/raw/rainfall/` (gitignored, like the TOD roads) and bakes the
  small committed raster `data/rainfall_mm.png` (16-bit, mm/yr) +
  `data/rainfall_mm.json` (affine header). Ocean cells are filled from
  the nearest land cell so per-pixel sampling never falls off the
  coastline. Eight QA points (Waiʻaleʻale ~9.9 m … Kawaihae 255 mm)
  assert on every run.
- `tools/rainfall.py` is the ONE reader both build steps share:
  `sample()` (bilinear), `wetness()` (LOG ramp 300→3000 mm — linear
  wastes its range on shades of rainforest), `lushness()` (extra depth
  2200→5000 mm). **Niʻihau is outside the atlas grid** — islands.py
  carries `rain_mm: 640` as its modelled fallback (the only island with
  one).
- build_map: the forest belt around every ridge is now GATED by rain
  (~900 mm mesic edge, noise-jittered) — leeward Waiʻanae/Haleakalā
  flanks stopped reading as rainforest; `rain` (mm/yr per tile) rides
  in map_grid_<slug>.json. `build/debug_rain_<slug>.png` previews the
  ramp per island.
- render_map: every ground class ramps between wet and dry pigments by
  the per-pixel field (`ground_color()`; dry stops in both palettes —
  gold grass ~650 mm, bare red-brown hardpan <400 mm, lush deep green
  at the rainforest end; rock_high goes red-brown cinder when dry).
  `DRY_STRENGTH` lets irrigated classes cheat: FIELD 0.62 / URBAN 0.55
  — Kekaha's green cane squares against tan IS the geography. Sprites
  follow the same field: forest canopy thins toward the dry edge, dry
  GRASS grows scattered kiawe `spr_shrub()`, wet grass a stray tree.
- Rainfall is TERRAIN DATA, so it flows through BOTH art styles. The
  `--style pixel` archive therefore now shows the dry ramps too; the
  pre-rainfall original is in git history, not behind the flag.

## Elevation — the actual mountains (2026-08-21, user's call: "make the
## mountains look like real mountains… the actual mountains")

Terrain height is MEASURED now, same pattern as rainfall:

- `tools/build_elevation.py` fetches AWS Terrain Tiles (terrarium z10,
  open bucket, ~65 tiles cached in gitignored `data/raw/elevation/`)
  and bakes `data/elevation_m.png` — 16-bit metres, **pixel-aligned
  with the rainfall raster** (same affine, from rainfall_mm.json), so
  the two fields share sampling maths. Below-sea clamps to 0. Eight QA
  points assert (Mauna Kea 4156, Kōnāhuanui ~895 — knife-edges lose
  ~7% to z10 smoothing, floors are set accordingly).
- `tools/elevation.py`: `sample()` bilinear; `height_units()` = the ONE
  metres→render-units curve (0.082·m^0.78 — power law, or the choice is
  a flat Koʻolau vs a Mauna Kea that leaves the canvas); `BEACH_MAX_M`
  (24 m) = where a sand shore can physically exist.
- build_map: `hgrid` is the DEM for ALL land (the ridge polylines in
  islands.py still place CLASSES — forest belts, peak tiles — but no
  longer invent topography; ridge-tuple h_mult is dead). Synthetic
  crater rims survive ONLY for cones under the DEM's resolution
  (r_out ≤ 1.2 km: the three Oʻahu tuff craters); Haleakalā,
  Mokuʻāweoweo and Kīlauea calderas are in the data. Per-tile `elev`
  (m) rides in the grid json.
- render_map samples the DEM per PIXEL (every 2nd px, bilinear up) —
  **going through the 320 m tile grid + the anti-corduroy blur is what
  airbrushed the Koʻolau into a loaf**; tile heights ride along only
  as a blurred positive delta (the tuff-cone rims). Light 3 px blur
  kills bilinear-cell facets in the hillshade. Height multiplier 2.5,
  hillshade gain 6.0/±46 with a ±3 px stencil (the old 3.2 gain was
  tuned for fake tent-slopes and read as airbrush on real ones).
- **Bare rock is measured, not height-proxied**: alpine line at
  ~1900 m ("t" from talt — Mauna Kea/Loa and Haleakalā summits, never
  the 900 m Koʻolau, which the old hpx rule painted as scree), plus
  steep-slope exposure streaks; rock hue still rides the rain ramp
  (wet grey vs dry red cinder). MOUNTAIN/PEAK wet-end ground is now
  vegetated green (`mtn` palette key) — a wet Hawaiian ridge is
  forested to the knife edge; the old rock_low base drew an olive
  dirt stripe along every crest.
- **Sand only where beaches exist** (both build_map's SAND rim and
  render's beach band gate on `elev < BEACH_MAX_M`): under a pali or
  on a lava bench the shore keeps its terrain colour over a dark
  wet-rock edge. Steep coasts keep their height to the waterline —
  the relief pass draws real sea cliffs (Nā Pali, Molokaʻi north
  shore, Hāmākua) for free; only gentle shores ease into the sea.

## Ocean & water (2026-08-21)

- **Open ocean in every bake fades to TRANSPARENT** (`A_FADE0/1` =
  78→150 px from shore, normalized by the same bay widening the colour
  bands use — un-normalized it cut Kāneʻohe's widened lagoon off
  mid-gradient as a dark wedge). This is what fixed **Kahoʻolawe being
  sliced off by Maui's rectangle**: island bakes overlap (Maui over
  Kahoʻolawe 1872×501 px, over Molokaʻi 551×331) and opaque rects
  clobbered whichever drew first. Bakes now COMPOSITE — build_world
  stitches them onto a transparent canvas and runtime just works
  (slices all sit at depth -1; alpha does the rest).
- **The overview IS the ocean at every zoom** (beyond ~2 km offshore
  only the backdrop is visible), so `build_world.paint_ocean()` paints
  the sea ONCE on that one continuous canvas: broad depth mottling,
  the two real shelves (Penguin Bank, the Maui Nui saddle — drawn from
  lon/lat), and a faint far-ocean vignette. Amplitude fades to zero
  within ~20 ov-px of any island so the bakes' flat-`deep` fade rims
  never seam, and at the canvas edge so the camera background matches.
  The "no position-dependent grading" rule for BAKES still stands —
  the overview is one canvas, it has no rectangles to draw.
- **Painterly water is a smooth piecewise-linear gradient** through the
  same band stops (last stop 66 px, inside band_dist's 68 px cap, so
  far water truly reaches flat `deep` before the alpha fade), with a
  SMOOTH wobble field — per-pixel dither over a continuous ramp made
  every water pixel unique and doubled the PNG weight. Crisp surf line
  at the shore, soft swell glints over lagoon depths, bay reef patches
  fade with bay influence (a hard `bay > x` cut drew the bbox corner as
  a crease). A medial-axis crease where two shores' distance gradients
  meet is rounded by blurring `dw` (~12 px). `--style pixel` keeps its
  original stepped, dithered bands and hard reef stamps verbatim.
- MAP_V is at **8** for this bake set (7 was the rainfall/ocean bake).

## Tax-flow presentation (2026-08-21)

- Motes are **streaks** (same day, superseding the comet: the
  ball-and-tail head "looked like sperm"): one thin tapered LINE per
  stream — alpha ramps toward the head, near-constant ~2px thickness,
  a short bright dash for the tip, nothing round anywhere — drawn
  pointing +x, rotated to `curve.getTangent()` each frame. Ambient
  alpha/speed budget unchanged — FEATURES.md "Visual language rules"
  still bind, and now record the one sanctioned exception:
- **Hover quantifies a flow** (user's call, same day): resting the
  pointer near a streak strokes its whole route (stops at t=0.95, same
  manners as the ribbons) and pins a DOM receipt (`#flow-tip`, z 20 =
  under the overlays) to the cursor — area name, ZIP, $/yr, share of
  its stream. `updateHover` in main.js: acquire on the nearest LIVE
  mote (motes carry `m.p`, paths carry zip/area/w), then STICKY to the
  curve so the moving streak doesn't drag the tooltip; suppressed
  while any `.ovl` is open (a stale pointer under a panel must not
  hold a tip). GET rows have no `area` — borrowed from the income
  file's zip→area map — and the GET tip carries the modeled-spread
  caveat line, per the measured-vs-modeled rule. Per-path dollars are
  just `p.w` ($M in BOTH streams: taxM / getM); share = `w / wTotal`
  (now stored on the stream). The tip element is created once and
  reused across scene restarts.
- **"✦ Streams" highlight toggle** (`#hi-chip`, OFF by default,
  localStorage `cq-flow-hi`): additive ribbons under each stream's top
  8 routes drawn in three segments that DIM toward the hub and stop at
  t=0.92 (90 full-length ribbons converging would white the Capitol
  out), tinted breathing glints on those routes' sources, a soft
  arrival pulse at the Capitol, motes ×1.5 rate / 0.68 alpha (pool
  420). Ribbons are stroked in world px and re-stroked when the zoom
  bucket (`round(log2(zoom)*3)`) changes; `redrawHi` is the single
  clean-up/redraw path and every toggle (streams AND highlight) goes
  through it.
- The Capitol sprite lost its reflecting pool (user's call; plaza
  widened to keep the apron) — `capitol.png?v=2` in BOTH loaders
  (Phaser preload + the money overlay's SVG hub image).

## Session overlay cinema pass (2026-08-21)

The tail of `site/css/style.css` ("THE CINEMA PASS") upgrades the
narrative screen's material: blurred-map scrim, lit panel + film grain,
banner art mask-faded into the page, choice/Continue plates with a
hover sheen, glowing metric cards, foil masthead, gold scrollbar.
**Everything in it is scoped to `#session-overlay`** — money/policy
overlays keep the plain house plates — and it re-states no layout and
none of the documented decisions above (nameplate voices, transcript
ageing, mast geometry). Sheens are disabled under
prefers-reduced-motion.

## The Capitol grounds scene (2026-08-22)

`tools/render_capitol.py` bakes the Capitol interior — **the gallery
ring above the rotunda** (user's call 2026-08-22: "the view is going
to be the gallery/railing area"; an aerial-exterior version was built
first the same day and replaced) → `site/assets/map/capitol_scene.png`
+ `site/map/capitol.json` (spawn + hotspots, px in image space).
Composition: a NARROW low-gallery balcony (one storey above the
chamber level — user's call, "lower levels, with narrower walkways")
on the overlay's ink ground, railings at the open well, the sunlit
courtyard one storey down, the chambers present ONLY as flared
lava drum walls at courtyard level (user-corrected 2026-08-22: the
cones are NOT visible from the balconies — the galleries wrap
straight around them; an earlier version drew glowing cone caps in
the well and was wrong), koa doors on the mauka walls of
THREE levels — the courtyard, the gallery ring the player stands on
(**level 2, the SENATE's floor**), and **level 3, the HOUSE's floor**
above it (a third storey landed 2026-08-24, reversing the standing
one-level rule; its chamber ownership was settled 2026-08-27 — see
"THE FLOOR HAS AN OWNER" below) — with open HALLWAY MOUTHS and recessed
ELEVATOR LOBBIES branching deeper into the building (corridor_at:
dark opening, floor running in, steel doors + call light for a
lift), and exit stairs at the makai corner. The courtyard has no
dark breezeway splotch and no ground-level doors (both removed,
user's call).
- **The third level is RECESSED, and the recess IS the feature**
  (`paint_upper_level`). A multi-floor stack was drawn 2026-08-22 and
  rolled back the same day because two rows of doors on one plane read
  as a motel elevation — nothing in the section said the upper floor
  was BEHIND the lower one. Stepping it back a full bay means the
  court widens as it rises, so you see the upper walkway's FLOOR and
  not just more wall, and the levels stay legible from a fixed camera.
  Rules that must survive edits:
  - `LVL2_IN == A_OUT` and `LVL2_Y ==` the lower slab's top, so the
    terrace TILES exactly — the upper rail stands on the lower wall's
    own line and there is no seam to hide. Change one, change both.
  - **Only the two MAUKA runs exist.** A makai half would stand
    between the camera and the room, which is what the dollhouse cut
    exists to prevent one storey down.
  - **The SLICED ENDS are not decoration.** Stepping back means the
    building carries mass between `A_OUT` and `LVL2_OUT` — the offices
    behind the lower wall — which nothing had ever drawn, because one
    storey down that mass is hidden by the wall itself. At the ʻEwa
    and Diamond Head corners the runs stop and the hole shows: without
    the cut faces the upper level's outer half hangs over bare ink and
    reads as a cantilever. Any further level needs its own.
  - **Both HALLWAY MOUTHS sit on the Diamond Head run** (user,
    2026-08-24): one hard against the top point, one past the
    rightmost door, so the recesses BRACKET the run. Mid-wall portals
    punch a hole through the door rhythm exactly where the eye travels
    along the wall. The ʻEwa run is all doors.
  - **THE GALLERY LEVEL BELOW IS THE SAME, RUN FOR RUN** (user,
    2026-08-24: "I wanted the hallways on second floor to be same as
    third floor" — this reverses the note that said it deliberately
    didn't, and it means the SAME RUN, not a mirrored one: a first
    pass bracketed the ʻEwa run down here on the theory that portals
    shouldn't stack between storeys, and that was not the ask).
    Both of its portals sit on the DIAMOND HEAD run — a hallway hard
    against the top point (t 0.07, same as the storey above) and the
    governor's lift lobby past the rightmost door (`gov`, t 0.94) —
    and the ʻEwa run is all doors. It used to carry a hall at ʻEwa
    0.45 and a lift at Diamond Head 0.47, both mid-wall. `gov` is a named hotspot, so it CHANGED RUNS to become
    the closing portal; the re-spacing moved the other named doors
    too (`wam` .57→.40, `finance` .35→.32, `house` .80→.70). Hotspot
    px come out of the bake, so nothing is hand-maintained — but
    CAP_V must be bumped or the stale JSON points at the old doors.
  - Painted far-to-near WITHIN each run — wall, then the walkway
    standing in front of it, then the rail at its inner edge. On the
    mauka side the OUTER ring is the FAR one, which is the opposite of
    the intuition that "outer" means "nearer".
  - **The lower wall carries NO white top-face strip any more**
    (2026-08-24, user: "the white strips for third floor railings are
    completely wrong"). The old dollhouse top-face polygon — up(e,72)
    offset (±9,-5) in paint_walls — was written for a wall with sky
    behind it; with the third level standing there, its slanted
    parallelogram covered ~10px ABOVE the slab line and painted white
    over the upper rail, so it read as a gold pinstripe in a white
    belt (measured on the staged bake). The terrace floor is what
    meets the slab line now.
  - **A NEAR-WHITE MEMBER TAKES `white_f(f)`, NEVER THE RAW FACE
    FACTOR** (2026-08-27, user: "the white trim for third floor
    railing looks off. you cant even see the spokes, it's all
    white"). `shade()` clamps at 255 and the fluted band's field
    (`FLUTE_FIELD` #ece6d4, lum 230) has almost no headroom, so the
    third level's ʻEwa run at **f = 1.10** landed the field on 253
    and the highlight line (#f7f3e6) on 268 — both clamped to the
    same flat white. Measured on the shipped bake: **fourteen
    identical rows straight through the band**, top highlight and
    base seam gone, against the Diamond Head run's field 222 /
    groove 145. The two halves of ONE railing were rendering as two
    different objects, and the ʻEwa half genuinely was a blank white
    ribbon — the flutes were drawn, they just had nothing to sit
    against. Now 230 / 150 vs 222 / 145. Rules:
    - **Cap the factor; do NOT darken the base white.** The band's
      230 is measured against the court floor (the executive-floor
      photo puts the white band at 1.79x the open paving, which is
      what sets `COURT` at 130), so it has to survive.
    - **On a material at the top of the range, light direction has
      to be carried by something that is not VALUE** — here the koa
      cap, which is dark, has headroom, and still takes the full
      `f`. Pushing a near-white field past the ceiling does not make
      it brighter, it makes it flatter.
    - `white_f` is a no-op wherever `f <= 1`, which is every other
      fluted band in the room (gallery runs 1.0 / 0.88, the makai
      fascia, both wings). Verified by diffing the bake: **0.57% of
      the canvas changed, all of it on the ʻEwa side** (x < 840,
      y 313-607) — the level-3 slab band and its parapet, nothing
      else. Hotspot JSON byte-identical.
    - **The clip was pre-existing, but `SS 2 -> 1` is what exposed
      it.** At SS 2 the LANCZOS downsample mushed BOTH halves, so
      they looked equally soft; at full resolution the Diamond Head
      half came up crisp and the clipped half did not, which is what
      made the mismatch obvious.
    - Judged at 1:1, not magnified — with the ceiling at 1.6 the room
      now renders at zoom ~1.05, so scene px are display px and
      **1:1 IS game scale**. The old "judge on the downscaled bake"
      rule still applies to anything that ships at SS 2.
    - **The clip was only HALF of it, and the claim that fixing it
      alone made the verticals read was WRONG** — corrected the same
      day, see the groove rule below.
  - **THE GROOVE IS A SHADOW GAP, NOT A TINT** (2026-08-27, user:
    "inspect the railing/fence. it's all white. dont you see it").
    `FLUTE_GROOVE` shipped at #9d9683 — lum 150 against the band's
    230, a ratio of 0.65, which is a light-grey pinstripe on
    near-white and reads as no spokes at all. It is #45423a (lum 66)
    now, at `FLUTE_W` 2 on `FLUTE_PITCH` 6: a DARK gap with a 4px
    white fin, so the band still reads as white trim. The well
    railing that always DID read as a railing runs its pickets at lum
    52-68 — that gap was the entire difference between the two, and
    every railing in the room now speaks the same language.
    - **JUDGE THIS ON THE GAME CANVAS, NEVER ON THE SOURCE PNG AT
      1:1.** This is the rule the whole episode exists to write down.
      The runtime resamples the bake at zoom ~1.047 through a LINEAR
      filter, which blends a 2px groove into its white neighbours.
      Read off the live canvas the shipped band came back as
      `[174,150,198,230,230,230]` — the groove is in the data and
      invisible on screen. A 1:1 crop of the bake shows it crisply
      and is a LIE about what the player sees; reading one is exactly
      what made the first pass call this fixed when it was not. Grab
      pixels with `canvas.getContext('2d').getImageData(...)`, or
      `drawImage` a sub-rect into a scratch canvas and look at that.
    - The old "judge on the DOWNSCALED bake" rule (written for SS 2)
      is the same rule; `SS 1` did not retire it, it only changed
      WHERE the resample happens — from LANCZOS at bake time to
      bilinear at draw time. Either way, never judge at 1:1.
    - Swept before choosing (`FLUTE_GROOVE`/`FLUTE_W` are
      module-level for exactly this, same pattern as `COL_FACETS`):
      at w2, #8a8271 is still white, #6e6a5c is faint, #585446 reads,
      #45423a is crisp. w3 gives a 50/50 bar that reads as a
      balustrade too, but it turns half of every band dark and the
      fascia stops reading as white trim — rejected on the
      whole-building view, not on a strip.
    - This constant drives EVERY fluted band (both parapets, both
      slab bands, the makai fascia), which is correct: the user's
      complaint was the room's white bands generally, not one rail.
    - Still no pickets on the third-floor rail — the 2026-08-24 call
      stands. The spokes read now because the groove is dark, not
      because the parapet became an open balustrade.
  - **The third-floor rail is a SOLID white fluted PARAPET with the
    koa cap on TOP — no pickets** (2026-08-24, user: "the pickets for
    the railings are showing over the white, which is incorrect").
    Open pickets cannot work up here: the terrace strip behind the
    rail thins to NOTHING toward the ʻEwa/Diamond Head ends (an iso
    diamond offset outward moves edges up-screen only near the apex),
    so the dark bars stood against the pale wall base and the white
    slab band — pickets painted over white. The executive-floor
    photo's upper balconies are white fluted parapets anyway; the koa
    cap riding the TOP edge of the white band is what says "railing"
    at this distance. The WELL railing keeps its open pickets — the
    dark drop behind it is what they read against.
  - **Bay columns are CLEARANCE-PLACED, both levels** — and since
    2026-08-25 they also keep off the FLUSH columns, which are the
    same wall face and would otherwise take a bronze stripe down
    their middle (`bay_columns`;
    2026-08-24, user: "many of the columns in general are clipping
    into other elements"). The old fixed i/8 grid landed bronze
    columns inside door architraves all along both walls — doors
    draw after columns, so every collision left a sliver poking out
    of a frame. Columns now sit at the corners and at feature-gap
    midpoints, and only where they clear the neighbouring frames
    (FEAT_HW + 6px); a column that cannot clear its gap is not
    drawn — on the door-dense gallery runs the koa leaves carry the
    rhythm alone.
  - No form mottle on purpose: most distant thing in the room, and
    skipping it keeps the level off the shared `rng`, so adding a
    storey cannot reshuffle the level below's wall texture.
  - **THE COURTYARD STOREY IS THE TALLEST ONE, and `DROP` is the
    number** (user, 2026-08-24: "the two floors are very tall in
    comparison to the rotunda; the rotunda floor should look much
    taller because it is"). DROP was 64 against 72px office storeys —
    the ground level read SHORTER than a floor of offices, so the
    section looked like three equal decks and the whole room read
    squashed. It is 100 now: the real court is a double-height
    arcade whose piers run to the underside of the gallery slab.
    Everything in the well is expressed against DROP, so it is one
    edit — but two things ride on it:
    - **The ceiling on DROP is the WELL, not taste.** The courtyard
      floor slides DOWN as the court deepens, so our own slab starts
      cutting the floor medallion — the composition's focal object.
      The bound is `hypot(62/288, 32/144) + (DROP-12)/144 <= 1`
      against the well diamond, i.e. ~100. At 108 the medallion was
      sliced and sat jammed against the near rail. Deeper than the
      bound means giving up the medallion; that is the trade.
    - **Anything standing ON the courtyard floor has to be re-placed,
      because a deep court hides its own near half** under the
      gallery slab. The kukui pair that used to stand below the
      medallion now FLANKS it (the far pair is unmoved), the chain
      ring came in to 72x37, and the arcade's arch head and rise are
      FRACTIONS of DROP (0.47 / 0.11) instead of a fixed 30/7 under
      the slab, or the heads bunch at the top of a tall wall with a
      blank field hanging under them. A pale stone PLINTH along the
      wall foot is what tells you that tall dark wall meets a floor.
  - **THE COURT'S TWO WALLS ARE NOT THE SAME WALL** (2026-08-24,
    from the user's own copy of `Interior of Hawaii State Capitol
    from Executive Floor.jpg`: "show the glass facade in particular,
    and the opening to the outside as well on the left wall"). Both
    runs used to be the same koa-slat screen, which is why the court
    read as a sealed box. Now:
    - **Diamond Head = the GLASS WALL, in TWO sections**
      (`court_glass`; reworked 2026-08-24 from the HABS courtyard
      photo, glazing re-cut 2026-08-25 from the executive-floor one).
      The CURVED section is the chamber drum's glazing bulging into
      the court, and on a flat iso face the curve is carried by cues
      that only work TOGETHER: mullions spaced by ANGLE, the SILL
      BOWING DOWN toward the viewer (9px, head 3px), and the
      sky-reflection band following the bow. Any one alone reads
      flat; the first pass had evenly spaced bars on a straight run
      and did. Four things about the bars, all from the photograph
      (user, 2026-08-25: "fix the mullions on the curved glass"):
      - **It is ONE curtain over the whole rest of the run**
        (`DOOR_TB` → 0.98). It used to stop at 0.62 with flat filler
        panes beyond on a sparser pitch, so the wall read as
        "mullions over the left third, then a dark slab". Past the
        well limit (t ≈ 0.66) our own slab eats the sill, so the bow
        out there costs nothing and is never seen.
      - **NO TRANSOM RAILS.** Two horizontal arcs used to cross the
        glass at 0.42/0.72. The photograph has none — bars run head
        to sill unbroken, and the horizontals were what made this
        read as a shopfront rather than a chamber drum.
      - **The spacing is ASYMMETRIC.** The old map was
        `0.5 - 0.5*cos(pi*u)`: dense at BOTH ends, open mid-arc — a
        half-cylinder seen FACE-ON. This drum is seen OBLIQUELY, so
        the bars compress monotonically toward the far (mauka) end
        and open toward the near one. Spacing goes as cos(theta)
        about the point where the drum faces the camera, and that
        point is at the near end of the visible arc. The sill bow
        now follows the SAME cos(theta), so the two cues agree —
        before, a symmetric bow was arguing with the mullions.
      - **20 bays at 2px, and that is the picket rule again.** At
        SS 2 a 1px bar is half a display pixel and LANCZOS renders
        the run as a bluish haze instead of glazing. 30 and 24 bays
        were both baked and both mushed at the compressed end
        (`TH_A` −64° puts the tightest gap at ~44% of the mean, so
        30 bays lands at 2.1 DISPLAY px). Judge this on the
        downscaled bake, never at 1:1.
      The section to its LEFT is the chamber's GLASS
      ENTRANCE DOORS: paired glazed leaves under a wide transom in a
      pale surround (Senate-entrance photo). Keep the glazing
      NEUTRAL: a teal pass read as water, not glass. No plinth — the
      glass runs to the floor.
      NB an intermediate pass replaced this whole layout with an
      open colonnade on both runs and the user rejected it outright
      ("you just messed the whole thing up") — the LAYOUT (glass on
      Diamond Head, one open bay on ʻEwa, koa slats elsewhere) is
      settled; only the rendering inside each section was wrong.
    - **ʻEwa = fully OPEN — a breezeway, not a wall with a bay**
      (`court_opening` + `OPEN_BAY` (0.03, 0.97); 2026-08-24,
      breezeway photo, user: "the slats shouldn't be on that
      entrance side. that's also open"). The koa slats, the arcade
      arch and the stone plinth are all DELETED — they were dressing
      on a wall that is not there. What shows through the whole run
      is the HABS/breezeway view out: sky GLARE, far towers on a
      shaded tree line, sunlit plaza, palms drawn as trunk + FAN
      (a disc on a stick is a street lamp). TWO rows of piers make
      the depth: the near pale row at 0.18/0.5/0.82 (drawn by the
      wall loop) and an outer silhouette row at 0.33/0.67 inside the
      view — offset from each other on purpose, or they read as one
      pier with a shadow. The broken silhouette is what says
      "outdoors"; flat colour bands did not.
    - **The courtyard's BIG STONE PLANTER-BENCHES** (`planter_bench`
      in paint_well; 2026-08-24, user's atrium photo: "you also
      forgot those empty planters … the big benches/planters"): two
      low square stone boxes flanking the breezeway with a stepped
      bench ledge all the way around, and mostly EMPTY — bare soil
      with a few dry stalks, per the photo; one carries the
      courtyard's tree (HABS view). They replaced the four floating
      kukui canopies, which had no planters under them and read as
      bushes growing out of pavement. Keep the empty one empty —
      that is what the photograph shows.
    - **THE SMOKESTACK IS A HALF-CONE CUT BY THE BLANK WALL'S PLANE,
      AND THE BLANK WALL IS THE COURT'S CORNER** (`smokestack` +
      `court_panel`; settled 2026-08-25 by the user's courtyard
      photograph plus two corrections: "it's a half-cone cut by the
      wall plane… you'd only be able to see a sliver of the cone in
      this perspective", then "do you see that blank wall it's
      attached to? imagine that wall is part of the CORNER formed
      with the glass facade"). SEVEN passes failed in sequence — a
      full cone free-standing, straddling the apex, wrapped by the
      balcony, abutting the wall, then a half-cone bonded to a
      MID-FACADE buttress with glazing running on past it — because
      the SHAPE was wrong, then because the WALL was: the wall is
      not a buttress in the middle of the glass, it TERMINATES the
      facade. In the photograph the cones stand in the open lanai at
      the chamber volume's corner; in this room's language that is
      the court's mauka corner, where the glass facade meets the
      ʻEwa plane.
    - **THE ASSEMBLY, one anchor**: everything hangs off
      `PIER_U0 = -A_IN` — the blank wall's ʻEwa flank sits exactly ON
      the ʻEwa plane, so wall + glass form the court's corner. The
      cone is bonded to that flank (`STACK_U = PIER_U0 - CUT*R`, axis
      WEST of the plane), which puts its body around the corner IN
      THE OPEN BREEZEWAY — drawn over the bay backdrop, before the
      wall — and only its sliver peeks back into the court past the
      corner. The door section attaches to the wall's other flank
      (`DOOR_TA` derived), and there is NO filler glazing between
      wall and apex any more: a pane there would be glass standing
      where the facade has already ended, which is exactly the
      mid-facade-buttress read the corner fix removed. `PIER_DEP`
      is NOT free — it must reach the cone's widest visible point,
      v = STACK_V + sin(acos(CUT))*R, or the bond seam shows past
      the wall's front arris; since 2026-08-25 it is DERIVED from
      exactly that expression, so it can never drift again.
    - **SLID IN AND TUCKED UNDER THE 2ND FLOOR** (2026-08-25, second
      correction: "it should look like it's under the 2nd floor…
      imagine that the wall is slid in more (also sliding the
      attached stack in more)"; pushed further the same day on "slide
      the wall in even more"). `ASM_IN` (1.20) slides wall AND
      cone together in -v, preserving the bond; the mass that slides
      behind the facade plane is inside the building and simply not
      drawn (the wall still draws from v = -A_IN), so the slide
      reads as LESS protrusion, never as a wall standing in front of
      the glass. And the cone's top is SHEARED BY THE GALLERY SLAB:
      it runs tall (h = DROP - 14) and smokestack() clamps every
      point to the fascia band's bottom line
      (y = apex + 18 + |x-CX|/2), so the courses die under the slab
      and the stack reads as continuing above, off-stage. The mouth
      rim is GONE — a visible rim means the stack ended in the well,
      the floating read this replaced. Don't shorten h back to "24px
      under the hole edge"; the shear line IS the top.
    - **`ASM_IN` HAS A HARD CEILING, AND IT IS THE CONE** (measured
      2026-08-25). Only the wall's DEPTH answers to the slide — its
      u position never moves — so "slid in" means `PIER_DEP`
      shrinking, and PIER_DEP hits 0 at
      `0.10 + sin(acos(CUT))*R` = **1.3557**, where the front face
      would sit mauka of the facade plane (the corner mass standing
      behind its own glass, bond seam showing). There is an assert on
      it. The PRACTICAL ceiling is lower: the depth is spent entirely
      on the RIGHT FLANK, which is 16*dep scene px = **8*dep DISPLAY
      px** after the SS downsample — 1.20 leaves 1.2 display px (the
      last value with any depth at all), 1.30 leaves 0.4 and LANCZOS
      erases it, so the corner flattens to a pale band instead of a
      projecting mass. Sliding further than 1.20 means shrinking the
      CONE or deepening `cut`, not nudging this number.
    - **THE ANGLES ARE FORCED BY THE PROJECTION, not chosen.** Radii
      are PLAN units so `iso()` places every point and the 2:1
      foreshortening comes out for free. With the cut plane at
      u = u0 and the cone bonded to its west flank:
      - retained solid is cos(theta) <= CUT, i.e. theta in
        (acos(CUT), 360-acos(CUT));
      - a face is turned toward this camera only where its plan
        normal has a positive dot with the view direction (1,1)/√2,
        i.e. cos+sin > 0, i.e. theta in (-45, 135);
      - the intersection at CUT 0.5 is **theta in (60, 135)** — a
        crescent lying entirely LEFT of the axis. That is the
        sliver, and the flat cut face is bonded against the wall
        and never visible.
      So it draws as a narrow tapering crescent, NOT a tower: cut
      edge right (dying behind the corner wall), silhouette left,
      sagging course arcs between, top sheared by the slab (no rim).
    - **`cut` IS THE ONLY DIAL THAT CHANGES HOW MUCH SHOWS.** It is
      where the panel's face slices the cone as a fraction of the
      radius from the axis: 0.0 is a true half-cone, positive means
      the cone protrudes past the panel's edge. The visible arc runs
      from acos(cut) to 135°, so a true half-cone leaves 6.6*R px —
      about THREE display px here, not a shape anyone can read.
      Moving or resizing the cone cannot substitute: the visible
      FRACTION is fixed by the projection. Shipped at cut 0.5.
    - **The value FLOOR of the shading matters more than its range.**
      The silhouette edge sits against the court's near-black
      glazing; at 0.72 it sank in and the crescent read as a smudge.
      It is 0.86 now, with a 2px keyline on the silhouette so the
      cone separates from the glass behind it.
    - **It belongs to the ROTUNDA FLOOR and nothing else** (user:
      "it's only for the rotunda floor. not for floors above it").
      The gallery and Senate corners stay SHARP, their slab edges
      STRAIGHT, walkways unbroken. **A pass that rounded the court's
      mauka corner — bending the fascia into a ∨, wrapping the
      balcony around a drum, dropping the corner post — is exactly
      what the photograph rules out.**
    - Surviving cone rules: batter power 1.35; coarse ~8px course
      arcs drawn 2px wide so they survive the SS downsample (they
      carry the wrap); **no per-tile detail and no vertical joints
      at all** — a photo-true tile is ~1.5 DISPLAY px here, under the
      sampling pitch (the wall the railing pickets hit), so tiles
      resolve to grey mush and full-height joints become FLUTES;
      per-COURSE weathering only.
    - The photograph shows a PAIR flanking the entrance; only the
      near one is drawn, per the standing one-stack call.
    - **The pier between the doors and the curve is an explicit
      drawn thing, and it LANDS** (same day: "the middle column
      going through the glass also isn't meeting the ground"). It
      used to be implied — the doors' right surround against the
      curve's dense left mullions — and the curve's sill shadow cut
      across its foot, so it hung in the glass. It is drawn LAST in
      court_glass, proud of both neighbours: full height, lit head,
      shaded flank, and a darker plinth block at the bottom that the
      floor line crosses.
    - **There is only ONE, and no companion at the far end of the
      glass** (user, same day): from this vantage the building hides
      it anyway, and the pass that added one at t 0.65 stood it
      between two courtyard piers, mid-colonnade, where it read as a
      chimney dropped into the middle of the arcade.
    - **Everything on the Diamond Head run stops at t ≈ 0.65, and the
      WELL decides that, not composition.** The wall's floor line is
      only inside the hole up to t = 0.66 (solve
      `t + |144t-46|/144 <= 1` against the well diamond), because the
      court floor is a storey down and our own slab eats the near end
      of every wall. So the curved glass ends at 0.62, and beyond it
      are flat filler panes whose upper half is all that ever shows.
      Same arithmetic is why the ʻEwa run's own corner shows nothing.
      The smokestack sits well inside that limit (its axis is at
      t ≈ 0.11), so the mask never reaches it.
    - **The flat pale piers pasted on the ground wall are GONE**
      (superseded 2026-08-25 by the full-height columns below). The
      2026-08-24 rule that produced them — "the courtyard piers keep
      off the glazed run", from "many of the columns in general are
      clipping into other elements" — was about piers drawn ON the
      wall plane, where a collision left a sliver poking out of a
      frame. It does not govern the real columns, which stand a bay
      in FRONT of the wall and occlude it honestly.
  - **THE WALL BENCHES ARE BACK, AND THE CONTACT PROBLEM IS SOLVED**
    (`bench_at`; user, 2026-08-26: "remove some of the inert doors and
    put dark wooden benches next to them"). The 2026-08-22 note said
    don't reintroduce them without solving why they read as "brown
    bars floating on the railings". Both halves of that were measured
    on the executive-floor photograph:
    - **CONTACT IS OVERLAP, NOT PROXIMITY.** The seat's back edge
      sits ON the wall's foot line and the bench OCCLUDES the bottom
      of the wall face — so it is painted after the wall and after
      the doors. A bar that merely stops near the wall has nothing
      holding it there.
    - **AND IT IS FOUND BY ITS SHADOW.** The bench body measures 0.89
      of the walkway it stands on — 11% DARKER than its own deck — so
      it never separates from the floor by value. What separates it
      is the contact shadow at 0.57 of the floor. Draw the bench and
      skip the shadow and it floats again. But the shadow must read
      as a SHADOW, not a hole: at 0.48 of the tile it merged with the
      bench's own front face and the pair read as one dark blob.
    - **IT IS NOT KOA-COLOURED.** The real bench measures R-B 9
      against koa's 53. Ours ships at R-B 7-17 — dark wood, as asked,
      but nowhere near the warm quarry-tile deck (R-B 43) it stands
      on. A koa-hued bar on a koa-hued deck is the other half of why
      the last attempt vanished.
    - Proportions are measured: length 1.5 office-leaf widths, seat
      8-9 px, depth equal to the height, BACKLESS, and no daylight
      under the seat. The render exaggerates height ~2.8x against
      plan, so the top plane is only ~3 px of screen y and the bench
      is mostly front face — the lit lip carries the whole object in
      two px and must never be feathered.
    - **On the UPPER level benches are drawn after the walkway, not
      in the feature loop**: up there the walkway is painted AFTER
      the wall, so a bench drawn with the doors ends up underneath
      its own floor, taking its contact shadow with it.
    - Count is measured too — a full run of the photograph carries
      three doors and ONE bench, about one per two door bays, never
      one per bay. Six ship, across four runs.
  - **`place_feats` DROPS ONLY FILLER, AND IN ORDER**: unnamed office
    doors first, then unnamed benches, then nothing. Portals and the
    corner ALCOVE are pieces of the building's plan, not dressing —
    the alcove was silently dropped the first time this ran, which is
    what the rule exists to prevent.
  - **NO PALE BASE STRIP ON THE UPPER WALLS** (2026-08-25, user: "get
    rid of that white base strip too"). `q(0, 8, POST)` put a white
    skirting under every door on both upper storeys; the photographs
    have nothing like it, and the walkway's own slab edge is what the
    wall meets. `POST` is gone with it — it had no other use.
  - **THE GROUND FLOOR IS A LOGGIA AND THE COLUMNS RUN FULL HEIGHT**
    (2026-08-25, from the executive-floor photo — user: "fix the
    column taper and the loggia setback… those columns go all the way
    up to top of third floor"). Until this the ground storey was a
    flat elevation with straight posts stuck to it. Rules:
    - **`GND_BACK` sets the wall back; the FASCIA does not move.**
      The fluted band is our own slab's edge and stays on the well
      line — drawing both off one edge is what kept the storey flat.
      The smokestack assembly is the corner of THAT wall, so it is
      anchored to `GND_OUT` and rides the set-back; the ASM_IN slide
      is still measured from the facade, so its tuning survives.
    - **The set-back is free geometrically — paint_well already
      clips to the hole, and that mask is exactly the right
      occluder.** A point at height dy below the gallery casts to
      floor coords `(u + s, v + s)` with `s = (DROP - dy)/16`, so the
      wall shows from its foot up to `dy = DROP - 16*GND_BACK` and
      the slab eats the rest — which is what the photo shows. **This
      is the trade and it is the only one: recess is bought by
      hiding more of the glass wall.** 1.6 was too shallow to read
      (a 13px band, wholly covered by the overhang shade); 3.2 buries
      the glazing. Shipped at 2.4 — wall visible to dy 61 of 100.
    - **Moving the wall buys NOTHING without shading the loggia
      floor.** The strip behind the columns came out the same bright
      stone as the open court, so it read as a wall further away and
      not as a recess. One band at `shade(COURT, .72)` between the
      A_IN and GND_OUT floor lines is what makes the set-back exist.
    - **The taper is LINEAR (`COL_FLARE` 1.0), and that is
      measured.** A power curve was tried first to put the swell at
      the head; it cannot work, because a column is only ever seen in
      short stretches — the loggia, then the band of each upper wall
      between one balcony's cap and the slab above — and an exponent
      that flares one flattens the others. Straight batter gives
      every stretch ≈1.4, which is the per-storey taper the photo
      shows. **The full-height 6→14
      ratio is not what the eye gets; the per-stretch ratio is.**
    - **THE COLUMN STANDS FREE ONLY ON THE GROUND FLOOR. ON THE
      SECOND AND THIRD IT IS FLUSH IN THE WALL** (user-corrected
      2026-08-25: "you're misreading the columns. they should be
      flush with the walls on the second and third floors"). Follow
      one stack down the executive-floor photograph and it is not
      ambiguous: a tapered shaft standing out in the loggia, then
      above each balcony a pale strip lying IN the wall face between
      the doors, with the walkway and its parapet crossing in front
      of it. The ground storey is the only one whose wall is set back
      far enough for the column to come out of it. Two earlier
      readings are retired — one broke the shaft at every parapet,
      the next ran it unbroken up the COURT EDGE and put nine
      free-standing poles between the camera and the room.
    - **A column is drawn in THREE pieces on three surfaces and
      `col_hw()` is why they line up**: free-standing in paint_well's
      clipped layer (`court_column`), then flush in the gallery wall
      and flush in the Senate wall (`wall_column`, called from
      paint_walls and paint_upper_level BEFORE the doors and long
      before the walkway). Separate taper maths in any of them would
      step at a join, and the middle of every storey is hidden, so
      the taper has to run through the parts nobody sees.
    - **The upper strips are drawn at the SAME SCREEN X as the shaft
      below, and that is a deliberate cheat.** The walls really do
      stand a walkway further back, and a true projection would step
      each strip ~20 display px sideways per storey — three
      unrelated marks instead of a column. The storey's own floor and
      slab fix the strip's vertical extent, so screen x is the only
      thing tying the pieces together and it is the one that has to
      be honest. `col_xs()` is the single source all three read.
    - **THE STRIP'S SURFACE IS A TWO-FACET STEP, AND EVERY NUMBER IN
      IT IS MEASURED** (`COL_FACETS`; rebuilt 2026-08-25 after the
      user: "the columns appear to lose their shape as they get
      higher. they look less like 3d objects, more like splotches").
      It had shipped as ONE flat fill — 13 identical pixels, self-
      contrast under 1%, at 0.86 of the white slab band where the
      photographs put a flush column at 0.48. The real profile is a
      narrow reveal, a ramp, a WIDE nearly-flat lit facet (~60% of
      the width), ONE hard arris, a shadow facet at ~0.6 of the lit
      one, and a keyline. Three rules survived measurement and a
      four-lens judge panel and must not be undone:
      - **No pixel at either outer edge is brighter than the body.**
        Not one, in either photograph, across eight columns sampled.
        The old 1px #ddd6c0 arris was brighter than everything in
        both photographs; a bright edge is a projecting-object cue.
      - **The keyline is darker than the WALL**, not merely darker
        than the column (#3a3732 is 0.78 of CONC). A midtone edge is
        what makes a strip look pasted ON a surface rather than cut
        INTO it — the old #8a8272 was 1.9x the wall.
      - **The shadow facet is NOT floored to the wall.** A real flush
        column's darkest sample measures 1.5x its wall (#6a655a is
        1.44x CONC). Darker than that and a quarter of the strip's
        width disappears into the concrete — which is exactly how the
        rival "storey-ramp" candidate failed.
      The strip is FLAT up its height (the photographs are flat to
      3-8%); the 5% head droop is all the vertical variation there
      should be. The loggia shaft keeps its own three-tone modelling
      and both keylines — it is a solid standing in the open.
    - **AND IT GETS DARKER AS IT RISES** (`COL_DIM_UP` 0.78). Scaled
      to the white slab band as a common white, the photographs put
      the flush column's lit face at 0.67 on the second floor and
      0.48 on the third, while the WALL beside it gets lighter with
      height. The bake did the exact opposite — the third-floor run
      carries f = 1.10, so the topmost strip was the widest AND the
      palest thing in the room. That, not the cross-section alone, is
      what "as they get higher" was pointing at.
    - **The sweep harness is worth rebuilding if this is ever
      retuned.** `COL_FACETS`/`COL_EDGE_*`/`COL_CAP`/`COL_DIM_UP` are
      module-level ON PURPOSE so a variant is a monkeypatch plus a
      re-render (0.3s) into a scratch path, never an edit to this
      file. Judge every candidate on the DOWNSCALED bake: at 9 display
      px (2F) and 13 (3F) a band under ~2 scene px is mush, and two of
      the eight candidates tried looked best at 8x and vanished at
      1:1. `COL_CAP` (a capital flare / soffit shadow) is wired and
      shipped OFF: both photo agents looked for a flare and measured
      the real strip dead-constant in width right up to the slab.
    - **THE STRIP SHEARS WITH THE WALL — it is a parallelogram, never
      an axis-aligned rectangle** (user, 2026-08-25: "the perspective
      is off now… you also added white trim to base of the wall on
      second and third floors"). BOTH complaints were this one bug.
      Drawn with horizontal foot and head lines on a 2:1 face, the
      strip read as a pale panel pasted flat on a receding wall, AND
      its lower corner hung ~11px below the wall's own foot — a row
      of those along each storey is the "white trim" that appeared at
      the base. Foot and head run WITH the face (`sl = ±0.5`),
      exactly the way `door_at` already builds its frames. Anything
      else drawn on a wall follows the same rule.
    - **THE CORNER COLUMN STANDS ON THE WALL CORNER, NOT THE COURT
      EDGE** (`COL_APEX_U`; user, 2026-08-26: "the central column
      should be further back… the column goes up through there").
      Measured on the executive-floor photograph: the corner strip's
      foot sits at y=250.5 where the two wall faces' intersection
      extrapolates to 251.0 and 251.3 from the left and right runs —
      one full walkway width behind the railing, plumb under the
      strips above. The MID-RUN ground columns are not affected;
      those really are free-standing in the loggia with the koa wall
      a bay behind them.
      It costs nothing in screen x — u == v at the apex, so it stays
      at CX on every diamond — and it moves UP 38 scene px, after
      which paint_well's hole mask trims its top 38 px, so it emerges
      from under our own slab already deep in the corner.
      **It is drawn between `smokestack()` and `court_panel()`**, not
      with the other stations at the end of paint_well: the cone's
      axis is farther out than the shaft and the corner wall's face
      nearer, so that is the depth order at the apex. Drawn last it
      painted over the corner mass instead of standing in it.
    - **THE LITTLE ALCOVE** (`alcove_at`) — a shallow, full-height
      dark pocket beside the corner column, one per ʻEwa run. At
      every level the photograph carries a near-black zone about one
      door bay wide flanking the corner column, stepped at its edges,
      as dark as the loggia recess (13-20 against a wall of 33-45)
      and the only full-height feature of its kind on either run.
      Only the ʻEwa side gets one drawn: on the Diamond Head side the
      hallway mouth already IS the recess, which is exactly the
      asymmetry the user described ("next to the hallway"). It is
      SHALLOW — a pocket, not a room — so `corridor_at` is the wrong
      model and would spill a lit floor wedge across the wall face.
    - **A CORNER COLUMN, AND TWO TO A SIDE** (user, 2026-08-25, with
      a courtyard photograph: "there's corner columns, but then aside
      from that it's two columns to a side"). Three a side read as a
      picket fence. The corner column is FREE: the mauka apex is the
      one place every diamond shares a screen x (`x = 16(u - v) = 0`
      when `u == v`), so the same column lands on the court edge and
      on both walls at CX, and each run draws its own HALF of it
      against its own slope — the two meet at the fold as a chevron,
      which is what a corner column looks like in this projection.
      The ʻEwa and Diamond Head corners get none: a vertical line at
      the well diamond's W or E point meets the hole at exactly ONE
      pixel, so paint_well's mask eats any shaft standing there, and
      those two ends are the dollhouse cut anyway — a sawn face, not
      a fold.
    - **THE COLUMNS COME FIRST AND THE DOORS FILL THE BAYS BETWEEN
      THEM** (`place_feats`; the dependency used to run the other
      way). A free-standing shaft may pass in front of a door
      honestly; a strip lying IN the wall may not, and a collision is
      a pale sliver poking out either side of a frame — the
      2026-08-24 "clipping into other elements" complaint. Measured
      before the rewrite: with the hand-written schedules where they
      were, a strip of ANY width had zero clear positions on the
      Diamond Head run and one 12px window on the ʻEwa run. So each
      run is divided into `COL_N + 1` even bays and every wall lays
      its own doors out inside them.
    - **`GALLERY_FEATS`/`UPPER_FEATS` carry ORDER AND KIND, no
      positions.** t comes out of the geometry, so moving a column or
      changing `COL_N` re-spaces the doors instead of leaving a
      hand-tuned schedule lying against the new bays. Order is the
      contract — place_feats never reorders — which is what keeps the
      hallway mouths bracketing the Diamond Head run and the lift
      lobby closing it. A wall that runs out of room drops UNNAMED
      office doors from the far end, one at a time; the named ones
      are hotspots and never go. Current cost is ONE filler office
      door, off the Diamond Head gallery wall.
    - **The split is EXHAUSTIVE, not proportional** (`_lay_bays`).
      Bays and items are both ordered, so the whole question is where
      to cut the list into one contiguous group per bay — a handful
      of possibilities at these sizes — and the cut whose FULLEST bay
      is loosest wins, which spreads the doors instead of packing the
      first bay. A proportional-share pass with a repair loop was
      tried first and ping-ponged one door between two bays that
      could each hold it only without the other, then gave up and
      dropped it: three doors lost off one wall.
    - **`PIL_PAD` 0 / `FEAT_GAP` 6 are measured.** At 1 and 10 the
      Diamond Head gallery wall seated five of its eight features,
      and the cliffs are savage — one bay missing the hall-plus-office
      pair by 0.4px cascades into three lost doors. Zero pad is also
      what the photograph shows: architraves run tight against the
      columns, and a frame that rounds onto a strip by a pixel is
      dark koa over pale stone.
    - **THE COURTYARD FLOOR IS STONE PAVING, AND IT WAS TOO BRIGHT
      BY A THIRD** (`court_paving`, re-based 2026-08-25 from the
      executive-floor photo). Three separate faults, all measured:
      - **Tone.** `COURT` was #b3ac97 — lum 167 against the fluted
        band's 226, a ratio of 1.35, which made the court one of the
        brightest surfaces in the room and left the pale columns
        nothing to stand against. In the photograph the white band
        runs **1.79x** the open floor (165 vs 92), so the floor
        belongs at 226/1.79 = 126; it ships at 130. It is also far
        more NEUTRAL now — the photo's paving is R-B 10, where
        #b3ac97 was R-B 28 and read as sand. **The column/floor
        ratio was already right at 1.13 and is unchanged**: the
        error was entirely the floor's relation to the white bands.
      - **Texture.** It was one flat fill with a faint 2-unit grid,
        which reads as poured concrete. It is now large slabs, each
        its own tone, under a broad low-frequency drift. BOTH terms
        are needed: per-slab jitter alone is television static, the
        drift alone is a gradient with joints drawn on it. Amplitude
        is measured, not taste — the photo's open paving runs
        sd/lum 10-21% and the first pass at ±4% came out flat; it
        ships at 20.6%. Joints stay FAINT (hairlines you read the
        grid from, not a drawn lattice).
      - **EVERY TINT ON THE FLOOR IS A MASK OVER THE PAVING, NEVER A
        FLAT FILL.** This is the one that cost the debugging. The
        mottle was drawn correctly all along and was invisible,
        because the sun quads, the breezeway daylight wedge and the
        breezeway band were opaque polygons painted on top of it and
        between them they covered most of the court. The floor is
        now painted once per lighting region and each is composited
        through its own mask, which keeps the CRISP square-oculus
        edge while the stone keeps its blotches inside the light.
        Anything new that tints this floor goes in that region list.
        (The narrow overhang shadow bands at the wall foot stay flat
        — they are wall, not floor.)
      - `court_paving` carries its OWN generator and reseeds per
        pass, so the mottle registers across a mask edge and so a
        slab added here cannot reshuffle paint_walls' form mottle
        downstream through the shared `rng`.
      (The glazing and column items formerly parked in this note
      were both fixed the same day — see the mullion bullets under
      the GLASS WALL, and the full-height column bullets above.)
    - **The light it throws is the cheap half of the effect and does
      more than anything drawn inside the opening**: a graded wedge
      on the court floor along the wall's own inward normal, painted
      with the floor and before the walls.
  - **`CY` is framing, not geometry.** The storey grows the room
    UPWARD only, so the content centre drifted 90px above the frame's
    and the room hung high in the viewport with dead space under it;
    CY 590 -> 680 shifts the whole scene as one, since everything
    derives from `iso()`. Re-check after any change to the room's
    height by measuring the content bbox against `INK`.
**Two MEASURED render-quality rules (2026-08-22, from "how can we make
the pixel art look higher quality") — the railing looked wrong for
five passes because of these, not because of how it was drawn:**
- **No painterly pass on this asset.** `cv2.xphoto.oilPainting` at
  radius 4 is tuned for TERRAIN read from far out; on 1-2px
  architecture it smears pickets into blobs of uneven width and breaks
  the handrail. Verified by baking both and diffing a railing crop at
  1:1. `--painterly` is kept ONLY to re-run that comparison; the
  default bake is crisp. This is why the interior does NOT follow the
  island map's painterly house style.
- **The camera zoom is SNAPPED so one TEXTURE pixel covers a whole
  number of screen pixels** (`RoomScene.fit`, `step = 1 / ss`). The
  history matters, because the first fix turned out to be half of one:
  - *2026-08-22* — the snap was `step = 1/dpr`. A fitted zoom of 0.58
    at dpr 2 gives 1.161 device px per source px, and nearest-neighbour
    sampling duplicates some columns and not others, so a regular
    balustrade renders with uneven pickets. No redrawing fixes an
    irregular resample.
  - *2026-08-24* — that snap made the sampling GRID regular, but only
    by locking the room to zoom 0.5, which is a **2x decimation**:
    every other row and column of the bake was discarded on the way to
    the screen. Measured on a rail crop — **83 unique colours reached
    the canvas where the source has 87 and a resample gives 376**. The
    picket run is 1px lines on a 2px pitch, so WHICH half survived
    drifted as the diagonal advanced. That drift is what read as
    jagged railings, and it is detail sampled below its own pitch,
    which no snap can rescue. Fixed by SUPERSAMPLING the bake (`SS`
    in both `render_*.py`): the room is drawn in the full scene space
    and LANCZOS-downsampled to display resolution ONCE, so the
    antialiasing is baked by a real filter. The sprite carries
    `scale: SS` out of the JSON, the JSON keeps SCENE coordinates
    (hotspot px, label/marker offsets and zone sizes never moved), and
    zoom 0.5 x scale 2 is an exact **1:1 blit with no runtime
    filtering**. This is the old option (b): the interiors are a
    painted illustration now, not crisp pixel art. The island map is
    untouched and keeps `pixelArt: true`.
  - *2026-08-27* — **the Capitol's `SS` is back to 1, and that is not
    a repeal of the above; it is the same rule applied to a framing
    that changed underneath it.** The whole 08-24 argument rests on
    "fit() SNAPS to zoom 0.5 and the renderer point-samples". Two days
    later the Capitol became the main view and got a `view` rect with
    CONTINUOUS zoom and a LINEAR-filtered texture — no 0.5 snap, no
    point sampling, so nothing decimates any more and the premise is
    gone. The COST stayed: at the old 0.9 ceiling the 840x620 PNG was
    already being blown up 1.8x, i.e. the bake was throwing away
    exactly the resolution the new framing wanted. `SS = 1` ships the
    full 1680x1240 authored space, which is what let the ceiling go to
    1.6. Notes:
    - **This raises DELIVERED resolution, never AUTHORED resolution.**
      Every painter is written in scene px with hardcoded literals
      (frame insets, 1px flute lines, FEAT_HW), so doubling W/H means
      rewriting all of them — 1680x1240 is what the art contains.
    - The PNG got SMALLER (123KB -> 112KB): the LANCZOS downsample had
      been inventing intermediate colours that PNG could not pack.
    - The trade is at the SMALL end — a phone at zoom ~0.35 now gets a
      Canvas2D reduction of full-res art where it used to get a clean
      blit of half-res art. Verified at 375px: no aliasing, no moire
      on the pickets, framing identical (mobile is width-constrained,
      so the ceiling was never what bound it there).
    - **`render_office.py` still supersamples** (office_finance.json
      is `scale: 2`) and should, because that room is still snap-fit.
      SS is per-bake, and the rule is the FRAMING, not the file.
  - *2026-08-28* — **`SS` IS GONE, SPLIT INTO `OVER` AND `SHIP`, AND
    THAT ENDS THE SEE-SAW THE THREE ENTRIES ABOVE DESCRIBE.** Every
    one of them is the same trade made in a different direction,
    because ONE constant meant two things: "oversample for AA" and
    "ship at 1/SS". So SS 2 bought antialiasing and threw away half
    the resolution; SS 1 bought the resolution back and threw away the
    antialiasing. They are independent now, in BOTH room renderers:
      - `SHIP` = file px per SCENE px (both rooms ship 2). The PNG is
        W*SHIP x H*SHIP, `meta.scale` is 1/SHIP, and the runtime
        scales the sprite back — so SCENE space is untouched.
      - `OVER` = supersample on top (both 2), LANCZOS-resized away at
        the end, so the AA is baked once by a real filter.
    Capitol 1680x1240 -> a 3360x2480 file; hallway 1500x1000 ->
    3000x2000. Measured on screen, in device px, as the RMS deviation
    of a 2:1 iso diagonal from the straight line it is meant to be —
    which is what "jagged" actually is: **hallway 0.444 px -> 0.054
    (8x straighter), capitol 0.292 -> 0.100**. A crude acutance
    average barely moves (+2.6%) and is the wrong measure: the gain is
    in edge PLACEMENT, not edge contrast.
  - **The painters were not rewritten, and could not have been.** They
    are written in scene px with hardcoded literals summed into iso()
    output (`up(p, ht - 5)`, `fx + int(x0 * s)`), so there is no seam
    where a scale could be applied by hand. `SDraw` scales at the DRAW
    CALL — the one place every coordinate, literal and computed alike,
    has already been added together — and `iso()`/`lerp()`/`up()` snap
    to 1/K of a scene px (K = SHIP*OVER) so the diagonals step on the
    grid the room is actually drawn on. Snapping to whole scene px and
    letting SDraw multiply would put every diagonal back on a
    staircase K times COARSER than the output, which is the opposite
    of the point. `even_run` is deliberately untouched: it steps in
    whole SCENE px from a now-finer endpoint, so the authored picket
    and flute rhythm is bit-for-bit what it was.
  - **THE GATE IS `K = 1`, AND IT IS NOT OPTIONAL.** Forced to
    SHIP 1 / OVER 1, both renderers reproduce their pre-change bake
    **byte for byte — 0 px differ**. That is what makes "this only
    changes resolution" a fact rather than a hope, and it is the check
    to re-run before shipping any edit to SDraw or snap(). Three
    things it caught, each of which silently corrupts the room without
    it: PIL boxes are INCLUSIVE, so `(x1+1)*K-1` is what keeps an
    n-scene-px box n*K px instead of collapsing every hairline to 1/K
    of its width; `width=` is a distance in scene px and must scale;
    `point` has to become a K x K block. Polygons take the plain
    corner mapping — vertices are positions and adjacent quads share
    an edge coordinate, so growing them would make every seam in the
    room overlap by K px.
  - **Consequences to keep in step**, all of them found by the checks
    rather than by reading:
    - **The `view` ceiling is 1.6 CSS px per FILE px, so `fit()`
      divides it by `ss`.** It was only ever written in scene px
      because every room used to ship one file px per scene px. A
      room baked at SHIP 2 has earned exactly twice the magnification
      and now says so from its own bake instead of a second hardcoded
      number that could drift. This is what retires the documented
      "a 1440p monitor HITS the ceiling at 51% filled".
    - **The swing sprite was missing `setScale(this.ss)`** and was
      only ever right by luck — every room with a swing happened to
      ship at scale 1. Its three exported numbers are in different
      spaces on purpose: `fw`/`fh` are FILE px (Phaser's spritesheet
      loader slices the file), `px`/`py` are SCENE px. The bbox is
      snapped to a whole K grid first, or the downsample puts half a
      source pixel on the seam between frames.
    - **`int()` at the JSON boundary now TRUNCATES a fractional
      coordinate** where whole-pixel iso had already rounded — a
      systematic -1 on every door px. `int(round(...))`.
    - **`mottle_ink`'s 44px grain is in SCENE px** and scales with the
      canvas; left at 44 it becomes a K-times-finer speckle the
      downsample averages away to nothing.
    - **The swing sheet is premultiplied before its downsample.** PIL
      resizes RGBA channels independently, so the leaf's edge gets its
      colour averaged with the transparent ground beside it and comes
      out as a dark hairline around a door that is supposed to be
      invisible at frame 0.
    - The frame-0 pop check still passes and reads BETTER than before
      in the only form that compares like with like — share of SOLID
      px differing, 18.1% -> 15.3%, mean 5.29 -> 4.46. The raw count
      rose (367 -> 1180) purely because the frame has 4x the pixels;
      always run it against the old assets as a control rather than
      against the number written down here.
  - **Never reintroduce the dpr form.** Besides the decimation it hid
    a real bug: at dpr 1, `Math.max(step, floor(fitZ/1)*1)` can only
    ever return 1, so dpr-1 users got the room at 1:1 and CROPPED
    while dpr-2 users got it fitted — the two device classes were
    seeing different scenes. The texture form retires that.
    *2026-08-28*: the dpr term is now gone from the snap entirely
    (`step = this.ss > 1 ? 1 / this.ss : 1`), because the canvas went
    device-resolution — canvas px ARE device px, so an ss-1 room snaps
    to whole device pixels with no ratio in the expression. The ss > 1
    case is untouched; the quantum was always the TEXTURE.
  - Per-texture `setFilter(LINEAR)` DOES work on the Canvas renderer,
    but it needs more than one frame to take: a probe that samples
    300ms after setting it reads unchanged and looks like a no-op (it
    is not — wait longer). Not the shipped answer, since it filters
    every frame instead of baking once, but it is the cheap way to
    preview the look before committing to a re-bake.
  - Corollary: with baked AA, a non-integer dpr (1.5 on Windows) is
    now survivable — the compositor's filtered upscale of a graded
    edge is fine, where it would have mangled hard pixel art.
- Geometry is pixel-snapped at the source (`iso`/`lerp`/`up` round),
  so repeating runs share one grid; float coords made picket spacing
  drift by a pixel and read as irregular. **That was only half a
  fix.** Snapping the ENDPOINTS still leaves the interior positions to
  `lerp(e0, e1, i / n)`, which rounds each one independently, so a
  pitch that is not a whole number of pixels beats anyway. Measured
  2026-08-24: the ring's picket pitch was 288/64 = **4.5 px** and the
  run came out 5,4,5,4… — 32 gaps of five against 31 of four. That is
  the "railing bars look unevenly spaced" report, and it survived the
  08-22 pass untouched.
- **Every repeating run along an edge goes through `even_run(e0, e1,
  pitch)`**, which steps in PIXELS and forces the pitch EVEN. These
  edges are exactly 2:1, so an even x step gives a whole-pixel y step
  and there is nothing left to round; even also means the pitch
  survives the SS downsample without picking up a second beat. Three
  runs use it — the rail pickets, the parapet flutes and the slab
  flutes above the doors. The floor REFLECTION of the pickets shares
  the same call: a reflection that drifts off its own bars is worse
  than no reflection. Anything new that repeats along an edge uses it
  too; do not go back to counting in `t`.
- **Picket pitch and width were judged on the DOWNSCALED bake**
  (`PICKET_PITCH` 6, `PICKET_W` 2), never at 1:1 — SS halves both, so
  a 1px bar is half a display pixel and LANCZOS renders the run as
  grey haze. The sweep: 4/1 is that haze (it was the shipped density),
  4/2 is nearly a solid dark band, 8/2 reads as sparse posts, 6/2
  keeps a clear bar-and-gap rhythm.

**Accuracy passes work from two Commons photos** (2026-08-22, after
"find other pictures of the perspectives from those balconies"):
`Interior of Hawaii State Capitol from Executive Floor.jpg` (view DOWN
the atrium — source of: dark-brown walkway floors edged in white
fluted fascia, dark bronze wall columns, tall koa doors, wall benches)
plus a third the user supplied 2026-08-25, a wide view of the
courtyard FROM THE ROTUNDA FLOOR looking up (source of the column
count — a corner column and two to a side — and of the coffered
balcony soffits cantilevering out past the loggia columns),
and `Hawaii State Capitol - Interior Rotunda (5683208622).jpg` (the
courtyard panorama — source of: large pale square ground piers,
vertical koa-slat chamber screens, tan stone planters, the chain-post
ring around the medallion). Re-check against BOTH before changing the
interior's materials.
**The floor medallion is a GENERIC original design on purpose** — the
real rotunda floor is Tadashi Sato's 'Aquarius', a copyrighted 2-D
artwork with no US freedom-of-panorama, so the bake must never
reproduce his composition (even terrazzo dot-grid + rings only; the
rule is written into paint_mosaic's docstring). Naming it in hotspot
TEXT is fine (facts aren't copyrightable); depicting it is not. Palette and
treatment follow make_event_art.py's interior set, NOT the bright
overworld map palette — except the gallery recesses, which are warm
LAVA-BRICK BROWN per the photos (banner navy read as wrong; user
feedback 2026-08-22). The railing is a measured three-layer assembly
from the photos and drawn CHUNKY so it survives game zoom: deep
fluted white parapet fascia (the dominant element), a shorter open
run of dark pickets, thin koa handrail — no fat posts; the well's far
walls repeat the same banding per level. `CapitolScene` in main.js displays it
fit-to-window; entered by tapping the overworld Capitol
(`scene.switch` — the world SLEEPS, never rebuilds), exited via the
stairs hotspot or Esc. Rules:

- **`CAP_V` in main.js is the ONE cache token for BOTH files** — they
  come out of one bake and the hotspot px are meaningless against a
  stale image. Hand-bumped, same rule as MAP_V.
- Standalone bake: no island-pipeline rebuild order, no Oʻahu
  regression stake. Reference was Wikimedia Commons
  (Category:Hawaii State Capitol); the art is drawn from scratch in
  code, so the asset is original work, no license baggage.
- **Orientation facts are real and load-bearing for content**: Senate
  cone = ʻEwa (Richards St) side — Moon chandelier (620 nautilus
  shells); House cone = Diamond Head (Punchbowl St) side — Sun
  chandelier (gold globes). Up = mauka (Beretania), down = makai
  (toward ʻIolani Palace). The open well is architecturally honest —
  the real rotunda IS open to the sky, and the public really does
  watch the chambers from gallery level. (make_sprites.py's cone
  comments had Senate/House swapped until today; the scene and the
  hotspot text are the corrected authority.)
- **THE GAME LANDS IN THE CAPITOL, NOT ON THE MAP** (`START_ROOM` in
  main.js; 2026-08-24, user's call: "make that the default view
  (replacing the map) for now. keep the map in case we want to use it
  later"). Set it to `null` to put the overworld back — that is the
  ONLY edit needed, which is the whole reason it is a switch and not a
  rewrite of the boot path:
  - **WorldScene still RUNS.** It builds the map, flows and labels AND
    initialises every panel — Money, Policy, Session, Island, Sfx all
    live in its `create()`. Booting a room directly instead would
    leave the entire game uninitialised. The map is built, then slept
    behind the room; nothing is deleted and nothing sits on a second
    code path that can rot.
  - **The map is no longer player-reachable** (2026-08-26, `noExit` —
    see the HUD bullet below; before that the stairs/Esc led out).
    `exitTo: "world"` remains in the config and `parkOnCapitol` still
    parks the camera on the Capitol at boot, so dropping `noExit` is
    the one edit that restores the whole route.
  - **The week-1 boot pop is suppressed while it is set**
    (`SessionPanel.init`): the point is to land on the ROOM, and an
    overlay opening over it defeats that. The creation funnel is not
    lost — it is `renderHub`'s early bail, so it fires the moment the
    session is opened from the map.
- **THE CAPITOL CARRIES THE FULL GAME HUD NOW** (2026-08-26, user's
  call: "move all the ui stuff from the map to the view of the capitol
  … this is supposed to be the main actual view of the game. so then
  remove the 'back to oahu' button too. the view should be zoomed in
  more"). Three changes, each with a rule:
  - `body.in-capitol` no longer hides `#hud` — it hides only the
    MAP-facing chrome (`#island-chip`, `#island-menu`, `#hint`,
    `#chips`); toolbar, End Turn, fund chip, standing and timeline all
    live over the room. End Turn is safe because `advanceWeek` skips
    the week-beat camera ritual whenever WorldScene `sys.isSleeping()`
    — without that guard the beat would stall 4s on the fallback timer
    every turn (the tween clock sleeps with the scene).
  - **`ROOM_CAPITOL.noExit: true`** — no exit hotspot is built, Esc is
    not bound, `leave()` bails. The map is unreachable by the player
    (still built and asleep underneath; drop `noExit` to restore the
    stairs). The office's own exit back to the capitol is untouched —
    `noExit` is per-room. The greet text lost its "stairs makai" line.
  - **`ROOM_CAPITOL.view: [x0,y0,x1,y1]`** (scene px) — `fit()` frames
    this rect instead of the whole canvas, with CONTINUOUS zoom capped
    at **1.6**, and `create()` switches that room's texture to LINEAR
    filtering (per-texture setFilter works on Canvas; a filtered
    fractional resample of the painting is clean, so the snap quantum
    doesn't apply — snap-fitted rooms keep NEAREST). The
    rect is the measured content bbox + margin; REMEASURE it after any
    re-bake that moves the composition. The wing (below) deliberately
    extends PAST the rect — cropped at the frame edge it reads as the
    building continuing, which is the point.
    **The ceiling is a TEXTURE-UPSCALE budget and it moved 0.9 -> 1.6
    on 2026-08-27** with the `SS 2 -> 1` re-bake (full argument in the
    render-quality section below). At 0.9 the room was a FIXED 965x619
    however big the window got — 65% of a 1280x720 laptop, 46% of a
    1440x900, **28% of a 1080p monitor, the rest empty ink**. Measured
    against the shipped `fit()` afterwards:
    `1280x720 -> 1.05 (88%)`, `1440x900 -> 1.31 (97%)`,
    `1920x1080 -> 1.57 (88%)`. 1.6 is LESS magnification than the old
    0.9 x ss 2 = 1.8x, from four times the source pixels.
    **It is a real limit, not a placeholder**: past ~1.6 a 1680px
    painting softens. Known consequence — a 1440p monitor HITS the
    ceiling (51% filled) and a 34" ultrawide more so (38%). Both are
    still 3x the old coverage, and the only way past it is authoring
    the room bigger, not raising this number.
- **THE ELONGATED PLAN — the whole room is a RECTANGLE now**
  (2026-08-26, two user calls: "extend the right side of the second
  and third floors so that they are more rectangular", then the
  correction that settled the design — "i wanted the railing to also
  reflect this new length. it's still in the same square". A first
  cut extended only the walls, leaving the well/railing square; that
  was wrong). `WING_EXT` (8.0 iso units) + **`rdiamond(a, dy)`** in
  render_capitol.py — diamond()'s elongated counterpart, E and S
  corners slid +WING_EXT in u, same corner ORDER so every (i, j)
  edge-pair loop works unchanged. Everything derived from the well
  follows it: ring floor, ring shade, sun spill, BOTH railing rings
  (pickets + pots at gallery, upper_parapet — the extracted single
  source — at Senate), courtyard paving + oculus light quads + loggia
  bands, the slab fins, the makai fascia edges. Rules:
  - **The rotunda-centred furniture does NOT follow**: mosaic, chain
    ring, planter benches, breezeway band, and the whole ʻEwa corner
    assembly (smokestack/panel/doors) stay in absolute u/v — the
    rotunda is where it is; the COURT is what got longer. That the
    mosaic now sits left-of-centre in the long court is true to the
    real building.
  - **`column_stations()` keeps the ORIGINAL square hole** — its
    stations must land on `col_xs()`'s screen x or the loggia shaft
    and the flush wall strips above it split apart (the one-source
    column rule). The extension got ONE extra loggia-only station
    (mid-extension) with no flush strip above it — survivable because
    the strips are the subtlest element in the room.
  - **The drum glazing CONTINUES PAST ITS APEX** (court_glass's `ext`
    param): the assembly (corner wall, doors, pier, main arc) is
    still parameterised on the ORIGINAL run — paint_well passes
    `iso(GND_OUT, -GND_OUT)` as e1 and the extended corner as `ext` —
    and the continuation mirrors the cylinder's physics (theta 0 →
    +52°, bars re-compressing toward the far corner, sill bow easing
    back up), starting AT the main arc's last mullion so the curtain
    is one sheet. Flat filler is exactly the "mullions then a dark
    slab" read the 2026-08-25 rework removed — don't regress to it.
  - **The stairs KEEP their spot**: `iso(A_OUT, A_OUT)`, the old S
    corner, now an ordinary point on the longer SW edge (a rectangle
    has no bottom apex). spawn and the (noExit-skipped) exit hotspot
    both still derive from `diamond(A_OUT)[2]` in render(), so
    nothing moved — hotspot json stayed byte-identical through the
    whole change.
  - The upper storeys' wall extensions (the wing blocks at the end of
    paint_walls and paint_upper_level) carry only UNNAMED filler (an
    office door and a bench each, on their own local span) —
    place_feats never sees the wing, so never put a named feature
    there. Flute phase steps from the ORIGINAL run start (even_run
    over the full span, filtered to the wing) so the 6px rhythm can't
    beat at the seam; wing form mottle uses a LOCAL generator
    (shared-rng rule, same as court_paving). The E sliced ends
    (paint_upper_level's mass face, paint_cut_ends' arris) sit at the
    extended corners.
- **THE FLOOR HAS AN OWNER — level 2 is the SENATE's, level 3 is the
  HOUSE's** (2026-08-27, user's call: "third floor is for house and
  second for senate"; scope settled with the user as *whole floors*,
  not offices-only). `GALLERY_FEATS` / `UPPER_FEATS` in
  render_capitol.py carry it, and BOTH runs of a level belong to that
  level's chamber. Before this, every public room (both galleries,
  both money committees) sat on the walkway and the storey above was
  labelled Senate — which put the Senate Clerk on the Diamond Head run
  and left no floor with an owner at all.
  - Level 2 (the walkway the player stands on): Senate Gallery + Ways
    & Means on the ʻEwa run, Senate President + Senate Clerk on the
    Diamond Head run.
  - Level 3 (the stepped-back storey): Speaker of the House + House
    Clerk on ʻEwa, House Finance + House Gallery on Diamond Head.
    `speaker` and `houseclerk` are NEW ids; `senpres`/`senclerk` kept
    theirs and moved down a floor.
  - **The ʻEwa / Diamond Head rule still stands and does NOT conflict**
    — it governs what is BELOW (Senate cone ʻEwa, House cone Diamond
    Head), not the door runs above it. Each chamber's gallery door is
    still on its own cone's side of its own floor, so the two rules
    agree exactly where they touch.
  - **`gov` is the deliberate exception.** The Level 5 lift belongs to
    neither chamber and stays on the walkway, because that is the
    floor the player is standing on and the way up has to be reachable
    from where you are. Its hotspot text says so.
  - Consequence to keep in step: the hotspot TEXTS name their floor
    ("Second level, and this floor is the Senate's"), which is the
    whole teaching. A door that moves floors moves its sentence too.
  - `ROOM_CAPITOL.enter` is keyed by hotspot ID, so `finance` still
    opens the office from its new storey — verified in the pane.
- **A HOTSPOT'S TAP TARGET COMES OUT OF THE BAKE** (2026-08-27),
  `zone: [cx, cy, w, h]` in scene px, from `feat_rect()` /
  `zones_for()` in render_capitol.py — the same geometry that drew the
  feature, which is the one-source rule the columns already follow.
  `RoomScene.create` reads it, falling back to the old fixed box for a
  bake that predates the field (office_finance.json). What it replaced:
  a hardcoded `120x84` at `(px, py + 6)` — three times the width of a
  door, sitting about a door-height BELOW it out on the walkway floor.
  Measured consequences, both real: on the near runs the box missed
  its door entirely, and **House Gallery and Governor overlapped by
  39% of a zone** — Phaser resolves a hit by BUILD ORDER, so a third
  of the gallery's target silently opened the lift. Rules:
  - **The padding is a CEILING, not a flat amount** (`ZONE_PAD` 9,
    applied by `zones_for`). The wall is not evenly packed: most named
    doors have most of a bay of air beside them, while the Senate
    Clerk sits one `FEAT_GAP` from the lift lobby that closes its run.
    Baked flat at 9 those two overlap by 2px. Two boxes are disjoint
    if they clear on EITHER axis, so a pair's budget is
    `max(gap_x, gap_y) / 2` and each box takes the smallest budget any
    neighbour allows — symmetric, or a third box could push one into a
    neighbour from its far side.
  - **`render()` ASSERTS that no two zones overlap**, and it earned
    its keep on the first run. Grow `ZONE_PAD` past what the bay
    layout leaves clear and the build fails instead of shipping a tap
    that opens the wrong door.
  - `FEAT_BOX` is read straight off `door_at` / `corridor_at` (a koa
    leaf is hw 17 in a ±hw+4 threshold, head at y 53). The runs are
    2:1 diagonals, so a box symmetric in WALL coordinates is a sheared
    parallelogram on screen — `feat_rect` takes all four corners; the
    width alone leaves the AABB short by the ±hw*uy the diagonal
    contributes.
  - The mosaic goes through the same solve (its rect is the
    medallion's own ellipse) so it is padded against the same set.
  - Shipped sizes are 50-58 x 93-100 screen px at zoom ~1.05 —
    comfortably over the 44px tap floor, where the old boxes were both
    too big and in the wrong place. Verified in the pane: all nine
    doors plus the medallion each resolve to exactly one label, and
    the old house/gov overlap midpoint now belongs to neither.
  - **Not changed, and still worth fixing**: the bouncing marker still
    hangs at `py - 30`, which is MID-LEAF on a 53px door, so it reads
    as door hardware rather than a "this is live" flag. Moving it above
    the transom needs a check against the storey above.
- **THE FINANCE DOOR SWINGS OPEN (2026-08-27, user's call: "light 3d
  effects … making the doors appear 3d when they open").** The bake
  emits a spritesheet per swinging door (`swing_sheet` in
  render_capitol.py → `site/assets/map/swing_<id>.png`, described by
  capitol.json's `swings` block); `RoomScene` plays it and enters the
  office on the last frame. Rules, most of them paid for:
  - **A BAKE, NOT A RUNTIME TRANSFORM, BECAUSE THE PROJECTION IS THE
    WHOLE POINT.** The leaf is rebuilt in PLAN at each angle and
    projected with the room's own axes, so it foreshortens correctly;
    rotating the sprite by the same angle on screen is a different
    motion and reads as a flat card spinning. Along-wall is (ux, uy),
    the outward normal is `(16*sgn, 8)` per PLAN unit — `bench_at`'s
    rule, reused — and one plan unit is `hypot(16, 8)` px along EITHER
    axis, which is what lets the two components be mixed by angle.
    Verticals stay vertical in this projection, so a leaf is always a
    quad with two plumb edges.
  - **IT SWINGS INWARD, AND THAT IS A READABILITY CALL.** Swung toward
    the camera the leaf is geometrically right and useless — from a
    3/4 overhead view it stands between the camera and the opening and
    hides the thing the animation exists to show. Both were baked; the
    outward one is unusable. Inward also decides the draw order: the
    leaf is BEHIND the wall plane, so it is clipped to the doorway
    aperture (a mask, not a guess — unclipped, the swing carried the
    leaf's top corner up past its own architrave and hung a brown post
    above the transom in every open frame).
  - **THE ANGLE'S BOUND IS CLEARANCE, NOT TASTE.** `SWING_MAX` 66° —
    the leaf is 2*hw = 34 px = 1.90 plan units and the level-3 walkway
    is `LVL2_OUT - LVL2_IN` = 2.5 deep, so at 66° it stands 1.74 units
    out and lands clear of the parapet it is drawn OVER at runtime.
    Raising it without redoing that arithmetic puts a door through a
    railing.
  - **FRAME 0 IS THE CLOSED DOOR AND MUST MATCH THE BAKE UNDER IT** —
    the sheet sits on top of the finished room, so any difference pops
    the instant the sprite appears. That is why `door_at`'s leaf was
    extracted to module level (`grand_leaf` + `leaf_grain` +
    `grand_seed`) and the swing draws the SAME leaf through a swung
    mapping: same grain seed, same recessed panel, same brass pull.
    Three separate things had to be fixed before it matched, all found
    by diffing frame 0 against the bake: an approximated leaf (banded
    strips, no panel), unrounded points (`door_at` rounds — a half
    pixel everywhere), and folding the wall's `f` into the leaf when
    `door_at` takes no wall factor at all (a uniform 13% darkening).
    It ships at 367 hairline px of 6090, mean delta 1.8. **Re-run that
    diff after any change here** — it is the only check that catches a
    pop, and eyeballing the sheet will not.
  - Nothing below the wall's foot line (y = 0) is drawn EXCEPT the
    light wedge: the walkway and the parapet are painted after the
    doors in the room, and redrawing a threshold over them is wrong.
    The wedge is the exception because it belongs on top of the
    walkway, and it is absent at frame 0 — no gap, no light.
  - Runtime: `cfg.swings` lists the hotspot ids, the sheets are queued
    off the meta json's own `filecomplete` (Phaser will not queue a
    spritesheet without frame sizes, and the meta is still loading in
    preload). `openThen()` plays, then acts. **A swing already running
    SWALLOWS the tap** — folding that in with the no-swing case ran
    the action immediately, so an impatient second tap SKIPPED the
    door and jumped into the room, which is backwards (caught live).
    A wall-clock fallback lands the transition if
    ANIMATION_COMPLETE never fires (rAF stops in a hidden tab — the
    same reason `weekBeat` carries one), and `enterRoom` resets every
    door to frame 0 so walking back out never finds one still open.
    Reduced motion skips the swing: the door is a flourish, never the
    only way in.
  - **Only doors that GO somewhere get one.** The swing covers a scene
    change that used to be a hard cut, which is where it earns its
    cost; a door that only shows text stays shut.
- **HOTSPOT NAMES ARE ON HOVER, NOT PAINTED OVER THE DOORS**
  (2026-08-24, user's call: "don't have those big labels over all the
  doors"). `RoomScene.create` still builds every label, but anything
  that isn't the EXIT starts hidden and is shown by the zone's
  pointerover/pointerout. Nine plates of stroked type stood across a
  painted room and read as a debug overlay — they hid the very doors
  they named. The bouncing marker is what says "this door is live"
  now. The exit keeps its label on purpose: the way out must never
  need hunting, and on touch (no hover) it is the one name a player
  cannot afford to miss.
- `body.in-capitol` hides `#hud` (one rule at the end of style.css) —
  End Turn must not run the week beat over a sleeping WorldScene.
  `#dialog` is a SIBLING of #hud, so the JRPG box stays.
- Pane-testing trap: the browser caches the `?v=`-stable JS/CSS/PNG
  hard across uncommitted edits. Refetch with
  `fetch(url, {cache:'reload'})` then reload, or the old asset renders
  and the new code silently isn't there.
- **Atrium-photo accuracy pass (2026-08-22, CAP_V 2)** — from a
  user-supplied gallery-corner photo (Dreamstime preview; watermark +
  license = reference ONLY, never a `--photo` source): glossy WIDE koa
  cap with a specular glint row over a white kerb plate (the rail is
  the dominant near element), arched arcade heads between the
  courtyard piers, reddish quarry tile with per-cell tone jitter and
  faint reflections (near-rail pickets/cap, wall columns, koa doors —
  the sheen is the cheap half of "polished"), potted plants at the
  near rail, stepped light falloff away from the well (scene lighting
  on ONE canvas, not the composite-vignette trap). Deliberately NOT
  added: the executive-floor white band and the overhead cone flanks
  the photo shows — both would reintroduce the rolled-back upper
  floors; the one-level call stands.
- **The makai side is JUST THE WALKWAY now** (2026-08-24, user's
  call: "on the cutaway walls facing user: don't need the walls, just
  showing the walkway is fine" — superseding the 2026-08-22 knee-high
  cut-stub treatment). `paint_cut_wall`, `CUT_H` and `CUT_T` are
  deleted: the near edges show the floor ending at its own slab edge
  with the fluted fascia hanging below (the same band the well edges
  wear), and nothing stands on them. Don't reintroduce stub walls.
  `cut_face()` survives for the cuts that remain — `paint_cut_ends`
  (the mauka walls sawn off at the ʻEwa/Diamond Head corners) and the
  third level's sliced ends — and its two measured rules still bind:
  the cut core (`CUT_CORE`) must clear the dressed flutes in VALUE
  (a pale cut vanished at the 0.5 game zoom, the only scale that
  matters), and any new slice routes through `cut_face` so every cut
  in the room is the same material.
- **Dressing pass (2026-08-22, later): NO FLAGS** — the flag pairs
  flanking the chamber doors were removed at the user's request
  (`paint_flag` deleted; don't reintroduce). Koa doors are PAIRED
  leaves in an architrave frame: recessed panels shaded sky-key (top
  reveal dark, bottom lit), grain sheen lines, brass pulls at the
  meeting stiles, kickplate, lit transom above the frame. Rail pots
  are layered — dark foliage mass first, asymmetric frond fan over,
  single light pixel at each tip (a symmetric fan reads as a printed
  icon; the layering is what reads as a plant at 20px).
- **Dense door schedule + real hallway portals (2026-08-22, later;
  user: "in reality there would be many more doors… those alcoves
  look off, they're supposed to represent hallways")**: each mauka
  wall now carries ~7 features — the named doorways (hotspots) plus
  narrow single-leaf `office` doors (`door_at` kind, hw 11) filling
  the runs. Keep feature centres ≥ 0.10 t apart (chamber frame 40px /
  office 28 / portal 38) and leave ONE gap per wall for the bench.
  `corridor_at` is a full one-point PORTAL now: receding floor
  darkening with depth, converging side walls, ceiling, a dim far
  window (or the lift's steel doors as the far end), everything
  clipped inside the opening and the far end nudged along the
  corridor's true iso direction. The old version spilled a sunlit
  floor wedge across the wall face — that is the "alcove with a plank
  in it" read; never draw corridor floor outside the portal. Planters
  moved AFTER walls in render() so the W/E corner planters occlude
  the corner-most doors' floor reflections.
- **Material corrections (2026-08-22, latest): the gallery walls are
  CONCRETE, not lava brick** ("the texture of the walls is more
  concrete-like") — grey `CONC`/`CONC_D` with pour joints + rng form
  mottle, corridor interiors in the same material; `RECESS` survives
  only as the well's under-gallery shadow. The wall BENCHES are gone
  — drawn mid-walkway with no wall contact they read as brown bars
  floating on the railings; don't reintroduce without solving the
  contact problem. The N-apex stone planter is gone too (only ʻEwa
  and Diamond Head corners keep one). Railing metal is BRONZE on both
  sides now (far pickets #4a4238, stanchions/corner posts #57503f —
  user: "shade of the railing should be darker"): the photos have no
  pale pickets; white belongs only to the kerb plate and the fascia.
- **House Finance chair's office (2026-08-22): `tools/render_office.py`**
  → `site/assets/map/office_finance.png` + `site/map/office_finance.json`
  (spawn + hotspots: reception, cubicles, door, desk, exit). Second
  interior in the same cutaway language: reception with three staff
  cubicles + L reception desk, then Kawaguchi's inner office. Theme is
  the w2-finance-office BANNER, not the capitol atrium: full-height
  koa-panel walls with dark seams, big clean koa desk + credenza, twin
  cream lamps as the ONLY light source (glow painted AFTER the walls so
  it washes both), aloha-blue as the one cool accent (cubicle fabric,
  binder spines, guest-chair seats). Interior partition is SLICED at
  the same CUT height with the koa double door standing full-height in
  its architrave — the RPG-cutaway convention extends to interior
  walls. Painter-order trap hit live: the exec chair must draw BEFORE
  the desk (only its koa-capped back shows) or it reads as a monolith
  standing on the desktop. WIRED 2026-08-22 (same day): `CapitolScene`
  is refactored into ONE generic **`RoomScene`** class (main.js),
  instantiated twice from `ROOM_CAPITOL` / `ROOM_OFFICE` configs —
  key, cache token (CAP_V / OFF_V), asset paths, `exitTo`, an `enter`
  map ({finance: "office"} sends that door somewhere instead of
  showing its text), and the entry greeting. Rules:
  - `exitTo: "world"` is the ONLY exit that drops `body.in-capitol` —
    room→room transitions keep the HUD hidden for the whole visit.
  - `_skipGreetOnce` (set by `enterChild`) suppresses the parent's
    greeting when you walk back OUT of a child room; fresh entries
    always greet. Don't replace with a greet-once flag — re-entering
    from the world should greet again.
  - A third room = a new `ROOM_*` config + scene-list entry + its own
    version token. Never fork the class.
  - Pane-testing trap: PHASER canvas taps must be synthesized as
    `MouseEvent` mousedown/mouseup — Phaser 3.90 registers mouse/touch
    listeners, and a synthetic `PointerEvent` is never seen. (The DOM
    session UI is the opposite: pointerdown only, per the note above.)
  Verified end-to-end in the pane: world → capitol (greet, HUD off) →
  finance-door tap → office (greet, capitol sleeps) → exit (no
  re-greet) → exit → world (HUD back).
- **The opening-week hallway (2026-08-27): `tools/render_hallway.py`**
  → `site/assets/map/hallway.png` + `site/map/hallway.json`, token
  `HALL_V` (user's call, from a reference photo of a Capitol corridor:
  "for the opening week … the scene portrayed in the game [is] a
  hallway … you're talking to the legislator off to the side.
  subsequent weeks revert back to the regular capitol scene").
  Third `RoomScene` room (`ROOM_HALLWAY`), and WEEK 1's home view:
  a House-wing corridor — white walls over a glossy red-brown tile
  floor with baked reflections, koa doors (the far one with the
  photo's taped notice), a glazed building directory, and the photo's
  widening rendered as a full-height RECESS in the far wall (a first
  pass built the lobby jutting toward the camera and it read as a
  floating fin — the recess is the same language as the capitol's
  hallway portals, so the whole widened area is visible). THE
  LEGISLATOR — the player's introducer, aloha shirt, lei, folder,
  faceless at sprite scale per the house rule — stands off to the
  side in that alcove. Rules:
  - **IT IS A SINGLE HALLWAY, AND `VH` SAYS SO** (2026-08-27, user:
    "make hallway narrower … it's just a single hallway"). The first
    bake ran `VH` 2.1 — a 4.2-unit floor against ~18 of run, which is
    a gallery, not a corridor — with a 7-unit recess that read as a
    second room opening off it. Now `VH` 1.45 (walls about a
    door-and-a-half apart, per the photo) and the recess narrowed
    with it to stay an alcove one person stands in. Narrowing has
    two knock-ons that any further change has to respect:
    - **The end-wall door has to come in with the walls** (±0.7, was
      ±0.8): its architrave flares 10% past the leaf either side, so
      a door sized for the old width leaves no wall beside it.
    - **The introducer's office door moved OUT of the alcove onto the
      corridor wall.** At the narrower width a door behind the
      legislator put two tap zones on top of each other and the
      disjoint-zone assert caught it — which is the assert doing its
      job, not an obstacle to route around. The alcove is where the
      person stands; the door they work behind is a few paces up the
      hall, and the composition is better for it.
    - **A pot at the alcove MOUTH gets sliced by the casing post** and
      reads as a clipping error. Both plants stand deep in the alcove,
      flanking the legislator.
  - **`bootRoom()` in main.js decides the landing, not START_ROOM
    directly**: fresh or week-1 save → "hallway", past week 1 →
    START_ROOM. It reads localStorage raw (SessionPanel's S is
    closure-private at that point in WorldScene.create). START_ROOM
    is still the one overworld switch — null still restores the map.
  - **The first End Turn retires the room**: advanceWeek switches a
    live hallway to the capitol right after save()/renderHead(), and
    "Restart session" mirrors it back (the same both-doors-match rule
    as the restart/boot funnel). switch() SLEEPS the hallway; the
    swap is queued by Phaser, so a synchronous probe right after the
    call still reads the old active scene — wait a frame in the pane.
  - **Tapping the legislator IS the week**: `RoomScene` grew a
    cfg.`action` map ({hotspotId: fn}, same shape as `enter`) and the
    hotspot calls `SessionPanel.openWeek()` (exposed in init because
    toggleSession is closure-private; open-only on purpose — a tap on
    the canvas can never mean "close"). The creation funnel still
    comes first: openWeek routes through the same branch as the
    Session button, and renderHub's early bail owns that order.
  - Home-room treatment like the capitol: `noExit: true`, full HUD,
    `view` rect + continuous zoom + LINEAR (SS = 1, full-res author
    space). The bake PRINTS its content bbox + suggested view rect on
    every run — re-copy into ROOM_HALLWAY.view after a re-bake that
    moves the composition. It also emits per-hotspot `zone` boxes
    from the drawn geometry and asserts they're disjoint (capitol
    rule). An exit hotspot is in the JSON but skipped by noExit —
    drop noExit and it walks out to the capitol.
  - Verified in the pane: fresh boot → hallway (greet, HUD, marker
    over the legislator, funnel opens on tap); week-3 save → capitol,
    hallway never starts; End Turn at week 1 → week-2 overlay over
    the capitol, hallway asleep; restart → hallway + funnel. Mobile
    375px framing checked. After the narrowing, all four zones
    re-verified to resolve to exactly one label each.
  - **THE VIEW IS TIGHTENED, AND HOTSPOTS ARE WHAT BOUND IT**
    (2026-08-28, user: "zoomed in more by default"). `view` is no
    longer the content bbox — it is that bbox shrunk **1.15x about its
    centre**, `[281, 206, 1099, 725]`, which lifts the fitted zoom from
    1.21 to ~1.39 at 1280x720 and stops the corridor floating in a
    field of ink. Cropping the run's ends is intended: a corridor cut
    by the frame reads as continuing, the Capitol wing's argument.
    Three numbers decide how far this can go, and they were measured,
    not guessed:
    - **1.15 is the limit, because of TAP TARGETS.** At 1.15 the
      caucus door's zone fell 7px outside the rect — visible and
      unclickable; at 1.35 the office door goes too. The caucus door
      is therefore drawn 0.3 OFF-CENTRE on the end wall (it has ±0.75
      of play before the leaf meets its own corner) to buy the margin
      back. render_hallway.py now ASSERTS every zone fits the rect —
      the rect lives in main.js, so keep the two in step.
    - **The zoom ceiling is 1.6 and it binds at framing ~1.35**, so a
      tighter rect past that buys crop without buying magnification.
    - **Past 1.6 the 1500px bake softens** — verified by rendering the
      same world region at 1.21 / 1.60 / 2.40; at 2.4 the lei, the
      shirt edge and the tile joints all go mushy. Zooming further
      means authoring the room bigger, not raising the number.
  - **The legislator's `figure()` was rebuilt for elegance (2026-08-28,
    from "I would like for it to be more elegant looking")**, after the
    OVER/SHIP resolution fix landed the same day — that fix is what
    made this worth doing: curves and diagonals finally resolve
    cleanly instead of the SS-1 staircase, so finer silhouette work
    actually survives to the screen. What changed:
    - **Every limb is a LOFTED taper through measured (cx, y, hw)
      stations**, proximal to distal — the same straight-segment-
      between-stations convention the building's own columns use
      (COL_FLARE = 1.0, "never a curve fit"). Legs go hip -> knee ->
      ankle instead of two flat rectangles; sleeves and forearms taper
      instead of being uniform tubes; the torso is a four-station
      hourglass (shoulder -> chest -> waist -> hem) that flares back
      open at the hem the way a loose aloha shirt actually drops,
      instead of a straight-sided box.
    - **The whole figure is split lit/shadow down the midline**, the
      same one-hard-key-light treatment the walls and doors already
      carry: torso, neck and limbs each take a full-strength tone on
      one side and a `shade(., ~0.84-0.88)` tone on the other. The
      head is the one genuinely ROUND part, so it is split with a
      pair of 180-degree `chord`s instead of the loft/half polygon
      trick — the one shape a straight-sided taper cannot fake.
      **The leg split shipped at 0.8 first and was too strong** — on
      a large flat area two-tone shading reads as two different
      pant colours rather than form, where the same split on the
      torso (broken up by the collar, the pattern and the sleeves)
      reads fine. Backed off to 0.88; the lesson is that split
      strength has to answer to the SIZE of the flat area it's
      shading, not just the light logic.
    - **Shoes are a pointed, outward-turned toe**, not a flat block —
      paired with a couple of units of outward turn at the right
      ankle, the relaxed contrapposto that keeps the stance from
      reading as a mannequin at attention.
    - **The right arm bends in across the chest to carry the folder;
      the left hangs at a slight relaxed angle** — the one asymmetry
      doing that work, rather than a mirror-symmetric pose.
    - **A folder gets ONE fold line, not two.** A first pass added
      both a shadow fold line and a brightened top edge; against
      PAPER (already near-white) the second line read as a second
      fold rather than a highlight, so it was cut.
    - **A couple of open collar buttons**: a shadowed V of folded
      fabric with a smaller SKIN triangle nested inside it, still
      faceless, still no detail above the collarbone — the same
      "no faces in focus" boundary every drawn character in this game
      keeps.
    - The lei went from 3 bare dots on an arc to 6 alternating-tone
      blossoms on a slightly fuller drape, and the shirt's pattern
      specks are now tinted toward whichever shirt half (lit/shadow)
      they land on, rather than a single fixed tint that would sit on
      top of the shading as a flat overlay.
    Verified same as the resolution work: `render_hallway.py --layers`
    still recomposites to the flat bake with 0 px differing, and the
    zone/view-fit asserts still pass unchanged — the figure grew a
    little (hem raised to sell longer legs, head raised a couple of
    units) but stayed well inside the 100px-tall hotspot zone. Bumped
    HALL_V to 4; hotspot px are unaffected, this is art only.
  - **Diorama-parallax spike (2026-08-28) — `--layers` on the bake,
    harness at `site/dev-parallax.html`.** `render(layers=True)` runs
    the SAME painters onto three depth bands (back / mid / front) and
    asserts the recomposite reproduces the flat bake; the flat output
    is byte-identical, so the split is safe to trust. Regenerate the
    bands with `python3 tools/render_hallway.py --layers` (they are
    derived and not committed). What it measured, so nobody re-learns
    it:
    - **Holes are a NON-ISSUE** — a flat 0.4% of the silhouette at
      every amplitude from 2 to 30px, which is edge antialiasing, not
      gaps. Each band is painted complete, so uncovering one reveals a
      layer drawn as if nothing ever occluded it.
    - **The real failure is CONTACT.** Objects lifted off their own
      contact shadows (those lived in the floor's gloss overlay) —
      visible at 6px, unmistakable at 14 — and the casing posts
      drifted off the wall ends they cap. Fixed by re-banding, not by
      tuning: shadows travel with their object, posts are structure.
      **In FLAT mode the shadows are still drawn straight into the
      gloss overlay**, because ImageDraw fills REPLACE pixels rather
      than blending and routing them through a second composite moved
      the shipped bake by a few units.
    - **Cost is ~3x the draw**: 18.5ms vs 6.4ms per frame at 2560x1440
      dpr 2, i.e. ~54fps against ~155. Measure this with a 1px
      `getImageData` after each draw — Canvas2D batches drawImage and
      the naive timing reads a meaningless 0.02ms.
    - **Verdict: not worth it here, and worse for the Capitol.** The
      effect is subtle at safe amplitudes, and at large ones it reads
      as objects sliding across the floor rather than a camera move,
      because in a projected iso box everything shares contact edges.
      The Capitol has railings, parapets and columns drawn in three
      pieces across storeys — the contact problem would recur at
      nearly every element. The tightened view above delivered most of
      the perceived gain for none of the cost.

## Vendored: rot.js + Phaser iso plugin (2026-08-26)

Two libraries vendored ahead of features that aren't built yet — neither
changes anything a player can currently see.

- **`site/vendor/rot.min.js`** (rot-js 2.2.1, BSD-3-Clause) — wired for
  ONE thing: `window.ROT.RNG` replaces `Math.random()` at the three
  gameplay-roll sites (`rollCheck`'s 2d6, and the two hazard `draw`s in
  `resolveBills` for the chair and floor gates). ROT.RNG seeds itself
  from the clock exactly like Math.random, so real play is unaffected;
  `?seed=<n>` in the URL (index.html, same dev-flag pattern as
  `?raf=mc`) freezes it for a reproducible run of the gauntlet. The
  rest of the library (Map/FOV/Path/Lighting/Scheduler — dungeon-gen
  and roguelike tooling that doesn't fit a real-GIS baked world) rides
  along unused; don't reach for it without a concrete reason, since
  nothing here has budgeted for it.
- **`site/vendor/phaser3-plugin-isometric.js`** (sebashwa/phaser3-plugin-
  isometric 0.0.7, MIT) — vendored, NOT wired into any scene. It exists
  for the still-open player-sprite roadmap item: once something moves
  relative to the static baked art, its `IsoSprite` depth-sorting
  (x+y+1.25z) is what keeps a moving token correctly layered against
  buildings. Today nothing in the game moves relative to anything else
  (the ground is one baked PNG the camera pans across — see the "North-
  up iso" rule above), so there is no caller yet and none should be
  added speculatively.
  - **Upstream only ships a CommonJS build** (`module.exports = …`),
    which throws `module is not defined` loaded as a plain `<script>`.
    The vendored file wraps upstream's untouched dist body in a small
    IIFE that supplies a local `module`/`exports` (it makes zero
    `require()` calls, so nothing else is needed) and republishes the
    result as `window.PhaserIso`. Verified in the pane (2026-08-26):
    the export surface is only `{default: IsoPlugin, IsoPhysics}` — the
    README's `IsoSprite`/`Point3`/`Cube` are used internally but not
    re-exported at this top level; `scene.add.isoSprite(...)` (wired up
    inside `IsoPlugin`'s constructor once it's registered) is how you
    actually get an IsoSprite. Re-vendoring means replacing only the
    marked span between the two `BEGIN/END upstream` comments — the
    wrapper itself is ours and should survive an upstream bump.
  - The plugin's module-level code reads `Phaser.GameObjects.Sprite`
    etc. at SCRIPT-LOAD time (webpack's eager module evaluation), so it
    must load after `phaser.min.js`, never before.
  - The original repo the user linked
    (lewster32/phaser-plugin-isometric) is Phaser 2-only and archived
    since 2018 — incompatible with this project's vendored Phaser 3.90.
    This fork is the maintained Phaser 3 successor; don't revert to the
    Phaser 2 one.
