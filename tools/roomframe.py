#!/usr/bin/env python3
"""ROOM FRAMES — one reference frame per baked room, the named frames
derived from its structure, and every placed thing declared ONCE in them.

WHY THIS EXISTS (2026-09-22, user: "figure out framework so we can more
easily adjust the layout of places like this capitol and have a reference
frame or something"). A room's layout was spread over five coordinate
systems — plan (u, v), screen offsets like `CX - 64`, a wall run's `t`,
wall-local (w, y) and heights in `dy` — with the same position often
written twice. Every bug of that kind has the same shape: the structure
moves and a literal does not. The Capitol's Diamond Head planter stayed at
the square plan's corner when the wing slid that corner out, and stood on
the governor's lift threshold for a month; the rail pots were painted 16
SCENE px off the rail while their collision discs were offset by 16 DRAW
px, so the player could stand on every pot. Nothing showed either of
those, and nothing checked.

THE MODEL
  THE FRAME. Plan coordinates (u, v) in plan units (~1 m in these rooms),
    the space `roomplan.Basis` projects: +u runs screen down-right, +v
    screen down-left. A room names its own axes and origin (`axes`).
  LEVELS. Floors at a height `dy` in scene px above the room's reference
    floor — the painters' own vertical unit. A level may carry the plan
    polygons where it HAS floor, and a `window` it is seen through (the
    Capitol's court is only visible through the well).
  NAMED FRAMES, derived from the room's structure constants, never typed:
    Run     a straight line on a level — a wall's foot, a railing, a
            colonnade. Positions along it:
              t  0..1 from `a` to `b`
              s  plan units from `a` (negative: back from `b`)
              n  plan units off the line INTO the room
            `t` stretches with the run; `s` holds its distance when the
            run grows. Use whichever you mean.
    Region  a plan polygon on a level — a floor, a corner square, the
            court. Positions: explicit (u, v) inside it, or fractions
            (fu, fv) of its bounding box (default: the centre).
  ITEMS. Every placed thing: an id, a kind, the frame it is placed in and
    its position in that frame. Painters, the walkmask, the depth bands,
    the JSON and both overlays all read the RESOLVED item — one source.
    `derived=True` marks items the room computes (doors laid out by a
    schedule, columns, posts) rather than places by hand; they are
    recorded so the overlay and the checks see them too.

THE CHECKS (Layout.check) encode the lessons, and run on every bake:
  errors   an item outside its frame; two footprints overlapping; a
           declared walkway loop cut (a ring the player can no longer go
           all the way round).
  warnings a footprint standing in front of a doorway; a depth-band
           policy the walk mask contradicts ("front" item the player can
           stand in front of, "back" item the player can stand behind).

THE OVERLAYS are the reference frame made visible: `debug_png()` writes a
labelled grid/frame/item map over the bake, and `json()` feeds the
in-game `?layout=1` overlay, whose cursor readout names the level, the
plan (u, v) and the wall run + t under the pointer — so a position can be
READ off the screen and written straight back into the placement table.
"""

from __future__ import annotations

import math


# Item colours by kind, for BOTH overlays: debug_png() draws with them and
# json() ships them, so the reference image and ?layout=1 cannot disagree
# about what colour a bench is. Anything unlisted is free-standing green.
KIND_COLORS = {"door": "#ffd166", "lift": "#ffd166", "hall": "#f4a261",
               "office": "#f4a261", "alcove": "#f4a261", "bench": "#e76f51",
               "post": "#9aa0a6", "column": "#e9ecef", "spawn": "#ffe066",
               "*": "#80ed99"}


# ------------------------------------------------------------ geometry
def _poly_rect(u0, u1, v0, v1):
    u0, u1 = min(u0, u1), max(u0, u1)
    v0, v1 = min(v0, v1), max(v0, v1)
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def _in_poly(poly, u, v):
    """Even-odd point in polygon, boundary counted inside (a rect region's
    own edge belongs to it — corner squares share edges with runs)."""
    inside = False
    n = len(poly)
    for i in range(n):
        (u1, v1), (u2, v2) = poly[i], poly[(i + 1) % n]
        # on the segment?
        cr = (u2 - u1) * (v - v1) - (v2 - v1) * (u - u1)
        if (abs(cr) < 1e-9 and min(u1, u2) - 1e-9 <= u <= max(u1, u2) + 1e-9
                and min(v1, v2) - 1e-9 <= v <= max(v1, v2) + 1e-9):
            return True
        if (v1 > v) != (v2 > v):
            x = u1 + (v - v1) * (u2 - u1) / (v2 - v1)
            if u < x:
                inside = not inside
    return inside


