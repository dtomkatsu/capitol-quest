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
photos, a user-supplied courtyard view from the rotunda floor
(2026-08-25 — the column count: a corner column and two to a side),
plus a user-supplied gallery-corner atrium photo (2026-08-22)
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
# SS 2 -> 1 (2026-08-27). The supersample was right for the framing it
# was written against and wrong for the one we have now.
#
# The 2026-08-24 rationale: the room was only ever SEEN at half the
# scene space, because fit() SNAPPED to zoom 0.5 and the renderer
# point-sampled, throwing away every other row and column. Measured on
# a rail crop, 83 unique colours reached the canvas where the source
# has 87 and a resample gives 376 — that decimation is what read as
# jagged railings, since the picket run is 1px lines on a 2px pitch
# and WHICH half survived drifted as the diagonal advanced. Baking the
# AA once with a real filter fixed it: zoom 0.5 x scale 2 is an exact
# 1:1 blit.
#
# Two days later the Capitol became the game's main view and got a
# `view` rect with CONTINUOUS zoom and a LINEAR-filtered texture
# (main.js fit()). There is no 0.5 snap on this room any more and
# nothing point-samples it, so the premise is gone — and the cost is
# not: at the old 0.9 cap the 840x620 PNG was already being blown up
# 1.8x, i.e. the bake was discarding exactly the resolution the new
# framing wants. Shipping the full 1680x1240 authored space instead
# lets the cap go to 1.6, which fills a 1080p window with real pixels.
#
# What this does NOT do is raise the AUTHORED resolution: every
# painter below is written in scene px with hardcoded literals (frame
# insets, 1px flute lines, FEAT_HW), so doubling the drawing means
# rewriting all of them. 1680x1240 is what the art actually contains;
# this just stops throwing half of it away.
#
# Downscale (small windows) is now the runtime's job rather than
# LANCZOS's. That is the trade: a phone at zoom ~0.35 gets a Canvas2D
# bilinear reduction of full-res art where it used to get a clean
# blit of half-res art. Acceptable because the phone framing is
# already the weak case for other reasons (see CLAUDE.md), and the
# desktop main view is what this bake is for.
#
# The JSON has always kept SCENE coordinates (w/h/spawn/hotspots) and
# still does — only `scale` changes, from 2 to 1.
SS = 1
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
# ---- THE ELONGATED PLAN (2026-08-26, two user calls: "extend the
# right side of the second and third floors so that they are more
# rectangular", then the correction that settled it — "i wanted the
# railing to also reflect this new length. it's still in the same
# square"; a first cut extended only the walls and was wrong). The
# whole room is a RECTANGLE, WING_EXT iso units longer in u than in
# v: rdiamond() is diamond()'s elongated counterpart and everything
# derived from the well reads it — ring floor, ring shade, sun
# spill, both railing rings, courtyard paving/light/loggia bands,
# slab fins, makai fascia. The upper walls run on past the old E
# corner (the wing blocks in paint_walls / paint_upper_level),
# closed by the sliced-end treatment translated +WING_EXT. Rules:
#   - The PLAY AREA IS UNTOUCHED: place_feats never sees the wing,
#     so every hotspot keeps its pixel position (json verified
#     byte-identical); the extensions carry only UNNAMED filler (an
#     office door and a bench per level), placed on their own local
#     span. Never put a named feature here.
#   - ROTUNDA-CENTRED furniture stays in absolute u/v (mosaic, chain
#     ring, planter benches, breezeway band, the ʻEwa corner
#     assembly): the rotunda is where it is — the COURT got longer.
#   - column_stations() keeps the ORIGINAL square (must land on
#     col_xs' x), plus ONE loggia-only extension station.
#   - court_glass takes the ORIGINAL run + `ext`: the drum's curtain
#     continues past its apex with mirrored physics, one sheet.
#   - Flute phase is CONTINUOUS across the junction: wing flute runs
#     step even_run from the ORIGINAL run's start and draw only the
#     wing's span, so the 6px rhythm cannot beat at the seam.
#   - Wing form mottle uses a LOCAL generator (same rule as
#     court_paving): the shared rng's sequence textures the mosaic
#     and both walls' mottle, and the wing must not reshuffle them.
WING_EXT = 8.0
RAIL_H = 15                # picket run height
PICKET_PITCH = 6           # px between pickets — EVEN, see even_run().
PICKET_W = 2               # judged on the DOWNSCALED bake: at SS 2 a
                           # 1px picket is half a display pixel and
                           # LANCZOS renders the run as grey haze.
FLUTE_PITCH = 6            # the white fluted bands, same rule
FLUTE_FIELD = "#ece6d4"    # the band's lit face
# THE GROOVE IS A SHADOW GAP, NOT A TINT (2026-08-27, user: "inspect
# the railing/fence. it's all white. dont you see it"). It shipped at
# #9d9683 — lum 150 against the band's 230, a ratio of 0.65 — which is
# a light-grey pinstripe on near-white, i.e. no visible spokes at all.
# The well railing that DOES read as a railing runs its pickets at lum
# 52-68, and that gap is the whole difference: one reads as a fence,
# the other as white trim. #45423a is lum 66, so every railing in the
# room now speaks the same language.
#
# JUDGE THIS ON THE GAME CANVAS, NEVER ON THE SOURCE PNG AT 1:1. The
# runtime resamples the bake at zoom ~1.047 through a LINEAR filter,
# which blends a 2px groove with its white neighbours; measured off
# the live canvas the shipped groove came back as [174,150,198,230,
# 230,230] — present in the data, invisible on screen. A 1:1 crop of
# the bake hides exactly that, and reading one is what made an earlier
# pass call this fixed when it was not.
FLUTE_GROOVE = "#45423a"   # the shadow gap between two flutes
# Width 2 on FLUTE_PITCH 6 — a DARK GAP with a 4px white fin, not a
# 50/50 bar. 3px was swept and reads as a balustrade too, but it turns
# half of every band dark and the fascia stops reading as white trim.
FLUTE_W = 2


def white_f(f):
    """A face factor for a NEAR-WHITE member, capped at 1.0.

    `shade()` clamps at 255, and the fluted band's field (#ece6d4,
    lum 230) has almost no headroom left. The third level's ʻEwa run
    carries f = 1.10, which lands the field on 253 and the highlight
    line (#f7f3e6) on 268 — so both clamp to the SAME flat white and
    the assembly loses its top highlight, its base seam and most of
    its flute contrast in one go. Measured on the shipped bake before
    this: fourteen identical rows straight through the band at
    x = 700, against the Diamond Head run's field 222 / groove 145.
    Two halves of one railing rendering as two different objects is
    what the user was seeing (2026-08-27: "the white trim for third
    floor railing looks off. you cant even see the spokes, it's all
    white") — the ʻEwa half really was a blank white ribbon.

    On a material already at the top of the range, LIGHT DIRECTION
    HAS TO BE CARRIED BY SOMETHING THAT IS NOT VALUE — here the koa
    cap (dark, plenty of headroom, and still shaded by the full `f`)
    and the grooves. Pushing the field past the ceiling does not
    make it brighter, it makes it flatter.

    Darkening the base white instead is the wrong fix: the band's
    230 is measured against the court floor (the executive-floor
    photo puts the white band at 1.79x the open paving, which is
    what sets COURT at 130), so it has to survive."""
    return min(f, 1.0)
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
# THE COLUMNS RUN THE WHOLE HEIGHT, BUT THEY ONLY STAND FREE ON THE
# GROUND FLOOR — ON THE SECOND AND THIRD THEY ARE FLUSH IN THE WALL
# (user, 2026-08-25: "you're misreading the columns. they should be
# flush with the walls on the second and third floors"). The
# executive-floor photograph is unambiguous once you follow ONE stack
# down: a tapered shaft standing free in the loggia, then above each
# balcony a pale strip lying IN the wall face between the doors, with
# the walkway and its parapet crossing in front of it. The ground
# storey is the only one whose wall is set back far enough for the
# column to come out of it.
#
# Two earlier readings are now both retired. The first broke the
# shaft at every parapet (a shaft passing behind each balcony); the
# second ran it unbroken up the COURT EDGE, which put a free-standing
# pole in front of both upper balconies — nine of them, standing
# between the camera and the room like a fence. Flush is the third
# reading and it is the photograph's.
#
# What survives from the second is the ALIGNMENT: the flush strip on
# each upper wall is drawn at the SAME SCREEN X as the shaft below
# it, so the eye still reads one column from the rotunda floor to the
# top. It is a cheat — the walls really do stand a walkway further
# back, and a true projection would step the strip 20 display px
# sideways per storey — but the storey's own floor and slab fix the
# strip's vertical extent, so screen x is the only thing tying the
# pieces together and it is the one that has to be honest.
COL_DY0, COL_DY1 = -DROP, LVL2_Y + 72     # foot / head, world height
# Half-width at foot / head. The RATIO is what has to survive the SS
# downsample — at display scale the shaft is only ~6px at the foot,
# so a photo-true ~1.5 taper rounds away to a straight post. 1.75 is
# the exaggeration that still reads as one continuous flare.
COL_HW0, COL_HW1 = 6.0, 14.0
COL_FLARE = 1.0            # LINEAR, and measured: a power curve was
                           # tried first to concentrate the swell at
                           # the head, and it cannot work here. A
                           # column is only ever seen in SHORT
                           # STRETCHES — the loggia, then the band of
                           # each upper wall between one balcony's
                           # cap and the slab above — and an exponent
                           # that flares one flattens the others.
                           # Straight batter gives every stretch
                           # about 1.4, which is what the photo shows
                           # per storey. The full-height 6->14 ratio
                           # is not what the eye gets; the
                           # per-stretch ratio is.
