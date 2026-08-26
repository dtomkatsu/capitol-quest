#!/usr/bin/env python3
"""Bake the Capitol interior — the GALLERY RING above the rotunda —
as a 2.5-D cutaway scene.

One painted room (FEATURES.md §4). The view is the gallery/railing
area (user's call 2026-08-22 — NOT an aerial of the whole building):
the player stands on the balcony ring that circles the open rotunda,
railings at the well's edge, looking down on the Aquarius mosaic and
the tops of the two chamber cones, with the committee doors and the
chamber viewing-gallery doors along the walls. Same vantage as the
w1-opening banner, in the game's 2:1 iso language, dollhouse-cut on
the makai side so the room reads.

Reference: Wikimedia Commons, Category:Hawaii State Capitol interior
photos, plus a user-supplied gallery-corner atrium photo (2026-08-22)
— all reference only, drawn from scratch, so the output is original
work. The corner photo settled: chunky GLOSSY koa cap over a white
kerb plate (the rail is the dominant near element), arched arcade
heads between the courtyard piers, reddish quarry-tile walkway with a
sheen (faint reflections of pickets/columns/doors), potted plants at
the rail, and light falling off away from the well. It also shows the
cone flanks flaring overhead at the chamber ends — NOT drawn, per the
standing one-level call ("just rotunda and the floor that you're on").
A second user photo (2026-08-23) settled the LEGISLATIVE OFFICE DOORS:
flush dark-koa slabs, no recessed panel, faint vertical figure, a
black engraved nameplate two-thirds up, a dull lever, and light dying
toward the floor. See door_at() for the measurements.
Orientation facts baked in:
  - up = mauka (Beretania), down = makai; left = ʻEwa, right = Diamond
    Head. SENATE gallery ʻEwa end (Moon, blue); HOUSE gallery Diamond
    Head end (Sun, red/gold).
  - the rotunda really is open to the sky — sunlight falls into the
    well and the mosaic sits in it.
  - THREE levels since 2026-08-24 (user's call): the courtyard, the
    gallery ring the player stands on, and a Senate floor above it.
    The upper level is RECESSED a full bay — see paint_upper_level().
Palette and treatment follow the interior banners (make_event_art.py):
bright daylit concrete, LIGHT rail over DARK recess, koa doors, one
warm key. Ground outside the room is the overlay's own ink.

Outputs (both hand-versioned in JS via CAP_V — bump together):
  site/assets/map/capitol_scene.png
  site/map/capitol.json          (spawn + hotspots, px in image space)

Build:  python3 tools/render_capitol.py              (crisp, default)
        python3 tools/render_capitol.py --painterly (oil pass; it
        destroys the railing detail — kept only to re-run the
        comparison, never for a shipped bake)
Standalone: does NOT touch the island pipeline; no rebuild order rules.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_PNG = ROOT / "site" / "assets" / "map" / "capitol_scene.png"
OUT_JSON = ROOT / "site" / "map" / "capitol.json"

W, H = 1680, 1240
# SUPERSAMPLE. Everything below is drawn in the FULL scene space
# above, but the room is only ever SEEN at half of it: fit() snaps to
# zoom 0.5 on any window shorter than the scene, and the renderer
# point-samples, so every other row and column was thrown away on the
# way to the screen. Measured 2026-08-24 on a rail crop: 83 unique
# colours reached the canvas where the source has 87 and a resample
# gives 376. That decimation is what read as jagged railings — the
# picket run is 1px lines on a 2px pitch, so WHICH half survived
# drifted as the diagonal advanced, and no redrawing can fix detail
# sampled below its own pitch. Resolving here means the AA is baked
# once by a real filter; the sprite then carries scale=SS, so zoom
# 0.5 x scale 2 is an exact 1:1 blit with no runtime filtering.
# The JSON keeps SCENE coordinates (w/h/spawn/hotspots) — only the
# PNG shrinks — so nothing downstream has to move.
SS = 2
CX, CY = 840, 680          # centre of the gallery ring, at floor level.
                           # CY moved 590 -> 680 when the third level
                           # landed (2026-08-24): the new storey grows
                           # the room UPWARD only, so the content
                           # centre had drifted 90px above the frame's
                           # and the room hung high in the viewport
                           # with dead space under it. Everything is
                           # derived from iso(), so this shifts the
                           # whole scene as one.
A_OUT = 11.5               # ring outer diamond half-size (iso units) —
                           # the walkway is a NARROW balcony (user's
                           # call), not a wide deck
A_IN = 9                   # the rotunda well
DROP = 100                 # COURTYARD STOREY HEIGHT — the drop from
                           # the gallery floor to the courtyard, and
                           # deliberately MUCH TALLER than the 72px
                           # office storeys above it (user, 2026-08-24:
                           # "the two floors are very tall in
                           # comparison to the rotunda; the rotunda
                           # floor should look much taller because it
                           # is"). It was 64 — SHORTER than a storey —
                           # which read as three equal floors and made
                           # the whole section look squashed. The real
                           # court is a double-height arcade: the piers
                           # run a full two storeys to the underside of
                           # the gallery slab. Everything in the well
                           # is expressed against DROP, so this is the
                           # one number; the ceiling on it is the HOLE,
                           # since the courtyard floor slides DOWN as
                           # the court deepens and our own slab starts
                           # eating the medallion past ~110.
# ---- the THIRD level (2026-08-24, user's call), Senate territory.
# It is RECESSED, and that is the entire design. A flush stack was
# drawn 2026-08-22 and rolled back the same day because two rows of
# doors on one plane read as a motel elevation — nothing in the
# section told you the upper floor was BEHIND the lower one. Stepping
# it back a full bay means the court WIDENS as it rises: you see the
# upper walkway's FLOOR, not just more wall, and the two levels are
# legible from a fixed camera. LVL2_IN == A_OUT and LVL2_Y == the
# lower slab's top, so the terrace tiles exactly — the upper rail
# stands on the lower wall's own line, no seam to hide.
LVL2_IN = A_OUT
LVL2_OUT = 14.0
LVL2_Y = 72
RAIL_H = 15                # picket run height
PICKET_PITCH = 6           # px between pickets — EVEN, see even_run().
PICKET_W = 2               # judged on the DOWNSCALED bake: at SS 2 a
                           # 1px picket is half a display pixel and
                           # LANCZOS renders the run as grey haze.
FLUTE_PITCH = 6            # the white fluted bands, same rule
DRUM_RT, DRUM_RB = 72, 102  # chamber drum: top / flared base radius
FASCIA_D = 24              # fluted slab-edge band depth — the photo's
                           # dominant element, deeper than the pickets
POST_H = 19
STUB_H = 10                # makai edge — now only the stair landing's
                           # datum. The knee-high CUT stub walls that
                           # used to stand on the near edges are GONE
                           # (2026-08-24, user: "don't need the walls,
                           # just showing the walkway is fine") — the
                           # walkway ends at its own slab fascia.
CUT_CORE = "#9a927c"       # the sliced wall's CORE. Must sit well clear
                           # of the dressed flutes (#ece6d4) in VALUE —
                           # a near-white cut face vanished entirely at
                           # the 0.5 game zoom, which is the only scale
                           # that matters here.

# THE GROUND FLOOR IS A LOGGIA: THE WALL IS SET BACK AND THE COLUMNS
# STAND IN FRONT OF IT (2026-08-25, from the executive-floor photo —
# user: "fix the column taper and the loggia setback"). Until now the
# courtyard walls stood ON the well line, so the ground storey was a
# flat elevation with piers pasted to it. In the photograph the wall
# is set back the better part of a bay and the columns are free-
# standing out in the court, with a deep shaded gap behind them; that
# gap is most of what says "ground floor" rather than "wall".
#
# THE SET-BACK IS FREE, GEOMETRICALLY: paint_well already clips its
# whole layer to the hole diamond, and the mask is exactly the right
# occluder. A point (u, v) at height dy below the gallery floor casts
# to floor coordinates (u + s, v + s) with s = (DROP - dy)/16, so the
# wall is visible only while |u + s| <= A_IN — i.e. from its foot up
# to dy = DROP - 16*GND_BACK. At 1.6 that is the bottom 74%, and the
# gallery slab eats the top quarter, which is precisely what the
# photograph shows. Deepen GND_BACK and you buy recess by hiding more
# of the glass wall; that is the trade, and it is the only one.
GND_BACK = 2.4
GND_OUT = A_IN + GND_BACK  # the ground storey's wall plane
# THE COLUMNS RUN THE WHOLE HEIGHT — courtyard floor to the top of the
# third floor (user, 2026-08-25: "those columns go all the way up to
# top of third floor"), which is what the photo's vertical strips
# show: one shaft passing BEHIND every walkway and railing, emerging
# again between them. They stand on the COURT EDGE (the A_IN line),
# which is the railing line at every level above — so the same line
# serves the ground colonnade and the upper balustrades, and the
# loggia depth falls out as GND_OUT - A_IN.
COL_DY0, COL_DY1 = -DROP, LVL2_Y + 72     # foot / head, world height
# Half-width at foot / head. The RATIO is what has to survive the SS
# downsample — at display scale the shaft is only ~6px at the foot,
# so a photo-true ~1.5 taper rounds away to a straight post. 1.75 is
# the exaggeration that still reads as one continuous flare.
COL_HW0, COL_HW1 = 6.0, 14.0
COL_FLARE = 1.0            # LINEAR, and measured: a power curve was
                           # tried first to concentrate the swell at
                           # the head, and it cannot work here. Only
                           # two stretches of any shaft are ever seen
                           # — the loggia (t 0 to .34) and above the
                           # gallery cap (t .5 to 1) — and an
                           # exponent that flares one flattens the
                           # other. Straight batter gives BOTH about
                           # 1.4, which is what the photo shows per
                           # storey. The full-height 6->14 ratio is
                           # not what the eye gets; the per-stretch
                           # ratio is.
COL_N = 4                  # stations per mauka run, before nudging

OPEN_BAY = (0.02, 1.0)    # the ʻEwa run's open extent — effectively
                           # the WHOLE run (2026-08-24, breezeway
                           # photo, user: "the slats shouldn't be on
                           # that entrance side. that's also open").
                           # The court's ground level is an open
                           # breezeway on this side: piers in front,
                           # daylight behind, no wall. Only thin
                           # margins remain so the corner posts read.

# THE SMOKESTACK, ITS WALL AND THE DOOR BAY ARE ONE ASSEMBLY, AND THE
# WALL IS THE COURT'S CORNER (user, 2026-08-25: "do you see that blank
# wall it's attached to? imagine that wall is part of the CORNER
# formed with the glass facade"). The blank wall is not a mid-facade
# buttress with more glazing running on past it — it TERMINATES the
# glass facade: its ʻEwa flank sits exactly ON the ʻEwa plane
# (u = -A_IN), so the wall and the glass form the court's mauka
# corner, the door section attaches to its other flank (DOOR_TA is
# DERIVED from it), and the old filler-glazing strip between wall and
# apex is gone because there is no longer any wall for it to live on.
# The cone is bonded to the ʻEwa flank, which puts its body AROUND
# the corner in the open breezeway — matching the photograph, where
# the cones stand in the open lanai at the chamber volume's corner —
# and only its sliver peeks back into the court past the corner.
# Everything below is derived from PIER_U0 = -A_IN; reposition the
# assembly by changing that one anchor.
#
# AND THE ASSEMBLY IS SLID IN, TUCKED UNDER THE 2ND FLOOR (user,
# 2026-08-25, second correction: "it should look like it's under the
# 2nd floor… imagine that the wall is slid in more (also sliding the
# attached stack in more)"). ASM_IN slides wall AND cone together in
# -v (mauka), so the bond between them never moves; the mass that
# slides behind the facade plane is inside the building and simply
# not drawn (the wall still draws from v = -A_IN), which is why the
# slide reads as the wall protruding LESS rather than standing in
# front of the glass. PIER_DEP is DERIVED now — the front face lands
# exactly on the cone's widest visible point at any slide — so the
# bond seam can never show past the front arris again. The "under
# the 2nd floor" half is in smokestack(): the cone runs tall and the
# gallery slab's fascia SHEARS it (it continues above, unseen).
#
# ASM_IN HAS A HARD CEILING AND IT IS THE CONE, NOT TASTE (measured
# 2026-08-25 when the user asked to slide it in further). Only the
# wall's DEPTH answers to the slide — its u position never moves — so
# "slid in" means PIER_DEP shrinking, and PIER_DEP hits 0 at
# ASM_IN = 0.10 + sin(acos(CUT))*R = 1.3557. Past that the front face
# would sit MAUKA of the facade plane, i.e. the corner mass would
# stand behind its own glass and the bond seam would show. The
# assertion below is the guard; the practical ceiling is lower still,
# because the RIGHT FLANK is the only face the depth is spent on and
# it is 16*dep scene px = 8*dep DISPLAY px after the SS downsample:
# 1.20 leaves 1.2 display px (the last value with any depth at all),
# 1.30 leaves 0.4 and LANCZOS erases it, so the corner reads as a
# flat pale band rather than a projecting mass. Shipped at 1.20.
# NB the anchor is the GROUND STOREY's plane (GND_OUT), not the well
# line: when the wall went back for the loggia the whole assembly went
# with it, because it IS that wall's corner. Everything below is
# expressed against GND_OUT for that reason — the slide (ASM_IN) is
# still measured from the facade, so the 2026-08-25 tuning survives
# the set-back unchanged.
PIER_U0 = -GND_OUT         # the wall's ʻEwa flank IS the ʻEwa plane
PIER_W = 0.55              # the wall's width along the run
ASM_IN = 1.20              # how far the whole assembly is slid mauka
STACK_R = 1.45             # base radius, PLAN units (see smokestack)
STACK_CUT = 0.5            # where the wall's flank slices the cone
STACK_U = PIER_U0 - STACK_CUT * STACK_R   # axis, west of the plane
STACK_V = -GND_OUT + 0.10 - ASM_IN        # axis, slid with the wall
# projection into the court: exactly to the cone's widest visible
# point (v = STACK_V + sin(acos(CUT)) * R) — derived, never a number
PIER_DEP = (STACK_V + math.sin(math.acos(STACK_CUT)) * STACK_R) + GND_OUT
assert PIER_DEP > 0, (
    "ASM_IN %.3f slides the corner wall behind its own facade plane "
    "(PIER_DEP %.3f): the bond seam would show. Ceiling is %.4f."
    % (ASM_IN, PIER_DEP, 0.10 + math.sin(math.acos(STACK_CUT)) * STACK_R))
PIER_U1 = PIER_U0 + PIER_W                # right-facing flank
DOOR_TA = (PIER_U1 + GND_OUT) / (2 * GND_OUT)   # the glass starts HERE
DOOR_TB = 0.36

rng = np.random.default_rng(7)


def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


# palette — the interior-banner set (make_event_art.py), adapted
INK = hx("#0a0e18")
# the well's under-gallery shadow recess (NOT the mauka walls — those
# are concrete, see CONC below; user-corrected 2026-08-22)
RECESS = hx("#372c22")
RECESS_D = hx("#241d16")
# the gallery walls are BOARD-FORMED CONCRETE in the photos — grey
# with pour joints and form mottle, not brick and not brown. DARK:
# they face away from the well's sky light, and the first pass
# (#716b5f) was the brightest surface in the room — the value
# hierarchy must keep the white fascia on top (user: "way too bright")
CONC = hx("#4a463f")
CONC_D = hx("#38352f")
# the balcony walkway floors are dark reddish QUARRY TILE in the
# photos (gallery-corner shot: warm terracotta, light grout, a sheen)
FLOOR = hx("#563d2b")
FLOOR_SH = hx("#3f2c1f")
# THE COURTYARD FLOOR IS STONE PAVING, AND IT IS DARKER THAN IT LOOKS
# (re-based 2026-08-25 from the executive-floor photo). It was
# #b3ac97 — lum 167 against the fluted band's 226, a ratio of 1.35,
# which made the court one of the BRIGHTEST surfaces in the room and
# left the pale columns with nothing to stand against. Measured off
# the photograph the white band runs 1.79x the open floor (165 vs 92),
# so the floor belongs at 226/1.79 = 126. It is also far more NEUTRAL
# than the old value: the photo's paving is R-B 10, a warm grey, where
# #b3ac97 was R-B 28 and read as sand. NB the column/floor ratio was
# already right at 1.13 and is unchanged by this — the error was
# entirely in the floor's relation to the white bands.
COURT = hx("#8a8378")      # courtyard below — lum 130, R-B 18
# The sun patch comes down with it. Left at #e4dbbc it stood 1.64x the
# new floor and read as a spotlight; the oculus throws daylight, not a
# follow-spot.
COURT_SUN = hx("#bcb4a0")
SLAB = 1.9                 # paving module, plan units
FASCIA = hx("#e6dfca")     # white floor-edge bands
POST = hx("#dbd4bf")
RAIL = hx("#d5cdb6")
KOA = hx("#7d5734")
KOA_LT = hx("#a97e4f")
# door leaves, MEASURED off the user's Capitol-corridor photo
# (2026-08-23). Against the cream corridor wall the real leaves sit at
# ~0.32 of the wall's value; the old #8a5f36 sat at 0.46 and read as
# light oak under a skylight. The sampled wood is also browner than it
# was orange — R:G:B ≈ 1 : 0.71 : 0.52.
KOA_DR = hx("#644632")     # leaf base
KOA_DR_L = hx("#835e42")   # grain sheen, the lit strike edge
KOA_DR_D = hx("#3a281c")   # architrave, deep reveals
PLAQUE = hx("#211b16")     # the black office nameplate
PLAQUE_TX = hx("#6f675c")  # its engraved lettering
DULL = hx("#6f6355")       # office lever hardware — NOT brass
STEEL = hx("#9aa2ac")
KEY = hx("#f2c14e")
LAVA = hx("#5c4a3d")
LAVA_LT = hx("#75604e")
LAVA_D = hx("#463830")
MOON = hx("#dfe9f6")


def iso(u, v, dy=0.0):
    """Iso projection, SNAPPED to whole pixels. Sub-pixel coords are
    why repeating detail (pickets, flutes) looked irregular: PIL
    rounds each primitive independently, so a run computed from float
    lerps lands on an uneven grid."""
    return (round(CX + 16.0 * (u - v)), round(CY + 8.0 * (u + v) - dy))


def diamond(a, dy=0.0):
    """N, E, S, W corners."""
    return [iso(-a, -a, dy), iso(a, -a, dy), iso(a, a, dy), iso(-a, a, dy)]


def lerp(p, q, t):
    return (round(p[0] + (q[0] - p[0]) * t),
            round(p[1] + (q[1] - p[1]) * t))


def up(p, dy):
    return (p[0], round(p[1] - dy))


def even_run(e0, e1, pitch):
    """Whole-pixel positions along a 2:1 iso edge, on an EXACT pitch.

    `lerp(e0, e1, i / n)` rounds every point independently, so a pitch
    that is not a whole number of pixels lands as a BEAT. Measured
    2026-08-24: the ring's picket pitch was 288/64 = 4.5 px and the run
    came out 5,4,5,4… — 32 gaps of five against 31 of four — which is
    what read as unevenly spaced bars. Snapping the ENDPOINTS to whole
    pixels (the 2026-08-22 pass) could never fix it, because the
    interior positions are still computed in t and rounded one by one.

    Step in PIXELS instead, and force the pitch EVEN: these edges run
    exactly 2:1, so an even x step gives a whole-pixel y step and there
    is nothing left to round. Even also means the pitch survives the
    SS downsample without picking up a second beat at display size.
    """
    dx, dy = e1[0] - e0[0], e1[1] - e0[1]
    step = max(2, int(round(pitch / 2)) * 2)
    n = max(2, int(abs(dx) // step))
    sx = 1 if dx >= 0 else -1
    sy = 1 if dy >= 0 else -1
    ry = abs(dy) / abs(dx) if dx else 0.0        # 0.5 on every ring edge
    return [(e0[0] + sx * (step // 2 + i * step),
             e0[1] + sy * int((step // 2 + i * step) * ry))
            for i in range(n)]


def shade(c, f):
    return tuple(int(max(0, min(255, v * f))) for v in c)


def mix(c1, c2, t):
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(3))


# ------------------------------------------------------------ ground
def paint_ground(d):
    d.rectangle([0, 0, W, H], fill=INK)


def mottle_ink(img):
    """Faint cool drift in the surround so the void isn't a dead flat."""
    arr = np.asarray(img, np.float32)
    small = rng.normal(0, 1, (H // 44 + 2, W // 44 + 2))
    noise = np.kron(small, np.ones((44, 44)))[:H, :W]
    mask = np.all(np.abs(arr - np.array(INK, np.float32)) < 12, axis=-1)
    arr[mask] += (noise[mask, None] * 2.4)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# --------------------------------------------------- ring floor + sun
def paint_ring_floor(d):
    d.polygon(diamond(A_OUT), fill=FLOOR)
    # quarry tile: per-cell tone jitter, then light grout joints —
    # a flat fill read as poured concrete, not tile (atrium photo)
    n = int(2 * A_OUT)
    for k in range(n):
        for l in range(n):
            u0, v0 = -A_OUT + k, -A_OUT + l
            if (-A_IN <= u0 and u0 + 1 <= A_IN
                    and -A_IN <= v0 and v0 + 1 <= A_IN):
                continue                       # the well covers it
            d.polygon([iso(u0, v0), iso(u0 + 1, v0),
                       iso(u0 + 1, v0 + 1), iso(u0, v0 + 1)],
                      fill=shade(FLOOR, rng.uniform(0.95, 1.07)))
    for k in range(1, n):
        a = -A_OUT + k
        d.line([iso(a, -A_OUT), iso(a, A_OUT)], fill=shade(FLOOR, 1.14),
               width=1)
        d.line([iso(-A_OUT, a), iso(A_OUT, a)], fill=shade(FLOOR, 1.14),
               width=1)


def paint_ring_shade(img):
    """Light falls off away from the well — the sky is the key light,
    so the walkway darkens toward the outer walls (atrium photo's
    value structure: dark frame, glowing centre). Stepped bands, not
    a radial vignette; walls/stairs repaint their own ground after."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.polygon(diamond(A_OUT + 0.2), fill=(8, 10, 16, 26))
    ld.polygon(diamond(A_OUT - 0.9), fill=(8, 10, 16, 14))
    ld.polygon(diamond(A_OUT - 1.8), fill=(0, 0, 0, 0))
    img.alpha_composite(lay)


def paint_sun(img):
    """Daylight spills out of the open well onto the inner ring."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for a, al in ((A_IN + 1.8, 22), (A_IN + 1.0, 24), (A_IN + 0.4, 28)):
        ld.polygon(diamond(a), fill=(255, 244, 214, al))
    img.alpha_composite(lay)


# ------------------------------------------------------ the well
def court_paving(img):
    """The courtyard's stone paving: LARGE slabs, each its own tone,
    under a broad low-frequency drift.

    The floor used to be one flat fill with a faint 2-unit grid on
    top, which is why it read as poured concrete. In the photograph
    it is big square pavers with real blotchiness — no two slabs the
    same value, plus staining that wanders across several at once —
    and that mottle is most of what says "stone" at this size.

    TWO tone terms, and they do different jobs. The per-slab jitter
    alone gives television static; the smooth drift alone gives a
    gradient with slab joints drawn over it. Together the staining
    reads as following the paving, which is what the photo shows.
    Amplitude is set by MEASUREMENT, not taste: the photo's open
    paving runs sd/lum 10-21%, and the first pass at +-4% jitter
    came out flat.

    THE SUN PATCH IS COMPOSITED THROUGH A MASK, NOT PAINTED OVER.
    It used to be two big flat quads drawn on top of the floor, which
    covered most of the court and wiped out every bit of this mottle
    — the paving texture was there all along and simply invisible.
    Painting the whole floor once per sun level and pasting through
    the quad's own mask keeps the CRISP oculus edge (a soft pool was
    tried years-ago-equivalent and rejected: the oculus is square)
    while the stone keeps its blotches inside the light.

    It carries its OWN generator rather than the shared `rng`, and
    reseeds it per pass so the mottle registers across the sun edge.
    Every draw here would otherwise shift the sequence for
    paint_walls' form mottle downstream — the same coupling the upper
    level's docstring avoids by taking no mottle at all — so adding a
    slab would silently reshuffle the wall texture two storeys up.
    """
    a = GND_OUT

    def slabs(d, base):
        rf = np.random.default_rng(11)
        d.polygon(diamond(a, -DROP), fill=base)
        k = int(math.ceil(2 * a / SLAB))
        for i in range(k):
            for j in range(k):
                u0, v0 = -a + i * SLAB, -a + j * SLAB
                u1, v1 = min(a, u0 + SLAB), min(a, v0 + SLAB)
                if u1 <= u0 or v1 <= v0:
                    continue
                uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
                drift = (0.075 * math.sin(0.55 * uc + 1.3)
                         * math.cos(0.42 * vc - 0.7)
                         + 0.045 * math.sin(0.21 * (uc + vc) + 2.1))
                d.polygon([iso(u0, v0, -DROP), iso(u1, v0, -DROP),
                           iso(u1, v1, -DROP), iso(u0, v1, -DROP)],
                          fill=shade(base, 1.0 + drift
                                     + rf.uniform(-0.085, 0.085)))
        # the joints, drawn last and KEPT FAINT: in the photo they are
        # hairlines you read the grid from, not a drawn lattice
        m = int(a / SLAB)
        for q in range(-m, m + 1):
            c = q * SLAB
            d.line([iso(c, -a, -DROP), iso(c, a, -DROP)],
                   fill=shade(base, 0.88), width=1)
            d.line([iso(-a, c, -DROP), iso(a, c, -DROP)],
                   fill=shade(base, 0.88), width=1)

    regions = []
    # light through the SQUARE oculus lands as an offset quadrilateral,
    # not a soft ellipse — crisp edge, then a softer halo where bounce
    # fills in.
    for a_, ox, oy, t in ((A_IN - 1.0, -46, 14, 0.62),
                          (A_IN - 2.4, -62, 18, 1.0)):
        regions.append(([(px_ + ox, py_ + oy)
                         for px_, py_ in diamond(a_, -DROP)],
                        mix(COURT, COURT_SUN, t)))
    # DAYLIGHT SPILLING IN THROUGH THE OPEN BAY. The bay only reads as
    # a hole through the building if the sun it lets in lands on
    # something: a wedge on the court floor, aimed along the wall's own
    # inward normal (+u at the ʻEwa wall), does more than anything
    # drawn inside the opening itself. It starts at the SET-BACK wall,
    # because that is where the breezeway now is.
    for k, tone in ((5.0, 0.55), (3.2, 0.75), (1.6, 1.0)):
        v0 = a - 2 * a * (OPEN_BAY[0] - 0.02)
        v1 = a - 2 * a * (OPEN_BAY[1] + 0.02)
        regions.append(([iso(-a, v0, -DROP), iso(-a, v1, -DROP),
                         iso(-a + k, v1, -DROP), iso(-a + k, v0, -DROP)],
                        mix(COURT, COURT_SUN, 0.32 * tone)))
    # the breezeway band, mauka-makai
    regions.append(([iso(-1.1, -a, -DROP), iso(1.1, -a, -DROP),
                     iso(1.1, a, -DROP), iso(-1.1, a, -DROP)],
                    mix(FASCIA, COURT, 0.45)))
    # THE LOGGIA FLOOR IS IN SHADE, and this band is what makes the
    # set-back read at all. The strip behind the columns came out the
    # same bright stone as the open court, so it read as a wall further
    # away and not as a recess. The gallery slab covers it, so it is
    # the one part of the floor that never sees the oculus — hence
    # LAST, after every light region.
    hd, gd = diamond(A_IN, -DROP), diamond(GND_OUT, -DROP)
    for i, j in ((3, 0), (0, 1)):
        regions.append(([hd[i], hd[j], gd[j], gd[i]], shade(COURT, 0.72)))

    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    slabs(ImageDraw.Draw(lay), COURT)
    for poly, base in regions:
        tint = Image.new("RGBA", img.size, (0, 0, 0, 0))
        slabs(ImageDraw.Draw(tint), base)
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        lay.paste(tint, (0, 0), mask)
    img.alpha_composite(lay)


def paint_well(img):
    """Everything seen THROUGH the hole: the sunlit chamber-level
    courtyard one storey down, the far inner walls (fluted slab
    fascia over the ground colonnade), and the two chamber-cone
    tops at the ʻEwa and Diamond Head ends."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    hole = diamond(A_IN)                     # N', E', S', W'
    gnd = diamond(GND_OUT)                   # the set-back wall plane

    # the courtyard floor and every tint that lands on it — see
    # court_paving, which composites them all through masks so the
    # paving keeps its mottle under the light
    court_paving(lay)
    d.line(diamond(A_IN - 0.7, -DROP) + [diamond(A_IN - 0.7, -DROP)[0]],
           fill=shade(COURT, 0.88), width=2)

    # the galleries' overhang shades the courtyard along the far walls
    # — the lit centre reads against this. These stay flat fills: they
    # are narrow shadow bands hugging the wall foot, not floor.
    for e0s, e1s in ((gnd[3], gnd[0]), (gnd[0], gnd[1])):
        d.polygon([(e0s[0], e0s[1] + DROP), (e1s[0], e1s[1] + DROP),
                   (e1s[0], e1s[1] + DROP + 16),
                   (e0s[0], e0s[1] + DROP + 16)],
                  fill=shade(COURT, 0.84))
        d.polygon([(e0s[0], e0s[1] + DROP), (e1s[0], e1s[1] + DROP),
                   (e1s[0], e1s[1] + DROP + 7),
                   (e0s[0], e0s[1] + DROP + 7)],
                  fill=shade(COURT, 0.76))

    # far inner walls: ONE storey down to the chamber level — the
    # player stands on a low gallery, so below our slab's fluted
    # fascia there is only the ground colonnade. Piers rise through.
    # The two runs are NOT the same wall (executive-floor photo,
    # 2026-08-24): the Diamond Head side is a full-height GLASS
    # CURTAIN WALL, and the ʻEwa side is dark arcade with one bay OPEN
    # TO THE OUTSIDE. Before this both were the same koa-slat screen,
    # which is why the court read as a sealed box.
    # THE WALL IS SET BACK, THE FASCIA IS NOT. The fluted band is our
    # own slab's EDGE and stays on the well line; only the wall behind
    # it retreats to GND_OUT, and the shaded gap between the two is
    # the loggia. Drawing both off one edge is what made the ground
    # storey a flat elevation for so long.
    for (h0, h1), (e0, e1), f, glazed in (
            ((hole[3], hole[0]), (gnd[3], gnd[0]), 1.0, False),
            ((hole[0], hole[1]), (gnd[0], gnd[1]), 0.86, True)):
        def q(y0, y1, col):
            d.polygon([up(e0, -y0), up(e1, -y0), up(e1, -y1),
                       up(e0, -y1)], fill=col)
        fluted_band(d, h0, h1, 0, 18, f)              # our slab's fins
        # the loggia's own shade, thrown from the slab down the
        # set-back wall: the recess has to be DARKER than the court
        # floor or the columns have nothing to stand against
        q(-6, DROP, shade(RECESS_D, f * 0.82))        # ground level
        if glazed:
            court_glass(d, e0, e1, f, 21, DROP - 2)
        else:
            # the WHOLE run is open — a breezeway, not a wall with a
            # bay (2026-08-24, breezeway photo). The koa slats that
            # used to fill the margins are gone: there is nothing on
            # this side for them to be a screen OF.
            court_opening(d, e0, e1, OPEN_BAY[0], OPEN_BAY[1], f,
                          22, DROP - 2)
        # no plinth and no arcade arches on either run any more:
        # glass runs to the floor, and the open side has no wall for
        # either to belong to (the arch was dressing on the koa
        # screen, gone with it)
        d.line([up(e0, -DROP + 2), up(e1, -DROP + 2)],
               fill=shade(COURT, f), width=2)
        # the flat pale piers that used to be pasted on this wall are
        # GONE — they were a ground-storey-only device standing on the
        # wall plane. The real columns are free-standing, full height
        # and live in court_column(); paint_columns() draws them.
    # THE SMOKESTACK-AND-CORNER ASSEMBLY (the STACK_*/PIER_* constants
    # carry the full story): the blank corner wall terminates the
    # glass facade with its ʻEwa flank ON the ʻEwa plane, the cone is
    # bonded to that flank with its body around the corner in the open
    # breezeway, and only its sliver peeks back past the corner into
    # the court. Cone first — over the bay backdrop the loop above
    # already painted — then the wall over its bond seam. The cone
    # runs TALL and the slab fascia SHEARS it (2026-08-25, user: "it
    # should look like it's under the 2nd floor") — the mouth is never
    # seen because the stack continues above the slab, off-stage;
    # smokestack() clamps every point to the fascia's bottom line.
    smokestack(d, STACK_U, STACK_V, DROP - 14, STACK_R, 0.55,
               STACK_CUT, 0.92)
    court_panel(d, PIER_U0, PIER_U1, PIER_DEP, 0.9)

    # THE COLUMNS, lower half — foot to the gallery floor. Drawn here
    # rather than with the upper half ON PURPOSE: this layer is
    # clipped to the hole, which is exactly the occlusion a column
    # standing at the court edge needs. Its shadow rises as the shaft
    # does (s = (DROP - dy)/16), so each shaft fades out behind the
    # slab right where it reaches the gallery, and a station too far
    # makai is hidden altogether — both for free, no per-column test.
    for b, cf in column_stations():
        court_column(d, b, COL_DY0, 0, cf)

    # the mosaic, in the sun
    paint_mosaic(d, lay, CX, CY + DROP - 12)

    # chain-post ring around the medallion, as in the photos
    mx, my = CX, CY + DROP - 12
    ring = []
    for a in range(12):
        ang = a * math.pi / 6
        ring.append((mx + math.cos(ang) * 72, my + math.sin(ang) * 37))
    for i, (px_, py_) in enumerate(ring):
        nx, ny = ring[(i + 1) % 12]
        sag = ((px_ + nx) / 2, (py_ + ny) / 2 + 3)
        d.line([(px_, py_ - 7), sag], fill=hx("#b9b2a0"), width=1)
        d.line([sag, (nx, ny - 7)], fill=hx("#b9b2a0"), width=1)
    for px_, py_ in ring:
        d.rectangle([px_ - 1, py_ - 7, px_ + 1, py_], fill=hx("#cfc8b6"))
        d.rectangle([px_ - 1, py_ - 8, px_ + 1, py_ - 7],
                    fill=hx("#8f8974"))

    # THE BIG STONE PLANTER-BENCHES (2026-08-24, from the user's
    # atrium photo — "you also forgot those empty planters that are in
    # the rotunda. the big benches/planters"). Low square stone boxes
    # with a stepped BENCH ledge all the way around, big enough to sit
    # on, and mostly EMPTY — bare soil, per the photo. One carries the
    # courtyard's tree, as in the HABS view. These replace the four
    # floating kukui canopies, which had no planters under them and
    # read as bushes growing out of pavement.
    def planter_bench(x, y, w, treed):
        h = w // 2                          # iso: 2:1
        stone, soil = hx("#c9b88f"), hx("#3a2e22")

        def dia(cx_, cy_, ww):
            hh = ww // 2
            return [(cx_ - ww, cy_), (cx_, cy_ - hh),
                    (cx_ + ww, cy_), (cx_, cy_ + hh)]

        # bench step: broad, low
        for pts, fy, drop_px in ((dia(x, y, w), 1.0, 5),
                                 (dia(x, y - 6, round(w * 0.72)),
                                  1.06, 7)):
            l_, t_, r_, b_ = pts[0], pts[1], pts[2], pts[3]
            d.polygon([l_, b_, (b_[0], b_[1] + drop_px),
                       (l_[0], l_[1] + drop_px)],
                      fill=shade(stone, 0.74 * fy))
            d.polygon([r_, b_, (b_[0], b_[1] + drop_px),
                       (r_[0], r_[1] + drop_px)],
                      fill=shade(stone, 0.60 * fy))
            d.polygon(pts, fill=shade(stone, fy))
            d.line([l_, b_], fill=shade(stone, 0.86 * fy), width=1)
            d.line([b_, r_], fill=shade(stone, 0.80 * fy), width=1)
        # the soil, sunk a hair inside the rim
        d.polygon(dia(x, y - 7, round(w * 0.56)), fill=soil)
        d.polygon(dia(x, y - 8, round(w * 0.56)),
                  outline=shade(soil, 1.35))
        if treed:
            st = round(w * 0.16)
            d.line([(x, y - 8), (x + 1, y - 8 - w // 2)],
                   fill=hx("#6b5236"), width=2)
            ty = y - 8 - w // 2
            d.ellipse([x - w * 0.52, ty - w * 0.30,
                       x + w * 0.52, ty + w * 0.18],
                      fill=hx("#567a4c"))
            d.ellipse([x - w * 0.30, ty - w * 0.22,
                       x + w * 0.24, ty + w * 0.02],
                      fill=hx("#6f9660"))
        else:
            # a few dry stalks — the photo's planters are not clean
            for sx, sh in ((-8, 7), (-2, 10), (5, 6), (9, 9)):
                d.line([(x + sx, y - 8), (x + sx + 2, y - 8 - sh)],
                       fill=hx("#8a7a5c"), width=1)

    planter_bench(CX - 64, CY + DROP - 52, 30, treed=True)
    planter_bench(CX + 64, CY + DROP - 52, 30, treed=False)

    # clip the whole layer to the hole and composite
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(hole, fill=255)
    m = ImageChops.multiply(mask, lay.getchannel("A"))
    img.paste(lay.convert("RGB"), (0, 0), m)


def court_bay_pt(e0, e1, t, y):
    """A point on a courtyard-level wall face: parameter t along the
    hole edge, y pixels BELOW it. The face is extruded straight down,
    so anything vertical on it is a vertical screen line."""
    b = lerp(e0, e1, t)
    return (b[0], b[1] + y)


def court_glass(d, e0, e1, f, top, bot):
    """THE GLASS WALL at courtyard level on the Diamond Head run
    (executive-floor photo). Two sections, as in the photograph:

    - the CENTRAL section is CURVED (user, 2026-08-24: "the central
      glass section should look more curved") — it is the chamber
      drum's glazing bulging into the court. On a flat iso face the
      curve is carried by three cues working together: the mullions
      are spaced by ANGLE (dense at the ends, opening toward the
      middle — a cylinder's foreshortening), the SILL BOWS DOWN
      toward the viewer at mid-arc while the head bows less, and the
      sky-reflection band follows the bow. Any one alone reads flat.
    - the section to its LEFT is the chamber's GLASS ENTRANCE DOORS
      (user: "the section to the left of it is the glass doors"):
      paired glazed leaves under a wide transom in a pale surround,
      per the Senate-entrance photo.

    Dark neutral glazing throughout — a teal pass read as water.
    """
    dy = bot - top

    def face_pt(t, yfrac):
        b = lerp(e0, e1, t)
        return (b[0], b[1] + top + dy * yfrac)

    # ---- the GLASS DOORS. The bay begins exactly at the CORNER
    # WALL'S RIGHT-FACING FLANK (`DOOR_TA`, derived — see the
    # constants at the top): the wall terminates the facade at the
    # corner, the door section attaches to its side, and the cone is
    # bonded to its other flank — the three read as one assembly.
    ta, tb = DOOR_TA, DOOR_TB
    p0, p1 = face_pt(ta, 0), face_pt(tb, 0)
    d.polygon([p0, p1, (p1[0], p1[1] + dy), (p0[0], p0[1] + dy)],
              fill=shade(hx("#d5cdb6"), f))            # pale surround
    q0, q1 = face_pt(ta + 0.02, 0.10), face_pt(tb - 0.02, 0.10)
    qdy = dy * 0.88
    d.polygon([q0, q1, (q1[0], q1[1] + qdy), (q0[0], q0[1] + qdy)],
              fill=shade(hx("#1d211f"), f))            # dark reveal
    # transom over the leaves, then the leaves
    d.line([(q0[0], q0[1] + qdy * 0.38), (q1[0], q1[1] + qdy * 0.38)],
           fill=shade(hx("#b0b4b0"), f), width=1)
    for k in range(1, 4):                              # stiles: 4 leaves
        t = ta + 0.02 + (tb - ta - 0.04) * k / 4
        b0 = face_pt(t, 0.10)
        d.line([(b0[0], b0[1] + qdy * 0.38), (b0[0], b0[1] + qdy)],
               fill=shade(hx("#9aa0a0"), f), width=1)
    for k in (1, 2):                                   # transom mullions
        t = ta + 0.02 + (tb - ta - 0.04) * k / 3
        b0 = face_pt(t, 0.10)
        d.line([(b0[0], b0[1]), (b0[0], b0[1] + qdy * 0.36)],
               fill=shade(hx("#8f958f"), f), width=1)
    # glazing glints on the upper leaves
    d.polygon([q0, q1, (q1[0], q1[1] + qdy * 0.20),
               (q0[0], q0[1] + qdy * 0.20)],
              fill=shade(hx("#39433f"), f))
    d.line([(q0[0], q0[1] - 2), (q1[0], q1[1] - 2)],
           fill=shade(hx("#e2dbc6"), f), width=2)      # lit head

    # ---- the CURVED section: THE WHOLE REST OF THE RUN, one sheet of
    # glazing (reworked 2026-08-25 from the executive-floor photo).
    # It used to stop at 0.62 with flat filler panes beyond, on a
    # sparser mullion pitch, so the wall read as "mullions over the
    # left third and then a dark slab". The photograph is one
    # continuous curtain of bars from the door pier to the corner.
    # Where the sill goes past the well limit (t ~ 0.66 — solve
    # t + |144t-46|/144 <= 1 against the hole diamond) our own slab
    # eats it, so the bow out there costs nothing and is never seen.
    #
    # THE SPACING IS ASYMMETRIC, and that is the correction. The old
    # map was `0.5 - 0.5*cos(pi*u)`: dense at BOTH ends, open in the
    # middle — a half-cylinder seen face-on. This drum is seen
    # OBLIQUELY. The bars compress monotonically toward the far
    # (mauka) end and open toward the near one, because spacing goes
    # as cos(theta) about the point where the drum faces the camera,
    # and that point sits at the near end of the visible arc. Sill
    # bow follows the SAME cos(theta), so the two cues finally agree
    # — before, a symmetric bow was arguing with the mullions.
    #
    # NO TRANSOM RAILS. Two horizontal arcs used to cross the glass
    # at 0.42/0.72; the photograph has none — the mullions run head
    # to sill unbroken, and the horizontals were what made this read
    # as a shopfront rather than a chamber drum.
    ta, tb = DOOR_TB, 0.98
    n = 20
    TH_A = math.radians(-64)   # the arc's far edge, turning away. Any
                               # steeper and the compressed end falls
                               # under the sampling pitch and mushes:
                               # cos(64) = .44, so the tightest gap is
                               # ~44% of the mean — see the printout
                               # in the docstring test below.
    sa = math.sin(TH_A)
    bow_s, bow_h = 9, 3        # sill and head bow, px, where it faces us
    tops, sills = [], []
    for i in range(n + 1):
        th = TH_A * (1 - i / n)                  # TH_A .. 0
        t = ta + (tb - ta) * (math.sin(th) - sa) / (0 - sa)
        bow = (math.cos(th) - math.cos(TH_A)) / (1 - math.cos(TH_A))
        p = face_pt(t, 0)
        tops.append((p[0], p[1] + round(bow_h * bow)))
        b = face_pt(t, 1.0)
        sills.append((b[0], b[1] + round(bow_s * bow)))
    d.polygon(tops + sills[::-1], fill=shade(hx("#171d1f"), f))
    # sky reflection following the bow, upper third
    refl = [lerp(pt, pb, 0.34) for pt, pb in zip(tops, sills)]
    d.polygon(tops + refl[::-1], fill=shade(hx("#2e3839"), f))
    d.polygon(tops + [lerp(pt, pb, 0.15) for pt, pb
                      in zip(tops, sills)][::-1],
              fill=shade(hx("#414d4b"), f))
    # 2px, not 1 — the picket rule again (PICKET_W): at SS 2 a 1px
    # bar is half a display pixel and LANCZOS renders the whole run
    # as a bluish haze instead of glazing. 20 bays at 2px gives the
    # bar-and-gap rhythm that survives the downsample; denser was
    # tried (30, 24) and both mushed at the compressed end.
    for i in range(n + 1):                             # angle mullions
        d.line([tops[i], sills[i]], fill=shade(hx("#a7ad9f"), f),
               width=2)
    d.line(tops, fill=shade(hx("#d9d2bc"), f), width=2)   # beam over
    d.line([(x, y + 2) for x, y in tops],
           fill=shade(hx("#8f8874"), f), width=1)
    d.line(sills, fill=shade(hx("#3a352c"), f), width=2)  # sill shadow

    # ---- the PIER between the doors and the curve, drawn LAST so it
    # stands proud of both. It was implied before — the doors' right
    # surround against the curve's dense left mullions — and the
    # curve's sill shadow cut across its foot, so it hung in the glass
    # without reaching the floor (user: "the middle column going
    # through the glass also isn't meeting the ground"). A pier is a
    # thing that STANDS: full height, a lit face, and a darker plinth
    # block at the bottom that the floor line crosses.
    pc = face_pt(0.352, 0)
    pw = 5
    d.polygon([(pc[0] - pw, pc[1] - 1), (pc[0] + pw, pc[1] - 1),
               (pc[0] + pw, pc[1] + dy), (pc[0] - pw, pc[1] + dy)],
              fill=shade(hx("#cfc8b2"), f))
    d.rectangle([pc[0] + pw - 2, pc[1] - 1, pc[0] + pw, pc[1] + dy],
                fill=shade(hx("#a29b87"), f))          # shaded flank
    d.rectangle([pc[0] - pw, pc[1] + dy - 7, pc[0] + pw, pc[1] + dy],
                fill=shade(hx("#b3ac97"), f))          # plinth foot
    d.line([(pc[0] - pw, pc[1] + dy - 7), (pc[0] + pw, pc[1] + dy - 7)],
           fill=shade(hx("#8b8574"), f), width=1)
    d.line([(pc[0] - pw, pc[1] - 1), (pc[0] + pw, pc[1] - 1)],
           fill=shade(hx("#e5deca"), f), width=1)      # lit head


def court_opening(d, e0, e1, t0, t1, f, top, bot):
    """A BAY OPEN TO THE OUTSIDE on the ʻEwa wall (2026-08-24, user:
    "the opening to the outside as well on the left wall"). The court
    is not sealed — the ground storey runs straight through the wing
    to the street, and in the photo that bay is the one BRIGHT hole in
    a dark arcade: daylight, the exterior colonnade in silhouette, and
    a pale slab of plaza under it.

    It is painted as depth, not as a light patch: sky at the head,
    the far colonnade standing on a horizon, then plaza. The jamb gets
    a dark reveal on one side and a lit arris on the other so the wall
    reads as having thickness.
    """
    q0, q1 = court_bay_pt(e0, e1, t0, top), court_bay_pt(e0, e1, t1, top)
    dy = bot - top

    def band(lo, hi, c):
        d.polygon([(q0[0], q0[1] + dy * lo), (q1[0], q1[1] + dy * lo),
                   (q1[0], q1[1] + dy * hi), (q0[0], q0[1] + dy * hi)],
                  fill=shade(hx(c), f))

    # WHAT IS OUT THERE IS CONCRETE, NOT A SKYLINE (2026-08-24, user:
    # "instead of showing a fake, made up background for the outside
    # (beyond the pillars), show the concrete stepped levels etc.").
    # The breezeway looks out along the building's own structure —
    # the outer pier rows, the slatted sunshade, and the stepped
    # concrete terraces of the plaza marching away in bands of light
    # and shade. An invented skyline of towers and palms was making
    # up a city that the room cannot actually see; concrete is both
    # true and easier to read, because every band is the same
    # material at a different angle to the sun.
    # ONE strong horizon (the shade/sun line where the covered walk
    # ends), and the steps only in the bottom third. A first pass ran
    # even bands the full height and read as a striped awning — a
    # terrace is legible because it is a LIT TREAD over a DARK RISER,
    # which needs room, so three big steps beat six small ones.
    band(0.00, 1.00, "#8e8b7c")                       # the covered walk
    band(0.00, 0.11, "#514f47")                       # deep under-slab
    band(0.11, 0.17, "#c6c1ac")                       # the sunshade run
    band(0.17, 0.55, "#8b8879")                       # walk, in shade
    band(0.55, 0.74, "#ece6ce")                       # plaza, full sun
    d.line([(q0[0], q0[1] + dy * 0.55), (q1[0], q1[1] + dy * 0.55)],
           fill=shade(hx("#8b8878"), f), width=2)     # the shade line
    # the STEPPED LEVELS, marching toward us
    for frac, lit, dark in ((0.74, "#e4dec6", "#8f8b7c"),
                            (0.83, "#dcd6be", "#87836f"),
                            (0.92, "#d3ccb4", "#7e7a68")):
        band(frac, min(frac + 0.09, 1.0), lit)
        d.line([(q0[0], q0[1] + dy * frac), (q1[0], q1[1] + dy * frac)],
               fill=shade(hx(dark), f), width=2)
    span = q1[0] - q0[0]
    # the OUTER pier rows, standing in the shaded walk — offset from
    # the near row's 0.18/0.5/0.82 or the two rows read as one pier
    # with a shadow. Two ranks, the far one paler and shorter.
    for pf, wd, lo, hi, c in ((0.33, 5, 0.10, 0.62, "#6a675c"),
                              (0.67, 5, 0.10, 0.62, "#6a675c"),
                              (0.21, 3, 0.14, 0.50, "#767366"),
                              (0.50, 3, 0.14, 0.50, "#767366"),
                              (0.79, 3, 0.14, 0.50, "#767366")):
        x = round(q0[0] + span * pf)
        yb = q0[1] + (q1[1] - q0[1]) * pf
        d.polygon([(x - wd, yb + dy * lo), (x + wd, yb + dy * lo),
                   (x + wd - 1, yb + dy * hi), (x - wd + 1, yb + dy * hi)],
                  fill=shade(hx(c), f))
        d.line([(x - wd, yb + dy * lo), (x - wd + 1, yb + dy * hi)],
               fill=shade(hx("#cbc7b4"), f), width=1)
    # the slatted sunshade fins over the outer walk
    sl0 = (q0[0], q0[1] + dy * 0.11)
    sl1 = (q1[0], q1[1] + dy * 0.11)
    for b in even_run(sl0, sl1, 8):
        d.line([(b[0], b[1]), (b[0], b[1] + 6)],
               fill=shade(hx("#9d9a88"), f), width=2)
    d.line([sl0, sl1], fill=shade(hx("#f2ecd8"), f), width=2)
    d.line([q0, (q0[0], q0[1] + dy)], fill=shade(hx("#2a231c"), f),
           width=2)                                    # dark reveal
    d.line([q1, (q1[0], q1[1] + dy)], fill=shade(hx("#e8e2ce"), f),
           width=1)                                    # lit arris
    d.line([q0, q1], fill=shade(hx("#4a4234"), f), width=2)  # head soffit


def column_stations():
    """Plan positions of the full-height columns, as screen points at
    GALLERY FLOOR level, with each run's shading factor. ONE list,
    shared by both halves of every shaft and by both call sites, so
    the piece below the gallery and the piece above cannot drift onto
    different centres.

    A shaft runs the whole height, so it has to clear the doorways on
    BOTH upper storeys, not just one — and those two schedules sit on
    different diamonds from each other and from the column line, so
    the clearance test is in SCREEN X (see run_x). Two rules earned
    the hard way when this was first wired:

    - **Only the NAMED doors are protected.** Clearing every doorway
      is impossible and asking for it returned zero columns: the runs
      carry 13 and 16 features, spaced 20-50px apart on the column
      line, against a shaft that needs ~30px of room either side.
      Passing in front of an anonymous office door is not the 08-24
      "clipping" complaint — that was bronze columns drawn ON the
      wall plane, where a collision left a sliver poking out of a
      frame. These stand a full bay in front of the wall and occlude
      it honestly, exactly as they do in the photograph. The named
      doors are protected because they are HOTSPOTS: covering one
      costs the player a door they need to click.
    - **The gap to test is the range of valid CENTRES, not the space
      between doors.** Requiring a clear span as wide as the shaft
      itself threw away every position on the Diamond Head run,
      where two named doors 61px apart still leave a perfectly good
      centre between them.

    Stations start on a regular pitch — a colonnade is structural and
    wants to look it — and a blocked one is NUDGED to the nearest
    clear x rather than dropped, so the rhythm survives contact with
    the door schedule instead of losing a whole bay to it.
    """
    hole = diamond(A_IN)
    out = []
    for (e0, e1), f, r in (((hole[3], hole[0]), 1.0, 0),
                           ((hole[0], hole[1]), 0.86, 1)):
        span = 32.0 * A_IN
        blocked = [(run_x(r, a, ft), FEAT_HW[k])
                   for feats, a in ((GALLERY_FEATS[r], A_OUT),
                                    (UPPER_FEATS[r], LVL2_OUT))
                   for nm, ft, k in feats if nm]

        def clears(t):
            x = run_x(r, A_IN, t)
            # HALF the frame, not all of it: the shaft may graze an
            # architrave but must leave the leaf and its centre — the
            # clickable part — clear. Demanding the whole frame put
            # every column on the Diamond Head run into its left half
            # and left the House door's end of the wall bare.
            return all(abs(x - bx) >= COL_HW1 + hw * 0.5 + 4
                       for bx, hw in blocked)

        for i in range(COL_N):
            t0 = (i + 0.5) / COL_N
            t = next((t0 + s * j / span for j in range(0, 44, 2)
                      for s in (1, -1)
                      if 0.03 < t0 + s * j / span < 0.97
                      and clears(t0 + s * j / span)), None)
            if t is not None:
                out.append((lerp(e0, e1, t), f))
    return out


def col_hw(dy):
    """Half-width of a courtyard column at world height dy. ONE
    function, because the shaft is drawn in two pieces — the part
    below the gallery floor goes into paint_well's clipped layer, the
    part above is painted after the walls — and if the two halves
    computed their own taper they would step at the join."""
    t = (dy - COL_DY0) / (COL_DY1 - COL_DY0)
    t = min(1.0, max(0.0, t))
    return COL_HW0 + (COL_HW1 - COL_HW0) * t ** COL_FLARE


def court_column(d, b, dy_lo, dy_hi, f=1.0):
    """One of the courtyard's FULL-HEIGHT columns, drawn between two
    world heights (the caller splits the shaft at the gallery floor).

    THE TAPER IS THE POINT (2026-08-25, from the executive-floor
    photo). These read as plain posts until they FLARE: the Capitol's
    columns are broad at the head and draw down to a narrow foot, and
    that one profile is the building's whole architectural idea. They
    were constant-width rectangles here, which is why the ground
    storey looked like scaffolding holding up a wall.

    `b` is the screen point of the column's plan position AT GALLERY
    FLOOR LEVEL, so screen y is just b[1] - dy: a vertical column has
    a fixed screen x, and only the width answers to height.
    """
    steps = 14
    lo, hi = min(dy_lo, dy_hi), max(dy_lo, dy_hi)
    left, right, inner, lit = [], [], [], []
    for i in range(steps + 1):
        dy = lo + (hi - lo) * i / steps
        hw, y = col_hw(dy), round(b[1] - dy)
        left.append((round(b[0] - hw), y))
        right.append((round(b[0] + hw), y))
        inner.append((round(b[0] + hw * 0.10), y))
        lit.append((round(b[0] - hw * 0.52), y))
    # THREE tones, not two: these shafts are faceted and nearly a
    # storey wide at the head, so a single flat face with one dark
    # edge read as a pale ribbon taped over the wall. Bright return,
    # mid front, shaded flank — the court's light comes over the
    # makai shoulder, so +x is the turned-away side, the same
    # convention the piers and the cone already use.
    d.polygon(left + right[::-1], fill=shade(hx("#c9c1ab"), f))
    d.polygon(left + lit[::-1], fill=shade(hx("#ddd6c0"), f))
    d.polygon(inner + right[::-1], fill=shade(hx("#948c7b"), f))
    # BOTH edges get a real keyline. The ʻEwa run's backdrop is the
    # open breezeway — bright plaza bands — so a pale shaft against it
    # has no silhouette at all without one; same lesson the cone's
    # 2px keyline records against the glazing.
    d.line(left, fill=shade(hx("#e2dbc6"), f), width=1)      # lit arris
    d.line(right, fill=shade(hx("#6d6657"), f), width=2)     # dark edge
    # ONE pour joint per storey — the photo's shafts are cast in
    # lifts and the horizontal break is what keeps a tall shaft from
    # reading as an extruded sliver. Nothing finer: at display scale
    # a second line per storey is noise.
    for dy in (0, LVL2_Y):
        if lo < dy < hi:
            hw, y = col_hw(dy), round(b[1] - dy)
            d.line([(round(b[0] - hw) + 1, y), (round(b[0] + hw) - 1, y)],
                   fill=shade(hx("#b3ab95"), f), width=1)


def court_panel(d, u_a, u_b, dep, f=1.0):
    """The PROJECTING PIER at the edge of the chamber's glass bay —
    the "panel" the half-cone is bonded to. It must stand proud of
    the curtain wall exactly far enough to hide the cone's flat cut
    face (PIER_DEP is derived from the cone for that reason); since
    the 2026-08-25 slide (ASM_IN) that projection is shallow — the
    wall reads as tucked under the gallery slab, not standing out in
    the well. Drawn AFTER the cone, so the cladding dies into its
    hidden ʻEwa-side flank.

    Its +u flank and its front face both turn toward this camera; the
    -u flank (the bonded one) does not, which is exactly why the cut
    never shows.
    """
    vw, vf = -GND_OUT, -GND_OUT + dep
    fl, tp = -(DROP - 2), -18
    d.polygon([iso(u_a, vf, fl), iso(u_b, vf, fl),
               iso(u_b, vf, tp), iso(u_a, vf, tp)],
              fill=shade(hx("#c2bba8"), f))              # front face
    d.polygon([iso(u_b, vf, fl), iso(u_b, vw, fl),
               iso(u_b, vw, tp), iso(u_b, vf, tp)],
              fill=shade(hx("#9a9384"), f))              # right flank
    d.polygon([iso(u_a, vf, tp), iso(u_b, vf, tp),
               iso(u_b, vw, tp), iso(u_a, vw, tp)],
              fill=shade(hx("#d6cfba"), f))              # soffit return
    d.line([iso(u_a, vf, fl), iso(u_a, vf, tp)],
           fill=shade(hx("#e6dfca"), f), width=1)        # lit arris
    d.line([iso(u_a, vf, fl), iso(u_b, vf, fl)],
           fill=shade(hx("#7d7768"), f), width=1)        # foot shadow


def smokestack(d, u0, v0, h, r_bot, r_top, cut=0.0, f=1.0):
    """THE TILE-CLAD CONE beside the chamber's glass entrance — and it
    is a HALF-CONE CUT BY THE PANEL'S PLANE, of which this vantage
    shows only a SLIVER (user, 2026-08-25: "it's a half-cone cut by
    the wall plane… it would be part of the left half of the cone that
    remains, but you'd only be able to see a sliver of the cone in
    this perspective"). Six passes drew a FULL free-standing cone and
    every one of them read as wrong perspective, because the shape
    itself was wrong — no amount of moving or resizing a whole cone
    can fix a cone that should be half buried in a panel.

    THE ANGLES, and they are forced, not chosen. Radii here are PLAN
    units, so `iso()` places every point and the 2:1 foreshortening
    comes out on its own. With the cut plane at u = u0 and the cone
    bonded to the panel's side face:
      - the retained half is u <= u0, i.e. theta in (90, 270).
      - a face is turned toward this camera only where its plan normal
        has a positive dot with the view direction (1,1)/sqrt2, i.e.
        cos(th) + sin(th) > 0, i.e. theta in (-45, 135).
      - the intersection is theta in (90, 135) — a 45-degree crescent,
        and it lies entirely LEFT of the axis on screen (dx runs from
        -16R at the cut to -22.6R at the silhouette). That is the
        sliver. The flat semicircular face is bonded against the
        panel and is never visible.

    So this draws a narrow tapering crescent, not a tower: the cut
    edge on the right where the cladding dies into the panel, the
    silhouette on the left, sagging course arcs between them.
    Everything else about the cone — the batter (power 1.35), the
    coarse ~8px courses that carry the wrap, no per-tile detail (it
    is under the sampling pitch) — is unchanged and still binding.

    THE TOP IS SHEARED BY THE GALLERY SLAB, NOT CAPPED (2026-08-25,
    user: "it should look like it's under the 2nd floor"): every
    drawn point is clamped to the fascia band's BOTTOM line
    (y = apex + 18 + |x - CX| / 2), so the courses die under the
    slab and the stack reads as continuing above it, off-stage. The
    mouth rim is gone with it — a mouth you can see means the stack
    ended in the well, which is exactly the old floating read this
    replaces. Don't shorten h back to "stop under the hole edge";
    the shear line IS the top.

    It belongs to the ROTUNDA FLOOR alone; nothing on the gallery or
    Senate levels reacts to it.
    """
    # `cut` is where the panel's face slices the cone, as a fraction
    # of the radius measured from the axis: 0.0 is a true half-cone,
    # positive means the cone protrudes PAST the panel's edge by that
    # much. It is the one dial that controls how much of the cone
    # survives, and it matters because the visible arc runs from
    # acos(cut) to 135 degrees and nothing else widens it — a true
    # half-cone leaves 6.6*R px, about three display pixels here,
    # which is not a shape anyone can read. Moving or resizing the
    # cone cannot substitute: the visible FRACTION is fixed by the
    # projection, only `cut` changes it.
    TH0, TH1 = math.acos(cut), math.radians(135)
    n = 10
    grout = hx("#5b5b50")
    y0 = -(DROP - 2)                            # courtyard floor
    # the gallery slab's fascia BOTTOM, as a screen line: the band
    # hangs 18px under the hole edge, and both mauka edges fall away
    # from the apex at the iso 1:2 — one expression covers the cone
    # whichever side of the corner a point lands on
    y_sh = CY - 16 * A_IN + 18

    def sh(p):
        return (p[0], max(p[1], round(y_sh + abs(p[0] - CX) / 2)))

    def radius(t):
        return r_top + (r_bot - r_top) * (1 - t) ** 1.35

    def arc(t):
        """The visible crescent at height fraction t, plus per-sample
        shading: lit where the surface still faces the court, falling
        away to the silhouette. Every point is sheared by the slab."""
        rr, dy = radius(t), y0 + h * t
        pts, fac = [], []
        for i in range(n + 1):
            th = TH0 + (TH1 - TH0) * i / n
            pts.append(sh(iso(u0 + rr * math.cos(th),
                              v0 + rr * math.sin(th), dy)))
            # the value FLOOR matters more than the range here: the
            # silhouette edge sits against the court's near-black
            # glazing, and at 0.72 it sank into it and the whole
            # crescent read as a smudge rather than as cladding
            fac.append(0.86 + 0.28 * (math.cos(th) + math.sin(th))
                       / 1.41421)
        return pts, fac

    # contact shadow, hugging the foot on the court side
    b_pts, _ = arc(0.0)
    d.polygon(b_pts + [(px_ + 5, py_ + 3) for px_, py_ in b_pts][::-1],
              fill=shade(hx("#8f8a76"), f))
    rows = max(6, int(h) // 8)
    prev, prev_f = arc(0.0)
    for r in range(1, rows + 1):
        cur, cur_f = arc(r / rows)
        wob = 1.0 + 0.022 * math.sin(r * 2.4)   # per COURSE, never per tile
        for i in range(n):
            tone = (cur_f[i] + cur_f[i + 1]) / 2
            d.polygon([prev[i], prev[i + 1], cur[i + 1], cur[i]],
                      fill=shade(hx("#96957f"), f * tone * wob))
        # the course arc, 2px so it survives the SS downsample
        d.line(cur, fill=shade(grout, f), width=2)
        prev, prev_f = cur, cur_f
    cut_edge = [arc(r / rows)[0][0] for r in range(rows + 1)]
    sil_edge = [arc(r / rows)[0][n] for r in range(rows + 1)]
    d.line(cut_edge, fill=shade(hx("#6d6a5c"), f), width=1)   # into panel
    # a real keyline on the silhouette — 2px, so it survives the SS
    # downsample and separates the cone from the glazing behind it.
    # Its sheared top run doubles as the shadow gap under the slab.
    d.line(sil_edge, fill=shade(hx("#3d3d36"), f), width=2)   # silhouette
    # NO mouth rim: the stack is sheared by the slab and continues
    # above it — a visible rim would put its top back in the well

def paint_mosaic(d, lay, cx, cy):
    """A round glass-tile floor medallion in sea colours. The REAL
    rotunda floor is Tadashi Sato's 'Aquarius' — a copyrighted 2-D
    artwork, and the US has no freedom-of-panorama for 2-D art — so
    this is deliberately a GENERIC original design: an even terrazzo
    scatter of small glass rounds inside border rings, reproducing
    nothing of Sato's composition. Keep it generic on every edit."""
    rx, ry = 58, 29
    d.ellipse([cx - rx - 4, cy - ry - 3, cx + rx + 4, cy + ry + 3],
              fill=hx("#8f8974"))
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=hx("#2e6b91"))
    d.ellipse([cx - rx + 7, cy - ry + 4, cx + rx - 7, cy + ry - 4],
              outline=hx("#7ec8e3"), width=2)
    cols = ["#3799c2", "#5cc6d2", "#7fd0b0", "#a8e6de", "#255e8e"]
    for gu in range(-7, 8):          # even jittered grid — terrazzo
        for gv in range(-7, 8):
            x = cx + gu * 8 + rng.uniform(-2, 2)
            y = cy + gv * 4 + rng.uniform(-1, 1)
            if ((x - cx) / (rx - 9)) ** 2 + ((y - cy) / (ry - 6)) ** 2 > 1:
                continue
            r = rng.uniform(2.0, 3.4)
            d.ellipse([x - r, y - r / 2, x + r, y + r / 2],
                      fill=hx(cols[rng.integers(len(cols))]))
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
              outline=hx("#e8e4d4"), width=2)


# ---------------------------------------------------------- railings
def fluted_band(d, e0, e1, y_top, depth, f=1.0):
    """The precast fin fascia: CHUNKY alternating white panels with
    real shadow gaps — the photo's most distinctive element. 5px fin,
    2px gap, bright top lip."""
    p0, p1 = (e0[0], e0[1] + y_top), (e1[0], e1[1] + y_top)
    d.polygon([p0, p1, (p1[0], p1[1] + depth), (p0[0], p0[1] + depth)],
              fill=shade(hx("#ece6d4"), f))
    for b in even_run(p0, p1, FLUTE_PITCH):
        d.line([(b[0], b[1] + 2), (b[0], b[1] + depth - 1)],
               fill=shade(hx("#9d9683"), f), width=2)
    d.line([p0, p1], fill=shade(hx("#f7f3e6"), f), width=2)
    d.line([(p0[0], p0[1] + depth), (p1[0], p1[1] + depth)],
           fill=shade(hx("#8a8474"), f), width=1)


def paint_railings(d):
    """The real railing, per the atrium photos, drawn CHUNKY enough to
    survive game zoom: a deep fluted white parapet fascia at the slab
    edge (hanging into the well), an OPEN run of dark metal pickets
    you see the well through, and a heavy koa handrail. No fat posts."""
    hole = diamond(A_IN)
    edges = [(hole[3], hole[0], False), (hole[0], hole[1], False),
             (hole[1], hole[2], True), (hole[2], hole[3], True)]
    for e0, e1, near in edges:
        # NB the near slabs' own fascia faces the well, i.e. AWAY from
        # the camera — drawing it here painted over the walkway floor
        # and made the front decks read as tilted faces (user-caught).
        # Only the far edges' fascia is visible, and that is painted
        # with the well walls.
        # white kerb plate at the floor (gallery-corner photo: a light
        # base curb sits under the picket run on the walkway side)
        d.polygon([e0, e1, up(e1, 4), up(e0, 4)],
                  fill=shade(hx("#ddd6c1"), 0.98))
        d.line([up(e0, 4), up(e1, 4)], fill=hx("#8a8474"), width=1)
        # pickets: thin metal, well-spaced — dark against the sunlit
        # courtyard (near), pale against the dark walkway (far)
        # dark bronze BOTH sides (user: railing shade darker — the
        # photos have no pale pickets; the white parts are the kerb
        # and the outer fascia, never the metal)
        pk = hx("#3a332a") if near else hx("#4a4238")
        for b in even_run(e0, e1, PICKET_PITCH):
            d.line([up(b, 5), up(b, RAIL_H)], fill=pk, width=PICKET_W)
        # slim stanchions — dark bronze like the pickets
        for i in range(1, 8):
            b = lerp(e0, e1, i / 8.0)
            d.rectangle([b[0] - 1, b[1] - RAIL_H, b[0] + 1, b[1] - 4],
                        fill=hx("#57503f"))
        # the koa handrail — a WIDE polished cap with a specular glint
        # (gallery-corner photo: the glossy rail is the dominant near
        # element; the glint row is what sells "polished")
        d.line([up(e0, RAIL_H + 1), up(e1, RAIL_H + 1)],
               fill=hx("#54391f"), width=2)          # underside
        d.line([up(e0, RAIL_H + 3), up(e1, RAIL_H + 3)],
               fill=hx("#9a6a38"), width=3)          # body
        d.line([up(e0, RAIL_H + 5), up(e1, RAIL_H + 5)],
               fill=hx("#c79a5c"), width=2)          # lit top
        d.line([up(e0, RAIL_H + 6), up(e1, RAIL_H + 6)],
               fill=hx("#ecd0a1"), width=1)          # gloss glint
        # contact shadow on the floor
        d.line([(e0[0], e0[1] + 2), (e1[0], e1[1] + 2)],
               fill=shade(FLOOR, 0.8), width=2)
        if near:
            # the polished tile throws the rail back at us — pickets
            # as faint verticals, the koa cap as a warm smear
            rf = mix(FLOOR, pk, 0.45)
            # the SAME run — a reflection that drifts off its own
            # pickets is worse than no reflection
            for b in even_run(e0, e1, PICKET_PITCH):
                d.line([(b[0], b[1] + 4), (b[0], b[1] + RAIL_H - 3)],
                       fill=rf, width=PICKET_W)
            d.line([(e0[0], e0[1] + RAIL_H + 2),
                    (e1[0], e1[1] + RAIL_H + 2)],
                   fill=mix(FLOOR, hx("#9a6a38"), 0.38), width=2)
            d.line([(e0[0], e0[1] + RAIL_H + 4),
                    (e1[0], e1[1] + RAIL_H + 4)],
                   fill=mix(FLOOR, hx("#ecd0a1"), 0.16), width=1)
    # corner posts where the rail runs meet — bronze, not white
    for c in hole:
        d.rectangle([c[0] - 2, c[1] - RAIL_H - 6, c[0] + 2, c[1]],
                    fill=hx("#57503f"))
        d.rectangle([c[0] + 1, c[1] - RAIL_H - 6, c[0] + 2, c[1]],
                    fill=hx("#443e30"))
        d.rectangle([c[0] - 2, c[1] - RAIL_H - 6, c[0] + 2,
                     c[1] - RAIL_H - 2], fill=KOA)
        d.line([(c[0] - 2, c[1] - RAIL_H - 6),
                (c[0] + 2, c[1] - RAIL_H - 6)], fill=KOA_LT, width=1)


def paint_rail_pots(d):
    """Potted plants set against the well railing on the walkway —
    the small life the gallery-corner photo shows at intervals.
    Terracotta pot lit from the well side (left), soil line, then
    arcing fronds drawn dark mass first, blades over, light tips
    last — the layering is what reads as a PLANT instead of a green
    blob at this size."""
    hole = diamond(A_IN)
    # (tip dx, tip dy rel. crown, colour) — a fan, asymmetric on
    # purpose; a symmetric fan reads as a printed icon
    fronds = ((-8, -8, "#3f5f3a"), (-5, -12, "#567a4c"),
              (-1, -14, "#6f9660"), (3, -13, "#567a4c"),
              (7, -10, "#8fb37c"), (-10, -4, "#567a4c"),
              (10, -5, "#3f5f3a"))
    for e0, e1 in ((hole[1], hole[2]), (hole[2], hole[3])):  # near edges
        for t in (0.34, 0.72):
            p = lerp(e0, e1, t)
            # tight to the rail: the walkway is only 40px deep here
            x, y = p[0], p[1] + 16
            d.ellipse([x - 7, y + 1, x + 7, y + 6],
                      fill=shade(FLOOR, 0.72))              # cast shadow
            # flared terracotta body, foot, lit rim
            d.polygon([(x - 5, y - 5), (x + 5, y - 5),
                       (x + 3, y + 2), (x - 3, y + 2)],
                      fill=hx("#8c5535"))
            d.polygon([(x - 5, y - 5), (x - 2, y - 5),
                       (x - 2, y + 2), (x - 3, y + 2)],
                      fill=hx("#a56a42"))                   # lit flank
            d.polygon([(x + 2, y - 5), (x + 5, y - 5),
                       (x + 3, y + 2), (x + 2, y + 2)],
                      fill=hx("#6d3f26"))                   # shade flank
            d.rectangle([x - 3, y + 2, x + 3, y + 3],
                        fill=hx("#5a331f"))                 # foot
            d.rectangle([x - 6, y - 8, x + 6, y - 5], fill=hx("#9c6038"))
            d.rectangle([x - 6, y - 8, x + 6, y - 7], fill=hx("#c08050"))
            d.rectangle([x + 4, y - 8, x + 6, y - 5], fill=hx("#7a4527"))
            d.rectangle([x - 4, y - 9, x + 4, y - 8], fill=hx("#2e2118"))
            # foliage: dark mass, then the frond fan out of the crown
            cy0 = y - 9
            d.ellipse([x - 6, cy0 - 8, x + 6, cy0 + 1],
                      fill=hx("#33502f"))
            for fx, fy, c in fronds:
                tip = (x + fx, cy0 + fy)
                bow = (x + round(fx * 0.45),
                       cy0 + round(fy * 0.55) - 3)
                d.line([(x, cy0), bow], fill=hx(c), width=1)
                d.line([bow, tip], fill=hx(c), width=1)
                d.point(tip, fill=hx("#a7c98f"))            # light tip


# ------------------------------------------------------- mauka walls
def door_at(d, e0, e1, t, kind, hw=17):
    """A doorway on a mauka wall's inner face.
    kind: koa (a WIDE single leaf, hw ~17 — chamber galleries,
    committee rooms) | office (a narrower single leaf, hw ~11 — the
    many ordinary legislative-office doors a wall this long really
    carries) | steel. Grand rooms used to get a PAIRED door, but a
    single wide leaf is what the building actually has (user,
    2026-08-24: "it shouldn't have the double doors, only the single
    ones") — width and hardware carry the grand-vs-ordinary read now,
    not leaf count.

    The office leaves follow the user's Capitol-corridor photo
    (2026-08-23, reference only, drawn from scratch). What that photo
    settled, against the old pass:
      - FLUSH slabs. The real office doors carry no recessed panel at
        all; the old raised-panel leaf read as a suburban front door.
      - a firm top-to-bottom falloff — the strongest value cue in the
        shot. Corridor light dies toward the floor: the leaf measures
        lum 63 at head height and 27 at the kick.
      - grain at very low contrast (R swung only 58-70 across a whole
        leaf, ±7%), so figure, never stripes.
      - a BLACK engraved nameplate two-thirds up, ~72% of the leaf
        wide. The single most identifiable thing on these doors.
      - a DULL lever, dark with a warm glint — not the brass pull.
        Brass stays on the grand leaf.
    """
    p = lerp(e0, e1, t)
    ex = (e1[0] - e0[0], e1[1] - e0[1])
    ln = math.hypot(*ex)
    ux, uy = ex[0] / ln, ex[1] / ln

    def pt(w, y=0):
        return (round(p[0] + ux * w), round(p[1] + uy * w - y))

    def quad(w0, w1, y0, y1, colq):
        d.polygon([pt(w0, y0), pt(w1, y0), pt(w1, y1), pt(w0, y1)],
                  fill=colq)

    def koa_leaf(w0, w1, y0, y1, seed):
        """A flush koa slab: separable grain(w) × falloff(y), painted
        as overlapping 1×2 cells so neither signal bands. Grain is
        seeded off the leaf's own position, so adding a door
        elsewhere on the wall never reshuffles its neighbours'
        figure."""
        g = np.random.default_rng(seed)
        ph = g.uniform(0, 2 * math.pi, 3)
        streaks = g.uniform(0.08, 0.92, int(g.integers(1, 3)))
        span, ht = w1 - w0, y1 - y0
        w = w0
        while w < w1:
            x = (w - w0) / span
            fg = 1.0 + sum(
                a * math.sin(2 * math.pi * fq * x + ph[i])
                for i, (a, fq) in enumerate(((.055, 0.9), (.030, 2.3),
                                             (.016, 5.1))))
            for s in streaks:                       # darker figure line
                if abs(x - s) < 0.035:
                    fg *= 0.88
            y = y0
            while y < y1:
                fy = 0.72 + 0.40 * ((y - y0) / ht) ** 0.7
                quad(w, min(w + 1.2, w1), y, min(y + 2.4, y1),
                     shade(KOA_DR, fg * fy))
                y += 2.0
            w += 1.0

    col = STEEL if kind == "steel" else KOA_DR
    # architrave frame, proud of the leaves, with a lit header
    quad(-hw - 3, hw + 3, 0, 49, KOA_DR_D)
    quad(-hw - 3, hw + 3, 48, 49, shade(KOA_DR, 0.86))
    if kind == "steel":
        quad(-hw, hw, 0, 46, col)
        d.line([pt(0, 1), pt(0, 45)], fill=shade(col, 0.72), width=2)
        d.ellipse([pt(hw, 38)[0] + 3, pt(hw, 38)[1],
                   pt(hw, 38)[0] + 7, pt(hw, 38)[1] + 4], fill=KEY)
    elif kind == "office":
        seed = (abs(int(p[0])) * 733 + abs(int(p[1])) * 97) % 99991
        koa_leaf(-hw, hw, 0, 46, seed)
        # reveals: dark hinge stile, the strike edge catching the well
        d.line([pt(-hw, 1), pt(-hw, 45)], fill=shade(KOA_DR, 0.50),
               width=1)
        d.line([pt(hw - 1, 1), pt(hw - 1, 45)], fill=KOA_DR_L, width=1)
        # the black nameplate, two-thirds up. To scale it is barely a
        # pixel tall (0.019 of the leaf); at 2 units it reads without
        # becoming the black bar the first pass drew. Lettering is
        # SHORT RUNS, dim — a solid bright line read as a second rail.
        pw = round(hw * 0.75)
        quad(-pw, pw, 29, 31, PLAQUE)
        for a, b in ((-pw + 1, -1), (1, pw - 2)):
            d.line([pt(a, 30), pt(b, 30)], fill=PLAQUE_TX, width=1)
        # dull lever on the strike side — dark, small, one warm glint
        d.line([pt(hw - 3, 21), pt(hw - 8, 21)], fill=hx("#332a20"),
               width=1)
        d.line([pt(hw - 3, 20), pt(hw - 3, 23)], fill=hx("#332a20"),
               width=1)
        d.point(pt(hw - 6, 21), fill=DULL)
        # the wall's card plate beside the jamb (in the photo by both)
        quad(hw + 5, hw + 7, 23, 27, hx("#8d8679"))
        d.line([pt(hw + 5, 23), pt(hw + 7, 23)], fill=hx("#4b463e"),
               width=1)
    else:
        # ONE wide leaf (2026-08-24, user: "it shouldn't have the
        # double doors, only the single ones") — width, the recessed
        # panel and brass hardware are what still tell a grand
        # doorway apart from an ordinary office one; leaf count no
        # longer does that job.
        koa_leaf(-hw, hw, 0, 46,
                 (abs(int(p[0])) * 41 + abs(int(p[1])) * 53 + 19)
                 % 99991)
        d.line([pt(-hw, 1), pt(-hw, 45)], fill=shade(col, 0.50),
               width=1)
        d.line([pt(hw - 1, 1), pt(hw - 1, 45)], fill=shade(col, 1.12),
               width=1)
        # single recessed panel, centred
        w0, w1 = -hw + 4, hw - 4
        quad(w0, w1, 9, 40, shade(col, 0.74))
        d.line([pt(w0, 40), pt(w1, 40)], fill=shade(col, 0.52), width=1)
        d.line([pt(w0, 9), pt(w1, 9)], fill=shade(col, 1.16), width=1)
        d.line([pt(w0, 9), pt(w0, 40)], fill=shade(col, 0.62), width=1)
        d.line([pt(w1, 9), pt(w1, 40)], fill=shade(col, 1.08), width=1)
        # brass pull, centred — grand rooms keep brass, offices get
        # the dull lever
        d.line([pt(0, 20), pt(0, 27)], fill=KEY, width=2)
        d.line([pt(0, 19), pt(0, 20)], fill=hx("#8a6420"), width=2)
        # kickplate
        quad(-hw, hw, 0, 5, shade(col, 0.62))
        d.line([pt(-hw, 5), pt(hw, 5)], fill=shade(col, 0.48), width=1)
    if kind == "office":
        # the photo has NO transom over the office doors: a dark head
        # jamb, one warm reveal under it. The grand doors keep the lit
        # transom, so the wall still reads grand-vs-ordinary.
        quad(-hw - 3, hw + 3, 49, 53, shade(KOA_DR, 0.44))
        d.line([pt(-hw - 3, 49), pt(hw + 3, 49)],
               fill=mix(KEY, KOA_DR, 0.55), width=1)
    else:
        quad(-hw - 3, hw + 3, 49, 53, mix(KEY, FASCIA, 0.4))
        d.line([pt(0, 49), pt(0, 53)], fill=hx("#b3a97f"), width=1)
    # threshold
    quad(-hw - 4, hw + 4, -3, -7, shade(FLOOR, 0.9))
    # faint reflection in the polished walkway tile
    d.polygon([pt(-hw + 2, -8), pt(hw - 2, -8),
               pt(hw - 4, -16), pt(-hw + 4, -16)],
              fill=mix(FLOOR, col, 0.20))
    return p


def corridor_at(d, e0, e1, t, f, elevator=False):
    """A HALLWAY portal in the wall — the offshoots that lead deeper
    into the building (the balconies are not a closed ring). A
    full-height opening with a fake one-point interior CLIPPED INSIDE
    the portal: receding floor darkening with depth, side walls
    converging on a dim far end (or, for a lift lobby, the steel
    doors), the far end nudged along the corridor's true iso
    direction. The first version spilled a sunlit floor wedge across
    the wall face and read as an alcove with a plank leaning in it
    (user-caught: "those alcoves look off — they're supposed to
    represent hallways")."""
    p = lerp(e0, e1, t)
    dx, dy = e1[0] - e0[0], e1[1] - e0[1]
    ln = math.hypot(dx, dy)
    ux, uy = dx / ln, dy / ln
    hw, ht = 16, 48
    # the corridor really runs perpendicular-INTO this iso wall, so
    # its far end sits offset along that direction, not dead centre
    ox, oy = round(uy * 5), round(-ux * 5)

    def pt(w, y=0.0):
        return (round(p[0] + ux * w), round(p[1] + uy * w - y))

    def fpt(w, y=0.0, k=1.0):
        q = pt(w, y)
        return (q[0] + round(ox * k), q[1] + round(oy * k))

    # architrave, same language as the doors, with a lit header
    d.polygon([pt(-hw - 3), pt(hw + 3), pt(hw + 3, ht + 4),
               pt(-hw - 3, ht + 4)], fill=shade(hx("#3b2a19"), f))
    d.polygon([pt(-hw - 3, ht + 3), pt(hw + 3, ht + 3),
               pt(hw + 3, ht + 4), pt(-hw - 3, ht + 4)],
              fill=shade(hx("#5c4326"), f))
    # the void
    d.polygon([pt(-hw), pt(hw), pt(hw, ht), pt(-hw, ht)],
              fill=shade(hx("#120e0b"), f))
    # far-end geometry
    fw = hw * (0.55 if elevator else 0.40)
    fy0, fy1 = (7, 38) if elevator else (10, 34)
    # receding floor, two bands darkening with depth
    d.polygon([pt(-hw), pt(hw), fpt(hw * 0.68, fy0 * 0.5, 0.5),
               fpt(-hw * 0.68, fy0 * 0.5, 0.5)],
              fill=shade(FLOOR, f * 0.86))
    d.polygon([fpt(-hw * 0.68, fy0 * 0.5, 0.5),
               fpt(hw * 0.68, fy0 * 0.5, 0.5),
               fpt(fw, fy0), fpt(-fw, fy0)],
              fill=shade(FLOOR, f * 0.62))
    # side walls converging on the far end (one lit, one in shadow) —
    # same concrete as the gallery walls outside
    d.polygon([pt(-hw), fpt(-fw, fy0), fpt(-fw, fy1), pt(-hw, ht)],
              fill=shade(CONC_D, f * 0.72))
    d.polygon([pt(hw), fpt(fw, fy0), fpt(fw, fy1), pt(hw, ht)],
              fill=shade(CONC_D, f * 0.50))
    # ceiling
    d.polygon([pt(-hw, ht), pt(hw, ht), fpt(fw, fy1), fpt(-fw, fy1)],
              fill=shade(hx("#0d0a08"), f))
    if elevator:
        # the lift lobby is shallow: the steel doors ARE the far end
        d.polygon([fpt(-fw, fy0), fpt(fw, fy0), fpt(fw, fy1),
                   fpt(-fw, fy1)], fill=shade(STEEL, f * 0.9))
        d.line([fpt(0, fy0 + 1), fpt(0, fy1 - 1)],
               fill=shade(STEEL, f * 0.6), width=1)
        d.line([fpt(-fw, fy0), fpt(fw, fy0)],
               fill=shade(STEEL, f * 0.65), width=1)
        q = fpt(0, fy1 + 3)
        d.rectangle([q[0] - 1, q[1] - 1, q[0] + 1, q[1] + 1], fill=KEY)
    else:
        # dim daylight from a window at the corridor's far end
        d.polygon([fpt(-fw, fy0), fpt(fw, fy0), fpt(fw, fy1),
                   fpt(-fw, fy1)], fill=shade(hx("#3f382e"), f))
        d.polygon([fpt(-fw * 0.4, fy0 + 6), fpt(fw * 0.4, fy0 + 6),
                   fpt(fw * 0.4, fy1 - 6), fpt(-fw * 0.4, fy1 - 6)],
                  fill=shade(hx("#6a5f4c"), f))
    # threshold + a dark smear of the opening in the polished tile
    d.polygon([pt(-hw - 4, -3), pt(hw + 4, -3), pt(hw + 4, -7),
               pt(-hw - 4, -7)], fill=shade(FLOOR, 0.9))
    d.polygon([pt(-hw + 2, -8), pt(hw - 2, -8), pt(hw - 4, -16),
               pt(-hw + 4, -16)], fill=mix(FLOOR, hx("#120e0b"), 0.18))
    return p


FEAT_HW = {"door": 20, "office": 14, "hall": 19, "lift": 19}

# THE TWO DOOR SCHEDULES, hoisted to module level (2026-08-25) so the
# column placer can thread its shafts between them. paint_walls and
# paint_upper_level draw from these and column_stations() reads them;
# a second copy would let a shaft "clear" a door that had since moved.
# Index 0 is the ʻEwa run, index 1 the Diamond Head run, matching the
# order both painters iterate in.
GALLERY_FEATS = (
    (("senate", 0.13, "door"), (None, 0.26, "office"),
     ("wam", 0.40, "door"), (None, 0.53, "office"),
     (None, 0.64, "office"), (None, 0.75, "office"),
     (None, 0.87, "office")),
    ((None, 0.07, "hall"), (None, 0.20, "office"),
     ("finance", 0.32, "door"), (None, 0.45, "office"),
     (None, 0.57, "office"), ("house", 0.70, "door"),
     (None, 0.82, "office"), ("gov", 0.94, "lift")),
)
UPPER_FEATS = (
    (("senpres", 0.22, "door"), (None, 0.37, "office"),
     (None, 0.49, "office"), (None, 0.63, "office"),
     (None, 0.75, "office"), (None, 0.87, "office")),
    ((None, 0.07, "hall"), (None, 0.20, "office"),
     (None, 0.32, "office"), ("senclerk", 0.44, "door"),
     (None, 0.58, "office"), (None, 0.71, "office"),
     (None, 0.84, "office"), (None, 0.95, "hall")),
)


def run_x(r, a, t):
    """Screen x of parameter t along a mauka run of half-size `a`.
    The column line, the gallery wall and the Senate wall sit on
    THREE different diamonds, so the same t is three different
    screen positions — comparing raw t between them (the obvious
    mistake) would clear a door that is nowhere near the shaft."""
    return CX + 32.0 * a * (t - 1 if r == 0 else t)


def bay_columns(d, e0, e1, f, feats, reflect=False):
    """Dark bronze columns between the bays — placed at the CORNERS
    and at the MIDPOINTS of the gaps between features, and only where
    they actually CLEAR the neighbouring frames (2026-08-24, user:
    "many of the columns in general are clipping into other
    elements"). The old fixed i/8 grid landed columns inside door
    architraves all along both walls — doors draw after columns, so
    every collision left a bronze sliver poking out of a frame. A
    column that cannot clear its gap is simply not drawn: on the
    door-dense gallery runs the koa leaves carry the rhythm alone."""
    span = abs(e1[0] - e0[0])
    ts = sorted(t for _, t, _ in feats)
    cand = [0.0, 1.0] + [(a + b) / 2 for a, b in zip(ts, ts[1:])]
    for t in cand:
        if any(abs(t - ft) * span < FEAT_HW[k] + 6 for _, ft, k in feats):
            continue
        b = lerp(e0, e1, t)
        d.rectangle([b[0] - 2, b[1] - 58, b[0] + 2, b[1] - 6],
                    fill=shade(hx("#241c15"), f))
        d.rectangle([b[0] - 2, b[1] - 58, b[0] - 1, b[1] - 6],
                    fill=shade(hx("#6b5c4a"), f))
        if reflect:
            # column reflection in the walkway tile
            d.line([(b[0], b[1] + 3), (b[0], b[1] + 9)],
                   fill=mix(FLOOR, hx("#241c15"), 0.45), width=2)


def paint_upper_level(d):
    """The third level — Senate offices — stepped BACK a full bay.

    Only the two MAUKA runs are drawn: a makai half would stand
    between the camera and the room, which is exactly what the
    dollhouse cut exists to prevent one storey down.

    Painted far-to-near within each run — wall, then the walkway that
    stands in front of it, then the rail at the walkway's inner edge.
    On the mauka side the OUTER ring is the far one, which is the
    opposite of the intuition that "outer" means "nearer".

    Deliberately carries no form mottle: it is the most distant thing
    in the room, where detail past value separation turns to noise,
    and skipping it keeps this off the shared `rng` so adding a level
    cannot reshuffle the level below's wall texture.
    """
    inn = diamond(LVL2_IN, LVL2_Y)
    out = diamond(LVL2_OUT, LVL2_Y)
    # ---- the SLICED ENDS first, or the upper floor floats.
    # Stepping back means the building carries mass between A_OUT and
    # LVL2_OUT — the offices BEHIND the lower wall — which nothing
    # ever drew, because one storey down that mass is hidden by the
    # wall itself. At the ʻEwa and Diamond Head corners the runs stop
    # and the hole shows: the upper level's outer half hung over bare
    # ink and read as a cantilever. Facing the slice with the same
    # core every other cut uses makes it a sawn-open building instead.
    g_in, g_out = diamond(A_OUT), diamond(LVL2_OUT)
    top = LVL2_Y + 72
    for i in (3, 1):
        c0, c1 = g_in[i], g_out[i]
        d.polygon([c0, c1, up(c1, top), up(c0, top)], fill=hx(CUT_CORE))
        for k, c in ((1, "#8e866f"), (2, "#a89f88")):    # aggregate
            t = k / 3.0
            d.line([lerp(c0, c1, t), lerp(up(c0, top), up(c1, top), t)],
                   fill=hx(c), width=1)
        # the floor PLATE, so the section reads as storeys stacked and
        # not as one solid pier
        for y in (LVL2_Y, LVL2_Y - 5):
            d.line([up(c0, y), up(c1, y)], fill=hx("#b9b096"), width=1)
        d.line([up(c0, LVL2_Y - 6), up(c1, LVL2_Y - 6)],
               fill=hx("#6f6957"), width=1)
        d.line([c0, up(c0, top)], fill=hx("#fffdf5"), width=2)  # arris
        d.line([c1, up(c1, top)], fill=hx("#6f6957"), width=1)
    doors = {}
    for i0, i1, feats, f in (
        # Both HALLWAY MOUTHS sit on the Diamond Head run (user,
        # 2026-08-24): one hard against the top point and one past the
        # rightmost door, so the recesses bracket the run instead of
        # punching a hole through the middle of it. Mid-wall portals
        # broke the door rhythm exactly where the eye travels.
        (3, 0, UPPER_FEATS[0], 1.10),
        (0, 1, UPPER_FEATS[1], 0.97),
    ):
        a0, a1 = inn[i0], inn[i1]
        e0, e1 = out[i0], out[i1]

        def q(y0, y1, col):
            d.polygon([up(e0, y0), up(e1, y0), up(e1, y1), up(e0, y1)],
                      fill=col)

        # ---- the wall (far)
        q(0, 8, shade(POST, f))
        q(8, 58, shade(CONC, f))
        for y in (24, 41):
            d.line([up(e0, y), up(e1, y)],
                   fill=shade(CONC, f * 0.90), width=1)
        bay_columns(d, e0, e1, f, feats)
        for did, t, kind in feats:
            if kind == "door":
                pos = door_at(d, e0, e1, t, "koa")
            elif kind == "office":
                pos = door_at(d, e0, e1, t, "office", hw=11)
            else:
                pos = corridor_at(d, e0, e1, t, f)
            if did:
                doors[did] = pos
        q(58, 72, shade(hx("#ece6d4"), f))
        for b in even_run(e0, e1, FLUTE_PITCH):
            d.line([up(b, 59), up(b, 71)],
                   fill=shade(hx("#9d9683"), f), width=2)

        # ---- the walkway, standing in front of the wall
        d.polygon([a0, a1, e1, e0], fill=shade(FLOOR, f * 0.94))
        d.line([a0, a1], fill=shade(FLOOR_SH, f), width=1)

        # ---- the rail at its inner edge (nearest, so last): a SOLID
        # white fluted PARAPET with the koa cap on top — NO pickets
        # (2026-08-24, user: "the pickets for the railings are
        # showing over the white, which is incorrect"). Open pickets
        # cannot work up here: the terrace strip behind the rail
        # thins to nothing toward the ʻEwa/Diamond Head ends (an iso
        # diamond offset outward moves edges up-screen only near the
        # apex), so the dark bars stood against the pale wall base
        # and the white slab band and read as pickets painted OVER
        # the white. The executive-floor photo's upper balconies are
        # white fluted parapets anyway — the koa cap riding the TOP
        # of the white band is what says "railing" at this distance.
        d.polygon([a0, a1, up(a1, RAIL_H), up(a0, RAIL_H)],
                  fill=shade(hx("#ece6d4"), f))
        for b in even_run(a0, a1, FLUTE_PITCH):
            d.line([up(b, 2), up(b, RAIL_H - 2)],
                   fill=shade(hx("#9d9683"), f), width=2)
        # seam at the slab line, so the parapet stands ON the floor
        # instead of merging with the fascia band below
        d.line([a0, a1], fill=shade(hx("#8a8474"), f), width=1)
        d.line([up(a0, RAIL_H), up(a1, RAIL_H)],
               fill=shade(hx("#f7f3e6"), f), width=1)
        d.line([up(a0, RAIL_H + 1), up(a1, RAIL_H + 1)],
               fill=shade(hx("#54391f"), f), width=2)
        d.line([up(a0, RAIL_H + 3), up(a1, RAIL_H + 3)],
               fill=shade(hx("#9a6a38"), f), width=3)
        d.line([up(a0, RAIL_H + 5), up(a1, RAIL_H + 5)],
               fill=shade(hx("#c79a5c"), f), width=2)
        d.line([up(a0, RAIL_H + 6), up(a1, RAIL_H + 6)],
               fill=shade(hx("#ecd0a1"), f), width=1)
    return doors


def paint_walls(d):
    """The GALLERY level — the bays, the doors, the hallway offshoots,
    then the slab fascia above and the dollhouse cut. The floor above
    is paint_upper_level(), drawn first because it is further back."""
    out = diamond(A_OUT)                     # N, E, S, W
    doors = {}
    # DENSE door schedule (user: "in reality there would be many more
    # doors — the space is quite large"): the named doorways keep
    # their hotspots, and narrow single-leaf office doors fill the
    # runs between them. Spacing floor: chamber doors are 40px of
    # frame, offices 28, portals 38 — keep centres ≥ 0.10 t apart or
    # the frames touch. One gap per wall is left for the bench.
    #
    # PORTALS SIT AT THE ENDS OF THE DIAMOND HEAD RUN — THE SAME
    # PLACEMENT AS THE STOREY ABOVE (user, 2026-08-24: "I wanted the
    # hallways on second floor to be same as third floor"). One hard
    # against the top point, one past the rightmost door, so the two
    # recesses BRACKET the run; the ʻEwa run is all doors, exactly as
    # in paint_upper_level. Before this the ʻEwa hall sat at 0.45 and
    # a lift at 0.47, punching holes through the door rhythm right
    # where the eye travels the wall. `gov` is the lift lobby that
    # closes the run — a named hotspot, so it moved runs with it.
    for e0, e1, feats, f in (
        (out[3], out[0], GALLERY_FEATS[0], 1.0),
        (out[0], out[1], GALLERY_FEATS[1], 0.88),
    ):
        def q(y0, y1, col):
            d.polygon([up(e0, y0), up(e1, y0), up(e1, y1), up(e0, y1)],
                      fill=col)
        q(0, 8, shade(POST, f))                       # base strip
        q(8, 58, shade(CONC, f))                      # concrete bays
        # concrete reads as POUR JOINTS + form mottle, not brick
        # courses (user-corrected: "the texture of the walls is more
        # concrete-like")
        for y in (24, 41):
            d.line([up(e0, y), up(e1, y)],
                   fill=shade(CONC, f * 0.90), width=1)
        for _ in range(10):
            b = lerp(e0, e1, rng.uniform(0.03, 0.97))
            mw = int(rng.uniform(5, 14))
            my0 = int(rng.uniform(12, 44))
            d.rectangle([b[0] - mw // 2, b[1] - my0 - int(rng.integers(4, 9)),
                         b[0] + mw // 2, b[1] - my0],
                        fill=shade(CONC, f * rng.uniform(0.94, 1.06)))
        # dark bronze columns between the bays (clearance-placed —
        # see bay_columns)
        bay_columns(d, e0, e1, f, feats, reflect=True)
        # doors, hallway portals, elevator lobbies
        for did, t, kind in feats:
            if kind == "door":
                pos = door_at(d, e0, e1, t, "koa")
            elif kind == "office":
                pos = door_at(d, e0, e1, t, "office", hw=11)
            else:
                pos = corridor_at(d, e0, e1, t, f,
                                  elevator=(kind == "lift"))
            if did:
                doors[did] = pos
        # the slab above, fluted. NO white top-face strip on it any
        # more (2026-08-24, "the white strips for third floor railings
        # are completely wrong"): the old dollhouse top-face polygon —
        # up(e, 72) offset (±9, -5) — was written for a wall with sky
        # behind it, and once the third level stood there its slanted
        # parallelogram covered ~10px ABOVE the slab line, painting
        # white over the upper rail's kerb and the bottom half of its
        # pickets. The rail read as a gold pinstripe in a white belt
        # (measured on the staged bake: the picket band went #efeadb
        # after paint_walls ran). The terrace floor drawn by
        # paint_upper_level is what meets the slab line now.
        q(58, 72, shade(hx("#ece6d4"), f))
        for b in even_run(e0, e1, FLUTE_PITCH):
            d.line([up(b, 59), up(b, 71)],
                   fill=shade(hx("#9d9683"), f), width=2)
        # NO benches: drawn floating mid-walkway they read as brown
        # bars sitting on the railing (user-caught, removed 2026-08-22)
    return doors


# ------------------------------------------- makai edge + exit stairs
def cut_face(d, a0, a1, off, arris=True):
    """One sliced surface: the wall's core between the run `a0..a1` and
    the same run pushed out by the wall's thickness. Shared by the
    makai stubs and by the mauka walls' sawn-off ends at the corners,
    so every cut in the room is the same material."""
    b0 = (a0[0] + off[0], a0[1] + off[1])
    b1 = (a1[0] + off[0], a1[1] + off[1])
    d.polygon([a0, a1, b1, b0], fill=hx(CUT_CORE))
    for k, c in ((1, "#8e866f"), (2, "#a89f88")):     # aggregate grain
        o = (off[0] * k / 3.0, off[1] * k / 3.0)
        d.line([(a0[0] + o[0], a0[1] + o[1]), (a1[0] + o[0], a1[1] + o[1])],
               fill=hx(c), width=1)
    if arris:
        d.line([a0, a1], fill=hx("#fffdf5"), width=2)
    d.line([b0, b1], fill=hx("#6f6957"), width=1)


def paint_cut_ends(d):
    """The mauka walls are SAWN OFF at the ʻEwa and Diamond Head
    corners — full height on one side of the line, knee height on the
    other. Facing the slice with the same core the stubs use is what
    makes the room read as a cutaway of a real building rather than as
    a set with two walls missing."""
    out = diamond(A_OUT)
    for c, moff in ((out[3], (-9, -5)), (out[1], (9, -5))):
        cut_face(d, c, up(c, 72), moff, arris=False)
        d.line([up(c, 72), (c[0] + moff[0], c[1] + moff[1] - 72)],
               fill=hx("#fffdf5"), width=2)


def paint_front_edge(d):
    """The makai edge is JUST THE WALKWAY now (2026-08-24, user:
    "don't need the walls, just showing the walkway is fine") — the
    knee-high cutaway stub walls were removed. The floor ends at the
    slab edge with its own fluted fascia hanging below, exactly the
    band the well edges wear, and nothing stands on it."""
    out = diamond(A_OUT)
    gap = 30
    for e0, e1 in ((out[1], out[2]), (out[2], out[3])):   # SE, SW
        # fascia broken at the S corner for the stairs
        span = 32.0 * A_OUT   # edge's horizontal extent, px
        if e1 is out[2]:      # SE runs E->S: stop short of S
            e1 = lerp(e0, e1, 1 - gap / span)
        else:                 # SW runs S->W: start past S
            e0 = lerp(e0, e1, gap / span)
        fluted_band(d, e0, e1, 0, FASCIA_D, 0.92)
    # stairs down from the S corner, out of the room
    s = out[2]
    for i in range(5):
        y = s[1] + STUB_H + i * 8
        wdt = 40 - i * 2
        d.polygon([(s[0] - wdt, y), (s[0] + wdt, y),
                   (s[0] + wdt - 4, y + 6), (s[0] - wdt + 4, y + 6)],
                  fill=shade(hx("#cbc3ae"), 0.95 - i * 0.13))
    # cheek walls flanking the run, landing at the foot
    for sgn in (-1, 1):
        d.polygon([(s[0] + sgn * 40, s[1] + STUB_H),
                   (s[0] + sgn * 30, s[1] + STUB_H + 44),
                   (s[0] + sgn * 30, s[1] + STUB_H + 52),
                   (s[0] + sgn * 44, s[1] + STUB_H + 4)],
                  fill=shade(hx("#b5ad98"), 0.9))
    d.polygon([(s[0] - 32, s[1] + STUB_H + 44),
               (s[0] + 32, s[1] + STUB_H + 44),
               (s[0] + 24, s[1] + STUB_H + 56),
               (s[0] - 24, s[1] + STUB_H + 56)],
              fill=shade(hx("#8f8a7a"), 0.85))


def paint_planters(d):
    """Raised TAN STONE planter boxes at the ʻEwa and Diamond Head
    corners of the walkway. The third one at the N apex was removed
    (user: "the central potted plant should be removed") — wedged at
    the corner between the two walls it read as clutter."""
    stone = hx("#c9b88f")
    for u, v in ((10.25, -10.25), (-10.25, 10.25)):
        x, y = iso(u, v)
        d.polygon([(x - 16, y), (x, y - 8), (x + 16, y), (x, y + 8)],
                  fill=stone)
        d.polygon([(x - 16, y), (x, y + 8), (x, y + 13), (x - 16, y + 5)],
                  fill=shade(stone, 0.78))
        d.polygon([(x + 16, y), (x, y + 8), (x, y + 13), (x + 16, y + 5)],
                  fill=shade(stone, 0.62))
        d.polygon([(x - 10, y), (x, y - 5), (x + 10, y), (x, y + 5)],
                  fill=hx("#567a4c"))
        d.polygon([(x - 6, y - 1), (x, y - 4), (x + 5, y - 1), (x, y + 2)],
                  fill=hx("#6f9660"))
        # broken canopy: shade pocket + leaf ticks, so it reads as
        # foliage instead of two flat diamonds
        d.polygon([(x - 8, y + 1), (x - 3, y - 1), (x - 1, y + 3),
                   (x - 6, y + 4)], fill=hx("#4a6a42"))
        for lx, ly in ((-7, -1), (-2, -3), (3, -2), (6, 1), (0, 2),
                       (-4, 3)):
            d.line([(x + lx, y + ly), (x + lx + 2, y + ly - 2)],
                   fill=hx("#8fb37c"), width=1)


# ------------------------------------------------------------- finish
def painterly(img):
    """Oil-paint facets + the map grade. NO vignette (house rule)."""
    import cv2
    rgb = np.asarray(img.convert("RGB"), np.uint8)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    painted = cv2.xphoto.oilPainting(bgr, 4, 1)
    painted = cv2.cvtColor(painted, cv2.COLOR_BGR2RGB).astype(np.float32)
    out = rgb.astype(np.float32) * 0.34 + painted * 0.66
    lum = (out[..., 0] * 0.299 + out[..., 1] * 0.587 +
           out[..., 2] * 0.114)[..., None]
    out = lum + (out - lum) * 1.12
    out = 255.0 * np.clip(out / 255.0, 0, 1) ** 0.97
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- main
def render(raw=False):
    img = Image.new("RGBA", (W, H), INK + (255,))
    d = ImageDraw.Draw(img)

    paint_ground(d)
    img = mottle_ink(img.convert("RGB")).convert("RGBA")
    d = ImageDraw.Draw(img)

    paint_ring_floor(d)
    paint_sun(img)
    paint_ring_shade(img)
    d = ImageDraw.Draw(img)
    paint_well(img)
    d = ImageDraw.Draw(img)
    paint_railings(d)
    paint_rail_pots(d)
    upper = paint_upper_level(d)          # furthest: before the walls
    doors = paint_walls(d)
    doors.update(upper)
    # THE COLUMNS, upper half — gallery floor to the top of the third
    # storey. After the walls and the upper level, because a shaft on
    # the court edge stands in front of both; the half below the
    # gallery went in with paint_well, where the hole mask trims it.
    # starts ABOVE the gallery parapet's koa cap: the balustrade
    # stands on the same A_IN line as the shaft, so it is the one
    # thing at this level genuinely in FRONT of it. The photo's
    # strips show exactly this — a shaft passing behind each balcony
    # and emerging between them. Everything higher (the Senate level)
    # is recessed to A_OUT and therefore BEHIND the shaft, so it
    # needs no such break.
    for b, cf in column_stations():
        court_column(d, b, RAIL_H + 7, COL_DY1, cf)
    # planters AFTER walls: the W/E corner planters sit in front of
    # the corner-most doors' floor reflections and must occlude them
    paint_planters(d)
    paint_front_edge(d)
    paint_cut_ends(d)

    img = img.convert("RGB")
    if not raw:
        img = painterly(img)
    img = img.resize((W // SS, H // SS), Image.LANCZOS)   # see SS
    img.save(OUT_PNG)
    # the runtime paints this behind the image (letterbox bars at odd
    # aspect ratios) — sample the finished surround so they can never
    # disagree, same one-source rule as `deep` in the island bakes
    bg = "#%02x%02x%02x" % img.getpixel((2, img.height // 2))

    # ---- hotspots, computed from the same geometry
    out = diamond(A_OUT)
    dpx = {k: (int(p[0]), int(p[1])) for k, p in doors.items()}
    meta = {
        "name": "Hawaiʻi State Capitol",
        "image": "capitol_scene.png",
        "w": W, "h": H, "scale": SS, "bg": bg,
        "spawn": [CX, int(out[2][1]) - 60],
        "hotspots": [
            dict(id="senate", name="Senate Gallery", kind="door",
                 px=dpx["senate"][0], py=dpx["senate"][1] + 6,
                 text="The ʻEwa cone, below this door: Hawaiʻi's 25 "
                      "senators under the Moon — a chandelier of 620 "
                      "chambered nautilus shells. The public watches "
                      "from up here, at the rail."),
            dict(id="house", name="House Gallery", kind="door",
                 px=dpx["house"][0], py=dpx["house"][1] + 6,
                 text="The Diamond Head cone: the 51 representatives "
                      "under the Sun, a chandelier of gold-plated "
                      "globes. Every state law begins as a bill read "
                      "in one of the two cones below."),
            dict(id="wam", name="Ways & Means", kind="door",
                 px=dpx["wam"][0], py=dpx["wam"][1] + 6,
                 text="The Senate's money committee. A revenue bill "
                      "that cannot clear Ways & Means goes no "
                      "further."),
            dict(id="finance", name="House Finance", kind="door",
                 px=dpx["finance"][0], py=dpx["finance"][1] + 6,
                 text="The House's money committee — every "
                      "appropriation in the state budget passes "
                      "across these tables."),
            dict(id="gov", name="Governor · Level 5", kind="door",
                 px=dpx["gov"][0], py=dpx["gov"][1] + 6,
                 text="The elevator to Level 5, where the Governor "
                      "and Lieutenant Governor look down into the "
                      "rotunda. The veto pen lives up there."),
            dict(id="senpres", name="Senate President", kind="door",
                 px=dpx["senpres"][0], py=dpx["senpres"][1] + 6,
                 text="Third level, and this floor is the Senate's. "
                      "Referrals are settled behind this door — which "
                      "committees a measure must clear before it can "
                      "reach the floor, and so how many ways it can "
                      "quietly die."),
            dict(id="senclerk", name="Senate Clerk", kind="door",
                 px=dpx["senclerk"][0], py=dpx["senclerk"][1] + 6,
                 text="Every measure is filed, numbered and journaled "
                      "here. What the chamber did is whatever this "
                      "office wrote down — the journal is the record, "
                      "not anyone's memory of the vote."),
            dict(id="mosaic", name="Aquarius", kind="poi",
                 px=CX, py=CY + DROP + 6,
                 text="The floor medallion below marks where Tadashi "
                      "Sato's sea-stone mosaic lies. Look up instead: "
                      "no dome — the rotunda "
                      "opens to the sky. The sky is Hawaiʻi's capitol "
                      "dome, and rain and rainbows come inside."),
            dict(id="exit", name="Back to Oʻahu", kind="exit",
                 px=CX, py=int(out[2][1]) + 66,
                 text=""),
        ],
    }
    OUT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print("wrote", OUT_PNG.name, f"{img.width}x{img.height}"
          f" (scene {W}x{H} @ {SS}x)", "and", OUT_JSON.name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--painterly", action="store_true",
                    help="apply the oil-paint finish (NOT the default: "
                         "measured 2026-08-22, radius 4 smears the "
                         "railing pickets into uneven blobs — the pass "
                         "is tuned for terrain, not architecture)")
    render(raw=not ap.parse_args().painterly)
