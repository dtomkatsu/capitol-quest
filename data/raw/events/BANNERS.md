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
