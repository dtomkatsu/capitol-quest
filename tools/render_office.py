#!/usr/bin/env python3
"""Bake the HOUSE FINANCE CHAIR'S OFFICE — reception with staff
cubicles, then Kawaguchi's inner office — as a 2.5-D iso cutaway in
the same language as render_capitol.py (2:1 iso, RPG cutaway: near
walls sliced at knee height, interior partition sliced too with the
koa door standing full-height in its architrave).

Theme is the w2-finance-office banner (the Kawaguchi meeting): warm
KOA PANEL walls with dark vertical seams, big clean koa desk, low
credenza, twin cream-shade LAMPS as the light source (no windows —
the banner's room is lit by lamps), deep warm shadow, and the
banner's single cool accent (aloha blue) carried by the cubicle
fabric and binder spines.

Outputs (hand-versioned in JS via OFF_V — bump together):
  site/assets/map/office_finance.png
  site/map/office_finance.json     (spawn + hotspots, px in image space)

ON THE ROOMS' MODERN PIPELINE since 2026-09-23 (the second aesthetic
pass). This was the last bake on the old one: a 620x400 file (SS 2)
snap-fitted to the WHOLE canvas at runtime, so the room filled about half
the frame, and at the zoom that fit gave each file pixel became a 4x4
block — chunky beside the smooth Capitol the player walks in from. It
now does what the hallway does: SHIP/OVER (the AA baked once by a real
filter, full resolution shipped), a `view` rect in main.js with
continuous LINEAR zoom, the shared backdrop, and a `mark` per hotspot.
The painters were not rewritten: SDraw scales at the draw call and
iso()/lerp()/up() snap to the draw grid, exactly as in the other rooms.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

import roomlight

ROOT = Path(__file__).resolve().parent.parent
OUT_PNG = ROOT / "site" / "assets" / "map" / "office_finance.png"
OUT_JSON = ROOT / "site" / "map" / "office_finance.json"

W, H = 1240, 800
# SHIP / OVER, as in render_capitol.py and render_hallway.py (the long
# form of the argument is there): SHIP is file px per SCENE px, OVER a
# supersample on top, LANCZOS-resized away once at the end. The JSON
# keeps SCENE coordinates; meta.scale is 1/SHIP and the runtime scales
# the sprite back. (This was SS 2 — the old "draw full, ship HALF" trade
# for a room snap-fitted at zoom 0.5 — until 2026-09-23.)
SHIP = 2
OVER = 2
K = SHIP * OVER
CX, CY = 620, 420
U, V = 12, 7               # room half-extents in iso units
WH = 64                    # full wall height
CUT = 13                   # near/partition slice height (capitol rule)
CUT_CORE = (154, 146, 124) # same cut-core material as the capitol
PART_U = -4                # partition line: chair office = u < PART_U

rng = np.random.default_rng(11)


def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


INK = hx("#0a0e18")
CARPET = hx("#4a3527")     # warm dark office carpet
CARPET_L = hx("#57402f")
KOA_W = hx("#5c4326")      # wall panel base
KOA_WD = hx("#48331d")
KOA_WL = hx("#75552f")
SEAM = hx("#33231262")[:3] if False else hx("#332312")
DESK = hx("#8a5f36")
DESK_D = hx("#6d4a29")
DESK_L = hx("#a97e4f")
CRED = hx("#7d5734")
SHADE = hx("#f0e3c2")      # lamp shade cream
GLOW = (255, 210, 140)
BLUE = hx("#4a6478")       # the aloha-blue accent (banner shirt)
BLUE_D = hx("#3a4f60")
FAB = hx("#5a6a72")        # cubicle fabric, cooled
FAB_D = hx("#47545b")
PAPER = hx("#e8e2d0")
SCREEN = hx("#20262c")
SCREEN_L = hx("#3a4854")
KEY = hx("#f2c14e")
CHAIRC = hx("#3a3a44")


def snap(v):
    """Round to 1/K of a scene px — the grid the room is DRAWN on (see
    render_capitol.snap). At K = 1 this is round(), which is what it
    used to be."""
    return round(v * K) / K


def iso(u, v, dy=0.0):
    return (snap(CX + 16.0 * (u - v)), snap(CY + 8.0 * (u + v) - dy))


def lerp(p, q, t):
    return (snap(p[0] + (q[0] - p[0]) * t),
            snap(p[1] + (q[1] - p[1]) * t))


def up(p, dy):
    return (p[0], snap(p[1] - dy))


class SDraw:
    """ImageDraw taking SCENE px onto a canvas K times bigger — the same
    class as render_capitol.py's and render_hallway.py's, with the same
    three rules: PIL boxes are inclusive, `width` is a scene distance,
    and `point` is a K x K block. Polygons take the plain corner mapping
    so shared edges stay shared."""

    _BOX = ("rectangle", "ellipse", "arc", "chord", "pieslice")
    _SEQ = ("polygon", "line")

    def __init__(self, im):
        self._d = ImageDraw.Draw(im)

    @staticmethod
    def _pts(xy):
        if xy and isinstance(xy[0], (list, tuple)):
            return [(q[0] * K, q[1] * K) for q in xy]
        return [v * K for v in xy]

    @staticmethod
    def _kw(kw):
        if kw.get("width"):
            kw = dict(kw, width=max(1, int(round(kw["width"] * K))))
        return kw

    def __getattr__(self, name):
        fn = getattr(self._d, name)
        if name in self._BOX:
            def box(xy, *a, **kw):
                x0, y0, x1, y1 = xy
                return fn([x0 * K, y0 * K, (x1 + 1) * K - 1,
                           (y1 + 1) * K - 1], *a, **self._kw(kw))
            return box
        if name in self._SEQ:
            def seq(xy, *a, **kw):
                return fn(self._pts(xy), *a, **self._kw(kw))
            return seq
        if name == "point":
            def point(xy, fill=None):
                pts = xy if (xy and isinstance(xy[0], (list, tuple))) else \
                    [(xy[i], xy[i + 1]) for i in range(0, len(xy), 2)]
                for x, y in pts:
                    self._d.rectangle([x * K, y * K,
                                       x * K + K - 1, y * K + K - 1],
                                      fill=fill)
            return point
        return fn


def shade(c, f):
    return tuple(int(max(0, min(255, x * f))) for x in c)


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def quad(d, pts, c):
    d.polygon(pts, fill=c)


# ------------------------------------------------------------ floor
def paint_floor(d):
    pts = [iso(-U, -V), iso(U, -V), iso(U, V), iso(-U, V)]
    d.polygon(pts, fill=CARPET)
    # carpet tile jitter
    for k in range(2 * U):
        for l in range(2 * V):
            u0, v0 = -U + k, -V + l
            d.polygon([iso(u0, v0), iso(u0 + 1, v0),
                       iso(u0 + 1, v0 + 1), iso(u0, v0 + 1)],
                      fill=shade(CARPET, rng.uniform(0.94, 1.06)))


def paint_glow(img):
    """warm lamp pools — the banner's room is LAMP-lit"""
    lay = Image.new("RGBA", (W * K, H * K), (0, 0, 0, 0))
    d = SDraw(lay)
    def pool(u, v, r, alphas=(52, 30, 14), lift=0):
        x, y = iso(u, v)
        y -= lift
        for rr, a in zip((r * 0.45, r * 0.75, r), alphas):
            d.ellipse([x - rr, y - rr * 0.55, x + rr, y + rr * 0.55],
                      fill=GLOW + (a,))
    pool(-11.0, -3.6, 96, lift=18)     # credenza lamp 1 (washes wall)
    pool(-11.0, 0.9, 96, lift=18)      # credenza lamp 2
    pool(5.4, 3.6, 80)                 # reception desk lamp
    pool(2.6, -5.2, 70, (24, 14, 7), lift=12)   # cubicle task spill
    # CLIPPED TO THE ROOM (2026-09-23): the pools are ellipses up to 96px
    # across, and the wall lamps' reached over the wall's top into the
    # void — a halo hanging in the sky, which the new lit backdrop made
    # plain. Light lands on the floor and the two far walls, nowhere else.
    room = Image.new("L", lay.size, 0)
    SDraw(room).polygon([iso(-U, V), up(iso(-U, V), WH), up(iso(-U, -V), WH),
                         up(iso(U, -V), WH), iso(U, -V), iso(U, V)], fill=255)
    lay.putalpha(ImageChops.multiply(lay.getchannel("A"), room))
    img.alpha_composite(lay)


