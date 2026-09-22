#!/usr/bin/env python3
"""PLAN-SPACE FLOOR GEOMETRY for the baked rooms — the walkmask and the
iso basis that a moving player character needs, emitted BY the bake.

WHY THIS EXISTS AT ALL. Every room is a painting: the walls, the
railings and the floor are pixels in a PNG, so nothing at runtime knows
where the floor is. A character that walks needs two facts the painters
already hold and have never written down:

  BASIS  the room's own 2:1 projection — `iso(u, v, dy)`. The character
         lives in PLAN coordinates (u, v) and is projected through this,
         never positioned in screen px. Same rule as the island map's
         `lonlat_to_cell()`: one transform, one source. A room's basis
         is NOT shared — the hallway runs 40x20 px per unit against the
         Capitol's 16x8 — so it is exported per bake, not hardcoded in
         main.js.
  WALK   where the feet may go, as plan-space regions: `allow` floors
         minus `block` obstacles.

AND WHY IT IS DERIVED RATHER THAN DRAWN BY HAND. The isometric render
is still moving — storeys, wing extensions, corridor widths and CY have
all shifted in the last month, and each of those moves the floor. A
hand-authored collision map would silently stop matching the picture on
the first re-bake, and the failure mode is a player walking through a
wall. So a room declares its floor from the SAME constants the painters
use (U0/U1/VH for the hallway, A_IN/A_OUT/WING_EXT for the Capitol) and
`check()` refuses to ship a bake whose geometry has come apart.

Units are PLAN units throughout, and they are very nearly metres in
both rooms (the hallway is 2.9 units wall to wall; the Capitol's
gallery balcony is 2.5 units deep), which is what lets one physical
character radius serve both.
"""

from __future__ import annotations

import math

# A standing person's collision radius, in plan units. Feet and body,
# not shoulders — you brush past a planter, you do not bounce off it at
# arm's length. ~0.3 m at the ~1 unit/m both rooms happen to share.
PAD = 0.3


class Basis:
    """A room's 2:1 iso projection, and its inverse at floor level.

    The forward half must agree with the renderer's own `iso()` — that
    is asserted in `check()` rather than trusted, because the whole
    point of exporting it is that the runtime and the painters cannot
    drift into two different rooms.
    """

    def __init__(self, cx, cy, sx, sy):
        self.cx, self.cy, self.sx, self.sy = cx, cy, float(sx), float(sy)

    def px(self, u, v, dy=0.0):
        """Plan -> scene px. No snapping: this is the analytic transform
        the runtime gets. The painters snap to their own draw grid."""
        return (self.cx + self.sx * (u - v),
                self.cy + self.sy * (u + v) - dy)

    def plan(self, x, y):
        """Scene px -> plan, AT FLOOR LEVEL (dy = 0).

        This is the half that makes tap-to-walk possible: it answers
        "which point of the floor did that click land on". It is only
        valid for dy = 0 — a click on a wall resolves to the floor
        point behind it, which is the correct reading for a walk
        target and the wrong one for anything else.
        """
        du = (x - self.cx) / self.sx          # u - v
        dv = (y - self.cy) / self.sy          # u + v
        return ((dv + du) / 2.0, (dv - du) / 2.0)

    def json(self):
        return {"cx": self.cx, "cy": self.cy, "sx": self.sx, "sy": self.sy}


def rect(u0, u1, v0, v1):
    """An axis-aligned region in PLAN space. Renders as a diamond (or,
    with unequal sides, the elongated diamond `rdiamond` draws) — which
    is why both rooms' floors are expressible this way: a corridor, a
    recess and a gallery ring are all plan rectangles."""
    return {"t": "rect", "u0": min(u0, u1), "u1": max(u0, u1),
            "v0": min(v0, v1), "v1": max(v0, v1)}


def disc(u, v, r):
    """A round obstacle in PLAN space — a planter, a pot, a person."""
    return {"t": "disc", "u": u, "v": v, "r": r}


