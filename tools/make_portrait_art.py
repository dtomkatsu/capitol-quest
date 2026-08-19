#!/usr/bin/env python3
"""Cut a character PORTRAIT out of a banner source photograph.

The portrait rail (`.sd-card` / `.cc-art` in the session overlay) is a
3:4 plate held beside the transcript for the whole conversation. It used
to hold a drawn faceless silhouette (`PORTRAIT` in main.js). For a
character who already appears in a photographic banner, the honest
portrait is a CROP OF THAT SAME PHOTOGRAPH: it is the same person, the
same room, the same light, so the rail and the banner cannot drift.

The treatment is deliberately the SAME as `make_event_art.py --photo`,
step for step — mild oil-paint pass, a few percent of grade toward the
overlay ground, grain, a soft vignette, then an adaptive palette — so a
portrait belongs to the same picture set as the banners rather than
looking like a photo pasted onto game art. Two things are portrait-
specific:

- **The brush is anchored to the OUTPUT, not to PAINT_W.** paintify()
  runs the banner at a fixed 1280px working width for a 960px output,
  i.e. 1.33x. A portrait is 540px wide, so its working width is 720 —
  otherwise the same `--paint 4` recipe would land a visibly finer
  brush on the portrait than on the banner beside it.
- **The crop is given in SOURCE PIXELS** (`--box`), not fractions. A
  banner's `--center` has to survive a change of banner ratio; a
  portrait box is just a rectangle around a head and never moves.

Recipes go in data/raw/events/BANNERS.md with the banners.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from make_event_art import BOUNCE, INK, mix

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "assets" / "portraits"

W, H = 180, 240          # the rail's CSS box — a 3:4 plate
DISPLAY = 3              # shipped file is 540x720
PAINT_RATIO = 4 / 3      # working width / output width, as the banner


def portrait(path, box, paint=4, paint_strength=0.55, grade=0.05,
             colors=96, noise=None, soften=None, soften_radius=None,
             soften_strength=0.72, vignette=0.30, dither=None):
    # Same resolution-from-strength as make_event_art.from_photo, and
    # for the same reason: a FULLY painted image has flat colour regions
    # that dithering muddies back toward "filtered photo", killing the
    # brushwork the paint pass exists to create, while a mild blend
    # still has photographic gradients that NEED dithering to survive a
    # small palette. Verified side by side on this portrait at 0.85.
    heavy = bool(paint) and paint_strength >= 0.85
    if dither is None:
        dither = not heavy
    if noise is None:
        noise = 1 if heavy else 3

    ow, oh = W * DISPLAY, H * DISPLAY
    src = Image.open(path).convert("RGB")

    # --- crop to the rail's aspect, holding the box's centre
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw, bh = x1 - x0, y1 - y0
    if bw / bh > ow / oh:                    # box is wider than 3:4
        bh = bw * oh / ow
    else:
        bw = bh * ow / oh
    crop = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    img = src.crop(tuple(int(round(v)) for v in crop))

    if paint:
        img = _paint(img, ow, oh, paint, paint_strength, soften,
                     soften_radius, soften_strength, crop)
    else:
        img = img.resize((ow, oh), Image.LANCZOS)

    arr = np.array(img).astype(np.float32)
    arr = arr * (1 - grade) + np.array(mix(INK, BOUNCE, 0.22),
                                       dtype=np.float32) * grade
    if noise:
        n = np.random.RandomState(11).randint(-noise, noise + 1,
                                              arr.shape[:2])
        arr = arr + n[:, :, None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # settle the plate into the rail's dark ground. Gentler and rounder
    # than the banner's: this one is a tall box with a head in the
    # middle of it, so a wide ellipse would darken the shoulders only.
    if vignette:
        vig = Image.new("L", (ow, oh), 0)
        ImageDraw.Draw(vig).ellipse([-ow * 0.30, -oh * 0.22,
                                     ow * 1.30, oh * 1.22], fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(ow * 0.10))
        img = Image.blend(
            Image.composite(img, Image.new("RGB", (ow, oh), INK), vig),
            img, 1 - vignette)

    # left in P mode on purpose: the rail is a small plate and a
    # palette PNG of it is a third the size of the same pixels written
    # as truecolour. The banners convert back to RGB because they are
    # composited further; nothing composites this.
    return img.quantize(
        colors=colors, method=Image.MEDIANCUT,
        dither=Image.FLOYDSTEINBERG if dither else Image.Dither.NONE)


def _paint(img, ow, oh, radius, strength, soften, soften_radius,
           soften_strength, crop):
    import cv2

    ww = int(round(ow * PAINT_RATIO))
    work = img.resize((ww, int(round(ww * oh / ow))), Image.LANCZOS)
    bgr = cv2.cvtColor(np.array(work), cv2.COLOR_RGB2BGR)
    out = Image.fromarray(cv2.cvtColor(cv2.xphoto.oilPainting(bgr, radius, 1),
                                       cv2.COLOR_BGR2RGB))
    if strength < 1.0:
        out = Image.blend(work, out, max(0.0, strength))

    if soften:                                # source px -> this frame
        cx0, cy0, cx1, cy1 = crop
        fw, fh = work.size
        sx0, sy0, sx1, sy1 = soften
        bx = ((sx0 - cx0) / (cx1 - cx0) * fw, (sy0 - cy0) / (cy1 - cy0) * fh,
              (sx1 - cx0) / (cx1 - cx0) * fw, (sy1 - cy0) / (cy1 - cy0) * fh)
        r = soften_radius or max(radius * 2, int((bx[2] - bx[0]) * 0.07), 6)
        heavy = Image.fromarray(
            cv2.cvtColor(cv2.xphoto.oilPainting(bgr, r, 1), cv2.COLOR_BGR2RGB))
        mask = Image.new("L", work.size, 0)
        ImageDraw.Draw(mask).ellipse(list(bx),
                                     fill=int(255 * soften_strength))
        mask = mask.filter(ImageFilter.GaussianBlur((bx[2] - bx[0]) * 0.24))
        out = Image.composite(heavy, out, mask)

    return out.resize((ow, oh), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photo", required=True)
    ap.add_argument("--id", required=True, help="output stem, e.g. kawaguchi")
    ap.add_argument("--box", required=True, metavar="X0,Y0,X1,Y1",
                    help="crop around the head, in SOURCE PIXELS; it is "
                         "widened or heightened to 3:4 about its centre")
    ap.add_argument("--paint", type=int, default=4)
    ap.add_argument("--paint-strength", type=float, default=0.55)
    ap.add_argument("--grade", type=float, default=0.05)
    ap.add_argument("--colors", type=int, default=96)
    ap.add_argument("--noise", type=int, default=None,
                    help="grain; default resolves from --paint-strength")
    ap.add_argument("--no-dither", action="store_true",
                    help="force dithering off (the default already "
                         "turns it off at --paint-strength >= 0.85)")
    ap.add_argument("--vignette", type=float, default=0.30)
    ap.add_argument("--soften", metavar="X0,Y0,X1,Y1", default=None,
                    help="heavier brush over this box (SOURCE PIXELS)")
    ap.add_argument("--soften-radius", type=int, default=None)
    ap.add_argument("--soften-strength", type=float, default=0.72)
    a = ap.parse_args()

    box = tuple(float(v) for v in a.box.split(","))
    soften = tuple(float(v) for v in a.soften.split(",")) if a.soften else None
    img = portrait(a.photo, box, a.paint, a.paint_strength, a.grade,
                   a.colors, a.noise, soften, a.soften_radius,
                   a.soften_strength, a.vignette,
                   dither=False if a.no_dither else None)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{a.id}.png"
    img.save(p, optimize=True)
    print(f"wrote {p.relative_to(ROOT)}  {img.width}x{img.height}")


if __name__ == "__main__":
    main()
