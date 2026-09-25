#!/usr/bin/env python3
"""Bake the OPENING-WEEK HALLWAY — a corridor deep in the House wing,
from the user's reference photo (2026-08-23): warm white walls, a
glossy red-brown floor that reflects everything standing on it, tall
koa doors (the far one with a notice taped to it), a glazed building
directory, and the stretch where the hallway widens into a lobby —
rendered as a full-height RECESS in the far wall, the same language
as the capitol bake's hallway portals, so the whole widened area is
visible instead of standing between the camera and the room. THE
LEGISLATOR — the player's House introducer, aloha shirt and
Opening-Day lei — stands off to the side in that lobby, beside their
own office door. Week 1 only: ROOM_HALLWAY in main.js boots here and
the first End Turn retires the room for the Capitol.

Same 2.5-D cutaway language as render_office.py / render_capitol.py
(2:1 iso, near walls sliced at knee height), but like the Capitol it
is the MAIN view: SS = 1, authored at full resolution, displayed
through a `view` rect with continuous zoom + LINEAR filtering — so
every deliberate line here is >= 2px.

Outputs (hand-versioned in JS via HALL_V — bump together):
  site/assets/map/hallway.png
  site/map/hallway.json     (spawn + hotspots + zones, px in scene space)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

import roomplan
import roombands
import roomlight

ROOT = Path(__file__).resolve().parent.parent
OUT_PNG = ROOT / "site" / "assets" / "map" / "hallway.png"
OUT_JSON = ROOT / "site" / "map" / "hallway.json"

W, H = 1500, 1000           # SCENE space — hotspot px and `view` live here

# ---------------------------------------------------------------- OVER/SHIP
# TWO NUMBERS, BECAUSE THEY ARE TWO DECISIONS (2026-08-28). `SS` used to
# be one constant meaning both "how much to oversample for antialiasing"
# and "ship at 1/SS", which is why it could only ever trade one against
# the other — SS 2 bought AA and threw away half the resolution, SS 1
# bought resolution and threw away the AA. The room is magnified ~2.8x
# on a dpr-2 display (see the DPR section in CLAUDE.md), which is the
# regime where BOTH matter, so they are separate now:
#
#   SHIP  file px per SCENE px. The shipped PNG is W*SHIP x H*SHIP and
#         the runtime scales it back down by meta.scale = 1/SHIP, so
#         SCENE coordinates — every hotspot px, every zone, the `view`
#         rect — are completely untouched by it.
#   OVER  supersample on top of that. The room is drawn at SHIP*OVER
#         and LANCZOS-resized down by OVER, so every diagonal is
#         antialiased ONCE by a real filter instead of being
#         point-sampled at display time.
#
# WHY THIS IS NOT JUST "DRAW THE OLD PICTURE BIGGER": the win is
# entirely in what was being quantised to the scene grid. `iso()` now
# rounds to 1/K of a scene pixel (K = SHIP*OVER), so a 2:1 iso diagonal
# — which is very nearly every edge in this room — steps 4x as finely
# and then gets filtered, where before it stepped in whole scene px and
# got magnified. Axis-aligned literals inside the painters land on
# exact K multiples and stay perfectly crisp; curves (the lei, the
# head, the contact shadows, the light pools) resolve at the finer
# grid for free.
#
# The painters were NOT rewritten for this, and could not have been:
# they are written in scene px with hardcoded literals mixed into
# iso() output (`up(p, ht - 5)`, `fx + int(x0 * s)`), so there is no
# seam at which a scale could be applied by hand. `SDraw` below scales
# at the DRAW CALL instead, which is the one place every coordinate,
# literal and computed alike, has already been summed.
SHIP = 2
OVER = 2
K = SHIP * OVER             # scene px -> draw px
CX, CY = 760, 560
SX, SY = 40, 20             # iso px per unit (2:1)
WH = 120                    # full wall height
CUT = 24                    # near-wall slice height (house cutaway rule)
DOOR_H = 88
CUT_CORE = (154, 146, 124)  # same cut-core material as the other rooms

# plan: corridor runs in u; the alcove is a RECESS in the far (NE)
# wall between LU0 and LU1, reaching back to LV.
# IT IS A SINGLE HALLWAY, AND THE WIDTH SAYS SO (2026-08-27, user:
# "make hallway narrower … it's just a single hallway"). At VH 2.1 the
# floor was 4.2 units against ~18 of run — a gallery, not a corridor,
# and the recess at 7 units wide read as a second room opening off it.
# 1.45 puts the walls a door-and-a-half apart, which is what the
# reference photo shows; the recess narrows with it so it stays an
# alcove the legislator stands in, not a lobby.
U0, U1 = -11.0, 7.5
VH = 1.45                   # corridor half-width
LU0, LU1 = -7.6, -2.2
LV = -4.8                   # alcove back wall

# ---- THINGS STANDING ON THE FLOOR, hoisted out of render() because the
# WALKMASK and the PAINTERS must not carry two copies of a position.
# The `_R_PX` numbers are the half-width of each object's own CONTACT
# SHADOW as drawn below — an object's footprint on the floor IS its
# obstacle, so the collision radius follows the art instead of being
# guessed a second time.
PLANTS = ((-7.0, -3.0), (2.9, -1.0))
PLANT_R_PX = 26
FIGURE_AT = (-5.4, -3.1)
FIGURE_R_PX = 19

# ---- THE PLAN FLOOR (see tools/roomplan.py). Declared from the SAME
# constants the painters draw with, so narrowing the corridor or moving
# the alcove moves the walkmask with it; render() asserts the two have
# not come apart. Spawn is the rotunda end of the run — the player
# arrives from the direction the exit hotspot points.
BASIS = roomplan.Basis(CX, CY, SX, SY)
WALK = roomplan.Walk(
    allow=[roomplan.rect(U0, U1, -VH, VH),        # the corridor run
           roomplan.rect(LU0, LU1, LV, -VH)],     # the alcove recess
    block=[roomplan.disc_from_px(BASIS, u, v, PLANT_R_PX)
           for u, v in PLANTS]
          + [roomplan.disc_from_px(BASIS, *FIGURE_AT, FIGURE_R_PX)],
    spawn=(5.5, 0.0),
)

rng = np.random.default_rng(23)

# ---- THE BACKDROP (tools/roomlight.py), in this room's own frame: the
# pool is centred on ROOM_HALLWAY.view and reaches exact INK inside the
# 1500x1000 canvas; the shadow is the floor dropped and pushed the way
# the Capitol's is, so the three rooms sit on one ground.
BACKDROP_C = (690, 466)
BACKDROP_R = (640, 420)
BACKDROP_LIFT = (30, 39, 57)
SHADOW_DROP = 60
SHADOW_SUN = (-0.45, 0.12)
SHADOW_BLUR = 20
SHADOW_A = 0.60


def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


INK = hx("#0a0e18")
WALL = hx("#e6dfcf")        # warm off-white (photo walls)
BASE = hx("#5e4c38")        # dark base trim
FLOOR = hx("#6b3e24")       # glossy red-brown (photo floor)
FLOOR_D = hx("#4e2c19")
KOA = hx("#5c4326")
KOA_D = hx("#48331d")
KOA_L = hx("#75552f")
FRAME = hx("#3b2a19")
PAPER = hx("#e8e2d0")
BLUE = hx("#4a6478")        # the aloha-blue accent (house palette)
STEEL = hx("#a8a296")
GLASS = hx("#2e3a42")
KEY = hx("#f2c14e")
SKIN = hx("#b9895a")
LEI = hx("#567a4c")
LEI_L = hx("#7fa06a")


def snap(v):
    """Round to 1/K of a scene pixel — the draw grid.

    THE POINT OF THE WHOLE EXERCISE IS IN THIS FUNCTION. It used to be
    round(v), and the standing rule (CLAUDE.md) is that geometry is
    pixel-snapped at the source so repeating runs share one grid —
    float coords made picket spacing drift by a pixel and read as
    irregular. That rule is kept, not broken: geometry is still snapped
    to a grid, it is simply the grid the room is actually DRAWN on
    rather than a K-times coarser one. Snapping to whole scene px and
    then multiplying by K would put every diagonal back on a staircase
    K times coarser than the output, which is the opposite of the
    intent."""
    return round(v * K) / K


def iso(u, v, dy=0.0):
    return (snap(CX + SX * (u - v)), snap(CY + SY * (u + v) - dy))


def lerp(p, q, t):
    return (snap(p[0] + (q[0] - p[0]) * t),
            snap(p[1] + (q[1] - p[1]) * t))


def up(p, dy):
    return (p[0], snap(p[1] - dy))


def shade(c, f):
    return tuple(int(max(0, min(255, x * f))) for x in c)


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


class SDraw:
    """ImageDraw, with every coordinate in SCENE px and the canvas K
    times bigger. The painters below hand it scene coordinates and know
    nothing about K.

    Three things have to be got right, and each of them was a visible
    bug before it was:

    - **BOXES ARE INCLUSIVE, so they need the +1 before scaling.** PIL
      fills `rectangle([x0, y0, x1, y1])` over x0..x1 INCLUSIVE, i.e. a
      1-scene-px hairline is written x0 == x1. Scaling the corners
      alone maps that to a 1-DRAW-px hairline — K times thinner
      relative to the image — and every kerb line, plaque edge and
      shadow gap in the room quietly evaporates on the downsample. The
      far corner is mapped as `(x1 + 1) * K - 1`, which takes an
      n-scene-px box to exactly n*K draw px.
    - **`width` IS A DISTANCE and scales with everything else.** A
      `width=1` rule is one SCENE pixel, not one draw pixel.
    - **`point` IS A K x K BLOCK**, for the same reason as boxes: a
      single draw pixel is 1/K of the mark that was authored, and at
      OVER 2 it comes out of the resize at quarter strength.

    Polygons take the corner mapping and NOT the +1: their vertices are
    positions rather than a span, adjacent quads share an edge
    coordinate, and growing each one would make every seam in the room
    overlap by K px instead of 1. The cost is that a filled polygon
    lands up to K-1 draw px short on its far side — a quarter of a
    scene pixel at these settings, measured below against the shipped
    bake and well inside the resample's own footprint."""

    _BOX = ("rectangle", "ellipse", "arc", "chord", "pieslice")
    _SEQ = ("polygon", "line")

    def __init__(self, im):
        self._d = ImageDraw.Draw(im)

    @staticmethod
    def _pts(xy):
        """[(x, y), ...] or a flat [x, y, x, y, ...] — PIL takes both"""
        if xy and isinstance(xy[0], (list, tuple)):
            return [(p[0] * K, p[1] * K) for p in xy]
        return [v * K for v in xy]

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

    @staticmethod
    def _kw(kw):
        if kw.get("width"):
            kw = dict(kw, width=max(1, int(round(kw["width"] * K))))
        return kw