def disc_from_px(basis, u, v, x_half):
    """A disc sized from the half-WIDTH IN SCENE PX of the thing the
    painter actually drew, so an obstacle's radius follows its art
    instead of being re-guessed.

    A plan disc of radius r projects to an ellipse whose x semi-axis is
    `sx * r * sqrt(2)` (the extreme is at u = -v), so that inverts to
    r = x_half / (sx * sqrt(2)). For the square stone planters the
    painters draw as diamonds this returns the CIRCUMSCRIBED radius,
    which is the conservative reading and the right one for collision.
    """
    return disc(u, v, x_half / (basis.sx * math.sqrt(2.0)))


def _inside(reg, u, v, grow=0.0):
    if reg["t"] == "rect":
        return (reg["u0"] - grow <= u <= reg["u1"] + grow and
                reg["v0"] - grow <= v <= reg["v1"] + grow)
    return math.hypot(u - reg["u"], v - reg["v"]) <= reg["r"] + grow


def _rect_corners(reg):
    return ((reg["u0"], reg["v0"]), (reg["u1"], reg["v0"]),
            (reg["u1"], reg["v1"]), (reg["u0"], reg["v1"]))


def _corners(reg):
    """Plan corners of any region — a disc's bounding box will do, since
    every caller wants an extent rather than an exact outline."""
    if reg["t"] == "rect":
        return _rect_corners(reg)
    u, v, r = reg["u"], reg["v"], reg["r"]
    return ((u - r, v - r), (u + r, v - r), (u + r, v + r), (u - r, v + r))


def _overlaps(a, b):
    """Does region `b` touch rect `a`? Both shapes, because an obstacle
    may be a planter (disc) or the rotunda well itself (rect)."""
    if b["t"] == "rect":
        return not (b["u1"] < a["u0"] or b["u0"] > a["u1"]
                    or b["v1"] < a["v0"] or b["v0"] > a["v1"])
    cu = min(max(b["u"], a["u0"]), a["u1"])      # nearest point in rect
    cv = min(max(b["v"], a["v0"]), a["v1"])
    return math.hypot(b["u"] - cu, b["v"] - cv) <= b["r"]


class Walk:
    """The floor: `allow` regions minus `block` regions.

    `ok()` takes the character's radius rather than baking it in — the
    floor is a fact about the room and the radius is a fact about the
    character, and the two change on different clocks. Insetting the
    allow regions and growing the blocks by the same radius is the
    standard configuration-space treatment: it turns "does this body
    fit" into "is this point inside", which is what a path search wants.
    """

    def __init__(self, allow, block=(), spawn=(0.0, 0.0), pad=PAD):
        self.allow = list(allow)
        self.block = list(block)
        self.spawn = (float(spawn[0]), float(spawn[1]))
        self.pad = pad

    def ok(self, u, v, pad=None):
        """Can a body of radius `pad` stand centred on (u, v)?

        THE INSET IS AGAINST THE UNION, NOT AGAINST EACH REGION. This
        is the whole subtlety of the test and it is easy to get wrong:
        shrinking every rectangle by the radius and asking whether the
        point is inside any of them opens a SEAM wherever two floors
        abut, because neither shrunken rectangle covers their shared
        edge any more. The hallway's alcove meets its corridor on a
        straight join, and the first version of this severed the two —
        the connectivity check caught it, reporting a floor in two
        pieces with 78% reachable.

        So the character's own disc has to fit inside the UNION: the
        centre and its whole perimeter must each land on some region.
        Sampled rather than solved, because the regions are few and an
        analytic distance-to-union-boundary buys nothing here; 15 deg
        steps resolve any notch wider than 0.08 units at the default
        radius, well under anything the painters can draw.
        """
        p = self.pad if pad is None else pad
        if not any(_inside(a, u, v) for a in self.allow):
            return False
        if p > 0:
            for k in range(0, 360, 15):
                th = math.radians(k)
                if not any(_inside(a, u + p * math.cos(th),
                                   v + p * math.sin(th))
                           for a in self.allow):
                    return False
        return not any(_inside(b, u, v, p) for b in self.block)

    def json(self):
        # rounded so the committed JSON diffs legibly — a derived radius
        # like 0.4596194077712559 is float noise, not information, and
        # 4 places is ~0.1 mm at these scales.
        def r4(reg):
            return {k: (round(v, 4) if isinstance(v, float) else v)
                    for k, v in reg.items()}
        return {"allow": [r4(a) for a in self.allow],
                "block": [r4(b) for b in self.block],
                "spawn": [round(self.spawn[0], 3), round(self.spawn[1], 3)],
                "pad": self.pad}

    def bbox_px(self, basis):
        """Screen bbox of the raw (un-inset) walkable floor."""
        xs, ys = [], []
        for a in self.allow:
            for u, v in _rect_corners(a):
                x, y = basis.px(u, v)
                xs.append(x)
                ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys))


