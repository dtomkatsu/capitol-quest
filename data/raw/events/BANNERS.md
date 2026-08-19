# Event banner build recipes

Every shipped banner in `site/assets/events/`, with the exact
`tools/make_event_art.py` invocation that produced it. **Add a line here
whenever you ship a banner** — the args are not recoverable from the PNG,
and reconstructing them once already cost a brute-force search over
`--center` plus an analytic fit of the `--soften` ellipse against a diff
map (2026-08-18). Sources are the `*-src.jpg` files beside this note.

Run from the repo root. Output is 640x320 (`W, H` in the tool).

```bash
python3 tools/make_event_art.py --photo data/raw/events/w1-opening-src.jpg \
  --id w1-opening --center 0.42 --paint 4

python3 tools/make_event_art.py --photo data/raw/events/w2-finance-src.jpg \
  --id w2-finance --center 0.58 --paint 4 --colors 96

python3 tools/make_event_art.py --photo data/raw/events/w2-finance-office-src.jpg \
  --id w2-finance-office --center 0.50 --paint 4 --colors 96 \
  --soften 0.4656,0.4198,0.5344,0.5687 --soften-radius 7 --soften-strength 0.72
```

## Repaired sources

`w2-finance-office-src.jpg` is NOT the file that came out of the image
model — that one is kept as `w2-finance-office-raw.jpg` and the shipped
source is a repaired copy of it (2026-08-19, user's call: "that ugly
splotch up and to the right of him"). The raw photo carries a
generation artifact on the wall behind Kawaguchi: an oval of
desaturated grey-mauve where the koa panelling should be. It is subtle
in the raw photo — a chroma drop, not a lightness jump — and the
banner pipeline AMPLIFIES it, because the 96-colour adaptive palette
on a room that is 90% brown wood has nothing to spend on the one
low-chroma region in frame and snaps it to a flat grey.

Do not chase this downstream. It was measured: 160 and 220 colours,
MAXCOVERAGE and FASTOCTREE all still show it, because the patch is
really in the photograph. Repair it once, at the source:

```bash
python3 tools/depatch_photo.py \
  --photo data/raw/events/w2-finance-office-raw.jpg \
  --out data/raw/events/w2-finance-office-src.jpg \
  --ellipse 1835,450,255,190 --mirror-y 280
```

Then re-run the banner command above unchanged — the recipe never sees
the repair. `--mirror-y` is the horizontal axis the wood GRAIN is
mirrored about and must land in clean wall just above the patch; the
grain is vertical, so a vertical mirror keeps every grain line and
every panel seam running the right way.

## Portraits

The portrait rail beside the transcript takes a 3:4 crop of the SAME
photograph (`tools/make_portrait_art.py`, output
`site/assets/portraits/<id>.png`, wired up by a `photo` key on the
character's `card` in session.json). Same treatment as the banners,
step for step, so the two belong to one picture set.

```bash
python3 tools/make_portrait_art.py \
  --photo data/raw/events/w2-finance-office-src.jpg \
  --id kawaguchi --box 1180,560,1640,1173 \
  --paint 6 --paint-strength 0.85 \
  --soften 1311,645,1505,873 --soften-radius 18 --soften-strength 0.6
```

Notes on those numbers:

- **The portrait is painted HARDER than the banner** (6 @ 0.85 against
  the banner's 4 @ 0.55; 2026-08-19, user's call — "I want the face
  cards to have the painterly effect"). It can afford to be: a banner
  is a whole room the player has to read, where heavy brushwork eats
  the architecture, while the portrait is one head at 180px and the
  brush is the only thing standing between "game art" and "photo pasted
  into the UI". 0.55 and 0.72 both still read as a filtered photograph
  at rail size; 1.0 starts dissolving him.
- **0.85 is the threshold where dithering turns OFF**, and the tool
  resolves that from the strength exactly the way `from_photo` does —
  a fully painted image has flat colour regions that Floyd-Steinberg
  muddies back toward "filtered photo", killing the brushwork the paint
  pass exists to create. Grain drops to 1 with it. Verified side by
  side on this portrait; the dithered version is visibly noisier in the
  aloha shirt for no gain.
- **`--soften` here is a brush on the FACE, not a redaction.** The
  banner's face pass exists to dissolve identity (house rule: no faces
  in focus). This one is smaller relative to the face — radius 18 at
  0.6, against a face ~304px wide in the working frame, where the
  banner's 7 sits on a face ~88px wide — so it reads as the features
  being painted rather than erased. The rail portrait IS the
  identification; a dossier headshot with its face dissolved is a
  redaction. The faceless house rule still governs every DRAWN portrait
  (`PORTRAIT` in main.js) and every crowd figure in a banner.
- The `--soften` box is the same face rectangle as the banner's, just
  in source PIXELS rather than fractions: 0.4656,0.4198,0.5344,0.5687
  x 2816x1536 = 1311,645,1505,873.

Notes on the args, so a re-render is a decision and not a guess:

- **`--center` is aspect-dependent and must be remapped if `H` changes.**
  It picks where the surviving band starts, so the same number frames a
  different part of the photo at a different ratio. To keep a composition
  when the ratio changes, hold the band's CENTRE fixed:
  `band = c*(1-k) + k/2` with `k = src_aspect / banner_aspect`, then
  `c_new = (band - k_new/2) / (1 - k_new)`. The 2.9:1 -> 2:1 change on
  2026-08-18 moved w1 0.45 -> 0.42 and w2-finance 0.55 -> 0.58 that way;
  the office banner is symmetric and stayed at 0.50.
- **`--soften` is in fractions of the SOURCE photo**, deliberately, so it
  survives exactly this kind of ratio change untouched — it is a fact
  about where the face is in the photograph, not about the crop.
- The office banner's `--soften-radius 7 --soften-strength 0.72` are a
  notch above the 6 / 0.65 that shipped at 2.9:1. Nothing about the face
  changed size; the taller frame quantizes against a different adaptive
  palette (much more brown wood in shot), which brought the features back
  slightly, and this puts them back where they were. Judge it against the
  house rule — placement and light survive, identity does not — not
  against the numbers.
- Both w2 banners need `--colors 96`: a 32-colour adaptive palette on a
  room that is 90% brown wood posterizes the walls into blotches.