def quad(d, pts, c):
    d.polygon(pts, fill=c)


# ------------------------------------------------------------ floor
def tiles(d, u0, u1, v0, v1, step=1.4):
    """big square floor tiles on a GLOBAL grid, so the corridor and
    the lobby share joints across their seam"""
    for i in range(math.floor(u0 / step), math.ceil(u1 / step)):
        for j in range(math.floor(v0 / step), math.ceil(v1 / step)):
            au, bu = max(u0, i * step), min(u1, (i + 1) * step)
            av, bv = max(v0, j * step), min(v1, (j + 1) * step)
            if au >= bu or av >= bv:
                continue
            f = rng.uniform(0.94, 1.06)
            d.polygon([iso(au, av), iso(bu, av), iso(bu, bv), iso(au, bv)],
                      fill=shade(FLOOR, f))
    # joints — hairlines, not a lattice
    for i in range(math.floor(u0 / step) + 1, math.ceil(u1 / step)):
        gu = i * step
        if u0 < gu < u1:
            d.line([iso(gu, v0), iso(gu, v1)], fill=shade(FLOOR, 0.84),
                   width=1)
    for j in range(math.floor(v0 / step) + 1, math.ceil(v1 / step)):
        gv = j * step
        if v0 < gv < v1:
            d.line([iso(u0, gv), iso(u1, gv)], fill=shade(FLOOR, 0.84),
                   width=1)