def approach(walk, u, v, step=0.05, limit=3.0):
    """The nearest point to (u, v) the character can actually stand on.

    A door's own position is ON the wall, which is the one place nobody
    can stand, so "walk to that door" has to mean "walk to the floor in
    front of it". Spiralling out from the feature rather than stepping
    along a hand-named normal is deliberate: a door, a lift lobby, an
    alcove mouth and a person standing in a recess all want different
    directions, and the floor already knows which way is open.

    Returns None if nothing within `limit` works — which is a bake
    error, not a runtime one, and `check()` says so.
    """
    if walk.ok(u, v):
        return (u, v)
    r = step
    while r <= limit:
        n = max(8, int(2 * math.pi * r / step))
        best = None
        for k in range(n):
            th = 2 * math.pi * k / n
            pu, pv = u + r * math.cos(th), v + r * math.sin(th)
            if walk.ok(pu, pv):
                d = math.hypot(pu - u, pv - v)
                if best is None or d < best[0]:
                    best = (d, pu, pv)
        if best:
            return (round(best[1], 3), round(best[2], 3))
        r += step
    return None


def check(name, basis, walk, iso, view=None, sample=0.1, targets=None):
    """Refuse to ship a bake whose plan geometry has come apart.

    This is the whole reason the export is safe to iterate against. It
    is deliberately loud rather than clever: each failure names the
    constant that moved.
    """
    # 1. The exported basis IS the renderer's own iso(). Everything else
    #    here is meaningless if these two have drifted.
    for u, v in ((0, 0), (3.5, -2.25), (-7.5, 4.0), (11.0, 9.5)):
        want = iso(u, v)
        got = basis.px(u, v)
        if abs(want[0] - got[0]) > 0.5 or abs(want[1] - got[1]) > 0.5:
            raise AssertionError(
                f"{name}: exported basis disagrees with iso() at "
                f"({u}, {v}): iso {want} vs basis {got} — CX/CY/SX/SY "
                f"and iso() must come from the same constants")

    # 2. The inverse must round-trip, or tap-to-walk lands elsewhere.
    for u, v in ((0, 0), (5.0, -3.0), (-9.0, 7.0)):
        ru, rv = basis.plan(*basis.px(u, v))
        if abs(ru - u) > 1e-6 or abs(rv - v) > 1e-6:
            raise AssertionError(f"{name}: basis.plan does not invert "
                                 f"basis.px at ({u}, {v})")

    # 3. A floor narrower than the character is a floor nobody can
    #    stand on — the failure mode of narrowing a corridor.
    if not walk.allow:
        raise AssertionError(f"{name}: no walkable region declared")
    for a in walk.allow:
        du, dv = a["u1"] - a["u0"], a["v1"] - a["v0"]
        if du <= 2 * walk.pad or dv <= 2 * walk.pad:
            raise AssertionError(
                f"{name}: walk region {a} is narrower than the "
                f"character (pad {walk.pad}) — {du:.2f} x {dv:.2f} units")

    # 4. An obstacle that touches no floor means the two drifted apart:
    #    the planter moved, or the ring did.
    for b in walk.block:
        if not any(_overlaps(a, b) for a in walk.allow):
            raise AssertionError(
                f"{name}: obstacle {b} sits on no walkable floor — its "
                f"position and the floor's extents have come apart")

    # 5. Spawn must be somewhere the character can actually stand.
    su, sv = walk.spawn
    if not walk.ok(su, sv):
        raise AssertionError(
            f"{name}: spawn ({su}, {sv}) is not walkable")
    if view is not None:
        sx_, sy_ = basis.px(su, sv)
        if not (view[0] <= sx_ <= view[2] and view[1] <= sy_ <= view[3]):
            raise AssertionError(
                f"{name}: spawn projects to ({sx_:.0f}, {sy_:.0f}), "
                f"outside the view rect {view}")

    # 6. EVERY HOTSPOT MUST BE WALKABLE TO. A door the player can tap
    #    and cannot reach is worse than one that is not there — the tap
    #    would start a walk that never arrives. Checked against the
    #    SPAWN's own connected component, not merely "is it walkable":
    #    the Capitol has a sealed pocket behind a planter, and an
    #    approach point that landed in it would pass the weaker test.
    if targets:
        reach = _reached(walk, sample)
        u0 = min(a["u0"] for a in walk.allow)
        v0 = min(a["v0"] for a in walk.allow)
        for tid, tu, tv in targets:
            cell = (int(round((tu - u0) / sample)),
                    int(round((tv - v0) / sample)))
            if cell not in reach:
                raise AssertionError(
                    f"{name}: hotspot '{tid}' approach ({tu}, {tv}) is "
                    f"not reachable from spawn — the player could tap a "
                    f"door they can never walk to")
        print(f"{name}: all {len(targets)} hotspot approaches reachable "
              f"from spawn")

    # ---- report. The floor extending past a deliberately tightened
    # `view` is intended (a corridor cut by the frame reads as
    # continuing), so this is printed, never asserted — but a jump in
    # the number after a composition change is worth looking at.
    bb = walk.bbox_px(basis)
    line = (f"{name}: floor bbox px "
            f"({bb[0]:.0f}, {bb[1]:.0f})-({bb[2]:.0f}, {bb[3]:.0f})")
    if view is not None:
        cropped = sum((bb[0] < view[0], bb[1] < view[1],
                       bb[2] > view[2], bb[3] > view[3]))
        line += f", view {tuple(view)} — "
        line += (f"{cropped} side(s) crop the floor" if cropped
                 else "fully inside")
    print(line)

    # CAN THE CHARACTER ACTUALLY GET AROUND? An obstacle that grows
    # until it spans a walkway severs the floor in two, and every
    # failure of that kind so far has come from the ROOM changing, not
    # the obstacle: a narrowed corridor, a shallower balcony. Reported
    # rather than asserted, since a room may legitimately have a ledge
    # nobody needs to reach — but a jump from 1 to 2 after a render
    # change is the signal to look at.
    comps, reach = _components(walk, sample)
    tot = sum(comps)
    # A POCKET IS NOT A SEVERED FLOOR, and conflating them makes this
    # warning noise. A planter wedged in a corner really does seal the
    # scrap of floor behind it — the Capitol's ʻEwa corner is a 0.4 x
    # 0.5 unit pocket of exactly that kind, correct and unreachable and
    # empty. Anything the character could not turn around in is
    # reported and not warned about; a second piece bigger than that is
    # a walkway actually cut in half, which is worth stopping for.
    floor = (2 * walk.pad) ** 2
    small = max(4, int(floor / (sample * sample)))
    real = [c for c in comps if c > small]
    pockets = len(comps) - len(real)
    tail = (f"; {pockets} unreachable pocket(s) under {floor:.2f} sq units"
            if pockets else "")
    if len(real) > 1:
        print(f"{name}: WARNING — walkable floor is SEVERED into "
              f"{len(real)} pieces {real}; spawn reaches {reach}/{tot} "
              f"cells ({100.0 * reach / tot:.0f}%){tail}")
    else:
        print(f"{name}: floor is one connected region ({tot} cells at "
              f"{sample} units), all reachable from spawn{tail}")


