# Capitol Quest — working notes

Educational isometric JRPG about Hawaiʻi state policymaking. Module 1:
taxes & the budget. Static site in `site/`, no build step for the frontend.

## Hard rules

- **North-up iso**: screen-up = geographic north. Grid axes are diagonal to
  geography — NEVER convert lon/lat to tiles by linear bbox scaling; always
  use `lonlat_to_cell()` / `cell_center_lonlat()` in `tools/build_map.py`.
- **Rebuild order**: `tools/build_map.py` → `tools/render_map.py`. Sprites:
  `tools/make_sprites.py`. The map is baked; editing `site/js/main.js` alone
  never changes terrain.
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

## Tax-flow layer (feature 1 — see FEATURES.md for the full scope)

`tools/build_tax_flows.py` parses DOTAX Table A-14 (individual income tax
by ZIP, TY2022) + Census ZCTA gazetteer → `site/map/tax_flows.json`;
runtime `buildFlows()`/`update()` in main.js drifts gold motes along
bezier paths into the Capitol (rate ∝ dollars, additive, alpha ≤ 0.55).
Island sections in A-14 are headed "O'AHU" / "MAUI COUNTY" etc. — match
via startswith, and keep the off-map px filter as the safety net. The
lon/lat→px transform ships in oahu.json under "transform" (written by
render_map) — downstream layers must use it, never re-derive offsets.

## Revenue-mix layer (feature 2a)

`tools/build_revenue.py` parses DOTAX Annual Report FY2024-25 Table 1.8
(pdfplumber; extracted digits arrive split — "4 ,630,396" — strip
whitespace in the number region) and REFUSES to write output unless the
row sum matches the printed TOTAL within 0.1%. New report year: drop the
PDF in data/raw/, update PDF/label constants, re-run.

## Data lineage

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
