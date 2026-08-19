#!/usr/bin/env python3
"""Event banner art for the session-overlay dialogues.

Two routes to a banner, both landing on 960x480 at
site/assets/events/<id>.png:

  --photo PATH   a PHOTOGRAPH (optionally with a crowd composited in by
                 an image model), letterboxed and brought into the
                 game's palette. This is the PRIMARY route — see
                 from_photo. Procedural drawing can place geometry
                 exactly but cannot paint; a photo carries real
                 materials, real light and real crowd motion for free.
  --scene ID     a procedural scene from SCENES. Full control of
                 composition, no painterly rendering. Use when no usable
                 photograph of the subject exists.

Scene coordinates are written in a 320x160 DESIGN space; output is
DISPLAY x that.

Resolving to 640 rather than rendering 320 and upscaling is not
cosmetic — it is what lets a human figure exist at all. At true
architectural scale a person is about half a storey, so a 320-wide
frame of a four-storey courtyard puts them at ~12px with a 2px head,
which cannot read as a person under any amount of shading, and which
any blur immediately melts into a blob. See opening_day for the other
two halves of that fix (crop closer, and occlude with the railings).

DISPLAY is then set so the shipped file MATCHES THE COLUMN, and the
column is measured, not remembered: the session overlay's panel is
1040px (its own override in style.css, wider than the shared 680px
panel), which leaves the banner ~986px after the panel padding, the
scene padding and the bleed. It was 640 until 2026-08-18, a figure
inherited from a ~615-652px column that the widened panel had made
obsolete years of edits ago — so every banner was being upscaled 1.54x
by the browser and reading soft. 960 lands within ~3% of the column.
Corollary either way: the CSS must NOT set image-rendering:pixelated,
because that turns a small resample into dropped rows instead of
filtered ones. If the panel width ever changes again, this number is
downstream of it — measure the rendered width of .sd-art and match.

House style (see CLAUDE.md "Session overlay"):
- ONE hard directional key light, deep shadow, colored bounce. That is
  what is borrowed from Disco Elysium — the LIGHTING logic, not the
  oil-paint brushwork, which does not survive translation to pixels.
  It is also the precise opposite of soft ambient warmth, which is the
  look we are steering away from.
- Palette locked to the overlay's own tokens so the art cannot drift:
  #0a0e18 ground, #f2c14e gold, #6fa8dc / #e8795c as the two accent
  temperatures.
- NO FACES IN FOCUS. Crowds at distance, backs, silhouettes, hands.
  One rule that buys consistency across ~20 banners, dodges uncanny AI
  faces, and keeps fictional people out of a real building.

Render pipeline: draw at 4x with PIL (which does not antialias), then
LANCZOS down to native size for free edge softening, then quantize to a
small adaptive palette WITH dithering — the dither noise is what reads
as painterly texture once it is blown up 2x.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "assets" / "events"

W, H = 320, 160          # DESIGN space — all scene coords are in this
# 160 (a 2:1 banner) — raised from 110 / 2.9:1 on 2026-08-18 (user's
# call: the banners read as too short to see in the transcript). The
# ratio is set by how much of a PHOTOGRAPH survives the letterbox,
# because the photo route is the primary one: a 4:3 source keeps 38%
# of its height at 3.5:1, ~46% at 2.9:1 and 67% at 2:1. Going taller
# is therefore not a crop decision but a "how much of the picture does
# the player actually get to see" decision, and 2:1 is the point where
# a 4:3 photo keeps two thirds of itself while the banner still fits
# the panel above the dialogue (see .sd-art's max-height in style.css,
# which was raised to 40vh in the same change and must move WITH this
# ratio — a taller file under the old clamp is just a cropped file).
# Widening past 2:1 starts pushing the transcript off the panel on a
# laptop, which is the constraint that stops this going to 16:9.
S = 4                    # supersample factor while drawing
DISPLAY = 3              # design -> output; shipped file is 960x480
PAINT_W = 1280           # fixed working width for paintify()'s brush —
                         # see paintify: this is deliberately NOT tied to
                         # DISPLAY, so a `--paint 4` recipe keeps meaning
                         # the same brush after an output-size change
COLORS = 32              # adaptive palette size after downsample


def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


# --- palette -------------------------------------------------------
# cool murky architecture + one warm punch, DE's basic bargain
INK      = hx("0a0e18")   # the overlay's own ground
SHADOW   = hx("101828")
WALL_D   = hx("18243c")
WALL_M   = hx("243756")
WALL_L   = hx("35506f")
STONE    = hx("4a6684")
HAZE     = hx("6d8fae")
SKY_HI   = hx("6d94c4")
SKY_LO   = hx("ffe3b0")
WARM_G   = hx("f0a562")   # warm daylight at the top of the light well
KEY      = hx("f2c14e")   # gold — the overlay's accent
KEY_HOT  = hx("fff0c4")
BOUNCE   = hx("6fa8dc")   # wonk blue, doubles as shadow bounce
LEI_A    = hx("e8795c")   # organizer orange
LEI_B    = hx("d9668a")
LEI_C    = hx("7fae72")


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


def sc(*vals):
    """scale 1x coords into the 4x drawing space"""
    return tuple(int(round(v * S)) for v in vals)


def poly(d, pts, fill):
    d.polygon([sc(*p) for p in pts], fill=fill)


def rect(d, x0, y0, x1, y1, fill):
    """Normalises the corners — callers build these from signed offsets
    and PIL rejects an inverted box outright."""
    d.rectangle([sc(min(x0, x1), min(y0, y1)),
                 sc(max(x0, x1), max(y0, y1))], fill=fill)


# --- the scene -----------------------------------------------------
def opening_day(rng):
    """Week 1. Inside the Capitol's open rotunda on Opening Day, looking
    DOWN and across the courtyard from an upper gallery. Busy day:
    people along every gallery rail.

    Built to a photo of the real rotunda. One-point perspective with the
    vanishing point above the frame — we are above everything we can
    see, so every gallery line rakes down and out toward the viewer.

    THE CROWD IS THE HARD PART, and two constraints fight each other.
    At true architectural scale a person is about half a storey tall, so
    showing the whole four-storey well puts them at ~12px — a head of 2
    pixels, which cannot read as a person no matter how it is shaded,
    and which any blur immediately melts into the torso. So this crops
    CLOSER than the reference: three bands instead of five, which buys
    roughly double the figure height. The other half of the fix is draw
    order — the railings are painted back OVER the crowd, so we see
    torsos and heads above a rail rather than whole free-standing
    figures. A head and shoulders above a balcony rail reads as a person
    instantly; a complete tiny body reads as a bottle on a shelf.

    Figures stay faceless and are softened only slightly. 'Vague' has to
    come from anonymity, not from blur — blur at this size destroys the
    head/shoulder separation that is doing all the work."""
    img = Image.new("RGB", (W * S, H * S), INK)
    d = ImageDraw.Draw(img)

    VPX, VPY = 150, -6             # eye level, above the top of the frame
    FL, FR = 52, 250               # the far wall's two corners
    LX, RX = -30, 350              # where the side walls leave the frame
    FLOOR_Y = 80                   # far wall meets the courtyard floor

    SKY_B, BEAM_B = 3.5, 8.0       # daylight strip, then the roof beam
    COL_B = 20.0                   # bottom of the top colonnade
    GAL = [COL_B, 44.0, 68.0]      # two full rail galleries below it
    GND_B = GAL[-1]                # ground arcade runs GND_B -> FLOOR_Y
    RAILF = 0.66                   # where the rail starts within a band

    def ray_y(cy, tx, cx):
        """y of the perspective ray through (cx, cy), at x = tx"""
        return VPY + (cy - VPY) * ((tx - VPX) / (cx - VPX))

    def quad(side, y0, y1):
        if side == "far":
            return [(FL, y0), (FR, y0), (FR, y1), (FL, y1)]
        if side == "left":
            return [(FL, y0), (LX, ray_y(y0, LX, FL)),
                    (LX, ray_y(y1, LX, FL)), (FL, y1)]
        return [(FR, y0), (RX, ray_y(y0, RX, FR)),
                (RX, ray_y(y1, RX, FR)), (FR, y1)]

    def rail_line(side, y):
        """the gallery line as (x0,y0,x1,y1), corner -> frame edge"""
        if side == "left":
            return FL, y, LX, ray_y(y, LX, FL)
        if side == "right":
            return FR, y, RX, ray_y(y, RX, FR)
        return FL, y, FR, y

    SIDES = ("far", "left", "right")
    SHADE = {"far": 0.96, "left": 1.00, "right": 0.82}
    GLOOM = hx("141a28")

    def sh(c, side):
        return mix(GLOOM, c, SHADE[side])

    # The reference is a BRIGHT daylit space — pale concrete, midday.
    SKYC   = hx("fff3da")
    BEAM   = hx("e6dfca")
    POST   = hx("dbd4bf")
    RECESS = hx("242938")
    RAIL   = hx("d5cdb6")
    DOOR   = hx("7d5734")
    PIER   = hx("5b6270")
    FLOORC = hx("565b66")
    PLANT  = hx("567a4c")

    # 1. daylight over the far parapet, and the towers beyond
    rect(d, 0, 0, W, SKY_B, SKYC)
    for _ in range(24):
        bx, bw = rng.uniform(0, W), rng.uniform(3, 11)
        rect(d, bx, rng.uniform(0, 1.8), bx + bw, SKY_B,
             mix(SKYC, HAZE, rng.uniform(0.25, 0.6)))
    rect(d, 0, SKY_B - 0.9, W, SKY_B, mix(SKYC, WARM_G, 0.45))

    # 2. roof beam
    for side in SIDES:
        poly(d, quad(side, SKY_B, BEAM_B), sh(BEAM, side))
        poly(d, quad(side, BEAM_B, BEAM_B + 1.1),
             sh(mix(BEAM, GLOOM, 0.45), side))

    # 3. top colonnade — thin posts against the dark, the detail that
    #    dates the building
    for side in SIDES:
        poly(d, quad(side, BEAM_B, COL_B), sh(RECESS, side))
        x0, ya, x1, yb = rail_line(side, BEAM_B)
        _, yc, _, yd = rail_line(side, COL_B)
        n = 15 if side == "far" else 16
        for k in range(n):
            u = ((k + 0.5) / n) ** (1.0 if side == "far" else 1.7)
            px = lerp(x0, x1, u)
            wd = lerp(1.1, 3.0, 0.0 if side == "far" else u)
            poly(d, [(px, lerp(ya, yb, u)), (px + wd, lerp(ya, yb, u)),
                     (px + wd, lerp(yc, yd, u)), (px, lerp(yc, yd, u))],
                 sh(POST, side))

    # 4. the rail galleries: dark recess with doors, rail drawn LATER
    for i in range(len(GAL) - 1):
        y0, y1 = GAL[i], GAL[i + 1]
        rl = y0 + (y1 - y0) * RAILF
        for side in SIDES:
            poly(d, quad(side, y0, rl), sh(RECESS, side))
            x0, ya, x1, yb = rail_line(side, y0)
            _, yc, _, yd = rail_line(side, rl)
            n = 8 if side == "far" else 9
            for k in range(n):
                u0, u1 = (k + 0.16) / n, (k + 0.74) / n
                if side != "far":
                    u0, u1 = u0 ** 1.7, u1 ** 1.7
                poly(d, [(lerp(x0, x1, u0), lerp(ya, yb, u0) + 0.8),
                         (lerp(x0, x1, u1), lerp(ya, yb, u1) + 0.8),
                         (lerp(x0, x1, u1), lerp(yc, yd, u1)),
                         (lerp(x0, x1, u0), lerp(yc, yd, u0))],
                     sh(mix(DOOR, RECESS, rng.uniform(0.12, 0.5)), side))

    # 5. ground level: heavy piers, dark arcade behind
    for side in SIDES:
        poly(d, quad(side, GND_B, FLOOR_Y), sh(RECESS, side))
        x0, ya, x1, yb = rail_line(side, GND_B)
        _, yc, _, yd = rail_line(side, FLOOR_Y)
        n = 6 if side == "far" else 7
        for k in range(n):
            u = ((k + 0.5) / n) ** (1.0 if side == "far" else 1.7)
            px = lerp(x0, x1, u)
            wd = lerp(3.0, 8.0, 0.0 if side == "far" else u)
            poly(d, [(px, lerp(ya, yb, u)), (px + wd, lerp(ya, yb, u)),
                     (px + wd, lerp(yc, yd, u)), (px, lerp(yc, yd, u))],
                 sh(PIER, side))

    # 6. courtyard floor, opening toward the viewer
    t_b = (H - VPY) / (FLOOR_Y - VPY)
    bl = VPX + (FL - VPX) * t_b
    br = VPX + (FR - VPX) * t_b
    poly(d, [(FL, FLOOR_Y), (FR, FLOOR_Y), (br, H), (bl, H)], FLOORC)
    poly(d, [(FL, FLOOR_Y), (FR, FLOOR_Y),
             (lerp(FR, br, 0.45), lerp(FLOOR_Y, H, 0.45)),
             (lerp(FL, bl, 0.45), lerp(FLOOR_Y, H, 0.45))],
         mix(FLOORC, GLOOM, 0.30))
    poly(d, [(130, 84.5), (176, 84.5), (186, 92), (120, 92)],
         mix(FLOORC, GLOOM, 0.50))
    for _ in range(26):
        cx, cy = rng.gauss(153, 10), rng.gauss(88, 2.4)
        r = rng.uniform(1.8, 4.0)
        d.ellipse([sc(cx - r, cy - r * 0.7), sc(cx + r, cy + r * 0.7)],
                  fill=mix(PLANT, GLOOM, rng.uniform(0.0, 0.4)))

    # 7. THE CROWD, on its own layer
    crowd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(crowd)

    def figure(cx, feet, s, body, alpha):
        """head / shoulders / body, narrowing downward. The head must be
        SMALL — about 45% of shoulder width. A wide blob with a bulb on
        top is a bottle, and a rail lined with them is a shelf."""
        hh, hw = s * 0.60, s * 0.40
        th, tw = s * 1.30, s * 0.92
        lh, lw = s * 1.10, s * 0.50
        cd.rectangle([sc(cx - lw / 2, feet - lh), sc(cx + lw / 2, feet)],
                     fill=body + (alpha,))
        cd.rectangle([sc(cx - tw / 2, feet - lh - th),
                      sc(cx + tw / 2, feet - lh)], fill=body + (alpha,))
        cd.ellipse([sc(cx - hw / 2, feet - lh - th - hh),
                    sc(cx + hw / 2, feet - lh - th)],
                   fill=mix(body, hx("b09a7e"), 0.44) + (alpha,))

    def people(side, y, n, lo, hi, dark, sink):
        x0, ya, x1, yb = rail_line(side, y)
        for _ in range(n):
            v = rng.random()
            u = v if side == "far" else v ** 1.55
            px, py = lerp(x0, x1, u), lerp(ya, yb, u)
            s = lerp(lo, hi, 0.0 if side == "far" else u) * rng.uniform(.85, 1.2)
            body = mix(hx("4e5665"), GLOOM, dark * 0.35)
            if rng.random() < 0.20:            # an aloha shirt or a lei
                body = mix(rng.choice((LEI_A, LEI_B, LEI_C)), GLOOM, 0.18)
            # feet sit BELOW the rail top: the rail is repainted over
            # this layer, so what survives is head and torso over a rail
            figure(px, py + sink + rng.uniform(-0.3, 0.4), s, body,
                   rng.randint(230, 255))

    for i in range(len(GAL) - 1):
        y0, y1 = GAL[i], GAL[i + 1]
        rl = y0 + (y1 - y0) * RAILF
        sink = (y1 - rl) * 0.62
        people("far", rl, 13, 3.9, 3.9, 0.55, sink)
        people("left", rl, 15, 3.9, 6.2, 0.42, sink)
        people("right", rl, 13, 3.9, 6.0, 0.72, sink)
    # up on the top colonnade, and down on the courtyard floor
    people("far", COL_B, 9, 3.4, 3.4, 0.60, -1.0)
    people("left", COL_B, 10, 3.4, 5.2, 0.48, -1.0)
    people("right", COL_B, 9, 3.4, 5.0, 0.75, -1.0)
    for _ in range(12):
        px = rng.uniform(bl + 10, br - 10)
        py = rng.uniform(FLOOR_Y + 3, H - 1)
        s = lerp(3.4, 5.6, (py - FLOOR_Y) / (H - FLOOR_Y))
        figure(px, py, s, mix(hx("4e5665"), GLOOM, 0.26), 245)

    # only a whisker of softening — see the docstring
    crowd = crowd.filter(ImageFilter.GaussianBlur(0.16 * S))
    img = Image.alpha_composite(img.convert("RGBA"), crowd).convert("RGB")
    d = ImageDraw.Draw(img)

    # 8. the railings, painted back OVER the crowd so the galleries
    #    occlude everyone's legs. This is what makes them read as
    #    people leaning on a balcony instead of free-standing dolls.
    for i in range(len(GAL) - 1):
        y0, y1 = GAL[i], GAL[i + 1]
        rl = y0 + (y1 - y0) * RAILF
        for side in SIDES:
            poly(d, quad(side, rl, y1), sh(RAIL, side))
            poly(d, quad(side, rl, rl + 1.0), sh(mix(RAIL, SKYC, 0.5), side))
            poly(d, quad(side, y1 - 0.9, y1), sh(mix(RAIL, GLOOM, 0.5), side))

    # 9. grade: the well darkens downward, and the near ends of the side
    #    walls fall away at the frame edges
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(int(SKY_B * S), H * S):
        t = (y - SKY_B * S) / ((H - SKY_B) * S)
        gd.line([(0, y), (W * S, y)], fill=GLOOM + (int(58 * t ** 1.5),))
    img = Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")

    side_g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sg = ImageDraw.Draw(side_g)
    for x in range(W * S):
        u = max(0.0, (abs(x / S - 158) - 88) / 74)
        if u > 0:
            sg.line([(x, 0), (x, H * S)],
                    fill=GLOOM + (int(88 * min(1.0, u) ** 1.35),))
    img = Image.alpha_composite(img.convert("RGBA"), side_g).convert("RGB")

    return img


SCENES = {"w1-opening": opening_day}


def finish(img):
    """Supersampled draw -> OUTPUT resolution, then quantize. The dither
    IS the texture.

    Output is DISPLAY x the design space, resolved here rather than by a
    nearest upscale at the end. That distinction is the whole reason the
    crowd reads: a person standing at a gallery rail is about 2px wide in
    DESIGN space, and no amount of blurring or shading makes 2px look
    like a person. Resolving straight to 640 gives every figure double
    the pixels — head, shoulders and body each get their own — while the
    architecture keeps the same proportions."""
    OW, OH = W * DISPLAY, H * DISPLAY
    img = img.resize((OW, OH), Image.LANCZOS)

    # vignette: settle the banner into the dark column. Deliberately
    # gentle — the scene already grades its own edges, and stacking the
    # two is what turned the daylit reference into a dungeon.
    vig = Image.new("L", (OW, OH), 0)
    ImageDraw.Draw(vig).ellipse([-OW * 0.45, -OH * 0.9,
                                 OW * 1.45, OH * 1.9], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(OW * 0.055))
    img = Image.blend(
        Image.composite(img, Image.new("RGB", (OW, OH), INK), vig), img, 0.45)

    # grain, pre-quantize, so the palette absorbs it as texture
    arr = np.array(img).astype(np.int16)
    noise = np.random.RandomState(11).randint(-4, 5, arr.shape[:2])[:, :, None]
    img = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

    return img.quantize(colors=COLORS, method=Image.MEDIANCUT,
                        dither=Image.FLOYDSTEINBERG).convert("RGB")


def paintify(img, radius=4, strength=0.55, work_width=None,
             soften=None, soften_radius=None, soften_strength=0.6):
    """Nudge a photograph toward PAINTED, not just colour-graded.

    Requires opencv-contrib (`pip3 install opencv-contrib-python-headless`
    — the plain opencv-python package lacks `cv2.xphoto`). Import is
    local so --photo without --paint never needs it installed.

    The brush radius has to be judged at PROPORTION to the frame, not
    to the source photo. `cv2.xphoto.oilPainting(src, 6, 1)` run on a
    2390px source is invisible — a 6px brush is a rounding error at that
    scale. So the pass runs at PAINT_W wide, then resizes to output.

    PAINT_W is a FIXED width and not a multiple of the output on
    purpose. It used to be `2 * output width`, which quietly made every
    radius in every recorded recipe a function of DISPLAY: raising
    DISPLAY 2 -> 3 on 2026-08-18 would have shrunk every brush by a
    third — the same banner, rebuilt from the same command, coming out
    visibly less painted. Radius is meant to be a unit the recipes in
    data/raw/events/BANNERS.md can carry, so it is now anchored to a
    resolution that does not move. `work_width` overrides it for a
    caller that genuinely wants a different brush scale.

    TWO dials, and `strength` is the important one. Radius alone is a
    bad mildness control: dropping it just makes the strokes small and
    busy, which reads as a noisy photo rather than a gentle painting.
    Blending the fully-painted result back over the original keeps the
    stroke SHAPE while letting photographic detail show through, which
    is what "mild painterly" actually means. Radius 4 + strength ~0.5
    is a light touch; strength 1.0 at radius 8 is the full poster-paint
    effect, which flattens far too much for this use.

    `soften` is a box (x0, y0, x1, y1) in FRACTIONS OF THIS FRAME that
    gets a much heavier pass of the SAME brush, feathered in through an
    ellipse. It exists for the one case the house "no faces in focus"
    rule cannot dodge: a named character who has to be looking at the
    player. Painting the face harder is not the same as blurring it —
    blur reads as a redaction bar and destroys the head/shoulder
    separation the figure depends on, whereas a bigger brush keeps the
    features' PLACEMENT and light while dissolving the identity, which
    is what the rest of the banner is already doing to every crowd
    figure. Feather radius is tied to the box width so it scales with
    however big the face lands in frame."""
    import cv2

    ow, oh = W * DISPLAY, H * DISPLAY
    ww = int(work_width or PAINT_W)
    work = img.resize((ww, int(round(ww * oh / ow))), Image.LANCZOS)
    bgr = cv2.cvtColor(np.array(work), cv2.COLOR_RGB2BGR)
    painted = cv2.xphoto.oilPainting(bgr, radius, 1)
    out = Image.fromarray(cv2.cvtColor(painted, cv2.COLOR_BGR2RGB))
    if strength < 1.0:
        out = Image.blend(work, out, max(0.0, strength))

    if soften:
        # judged against the frame, like `radius` itself: the brush has
        # to be a real fraction of the FACE, not of the photograph
        fw, fh = work.size
        x0, y0, x1, y1 = (f * d for f, d in zip(soften, (fw, fh, fw, fh)))
        r = soften_radius or max(radius * 2, int((x1 - x0) * 0.07), 6)
        heavy = cv2.xphoto.oilPainting(bgr, r, 1)
        heavy = Image.fromarray(cv2.cvtColor(heavy, cv2.COLOR_BGR2RGB))
        # peak alpha BELOW 1 is what keeps this a face. Composited at
        # full strength the brush does not soften the features, it
        # deletes them — the head goes to a blank oval, which is more
        # uncanny than the sharp face was and destroys the silhouette
        # that makes him read as a person at all. ~0.6 leaves eyes and
        # mouth as suggestions: placement and light survive, identity
        # does not.
        mask = Image.new("L", work.size, 0)
        ImageDraw.Draw(mask).ellipse([x0, y0, x1, y1],
                                     fill=int(255 * soften_strength))
        mask = mask.filter(ImageFilter.GaussianBlur((x1 - x0) * 0.24))
        out = Image.composite(heavy, out, mask)

    return out.resize((ow, oh), Image.LANCZOS)


def from_photo(path, center=0.42, grade=None, colors=None, paint=None,
              dither=None, noise=None, paint_strength=0.55, soften=None,
              soften_radius=None, soften_strength=0.6):
    """Bring a PHOTOGRAPH into the banner style.

    The procedural scenes below can nail perspective but cannot paint;
    a reference photo (optionally with a crowd composited in by an image
    model) carries real materials, real light and real crowd motion. All
    this has to do is make it belong to the game: letterbox-crop it,
    optionally run it through paintify(), resolve to output size, nudge
    it a few percent toward the overlay's palette, and quantize so it
    carries the same limited palette as everything else.

    Unpainted vs. painted want OPPOSITE finishing, which is why grade/
    colors/dither/noise all default to None and get resolved below
    rather than sharing one constant default:
    - Unpainted: dithering is what makes a small palette look like
      texture instead of banding on a photo's smooth gradients.
    - Painted: oilPainting has already flattened the photo into broad
      colour regions — dithering on TOP of that reintroduces exactly
      the per-pixel noise the paint filter exists to remove, muddying
      the brushstrokes back toward "photo with a filter" instead of
      "painting." Off + a bigger palette keeps the flat regions clean.
    Grade is small either way. The point of going to a photo was
    realism; pushing it hard toward the navy/gold tokens just reinvents
    the stylisation that made the procedural version look wrong — and
    when painted, oilPainting is already doing most of that work.
    `center` picks which horizontal band of the source survives the
    letterbox crop (0 = top, 1 = bottom).

    `soften` is given in fractions of the SOURCE photograph and mapped
    through the crop here, so that pointing at a face is a fact about
    the photo and survives any later change to `center`."""
    if grade is None:
        grade = 0.05 if paint else 0.16
    heavy = bool(paint) and paint_strength >= 0.85
    if colors is None:
        colors = 96 if heavy else COLORS
    if dither is None:
        # only a FULLY painted image has flat regions that dithering
        # would muddy; a mild blend still has photographic gradients
        # that need dithering to survive a small palette
        dither = not heavy
    if noise is None:
        noise = 1 if heavy else 3

    OW, OH = W * DISPLAY, H * DISPLAY
    src = Image.open(path).convert("RGB")

    # letterbox crop to the banner aspect, keeping `center` of the frame
    want = OW / OH
    cw, ch = src.width, int(round(src.width / want))
    if ch > src.height:                       # source is wider than the crop
        ch, cw = src.height, int(round(src.height * want))
    x0 = (src.width - cw) // 2
    y0 = int(round((src.height - ch) * min(1.0, max(0.0, center))))
    img = src.crop((x0, y0, x0 + cw, y0 + ch))
    if soften:                                # source fractions -> crop
        sx0, sy0, sx1, sy1 = soften
        soften = ((sx0 * src.width - x0) / cw, (sy0 * src.height - y0) / ch,
                  (sx1 * src.width - x0) / cw, (sy1 * src.height - y0) / ch)
    img = (paintify(img, paint, paint_strength, soften=soften,
                    soften_radius=soften_radius,
                    soften_strength=soften_strength) if paint else
           img.resize((OW, OH), Image.LANCZOS))

    # a few percent toward the overlay's own ground so the banner sits
    # in the panel rather than on top of it
    arr = np.array(img).astype(np.float32)
    arr = arr * (1 - grade) + np.array(mix(INK, BOUNCE, 0.22),
                                       dtype=np.float32) * grade
    if noise:
        n = np.random.RandomState(11).randint(-noise, noise + 1, arr.shape[:2])
        arr = arr + n[:, :, None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    vig = Image.new("L", (OW, OH), 0)
    ImageDraw.Draw(vig).ellipse([-OW * 0.45, -OH * 0.9,
                                 OW * 1.45, OH * 1.9], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(OW * 0.055))
    img = Image.blend(
        Image.composite(img, Image.new("RGB", (OW, OH), INK), vig), img, 0.45)

    return img.quantize(
        colors=colors, method=Image.MEDIANCUT,
        dither=Image.FLOYDSTEINBERG if dither else Image.Dither.NONE
    ).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="w1-opening", choices=sorted(SCENES))
    ap.add_argument("--id", metavar="EVENT_ID",
                    help="output as site/assets/events/<EVENT_ID>.png. "
                         "Required for a --photo banner of a NEW event: "
                         "the filename otherwise comes from --scene, "
                         "which would overwrite an existing banner.")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--preview", type=int, default=0,
                    help="also write a Nx nearest-neighbour preview")
    ap.add_argument("--photo", metavar="PATH",
                    help="build the banner from a photograph instead of "
                         "the procedural scene")
    ap.add_argument("--center", type=float, default=0.42,
                    help="--photo: which horizontal band survives the "
                         "letterbox crop, 0=top 1=bottom")
    ap.add_argument("--grade", type=float, default=None,
                    help="--photo: how far to pull toward the overlay "
                         "palette, 0-1. Keep it small. Default 0.16, "
                         "or 0.05 with --paint (oilPainting already "
                         "does most of that work).")
    ap.add_argument("--colors", type=int, default=None,
                    help="palette size (default %d, or 96 with --paint "
                         "— a bigger palette keeps oilPainting's flat "
                         "regions clean)" % COLORS)
    ap.add_argument("--paint-strength", type=float, default=0.55,
                    metavar="0-1",
                    help="--paint: how far to blend the painted result "
                         "over the original. THIS is the mildness dial; "
                         "radius alone just makes strokes small and busy. "
                         "0.4-0.6 = a light touch, 1.0 = full poster paint.")
    ap.add_argument("--paint", type=int, default=None, metavar="RADIUS",
                    help="--photo: run through the oil-paint filter at "
                         "this brush radius (try 6-10) before grading — "
                         "this is what makes it look PAINTED rather "
                         "than a colour-graded photo. Needs "
                         "opencv-contrib-python-headless.")
    ap.add_argument("--soften", metavar="X0,Y0,X1,Y1",
                    help="--paint: give this box a much heavier pass of "
                         "the same brush, feathered through an ellipse. "
                         "Four fractions of the SOURCE photo (0-1). For "
                         "a named character's face, where the 'no faces "
                         "in focus' rule cannot be met by turning them "
                         "away. Blur would read as a redaction bar; a "
                         "bigger brush dissolves the identity while "
                         "keeping the features' placement and light.")
    ap.add_argument("--soften-radius", type=int, default=None,
                    help="--soften: brush radius for that box (default "
                         "scales with the box's width)")
    ap.add_argument("--soften-strength", type=float, default=0.6,
                    metavar="0-1",
                    help="--soften: peak opacity of the heavy pass. Keep "
                         "it BELOW 1: at full strength the brush deletes "
                         "the features instead of softening them and the "
                         "head becomes a blank oval.")
    ap.add_argument("--no-dither", action="store_true",
                    help="--photo: skip Floyd-Steinberg (default off "
                         "already when --paint is set)")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    eid = a.id or a.scene
    if a.photo:
        dither = False if a.no_dither else None
        soften = tuple(float(v) for v in a.soften.split(",")) if a.soften else None
        img = from_photo(a.photo, a.center, a.grade, a.colors, a.paint,
                         dither=dither, paint_strength=a.paint_strength,
                         soften=soften, soften_radius=a.soften_radius,
                         soften_strength=a.soften_strength)
    else:
        img = finish(SCENES[a.scene](random.Random(a.seed)))
    p = OUT / f"{eid}.png"
    img.save(p)
    print(f"wrote {p.relative_to(ROOT)}  {img.width}x{img.height}"
          f"  (design {W}x{H} @{DISPLAY}x)")

    if a.preview:
        n = a.preview
        q = OUT / f"{eid}@{n}x.png"
        img.resize((img.width * n, img.height * n), Image.NEAREST).save(q)
        print(f"wrote {q.relative_to(ROOT)}  {img.width * n}x{img.height * n}")


if __name__ == "__main__":
    main()