def _bbox(poly):
    us = [p[0] for p in poly]
    vs = [p[1] for p in poly]
    return min(us), max(us), min(vs), max(vs)


def _reg_dist(reg, u, v):
    """Distance from a point to a roomplan region (0 if inside)."""
    if reg["t"] == "disc":
        return max(0.0, math.hypot(u - reg["u"], v - reg["v"]) - reg["r"])
    du = max(reg["u0"] - u, 0.0, u - reg["u1"])
    dv = max(reg["v0"] - v, 0.0, v - reg["v1"])
    return math.hypot(du, dv)


def _extent_in_run(run, reg):
    """A footprint's span in a run's frame: (s_min, s_max, n_min, n_max)."""
    if reg["t"] == "disc":
        _, s, n = run.locate(reg["u"], reg["v"])
        r = reg["r"]
        return s - r, s + r, n - r, n + r
    cs = [run.locate(u, v) for u, v in _poly_rect(reg["u0"], reg["u1"],
                                                   reg["v0"], reg["v1"])]
    return (min(c[1] for c in cs), max(c[1] for c in cs),
            min(c[2] for c in cs), max(c[2] for c in cs))


def _regs_overlap(a, b):
    """Do two roomplan regions (disc/rect) overlap? Touching is allowed."""
    if a["t"] == "disc" and b["t"] == "disc":
        return math.hypot(a["u"] - b["u"], a["v"] - b["v"]) < \
            a["r"] + b["r"] - 1e-6
    if a["t"] == "rect" and b["t"] == "rect":
        return not (a["u1"] <= b["u0"] + 1e-6 or b["u1"] <= a["u0"] + 1e-6
                    or a["v1"] <= b["v0"] + 1e-6 or b["v1"] <= a["v0"] + 1e-6)
    d, r = (a, b) if a["t"] == "disc" else (b, a)
    return _reg_dist(r, d["u"], d["v"]) < d["r"] - 1e-6


# -------------------------------------------------------------- frames
class Level:
    """A floor at height `dy` (scene px above the room's reference floor).

    `floors` are plan polygons where this level has walkable/placeable
    floor — the cursor readout tests them to say which level the pointer
    is on. `window` is a (plan polygon, dy) the level is SEEN through, if
    any: the Capitol's court is under the gallery slab except where the
    well opens over it, so its grid is clipped to that opening."""

    def __init__(self, name, dy, color, window=None):
        self.name, self.dy, self.color = name, float(dy), color
        self.floors = []
        self.window = window


class Run:
    """A straight line on a level, in plan. See the module docstring for
    t / s / n. `into` is the plan direction of the room side — the side a
    door opens onto, a bench stands out toward, a pot sits in from the
    rail — as a vector; only its sign relative to the line matters."""

    def __init__(self, name, level, a, b, into, height=0.0, kind="wall"):
        self.name, self.level, self.kind = name, level, kind
        self.a, self.b = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
        self.height = float(height)
        du, dv = self.b[0] - self.a[0], self.b[1] - self.a[1]
        L = math.hypot(du, dv)
        if L == 0:
            raise ValueError(f"run {name}: zero length")
        self.length = L
        self.dir = (du / L, dv / L)
        nu, nv = -self.dir[1], self.dir[0]           # a left-hand normal
        if nu * into[0] + nv * into[1] < 0:
            nu, nv = -nu, -nv
        self.normal = (nu, nv)

    def t_of(self, t=None, s=None):
        if (t is None) == (s is None):
            raise ValueError(f"run {self.name}: give exactly one of t / s")
        if s is not None:
            return (s if s >= 0 else self.length + s) / self.length
        return float(t)

    def at(self, t=None, s=None, n=0.0):
        """Plan point at t (or s) along the run, n plan units into the
        room."""
        tt = self.t_of(t, s)
        return (self.a[0] + (self.b[0] - self.a[0]) * tt + self.normal[0] * n,
                self.a[1] + (self.b[1] - self.a[1]) * tt + self.normal[1] * n)

    def locate(self, u, v):
        """(t, s, n) of a plan point in this run's frame — the inverse of
        at(). The cursor readout and the doorway check both use it."""
        pu, pv = u - self.a[0], v - self.a[1]
        s = pu * self.dir[0] + pv * self.dir[1]
        n = pu * self.normal[0] + pv * self.normal[1]
        return s / self.length, s, n

    def ends(self, iso):
        """The run's two ends as the RENDERER's own snapped screen points
        — what its painters take as (e0, e1)."""
        return (iso(self.a[0], self.a[1], self.level.dy),
                iso(self.b[0], self.b[1], self.level.dy))