def _reached(walk, step):
    """The set of grid cells the spawn can actually get to."""
    u0 = min(a["u0"] for a in walk.allow)
    u1 = max(a["u1"] for a in walk.allow)
    v0 = min(a["v0"] for a in walk.allow)
    v1 = max(a["v1"] for a in walk.allow)
    nu = int((u1 - u0) / step) + 1
    nv = int((v1 - v0) / step) + 1
    si = int(round((walk.spawn[0] - u0) / step))
    sj = int(round((walk.spawn[1] - v0) / step))
    seen, stack = set(), [(si, sj)]
    seen.add((si, sj))
    while stack:
        a, b = stack.pop()
        for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = a + da, b + db
            if (0 <= x < nu and 0 <= y < nv and (x, y) not in seen
                    and walk.ok(u0 + x * step, v0 + y * step)):
                seen.add((x, y))
                stack.append((x, y))
    return seen


def _components(walk, step):
    """Connected components of the walkable floor on a grid, and how
    many cells the spawn can reach.

    4-connected on the plan grid: the character moves continuously, but
    a gap a grid step wide is a gap the path search would have to thread
    exactly, so treating it as impassable is the honest reading.
    """
    u0 = min(a["u0"] for a in walk.allow)
    u1 = max(a["u1"] for a in walk.allow)
    v0 = min(a["v0"] for a in walk.allow)
    v1 = max(a["v1"] for a in walk.allow)
    nu = int((u1 - u0) / step) + 1
    nv = int((v1 - v0) / step) + 1
    free = [[walk.ok(u0 + i * step, v0 + j * step)
             for j in range(nv)] for i in range(nu)]

    seen = [[False] * nv for _ in range(nu)]
    sizes, spawn_size = [], 0
    si = int(round((walk.spawn[0] - u0) / step))
    sj = int(round((walk.spawn[1] - v0) / step))
    for i in range(nu):
        for j in range(nv):
            if not free[i][j] or seen[i][j]:
                continue
            stack, n, has_spawn = [(i, j)], 0, False
            seen[i][j] = True
            while stack:
                a, b = stack.pop()
                n += 1
                if abs(a - si) <= 1 and abs(b - sj) <= 1:
                    has_spawn = True
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if (0 <= x < nu and 0 <= y < nv
                            and free[x][y] and not seen[x][y]):
                        seen[x][y] = True
                        stack.append((x, y))
            sizes.append(n)
            if has_spawn:
                spawn_size = n
    return sorted(sizes, reverse=True), spawn_size