# THE COLUMNS COME FIRST AND THE DOORS FILL THE BAYS BETWEEN THEM.
# That dependency used to run the other way — stations were nudged
# along the run until they cleared the named doorways — and it cannot
# survive the columns being flush: a free-standing shaft may pass in
# front of a door honestly, a strip lying IN the wall may not, and a
# collision is a pale sliver poking out either side of a frame (the
# 2026-08-24 "clipping into other elements" complaint). Measured
# before the rewrite: with both schedules where they were, a strip of
# any width had ZERO clear positions on the Diamond Head run and one
# 12px window on the ʻEwa run. So each run is divided into bays by
# its own columns, and place_feats() lays that wall's doors out
# inside them.
# COUNT: A CORNER COLUMN, AND TWO TO A SIDE (user, 2026-08-25, with
# a courtyard photograph: "look at how there's corner columns, but
# then aside from that it's two columns to a side"). Three per run
# read as a picket fence; the corner one is what makes the fold
# structural, and it is FREE — the mauka apex is the one place every
# diamond shares a screen x (x = 16(u - v) = 0 when u == v), so the
# same column lands at CX on the court edge and on both walls, and
# each run draws its own half of it against its own slope.
#
# The ʻEwa and Diamond Head corners get no column: a vertical line at
# the well diamond's W or E point meets the hole at exactly ONE pixel,
# so paint_well's mask eats any shaft standing there. Those two ends
# are the dollhouse cut anyway — a sawn face, not a fold.
COL_T = (1 / 3.0, 2 / 3.0)  # the interior pair; the apex is added per run
# THE CORNER COLUMN STANDS ON THE WALL CORNER, NOT THE COURT EDGE
# (user, 2026-08-25: "the central column should be further back. the
# top point of the graphic, next to the hallway, is where a little
# alcove is. the column goes up through there"). Measured off the
# executive-floor photograph: the corner strip's foot sits at y=250.5
# where the two wall faces' intersection extrapolates to y=251.0 and
# 251.3 from the left and right runs — one full walkway width behind
# the railing, and plumb under the strips on the floors above. The
# mid-run ground columns are NOT affected: those really are
# free-standing in the loggia with the koa wall a bay behind them.
#
# It costs nothing in screen x. u == v at the apex, so x = 16(u - v)
# is CX on every diamond — the shaft still lines up with the flush
# strips above. It moves UP 16*(GND_OUT - A_IN) = 38 scene px, and
# paint_well's hole mask then trims its top 38 px, so it emerges from
# under our own slab already deep in the corner. That is the whole
# effect and it is free.
COL_APEX_U = GND_OUT

# THE FLUSH COLUMN'S SURFACE, as bands across its width. `u` runs -1
# at the left arris to +1 at the right, as a FRACTION of the
# half-width, so every band tapers with the shaft. Each band carries
# a colour at the storey's FOOT and at its HEAD and is drawn as a
# vertical gradient between them; bands paint in order, so a later
# one may overlay an earlier.
#
# THE RESOLUTION CEILING IS THE WHOLE DESIGN PROBLEM. The strip is
# ~19 scene px wide on the second floor and ~27 on the third, and the
# bake is LANCZOS-downsampled 2x, so that is 9 and 13 DISPLAY px —
# four or five distinguishable bands at the very most, and anything
# under ~2 scene px is mush. Judge any change to this on the
# DOWNSCALED bake, never at 1:1.
# It shipped as ONE flat fill and the user's verdict was exact: "the
# columns appear to lose their shape as they get higher. they look
# less like 3d objects, more like splotches." Measured, it was 13
# identical pixels — self-contrast under 1% — at 0.86 of the white
# slab band, where the photographs put a flush column at 0.48.
#
# What replaced it is the profile the photographs actually carry, and
# it is a TWO-FACET STEP, not a smooth cylinder: a narrow reveal, a
# ramp, a WIDE nearly-flat lit facet (~60% of the width), ONE hard
# arris, a shadow facet at ~0.6 of the lit one, and a keyline DARKER
# THAN THE WALL. Three rules that came out of the measuring and must
# not be undone:
#   - NO pixel at either outer edge is brighter than the body. Not
#     one, in either photograph, on any of eight columns sampled. The
#     old 1px #ddd6c0 arris was brighter than everything in both
#     photographs, and a bright edge is a projecting-object cue.
#   - The keyline must be darker than the WALL (#3a3732 is 0.78 of
#     CONC), not merely darker than the column. A midtone edge is
#     what makes a strip look pasted ON a surface instead of cut
#     INTO it.
#   - The shadow facet must NOT be floored to the wall: measured, a
#     real flush column's darkest sample is 1.5x its wall (#6a655a
#     is 1.44x CONC). Darker than that and the column loses a
#     quarter of its width into the concrete.
# The strip is FLAT up its height (the photographs are flat to 3-8%);
# the 5% head droop is the whole vertical variation there should be.
"""Facet palette de-yellowed 2026-08-27 with court_column's (the
breezeway photo, "same with the columns"): same values, r-b warmth
halved, so the flush strip stays the same concrete as the free shaft
it continues."""
COL_FACETS = (
    (-1.00, -0.84, "#706d64", "#6b685f"),   # lit-side reveal
    (-0.84, -0.66, "#999488", "#918d81"),   # ramp in
    (-0.66,  0.10, "#aeaa9c", "#a5a194"),   # the lit facet
    ( 0.10,  0.24, "#a7a396", "#9f9b8f"),   # its inner droop
    ( 0.24,  0.40, "#87847a", "#807d74"),   # the arris: ONE hard step
    ( 0.40,  0.84, "#68655d", "#636159"),   # the shadow facet
    ( 0.84,  1.00, "#3a3834", "#373532"),   # keyline, darker than wall
)
COL_EDGE_L = ("#706d64", 1)     # matches the reveal — never brighter
COL_EDGE_R = ("#3a3834", 2)     # the recessed joint
# Optional CAPITAL: (height in px, half-width multiplier at the very
# top, soffit-shadow colour or None). The real columns trumpet out
# where they meet the slab; whether that survives at 4 display px of
# height is a question for the bake, not for taste.
COL_CAP = (0, 1.0, None)
# THE STRIP GETS DARKER AS IT RISES, and this is measured, not mood.
# Against the white slab band as a common white, the photographs put
# the flush column's lit face at 0.67 of white on the second floor
# and 0.48 on the third, while the WALL beside it gets lighter with
# height (0.19 -> 0.23). The bake was doing the exact opposite: the
# third-floor run carries f = 1.10, so the topmost strip was the
# widest AND the palest thing in the room — which is precisely the
# "they lose their shape as they get higher" report.
COL_DIM_UP = 0.78
PIL_PAD = 0                # clear px between a flush column and a frame
FEAT_GAP = 6               # clear px between two frames in one bay
# Both measured, not chosen: at PIL_PAD 1 / FEAT_GAP 10 the Diamond
# Head gallery wall could seat only five of its eight features, and
# the cliffs are savage — one bay missing the hall-plus-office pair
# by 0.4px cascades into three lost doors. Zero pad is also what the
# photograph shows: the door architraves run tight against the
# columns. A frame that rounds onto a strip by a pixel is dark koa
# over pale stone and invisible.

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


def rdiamond(a, dy=0.0):
    """The ELONGATED (rectangular-plan) counterpart of diamond():
    N, E, S, W with the E and S corners slid +WING_EXT in u. This is
    the wing done properly (2026-08-26, user: "i wanted the railing
    to also reflect this new length. it's still in the same square")
    — the well, the railing ring, the walkway and the courtyard all
    follow the longer plan, not just the outer walls. Same corner
    ORDER as diamond(), so every (i, j) edge-pair loop works
    unchanged. The rotunda-centred furniture (mosaic, chain ring,
    planter benches, breezeway band, the ʻEwa corner assembly) stays
    in absolute u/v and deliberately does NOT follow: the rotunda is
    where it is — the COURT is what got longer."""
    return [iso(-a, -a, dy), iso(a + WING_EXT, -a, dy),
            iso(a + WING_EXT, a, dy), iso(-a, a, dy)]


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
    d.polygon(rdiamond(A_OUT), fill=FLOOR)
    # quarry tile: per-cell tone jitter, then light grout joints —
    # a flat fill read as poured concrete, not tile (atrium photo).
    # The plan is a RECTANGLE now (see rdiamond/WING_EXT): u runs
    # WING_EXT further than v, and the well skip-test follows.
    nu = int(2 * A_OUT + WING_EXT)
    nv = int(2 * A_OUT)
    for k in range(nu):
        for l in range(nv):
            u0, v0 = -A_OUT + k, -A_OUT + l
            if (-A_IN <= u0 and u0 + 1 <= A_IN + WING_EXT
                    and -A_IN <= v0 and v0 + 1 <= A_IN):
                continue                       # the well covers it
            d.polygon([iso(u0, v0), iso(u0 + 1, v0),
                       iso(u0 + 1, v0 + 1), iso(u0, v0 + 1)],
                      fill=shade(FLOOR, rng.uniform(0.95, 1.07)))
    for k in range(1, nu):
        a = -A_OUT + k
        d.line([iso(a, -A_OUT), iso(a, A_OUT)], fill=shade(FLOOR, 1.14),
               width=1)
    for k in range(1, nv):
        a = -A_OUT + k
        d.line([iso(-A_OUT, a), iso(A_OUT + WING_EXT, a)],
               fill=shade(FLOOR, 1.14), width=1)