# ------------------------------------------------------------ walls
def koa_wall(d, e0, e1, ht, f=1.0):
    """full-height koa panel wall with dark vertical seams + top rail"""
    quad(d, [e0, e1, up(e1, ht), up(e0, ht)], shade(KOA_W, f))
    ln = math.hypot(e1[0] - e0[0], e1[1] - e0[1])
    # broad panel value drift
    n_p = max(2, int(ln // 34))
    for i in range(n_p):
        t0, t1 = i / n_p, (i + 1) / n_p
        a, b = lerp(e0, e1, t0), lerp(e0, e1, t1)
        fpan = f * (0.94 + 0.10 * ((i * 7) % 3) / 2)
        quad(d, [a, b, up(b, ht), up(a, ht)], shade(KOA_W, fpan))
    # seams
    n_s = max(2, int(ln // 11))
    for i in range(1, n_s):
        b = lerp(e0, e1, i / n_s)
        d.line([up(b, 4), up(b, ht - 5)], fill=shade(SEAM, f), width=1)
    # base shadow + top rail
    d.line([e0, e1], fill=shade(KOA_WD, f * 0.8), width=2)
    d.line([up(e0, ht - 3), up(e1, ht - 3)], fill=shade(KOA_WL, f), width=1)
    d.line([up(e0, ht), up(e1, ht)], fill=shade(KOA_WD, f), width=2)


def cut_wall(d, e0, e1, off, f=0.95):
    """near walls, RPG-sliced: koa stub + the cut core on top"""
    t0, t1 = up(e0, CUT), up(e1, CUT)
    quad(d, [e0, e1, t1, t0], shade(KOA_W, f))
    ln = math.hypot(e1[0] - e0[0], e1[1] - e0[1])
    for i in range(1, max(2, int(ln // 11))):
        b = lerp(e0, e1, i / max(2, int(ln // 11)))
        d.line([(b[0], b[1] - 2), (b[0], b[1] - CUT + 2)],
               fill=shade(SEAM, f), width=1)
    b0 = (t0[0] + off[0], t0[1] + off[1])
    b1 = (t1[0] + off[0], t1[1] + off[1])
    d.polygon([t0, t1, b1, b0], fill=CUT_CORE)
    d.line([t0, t1], fill=hx("#fff7e6"), width=2)
    d.line([b0, b1], fill=shade(CUT_CORE, 0.72), width=1)
    d.line([e0, e1], fill=shade(CARPET, 0.7), width=2)


# --------------------------------------------------------- furniture
def iso_box(d, u0, v0, u1, v1, h, top, fl, fr, dy=0.0):
    """box with top + SW + SE faces (viewed from S)"""
    tN, tE = iso(u0, v0, dy + h), iso(u1, v0, dy + h)
    tS, tW = iso(u1, v1, dy + h), iso(u0, v1, dy + h)
    bE, bS, bW = iso(u1, v0, dy), iso(u1, v1, dy), iso(u0, v1, dy)
    d.polygon([tW, tS, bS, bW], fill=fl)        # SW face
    d.polygon([tS, tE, bE, bS], fill=fr)        # SE face
    d.polygon([tN, tE, tS, tW], fill=top)
    return tN, tE, tS, tW


def lamp(d, u, v, dy=0.0):
    x, y = iso(u, v, dy)
    d.rectangle([x - 1, y - 14, x + 1, y], fill=hx("#3a2c1c"))
    d.polygon([(x - 6, y - 14), (x + 6, y - 14),
               (x + 4, y - 22), (x - 4, y - 22)], fill=SHADE)
    d.line([(x - 6, y - 14), (x + 6, y - 14)], fill=hx("#c9b88f"))
    # the lit underside of the shade. It was `fill=GLOW + (0,)` — a
    # TRANSPARENT fill that replaced pixels and only showed as this
    # light ellipse because convert("RGB") kept the colour; on an RGBA
    # ground it would punch a hole. Said outright now.
    d.ellipse([x - 8, y - 13, x + 8, y - 7], fill=GLOW)
    # glow halo
    return


def monitor(d, u, v, dy, flip=False):
    x, y = iso(u, v, dy)
    s = -1 if flip else 1
    d.polygon([(x - 5 * s, y - 3), (x + 4 * s, y - 6),
               (x + 4 * s, y - 14), (x - 5 * s, y - 11)], fill=SCREEN)
    d.polygon([(x - 4 * s, y - 5), (x + 3 * s, y - 7),
               (x + 3 * s, y - 13), (x - 4 * s, y - 10)], fill=SCREEN_L)
    d.rectangle([x - 1, y - 3, x + 1, y], fill=hx("#2c2c30"))


def papers(d, u, v, dy, n=3):
    x, y = iso(u, v, dy)
    for i in range(n):
        ox, oy = int(rng.uniform(-4, 4)), int(rng.uniform(-2, 2)) - i
        d.polygon([(x + ox - 5, y + oy), (x + ox + 3, y + oy - 4),
                   (x + ox + 8, y + oy - 1), (x + ox, y + oy + 3)],
                  fill=shade(PAPER, 1 - i * 0.05))


def office_chair(d, u, v, back_dy=16, col=CHAIRC):
    iso_box(d, u - 0.5, v - 0.5, u + 0.5, v + 0.5, 7,
            shade(col, 1.15), shade(col, 0.85), col)
    x, y = iso(u - 0.45, v, 7)
    d.polygon([(x - 4, y), (x + 4, y - 4),
               (x + 4, y - back_dy), (x - 4, y - back_dy + 4)],
              fill=shade(col, 1.05))


def plant(d, u, v):
    x, y = iso(u, v)
    d.ellipse([x - 8, y - 2, x + 8, y + 4], fill=shade(CARPET, 0.7))
    d.polygon([(x - 5, y - 6), (x + 5, y - 6), (x + 4, y), (x - 4, y)],
              fill=hx("#8c5535"))
    d.rectangle([x - 6, y - 8, x + 6, y - 6], fill=hx("#c08050"))
    for fx, fy, c in ((-8, -20, "#3f5f3a"), (-4, -24, "#567a4c"),
                      (0, -26, "#6f9660"), (4, -24, "#567a4c"),
                      (8, -19, "#3f5f3a"), (-10, -14, "#567a4c"),
                      (10, -15, "#6f9660")):
        bow = (x + fx // 2, y - 12 + fy // 2 - 3)
        d.line([(x, y - 8), bow], fill=hx(c), width=1)
        d.line([bow, (x + fx, y + fy)], fill=hx(c), width=1)


def standing_door(d, u, vc, hw_v=1.1):
    """koa double door standing full height in the SLICED partition"""
    e0, e1 = iso(u, vc - hw_v), iso(u, vc + hw_v)
    fr0 = lerp(e0, e1, -0.12); fr1 = lerp(e0, e1, 1.12)
    quad(d, [fr0, fr1, up(fr1, 52), up(fr0, 52)], hx("#3b2a19"))
    quad(d, [e0, e1, up(e1, 48), up(e0, 48)], DESK)
    mid = lerp(e0, e1, 0.5)
    d.line([up(mid, 1), up(mid, 47)], fill=shade(DESK, 0.55), width=2)
    for t in (0.25, 0.75):
        b = lerp(e0, e1, t)
        d.line([up(b, 10), up(b, 40)], fill=shade(DESK, 0.82), width=1)
    for t in (0.42, 0.58):
        b = lerp(e0, e1, t)
        d.line([up(b, 21), up(b, 26)], fill=KEY, width=2)
    quad(d, [up(fr0, 52), up(fr1, 52), up(fr1, 56), up(fr0, 56)],
         mix(KEY, PAPER, 0.4))
    return iso(u, vc)


# ------------------------------------------------------------- main
# ---- THE BACKDROP (tools/roomlight.py): the rooms' shared ground, in
# this room's frame. The pool is centred on ROOM_OFFICE.view and reaches
# exact INK inside the 1240x800 canvas; the shadow is the floor dropped
# SHADOW_DROP and pushed the way the Capitol's is.
BACKDROP_C = (620, 404)
BACKDROP_R = (560, 380)
BACKDROP_LIFT = (30, 39, 57)
SHADOW_DROP = 40
SHADOW_SUN = (-0.45, 0.12)
SHADOW_BLUR = 16
SHADOW_A = 0.60
# ROOM_OFFICE.view lives in main.js; it is repeated here so the bake can
# assert every hotspot lands inside it, as the other rooms do
VIEW = (291, 179, 949, 597)


def render():
    img = roomlight.backdrop(
        W, H, SHIP, K, INK, BACKDROP_LIFT, BACKDROP_C, BACKDROP_R,
        polys=[[iso(-U, -V, -SHADOW_DROP), iso(U, -V, -SHADOW_DROP),
                iso(U, V, -SHADOW_DROP), iso(-U, V, -SHADOW_DROP)]],
        sun=(SHADOW_SUN[0] * SHADOW_DROP, SHADOW_SUN[1] * SHADOW_DROP),
        blur=SHADOW_BLUR, alpha=SHADOW_A)
    d = SDraw(img)

    paint_floor(d)
    # rug in the chair's office
    rN = [iso(-10.5, -4.2), iso(-5.6, -4.2), iso(-5.6, 2.2), iso(-10.5, 2.2)]
    d.polygon(rN, fill=hx("#5e2f24"))
    d.polygon([lerp(rN[0], rN[2], 0.06), lerp(rN[1], rN[3], 0.06),
               lerp(rN[2], rN[0], 0.06), lerp(rN[3], rN[1], 0.06)],
              outline=hx("#8a4a34"), width=2)
    # far walls first — the lamp glow then washes over wall AND floor
    koa_wall(d, iso(-U, V), iso(-U, -V), WH, 1.0)     # NW (mauka)
    koa_wall(d, iso(-U, -V), iso(U, -V), WH, 0.86)    # NE
    paint_glow(img)
    d = SDraw(img)
    # framed photos on NE wall (reception side)
    for t in (0.62, 0.74):
        b = lerp(iso(-U, -V), iso(U, -V), t)
        d.rectangle([b[0] - 7, b[1] - 46, b[0] + 7, b[1] - 34],
                    fill=hx("#3b2a19"))
        d.rectangle([b[0] - 5, b[1] - 44, b[0] + 5, b[1] - 36],
                    fill=mix(BLUE, PAPER, 0.35))
    # Hawaiʻi seal plaque in the chair's office section
    b = lerp(iso(-U, V), iso(-U, -V), 0.72)
    d.ellipse([b[0] - 7, b[1] - 50, b[0] + 7, b[1] - 36], fill=KEY)
    d.ellipse([b[0] - 5, b[1] - 48, b[0] + 5, b[1] - 38],
              fill=shade(KEY, 0.72))

    # ---- chair's office (u < PART_U)
    # credenza against NW wall + twin lamps (the banner's composition)
    iso_box(d, -11.7, -4.4, -11.0, 1.6, 12, CRED, shade(CRED, 0.8),
            shade(CRED, 0.65))
    lamp(d, -11.2, -3.7, 12)
    lamp(d, -11.2, 0.9, 12)
    papers(d, -11.3, -1.4, 12, 2)
    # bookcase against NE wall: binder spines incl the blue accent
    tN, tE, tS, tW = iso_box(d, -10.2, -6.7, -6.4, -5.9, 34,
                             shade(CRED, 0.9), shade(CRED, 0.7),
                             shade(CRED, 0.55))
    e0, e1 = iso(-10.2, -5.9, 0), iso(-6.4, -5.9, 0)
    for row_y in (8, 18, 28):
        a, b2 = up(e0, row_y), up(e1, row_y)
        d.line([a, b2], fill=shade(CRED, 0.45), width=1)
        n_b = 12
        for i in range(n_b):
            t = (i + 0.5) / n_b
            bb = lerp(a, b2, t)
            col = (BLUE if i % 4 == 0 else
                   hx("#8a3a2e") if i % 4 == 1 else
                   hx("#b08a3a") if i % 4 == 2 else hx("#5a6a4a"))
            d.rectangle([bb[0] - 1, bb[1] - 8, bb[0] + 1, bb[1] - 1],
                        fill=col)
    # flag by the N corner
    fx, fy = iso(-11.1, -5.9)
    d.rectangle([fx - 1, fy - 54, fx + 1, fy], fill=hx("#77726a"))
    d.ellipse([fx - 3, fy - 58, fx + 3, fy - 53], fill=KEY)
    d.polygon([(fx + 1, fy - 53), (fx + 15, fy - 45), (fx + 1, fy - 32)],
              fill=mix(BLUE, PAPER, 0.25))
    d.polygon([(fx + 1, fy - 48), (fx + 10, fy - 44), (fx + 1, fy - 39)],
              fill=mix(hx("#c03b46"), PAPER, 0.3))
    # executive chair BEHIND the desk — drawn first so the desk
    # overlaps its seat and only the tall back shows (painter order).
    # A flat dark slab read as a monolith; the leather back needs its
    # koa cap rim and an edge light to read as a chair.
    iso_box(d, -10.3, -1.5, -9.4, -0.5, 8, hx("#343841"),
            hx("#282c33"), hx("#20242a"))
    bx, by = iso(-10.25, -1.0, 8)
    d.polygon([(bx - 5, by + 2), (bx + 5, by - 3),
               (bx + 5, by - 24), (bx - 5, by - 19)],
              fill=hx("#343841"))
    d.line([(bx - 5, by - 15), (bx + 5, by - 20)],
           fill=hx("#42485366"[:7]) if False else hx("#424853"), width=1)
    d.polygon([(bx - 5, by - 19), (bx + 5, by - 24),
               (bx + 5, by - 26), (bx - 5, by - 21)], fill=CRED)
    # the desk — big, clean, koa (banner: one folder, a phone)
    iso_box(d, -9.0, -3.0, -7.0, 1.0, 17, DESK, DESK_D, shade(DESK, 0.55))
    d.polygon([iso(-9.15, -3.15, 17), iso(-6.85, -3.15, 17),
               iso(-6.85, 1.15, 17), iso(-9.15, 1.15, 17)], fill=DESK_L)
    papers(d, -8.2, -0.6, 17, 1)
    px_, py_ = iso(-7.8, 0.6, 17)
    d.rectangle([px_ - 3, py_ - 2, px_ + 3, py_], fill=hx("#2c2c30"))
    px_, py_ = iso(-8.4, -2.2, 17)
    d.rectangle([px_ - 4, py_ - 2, px_ + 4, py_], fill=KEY)  # nameplate
    # guest chairs facing the desk — koa frames, aloha-blue seats
    for gv in (-2.0, 0.4):
        iso_box(d, -6.3, gv - 0.45, -5.5, gv + 0.45, 6,
                BLUE, BLUE_D, shade(BLUE, 0.7))
        gx, gy = iso(-5.55, gv, 6)
        d.polygon([(gx - 4, gy + 1), (gx + 4, gy - 3),
                   (gx + 4, gy - 14), (gx - 4, gy - 10)],
                  fill=CRED)

    # ---- sliced partition + standing door
    pe0, pe1 = iso(PART_U, -V), iso(PART_U, V)
    # slice runs in two segments around the door
    door_v = 3.4
    segs = [(-V, door_v - 1.35), (door_v + 1.35, V)]
    for v0, v1 in segs:
        s0, s1 = iso(PART_U, v0), iso(PART_U, v1)
        t0, t1 = up(s0, CUT), up(s1, CUT)
        quad(d, [s0, s1, t1, t0], shade(KOA_W, 0.92))
        b0 = (t0[0] - 9, t0[1] - 5)
        b1 = (t1[0] - 9, t1[1] - 5)
        d.polygon([t0, t1, b1, b0], fill=shade(CUT_CORE, 0.9))
        d.line([t0, t1], fill=hx("#d9d2c0"), width=1)
        d.line([s0, s1], fill=shade(CARPET, 0.7), width=2)
    door_px = standing_door(d, PART_U, door_v)

    # ---- reception (u > PART_U)
    # cubicle row along the NE wall — fabric in the aloha blue-grey
    for cu0 in (-1.5, 1.5, 4.5):
        cu1 = cu0 + 2.6
        # divider walls — SHORT returns, or they read as sofa backs
        iso_box(d, cu0, -6.8, cu0 + 0.22, -4.9, 22, FAB, FAB_D,
                shade(FAB, 0.8))
        iso_box(d, cu1, -6.8, cu1 + 0.22, -4.9, 22, FAB, FAB_D,
                shade(FAB, 0.8))
        # desk slab against the wall, top lit
        iso_box(d, cu0 + 0.28, -6.6, cu1 - 0.05, -5.5, 13,
                DESK_L, DESK_D, shade(DESK, 0.6))
        monitor(d, (cu0 + cu1) / 2, -5.9, 13)
        papers(d, cu1 - 0.7, -5.8, 13, 2)
        office_chair(d, (cu0 + cu1) / 2, -3.9, 15)
    # reception desk near the entry, L-shaped
    iso_box(d, 3.6, 3.0, 7.0, 4.1, 15, DESK, DESK_D, shade(DESK, 0.55))
    iso_box(d, 3.6, 0.8, 4.6, 3.0, 15, DESK, DESK_D, shade(DESK, 0.55))
    d.polygon([iso(3.45, 2.85, 15), iso(7.15, 2.85, 15),
               iso(7.15, 4.25, 15), iso(3.45, 4.25, 15)], fill=DESK_L)
    monitor(d, 4.2, 1.8, 15, flip=True)
    papers(d, 5.8, 3.6, 15, 2)
    lamp(d, 6.6, 3.4, 15)
    office_chair(d, 4.6, 4.9, 15)
    # waiting area by the SE wall
    office_chair(d, 10.3, -0.5, 14, hx("#4a4438"))
    office_chair(d, 10.3, 1.3, 14, hx("#4a4438"))
    plant(d, 10.6, 3.4)
    plant(d, -2.8, 5.8)

    # ---- near walls, sliced, with the entry gap in the SW run
    # SE wall (u = U) and SW wall (v = V), the SW with the entry gap at
    # u 5.2..7.8. THE CUT FACE GOES ACROSS THE WALL, INTO THE ROOM
    # (2026-09-23): the offsets were swapped — (9, -5) on the SE wall and
    # (-9, -5) on the SW one each run ALONG that wall, so each "top face"
    # was a zero-width sliver sheared past the wall's end, and it showed
    # as a stray pale line hanging beyond both outer corners. Inward is
    # -u for the SE wall, (-16, -8) per unit, and -v for the SW one,
    # (16, -8) per unit.
    cut_wall(d, iso(U, -V), iso(U, V), (-9, -5), 0.9)
    cut_wall(d, iso(-U, V), iso(5.2, V), (9, -5), 0.95)
    cut_wall(d, iso(7.8, V), iso(U, V), (9, -5), 0.95)
    # worn runner from the entry toward the chair's door
    run = [iso(6.9, 6.2), iso(7.6, 6.2), iso(-2.4, 4.6), iso(-3.1, 4.6)]
    d.polygon(run, fill=shade(CARPET, 1.12))
    # entry threshold + mat
    m0, m1 = iso(5.4, V - 0.1), iso(7.6, V - 0.1)
    d.polygon([m0, m1, (m1[0] - 14, m1[1] + 8), (m0[0] - 14, m0[1] + 8)],
              fill=shade(CARPET, 1.25))

    img = img.convert("RGB")
    # down by OVER, not to scene size — the OVER/SHIP split
    img = img.resize((W * SHIP, H * SHIP), Image.LANCZOS)
    img.save(OUT_PNG)
    bg = "#%02x%02x%02x" % img.getpixel((2, img.height // 2))

    def sp(v):          # the JSON is SCENE space and integer: round here
        return int(round(v))

    dpx = {
        "exit": iso(6.5, V),
        "reception": iso(5.2, 3.6),
        "cubicles": iso(2.8, -5.2),
        "door": door_px,
        "desk": iso(-8.0, -1.0),
    }
    # `mark` — where the runtime hangs each hotspot's marker, just over
    # the thing it marks: the reception desk's monitor (15 + ~14), the
    # cubicle dividers (22), the standing door's head (56), the chair's
    # desk and chair back (~26)
    lift = {"reception": 34, "cubicles": 28, "door": 60, "desk": 32}
    meta = {
        "name": "House Finance — Chair's Office",
        "image": "office_finance.png",
        # w/h stay SCENE size; `scale` is scene px per FILE px
        "w": W, "h": H, "scale": 1 / SHIP, "bg": bg,
        "spawn": [sp(iso(6.5, V - 1.2)[0]), sp(iso(6.5, V - 1.2)[1])],
        "hotspots": [
            dict(id="reception", name="Reception", kind="poi",
                 px=sp(dpx["reception"][0]), py=sp(dpx["reception"][1]) + 6,
                 text="Committee staff triage everything here — every "
                      "bill with a dollar figure in the House crosses "
                      "this desk on its way to the chair."),
            dict(id="cubicles", name="Committee Staff", kind="poi",
                 px=sp(dpx["cubicles"][0]), py=sp(dpx["cubicles"][1]) + 6,
                 text="Analysts who read every fiscal note. The "
                      "binders hold the executive budget request, "
                      "line by line."),
            dict(id="door", name="The Chair", kind="door",
                 px=sp(dpx["door"][0]), py=sp(dpx["door"][1]) + 6,
                 text="Beyond the koa doors: the member who decides "
                      "which revenue bills get a hearing at all."),
            dict(id="desk", name="Chair Kawaguchi", kind="poi",
                 px=sp(dpx["desk"][0]), py=sp(dpx["desk"][1]) + 6,
                 text="A clean desk, two lamps, and the quiet power "
                      "of the schedule. Bills die politely here — "
                      "by never being heard."),
            dict(id="exit", name="Back to the gallery", kind="exit",
                 px=sp(dpx["exit"][0]), py=sp(dpx["exit"][1]) + 20,
                 text=""),
        ],
    }
    for h in meta["hotspots"]:
        if h["id"] in lift:
            h["mark"] = [sp(dpx[h["id"]][0]),
                         sp(dpx[h["id"]][1] - lift[h["id"]])]
    # every hotspot inside the view rect, or it is visible and unpressable
    for h in meta["hotspots"]:
        assert (VIEW[0] <= h["px"] <= VIEW[2] and
                VIEW[1] <= h["py"] <= VIEW[3]), (
            f"hotspot {h['id']} ({h['px']}, {h['py']}) falls outside "
            f"view {VIEW} — keep ROOM_OFFICE.view and VIEW in step")
    OUT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    # the content bbox against the backdrop's own ground — what the
    # `view` rect is measured from (plus breathing room)
    ref = np.asarray(roomlight.backdrop(
        W, H, SHIP, SHIP, INK, BACKDROP_LIFT, BACKDROP_C, BACKDROP_R,
        polys=[[iso(-U, -V, -SHADOW_DROP), iso(U, -V, -SHADOW_DROP),
                iso(U, V, -SHADOW_DROP), iso(-U, V, -SHADOW_DROP)]],
        sun=(SHADOW_SUN[0] * SHADOW_DROP, SHADOW_SUN[1] * SHADOW_DROP),
        blur=SHADOW_BLUR, alpha=SHADOW_A).convert("RGB"), np.int16)
    arr = np.asarray(img, np.int16)
    ys, xs = np.where(np.abs(arr - ref).max(axis=-1) > 10)
    bbox = (int(xs.min()) // SHIP, int(ys.min()) // SHIP,
            int(xs.max()) // SHIP, int(ys.max()) // SHIP)
    print("wrote", OUT_PNG.name, f"{img.width}x{img.height}"
          f" (scene {W}x{H} @ ship {SHIP}x, over {OVER}x)", "and",
          OUT_JSON.name)
    print("content bbox:", bbox, "-> suggested view:",
          [bbox[0] - 24, bbox[1] - 24, bbox[2] + 24, bbox[3] + 24])


if __name__ == "__main__":
    render()
