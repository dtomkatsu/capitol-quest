# Capitol Quest — Oʻahu

A browser-playable isometric game, JRPG pixel-art style, that explains
**state-level policymaking in Hawaiʻi**. Module 1 (in progress): **taxes &
the budget** — how money flows into and out of the State Capitol.

Current state: the explorable **overworld map of Oʻahu** (north-up), built
from real geodata, with the Hawaiʻi State Capitol as its first interactive
landmark.

## Play it locally

Any static server over `site/` works:

```bash
python3 -m http.server 8794 --directory site
```

Then open http://localhost:8794. Drag to pan, scroll/pinch to zoom, tap the
Capitol.

## How the map is made

The map is **baked at build time** into pixel-art PNG slices — the browser
just pans/zooms a big pre-rendered world (fast everywhere, phones included).
The ground is rendered per pixel in screen space (smooth polygon coastline,
distance-based water bands, noise-jittered terrain borders, relief-shaded
heightfield mountains) with outlined object sprites scattered on top.
Real geography drives every tile:

| Input | Source | Drives |
|---|---|---|
| `data/island_outline.geojson` | Māhele Atlas project | coastline → land/water/reef rings |
| `~/Revenue-Modeling-TOD/data/raw/road_centerlines.geojson` | City & County GIS (not committed, 40 MB) | road density → town / dense-urban tiles |
| `data/rail_alignment.geojson` | HART Skyline alignment | elevated rail viaduct ink |
| `data/stations.geojson` | HART | 19 station points (future tax/TOD module) |
| Hand-drawn ridgelines in `tools/build_map.py` | — | Koʻolau & Waiʻanae ranges, craters (Lēʻahi, Koko, Pūowaina) |
| `data/raw/2022indinc_tables.xlsx` | DOTAX Individual Income Tax Statistics TY2022, Table A-14 | tax inflow streams by ZIP (`tools/build_tax_flows.py`) |
| `data/raw/2020_Gaz_zcta_national.txt` | Census 2020 ZCTA gazetteer | ZIP centroid locations |

### Build pipeline

```bash
python3 tools/build_map.py     # classify 288x288 tile grid  -> build/map_grid.json + debug PNG
python3 tools/render_map.py    # bake pixel-art iso map      -> site/assets/map/*.png + site/map/oahu.json
python3 tools/make_sprites.py  # capitol, marker, sparkles   -> site/assets/sprites/*.png
python3 tools/render_capitol.py # Capitol grounds 2.5D scene -> site/assets/map/capitol_scene.png + site/map/capitol.json
python3 tools/make_event_art.py --scene <id>          # procedural banner -> site/assets/events/<id>.png
python3 tools/make_event_art.py --photo P --paint 8   # or from a photo, oil-paint filter for a painted look
```

Requires Python 3 with numpy + Pillow (matplotlib speeds up point-in-polygon
if present). Rebuild order matters: `build_map` → `render_map`.
`make_event_art.py --paint` additionally needs
`pip3 install opencv-contrib-python-headless` (`cv2.xphoto.oilPainting` —
the plain `opencv-python` package lacks the `xphoto` module); everything
else in the file runs without it.

**North-up isometric**: screen-up is geographic north, so the tile-grid axes
run diagonally across geography (+col = SE, +row = SW). All lon/lat →
tile-grid conversion goes through `lonlat_to_cell()` in `build_map.py`.

## Runtime

- [Phaser 3.90](https://phaser.io) (MIT), vendored at
  `site/vendor/phaser.min.js`. Canvas renderer on purpose (the world is one
  baked image; avoids WebGL/texture-size quirks).
- `site/js/main.js` — boot + world scene: camera intro flight, drag/wheel/
  pinch navigation, landmark labels that hold screen size across zoom,
  water-sparkle animation, JRPG dialogue box (DOM overlay).
- `?raf=mc` query param: dev-only requestAnimationFrame shim so hidden
  webviews (automated previews) can render. Never active for players.

## Roadmap

- [ ] Module 1 — Taxes & the Budget: enter the Capitol, follow a dollar
      (GET, income tax, TAT → general fund → departments)
- [ ] Player character / guide sprite walking the overworld
- [ ] Rail stations as interactive stops (ties into TOD & property-tax story)
- [ ] More landmarks (UH Mānoa, Aloha Tower, county buildings)
- [ ] Pixel webfont with Hawaiian diacritics (ʻokina/kahakō) for full JRPG
      typography; system font used meanwhile
- [ ] Sound: light ambient loop + UI blips
