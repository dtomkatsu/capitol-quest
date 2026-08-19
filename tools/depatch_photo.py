#!/usr/bin/env python3
"""Repair a flat, discoloured patch in a source PHOTOGRAPH.

Why this exists: `w2-finance-office-src.jpg` carries a generation
artifact on the wall behind Kawaguchi — an oval of desaturated
grey-mauve where the koa panelling should be. In the raw photo it is
subtle (chroma drop, not a lightness jump), but the banner pipeline
AMPLIFIES it: `make_event_art.py` grades toward the overlay ground and
then quantizes to a 96-colour adaptive palette that is almost entirely
browns, so the one low-chroma region in frame snaps to a flat grey and
reads as a splotch. Fixing it downstream is hopeless — 220 colours and
every quantizer PIL has still show it (measured 2026-08-19) — because
the patch is really there. So it gets repaired ONCE, here, and the
banner recipe in data/raw/events/BANNERS.md is unchanged.

The repair is frequency-split, not a clone stamp or an inpaint:

  LOW frequencies come from the wall's own illumination, rebuilt by
  interpolating horizontally ACROSS the patch between clean columns on
  either side and blurring hard. That keeps the lamp falloff and the
  panel's true hue, which is the half the artifact actually broke.

  HIGH frequencies (the grain) come from the same columns MIRRORED
  about a horizontal axis above the patch. Koa panelling runs vertical,
  so a vertical mirror keeps every grain line running the right way and
  keeps the panel seams — which are vertical, and therefore identical
  in the mirrored rows — exactly where they were. Row indices mirror by
  ABSOLUTE VALUE rather than clipping: clipping repeats row 0 and
  smears the bottom of the patch into vertical streaks (seen, fixed).

  The two are recombined inside a smoothstep-feathered ellipse, so
  nothing has a boundary.

Blur, don't clone-stamp: a clone brings its own lighting with it and
this wall is lit from two lamps at the frame edges.

Usage (the shipped invocation is recorded in BANNERS.md):

  python3 tools/depatch_photo.py --photo IN.jpg --out OUT.jpg \
      --ellipse 1835,450,255,190 --mirror-y 280
"""

from __future__ import annotations

import argparse

import numpy as np
from PIL import Image, ImageFilter

BLUR = 45          # separates "illumination" from "grain" for this wall
FEATHER = 0.45     # ellipse radii over which the repair fades out
REACH = 1.4        # how far past the radii the clean sample columns sit


def depatch(img, cx, cy, rx, ry, mirror_y, blur=BLUR, feather=FEATHER):
    a = np.array(img.convert("RGB"), np.float32)
    h, w, _ = a.shape

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    m = np.clip((1 + feather - d) / feather, 0, 1)
    m = (m * m * (3 - 2 * m))[..., None]          # smoothstep

    # --- low frequency: the wall's light, with the patch interpolated out
    xa, xb = int(cx - rx * REACH), int(cx + rx * REACH)
    y0, y1 = int(cy - ry * REACH), int(cy + ry * REACH)
    flat = a.copy()
    left = a[y0:y1, xa - 30:xa].mean(1)[:, None, :]
    right = a[y0:y1, xb:xb + 30].mean(1)[:, None, :]
    t = np.linspace(0, 1, xb - xa, dtype=np.float32)[None, :, None]
    flat[y0:y1, xa:xb] = left * (1 - t) + right * t
    lo = _blur(flat, blur)

    # --- high frequency: grain from the same columns, mirrored upward
    rows = np.clip(np.abs(2 * mirror_y - np.arange(h)), 0, h - 1)
    donor = a[rows]
    hi = donor - _blur(donor, blur)

    out = a * (1 - m) + (lo + hi) * m
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def _blur(arr, r):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return np.array(im.filter(ImageFilter.GaussianBlur(r)), np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ellipse", required=True, metavar="CX,CY,RX,RY",
                    help="patch to repair, in SOURCE PIXELS")
    ap.add_argument("--mirror-y", type=int, required=True,
                    help="horizontal axis (source px) the grain is "
                         "mirrored about; put it just above the patch, "
                         "in clean wall")
    ap.add_argument("--blur", type=int, default=BLUR)
    ap.add_argument("--feather", type=float, default=FEATHER)
    ap.add_argument("--quality", type=int, default=95)
    a = ap.parse_args()

    cx, cy, rx, ry = (float(v) for v in a.ellipse.split(","))
    img = depatch(Image.open(a.photo), cx, cy, rx, ry, a.mirror_y,
                  a.blur, a.feather)
    img.save(a.out, quality=a.quality, subsampling=0)
    print(f"wrote {a.out}  {img.width}x{img.height}")


if __name__ == "__main__":
    main()
