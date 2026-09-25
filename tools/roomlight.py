#!/usr/bin/env python3
"""THE ROOMS' SHARED BACKDROP — a lit pool behind the building and the
building's own shadow falling into it.

It started in render_capitol.py (2026-09-22, "more slick"), where the
void around the cutaway was 88px squares of noise. Once the Capitol had
it, the hallway and the Finance office sat on flat ink beside it and read
as a different game (2026-09-23, the second aesthetic pass), so it lives
here and every room bake calls the same function. The full argument —
why a PLAN footprint and not a silhouette, why the pool reaches exact INK
inside the canvas, why there is no dither — is in CLAUDE.md under "The
slick pass"; the rules it leaves every caller with are:

  - The pool must reach EXACTLY `ink` inside the canvas. The runtime
    letterboxes a room with `bg`, which each bake samples off its own
    finished edge, so a pool that runs off the canvas draws the
    picture's rectangle on a wide window.
  - The shadow is the room's PLAN FOOTPRINT dropped under its floor and
    pushed along the room's own sun. Pass the footprint polygons already
    projected at the drop (scene px); this module only shifts, blurs and
    darkens.
  - No dither: an 8-bit pool this dark steps one level at a time, under a
    just-noticeable difference, and noise costs the PNG its compression.

Computed at SHIP resolution — where it ships — and held through the OVER
downsample by a NEAREST upscale.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def backdrop(w, h, ship, k, ink, lift, center, radii, polys=(),
             sun=(0.0, 0.0), blur=22, alpha=0.62):
    """The ground a room is painted on, as an RGBA image at DRAW size.

    w, h      scene size of the room's canvas
    ship, k   file px per scene px, and draw px per scene px
    ink/lift  the colour at the canvas edge, and at the pool's centre
    center    the pool's centre, scene px (the room's view-rect centre)
    radii     the pool's reach, scene px — must stay inside the canvas
    polys     the footprint, scene px, ALREADY at the drop
    sun       the screen shift applied to the footprint, scene px
    blur      shadow softness, scene px
    alpha     the shadow's darkening at its core
    """
    sw, sh_ = w * ship, h * ship
    ys, xs = np.mgrid[0:sh_, 0:sw].astype(np.float32)
    X, Y = (xs + 0.5) / ship, (ys + 0.5) / ship
    r = np.hypot((X - center[0]) / radii[0], (Y - center[1]) / radii[1])
    pool = smoothstep(0.0, 1.0, 1.0 - r)
    base = np.array(ink, np.float32)
    col = base + (np.array(lift, np.float32) - base) * pool[..., None]
    if polys:
        m = Image.new("L", (sw, sh_), 0)
        dm = ImageDraw.Draw(m)
        for poly in polys:
            dm.polygon([((q[0] + sun[0]) * ship, (q[1] + sun[1]) * ship)
                        for q in poly], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(blur * ship))
        s = np.asarray(m, np.float32) / 255.0 * alpha
        col *= (1.0 - s)[..., None]
    out = Image.fromarray(np.clip(np.rint(col), 0, 255).astype(np.uint8))
    return out.resize((w * k, h * k), Image.NEAREST).convert("RGBA")