# ------------------------------------------------------------ walls
def white_wall(d, e0, e1, ht, f=1.0):
    quad(d, [e0, e1, up(e1, ht), up(e0, ht)], shade(WALL, f))
    ln = math.hypot(e1[0] - e0[0], e1[1] - e0[1])
    n_p = max(2, int(ln // 110))
    for i in range(n_p):
        t0, t1 = i / n_p, (i + 1) / n_p
        a, b = lerp(e0, e1, t0), lerp(e0, e1, t1)
        fpan = f * (0.985 + 0.028 * ((i * 5) % 3) / 2)
        quad(d, [a, b, up(b, ht), up(a, ht)], shade(WALL, fpan))
    d.line([up(e0, ht), up(e1, ht)], fill=shade(WALL, f * 0.78), width=2)
    # dark base trim (photo) — the wall's contact with the shiny floor
    quad(d, [e0, e1, up(e1, 10), up(e0, 10)], shade(BASE, f))
    d.line([up(e0, 10), up(e1, 10)], fill=shade(BASE, f * 1.3), width=1)
    d.line([e0, e1], fill=shade(FLOOR_D, 0.6), width=2)


def cut_wall(d, e0, e1, off, f=0.95):
    """near walls, RPG-sliced: white stub + the cut core on top.

    The core is the stub's run pushed by `off`, and `off` points along
    the run's OUTSIDE at both ends — so at e0, which is the room's
    outermost corner for both near walls (W for the SW run, E for the
    near end), the core used to overshoot the silhouette by |off| and
    hang in the ink as a bare tick. The e0 end is clipped to the
    corner's x, which IS the room's edge there: nothing but ink lies
    beyond it."""
    t0, t1 = up(e0, CUT), up(e1, CUT)
    quad(d, [e0, e1, t1, t0], shade(WALL, f * 0.9))
    d.line([e0, e1], fill=shade(BASE, f), width=3)
    b0 = (t0[0] + off[0], t0[1] + off[1])
    b1 = (t1[0] + off[0], t1[1] + off[1])
    s0 = (t0[0] - b0[0]) / float(b1[0] - b0[0])
    b0 = lerp(b0, b1, s0)
    d.polygon([t0, t1, b1, b0], fill=CUT_CORE)
    d.line([t0, t1], fill=hx("#fff7e6"), width=2)
    d.line([b0, b1], fill=shade(CUT_CORE, 0.72), width=1)


def pilaster(d, p, side, w=9, ht=WH):
    """white casing capping a wall end at the lobby mouth (the photo's
    cased opening). side=-1 hugs the end of the wall to its LEFT,
    side=+1 the wall to its RIGHT — never free-standing over the
    recess floor, which read as a floating plank."""
    x, y = p
    x0, x1 = (x - w, x + 2) if side < 0 else (x - 2, x + w)
    d.rectangle([x0, y - ht - 4, x1, y + 1], fill=shade(WALL, 1.03))
    d.rectangle([x1 - 3, y - ht - 4, x1, y + 1], fill=shade(WALL, 0.84))
    d.line([(x0, y + 1), (x1, y + 1)], fill=shade(FLOOR_D, 0.6), width=2)


# --------------------------------------------------------- features
def koa_door(d, a, b, ht=DOOR_H, notice=False, lei_on_pull=False):
    """koa leaf standing in a dark architrave on a wall base span a->b"""
    fr0, fr1 = lerp(a, b, -0.10), lerp(a, b, 1.10)
    quad(d, [fr0, fr1, up(fr1, ht + 6), up(fr0, ht + 6)], FRAME)
    quad(d, [a, b, up(b, ht), up(a, ht)], KOA)
    for t, f in ((0.2, 0.9), (0.35, 0.95), (0.5, 0.78),
                 (0.65, 0.95), (0.8, 0.9)):
        p = lerp(a, b, t)
        d.line([up(p, 5), up(p, ht - 5)], fill=shade(KOA, f), width=1)
    d.line([up(lerp(a, b, 0.08), int(ht * 0.42)),
            up(lerp(a, b, 0.92), int(ht * 0.42))],
           fill=shade(KOA, 0.8), width=1)
    # top reveal dark, lit lower rail — sky-key shading, house rule
    d.line([up(a, ht - 3), up(b, ht - 3)], fill=KOA_D, width=2)
    quad(d, [lerp(a, b, 0.05), lerp(a, b, 0.95),
             up(lerp(a, b, 0.95), 8), up(lerp(a, b, 0.05), 8)],
         shade(KOA, 0.7))
    pull = lerp(a, b, 0.8)
    d.line([up(pull, int(ht * 0.4)), up(pull, int(ht * 0.52))],
           fill=hx("#c9b88f"), width=2)
    if lei_on_pull:  # Opening Day — lei hung on the doorknob
        px_, py_ = up(pull, int(ht * 0.4))
        d.ellipse([px_ - 4, py_ - 1, px_ + 4, py_ + 11], outline=LEI,
                  width=2)
        d.point([(px_ - 3, py_ + 3), (px_ + 3, py_ + 6)], fill=LEI_L)
    if notice:       # white sheet taped to the upper leaf (photo)
        c = lerp(a, b, 0.5)
        nx, ny = up(c, int(ht * 0.72))
        d.polygon([(nx - 8, ny), (nx + 8, ny - 2),
                   (nx + 9, ny + 20), (nx - 7, ny + 22)], fill=PAPER)
        d.line([(nx - 5, ny + 6), (nx + 5, ny + 5)],
               fill=shade(PAPER, 0.7), width=1)
        d.line([(nx - 5, ny + 11), (nx + 5, ny + 10)],
               fill=shade(PAPER, 0.7), width=1)


def plaque(d, p, w=18, h=12):
    """member nameplate beside a door — dark koa, one gold line"""
    x, y = p
    d.rectangle([x - w // 2, y - h, x + w // 2, y], fill=FRAME)
    d.line([(x - w // 2 + 3, y - h + 3), (x + w // 2 - 3, y - h + 3)],
           fill=KEY, width=1)
    d.line([(x - w // 2 + 3, y - h + 6), (x + w // 2 - 4, y - h + 6)],
           fill=PAPER, width=1)
    d.line([(x - w // 2 + 3, y - h + 9), (x + w // 2 - 6, y - h + 9)],
           fill=shade(PAPER, 0.8), width=1)


def directory(d, a, b, y0=30, y1=66):
    """glazed building directory recessed in the wall (photo, left
    wall): steel frame, dark glass, pale listing lines"""
    f0, f1 = lerp(a, b, -0.06), lerp(a, b, 1.06)
    quad(d, [up(f0, y0 - 3), up(f1, y0 - 3), up(f1, y1 + 3),
             up(f0, y1 + 3)], shade(STEEL, 0.75))
    quad(d, [up(a, y0), up(b, y0), up(b, y1), up(a, y1)], GLASS)
    ln = 5
    for i in range(ln):
        yy = y0 + 7 + i * (y1 - y0 - 12) / ln
        p0 = lerp(a, b, 0.14)
        p1 = lerp(a, b, 0.86 - (0.18 if i % 2 else 0.0))
        d.line([up(p0, yy), up(p1, yy)],
               fill=mix(GLASS, PAPER, 0.55 if i == 0 else 0.35), width=1)
    d.line([up(lerp(a, b, 0.7), y0 + 4), up(lerp(a, b, 0.9), y1 - 6)],
           fill=mix(GLASS, PAPER, 0.25), width=2)


def art_frame(d, p, w=15, h=20):
    """small framed print on the blank stretch of wall"""
    x, y = p
    d.rectangle([x - w // 2 - 2, y - h - 2, x + w // 2 + 2, y], fill=FRAME)
    d.rectangle([x - w // 2, y - h, x + w // 2, y - 2],
                fill=mix(BLUE, PAPER, 0.45))
    d.line([(x - w // 2 + 2, y - 8), (x + w // 2 - 2, y - 12)],
           fill=mix(BLUE, PAPER, 0.2), width=2)


def plant(d, u, v, s=1.7):
    """potted palm, office plant scaled up for the closer camera"""
    x, y = iso(u, v)
    d.polygon([(x - int(8 * s), y - int(10 * s)),
               (x + int(8 * s), y - int(10 * s)),
               (x + int(6 * s), y), (x - int(6 * s), y)],
              fill=hx("#8c5535"))
    d.rectangle([x - int(9 * s), y - int(13 * s), x + int(9 * s),
                 y - int(10 * s)], fill=hx("#c08050"))
    d.line([(x - int(6 * s), y), (x + int(6 * s), y)],
           fill=shade(FLOOR_D, 0.8), width=2)
    for fx, fy, c in ((-8, -30, "#3f5f3a"), (-4, -36, "#567a4c"),
                      (0, -39, "#6f9660"), (4, -36, "#567a4c"),
                      (8, -29, "#3f5f3a"), (-11, -22, "#567a4c"),
                      (11, -23, "#6f9660"), (-2, -33, "#3f5f3a")):
        top = (x + int(fx * s), y - int(13 * s) + int(fy * s))
        bow = (x + int(fx * s) // 2, y - int(13 * s) + int(fy * s) // 2 - 4)
        d.line([(x, y - int(13 * s)), bow], fill=hx(c), width=2)
        d.line([bow, top], fill=hx(c), width=2)


def figure(d, u, v, s=1.15):
    """the introducer — aloha shirt, slacks, Opening-Day lei. Faceless
    at this scale, per the house rule; the lei and the folder are what
    say 'member on Opening Day'. Rebuilt 2026-08-28 for elegance: every
    limb is a LOFTED taper through measured stations (the same
    straight-segment-between-stations convention the building's own
    columns use, COL_FLARE = 1.0 — never a curve fit), and the whole
    figure is split lit/shadow down the midline for the room's one
    hard key light, the same treatment the walls and doors already
    carry. Returns the feet px."""
    fx, fy = iso(u, v)

    def P(x, y):
        return (fx + x * s, fy + y * s)

    def loft(stations, fill):
        """A tapered silhouette through (cx, y, hw) stations, proximal
        to distal (top to bottom). Used for anything that isn't round:
        legs, sleeves, forearms."""
        outer = [P(cx - hw, y) for cx, y, hw in stations]
        inner = [P(cx + hw, y) for cx, y, hw in stations]
        d.polygon(outer + inner[::-1], fill=fill)

    def half(stations, side, fill):
        """One symmetric half (side=-1 left / +1 right) of a centred,
        tapered silhouette — split down the midline for the key-light
        shading. `stations` are (y, hw) since cx is always 0."""
        near = [P(0, y) for y, hw in stations]
        far = [P(side * hw, y) for y, hw in reversed(stations)]
        d.polygon(near + far, fill=fill)

    SHIRT, SHIRT_SH = BLUE, shade(BLUE, 0.84)
    SKIN_SH = shade(SKIN, 0.86)
    SLACKS, SLACKS_SH = hx("#2e2c30"), shade(hx("#2e2c30"), 0.88)
    SHOE, SHOE_SH = hx("#1c1a18"), shade(hx("#1c1a18"), 0.75)

    # ---- legs: hip -> knee -> ankle, LEFT lit / RIGHT in shadow. The
    # right ankle turns out a couple of units more than the left —
    # the relaxed contrapposto that keeps the stance from reading as
    # a mannequin standing at attention.
    loft([(-5.0, -37, 4.3), (-5.0, -20, 3.6), (-5.3, -6, 2.6)], SLACKS)
    loft([(5.0, -37, 4.3), (5.5, -20, 3.6), (6.3, -6, 2.7)], SLACKS_SH)

    # ---- shoes: a pointed toe turned outward, sole wider than the
    # ankle opening — not the flat rectangular block this used to be.
    def shoe(cx, hw, out, fill, hi):
        heel_o, heel_i = P(cx - hw, -6), P(cx + hw, -6)
        sole_o, sole_i = P(cx - hw - 1.3, -1), P(cx + hw + 0.6, -1)
        toe = P(cx + out * 3.4, 1.6)
        d.polygon([heel_o, sole_o, toe, sole_i, heel_i], fill=fill)
        d.line([P(cx - hw - 0.6, -4.5), P(cx + out * 1.6, -0.6)],
               fill=hi, width=1)

    shoe(-5.3, 2.6, -1, SHOE, mix(SHOE, WALL, 0.3))
    shoe(6.3, 2.7, 1, SHOE_SH, mix(SHOE_SH, WALL, 0.2))

    # ---- torso: shoulder -> chest -> waist -> hem, an hourglass that
    # flares back open at the hem the way a loose aloha shirt drops —
    # not the straight-sided box this used to be.
    TORSO = [(-62, 8.6), (-52, 7.6), (-46, 6.4), (-37, 8.0)]
    half(TORSO, -1, SHIRT)
    half(TORSO, 1, SHIRT_SH)
    # a couple of buttons open at the collar: a shadowed V of folded
    # fabric with a sliver of skin nested inside it — not a face, but
    # enough to read as a shirt actually being worn
    d.polygon([P(-3.2, -62), P(3.2, -62), P(0, -54)], fill=shade(SHIRT_SH, 0.72))
    d.polygon([P(-1.8, -61), P(1.8, -61), P(0, -57)], fill=SKIN)

    # ---- pattern: sparse specks, tinted toward whichever shirt half
    # they land on so the print reads through the two-tone shading
    # instead of sitting on top of it as a flat overlay
    for dx, dy in ((-6, -42), (2, -46), (7, -40), (-3, -54),
                   (5, -57), (-8, -51), (4, -49), (-4, -37)):
        base = SHIRT if dx < 0 else SHIRT_SH
        px_, py_ = P(dx, dy)
        d.point([(px_, py_), (px_ + 1, py_)], fill=mix(base, PAPER, 0.4))

    # ---- sleeves, short and capped at the bicep, then bare forearms.
    # The left arm hangs at a slight relaxed angle; the right bends in
    # across the chest to carry the folder — the one asymmetry that
    # keeps the pose from reading as a mannequin's.
    loft([(-11.0, -62, 3.6), (-11.6, -53, 2.9)], SHIRT)
    loft([(11.0, -62, 3.6), (11.6, -53, 2.9)], SHIRT_SH)
    loft([(-11.6, -53, 2.6), (-13.4, -34, 2.0)], SKIN)
    loft([(11.6, -53, 2.6), (6.4, -41, 2.1)], SKIN_SH)
    d.ellipse([*P(-15.5, -36.1), *P(-11.3, -31.9)], fill=SKIN)
    d.ellipse([*P(4.4, -43.0), *P(8.4, -39.0)], fill=SKIN_SH)

    # ---- folder, tucked under the bent forearm — a fold line and a
    # lit leading edge so it reads as paper rather than a flat card,
    # plus the sliver of shadow it drops onto the shirt beneath it
    d.polygon([P(3, -37), P(17, -35), P(16, -33), P(3, -34)],
              fill=shade(SHIRT_SH, 0.78))
    d.polygon([P(4, -38), P(4, -46), P(19, -43), P(18, -36)], fill=PAPER)
    d.line([P(5, -39), P(17, -42)], fill=mix(PAPER, SHIRT_SH, 0.25), width=1)

    # ---- lei — draped fuller across the collarbone, alternating
    # blossom tones so it reads as flowers rather than a rope of dots
    d.arc([*P(-9.5, -66), *P(9.5, -42)], 12, 168,
          fill=mix(LEI, LEI_L, 0.3), width=4)
    for i, t in enumerate((28, 55, 82, 98, 125, 152)):
        ax, ay = P(9.2 * math.cos(math.radians(t)),
                   -53 + 10.5 * math.sin(math.radians(t)))
        col = LEI_L if i % 2 else mix(LEI, LEI_L, 0.55)
        d.ellipse([ax - 1.1, ay - 1.1, ax + 1.1, ay + 1.1], fill=col)

    # ---- neck, then the head — the neck keeps the same lofted-taper
    # shading as the rest of the body; the head is genuinely round, so
    # it is split with a pair of 180-degree chords instead, the one
    # shape a straight-sided taper cannot fake.
    half([(-68, 2.6), (-62, 2.9)], -1, SKIN)
    half([(-68, 2.6), (-62, 2.9)], 1, SKIN_SH)
    HEAD = [*P(-5.3, -84), *P(5.3, -68)]
    d.chord(HEAD, 90, 270, fill=SKIN)
    d.chord(HEAD, 270, 450, fill=SKIN_SH)
    HAIR = hx("#2a221c")
    d.chord([*P(-5.4, -85), *P(5.4, -71)], 180, 360, fill=HAIR)
    d.line([P(-1.5, -84.5), P(-3.5, -78)], fill=mix(HAIR, SKIN, 0.2), width=1)

    return fx, fy


# ------------------------------------------------------------- main
def render(layers=True, walk_png=False):
    """Bake the room. With `layers=True` the SAME painters draw onto
    three depth targets instead of one canvas — the diorama-parallax
    spike (2026-08-27). The split is by depth band, not by painter
    convenience:
      BACK  the floor, the far walls and everything ON them, plus the
            gloss/reflection overlay that belongs to the floor
      MID   what STANDS on the floor — plants, the legislator — and
            the casing posts at the alcove mouth
      FRONT the sliced near walls, the dollhouse cut itself
    Every layer is drawn COMPLETE on its own transparent canvas, which
    is the whole reason this can work: offsetting a near layer uncovers
    a far layer that was painted as if nothing ever occluded it, so no
    holes open up. Compositing them back in order must reproduce the
    flat bake — render() asserts that so the split cannot silently
    drift from the shipped room."""
    DW, DH = W * K, H * K              # draw space; SCENE space is W, H
    # THE SAME GROUND AS THE CAPITOL (tools/roomlight.py, 2026-09-23): a
    # lit pool behind the corridor and the floor's shadow falling into
    # it. On flat ink this room read as a different game beside the one
    # the player walks into next. The footprint is the floor itself —
    # the corridor and the alcove — dropped SHADOW_DROP under it.
    img = roomlight.backdrop(
        W, H, SHIP, K, INK, BACKDROP_LIFT, BACKDROP_C, BACKDROP_R,
        polys=[[iso(u0, v0, -SHADOW_DROP), iso(u1, v0, -SHADOW_DROP),
                iso(u1, v1, -SHADOW_DROP), iso(u0, v1, -SHADOW_DROP)]
               for u0, u1, v0, v1 in ((U0, U1, -VH, VH),
                                      (LU0, LU1, LV, -VH))],
        sun=(SHADOW_SUN[0] * SHADOW_DROP, SHADOW_SUN[1] * SHADOW_DROP),
        blur=SHADOW_BLUR, alpha=SHADOW_A)
    # ---- DEPTH BANDS (tools/roombands.py). Declaration order IS
    # composite order, and must stay in DEPTH order for the things the
    # character can walk both ways around: the two pots, the two casing
    # posts at the alcove mouth, and the legislator. Everything else is
    # the floor and the far walls (always behind) or the sliced near
    # walls (always in front).
    POT0, POT1 = [u + v for u, v in PLANTS]
    FIG_D = FIGURE_AT[0] + FIGURE_AT[1]
    POST0, POST1 = LU0 + -VH, LU1 + -VH
    ground = img.copy()
    bands = roombands.Bands((DW, DH), img, layers)
    bands.add("back", roombands.BACK)
    bands.add("pot0", POT0)
    bands.add("post0", POST0)
    bands.add("figure", FIG_D)
    bands.add("post1", POST1)
    bands.add("pot1", POT1)
    bands.add("front", roombands.FRONT)
    tb, tf = bands["back"], bands["front"]
    d = SDraw(tb)

    # ---- floor: corridor + lobby recess, one shared tile grid
    tiles(d, U0, U1, -VH, VH)
    tiles(d, LU0, LU1, LV, -VH)

    # ---- far walls, painted back-to-front: the lobby's back wall is
    # the deepest surface in the room, then its lit side reveal, then
    # the corridor walls the recess interrupts
    white_wall(d, iso(LU0, LV), iso(LU1, LV), WH, 0.84)      # lobby back
    white_wall(d, iso(LU0, -VH), iso(LU0, LV), WH, 0.98)     # lobby reveal
    white_wall(d, iso(U0, -VH), iso(LU0, -VH), WH, 0.9)      # NE, far seg
    white_wall(d, iso(LU1, -VH), iso(U1, -VH), WH, 0.9)      # NE, near seg
    white_wall(d, iso(U0, VH), iso(U0, -VH), WH, 1.0)        # corridor end

    # ---- features on the walls
    # far end: the caucus-room door, notice taped to it (photo).
    # OFF-CENTRE BY 0.3 ON PURPOSE (2026-08-28): the room's `view` rect
    # tightened to fill the frame, and dead-centre on the end wall put
    # this door's tap zone 7px outside it — visible but unclickable.
    # The wall gives ±0.75 of play before the leaf meets its own
    # corner, so a third of that buys the margin and still reads as
    # the door terminating the corridor.
    koa_door(d, iso(U0, 0.4), iso(U0, -1.0), notice=True)
    # NE far segment: the introducer's office door + nameplate + lei.
    # It sits on the CORRIDOR wall, not in the alcove: at the narrowed
    # width the alcove holds one person, and a door behind them put two
    # tap zones on top of each other (the disjoint-zone assert caught
    # it). The alcove is where the legislator stands; the door they
    # work behind is a few paces up the hall.
    koa_door(d, iso(-9.9, -VH), iso(-8.5, -VH), lei_on_pull=True)
    plaque(d, up(iso(-8.2, -VH), 46))
    # small framed print on the alcove's back wall
    art_frame(d, up(iso(-4.9, LV), 46))
    # NE near segment: glazed building directory + an unnamed door
    directory(d, iso(0.4, -VH), iso(1.8, -VH))
    koa_door(d, iso(4.0, -VH), iso(5.4, -VH))

    # ---- reflections + light pools: ONE overlay on the glossy floor.
    # The gloss is the photo's signature — doors, plants and the
    # legislator all smear toward the camera at low alpha.
    lay = Image.new("RGBA", (DW, DH), (0, 0, 0, 0))
    dl = SDraw(lay)

    def refl(a, b, direction, ln, col, alpha):
        ox, oy = (SX * ln, SY * ln) if direction == "u" else (-SX * ln,
                                                              SY * ln)
        dl.polygon([a, b, (b[0] + ox, b[1] + oy), (a[0] + ox, a[1] + oy)],
                   fill=col + (alpha,))

    refl(iso(U0, 0.5), iso(U0, -1.1), "u", 2.0, KOA_D, 40)
    refl(iso(U0, 0.5), iso(U0, -1.1), "u", 3.2, KOA_D, 16)
    refl(iso(-9.9, -VH), iso(-8.5, -VH), "v", 1.6, KOA_D, 32)
    refl(iso(4.0, -VH), iso(5.4, -VH), "v", 1.5, KOA_D, 28)
    refl(iso(0.4, -VH), iso(1.8, -VH), "v", 1.1, GLASS, 24)
    # overhead-light streaks running down the corridor (photo ceiling)
    for pu, pv, rw, al in ((-8.6, 0.2, 64, 18), (-4.6, 0.2, 70, 20),
                           (-0.4, 0.2, 64, 18), (3.6, 0.2, 62, 16),
                           # the alcove's pool sits left of the casing
                           # post: at -4.4 its right half fell on the
                           # near NE wall's face, not the floor
                           (-5.6, -3.6, 56, 14)):
        x, y = iso(pu, pv)
        for rr, aa in ((rw, al // 2), (rw * 0.6, al)):
            dl.ellipse([x - rr, y - rr * 0.22, x + rr, y + rr * 0.22],
                       fill=(255, 236, 200, aa))
    # ---- CONTACT SHADOWS BELONG TO THE OBJECT, NOT THE FLOOR.
    # Parked on the floor (where they started) the legislator lifts
    # clean off her own shadow the moment the bands separate —
    # measured on the parallax spike, visible at 6px and unmistakable
    # by 14. In FLAT mode they are still drawn straight into the gloss
    # overlay, exactly as before: ImageDraw fills REPLACE pixels rather
    # than blending, so routing them through a second composite is not
    # the same picture and moved the shipped bake by a few units.
    shadows = {}

    def sd(name):
        """A shadow belongs to its OBJECT, not to the floor: parked on
        the floor band the object lifts clean off it the moment the
        character walks between them. In FLAT mode they still go
        straight into the gloss overlay exactly as before — ImageDraw
        fills REPLACE pixels rather than blending, so routing them
        through a second composite is not the same picture."""
        if not bands.on:
            return dl
        shadows[name] = Image.new("RGBA", (DW, DH), (0, 0, 0, 0))
        return SDraw(shadows[name])

    for pi, (pu, pv) in enumerate(PLANTS):
        ds = sd("pot%d" % pi)
        x, y = iso(pu, pv)
        ds.ellipse([x - PLANT_R_PX, y - 9, x + PLANT_R_PX, y + 9],
                   fill=tuple(shade(FLOOR_D, 0.7)) + (70,))
        ds.ellipse([x - 14, y + 4, x + 14, y + 28],
                   fill=hx("#2c3d28") + (26,))
    ds = sd("figure")
    fxp, fyp = iso(*FIGURE_AT)
    ds.ellipse([fxp - FIGURE_R_PX, fyp - 8, fxp + FIGURE_R_PX,
                fyp + 8],
               fill=tuple(shade(FLOOR_D, 0.7)) + (70,))
    ds.polygon([(fxp - 10, fyp + 4), (fxp + 10, fyp + 4),
                (fxp + 7, fyp + 28), (fxp - 7, fyp + 28)],
               fill=BLUE + (26,))
    tb.alpha_composite(lay)
    for nm, im in shadows.items():
        bands[nm].alpha_composite(im)
    d = SDraw(tb)

    # ---- things standing on the floor, EACH IN ITS OWN BAND at its
    # own plan depth, because the character can walk round any of them
    plant(SDraw(bands["pot0"]), *PLANTS[0])
    ffx, ffy = figure(SDraw(bands["figure"]), *FIGURE_AT)
    # the second pot stands in the CORRIDOR, between the directory and
    # the unnamed door. It stood deep in the alcove at (-3.0, -4.0),
    # chosen so the casing post would not slice it — but every screen
    # px of alcove floor right of that post is BEHIND the near NE
    # wall segment (u+v -7 against the wall's -3.65), and the pot was
    # painted in the mid band over that wall's face, its floor shadow
    # landing on the plaster as a pale disc. The alcove's whole visible
    # floor is the legislator's; the plant goes where a plant can be.
    plant(SDraw(bands["pot1"]), *PLANTS[1])

    # white casing posts at the lobby mouth (photo's cased opening) —
    # they also seat the wall seams where the recess interrupts the run.
    # THEIR OWN BANDS: the character passes in FRONT of a post from the
    # corridor and BEHIND it from inside the alcove, so a post parked in
    # the back band is one the player can never walk behind. (They sat
    # in BACK for the parallax spike, where the rule was that a post
    # capping a wall end must not drift off it — nothing drifts when
    # the bands are static.)
    pilaster(SDraw(bands["post0"]), iso(LU0, -VH), -1)
    pilaster(SDraw(bands["post1"]), iso(LU1, -VH), +1)

    # ---- near walls, sliced (far-to-near) -> FRONT
    d = SDraw(tf)
    cut_wall(d, iso(U0, VH), iso(U1, VH), (-18, -10))        # SW run
    cut_wall(d, iso(U1, -VH), iso(U1, VH), (18, -10))        # near end

    # ---- THE SHIPPED PICTURE IS THE BANDS, COMPOSITED. Nothing is
    # painted twice and there is no second code path that can rot: the
    # flat bake is literally what the layered room adds up to, and it
    # is checked against the PNG already on disk before that PNG is
    # replaced. A band moved past something it OVERLAPS shows up here
    # as a nonzero pixel count, which is the whole point of the gate.
    flat = img.copy()
    for _, _, L in bands.order:
        flat.alpha_composite(L)
    # Both sides of the compare have to be at SHIP size: `flat` is
    # still in DRAW space and the bake on disk is not.
    flat = flat.convert("RGB").resize((W * SHIP, H * SHIP), Image.LANCZOS)
    if bands.on and OUT_PNG.exists():
        ref = np.asarray(Image.open(OUT_PNG).convert("RGB"), np.int16)
        cur = np.asarray(flat, np.int16)
        if ref.shape == cur.shape:
            dd = np.abs(ref - cur).max(axis=-1)
            n = int((dd > 0).sum())
            print(f"bands recomposite vs shipped bake: {n} px differ "
                  f"(max {int(dd.max())})")
            if n:
                ys, xs = np.where(dd > 0)
                print(f"  diff bbox scene px "
                      f"({int(xs.min()) // SHIP}, {int(ys.min()) // SHIP})"
                      f"-({int(xs.max()) // SHIP}, {int(ys.max()) // SHIP})"
                      f"  |  {int((dd > 8).sum())} px over the "
                      f"alpha-arithmetic floor of 8")
            # A TOLERANCE OF 8, AND IT IS NOT SLOP. Painters fill with
            # ImageDraw, which REPLACES pixels rather than blending, so
            # in the flat bake a translucent contact shadow drawn over
            # a translucent floor reflection overwrites it — while in
            # band mode the two live on different layers and get
            # alpha-composited, which blends. That is a real arithmetic
            # difference of a few units wherever those two overlap, and
            # nothing else in the room can produce one: a band actually
            # moved past something it occludes swaps OPAQUE pixels and
            # lands in the hundreds. So the gate is on the MAGNITUDE.
            if int((dd > 8).sum()):
                raise AssertionError(
                    f"the banded render is not the shipped picture "
                    f"({int((dd > 8).sum())} px differ by more than 8, "
                    f"max {int(dd.max())}) — a band was declared out of "
                    f"draw order past something it overlaps")
    img = flat

    # DOWN BY `OVER`, NOT TO SCENE SIZE — that difference is the whole
    # OVER/SHIP split. The AA is baked here, once, by a real filter;
    # the resolution SHIP bought is kept.
    img.save(OUT_PNG)
    # the ground (the backdrop) rides in the back band now, as the
    # Capitol's does — without `base` the lit pool would never ship
    band_meta = bands.emit(OUT_PNG.parent, "hallway", SHIP, OVER,
                           base=ground) if bands.on else []
    bg = "#%02x%02x%02x" % img.getpixel((2, img.height // 2))

    # content bbox against the ink — the JS `view` rect is measured
    # from this (plus breathing margin); re-print on every re-bake
    # A TOLERANCE, NOT AN EXACT COMPARE, now that the bake is resampled:
    # LANCZOS rings slightly into the ink around every content edge, so
    # `!= INK` would call a few hundred px of ripple "content" and creep
    # the bbox outward on every re-bake. 6/255 is under the ring and far
    # under any drawn value. Divided back into SCENE px, because the
    # `view` rect this feeds is scene-space.
    # MEASURED FROM THE BANDS since the backdrop (2026-09-23): the lit
    # pool is not ink, so the old "differs from INK" test called the
    # whole pool content. The room is what the bands carry.
    if bands.on:
        union = Image.new("L", (DW, DH), 0)
        for _, _, L in bands.order:
            union = ImageChops.lighter(union, L.getchannel("A"))
        x0_, y0_, x1_, y1_ = union.getbbox()
        bbox = (x0_ // K, y0_ // K, x1_ // K, y1_ // K)
    else:
        bbox = (0, 0, W, H)

    def zone(cx, cy, w, h):
        return [int(round(cx)), int(round(cy)), int(w), int(h)]

    caucus_c = iso(U0, -0.3)
    office_c = iso(-9.2, -VH)
    dirx_c = iso(1.1, -VH)
    # iso() carries 1/K precision now; the JSON is SCENE space and
    # integer, so round at this boundary and nowhere else.
    def sp(v):
        return int(round(v))

    # WHERE THE PLAYER STANDS TO USE EACH HOTSPOT, from the same screen
    # point that placed it: a door's own point is ON the wall and the
    # legislator's is inside their own footprint, so roomplan.approach()
    # spirals out to the nearest floor. A hotspot with an `at` is walked
    # to before it acts; one without acts on the tap.
    def at(px_, py_):
        a = roomplan.approach(WALK, *BASIS.plan(px_, py_))
        assert a, f"no standable floor near ({px_:.0f}, {py_:.0f})"
        return list(a)

    hotspots = [
        # `mark` — where the runtime hangs this hotspot's marker, just
        # over the thing it marks (2026-09-23): the legislator's head,
        # a door's frame (94 px: koa_door's architrave), the
        # directory's frame (69). It used to hang at a fixed offset from
        # py, which put pins on the leaves of the doors.
        dict(id="legislator", name="Your Introducer", kind="door",
             px=sp(ffx), py=sp(ffy - 60), mark=[sp(ffx), sp(ffy - 98)],
             zone=zone(ffx, ffy - 44, 66, 100), at=at(ffx, ffy),
             text="Rep. Christina Silva — the member who agreed to carry your "
                  "bills, waiting off to the side between the morning "
                  "caucus and the first floor session. Opening Day is "
                  "the one morning everyone is reachable."),
        dict(id="caucus", name="Caucus Room", kind="poi",
             px=sp(caucus_c[0]), py=sp(caucus_c[1] - 40),
             mark=[sp(caucus_c[0]), sp(caucus_c[1] - 98)],
             zone=zone(caucus_c[0], caucus_c[1] - 50, 92, 108),
             at=at(*caucus_c),
             text="Koa doors and a taped agenda: the majority caucus "
                  "met behind them before the session even opened. "
                  "The floor ratifies; rooms like this decide."),
        dict(id="office", name="Member's Office", kind="poi",
             px=sp(office_c[0]), py=sp(office_c[1] - 40),
             mark=[sp(office_c[0]), sp(office_c[1] - 98)],
             zone=zone(office_c[0], office_c[1] - 50, 88, 106),
             at=at(*office_c),
             text="Your introducer's office — nameplate polished, a "
                  "lei on the door pull. Every member gets one door "
                  "on these hallways; what they carry through it is "
                  "what gets a number and a hearing."),
        dict(id="directory", name="Directory", kind="poi",
             px=sp(dirx_c[0]), py=sp(dirx_c[1] - 36),
             mark=[sp(dirx_c[0]), sp(dirx_c[1] - 73)],
             zone=zone(dirx_c[0], dirx_c[1] - 50, 80, 58),
             at=at(*dirx_c),
             text="The building directory behind glass. Committee "
                  "rooms below, member offices along these wings — "
                  "the Capitol is small enough to walk and big "
                  "enough to get lost in."),
        dict(id="exit", name="To the rotunda", kind="exit",
             px=sp(iso(6.2, 0)[0]), py=sp(iso(6.2, 0)[1] + 6),
             text=""),
    ]
    # zones must be disjoint — same assert the capitol bake earns
    zs = [h["zone"] for h in hotspots if "zone" in h]
    for i in range(len(zs)):
        for j in range(i + 1, len(zs)):
            a_, b_ = zs[i], zs[j]
            if (abs(a_[0] - b_[0]) * 2 < a_[2] + b_[2] and
                    abs(a_[1] - b_[1]) * 2 < a_[3] + b_[3]):
                raise AssertionError(f"zones overlap: {a_} vs {b_}")

    # EVERY HOTSPOT MUST FIT THE ROOM'S `view` RECT. The rect lives in
    # main.js (ROOM_HALLWAY.view) but the consequence is baked here: a
    # zone outside it is a door the player can see and cannot press.
    # Keep the two in step — this asserts the pairing rather than
    # trusting it, the same way the zone-overlap check does.
    VIEW = (281, 206, 1099, 725)
    for h in hotspots:
        z = h.get("zone")
        if not z:
            continue
        if not (z[0] - z[2] / 2 >= VIEW[0] and z[1] - z[3] / 2 >= VIEW[1]
                and z[0] + z[2] / 2 <= VIEW[2]
                and z[1] + z[3] / 2 <= VIEW[3]):
            raise AssertionError(
                f"hotspot {h['id']} zone {z} falls outside view {VIEW}")

    meta = {
        "name": "House Wing — Opening Day",
        "image": "hallway.png",
        # w/h stay SCENE size and `scale` is scene px per FILE px, so
        # everything downstream — hotspot px, zones, the view rect —
        # is unchanged by SHIP. The runtime multiplies the sprite by
        # this to put the file back into scene space.
        "w": W, "h": H, "scale": 1 / SHIP, "bg": bg,
        # LEGACY, screen px, and superseded by walk.spawn below — which
        # is in PLAN units, the space a moving character lives in.
        "spawn": [sp(iso(6, 0)[0]), sp(iso(6, 0)[1])],
        # THE PROJECTION AND THE FLOOR (tools/roomplan.py). The basis is
        # this room's own iso() — 40x20 px per unit here against the
        # Capitol's 16x8, which is exactly why it ships per room rather
        # than living as a constant in main.js.
        "basis": BASIS.json(),
        "walk": WALK.json(),
        # DEPTH BANDS. The runtime draws these instead of `image` when
        # present, each at its own depth, and puts the character
        # between them by its plan u+v. `image` stays as the flat
        # reference and the fallback.
        "bands": band_meta,
        "hotspots": hotspots,
    }
    # The floor must still match the room the painters just drew.
    roomplan.check("hallway", BASIS, WALK, iso, view=VIEW,
                   targets=[(h["id"], *h["at"]) for h in hotspots
                            if "at" in h])
    OUT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print("wrote", OUT_PNG.name, f"{img.width}x{img.height}",
          "and", OUT_JSON.name)
    print("content bbox:", bbox,
          "-> suggested view:",
          [bbox[0] - 24, bbox[1] - 24, bbox[2] + 24, bbox[3] + 24])
    if walk_png:
        roomplan.debug_png(img, BASIS, WALK,
                           ROOT / "build" / "debug_walk_hallway.png",
                           ship=SHIP, view=VIEW)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", action="store_true",
                    help="render the old single-canvas way, with every "
                         "band pointing at one image — the escape hatch "
                         "for checking that the split changed nothing")
    ap.add_argument("--walk", action="store_true",
                    help="also write build/debug_walk_hallway.png — the "
                         "walkmask drawn over the bake")
    a = ap.parse_args()
    render(layers=not a.flat, walk_png=a.walk)