def paint_ring_shade(img):
    """Light falls off away from the well — the sky is the key light,
    so the walkway darkens toward the outer walls (atrium photo's
    value structure: dark frame, glowing centre). Stepped bands, not
    a radial vignette; walls/stairs repaint their own ground after."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.polygon(rdiamond(A_OUT + 0.2), fill=(8, 10, 16, 26))
    ld.polygon(rdiamond(A_OUT - 0.9), fill=(8, 10, 16, 14))
    ld.polygon(rdiamond(A_OUT - 1.8), fill=(0, 0, 0, 0))
    img.alpha_composite(lay)


def paint_sun(img):
    """Daylight spills out of the open well onto the inner ring."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for a, al in ((A_IN + 1.8, 22), (A_IN + 1.0, 24), (A_IN + 0.4, 28)):
        ld.polygon(rdiamond(a), fill=(255, 244, 214, al))
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
        d.polygon(rdiamond(a, -DROP), fill=base)
        ku = int(math.ceil((2 * a + WING_EXT) / SLAB))
        kv = int(math.ceil(2 * a / SLAB))
        for i in range(ku):
            for j in range(kv):
                u0, v0 = -a + i * SLAB, -a + j * SLAB
                u1 = min(a + WING_EXT, u0 + SLAB)
                v1 = min(a, v0 + SLAB)
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
        mu = int((a + WING_EXT) / SLAB)
        for q in range(-m, mu + 1):
            c = q * SLAB
            if c <= a + WING_EXT:
                d.line([iso(c, -a, -DROP), iso(c, a, -DROP)],
                       fill=shade(base, 0.88), width=1)
        for q in range(-m, m + 1):
            c = q * SLAB
            d.line([iso(-a, c, -DROP), iso(a + WING_EXT, c, -DROP)],
                   fill=shade(base, 0.88), width=1)

    regions = []
    # light through the SQUARE oculus lands as an offset quadrilateral,
    # not a soft ellipse — crisp edge, then a softer halo where bounce
    # fills in.
    for a_, ox, oy, t in ((A_IN - 1.0, -46, 14, 0.62),
                          (A_IN - 2.4, -62, 18, 1.0)):
        regions.append(([(px_ + ox, py_ + oy)
                         for px_, py_ in rdiamond(a_, -DROP)],
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
    hd, gd = rdiamond(A_IN, -DROP), rdiamond(GND_OUT, -DROP)
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
    # THE WELL IS A RECTANGLE now (see rdiamond/WING_EXT) — hole,
    # wall planes, courtyard and every band derived from them run
    # WING_EXT further in u. The rotunda-centred furniture (mosaic,
    # chain ring, planter benches) and the ʻEwa corner assembly stay
    # in absolute u/v below and do not follow.
    hole = rdiamond(A_IN)                    # N', E', S', W'
    gnd = rdiamond(GND_OUT)                  # the set-back wall plane

    # the courtyard floor and every tint that lands on it — see
    # court_paving, which composites them all through masks so the
    # paving keeps its mottle under the light
    court_paving(lay)
    d.line(rdiamond(A_IN - 0.7, -DROP) + [rdiamond(A_IN - 0.7, -DROP)[0]],
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
        # the loggia's own shade, thrown from the slab down the
        # set-back wall: the recess has to be DARKER than the court
        # floor or the columns have nothing to stand against
        q(-6, DROP, shade(RECESS_D, f * 0.82))        # ground level
        if glazed:
            # the ASSEMBLY (corner wall, doors, drum curve, pier) is
            # anchored in absolute u and parameterised on the
            # ORIGINAL run — pass that, with the extended corner as
            # `ext` so the drum's glazing continues past its apex
            # over the well's new length (see court_glass)
            court_glass(d, e0, iso(GND_OUT, -GND_OUT), f, 21,
                        DROP - 2, ext=e1)
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
        # OUR OWN SLAB'S EDGE, AND IT GOES LAST (2026-08-27, user:
        # "the second floor is missing the white band extending
        # beneath the railing. it just ends immediately"). It was
        # drawn FIRST in this loop and had been invisible ever since
        # the wall was set back (2026-08-25): the recess quad starts
        # 6px above the SET-BACK line, which on the far runs is
        # up-screen of the well line, so q(-6, DROP) spans 106px
        # straight down over the 18px band — measured at x=1000, the
        # band at y 616-634 sat under a fill covering 575-681. The
        # fascia belongs to the near slab, a whole bay in front of
        # that wall, so it is painted after everything the wall
        # carries. It still goes BEFORE the loggia columns and the
        # smokestack below: those stand at the well line and cross
        # in front of the band, exactly as in the breezeway photo.
        # FASCIA_D, not the old 18 — it is the same slab the makai
        # edge shows (paint_front_edge: "exactly the band the well
        # edges wear"), and the two disagreeing was only survivable
        # while this one drew into the dark.
        fluted_band(d, h0, h1, 0, FASCIA_D, f)
        # the flat pale piers that used to be pasted on this wall are
        # GONE — they were a ground-storey-only device standing on the
        # wall plane. THIS storey's columns are the real ones and they
        # stand free out in the loggia (court_column, just below);
        # from the second floor up the same column is flush in the
        # wall and wall_column() paints it there.
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
    # THE CORNER COLUMN, and it is drawn HERE — between the cone and
    # the panel — because that is the depth order at the apex. The
    # cone's axis is at v = STACK_V (farthest), the shaft at
    # v = -COL_APEX_U, and the panel's face nearer still, so the cone
    # goes behind the shaft and the corner wall in front of it. Drawn
    # with the other stations at the end of this function it would
    # paint over the corner mass instead of standing in it.
    court_column(d, iso(-COL_APEX_U, -COL_APEX_U), COL_DY0, 0, 1.0)
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


def court_glass(d, e0, e1, f, top, bot, ext=None):
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

    # ---- THE DRUM CONTINUES PAST ITS APEX (the elongated well — see
    # rdiamond/WING_EXT). The main arc ends where the drum faces the
    # camera (theta 0, maximum bow, widest mullion gaps); past that
    # point the same cylinder turns AWAY again, so the continuation
    # mirrors the physics — bars re-compressing toward the far corner,
    # sill bow easing back up — rather than running on as flat filler,
    # which is exactly the "mullions then a dark slab" read the
    # 2026-08-25 rework removed. It starts AT the last mullion of the
    # main arc so the curtain is one unbroken sheet.
    if ext is not None:
        TH_B = math.radians(52)
        sb = math.sin(TH_B)
        n2 = 11                     # ~the main arc's px pitch over
                                    # the 16*WING_EXT px extension
        p_end, b_end = tops[-1], sills[-1]

        def ext_pt(t2, yfrac):
            b = lerp(e1, ext, t2)
            return (b[0], b[1] + top + dy * yfrac)

        tops2, sills2 = [p_end], [b_end]
        for i in range(1, n2 + 1):
            th = TH_B * i / n2
            t2 = math.sin(th) / sb
            bow = (math.cos(th) - math.cos(TH_A)) / (1 - math.cos(TH_A))
            p = ext_pt(t2, 0)
            tops2.append((p[0], p[1] + round(bow_h * bow)))
            b = ext_pt(t2, 1.0)
            sills2.append((b[0], b[1] + round(bow_s * bow)))
        d.polygon(tops2 + sills2[::-1], fill=shade(hx("#171d1f"), f))
        refl2 = [lerp(pt, pb, 0.34) for pt, pb in zip(tops2, sills2)]
        d.polygon(tops2 + refl2[::-1], fill=shade(hx("#2e3839"), f))
        d.polygon(tops2 + [lerp(pt, pb, 0.15) for pt, pb
                           in zip(tops2, sills2)][::-1],
                  fill=shade(hx("#414d4b"), f))
        for i in range(1, n2 + 1):
            d.line([tops2[i], sills2[i]], fill=shade(hx("#a7ad9f"), f),
                   width=2)
        d.line(tops2, fill=shade(hx("#d9d2bc"), f), width=2)
        d.line([(x, y + 2) for x, y in tops2],
               fill=shade(hx("#8f8874"), f), width=1)
        d.line(sills2, fill=shade(hx("#3a352c"), f), width=2)


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
    """Plan positions of the courtyard columns, as screen points at
    GALLERY FLOOR level, with each run's shading factor.

    An EVEN division of each mauka run into COL_N + 1 bays, and
    nothing else — no door-dodging, because the doors are laid out
    around these now (place_feats) rather than the other way round.
    A colonnade is structural and this is what structural looks like.

    ONE list, shared by the free-standing shaft in the loggia and by
    the flush strip on each upper wall, so the three pieces of a
    column cannot drift onto different centres.

    Deliberately the ORIGINAL square hole, NOT rdiamond: these
    stations must land on col_xs()'s screen x (run_x over A_IN with
    no extension) or the loggia shaft and the flush wall strips
    above it split apart. The elongated well's extension keeps the
    colonnade rhythm it inherits — do not re-space it here without
    re-deriving every wall's door bays.
    """
    hole = diamond(A_IN)
    out = []
    for (e0, e1), f in (((hole[3], hole[0]), 1.0),
                        ((hole[0], hole[1]), 0.86)):
        for t in COL_T:
            out.append((lerp(e0, e1, t), f))
    # ONE extra station mid-extension on the elongated DH run (see
    # rdiamond/WING_EXT): without it the colonnade stops at the old
    # 2/3 station and the drum glazing runs ~220px bare. A loggia
    # shaft only — the wing walls above carry no flush strip, which
    # is survivable because the strips are the subtlest element in
    # the room; the free shafts are not.
    out.append((iso(A_IN + WING_EXT / 2, -A_IN), 0.86))
    return out


def col_hw(dy):
    """Half-width of a courtyard column at world height dy. ONE
    function, because a column is drawn in THREE pieces on three
    different surfaces — free-standing in the loggia (paint_well's
    clipped layer), then flush in the gallery wall, then flush in the
    Senate wall — and separate taper maths in each would step at
    every join."""
    t = (dy - COL_DY0) / (COL_DY1 - COL_DY0)
    t = min(1.0, max(0.0, t))
    return COL_HW0 + (COL_HW1 - COL_HW0) * t ** COL_FLARE


def court_column(d, b, dy_lo, dy_hi, f=1.0):
    """A column WHERE IT STANDS FREE — the loggia, and only there.
    Above the gallery floor the same shaft is flush in the wall and
    wall_column() draws it; the two share col_hw(), so the taper runs
    straight through the storeys the eye cannot see.

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
    #
    # NEUTRAL GRAY, not khaki (2026-08-27, from the breezeway photo:
    # "same with the columns"). The photo's shafts meter at r-b ≈ 17
    # (144,139,127 mid face) — smooth cool concrete; the shipped
    # palette carried r-b ≈ 30 and read as sandstone. Values kept,
    # warmth halved.
    d.polygon(left + right[::-1], fill=shade(hx("#c5c1b6"), f))
    d.polygon(left + lit[::-1], fill=shade(hx("#d9d6cb"), f))
    d.polygon(inner + right[::-1], fill=shade(hx("#918d82"), f))
    # faint vertical weathering streaks on the lit face — the photo's
    # shafts are smooth but not flat; two 1px runs that follow the
    # taper (a straight line would exit the shaft as it flares)
    for uS in (-0.34, -0.16):
        d.line([(round(b[0] + uS * col_hw(lo + (hi - lo) * i / steps)),
                 round(b[1] - (lo + (hi - lo) * i / steps)))
                for i in range(steps + 1)],
               fill=shade(hx("#bcb8ac"), f), width=1)
    # BOTH edges get a real keyline. The ʻEwa run's backdrop is the
    # open breezeway — bright plaza bands — so a pale shaft against it
    # has no silhouette at all without one; same lesson the cone's
    # 2px keyline records against the glazing.
    d.line(left, fill=shade(hx("#e2ddd1"), f), width=1)      # lit arris
    d.line(right, fill=shade(hx("#6a665c"), f), width=2)     # dark edge
    # ONE pour joint per storey — the photo's shafts are cast in
    # lifts and the horizontal break is what keeps a tall shaft from
    # reading as an extruded sliver. Nothing finer: at display scale
    # a second line per storey is noise.
    for dy in (0, LVL2_Y):
        if lo < dy < hi:
            hw, y = col_hw(dy), round(b[1] - dy)
            d.line([(round(b[0] - hw) + 1, y), (round(b[0] + hw) - 1, y)],
                   fill=shade(hx("#b0ac9f"), f), width=1)


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
    (y = apex + FASCIA_D + |x - CX| / 2), so the courses die under the
    slab and the stack reads as continuing above it, off-stage. The
    mouth rim is gone with it — a mouth you can see means the stack
    ended in the well, which is exactly the old floating read this
    replaces. Don't shorten h back to "stop under the hole edge";
    the shear line IS the top.

    It belongs to the ROTUNDA FLOOR alone; nothing on the two office
    levels above it reacts to it.
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
    # hangs FASCIA_D under the hole edge, and both mauka edges fall
    # away from the apex at the iso 1:2 — one expression covers the
    # cone whichever side of the corner a point lands on. READ FROM
    # THE CONSTANT: this was a literal 18 matching the well fascia's
    # own literal, and when that band went to FASCIA_D (2026-08-27)
    # the shear line stayed put and the cone drew over the bottom
    # 6px of the white band it is supposed to die under.
    y_sh = CY - 16 * A_IN + FASCIA_D

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
def fluted_band(d, e0, e1, y_top, depth, f=1.0, flutes=True):
    """The precast fin fascia: CHUNKY alternating white panels with
    real shadow gaps — the photo's most distinctive element. 5px fin,
    2px gap, bright top lip. `flutes=False` drops the grooves for a
    PLAIN slab edge — the makai CUT bands use it (2026-08-27, user:
    "remove the lines on the cutaway bottom of the second floor"):
    the dollhouse cut is sawn slab, not a dressed facade, and at
    FASCIA_D deep the striping read as one more balustrade."""
    p0, p1 = (e0[0], e0[1] + y_top), (e1[0], e1[1] + y_top)
    d.polygon([p0, p1, (p1[0], p1[1] + depth), (p0[0], p0[1] + depth)],
              fill=shade(hx(FLUTE_FIELD), white_f(f)))
    if flutes:
        for b in even_run(p0, p1, FLUTE_PITCH):
            d.line([(b[0], b[1] + 2), (b[0], b[1] + depth - 1)],
                   fill=shade(hx(FLUTE_GROOVE), white_f(f)),
                   width=FLUTE_W)
    d.line([p0, p1], fill=shade(hx("#f7f3e6"), f), width=2)
    d.line([(p0[0], p0[1] + depth), (p1[0], p1[1] + depth)],
           fill=shade(hx("#8a8474"), f), width=1)


def paint_railings(d):
    """The real railing, per the atrium photos, drawn CHUNKY enough to
    survive game zoom: a deep fluted white parapet fascia at the slab
    edge (hanging into the well), an OPEN run of dark metal pickets
    you see the well through, and a heavy koa handrail. No fat posts.
    The ring follows the ELONGATED well (rdiamond) — the DH and SW
    runs are longer and the E'/S' corners sit WING_EXT further out."""
    hole = rdiamond(A_IN)
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
    hole = rdiamond(A_IN)
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


def bench_at(d, e0, e1, t, f):
    """A DARK WOODEN BENCH standing against the wall on the walkway.

    Benches were drawn here once before and deleted; CLAUDE.md records
    why — "drawn mid-walkway with no wall contact they read as brown
    bars floating on the railings". Both halves of that are fixed by
    measurement, not by redrawing:

    CONTACT IS OVERLAP, NOT PROXIMITY. The seat's back edge sits ON
    the wall's foot line and the bench OCCLUDES the bottom of the wall
    face, so it is painted after the wall and after the doors. A bar
    that merely stops near the wall has nothing holding it there.

    AND IT IS FOUND BY ITS SHADOW. Measured on the executive-floor
    photograph, the bench body is 0.89 of the walkway it stands on —
    11% DARKER than its own deck, so it never separates from the floor
    by value. What separates it is the contact shadow at 0.57 of the
    floor. Draw the bench and skip the shadow and it floats again.

    Proportions are measured too: length 1.5 office-leaf widths, seat
    8-9 px, depth equal to the height, backless, and no daylight
    under the seat (the underside samples flat, sd 2.5). The render
    exaggerates height ~2.8x against plan, so the top plane is only
    ~3 px of screen y and the front face 8 — the bench is mostly front
    face, and the lit lip has to carry the whole object in two px.

    ON THE COLOUR. The real bench measures NEUTRAL — R-B of 9 against
    koa's 53 — because it sits in shade; the user asked for dark wood.
    This splits the difference deliberately: dark enough and desatur-
    ated enough (R-B 7-17) that it cannot camouflage against the warm
    quarry-tile deck (R-B 43), which is the other half of why the last
    attempt read as a brown bar.
    """
    p = lerp(e0, e1, t)
    ex = (e1[0] - e0[0], e1[1] - e0[1])
    ln = math.hypot(*ex)
    ux, uy = ex[0] / ln, ex[1] / ln
    # OUTWARD, toward the court: the wall's normal in screen space.
    # Run 0 falls to the right (slope -0.5) and its normal is
    # (+2, +1); run 1 rises and its normal mirrors to (-2, +1).
    sgn = 1 if ex[1] / ex[0] < 0 else -1
    dx, dy = 6 * sgn, 3                     # 0.375 plan units of depth
    hw, ht = FEAT_HW["bench"] - 2, 9

    def pt(w, y, out=0):
        return (round(p[0] + ux * w + dx * out),
                round(p[1] + uy * w + dy * out - y))

    def quad(w0, w1, a, b, col):
        d.polygon([pt(w0, *a), pt(w1, *a), pt(w1, *b), pt(w0, *b)],
                  fill=col)

    # the contact shadow FIRST, on the floor. It has to be a SHADOW
    # and not a hole: at 0.48 of the tile it merged with the bench's
    # own front face and the pair read as one dark blob, which is a
    # different failure from floating but just as bad. 0.62 of the
    # tile, and only 1.8 units deep.
    quad(-hw, hw, (0, 0), (-1, 1.8), mix(FLOOR, hx("#120c08"), 0.38))
    # the front face and the solid under-mass, as one dark plane
    quad(-hw, hw, (ht, 1), (0, 1), shade(hx("#26221c"), f))
    # the seat's top plane: dark where it meets the wall, and it is
    # only ~3 px of screen y, so this is nearly all lip
    quad(-hw, hw, (ht, 0), (ht, 1), shade(hx("#3b352d"), f))
    # THE LIT LIP — 1.45x the body, full strength, no gradient. At
    # display scale this single line IS the bench, so it is the one
    # thing here that must not be feathered or dimmed.
    d.line([pt(-hw, ht, 1), pt(hw, ht, 1)],
           fill=shade(hx("#564e42"), f), width=2)
    # a dark seam where the seat back bites into the wall
    d.line([pt(-hw, ht, 0), pt(hw, ht, 0)],
           fill=shade(hx("#1b1814"), f), width=1)
    return p


def alcove_at(d, e0, e1, t, f):
    """THE LITTLE ALCOVE at the court's corner — a shallow, full-height
    dark pocket in the wall, beside the corner column (user,
    2026-08-25: "the top point of the graphic, next to the hallway, is
    where a little alcove is").

    Measured on the executive-floor photograph: at every level a
    near-black zone about one door bay wide flanks the corner column
    on BOTH runs, stepped at its edges rather than graded, as dark as
    the ground-floor loggia recess (13-20 against a wall of 33-45) and
    the only full-height feature of its kind on either run. Only the
    ʻEwa side gets one here — on the Diamond Head side the hallway
    mouth already is the recess, which is exactly the asymmetry the
    user described.

    It is SHALLOW — the one 6px reveal it can be measured from puts it
    at about a quarter of a walkway width — so this is a pocket, not a
    room: no receding floor, no far wall, no corridor perspective.
    corridor_at() is the wrong model and would spill a lit floor wedge
    across the wall face.
    """
    p = lerp(e0, e1, t)
    ex = (e1[0] - e0[0], e1[1] - e0[1])
    ln = math.hypot(*ex)
    ux, uy = ex[0] / ln, ex[1] / ln
    hw = FEAT_HW["alcove"] - 3

    def pt(w, y):
        return (round(p[0] + ux * w), round(p[1] + uy * w - y))

    def quad(w0, w1, y0, y1, col):
        d.polygon([pt(w0, y0), pt(w1, y0), pt(w1, y1), pt(w0, y1)],
                  fill=col)

    quad(-hw, hw, 0, 56, shade(hx("#1c1b18"), f))          # the pocket
    quad(-hw, -hw + 3, 0, 56, shade(hx("#2c2a26"), f))     # near cheek
    d.line([pt(-hw, 56), pt(hw, 56)],
           fill=shade(hx("#131210"), f), width=2)          # soffit
    d.line([pt(-hw, 1), pt(hw, 1)],
           fill=shade(hx("#26241f"), f), width=1)          # its floor
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


FEAT_HW = {"door": 20, "office": 14, "hall": 19, "lift": 19,
           "bench": 21, "alcove": 17}

# THE CLICKABLE BOX OF A WALL FEATURE, in the same wall coordinates
# the painters use: (half-width along the RUN, y_lo, y_hi) where y is
# height above the wall foot, exactly as door_at/corridor_at's inner
# pt(w, y) reads them. Straight off those two painters — a koa leaf
# is hw 17 with a frame proud of it and a threshold at ±hw+4, and its
# head/transom quad closes at y 53; a corridor portal is hw 16 in a
# ±hw+4 frame, ht 48 plus its head.
#
# This exists because the runtime used to size every zone 120x84 at
# (px, py+6), which is a box three times the width of a door sitting
# roughly a door-height BELOW it, out on the walkway floor. Two
# consequences, both measured 2026-08-27: House Gallery and Governor
# overlapped by 39% of a zone (and the later-built one won, so a third
# of the gallery's target opened the lift instead), and on the near
# runs the box missed its door entirely. Deriving the box from the
# drawing is the one-source rule the columns already follow.
FEAT_BOX = {"door": (21, -7, 53), "office": (15, -7, 53),
            "hall": (20, -7, 54), "lift": (20, -7, 54)}
# The most a zone may grow on every side before it ships: a door frame
# is only ~38 screen px across and the box wants to forgive a near
# miss. It is a CEILING, not a flat amount — see zones_for.
ZONE_PAD = 9


def feat_rect(e0, e1, t, kind):
    """The screen-space AABB (scene px) of the feature `place_feats`
    put at run parameter `t`. The run is a 2:1 iso diagonal, so a box
    that is symmetric in WALL coordinates is a sheared parallelogram
    on screen and its bounding box has to take all four corners —
    using the width alone (the obvious version) leaves the box short
    by the ±hw*uy the diagonal contributes to its height."""
    p = lerp(e0, e1, t)
    ex, ey = e1[0] - e0[0], e1[1] - e0[1]
    ln = math.hypot(ex, ey)
    ux, uy = ex / ln, ey / ln
    a, y_lo, y_hi = FEAT_BOX[kind]
    xs = [p[0] - ux * a, p[0] + ux * a]
    ys = [p[1] + uy * w - y
          for w in (-a, a) for y in (y_lo, y_hi)]
    return (min(xs), min(ys), max(xs), max(ys))


def zones_for(rects, pad=ZONE_PAD):
    """Every hotspot rect as the `[cx, cy, w, h]` the runtime builds a
    Phaser zone from (centre and size, SCENE px), grown toward `pad` on
    all sides but never into a neighbour.

    A FLAT pad is the wrong shape for this wall, because the wall is
    not evenly packed: most named doors have most of a bay of air
    beside them and can take the full 9, while the Senate Clerk sits
    one FEAT_GAP from the lift lobby that closes its run and has about
    8 to give. Baked flat at 9 those two overlap by 2px — measured, it
    is what the assert in render() caught first time out.

    Two axis-aligned boxes are disjoint if they clear on EITHER axis,
    so a pair's whole budget is `max(gap_x, gap_y) / 2` and each box
    takes the smallest budget any neighbour allows. Symmetric on
    purpose: give one box of a pair the slack and the other could still
    be pushed into it from its far side by a third."""
    ids = list(rects)
    room = {k: float(pad) for k in ids}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = rects[ids[i]], rects[ids[j]]
            gx = (abs((a[0] + a[2] - b[0] - b[2]) / 2)
                  - ((a[2] - a[0]) + (b[2] - b[0])) / 2)
            gy = (abs((a[1] + a[3] - b[1] - b[3]) / 2)
                  - ((a[3] - a[1]) + (b[3] - b[1])) / 2)
            # the 0.5 is the rounding headroom the ints below can eat
            lim = max(gx, gy) / 2 - 0.5
            room[ids[i]] = min(room[ids[i]], lim)
            room[ids[j]] = min(room[ids[j]], lim)
    out = {}
    for k, (x0, y0, x1, y1) in rects.items():
        p = max(0.0, room[k])
        out[k] = [round((x0 + x1) / 2), round((y0 + y1) / 2),
                  int(x1 - x0 + 2 * p), int(y1 - y0 + 2 * p)]
    return out

# THE TWO DOOR SCHEDULES — ORDER AND KIND ONLY, NO POSITIONS
# (re-cut 2026-08-25 when the columns went flush). The t values used
# to be written here by hand and the columns were nudged around them;
# now place_feats() lays each list out in the bays between the
# columns, so a wall re-spaces itself when COL_N or the column line
# moves instead of leaving a hand-tuned schedule lying against the
# new bays. Index 0 is the ʻEwa run, index 1 the Diamond Head run,
# matching the order both painters iterate in.
#
# ORDER IS THE CONTRACT: place_feats never reorders, so the Diamond
# Head run's portals still BRACKET it — a hallway mouth first, the
# lift lobby last — and the ʻEwa run is still all doors. An unnamed
# office is filler and may be dropped if its wall runs out of room;
# a named one is a hotspot and never is.
# FEWER INERT DOORS, AND BENCHES BESIDE THE ONES THAT REMAIN (user,
# 2026-08-25: "remove some of the inert doors and put dark wooden
# benches next to them"). The count is measured, not chosen: a full
# run of the executive-floor photograph carries three doors and ONE
# bench, and the balcony above it the same — about one bench per two
# door bays, two to a run, never one per bay. A bench is also SHORTER
# than a door, so converting one hands wall room back to the bay
# layout. The corner-most slot on each ʻEwa run is the ALCOVE (see
# alcove_at); the Diamond Head runs already close on a portal.
# THE FLOOR HAS AN OWNER (2026-08-27, user's call: "third floor is
# for house and second for senate"). Level 2 — the gallery walkway
# the player stands on — is the SENATE's floor on BOTH of its runs;
# level 3 is the HOUSE's on both of its. Before this the two levels
# were split the other way: every public room (both galleries, both
# money committees) sat on the walkway and the offices above were
# labelled Senate, which put the Senate Clerk on the Diamond Head run
# and left no floor with an owner at all.
#
# The ʻEwa / Diamond Head rule still stands, but it governs what is
# BELOW — Senate cone ʻEwa, House cone Diamond Head — not the door
# runs above it. Each chamber's gallery door is still on its own
# cone's side of its own floor (senate on GALLERY[0], house on
# UPPER[1]), so the two rules agree where they touch.
#
# `gov` is the deliberate exception: the Level 5 lift belongs to
# neither chamber, and it stays on the walkway because that is the
# floor the player is standing on — the way up has to be reachable
# from where you are.
GALLERY_FEATS = (                       # LEVEL 2 — the Senate's floor
    (("senate", "door"), (None, "office"), ("wam", "door"),
     (None, "bench"), (None, "office"), (None, "alcove")),
    ((None, "hall"), (None, "office"), ("senpres", "door"),
     (None, "bench"), ("senclerk", "door"), ("gov", "lift")),
)
UPPER_FEATS = (                         # LEVEL 3 — the House's floor
    (("speaker", "door"), (None, "office"), (None, "bench"),
     ("houseclerk", "door"), (None, "bench"), (None, "alcove")),
    ((None, "hall"), (None, "office"), (None, "bench"),
     ("finance", "door"), (None, "office"), ("house", "door"),
     (None, "hall")),
)


def run_x(r, a, t):
    """Screen x of parameter t along a mauka run of half-size `a`.
    The column line, the gallery wall and the Senate wall sit on
    THREE different diamonds, so the same t is three different
    screen positions — comparing raw t between them (the obvious
    mistake) would clear a door that is nowhere near the shaft."""
    return CX + 32.0 * a * (t - 1 if r == 0 else t)


def run_t(r, a, x):
    """Inverse of run_x — the parameter along a mauka run of half-size
    `a` that lands on screen x. The bay layout is computed in screen
    x (it has to be: the column line and the two walls sit on three
    different diamonds) and the painters all speak t, so this is the
    one place the two coordinates meet."""
    return (x - CX) / (32.0 * a) + (1.0 if r == 0 else 0.0)


def col_ts(r):
    """The columns as run parameters: the interior pair, plus the
    CORNER column at the mauka apex — t = 1 on the ʻEwa run, t = 0 on
    the Diamond Head one, which is the same column seen from either
    side."""
    return list(COL_T) + [1.0] if r == 0 else [0.0] + list(COL_T)


def col_xs(r):
    """Screen x of every column on run `r`. ONE source — the shaft in
    the loggia, the flush strip on each upper wall and the bays the
    doors are laid out in all read this, so a column cannot be in
    three places at once."""
    return [run_x(r, A_IN, t) for t in col_ts(r)]


def wall_bays(r, a, hw):
    """The clear spans of a wall run, in screen x, between the FLUSH
    columns — where doors are allowed to be. `hw` is the widest the
    strip gets on this storey (it tapers, so the head is what has to
    clear). The two end bays reach the corners, which is why they are
    the wide ones: the wall diamond is bigger than the column line's,
    so each run's wall carries mass past its outermost column."""
    x0, x1 = sorted((run_x(r, a, 0.0), run_x(r, a, 1.0)))
    out, lo = [], x0
    for cx in sorted(col_xs(r)):
        out.append((lo, cx - hw - PIL_PAD))
        lo = cx + hw + PIL_PAD
    out.append((lo, x1))
    # the apex column stands ON the run's end, so the bay it closes
    # off has no width at all — drop it rather than let the allocator
    # hand it a door it cannot hold
    return [(p_, q_) for p_, q_ in out if q_ - p_ > 8]


def _lay_bays(bays, items):
    """Screen x for each item, or None if this many will not fit.

    An EXHAUSTIVE split, not a heuristic: the bays are ordered, the
    items are ordered, so the whole question is where to cut the list
    into one contiguous group per bay — a handful of possibilities at
    these sizes. Every feasible cut is scored by its FULLEST bay and
    the loosest one wins, which spreads the doors instead of packing
    the first bay and starving the rest.

    A proportional-share pass with a repair loop was tried first and
    ping-ponged one door between two bays that could each hold it
    only without the other, then gave up and dropped it — three doors
    lost off the Diamond Head gallery wall. Order is the constraint
    that makes the exhaustive form cheap; use it.
    """
    n, k = len(items), len(bays)
    if not n:
        return []
    if not k:
        return None

    def span(seg):
        return (sum(2 * FEAT_HW[kk] for _, kk in seg)
                + FEAT_GAP * (len(seg) - 1)) if seg else 0.0

    best = [None, None]

    def walk(j, i, cuts):
        if j == k:
            if i != n:
                return
            fill, s0 = 0.0, 0
            for c, (p_, q_) in zip(cuts, bays):
                fill = max(fill, span(items[s0:s0 + c]) / (q_ - p_))
                s0 += c
            if best[0] is None or fill < best[0]:
                best[0], best[1] = fill, list(cuts)
            return
        p_, q_ = bays[j]
        for c in range(0, n - i + 1):
            if span(items[i:i + c]) > q_ - p_:
                break
            cuts.append(c)
            walk(j + 1, i + c, cuts)
            cuts.pop()

    walk(0, 0, [])
    if best[1] is None:
        return None

    xs, s0 = [], 0
    for c, (a_, b_) in zip(best[1], bays):
        ks = items[s0:s0 + c]
        s0 += c
        if not ks:
            continue
        m = ((b_ - a_) - span(ks)) / (len(ks) + 1)
        x = a_ + m
        for _, kk in ks:
            xs.append(x + FEAT_HW[kk])
            x += 2 * FEAT_HW[kk] + FEAT_GAP + m
    return xs


def place_feats(r, a, hw, feats):
    """One wall's door schedule, laid out in the bays between the
    flush columns. `feats` is the ORDERED list — names and kinds, no
    positions — and the t values come out of the geometry, so moving
    a column or changing COL_N re-spaces the doors instead of leaving
    a hand-tuned schedule lying against the new bays.

    A wall that cannot hold its whole list loses FILLER from the far
    end, one item at a time, until it can — and only filler. Named
    entries are HOTSPOTS, so dropping one costs the player a door they
    need to click; a portal or an ALCOVE is a piece of the building's
    plan rather than dressing, and the corner alcove in particular is
    the whole point of the corner (it was silently dropped the first
    time this ran, which is what this rule exists to prevent). So the
    drop order is: unnamed office doors first, then unnamed benches,
    then nothing. The dense-doors call (2026-08-22, "in reality there
    would be many more doors") is served by filling every bay, not by
    a fixed count.
    """
    bays = wall_bays(r, a, hw)
    items = list(feats)
    while True:
        xs = _lay_bays(bays, items)
        if xs is not None:
            return [(nm, run_t(r, a, x), k)
                    for (nm, k), x in zip(items, xs)]
        i = next((i for kinds in (("office",), ("bench",))
                  for i in range(len(items) - 1, -1, -1)
                  if items[i][0] is None and items[i][1] in kinds), None)
        assert i is not None, "no room on this wall for its fixed features"
        items.pop(i)


def wall_column(d, r, e0, e1, y_lo, y_hi, dy_lo, dy_hi, f):
    """THE COLUMN WHERE IT IS FLUSH IN THE WALL — the second and third
    storeys. Drawn with the wall and before anything that stands in
    front of it, so the walkway and its parapet cross it exactly as
    they do in the photograph, and it shows only in the band between
    one balcony's cap and the slab above.

    FLAT, deliberately: one face, a light arris and a shadowed
    reveal. The loggia shaft below is modelled in three tones because
    it is a solid standing in the open; giving the strip the same
    treatment would make it read as projecting again, which is the
    whole thing being fixed here.

    The taper carries straight through from the shaft (`col_hw` on
    the storey's own world heights), so the column keeps thickening
    as it rises even though the middle of every storey is hidden.
    """
    hw_lo, hw_hi = col_hw(dy_lo), col_hw(dy_hi)
    x_lo, x_hi = sorted((e0[0], e1[0]))
    sl = (e1[1] - e0[1]) / (e1[0] - e0[0])       # ±0.5 on every run
    for cx in col_xs(r):
        if not x_lo <= cx <= x_hi:
            continue
        yb = e0[1] + (cx - e0[0]) * sl

        def pt(dx, y):
            """A point `dx` along the RUN from the column's centre.
            The strip has to SHEAR with the wall: its foot and head
            are lines running with the 2:1 face, not horizontals.
            Drawn as an axis-aligned rectangle it read as a pale
            panel pasted flat on a receding wall — and its lower
            corner hung below the wall's own foot, which is the
            white nub that showed up along the base of both upper
            storeys (user, 2026-08-25)."""
            return (round(cx + dx), round(yb + dx * sl - y))

        # a corner column stands ON the run's end and only its half
        # belongs to this face; the other half is the next run's, and
        # the two meet at the fold
        a_lo, a_hi = max(-hw_hi, x_lo - cx), min(hw_hi, x_hi - cx)

        def cl(w):
            return max(a_lo, min(a_hi, w))

        cap_h, cap_w, cap_c = COL_CAP
        f = f * (COL_DIM_UP if dy_lo >= LVL2_Y else 1.0)

        def cap(w, y):
            """The capital's extra flare, if any — a widening confined
            to the top `cap_h` px, in the WALL PLANE, so it can never
            read as the column stepping out of the wall."""
            if cap_h <= 0 or y < y_hi - cap_h:
                return w
            return w * (1.0 + (cap_w - 1.0) * (y - (y_hi - cap_h)) / cap_h)

        # the surface, band by band. Each band is SLICED up the
        # storey so its foot->head gradient is a real ramp: PIL fills
        # a polygon flat, and one flat quad per band is exactly the
        # "splotch" this exists to fix. Slices overlap by a pixel
        # upward and the next one paints over the seam.
        n = max(6, int(abs(y_hi - y_lo) / 3))
        for u0, u1, c0, c1 in COL_FACETS:
            a, b = hx(c0), hx(c1)
            for i in range(n):
                t0, t1 = i / n, (i + 1) / n
                yA = y_lo + (y_hi - y_lo) * t0
                yB = y_lo + (y_hi - y_lo) * t1 + 1
                wA = hw_lo + (hw_hi - hw_lo) * t0
                wB = hw_lo + (hw_hi - hw_lo) * t1
                wA, wB = cap(wA, yA), cap(wB, yB)
                d.polygon([pt(cl(u0 * wA), yA), pt(cl(u1 * wA), yA),
                           pt(cl(u1 * wB), yB), pt(cl(u0 * wB), yB)],
                          fill=shade(mix(a, b, (t0 + t1) / 2), f))
        for u, (c, w) in ((-1.0, COL_EDGE_L), (1.0, COL_EDGE_R)):
            if a_lo <= u * hw_lo <= a_hi:
                d.line([pt(u * hw_lo, y_lo),
                        pt(u * cap(hw_hi, y_hi), y_hi)],
                       fill=shade(hx(c), f), width=w)
        if cap_c:
            # the slab's soffit shadow across the column head
            w = cap(hw_hi, y_hi)
            d.line([pt(cl(-w), y_hi - 1), pt(cl(w), y_hi - 1)],
                   fill=shade(hx(cap_c), f), width=2)


def bay_columns(d, r, e0, e1, f, feats, reflect=False):
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
        # …and off the FLUSH COLUMNS, which are the same wall face and
        # would otherwise take a bronze stripe down their middle
        if any(abs(b[0] - cx) < COL_HW1 + 6 for cx in col_xs(r)):
            continue
        d.rectangle([b[0] - 2, b[1] - 58, b[0] + 2, b[1] - 6],
                    fill=shade(hx("#241c15"), f))
        d.rectangle([b[0] - 2, b[1] - 58, b[0] - 1, b[1] - 6],
                    fill=shade(hx("#6b5c4a"), f))
        if reflect:
            # column reflection in the walkway tile
            d.line([(b[0], b[1] + 3), (b[0], b[1] + 9)],
                   fill=mix(FLOOR, hx("#241c15"), 0.45), width=2)


def upper_parapet(d, a0, a1, f, phase0=None):
    """The third level's rail: THE SECOND FLOOR'S RAILING, VERBATIM
    (2026-08-27, user, closing a five-state saga: "why doesnt it
    just look like the second floor railings?"). Same assembly as
    paint_railings' far edges — white kerb plate, open dark-bronze
    pickets you see the terrace through, slim stanchions, the wide
    koa handrail. Nothing invented: solid parapet, white-groove
    parapet, and two cuts of a photo-derived white balustrade were
    all tried and all read wrong up here; the room already had a
    railing the user liked, one storey down. If this rail ever needs
    to change again, change paint_railings WITH it.

    The ONE deviation is the picket colour: the well rail's far-edge
    #4a4238 (lum 66) vanishes on this storey's darker walkway
    (lum ~60, vs the gallery's ~85) — Δ6 where the well rail carries
    Δ20-25. The bay columns' deep bronze (#241c15, lum ~29) restores
    the same gap against THIS floor: same relationship, same read,
    different constant. `phase0` anchors the picket rhythm: pass the
    ORIGINAL run's start so a wing segment keeps the 6px beat across
    the junction (pickets are drawn only inside a0..a1)."""
    fw = white_f(f)
    x_lo, x_hi = sorted((a0[0], a1[0]))
    # white kerb plate at the floor (paint_railings: "a light base
    # curb sits under the picket run")
    d.polygon([a0, a1, up(a1, 4), up(a0, 4)],
              fill=shade(hx("#ddd6c1"), fw * 0.98))
    d.line([up(a0, 4), up(a1, 4)], fill=shade(hx("#8a8474"), fw),
           width=1)
    # pickets: thin dark metal, the terrace showing between them
    pk = shade(hx("#241c15"), f)
    for b in even_run(phase0 or a0, a1, PICKET_PITCH):
        if not x_lo <= b[0] <= x_hi:
            continue
        d.line([up(b, 5), up(b, RAIL_H)], fill=pk, width=PICKET_W)
    # slim stanchions — dark bronze like the pickets, pitched by
    # SPAN (the well rail's i/8 would bunch eight into the short
    # wing segment)
    n = max(1, round(abs(a1[0] - a0[0]) / 55.0))
    for i in range(1, n):
        b = lerp(a0, a1, i / n)
        d.rectangle([b[0] - 1, b[1] - RAIL_H, b[0] + 1, b[1] - 4],
                    fill=shade(hx("#57503f"), f))
    # end posts — the rail terminates INTO something at the sliced
    # ends and the apex instead of stopping mid-air (the well rail's
    # corner posts, bronze with the koa top)
    for c in (a0, a1):
        d.rectangle([c[0] - 2, c[1] - RAIL_H - 6, c[0] + 2, c[1]],
                    fill=shade(hx("#57503f"), f))
        d.rectangle([c[0] + 1, c[1] - RAIL_H - 6, c[0] + 2, c[1]],
                    fill=shade(hx("#443e30"), f))
        d.rectangle([c[0] - 2, c[1] - RAIL_H - 6, c[0] + 2,
                     c[1] - RAIL_H - 2], fill=KOA)
        d.line([(c[0] - 2, c[1] - RAIL_H - 6),
                (c[0] + 2, c[1] - RAIL_H - 6)], fill=KOA_LT, width=1)
    # the koa handrail — the same wide polished cap as the well rail
    d.line([up(a0, RAIL_H + 1), up(a1, RAIL_H + 1)],
           fill=shade(hx("#54391f"), f), width=2)
    d.line([up(a0, RAIL_H + 3), up(a1, RAIL_H + 3)],
           fill=shade(hx("#9a6a38"), f), width=3)
    d.line([up(a0, RAIL_H + 5), up(a1, RAIL_H + 5)],
           fill=shade(hx("#c79a5c"), f), width=2)
    d.line([up(a0, RAIL_H + 6), up(a1, RAIL_H + 6)],
           fill=shade(hx("#ecd0a1"), f), width=1)


def paint_upper_level(d):
    """The third level — the HOUSE's floor — stepped BACK a full bay.

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
    # the E-side face rides out with the wing (see WING_EXT) — the
    # runs continue, so the sawn end has to close them at their NEW
    # ends or the wing walls hang open over ink
    g_in[1] = iso(A_OUT + WING_EXT, -A_OUT)
    g_out[1] = iso(LVL2_OUT + WING_EXT, -LVL2_OUT)
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
    for r, (i0, i1, f) in enumerate((
        # Both HALLWAY MOUTHS sit on the Diamond Head run (user,
        # 2026-08-24): one hard against the top point and one past the
        # rightmost door, so the recesses bracket the run instead of
        # punching a hole through the middle of it. Mid-wall portals
        # broke the door rhythm exactly where the eye travels.
        (3, 0, 1.10),
        (0, 1, 0.97),
    )):
        feats = place_feats(r, LVL2_OUT, col_hw(LVL2_Y + 58),
                            UPPER_FEATS[r])
        a0, a1 = inn[i0], inn[i1]
        e0, e1 = out[i0], out[i1]

        def q(y0, y1, col):
            d.polygon([up(e0, y0), up(e1, y0), up(e1, y1), up(e0, y1)],
                      fill=col)

        # ---- the wall (far)
        # NO pale base strip: the wall is concrete to its own foot
        # (user, 2026-08-25 — "get rid of that white base strip too").
        # It was a white skirting under every door on both upper
        # storeys and the photographs have nothing like it; the
        # walkway's own slab edge is what the wall meets.
        q(0, 58, shade(CONC, f))
        for y in (24, 41):
            d.line([up(e0, y), up(e1, y)],
                   fill=shade(CONC, f * 0.90), width=1)
        # the column, FLUSH in this wall — before the doors and long
        # before the walkway that crosses it
        wall_column(d, r, e0, e1, 0, 58, LVL2_Y, LVL2_Y + 58, f)
        bay_columns(d, r, e0, e1, f, feats)
        benches = []
        for did, t, kind in feats:
            if kind == "door":
                pos = door_at(d, e0, e1, t, "koa")
            elif kind == "office":
                pos = door_at(d, e0, e1, t, "office", hw=11)
            elif kind == "alcove":
                pos = alcove_at(d, e0, e1, t, f)
            elif kind == "bench":
                benches.append(t)
                continue
            else:
                pos = corridor_at(d, e0, e1, t, f)
            if did:
                # position AND the box the runtime will make
                # clickable, from the geometry that drew it
                doors[did] = (pos, feat_rect(e0, e1, t, kind))
        q(58, 72, shade(hx(FLUTE_FIELD), white_f(f)))
        for b in even_run(e0, e1, FLUTE_PITCH):
            d.line([up(b, 59), up(b, 71)],
                   fill=shade(hx(FLUTE_GROOVE), white_f(f)), width=FLUTE_W)

        # ---- the walkway, standing in front of the wall
        d.polygon([a0, a1, e1, e0], fill=shade(FLOOR, f * 0.94))
        d.line([a0, a1], fill=shade(FLOOR_SH, f), width=1)
        # THE BENCHES GO HERE, not in the feature loop: up on this
        # level the walkway is painted AFTER the wall, so a bench
        # drawn with the doors would end up underneath its own floor —
        # and its contact shadow, which is the whole anchor, with it.
        for bt in benches:
            bench_at(d, e0, e1, bt, f)

        # ---- the rail at its inner edge (nearest, so last): the
        # SAME railing as the well one storey down — kerb, open dark
        # pickets, koa cap (2026-08-27, user: "why doesnt it just
        # look like the second floor railings?"). The five-state
        # history lives in upper_parapet's docstring — read it
        # before changing this again.
        upper_parapet(d, a0, a1, f)

    # ---- THE DIAMOND HEAD WING (see WING_EXT): this storey runs on
    # past the E corner. Same bands, same walkway, same parapet, in
    # the DH run's own light (f 0.97); UNNAMED filler only, so no
    # hotspot moves. Drawn in the run's own order — wall, doors, slab
    # band, walkway, bench, parapet — and phase-anchored to the run's
    # start so the flute rhythm cannot beat at the junction.
    fdh = 0.97
    w0, w1 = out[1], iso(LVL2_OUT + WING_EXT, -LVL2_OUT, LVL2_Y)
    aw0, aw1 = inn[1], iso(LVL2_IN + WING_EXT, -LVL2_IN, LVL2_Y)
    d.polygon([w0, w1, up(w1, 58), up(w0, 58)], fill=shade(CONC, fdh))
    for y in (24, 41):
        d.line([up(w0, y), up(w1, y)],
               fill=shade(CONC, fdh * 0.90), width=1)
    door_at(d, w0, w1, 0.35, "office", hw=11)
    d.polygon([up(w0, 58), up(w1, 58), up(w1, 72), up(w0, 72)],
              fill=shade(hx(FLUTE_FIELD), white_f(fdh)))
    for b in even_run(out[0], w1, FLUTE_PITCH):
        if b[0] < w0[0]:
            continue
        d.line([up(b, 59), up(b, 71)],
               fill=shade(hx(FLUTE_GROOVE), white_f(fdh)), width=FLUTE_W)
    d.polygon([aw0, aw1, w1, w0], fill=shade(FLOOR, fdh * 0.94))
    d.line([aw0, aw1], fill=shade(FLOOR_SH, fdh), width=1)
    bench_at(d, w0, w1, 0.72, fdh)
    upper_parapet(d, aw0, aw1, fdh, phase0=inn[0])
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
    for r, (e0, e1, f) in enumerate((
        (out[3], out[0], 1.0),
        (out[0], out[1], 0.88),
    )):
        feats = place_feats(r, A_OUT, col_hw(58), GALLERY_FEATS[r])
        benches = []

        def q(y0, y1, col):
            d.polygon([up(e0, y0), up(e1, y0), up(e1, y1), up(e0, y1)],
                      fill=col)
        # concrete to the foot — no pale base strip (see the same
        # removal in paint_upper_level)
        q(0, 58, shade(CONC, f))                      # concrete bays
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
        # the column, FLUSH in this wall — under the doors and under
        # the walkway and parapet that cross it (both drawn well
        # after this, at the well line a whole bay nearer the camera)
        wall_column(d, r, e0, e1, 0, 58, 0, 58, f)
        # dark bronze columns between the bays (clearance-placed —
        # see bay_columns)
        bay_columns(d, r, e0, e1, f, feats, reflect=True)
        # doors, hallway portals, elevator lobbies
        for did, t, kind in feats:
            if kind == "door":
                pos = door_at(d, e0, e1, t, "koa")
            elif kind == "office":
                pos = door_at(d, e0, e1, t, "office", hw=11)
            elif kind == "alcove":
                pos = alcove_at(d, e0, e1, t, f)
            elif kind == "bench":
                # benches LAST on this run, after every door, so the
                # seat can bite into the wall foot — that overlap is
                # the wall contact
                benches.append(t)
                continue
            else:
                pos = corridor_at(d, e0, e1, t, f,
                                  elevator=(kind == "lift"))
            if did:
                # position AND the box the runtime will make
                # clickable, from the geometry that drew it
                doors[did] = (pos, feat_rect(e0, e1, t, kind))
        for bt in benches:
            bench_at(d, e0, e1, bt, f)
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
        q(58, 72, shade(hx(FLUTE_FIELD), white_f(f)))
        for b in even_run(e0, e1, FLUTE_PITCH):
            d.line([up(b, 59), up(b, 71)],
                   fill=shade(hx(FLUTE_GROOVE), white_f(f)), width=FLUTE_W)
        # NO benches: drawn floating mid-walkway they read as brown
        # bars sitting on the railing (user-caught, removed 2026-08-22)

    # ---- THE DIAMOND HEAD WING (see WING_EXT): the gallery run
    # continues past the E corner — wall + slab in the run's own
    # light (f 0.88), unnamed filler only. The FLOOR under it is no
    # longer drawn here: since the well went rectangular (rdiamond,
    # 2026-08-26 "the railing should also reflect this new length")
    # the ring floor, sun spill, railings and slab fins all extend on
    # their own; the wing is just more wall. Form mottle keeps its
    # LOCAL generator — the shared rng textures the mosaic and both
    # walls' mottle, and the wing must not reshuffle them.
    wrng = np.random.default_rng(23)
    fw = 0.88
    out_g = diamond(A_OUT)
    w0, w1 = out_g[1], iso(A_OUT + WING_EXT, -A_OUT)
    # wall + slab, continuous with the run — pour joints at the same
    # heights, flute phase stepped from the run's own start
    d.polygon([w0, w1, up(w1, 58), up(w0, 58)], fill=shade(CONC, fw))
    for y in (24, 41):
        d.line([up(w0, y), up(w1, y)], fill=shade(CONC, fw * 0.90),
               width=1)
    for _ in range(4):                            # form mottle, local
        b = lerp(w0, w1, wrng.uniform(0.05, 0.95))
        mw = int(wrng.uniform(5, 14))
        my0 = int(wrng.uniform(12, 44))
        d.rectangle([b[0] - mw // 2, b[1] - my0 - int(wrng.integers(4, 9)),
                     b[0] + mw // 2, b[1] - my0],
                    fill=shade(CONC, fw * wrng.uniform(0.94, 1.06)))
    door_at(d, w0, w1, 0.35, "office", hw=11)
    bench_at(d, w0, w1, 0.72, fw)
    d.polygon([up(w0, 58), up(w1, 58), up(w1, 72), up(w0, 72)],
              fill=shade(hx(FLUTE_FIELD), white_f(fw)))
    for b in even_run(out_g[0], w1, FLUTE_PITCH):
        if b[0] < w0[0]:
            continue
        d.line([up(b, 59), up(b, 71)],
               fill=shade(hx(FLUTE_GROOVE), white_f(fw)), width=FLUTE_W)
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
    # the Diamond Head end rides out with the wing (see WING_EXT) —
    # the gallery wall now ends at the wing's far corner
    for c, moff in ((out[3], (-9, -5)),
                    (iso(A_OUT + WING_EXT, -A_OUT), (9, -5))):
        cut_face(d, c, up(c, 72), moff, arris=False)
        d.line([up(c, 72), (c[0] + moff[0], c[1] + moff[1] - 72)],
               fill=hx("#fffdf5"), width=2)


def paint_front_edge(d):
    """The makai edge is JUST THE WALKWAY now (2026-08-24, user:
    "don't need the walls, just showing the walkway is fine") — the
    knee-high cutaway stub walls were removed. The floor ends at the
    slab edge with its own fluted fascia hanging below, exactly the
    band the well edges wear, and nothing stands on it."""
    out = rdiamond(A_OUT)
    # THE STAIRS KEEP THEIR SPOT: the old S corner, now an ordinary
    # point on the longer SW edge (the rectangular plan has no bottom
    # apex). spawn and the (unused) exit hotspot both derive from
    # diamond(A_OUT)[2] in render(), so nothing else moves.
    s = iso(A_OUT, A_OUT)
    # SE edge — the wing's far side, one unbroken band. PLAIN, no
    # flutes: this is the sawn dollhouse cut (see fluted_band)
    fluted_band(d, out[1], out[2], 0, FASCIA_D, 0.92, flutes=False)
    # SW edge — broken at the stairs
    e0, e1 = out[2], out[3]
    span = float(e0[0] - e1[0])   # horizontal extent, px
    t_s = (e0[0] - s[0]) / span
    half = 34.0 / span
    fluted_band(d, e0, lerp(e0, e1, t_s - half), 0, FASCIA_D, 0.92,
                flutes=False)
    fluted_band(d, lerp(e0, e1, t_s + half), e1, 0, FASCIA_D, 0.92,
                flutes=False)
    # stairs down out of the room
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
    # NO free-standing column above the gallery floor any more: from
    # the second storey up the shaft is FLUSH in the wall and was
    # already painted there, by wall_column() inside paint_walls and
    # paint_upper_level. The piece below the gallery went in with
    # paint_well, where the hole mask trims it. Drawing a shaft out
    # here — on the court edge, after everything — is what put nine
    # poles in front of both balconies (user, 2026-08-25: "you're
    # misreading the columns. they should be flush with the walls on
    # the second and third floors").
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
    dpx = {k: (int(p[0]), int(p[1])) for k, (p, _) in doors.items()}
    # the mosaic goes in with the doors so it is inside the same
    # no-overlap solve, not padded against a set it isn't part of.
    # Its rect is the medallion's own ellipse (paint_mosaic: rx 62,
    # ry 32 with its kerb), which sits a little above the hotspot's
    # label anchor.
    rects = {k: r for k, (_, r) in doors.items()}
    rects["mosaic"] = (CX - 62, CY + DROP - 44, CX + 62, CY + DROP + 20)
    dz = zones_for(rects)
    meta = {
        "name": "Hawaiʻi State Capitol",
        "image": "capitol_scene.png",
        "w": W, "h": H, "scale": SS, "bg": bg,
        "spawn": [CX, int(out[2][1]) - 60],
        # LEVEL 2 IS THE SENATE'S, LEVEL 3 IS THE HOUSE'S — see the
        # note over GALLERY_FEATS/UPPER_FEATS. The text says which
        # floor you are on, because the whole point of the split is
        # that the floor tells you whose house you are in.
        "hotspots": [
            # --- level 2, the walkway the player stands on: SENATE
            dict(id="senate", name="Senate Gallery", kind="door",
                 px=dpx["senate"][0], py=dpx["senate"][1] + 6,
                 zone=dz["senate"],
                 text="Second level, and this floor is the Senate's. "
                      "The ʻEwa cone below this door: Hawaiʻi's 25 "
                      "senators under the Moon — a chandelier of 620 "
                      "chambered nautilus shells. The public watches "
                      "from up here, at the rail."),
            dict(id="wam", name="Ways & Means", kind="door",
                 px=dpx["wam"][0], py=dpx["wam"][1] + 6,
                 zone=dz["wam"],
                 text="The Senate's money committee, on the Senate's "
                      "own floor. A revenue bill that cannot clear "
                      "Ways & Means goes no further."),
            dict(id="senpres", name="Senate President", kind="door",
                 px=dpx["senpres"][0], py=dpx["senpres"][1] + 6,
                 zone=dz["senpres"],
                 text="Referrals are settled behind this door — which "
                      "committees a measure must clear before it can "
                      "reach the floor, and so how many ways it can "
                      "quietly die."),
            dict(id="senclerk", name="Senate Clerk", kind="door",
                 px=dpx["senclerk"][0], py=dpx["senclerk"][1] + 6,
                 zone=dz["senclerk"],
                 text="Every Senate measure is journaled here. What "
                      "the chamber did is whatever this office wrote "
                      "down — the journal is the record, not anyone's "
                      "memory of the vote."),
            dict(id="gov", name="Governor · Level 5", kind="door",
                 px=dpx["gov"][0], py=dpx["gov"][1] + 6,
                 zone=dz["gov"],
                 text="The elevator to Level 5, where the Governor "
                      "and Lieutenant Governor look down into the "
                      "rotunda. It belongs to neither chamber, which "
                      "is why it opens off the floor you are standing "
                      "on. The veto pen lives up there."),
            # --- level 3, the stepped-back storey above: HOUSE
            dict(id="house", name="House Gallery", kind="door",
                 px=dpx["house"][0], py=dpx["house"][1] + 6,
                 zone=dz["house"],
                 text="Third level, and this floor is the House's. "
                      "The Diamond Head cone: the 51 representatives "
                      "under the Sun, a chandelier of gold-plated "
                      "globes. Every state law begins as a bill read "
                      "in one of the two cones below."),
            dict(id="finance", name="House Finance", kind="door",
                 px=dpx["finance"][0], py=dpx["finance"][1] + 6,
                 zone=dz["finance"],
                 text="The House's money committee, on the House's "
                      "own floor — every appropriation in the state "
                      "budget passes across these tables."),
            dict(id="speaker", name="Speaker of the House",
                 kind="door",
                 px=dpx["speaker"][0], py=dpx["speaker"][1] + 6,
                 zone=dz["speaker"],
                 text="The Speaker refers every House bill to "
                      "committee and decides what reaches the floor "
                      "calendar. A measure nobody schedules is not "
                      "voted down; it simply never comes up."),
            dict(id="houseclerk", name="House Clerk", kind="door",
                 px=dpx["houseclerk"][0], py=dpx["houseclerk"][1] + 6,
                 zone=dz["houseclerk"],
                 text="Bills are filed, numbered and time-stamped "
                      "here. A measure that misses a filing deadline "
                      "by an hour is as dead as one voted down, and "
                      "this counter is where the hour is decided."),
            dict(id="mosaic", name="Aquarius", kind="poi",
                 px=CX, py=CY + DROP + 6, zone=dz["mosaic"],
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
    # NO TWO HOTSPOT ZONES MAY OVERLAP. Phaser resolves a hit by the
    # order the zones were built, so an overlap is a tap that silently
    # opens the wrong door — House Gallery and Governor overlapped by
    # 39% of a zone under the old fixed 120x84 boxes, and the lift won.
    # This is the gate on ZONE_PAD: grow the padding past what the bay
    # layout leaves clear and the build fails here instead of shipping.
    zs = [(h["id"], h["zone"]) for h in meta["hotspots"] if "zone" in h]
    for i in range(len(zs)):
        for j in range(i + 1, len(zs)):
            (ai, a), (bi, b) = zs[i], zs[j]
            ox = (a[2] + b[2]) / 2 - abs(a[0] - b[0])
            oy = (a[3] + b[3]) / 2 - abs(a[1] - b[1])
            assert ox <= 0 or oy <= 0, (
                f"hotspot zones {ai} and {bi} overlap by "
                f"{ox:.0f}x{oy:.0f} px — lower ZONE_PAD or re-space "
                f"the door schedule")
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