class Region:
    """A plan polygon on a level. `floor=True` adds it to the level's
    floors (the readout's level test)."""

    def __init__(self, name, level, poly, kind="floor"):
        self.name, self.level, self.kind = name, level, kind
        self.poly = [(float(u), float(v)) for u, v in poly]

    def contains(self, u, v):
        return _in_poly(self.poly, u, v)

    def at(self, fu=0.5, fv=0.5):
        u0, u1, v0, v1 = _bbox(self.poly)
        return (u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv)


class Item:
    """A placed thing, resolved to a plan point on a level.

    foot    walk footprint: a list of roomplan regions (disc / rect), or
            empty. Used for overlap and doorway checks, and — with
            `blocks` — as walk obstacles.
    band    the depth policy the renderer gives it: "back" (always
            behind the character), "front" (always in front), "sort"
            (its own band at plan depth u+v), or None (not on the walk
            level / not decided).
    extent  its drawn box in SCENE px relative to its screen point,
            (x0, y0, x1, y1) — what the band check overlaps the
            character against.
    """

    def __init__(self, id, kind, level, u, v, frame, where, foot=(),
                 blocks=False, band=None, extent=None, derived=False,
                 note="", **meta):
        self.id, self.kind, self.level = id, kind, level
        self.u, self.v = u, v
        self.frame, self.where = frame, dict(where)
        self.foot = list(foot)
        self.blocks, self.band, self.extent = blocks, band, extent
        self.derived, self.note, self.meta = derived, note, meta

    @property
    def t(self):
        """The run parameter this item was placed at (runs only)."""
        return self.meta.get("t")

    def __repr__(self):
        return (f"<{self.id} {self.kind} {self.level.name} "
                f"({self.u:.3f}, {self.v:.3f}) in {self.frame.name}>")


