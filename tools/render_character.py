#!/usr/bin/env python3
"""THE PLAYER CHARACTER — the Advocate — as a walk-cycle spritesheet.

  site/assets/map/char_advocate.png   8 facings x (idle + 6 walk frames)
  site/map/character.json             frame size, anchor, authored scale

WHY THIS IS NOT render_hallway.py's `figure()` GROWN A FEW FRAMES.
`figure()` is a BILLBOARD: it is drawn in flat body coordinates, `P(x,
y)` straight to screen, and it only ever has to look right from one
angle standing still. That is the correct model for a character in an
iso room and it stays the model here — what changes is that a walking
character has EIGHT facings, and a billboard cannot be turned. So the
body is defined in real 3D and projected:

    bx  across the body (+ = the character's left)
    by  forward, the way they are facing
    bz  up

rotated by the facing angle in PLAN and pushed through the room's own
iso. That is the same argument `swing_sheet` makes for the door leaf —
rebuild in plan, project with the room's axes; rotating a flat sprite
on screen is a different motion and reads as a card spinning — and it
buys three things that would each otherwise be hand-drawn eight times:
shoulders foreshorten as the body turns, the forward leg in profile
separates fore-and-aft instead of side-to-side, and the KEY LIGHT
stays put in the world while the character turns inside it.

UNITS ARE METRES. Plan units are ~1 m in both rooms (the hallway is 2.9
units wall to wall, the Capitol's balcony 2.5 deep), so the skeleton
below is a real 1.75 m person and every station reads as an anatomy
measurement rather than a pixel count.

ONE BAKE, SCALED PER ROOM. It is authored at CHAR_SX — the hallway's
40 px per plan unit — and the runtime scales it by `room.basis.sx /
char.sx`, which is 0.4 in the Capitol. The alternative, a sheet per
room, would be two sources for one character.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_PNG = ROOT / "site" / "assets" / "map" / "char_advocate.png"
OUT_JSON = ROOT / "site" / "map" / "character.json"

# ---- resolution. Same two-decisions split as the rooms (2026-08-28):
# SHIP is file px per scene px, OVER is the antialiasing oversample
# that is LANCZOS'd away at the end. Never one constant meaning both.
SHIP = 2
OVER = 2
K = SHIP * OVER

CHAR_SX = 40.0             # authored plan scale — the hallway's
CHAR_SY = CHAR_SX / 2      # 2:1, always
# HEIGHT EXAGGERATION. Measured off the hallway's own figure: its head
# tops out ~97 scene px for a 1.75 m person, i.e. ~55 px/m against the
# floor's 40 px/unit. The room's architecture carries the same lie
# (bench_at notes "~2.8x against plan"), so a character drawn to true
# iso height would look squat beside it.
ZS = 55.0

WALK_N = 6                 # frames in the cycle; idle is frame 0
DIRS = ("S", "SE", "E", "NE", "N", "NW", "W", "SW")

# THE KEY LIGHT, as a PLAN direction. The rooms light from screen
# upper-left — `figure()` puts its lit half on the left and its shadow
# on the right — and screen-left is plan (-1, +1). Keeping the light in
# the world rather than on the body is the whole reason a turned
# character still reads as lit: face away from it and you see the
# shadow side, which is what makes N and S different drawings.
LIGHT = (-1.0 / math.sqrt(2), 1.0 / math.sqrt(2))


def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def shade(c, f):
    return tuple(int(max(0, min(255, x * f))) for x in c)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---- palette. The Advocate is NOT the legislator: no aloha print, no
# lei — those say "member on Opening Day" and belong to the introducer.
# This is someone who works the building from outside it, so: a plain
# shirt, dark slacks, and the one prop that carries the identity, a
# canvas SHOULDER BAG. Faceless, per the house rule.
SKIN = hx("#c69a6d")
SHIRT = hx("#8d5a4a")      # muted brick — distinct from the
                           # introducer's aloha blue at a glance
SLACKS = hx("#2e2c30")
SHOE = hx("#1c1a18")
HAIR = hx("#2a221c")
BAG = hx("#6b6455")
BAG_L = hx("#8a8270")
LIT, SHA = 1.0, 0.84       # the room's own two-tone split


# ------------------------------------------------------- the skeleton
# Every station is (bx, by, bz) in METRES on a 1.75 m body. Heights are
# anatomical: ankle 0.08, knee 0.50, hip 0.95, shoulder 1.42, crown
# 1.75. Widths are half-widths, also metres.
HIP_Z, KNEE_Z, ANKLE_Z = 0.95, 0.50, 0.08
SHO_Z, ELB_Z, WRI_Z = 1.42, 1.13, 0.86
HIP_X, SHO_X = 0.085, 0.165
NECK_Z, CROWN_Z = 1.50, 1.75

THIGH = HIP_Z - KNEE_Z
SHIN = KNEE_Z - ANKLE_Z
UPPER = SHO_Z - ELB_Z
FORE = ELB_Z - WRI_Z

SWING = math.radians(26)   # thigh amplitude
ARM_SWING = math.radians(18)
KNEE_FLEX = math.radians(42)


def gait(phase, side):
    """Joint positions for one leg and one arm at cycle `phase`, for
    side -1 (character's right) / +1 (left).

    A pendulum model, not IK: the thigh swings about the hip, the knee
    flexes only while the leg is SWINGING THROUGH (a straight leg on
    the back half is what makes cheap walk cycles read as a puppet
    scissoring), and the arm opposes the leg on the same side. The
    body bobs twice per cycle, at the two passing positions.
    """
    t = 2 * math.pi * (phase + (0.5 if side > 0 else 0.0))
    th = SWING * math.cos(t)
    # flex on the swing-through half only, eased so it peaks mid-swing
    flex = KNEE_FLEX * max(0.0, math.sin(t)) ** 1.3
    knee = (side * HIP_X, THIGH * math.sin(th), HIP_Z - THIGH * math.cos(th))
    kth = th - flex
    ankle = (side * HIP_X,
             knee[1] + SHIN * math.sin(kth),
             knee[2] - SHIN * math.cos(kth))
    ath = -ARM_SWING * math.cos(t)
    elbow = (side * SHO_X, UPPER * math.sin(ath), SHO_Z - UPPER * math.cos(ath))
    wrist = (side * SHO_X,
             elbow[1] + FORE * math.sin(ath * 0.6),
             elbow[2] - FORE * math.cos(ath * 0.6))
    return knee, ankle, elbow, wrist


def bob(phase):
    """Vertical bob — two dips per cycle, at the passing positions."""
    return 0.018 * (math.cos(4 * math.pi * phase) - 1.0)


# ------------------------------------------------------- projection
def proj(bx, by, bz, th):
    """Body-local metres -> (draw px x, draw px y, depth), relative to
    the feet. Depth is plan u+v: bigger is NEARER the camera, which is
    what the part sort below reads."""
    c, s = math.cos(th), math.sin(th)
    du = by * c - bx * s               # forward along f=(c,s)
    dv = by * s + bx * c               # across along l=(-s,c)
    return (CHAR_SX * (du - dv) * K,
            (CHAR_SY * (du + dv) - bz * ZS) * K,
            du + dv)


def lit_f(bx, th):
    """Is a part sitting at across-offset `bx` on the lit side?

    The light is fixed in the WORLD, so this has to be asked in plan,
    not on the body — that is the whole reason a turned character
    still reads as lit rather than as a flat two-tone decal."""
    c, s = math.cos(th), math.sin(th)
    return LIT if bx * (-s * LIGHT[0] + c * LIGHT[1]) > 0 else SHA


def body_hw(a, b, th):
    """Projected half-width (screen x, draw px) of an elliptical
    cross-section with semi-axes `a` across the body and `b` front to
    back. In profile this returns the body's DEPTH and face-on its
    WIDTH, which is the foreshortening the eight facings exist for."""
    c, s = math.cos(th), math.sin(th)
    return CHAR_SX * math.hypot(a * (s + c), b * (c - s)) * K


def silhouette(a, b, bz, th):
    """The two SILHOUETTE points of that cross-section, each as
    (x, y, bx) in draw px relative to the feet.

    A HALF-WIDTH ALONE IS NOT ENOUGH, and assuming it was is what made
    the first bake's shoulders look stepped: moving across the body
    changes screen Y as well as screen X in this projection, so a
    shoulder line drawn flat at the centre's own y is a shoulder line
    that never turns. It has to TILT — near shoulder low, far shoulder
    high — and that only falls out if the extreme points are projected
    as points.

    Screen x over the ellipse (bx, by) = (a cos p, b sin p) is
    SX*[by(c-s) - bx(s+c)], stationary where
    b cos p (c-s) + a sin p (s+c) = 0.
    """
    c, s = math.cos(th), math.sin(th)
    p0 = math.atan2(-b * (c - s), a * (s + c))
    out = []
    for p in (p0, p0 + math.pi):
        bx, by = a * math.cos(p), b * math.sin(p)
        x, y, _ = proj(bx, by, bz, th)
        out.append((x, y, bx))
    out.sort(key=lambda q: q[0])
    return out


# ------------------------------------------------------- primitives
def tube(d, o, th, stations, col):
    """A tapered limb through (bx, by, bz, hw) stations, proximal to
    distal — the lofted-station convention the building's columns and
    the introducer's limbs both use. Width is laid perpendicular to
    the SCREEN direction, because a limb reads as its silhouette."""
    pts = [proj(bx, by, bz, th) for bx, by, bz, _ in stations]
    hw = [st[3] * ZS * K for st in stations]
    n = len(pts)
    left, right = [], []
    for i in range(n):
        if i == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        elif i == n - 1:
            dx, dy = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        m = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / m, dx / m
        left.append((o[0] + pts[i][0] + nx * hw[i], o[1] + pts[i][1] + ny * hw[i]))
        right.append((o[0] + pts[i][0] - nx * hw[i], o[1] + pts[i][1] - ny * hw[i]))
    d.polygon(left + right[::-1], fill=col)


def torso(d, o, th, stations, base):
    """The trunk, as two lit/shadow halves split down the body's own
    midline — `figure()`'s treatment, with both the width AND the
    tilt of every section coming from `silhouette`, so the shoulders
    turn with the body instead of staying a flat-topped card.
    `stations` are (bz, a, b): height, half-width across, half-depth
    front to back."""
    edges = [silhouette(a, b, bz, th) for bz, a, b in stations]
    mid = [proj(0, 0, bz, th)[:2] for bz, _, _ in stations]
    for i in (0, 1):
        col = [(o[0] + e[i][0], o[1] + e[i][1]) for e in edges]
        f = lit_f(edges[0][i][2], th)
        d.polygon([(o[0] + m[0], o[1] + m[1]) for m in mid] + col[::-1],
                  fill=shade(base, f))


# ------------------------------------------------------------ figure
def paint(d, o, th, phase, walking):
    """One frame: the Advocate at facing `th`, cycle `phase`.

    Parts are collected with a depth and drawn back to front, so the
    near leg crosses the far one and the bag sits on the right side of
    the body whichever way it is turned. Nothing here is hand-placed
    per direction — every part is a 3D station list and the eight
    drawings fall out of the projection."""
    ph = phase if walking else 0.0
    dz = bob(ph) if walking else 0.0
    parts = []

    def add(depth, fn):
        parts.append((depth, len(parts), fn))

    for side in (-1, 1):                      # -1 right, +1 left
        knee, ankle, elbow, wrist = gait(ph, side)
        if not walking:
            # standing: feet together, the right ankle turned out a
            # little — the introducer's contrapposto, kept
            knee = (side * HIP_X, 0.0, KNEE_Z)
            ankle = (side * HIP_X, 0.0, ANKLE_Z)
            elbow = (side * SHO_X * 1.05, 0.015, ELB_Z)
            wrist = (side * SHO_X * 1.12, 0.03, WRI_Z)
        hip = (side * HIP_X, 0.0, HIP_Z + dz)
        leg_f = lit_f(side * HIP_X, th)
        arm_f = lit_f(side * SHO_X, th)
        # THE SLEEVE STARTS BELOW THE JOINT. A tube centred on the
        # shoulder puts its flat cap half a sleeve-width ABOVE the
        # torso, and on the far side that cap clears the trunk
        # entirely and reads as a flap standing off the shoulder —
        # which is what the first bake did in every 3/4 facing. The
        # arm hangs FROM the joint; the trapezius is above it.
        sho = (side * SHO_X, 0.0, SHO_Z - 0.045 + dz)

        def leg(hip=hip, knee=knee, ankle=ankle, f=leg_f):
            tube(d, o, th, [(*hip, 0.075), (*knee, 0.058),
                            (ankle[0], ankle[1], ankle[2] - 0.02, 0.046)],
                 shade(SLACKS, f))
            # THE SHOE HAS HEIGHT. Drawn flat on the ground plane it is
            # seen almost edge-on from this camera and reads as a smear
            # of shadow, not a shoe — which is exactly how the first
            # bake came out. It is a chunky lozenge from heel to toe,
            # lofted like every other limb, pointing along the body's
            # own forward axis so it goes where the character goes.
            tube(d, o, th,
                 [(ankle[0], ankle[1] - 0.05, 0.062, 0.043),
                  (ankle[0], ankle[1] + 0.055, 0.045, 0.040),
                  (ankle[0], ankle[1] + 0.115, 0.022, 0.030)],
                 shade(SHOE, f))

        def arm(sho=sho, elbow=elbow, wrist=wrist, f=arm_f):
            tube(d, o, th, [(*sho, 0.055), (*elbow, 0.042)],
                 shade(SHIRT, f))                      # short sleeve
            tube(d, o, th, [(*elbow, 0.038), (*wrist, 0.030)],
                 shade(SKIN, f))
            hx_, hy_, _ = proj(*wrist, th)
            r = 0.035 * ZS * K
            d.ellipse([o[0] + hx_ - r, o[1] + hy_ - r,
                       o[0] + hx_ + r, o[1] + hy_ + r], fill=shade(SKIN, f))

        add(proj(*ankle, th)[2], leg)
        add(proj(*wrist, th)[2] + 0.02, arm)

    def trunk():
        torso(d, o, th, [(SHO_Z + 0.05 + dz, 0.165, 0.105),
                         (1.24 + dz, 0.150, 0.100),
                         (1.06 + dz, 0.128, 0.092),
                         (0.90 + dz, 0.150, 0.098)], SHIRT)

    def head():
        # neck
        tube(d, o, th, [(0, 0, NECK_Z + dz, 0.042),
                        (0, 0, SHO_Z - 0.02 + dz, 0.050)],
             shade(SKIN, lit_f(-0.02, th)))
        cx_, cy_, _ = proj(0, 0, (NECK_Z + CROWN_Z) / 2 + dz, th)
        a = body_hw(0.092, 0.100, th)
        hh = (CROWN_Z - NECK_Z) / 2 * ZS * K
        box = [o[0] + cx_ - a, o[1] + cy_ - hh, o[0] + cx_ + a, o[1] + cy_ + hh]
        # the skull, split by a pair of chords — the one genuinely
        # round part, which a straight-sided taper cannot fake
        d.chord(box, 90, 270, fill=shade(SKIN, lit_f(-0.05, th)))
        d.chord(box, 270, 450, fill=shade(SKIN, lit_f(0.05, th)))
        # HAIR GROWS WITH THE BACK OF THE HEAD. Facing the camera it is
        # a cap; facing away it is the whole silhouette. Faceless either
        # way — this is the only cue that says which way the head is
        # turned, so it has to answer to the facing and not be a
        # constant chord.
        c, s = math.cos(th), math.sin(th)
        toward = (c + s) / math.sqrt(2)               # +1 at S, -1 at N
        frac = 0.40 + 0.60 * (1 - toward) / 2
        d.chord([box[0] - 1, box[1] - 1, box[2] + 1,
                 box[1] + (box[3] - box[1]) * frac], 180, 360, fill=HAIR)

    def bag():
        """THE ADVOCATE'S ONE PROP — a canvas shoulder bag on the
        character's right hip. It is what separates this silhouette
        from the introducer's at 40 px in the Capitol, and it breaks
        the body's symmetry, which is most of how a turned figure
        reads as turned."""
        strap = [(0.10, -0.02, SHO_Z - 0.04 + dz), (-0.13, 0.03, 1.02 + dz)]
        tube(d, o, th, [(*strap[0], 0.016), (*strap[1], 0.016)],
             shade(BAG_L, lit_f(0.0, th)))
        cx_, cy_, _ = proj(-0.17, 0.02, 0.98 + dz, th)
        w, h = body_hw(0.086, 0.056, th), 0.096 * ZS * K
        f = lit_f(-0.17, th)
        d.polygon([(o[0] + cx_ - w, o[1] + cy_ - h),
                   (o[0] + cx_ + w, o[1] + cy_ - h),
                   (o[0] + cx_ + w * 0.92, o[1] + cy_ + h),
                   (o[0] + cx_ - w * 0.92, o[1] + cy_ + h)],
                  fill=shade(BAG, f))
        d.line([(o[0] + cx_ - w, o[1] + cy_ - h * 0.25),
                (o[0] + cx_ + w, o[1] + cy_ - h * 0.25)],
               fill=shade(BAG_L, f), width=max(1, K // 2))

    add(proj(0, 0, 1.1, th)[2], trunk)
    add(proj(0, 0, 1.6, th)[2] + 0.001, head)
    add(proj(-0.17, 0.02, 1.0, th)[2] + 0.03, bag)

    for _, _, fn in sorted(parts, key=lambda p: (p[0], p[1])):
        fn()


# -------------------------------------------------------------- sheet
CELL_W, CELL_H = 140, 170          # generous scratch cell, SCENE px
FOOT = (70, 158)                   # where the feet sit inside it


def frames():
    """Every cell, drawn oversized; the sheet is cropped to their union
    afterwards so the frame box is derived rather than guessed."""
    out = []
    for di, _ in enumerate(DIRS):
        th = math.radians(45 - 45 * di)
        for fi in range(WALK_N + 1):
            im = Image.new("RGBA", (CELL_W * K, CELL_H * K), (0, 0, 0, 0))
            paint(ImageDraw.Draw(im), (FOOT[0] * K, FOOT[1] * K), th,
                  (fi - 1) / WALK_N, fi > 0)
            out.append(im)
    return out


def main():
    cells = frames()

    # ---- ONE frame box for the whole sheet, from the union of what
    # was actually drawn. Every cell keeps the SAME foot anchor, so a
    # character turning on the spot cannot shift by a pixel.
    box = None
    for im in cells:
        b = im.getbbox()
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                     max(box[2], b[2]), max(box[3], b[3]))
    # snap outward to a whole K grid, or the downsample puts half a
    # source pixel on the seam between frames (the swing-sheet rule)
    x0, y0 = (box[0] // K) * K, (box[1] // K) * K
    x1, y1 = -(-box[2] // K) * K, -(-box[3] // K) * K
    fw_d, fh_d = x1 - x0, y1 - y0
    cols, rows = WALK_N + 1, len(DIRS)

    sheet = Image.new("RGBA", (fw_d * cols, fh_d * rows), (0, 0, 0, 0))
    for i, im in enumerate(cells):
        sheet.paste(im.crop((x0, y0, x1, y1)),
                    ((i % cols) * fw_d, (i // cols) * fh_d))

    # ---- PREMULTIPLY BEFORE THE DOWNSAMPLE. PIL resizes RGBA channels
    # independently, so a silhouette edge gets its colour averaged with
    # the transparent ground beside it and comes back as a dark
    # hairline all the way round the figure. Same trap the door-swing
    # sheet already paid for.
    a = sheet.getchannel("A")
    rgb = Image.merge("RGB", [Image.composite(ch, Image.new("L", sheet.size), a)
                              for ch in sheet.split()[:3]])
    w, h = sheet.width // OVER, sheet.height // OVER
    rgb = rgb.resize((w, h), Image.LANCZOS)
    a = a.resize((w, h), Image.LANCZOS)
    px_rgb, px_a = rgb.load(), a.load()
    for y in range(h):                      # un-premultiply
        for x in range(w):
            al = px_a[x, y]
            if al:
                r, g, b_ = px_rgb[x, y]
                px_rgb[x, y] = (min(255, r * 255 // al), min(255, g * 255 // al),
                                min(255, b_ * 255 // al))
    final = Image.merge("RGBA", (*rgb.split(), a))
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    final.save(OUT_PNG)

    meta = {
        "image": "char_advocate.png",
        # fw/fh are FILE px — Phaser's spritesheet loader slices the
        # FILE. Everything else here is SCENE px, the same split the
        # door swings keep.
        "fw": fw_d // OVER, "fh": fh_d // OVER,
        "scale": 1 / SHIP,
        # THE PLAN SCALE THIS WAS AUTHORED AT. The runtime scales the
        # sprite by room.basis.sx / this, so one bake serves rooms that
        # disagree about how big a metre is (hallway 40, Capitol 16).
        "sx": CHAR_SX,
        # the feet, in SCENE px inside a frame — the sprite's origin,
        # and the point that sits on the plan position
        "anchor": [(FOOT[0] * K - x0) / K, (FOOT[1] * K - y0) / K],
        "dirs": list(DIRS),
        "walk": WALK_N,
        "height": CROWN_Z * ZS,      # scene px, for a sanity check
    }
    OUT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"wrote {OUT_PNG.name} {final.width}x{final.height} "
          f"({cols}x{rows} frames of {meta['fw']}x{meta['fh']} file px)")
    print(f"      anchor {meta['anchor']} scene px, "
          f"figure {meta['height']:.0f} scene px tall at sx {CHAR_SX}")


if __name__ == "__main__":
    main()
