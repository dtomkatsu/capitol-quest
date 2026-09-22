#!/usr/bin/env python3
"""DEPTH BANDS — a baked room split so a walking character can pass
BEHIND things in it.

A room is one painting, so a character drawn over it is drawn over all
of it: no railing, no post and no planter can ever stand in front. The
fix is to paint the room onto several targets and let the runtime
interleave the character by DEPTH.

WHAT A BAND IS, AND WHY THERE ARE SO FEW. Depth in this projection is
plan u+v (bigger is nearer the camera), so in principle every element
wants its own. In practice occlusion only matters where two things
OVERLAP ON SCREEN, and that collapses the list hard:

  - Anything the character can only ever see from one side needs no
    sort at all, just a side. The Capitol's mauka railing is only ever
    overlapped by characters standing behind it; the makai railing only
    by characters in front of it. Two bands, no depths.
  - Only something the character can walk BOTH WAYS AROUND needs its
    own depth — the hallway's pots, its legislator, the casing posts at
    the alcove mouth.

So a room is a big BACK band, a big FRONT band, and a handful of small
ones for the things you can circle.

BANDS ARE CROPPED TO THEIR OWN CONTENT. A full-canvas PNG per band puts
the room's weight up by the number of bands for no pixels; the objects
that need their own are small. Each band records its scene-px offset
and the runtime places it there.

THE GATE IS THE RECOMPOSITE. Compositing the bands in order must
reproduce the flat bake EXACTLY. That is what makes a split safe to
trust — it cannot silently become a different picture — and it is what
catches a band ordering that moved an element past something it
overlaps. `verify()` raises with the pixel count when it does.
"""

from __future__ import annotations

from PIL import Image

BACK = -1000.0             # always behind the character
FRONT = 1000.0             # always in front of it


class Bands:
    """Ordered draw targets for one room. `enabled=False` makes every
    band the same canvas, which IS the flat bake — so the renderer runs
    one code path and the split cannot drift from the shipped room."""

    def __init__(self, size, flat, enabled):
        self.size = size
        self.flat = flat
        self.on = enabled
        self.order = []                     # [(name, depth, Image)]
        self._by = {}

    def add(self, name, depth):
        """Declare a band. Order of declaration IS composite order."""
        if not self.on:
            self._by[name] = self.flat
            return self.flat
        im = Image.new("RGBA", self.size, (0, 0, 0, 0))
        self.order.append((name, depth, im))
        self._by[name] = im
        return im

    def __getitem__(self, name):
        return self._by[name]

    def verify(self, ref):
        """Composite in order over the room's own ground and compare to
        the flat bake. `ref` is the finished flat image (RGB)."""
        out = Image.new("RGBA", self.size, (0, 0, 0, 0))
        for _, _, im in self.order:
            out.alpha_composite(im)
        return out

    def emit(self, out_dir, prefix, ship, over, base=None):
        """Crop each band to its content, write it, and return the meta
        the room json carries. Sizes and offsets come out in SCENE px,
        the space every other coordinate in these files uses."""
        meta = []
        for name, depth, im in self.order:
            layer = im
            if base is not None and name == self.order[0][0]:
                # the first band carries the room's opaque ground, so it
                # is composited onto it rather than shipped transparent
                layer = base.copy()
                layer.alpha_composite(im)
            box = layer.getbbox()
            if box is None:
                continue
            k = ship * over
            x0, y0 = (box[0] // k) * k, (box[1] // k) * k
            x1, y1 = -(-box[2] // k) * k, -(-box[3] // k) * k
            crop = layer.crop((x0, y0, x1, y1))
            w, h = (x1 - x0) // over, (y1 - y0) // over
            crop = _down(crop, w, h)
            f = f"{prefix}_{name}.png"
            crop.save(out_dir / f)
            meta.append({"f": f, "x": x0 // k, "y": y0 // k,
                         "d": round(depth, 3)})
        return meta


def _down(im, w, h):
    """LANCZOS down, PREMULTIPLIED. PIL resizes RGBA channels
    independently, so an edge against transparency averages its colour
    with nothing and comes back as a dark hairline — the same trap the
    door-swing and character sheets already pay for."""
    a = im.getchannel("A")
    black = Image.new("L", im.size)
    rgb = Image.merge("RGB", [Image.composite(c, black, a)
                              for c in im.split()[:3]])
    rgb = rgb.resize((w, h), Image.LANCZOS)
    a2 = a.resize((w, h), Image.LANCZOS)
    pr, pa = rgb.load(), a2.load()
    for y in range(h):
        for x in range(w):
            al = pa[x, y]
            if al:
                r, g, b = pr[x, y]
                pr[x, y] = (min(255, r * 255 // al), min(255, g * 255 // al),
                            min(255, b * 255 // al))
    return Image.merge("RGBA", (*rgb.split(), a2))
