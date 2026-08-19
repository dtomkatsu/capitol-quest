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
s.stopIntro(); s.cameras.main.setZoom(1.3);   // maxZoom is 1.35
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
  - PORTRAITS ARE FACELESS, as ever. But bigger makes that rule HARDER:
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
  `site/assets/events/<id>.png` (960x480), shown when a dialogue (or a
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
    2. **Resolution — `DISPLAY`, now 3 (960 wide, was 2 / 640).** The
       column is ~986px at the session panel's 1040px width, so 640
       was being upscaled 1.54x by the browser and reading soft. That
       640 was inherited from a ~615-652px column the widened panel had
       made obsolete. MEASURE `.sd-art`'s rendered width if the panel
       ever changes again.
       Corollary: `PAINT_W` is now a fixed working width for the brush,
       deliberately NOT `2 x output`, so `--paint 4` in a recorded
       recipe keeps meaning the same brush after a DISPLAY change.
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
  - **Designed at 320x110, SHIPPED at 640x220.** Resolving natively to
    640 (rather than rendering 320 and upscaling) is what lets a figure
    exist at all — see the crowd note above. The column is ~615–652px
    wide depending on the overlay scrollbar, so the file is only ever
    resampled by about a percent; `.sd-art` therefore deliberately does
    NOT set `image-rendering: pixelated`, which would turn that small
    downscale into dropped rows. Don't "fix" either half alone.
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
  There is no week 0 — the session starts at week 1 (Opening Day),
  whose calendar entry carries `agenda: true` so the same turn also
  locks the ≤3-bill agenda (`S.agendaLocked`) that lined-up members
  will introduce.
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
    back/forward nav plate. The ≤3-bill cap is SHARED across both
    steps — step 2 can open with the budget already spent, which is
    the module's argument; don't give each step its own cap.
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
- The weekly overlay auto-pops only while the week's event is
  unplayed; generic weeks cycle `genericEvents` by `(week-2) % n`.
  Pinning a scripted event to a week SHIFTS that cycle rather than
  dropping anything — weeks 2, 3 and 4 are scripted
  (`w2-kawaguchi` / `w3-federal` / `w4-souza`), so the six generics run
  weeks 5–15 at indices 3,4,5,0,1,2,3,4,5,0,1 and all six still appear.
  **Re-check the whole rotation after pinning a week or adding a
  generic** (`ev-introducer` made it six on 2026-08-15); a generic that
  only lands on pinned weeks would vanish from the session entirely.
- **The scripted opening is weeks 1–4, and it is a chain.** Opening Day
  (the caucus, `kawaguchi-date`) → week 2 the courtesy call in
  Kawaguchi's office (`souza-intro`) → **week 3 `w3-federal`, the HR1
  safety-net briefing** → week 4 failing to reach Souza (`w4-souza`),
  where `souza-intro` is worth +3 on the hallway roll (58% → 92% at the
  same skills). Flags are the only cross-week memory the engine has —
  there is no node-level `req`/`if`, so a past choice can change a
  later scene ONLY as a `{"from": "flag"}` check mod. Write for that.
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
  Rebuilt 2026-08-15; four things must not regress:
  - **The session panel is WIDER than the other overlays on purpose**
    (`#session-overlay .ovl-panel`, 1040px vs the shared 680px). The
    strip is a fixed 940px — that width is what keeps eleven milestone
    labels from colliding — so at 680px only ~634px of it was ever on
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
    still inside, so week 6 reads "First Lateral"). Eleven labels at
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
- **Support/influence are ALSO per-bill** (2026-08-13): `S.metrics.*`
  is the campaign's global numbers; each `S.bills[i]` carries its own
  `support`/`influence`, seeded at introduction from the global numbers
  plus a small editorial tilt by tax family (`chairs.json`
  `gate.familyTilt`). `chairOdds`/`floorOdds` read the BILL's numbers,
  not the global ones — that split is what makes low-influence
  (never heard) and low-support (heard but diluted at the chair gate,
  `gate.dilution`) genuinely different failure modes instead of both
  feeding one probability. New bills always need this seed
  (`startBills`); old saves need `migrateBills()` at boot, or their
  bills' odds silently go `NaN` and stop being heard forever.
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
  `.rolling` (dice cycling via a 75ms interval, "the dice are out",
  choice strip EMPTIED so nothing is clickable). Since 2026-08-15 the
  reveal is a POP-OUT TRAY (`popTray` in main.js, `.sd-tray` in CSS)
  centered over the whole panel: a veil dims the scene, a card pops
  with the skill name, two real 3×3 pip dice tumbling (`setFace`/
  `pipHtml` — a numeral in a box reads as a form field), the DC line,
  then dice slam down staggered, the arithmetic ticks in, and the
  verdict stamps SUCCESS/FAILURE in verdict color. The inline card is
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
- **The HUD chip is a PROGRESS BAR, not a dot strip** (2026-08-15,
  user's call — `renderHudTimeline`, `#hud-timeline`). At 168px the old
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
  - **PORTRAITS ARE FACELESS**, the same house rule as the event
    banners and the skill glyphs: a silhouette at a committee desk, a
    collar, a nameplate. No features, ever. Drawings live in the
    `PORTRAIT` map in main.js, named by the card's `art` key.
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
- Calibrated by simulation (20k sessions/profile, see the design doc):
  passive play enacts ~5-9% of bills, engaged ~19-31%, insider ~30-45%,
  a tax CREDIT passes ~1.5× as often as a wealth tax at every skill level,
  and "never heard" is the leading cause of death in every profile. If a
  change moves those a lot, that is a finding to explain.

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