def debug_png(img, basis, walk, out, ship=1, view=None, step=0.12):
    """Draw the walkmask OVER the bake, so a render change can be
    checked by eye as well as by assert.

    Same role as `build/debug_rain_<slug>.png` in the island pipeline:
    derived, gitignored, regenerated on demand. Sampling the mask rather
    than drawing the declared regions is deliberate — it shows what
    `ok()` actually returns, insets and obstacle growth and all, which
    is the floor the character will really move through; drawing the
    rectangles would only show what was typed.
    """
    from PIL import Image, ImageDraw

    im = img.convert("RGB").copy()
    d = ImageDraw.Draw(im, "RGBA")

    def S(p):
        return (p[0] * ship, p[1] * ship)

    u0 = min(a["u0"] for a in walk.allow)
    u1 = max(a["u1"] for a in walk.allow)
    v0 = min(a["v0"] for a in walk.allow)
    v1 = max(a["v1"] for a in walk.allow)

    n = 0
    u = u0
    while u <= u1:
        v = v0
        while v <= v1:
            if walk.ok(u, v):
                x, y = S(basis.px(u, v))
                r = 1.6 * ship
                d.ellipse([x - r, y - r, x + r, y + r],
                          fill=(80, 230, 140, 130))
                n += 1
            v += step
        u += step

    # obstacles: the drawn footprint, and again grown by the character
    for b in walk.block:
        for grow, col in ((0.0, (255, 90, 70, 220)),
                          (walk.pad, (255, 90, 70, 90))):
            if b["t"] == "rect":
                pts = [S(basis.px(u, v)) for u, v in _rect_corners(
                    rect(b["u0"] - grow, b["u1"] + grow,
                         b["v0"] - grow, b["v1"] + grow))]
            else:
                r = b["r"] + grow
                pts = [S(basis.px(b["u"] + r * math.cos(math.radians(k)),
                                  b["v"] + r * math.sin(math.radians(k))))
                       for k in range(0, 360, 6)]
            d.line(pts + [pts[0]], fill=col, width=max(1, ship))

    sx_, sy_ = S(basis.px(*walk.spawn))
    r = 7 * ship
    d.line([(sx_ - r, sy_), (sx_ + r, sy_)], fill=(255, 220, 90, 255),
           width=max(1, ship))
    d.line([(sx_, sy_ - r), (sx_, sy_ + r)], fill=(255, 220, 90, 255),
           width=max(1, ship))

    if view is not None:
        d.rectangle([view[0] * ship, view[1] * ship,
                     view[2] * ship, view[3] * ship],
                    outline=(120, 190, 255, 200), width=max(1, ship))

    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print(f"walk overlay -> {out}  ({n} sample points walkable)")