# -------------------------------------------------------------- layout
class Layout:
    """A room's frames and items. Declare levels, then frames, then place
    items; read items back by id or kind in DECLARATION ORDER (painters
    rely on it — draw order is part of the picture)."""

    def __init__(self, room, basis, axes):
        self.room, self.basis, self.axes = room, basis, dict(axes)
        self.levels = {}
        self.frames = {}
        self._items = {}

    # ---- declaration
    def add_level(self, name, dy, color, window=None):
        lv = Level(name, dy, color, window)
        self.levels[name] = lv
        return lv

    def add_run(self, name, level, a, b, into, height=0.0, kind="wall"):
        return self._frame(Run(name, self.levels[level], a, b, into,
                               height, kind))

    def add_region(self, name, level, poly, kind="floor"):
        reg = Region(name, self.levels[level], poly, kind)
        if kind == "floor":
            self.levels[level].floors.append(reg.poly)
        return self._frame(reg)

    def add_rect(self, name, level, u0, u1, v0, v1, kind="floor"):
        return self.add_region(name, level, _poly_rect(u0, u1, v0, v1), kind)

    def _frame(self, f):
        if f.name in self.frames:
            raise ValueError(f"frame {f.name} declared twice")
        self.frames[f.name] = f
        return f

    def place(self, id, kind, frame, *, t=None, s=None, n=0.0, u=None,
              v=None, fu=None, fv=None, **kw):
        """Place an item in a named frame. On a Run: t or s along it, n
        into the room. On a Region: explicit u, v, or fractions fu, fv
        of its bbox (default the centre). `foot` may be a callable
        (u, v) -> [regions], evaluated at the resolved point, so a
        footprint follows its item wherever the frame puts it."""
        if id in self._items:
            raise ValueError(f"item {id} placed twice")
        f = self.frames[frame]
        if isinstance(f, Run):
            pu, pv = f.at(t=t, s=s, n=n)
            where = {k: x for k, x in (("t", t), ("s", s), ("n", n))
                     if x is not None and not (k == "n" and x == 0.0)}
            kw.setdefault("t", f.t_of(t, s))
        else:
            if u is not None or v is not None:
                if u is None or v is None:
                    raise ValueError(f"{id}: give both u and v")
                pu, pv = float(u), float(v)
                where = {"u": u, "v": v}
            else:
                fu_ = 0.5 if fu is None else fu
                fv_ = 0.5 if fv is None else fv
                pu, pv = f.at(fu_, fv_)
                where = {"fu": fu_, "fv": fv_}
        return self._add(Item(id, kind, f.level, pu, pv, f, where,
                              **self._foot(kw, pu, pv)))

    def place_at(self, id, kind, frame, u, v, **kw):
        """Record an item at a plan point the room computed itself — a
        door a schedule laid out, a column station. It is filed under
        `frame` with its coordinates in that frame, so the overlay and
        the checks treat it like any placed item; `derived` defaults on,
        because the way to move it is the thing that computed it."""
        if id in self._items:
            raise ValueError(f"item {id} placed twice")
        f = self.frames[frame]
        kw.setdefault("derived", True)
        if isinstance(f, Run):
            tt, ss, nn = f.locate(u, v)
            kw.setdefault("t", tt)
            where = {"t": round(tt, 4)}
            if abs(nn) > 1e-6:
                where["n"] = round(nn, 4)
        else:
            where = {"u": u, "v": v}
        return self._add(Item(id, kind, f.level, float(u), float(v), f, where,
                              **self._foot(kw, u, v)))

    @staticmethod
    def _foot(kw, u, v):
        if callable(kw.get("foot")):
            kw = dict(kw, foot=kw["foot"](u, v))
        return kw

    def _add(self, it):
        self._items[it.id] = it
        return it

    # ---- reading
    def __getitem__(self, id):
        return self._items[id]

    def items(self, kind=None, level=None, frame=None):
        out = list(self._items.values())
        if kind is not None:
            kinds = (kind,) if isinstance(kind, str) else tuple(kind)
            out = [i for i in out if i.kind in kinds]
        if level is not None:
            out = [i for i in out if i.level.name == level]
        if frame is not None:
            out = [i for i in out if i.frame.name == frame]
        return out

    def run(self, name):
        return self.frames[name]

    def px(self, item):
        """Analytic scene px of an item (no snapping — the renderer's own
        iso() snaps to its draw grid)."""
        return self.basis.px(item.u, item.v, item.level.dy)

    def blockers(self, level):
        """Walk obstacles contributed by items on `level`."""
        return [r for it in self.items(level=level) if it.blocks
                for r in it.foot]

    # ---- checks
    def check(self, walk=None, walk_level=None, char_box=(-7, -39, 7, 0),
              loops=(), clear=0.8, doors=("door", "office", "hall", "lift",
                                         "alcove"), step=0.1, strict=True):
        """Validate the layout. Prints a report; raises on errors when
        `strict`. Returns (errors, warnings)."""
        errs, warns = [], []

        # 1. every item inside its own frame
        for it in self._items.values():
            f = it.frame
            if isinstance(f, Run):
                tt = it.meta.get("t")
                if tt is not None and not (-1e-9 <= tt <= 1 + 1e-9):
                    errs.append(f"{it.id}: t={tt:.3f} is off its run "
                                f"{f.name} (0..1)")
            elif not f.contains(it.u, it.v):
                errs.append(f"{it.id}: ({it.u:.2f}, {it.v:.2f}) is outside "
                            f"its region {f.name}")

        # 2. footprints must not overlap on a level
        by_level = {}
        for it in self._items.values():
            if it.foot:
                by_level.setdefault(it.level.name, []).append(it)
        for lname, its in by_level.items():
            for i in range(len(its)):
                for j in range(i + 1, len(its)):
                    a, b = its[i], its[j]
                    if any(_regs_overlap(ra, rb)
                           for ra in a.foot for rb in b.foot):
                        errs.append(f"{a.id} and {b.id} overlap on {lname}")

        # 3. nothing free-standing in front of a doorway: a box in the
        #    door's own run frame, the door's width along the wall and
        #    `clear` plan units out from it
        for dr in self.items(kind=doors):
            f = dr.frame
            if not isinstance(f, Run) or dr.meta.get("t") is None:
                continue
            hw = dr.meta.get("hw_plan", 0.9)
            s0 = dr.meta["t"] * f.length
            for it in by_level.get(dr.level.name, []):
                if it is dr:
                    continue
                for reg in it.foot:
                    smin, smax, nmin, nmax = _extent_in_run(f, reg)
                    # on the ROOM side of the wall (n > 0) and inside
                    # the box — behind a wall is not in front of its door
                    if (smax > s0 - hw and smin < s0 + hw
                            and nmin < clear and nmax > 0):
                        warns.append(f"{it.id} stands in front of {dr.id} "
                                     f"({f.name} t={dr.meta['t']:.2f}) — "
                                     f"inside its {clear} m doorway "
                                     f"clearance")
                        break

        # 4 + 5 need the walk mask on a grid
        if walk is not None:
            grid = _WalkGrid(walk, step)
            for name, (hu, hv) in loops:
                if grid.loop_cut(hu, hv):
                    errs.append(f"walkway loop '{name}' is CUT — the floor "
                                f"no longer goes all the way round "
                                f"({hu}, {hv}); something blocks it from "
                                f"rail to wall")
            if walk_level is not None:
                warns += self._band_check(grid, walk_level, char_box)

        ok = not errs
        head = (f"{self.room} layout: {len(self._items)} items in "
                f"{len(self.frames)} frames — {len(errs)} error(s), "
                f"{len(warns)} warning(s)")
        print(head)
        for e in errs:
            print("  ERROR  " + e)
        for w in warns:
            print("  warn   " + w)
        if errs and strict:
            raise AssertionError(f"{self.room} layout has {len(errs)} "
                                 f"error(s): " + "; ".join(errs))
        return errs, warns

    def _band_check(self, grid, level, char_box, min_px=4):
        """A "front" item the character can stand IN FRONT of while
        overlapping it on screen is painted over them; a "back" item they
        can stand BEHIND is painted under them. Either is a visible clip.
        Sampled on the walk grid, so it tests the floor the character can
        really reach.

        Both boxes are approximations of what is drawn, so an overlap has
        to be at least `min_px` scene px on BOTH axes to count — grazing
        corners of two bounding boxes is not a clip anyone can see — and
        the spot reported is the one with the most overlap, i.e. the most
        visible one."""
        out = []
        cx0, cy0, cx1, cy1 = char_box
        for it in self.items(level=level):
            if it.band not in ("front", "back") or not it.extent:
                continue
            ix, iy = self.px(it)
            ex0, ey0, ex1, ey1 = it.extent
            box = (ix + ex0, iy + ey0, ix + ex1, iy + ey1)
            d_it = it.u + it.v
            worst = None
            for (pu, pv) in grid.free_near(it.u, it.v, 3.0):
                dd = (pu + pv) - d_it
                if not ((it.band == "front" and dd > 0.05) or
                        (it.band == "back" and dd < -0.05)):
                    continue
                x, y = self.basis.px(pu, pv, self.levels[level].dy)
                ox = min(x + cx1, box[2]) - max(x + cx0, box[0])
                oy = min(y + cy1, box[3]) - max(y + cy0, box[1])
                if ox < min_px or oy < min_px:
                    continue
                if worst is None or ox * oy > worst[0] * worst[1]:
                    worst = (ox, oy, pu, pv)
            if worst:
                side = "in front of" if it.band == "front" else "behind"
                over = "over" if it.band == "front" else "under"
                out.append(f"{it.id} is in the '{it.band}' band but the "
                           f"character can stand {side} it — at "
                           f"({worst[2]:.2f}, {worst[3]:.2f}) it is drawn "
                           f"{over} them across ~{worst[0]:.0f}x"
                           f"{worst[1]:.0f} px; give it its own depth band")
        return out

    # ---- export
    def json(self, extra=None):
        """The frame file the in-game `?layout=1` overlay reads."""
        def r4(x):
            return round(x, 4) if isinstance(x, float) else x

        def poly(p):
            return [[r4(u), r4(v)] for u, v in p]

        lv = []
        for L in self.levels.values():
            d = {"name": L.name, "dy": r4(L.dy), "color": L.color,
                 "floors": [poly(p) for p in L.floors]}
            if L.window:
                d["window"] = {"poly": poly(L.window[0]),
                               "dy": r4(float(L.window[1]))}
            lv.append(d)
        runs, regions = [], []
        for f in self.frames.values():
            if isinstance(f, Run):
                runs.append({"name": f.name, "level": f.level.name,
                             "kind": f.kind, "a": [r4(f.a[0]), r4(f.a[1])],
                             "b": [r4(f.b[0]), r4(f.b[1])],
                             "into": [r4(f.normal[0]), r4(f.normal[1])],
                             "h": r4(f.height)})
            else:
                regions.append({"name": f.name, "level": f.level.name,
                                "kind": f.kind, "poly": poly(f.poly)})
        items = []
        for it in self._items.values():
            d = {"id": it.id, "kind": it.kind, "level": it.level.name,
                 "u": r4(it.u), "v": r4(it.v), "frame": it.frame.name,
                 "at": {k: r4(float(x)) for k, x in it.where.items()}}
            if it.derived:
                d["derived"] = True
            if it.band:
                d["band"] = it.band
            if it.foot:
                d["foot"] = [{k: r4(x) for k, x in r.items()}
                             for r in it.foot]
            if it.meta.get("tall"):
                d["tall"] = r4(float(it.meta["tall"]))
            items.append(d)
        out = {"room": self.room, "basis": self.basis.json(),
               "axes": self.axes, "levels": lv, "runs": runs,
               "regions": regions, "items": items, "kinds": KIND_COLORS}
        if extra:
            out.update(extra)
        return out

    # ---- the reference image
    def debug_png(self, img, out, ship=1, view=None, title=None):
        """The reference frame over the bake: every level's floor grid
        (1 plan unit, bold every 5, labelled), every run with its t ticks
        and name, every item with its id. Derived, gitignored, and the
        picture to talk about positions with — the same role
        `debug_walk_<room>.png` plays for the walkmask.

        A level seen through a WINDOW (the Capitol's court, under the
        gallery slab except where the well opens) is clipped to it —
        grid, runs, labels and markers alike — or its lines would run
        out under the slab and into the ink, and its items would appear
        to stand on the floor above. An item with a `tall` height (a
        column) is marked at the middle of its VISIBLE span, since its
        foot is usually the hidden end."""
        from PIL import Image, ImageChops, ImageDraw, ImageFont

        def font(sz):
            for pth in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                        "/System/Library/Fonts/Supplemental/Arial.ttf",
                        "/Library/Fonts/Arial.ttf"):
                try:
                    return ImageFont.truetype(pth, sz)
                except OSError:
                    pass
            return ImageFont.load_default()

        S = float(ship)
        F_LAB, F_ID = font(int(9 * S)), font(int(8 * S))
        F_T, F_HEAD = font(int(7 * S)), font(int(12 * S))
        base = Image.eval(img.convert("RGB"), lambda c: int(c * 0.42))
        canvas = base.convert("RGBA")
        size = canvas.size

        def P(u, v, dy):
            x, y = self.basis.px(u, v, dy)
            return (x * S, y * S)

        def hexa(c, a):
            c = c.lstrip("#")
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)

        def poly_mask(polys, dy):
            m = Image.new("L", size, 0)
            dm = ImageDraw.Draw(m)
            for pl in polys:
                dm.polygon([P(u, v, dy) for u, v in pl], fill=255)
            return m

        # where each level can be SEEN: everywhere, or through its window
        seen = {L.name: (poly_mask([L.window[0]], L.window[1])
                         if L.window else None)
                for L in self.levels.values()}

        def visible(lname, x, y):
            m = seen[lname]
            if m is None:
                return 0 <= x < size[0] and 0 <= y < size[1]
            return (0 <= x < size[0] and 0 <= y < size[1]
                    and m.getpixel((int(x), int(y))) > 0)

        def through(lname, layer):
            """Composite a level's layer, clipped to where it is seen."""
            m = seen[lname]
            if m is not None:
                a = ImageChops.multiply(layer.getchannel("A"), m)
                layer.putalpha(a)
            canvas.alpha_composite(layer)

        # ---- floors + grids, one level at a time, clipped to its floors
        # (and to its window)
        for L in self.levels.values():
            if not L.floors:
                continue
            layer = Image.new("RGBA", size, (0, 0, 0, 0))
            dl = ImageDraw.Draw(layer)
            u0 = min(_bbox(pl)[0] for pl in L.floors)
            u1 = max(_bbox(pl)[1] for pl in L.floors)
            v0 = min(_bbox(pl)[2] for pl in L.floors)
            v1 = max(_bbox(pl)[3] for pl in L.floors)
            for pl in L.floors:
                dl.polygon([P(u, v, L.dy) for u, v in pl],
                           fill=hexa(L.color, 38))
            for k in range(math.floor(u0), math.ceil(u1) + 1):
                mj = k % 5 == 0
                dl.line([P(k, v0, L.dy), P(k, v1, L.dy)],
                        fill=hexa(L.color, 190 if mj else 70),
                        width=max(1, int(S * (1.5 if mj else 0.6))))
            for k in range(math.floor(v0), math.ceil(v1) + 1):
                mj = k % 5 == 0
                dl.line([P(u0, k, L.dy), P(u1, k, L.dy)],
                        fill=hexa(L.color, 190 if mj else 70),
                        width=max(1, int(S * (1.5 if mj else 0.6))))
            fm = poly_mask(L.floors, L.dy)
            layer.putalpha(ImageChops.multiply(layer.getchannel("A"), fm))
            through(L.name, layer)
            # label each major line at its first visible floor point
            d = ImageDraw.Draw(canvas)
            for axis in ("u", "v"):
                lo, hi = (u0, u1) if axis == "u" else (v0, v1)
                o0, o1 = (v0, v1) if axis == "u" else (u0, u1)
                for k in range(math.ceil(lo / 5) * 5, math.floor(hi) + 1, 5):
                    for i in range(61):
                        o = o1 - (o1 - o0) * i / 60
                        uu, vv = (k, o) if axis == "u" else (o, k)
                        x, y = P(uu, vv, L.dy)
                        if (0 <= x < size[0] and 0 <= y < size[1]
                                and fm.getpixel((int(x), int(y)))
                                and visible(L.name, x, y)):
                            _label(d, (x + 3 * S, y - 10 * S),
                                   f"{L.name} {axis}={k}", F_LAB,
                                   hexa(L.color, 255))
                            break

        # ---- runs: a line on the foot, ticks every plan unit, the name
        # and its t0 / t1 ends — each on its level's layer, so a windowed
        # level's runs are clipped like its grid
        for L in self.levels.values():
            runs = [f for f in self.frames.values()
                    if isinstance(f, Run) and f.level is L]
            if not runs:
                continue
            layer = Image.new("RGBA", size, (0, 0, 0, 0))
            dl = ImageDraw.Draw(layer)
            labels = []
            for f in runs:
                col = hexa(L.color, 230)
                a, b = P(*f.a, L.dy), P(*f.b, L.dy)
                dl.line([a, b], fill=col, width=max(1, int(1.5 * S)))
                for k in range(int(f.length) + 1):
                    x, y = P(*f.at(s=float(k)), L.dy)
                    ln = (5 if k % 5 == 0 else 2.5) * S
                    dl.line([(x, y), (x, y - ln)], fill=col,
                            width=max(1, int(S)))
                # the name at the middle of the VISIBLE stretch
                vis = [tt / 40 for tt in range(41)
                       if visible(L.name, *P(*f.at(t=tt / 40), L.dy))]
                if vis:
                    x, y = P(*f.at(t=vis[len(vis) // 2]), L.dy)
                    hh = (f.height * 0.55 if f.kind == "wall" else 12) * S
                    labels.append(((x - 18 * S, y - hh), f.name, F_LAB))
                for end, pt_ in (("t0", a), ("t1", b)):
                    if visible(L.name, *pt_):
                        labels.append(((pt_[0] - 4 * S, pt_[1] + 2 * S),
                                       end, F_T))
            through(L.name, layer)
            d = ImageDraw.Draw(canvas)
            for xy, text, fnt in labels:
                _label(d, xy, text, fnt, hexa(L.color, 255))

        # ---- items: footprint, marker, id
        d = ImageDraw.Draw(canvas)
        for it in self._items.values():
            lv = it.level
            col = KIND_COLORS.get(it.kind, KIND_COLORS["*"])
            x, y = P(it.u, it.v, lv.dy)
            if not visible(lv.name, x, y):
                tall = it.meta.get("tall")
                if not tall:
                    continue            # hidden, and nothing rises from it
                span = [h for h in range(0, int(tall) + 1, 2)
                        if visible(lv.name, *P(it.u, it.v, lv.dy + h))]
                if not span:
                    continue
                x, y = P(it.u, it.v, lv.dy + span[len(span) // 2])
            elif it.foot:
                fl = Image.new("RGBA", size, (0, 0, 0, 0))
                df = ImageDraw.Draw(fl)
                for reg in it.foot:
                    if reg["t"] == "disc":
                        pts = [P(reg["u"] + reg["r"] * math.cos(k * math.pi / 18),
                                 reg["v"] + reg["r"] * math.sin(k * math.pi / 18),
                                 lv.dy) for k in range(36)]
                    else:
                        pts = [P(uu, vv, lv.dy) for uu, vv in _poly_rect(
                            reg["u0"], reg["u1"], reg["v0"], reg["v1"])]
                    df.line(pts + [pts[0]], fill=hexa(col, 200),
                            width=max(1, int(S)))
                through(lv.name, fl)
                d = ImageDraw.Draw(canvas)
            r = 2.6 * S
            d.ellipse([x - r, y - r, x + r, y + r], fill=hexa(col, 255),
                      outline=(0, 0, 0, 255))
            _label(d, (x + 3 * S, y - 9 * S), it.id, F_ID, hexa(col, 255))

        # ---- legend
        lines = [title or f"{self.room} — layout reference frame",
                 "grid: 1 plan unit (~1 m), bold every 5; "
                 f"origin (0, 0) = {self.axes.get('origin', '')}",
                 f"+u → {self.axes.get('+u', '')}    "
                 f"+v → {self.axes.get('+v', '')}",
                 "runs: t 0→1 from the 't0' end; ticks every 1 unit (s)",
                 "levels: " + ", ".join(f"{L.name} (dy {L.dy:+.0f})"
                                        for L in self.levels.values())]
        lx, ly = ((view[0] + 8) * S, (view[1] + 8) * S) if view \
            else (8 * S, 8 * S)
        lh = 13 * S
        wbox = max(d.textlength(s_, font=F_HEAD if i == 0 else F_LAB)
                   for i, s_ in enumerate(lines)) + 12 * S
        d.rectangle([lx - 6 * S, ly - 6 * S, lx + wbox,
                     ly + (len(lines) + 1) * lh + 2 * S],
                    fill=(10, 12, 20, 225), outline=(200, 200, 210, 160))
        for i, s_ in enumerate(lines):
            d.text((lx, ly + i * lh), s_,
                   fill=(255, 214, 102, 255) if i == 0 else (245, 240, 225, 255),
                   font=F_HEAD if i == 0 else F_LAB)
        yy, xx = ly + len(lines) * lh + 2 * S, lx
        for L in self.levels.values():
            d.rectangle([xx, yy, xx + 10 * S, yy + 7 * S],
                        fill=hexa(L.color, 255))
            d.text((xx + 13 * S, yy - 1 * S), L.name, font=F_LAB,
                   fill=(245, 240, 225, 255))
            xx += 13 * S + d.textlength(L.name, font=F_LAB) + 14 * S

        if view is not None:
            canvas = canvas.crop([int(view[0] * S), int(view[1] * S),
                                  int(view[2] * S), int(view[3] * S)])
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(out)
        print(f"layout overlay -> {out}  ({len(self._items)} items, "
              f"{len(self.frames)} frames)")

def _label(d, xy, text, font, fill):
    x, y = xy
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
        d.text((x + ox, y + oy), text, font=font, fill=(0, 0, 0, 230))
    d.text((x, y), text, font=font, fill=fill)


# ------------------------------------------------------------ walk grid
class _WalkGrid:
    """The walk mask sampled once on a plan grid, shared by the checks."""

    def __init__(self, walk, step):
        self.walk, self.step = walk, step
        A = walk.allow
        self.u0 = min(a["u0"] for a in A) - step
        self.v0 = min(a["v0"] for a in A) - step
        u1 = max(a["u1"] for a in A) + step
        v1 = max(a["v1"] for a in A) + step
        self.nu = int(round((u1 - self.u0) / step)) + 1
        self.nv = int(round((v1 - self.v0) / step)) + 1
        self.free = [[walk.ok(self.u0 + i * step, self.v0 + j * step)
                      for j in range(self.nv)] for i in range(self.nu)]

    def cell(self, u, v):
        return (int(round((u - self.u0) / self.step)),
                int(round((v - self.v0) / self.step)))

    def free_near(self, u, v, rad):
        ci, cj = self.cell(u, v)
        k = int(rad / self.step) + 1
        for i in range(max(0, ci - k), min(self.nu, ci + k + 1)):
            for j in range(max(0, cj - k), min(self.nv, cj + k + 1)):
                if self.free[i][j]:
                    yield (self.u0 + i * self.step, self.v0 + j * self.step)

    def loop_cut(self, hu, hv):
        """Is the hole at (hu, hv) still ENCLOSED by walkable floor? Flood
        the NON-walkable cells from the grid's border (the grid is padded
        by a cell, so the border is always outside): if that flood
        reaches the hole, something blocks the walkway from its inner
        edge to its outer one and the loop is cut."""
        hi, hj = self.cell(hu, hv)
        seen = [[False] * self.nv for _ in range(self.nu)]
        stack = []
        for i in range(self.nu):
            for j in (0, self.nv - 1):
                if not self.free[i][j] and not seen[i][j]:
                    seen[i][j] = True
                    stack.append((i, j))
        for j in range(self.nv):
            for i in (0, self.nu - 1):
                if not self.free[i][j] and not seen[i][j]:
                    seen[i][j] = True
                    stack.append((i, j))
        while stack:
            a, b = stack.pop()
            if (a, b) == (hi, hj):
                return True
            # 8-connected on the BLOCKED side, so a diagonal pinch counts
            # as a cut — the character is 4-connected on the free side
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    x, y = a + da, b + db
                    if (0 <= x < self.nu and 0 <= y < self.nv
                            and not self.free[x][y] and not seen[x][y]):
                        seen[x][y] = True
                        stack.append((x, y))
        return False
