"""Pictures of the scene scripts, drawn to be MARKED UP with a pen.

Two views, both black-on-white SVG sized for an e-ink tablet:

  tree_svg(...)  one scene's decision tree. Every node and choice carries a
                 short handle (A, A1, B3) so a pen mark or a sentence can
                 point at it; every node shows six skill chips (filled =
                 that instinct speaks there) and a blank margin to write in;
                 the page ends with the legend of pen marks.
  map_svg(...)   the whole session, one row per week: the scenes that play,
                 the talks they open, and every flag drawn as a line from
                 the scene that sets it to the scenes that read it.

The handles are deterministic (breadth-first from `start`), so the same
scene always draws the same letters — `handles()` is the lookup for
turning "B3" back into a node and choice.
"""
from collections import defaultdict

INK, PAPER, GREY = "#000", "#fff", "#666"
SANS = "Helvetica, sans-serif"
SHORT = {"fiscal": "BRAIN", "procedure": "PROC", "educator": "EDU",
         "talkstory": "TALK", "mobilizing": "MOB", "basebuilding": "BASE"}
MINUS = "−"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def wrap(s, n):
    lines, cur = [], ""
    for w in s.split():
        if cur and len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def clip(s, n):
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def num(n):
    return (f"+{n}" if n > 0 else f"{MINUS}{-n}")


def fx_short(fx):
    """{+1 support, flag x} -> '+1 sup ⚑x' — the compact form for a row."""
    out = []
    for k, v in (fx or {}).items():
        if k == "support":
            out.append(f"{num(v)} sup")
        elif k == "influence":
            out.append(f"{num(v)} inf")
        elif k == "rapport":
            out += [f"{num(n)} {who}" for who, n in v.items()]
        elif k == "revenueK":
            a = abs(v)
            amt = f"${a // 1000}M" if a % 1000 == 0 else f"${a}K"
            out.append(("+" if v > 0 else MINUS) + amt)
        elif k == "flag":
            out.append(f"⚑{v}")
        elif k == "skill":
            out.append(f"+1 {SHORT.get(v, v)}")
        elif k == "unlock":
            out += [f"opens {c}" for c in v.get("talks", {})]
            out += [f"opens {a}" for a in v.get("actions", [])]
    return " ".join(out)


def choices_of(n):
    """A node's choices — or, for a no-choice node, its lone Continue."""
    return n["choices"] or [{"label": "Continue ▸", "goto": n.get("goto"), "_continue": True}]


def nodes_of(dlg):
    return [k for k, v in dlg.items() if isinstance(v, dict) and "choices" in v]


def targets(c):
    """(pass_target, fail_target) for a checked choice, (t, t) for a plain one."""
    if c.get("check"):
        p = (c.get("success") or {}).get("goto") or c.get("goto")
        f = (c.get("failure") or {}).get("goto") or c.get("goto")
        return p, f
    return c.get("goto"), c.get("goto")


def handles(dlg):
    """Breadth-first node order from start, then anything unreachable.
    Returns ({node_id: letter}, reachable_set)."""
    order, seen, q = [], set(), ["start"]
    while q:
        x = q.pop(0)
        if x in seen or x not in dlg:
            continue
        seen.add(x)
        order.append(x)
        for c in choices_of(dlg[x]):
            q += [t for t in targets(c) if t]
    reach = set(order)
    order += [n for n in nodes_of(dlg) if n not in reach]

    def letter(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    return {n: letter(i) for i, n in enumerate(order)}, reach


def svg_open(w, h):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" '
            f'font-family="Georgia, serif" font-size="15">',
            f'<rect width="100%" height="100%" fill="{PAPER}"/>',
            '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
            'markerHeight="8" orient="auto"><path d="M0,0L10,5L0,10z"/></marker></defs>']


def chips(x, y, voiced, skills, S, w=66, gap=6):
    for i, sid in enumerate(skills):
        cx = x + i * (w + gap)
        on = sid in voiced
        S.append(f'<rect x="{cx}" y="{y}" width="{w}" height="20" rx="10" '
                 f'fill="{INK if on else PAPER}" stroke="{INK}"/>')
        S.append(f'<text x="{cx + w / 2}" y="{y + 14}" text-anchor="middle" font-family="{SANS}" '
                 f'font-size="11" font-weight="bold" fill="{PAPER if on else INK}">'
                 f'{SHORT.get(sid, sid.upper()[:5])}</text>')


LEGEND = [
    ("→", "arrow from a choice to a node = go there"),
    ("○", "circle a hollow chip + write = add that voice"),
    ("—", "strike through a line = cut it"),
    ("+", "write in a margin = new choice or rewrite"),
    ("▢", "box drawn below the tree = new node"),
    ("A1", "every line has a handle to point at"),
    ("●", "filled chip = that skill speaks here"),
    ("○", "hollow chip = silent here"),
]


# --------------------------------------------------------------- the tree
def tree_svg(did, dlg, skills, chars, sched=None, flags_here=None):
    """skills: ordered skill ids. chars: session characters. sched: list of
    where the scene plays. flags_here: {"set": [...], "read": [...]}."""
    H, reach = handles(dlg)
    order = sorted(H, key=lambda n: (len(H[n]), H[n]))
    BX, BW, PAD = 24, 480, 16
    TOP_GAP = 46                       # room above every box for arrivals
    lane_x0 = BX + BW + 12
    # one lane per target node, in order of first use
    lanes = {}
    for nid in order:
        for c in choices_of(dlg[nid]):
            for t in targets(c):
                if t and t in dlg and t not in lanes:
                    lanes[t] = len(lanes)
    MX = lane_x0 + 12 * max(len(lanes), 1) + 14
    MW = 220
    W = MX + MW + 24

    # measure
    boxes, y = {}, 96 + (22 if flags_here and (flags_here["set"] or flags_here["read"]) else 0)
    for nid in order:
        n = dlg[nid]
        txt = wrap(n["text"].replace("\n\n", " ¶ "), 54)
        if len(txt) > 3:
            txt = txt[:3]
            txt[-1] = clip(txt[-1] + " …", 56)
        rows = []
        for i, c in enumerate(choices_of(n)):
            rows.append((i, c, 50 if c.get("check") else 32))
        h = PAD + 26 + 20 * len(txt) + 34 + 10 + sum(r[2] for r in rows) + 6
        y += TOP_GAP
        boxes[nid] = dict(y=y, h=h, txt=txt, rows=rows)
        y += h
    legend_y = y + 40
    Ht = legend_y + 24 + 22 * ((len(LEGEND) + 1) // 2) + 16

    S = svg_open(W, Ht)
    S.append(f'<text x="{BX}" y="38" font-size="24" font-weight="bold">{esc(did)}</text>')
    sub = " · ".join(sched or ["not scheduled"])
    S.append(f'<text x="{BX}" y="62" font-family="{SANS}" font-size="13">{esc(clip(sub, 110))}</text>')
    opens = []
    u = dlg.get("unlocks") or {}
    opens += [f"talk {c}" for c in (u.get("talks") or {})]
    opens += [f"action {a}" for a in (u.get("actions") or [])]
    if opens:
        S.append(f'<text x="{BX}" y="82" font-family="{SANS}" font-size="13">'
                 f'opens: {esc(", ".join(opens))}</text>')
    if flags_here and (flags_here["set"] or flags_here["read"]):
        bits = []
        if flags_here["set"]:
            bits.append("sets " + ", ".join("⚑" + f for f in flags_here["set"]))
        if flags_here["read"]:
            bits.append("reads " + ", ".join("⚑" + f for f in flags_here["read"]))
        S.append(f'<text x="{BX}" y="104" font-family="{SANS}" font-size="13">'
                 f'{esc(" · ".join(bits))}</text>')

    stubs = defaultdict(list)          # target -> [(x, y)]
    for nid in order:
        b, n = boxes[nid], dlg[nid]
        y0 = b["y"]
        dash = ' stroke-dasharray="8 6"' if nid not in reach else ""
        S.append(f'<rect x="{BX}" y="{y0}" width="{BW}" height="{b["h"]}" fill="{PAPER}" '
                 f'stroke="{INK}" stroke-width="{3 if nid == "start" else 1.5}" rx="8"{dash}/>')
        S.append(f'<rect x="{MX}" y="{y0}" width="{MW}" height="{b["h"]}" fill="none" '
                 f'stroke="{INK}" stroke-dasharray="3 5"/>')
        S.append(f'<text x="{MX + 8}" y="{y0 + 16}" font-family="{SANS}" font-size="11" '
                 f'fill="{GREY}">{H[nid]} notes</text>')
        hx, hy = BX + 26, y0 + 26
        S.append(f'<circle cx="{hx}" cy="{hy}" r="15" fill="{INK}"/>')
        S.append(f'<text x="{hx}" y="{hy + 6}" fill="{PAPER}" font-weight="bold" '
                 f'text-anchor="middle">{H[nid]}</text>')
        who = (chars.get(n["speaker"], {}).get("name", n["speaker"]).upper()
               if n.get("speaker") else "narration")
        extra = "  UNREACHABLE" if nid not in reach else ""
        S.append(f'<text x="{BX + 50}" y="{hy + 6}" font-weight="bold" font-size="17">{esc(nid)} '
                 f'<tspan font-style="italic" font-weight="normal" font-size="15">{esc(who)}</tspan>'
                 f'<tspan font-family="{SANS}" font-size="12" font-weight="bold">{extra}</tspan></text>')
        yy = y0 + PAD + 26
        for t in b["txt"]:
            yy += 20
            S.append(f'<text x="{BX + 16}" y="{yy}">{esc(t)}</text>')
        yy += 10
        chips(BX + 16, yy, {v["t"] for v in n.get("voices", [])}, skills, S)
        yy += 34
        S.append(f'<line x1="{BX}" x2="{BX + BW}" y1="{yy}" y2="{yy}" stroke="{INK}"/>')
        yy += 6
        for i, c, rh in b["rows"]:
            ly = yy + 22
            hd = f"{H[nid]}{i + 1}"
            S.append(f'<text x="{BX + 14}" y="{ly}" font-weight="bold">{hd}'
                     f'<tspan font-weight="normal" dx="10">{esc(clip(c["label"], 38 if c.get("check") else 42))}</tspan></text>')
            p, f = targets(c)
            if c.get("check"):
                ck = c["check"]
                tag = f'{SHORT.get(ck["skill"], ck["skill"])} {ck["dc"]}{" · RED" if ck.get("type") == "red" else ""}'
                S.append(f'<rect x="{BX + BW - 140}" y="{ly - 15}" width="130" height="20" rx="3" fill="{INK}"/>')
                S.append(f'<text x="{BX + BW - 75}" y="{ly}" text-anchor="middle" fill="{PAPER}" '
                         f'font-family="{SANS}" font-size="11" font-weight="bold">CHECK {esc(tag)}</text>')
                ante = fx_short(c.get("effects"))
                line = (f'✓ {fx_short(c["success"].get("effects")) or "—"}   '
                        f'✗ {fx_short(c["failure"].get("effects")) or "—"}'
                        + (f"   stake {ante}" if ante else ""))
                S.append(f'<text x="{BX + 44}" y="{ly + 20}" font-family="{SANS}" font-size="12">'
                         f'{esc(clip(line, 64))}</text>')
            else:
                fx = fx_short(c.get("effects"))
                if fx:
                    S.append(f'<text x="{BX + BW - 12}" y="{ly}" text-anchor="end" font-family="{SANS}" '
                             f'font-size="12">{esc(clip(fx, 22))}</text>')
            ends = []
            for t, sy in ((p, ly - 5), (f, ly + 15)) if p != f else ((p, ly - 5),):
                if t and t in dlg:
                    stubs[t].append((BX + BW, sy))
                else:
                    ends.append(sy)
            for sy in ends:
                S.append(f'<text x="{BX + BW + 4}" y="{sy + 4}" font-family="{SANS}" '
                         f'font-size="11">■</text>')
            yy += rh

    for t, pts in stubs.items():
        lx = lane_x0 + 12 * lanes[t]
        ty = boxes[t]["y"]
        ay = ty - 12 - 8 * (lanes[t] % 3)
        ax = BX + BW - 40 - 18 * (lanes[t] % 4)
        ys = [sy for _, sy in pts] + [ay]
        for x, sy in pts:
            S.append(f'<path d="M{x},{sy} H{lx}" stroke="{INK}" stroke-width="1.6"/>')
        S.append(f'<path d="M{lx},{min(ys)} V{max(ys)}" stroke="{INK}" stroke-width="1.6"/>')
        S.append(f'<path d="M{lx},{ay} H{ax} V{ty - 2}" fill="none" stroke="{INK}" '
                 f'stroke-width="1.6" marker-end="url(#a)"/>')

    S.append(f'<rect x="{BX}" y="{legend_y - 22}" width="{W - 2 * BX}" '
             f'height="{Ht - legend_y + 6}" fill="{PAPER}" stroke="{INK}" rx="6"/>')
    S.append(f'<text x="{BX + 16}" y="{legend_y}" font-family="{SANS}" font-size="14" '
             f'font-weight="bold">PEN MARKS   <tspan font-weight="normal" font-size="12">'
             f'■ = scene ends</tspan></text>')
    half = (len(LEGEND) + 1) // 2
    for i, (mark, say) in enumerate(LEGEND):
        col, row = divmod(i, half)
        S.append(f'<text x="{BX + 16 + col * (W - 2 * BX) / 2}" y="{legend_y + 24 + 22 * row}" '
                 f'font-family="{SANS}" font-size="13"><tspan font-weight="bold">{esc(mark)}</tspan>'
                 f'  {esc(say)}</text>')
    S.append("</svg>")
    return "\n".join(S)


# --------------------------------------------------------------- the map
def schedule(data, dialogues):
    """[(week, title, [(dialogue_id, role)])] in play order, plus the set of
    scenes that never play. Mirrors calFor() in main.js."""
    cal = {c["week"]: c for c in data.get("calendar", [])}
    gens = data.get("genericEvents", [])
    sd = data.get("sineDieWeek", 16)
    titles = data.get("weekTitles", [])
    weeks, placed = [], set()
    for w in range(1, sd + 1):
        hit = cal.get(w, {})
        title = hit.get("title") or (titles[w] if w < len(titles) else "") or "Interim"
        ev = hit["event"] if "event" in hit else (
            gens[(w - 2) % len(gens)] if gens and 2 <= w < sd else None)
        row = []
        if hit.get("pre"):
            row.append((hit["pre"], "before the week"))
        if ev:
            row.append((ev, "generic event" if "event" not in hit else "event"))
        opened = []
        for d, _ in list(row):
            dl = dialogues.get(d) or {}
            u = dl.get("unlocks") or {}
            opened += [(t, f"talk: {c}") for c, t in (u.get("talks") or {}).items()]
            for nid in nodes_of(dl):
                for c in dl[nid]["choices"]:
                    for o in (c, c.get("success") or {}, c.get("failure") or {}):
                        fu = (o.get("effects") or {}).get("unlock") or {}
                        opened += [(t, f"talk: {cc} (if chosen)") for cc, t in (fu.get("talks") or {}).items()]
        row += opened
        weeks.append((w, title, row))
        placed |= {d for d, _ in row}
    return weeks, [d for d in dialogues if d not in placed]


def scene_facts(dlg):
    voiced, speakers, checks, sets, reads = set(), [], 0, set(), set()
    for nid in nodes_of(dlg):
        n = dlg[nid]
        voiced |= {v["t"] for v in n.get("voices", [])}
        if n.get("speaker") and n["speaker"] not in speakers:
            speakers.append(n["speaker"])
        for c in n["choices"]:
            for o in (c, c.get("success") or {}, c.get("failure") or {}):
                voiced |= {v["t"] for v in o.get("voices", [])}
                f = (o.get("effects") or {}).get("flag")
                if f:
                    sets.add(f)
            if c.get("check"):
                checks += 1
                reads |= {m["id"] for m in c["check"].get("mods", []) if m.get("from") == "flag"}
    return dict(voiced=voiced, speakers=speakers, checks=checks,
                nodes=len(nodes_of(dlg)), sets=sets, reads=reads)


def map_svg(data, dialogues, skills):
    weeks, never = schedule(data, dialogues)
    chars = data.get("characters", {})
    facts = {d: scene_facts(dl) for d, dl in dialogues.items()}
    LX, SX, BW, BH, ROWGAP = 24, 128, 420, 46, 14
    first, y = {}, 100
    rows = []
    for w, title, row in weeks:
        boxes, repeats = [], []
        for d, role in row:
            if d in first:
                if d not in repeats:
                    repeats.append(d)
            else:
                first[d] = None
                boxes.append((d, role))
        h = max(1, len(boxes)) * (BH + 6) + (20 if repeats else 0)
        rows.append((w, title, boxes, repeats, y, h))
        for i, (d, role) in enumerate(boxes):
            first[d] = (y + i * (BH + 6), role)
        y += h + ROWGAP
    never_y = y + 10
    for i, d in enumerate(never):
        first[d] = (never_y + 26 + i * (BH + 6), "never plays")
    y = never_y + 26 + max(1, len(never)) * (BH + 6)

    # flags: setter -> readers
    setters, readers = defaultdict(list), defaultdict(list)
    for d, f in facts.items():
        for fl in f["sets"]:
            setters[fl].append(d)
        for fl in f["reads"]:
            readers[fl].append(d)
    flags = sorted(set(setters) | set(readers), key=lambda fl: min(
        [first[d][0] for d in setters.get(fl, []) + readers.get(fl, []) if first.get(d)] or [0]))
    lane0 = SX + BW + 30
    W = lane0 + 22 * max(len(flags), 1) + 160
    Ht = y + 40

    S = svg_open(W, Ht)
    S.append(f'<text x="{LX}" y="36" font-size="24" font-weight="bold">The session, week by week</text>')
    S.append(f'<text x="{LX}" y="58" font-family="{SANS}" font-size="13">Each scene once, where it '
             f'first plays. Lines on the right are flags: ● where set, ▶ where read, ○ never read.</text>')
    for w, title, boxes, repeats, ry, h in rows:
        S.append(f'<line x1="{LX}" x2="{W - LX}" y1="{ry - ROWGAP / 2}" y2="{ry - ROWGAP / 2}" '
                 f'stroke="{INK}" stroke-width=".4"/>')
        S.append(f'<text x="{LX}" y="{ry + 24}" font-size="26" font-weight="bold">{w}</text>')
        S.append(f'<text x="{LX}" y="{ry + 42}" font-family="{SANS}" font-size="11">'
                 f'{esc(clip(title, 18))}</text>')
        if repeats:
            S.append(f'<text x="{SX}" y="{ry + h - 6}" font-family="{SANS}" font-size="11" fill="{GREY}">'
                     f'again: {esc(clip(", ".join(repeats), 70))}</text>')
    for d, (by, role) in ((d, v) for d, v in first.items() if v):
        f = facts[d]
        big = role in ("event", "generic event", "before the week", "never plays")
        dash = ' stroke-dasharray="6 5"' if role == "never plays" else ""
        S.append(f'<rect x="{SX}" y="{by}" width="{BW}" height="{BH}" rx="6" fill="{PAPER}" '
                 f'stroke="{INK}" stroke-width="{2.2 if big else 1}"{dash}/>')
        who = ", ".join(chars.get(s, {}).get("name", s) for s in f["speakers"]) or "narration"
        S.append(f'<text x="{SX + 10}" y="{by + 19}" font-weight="bold" font-size="15">{esc(d)}'
                 f'<tspan font-weight="normal" font-family="{SANS}" font-size="11" dx="8">'
                 f'{esc(role)}</tspan></text>')
        meta = f'{f["nodes"]} node{"s" if f["nodes"] != 1 else ""} · {f["checks"]} check{"s" if f["checks"] != 1 else ""} · {who}'
        S.append(f'<text x="{SX + 10}" y="{by + 37}" font-family="{SANS}" font-size="11">'
                 f'{esc(clip(meta, 46))}</text>')
        for i, sid in enumerate(skills):     # six voice dots, right side
            cx = SX + BW - 112 + i * 18
            S.append(f'<circle cx="{cx}" cy="{by + 33}" r="6" fill="{INK if sid in f["voiced"] else PAPER}" '
                     f'stroke="{INK}"/>')
    S.append(f'<text x="{LX}" y="76" font-family="{SANS}" font-size="13">Dots, left to right: '
             f'{" · ".join(SHORT.get(s, s) for s in skills)} (filled = that skill speaks in the scene).</text>')
    S.append(f'<text x="{LX}" y="{never_y + 14}" font-family="{SANS}" font-size="13" '
             f'font-weight="bold">{"NEVER PLAYS" if never else ""}</text>')

    for k, fl in enumerate(flags):
        lx = lane0 + 22 * k
        ends = []
        for d in setters.get(fl, []):
            if first.get(d):
                ends.append(("set", first[d][0] + BH / 2))
        for d in readers.get(fl, []):
            if first.get(d):
                ends.append(("read", first[d][0] + BH / 2 + 6))
        if not ends:
            continue
        ys = [e[1] for e in ends]
        S.append(f'<path d="M{lx},{min(ys)} V{max(ys)}" stroke="{INK}" stroke-width="2"/>')
        for kind, ey in ends:
            if kind == "set":
                S.append(f'<path d="M{SX + BW},{ey} H{lx}" stroke="{INK}" stroke-width="1.2"/>')
                S.append(f'<circle cx="{lx}" cy="{ey}" r="5" fill="{INK}"/>')
            else:
                S.append(f'<path d="M{lx},{ey} H{SX + BW + 2}" stroke="{INK}" stroke-width="1.2" '
                         f'marker-end="url(#a)"/>')
        unread = not readers.get(fl)
        early = (setters.get(fl) and readers.get(fl) and
                 min(first[d][0] for d in readers[fl] if first.get(d)) <
                 min(first[d][0] for d in setters[fl] if first.get(d)))
        top = min(ys)
        if unread:
            S.append(f'<circle cx="{lx}" cy="{top + 16}" r="5" fill="{PAPER}" stroke="{INK}" stroke-width="1.5"/>')
            S.append(f'<path d="M{lx},{top} V{top + 11}" stroke="{INK}" stroke-width="2"/>')
        label = fl + ("  (never read)" if unread else "") + ("  ⚠ read before set" if early else "")
        tx = lane0 + 22 * len(flags)
        S.append(f'<path d="M{lx},{top} H{tx - 4}" stroke="{INK}" stroke-width=".6" '
                 f'stroke-dasharray="2 3"/>')
        S.append(f'<text x="{tx}" y="{top + 4}" font-family="{SANS}" font-size="11" '
                 f'font-weight="bold">⚑ {esc(label)}</text>')
    S.append("</svg>")
    return "\n".join(S)


# --------------------------------------------------------------- big pages
import re as _re

LONG = {"fiscal": "BRAIN", "procedure": "PROCEDURE", "educator": "EDUCATOR",
        "talkstory": "TALK STORY", "mobilizing": "MOBILIZING", "basebuilding": "BASE BUILD"}


def sentences(text):
    return [x.strip() for x in _re.split(r'(?<=[.!?…"”])\s+(?=["“A-Z])', text.replace("\n\n", " ")) if x.strip()]


def first_sentence(text, n):
    ss = sentences(text)
    return clip(ss[0] if ss else text, n)


def passage(text, width, head=3, tail=3):
    """A long passage as its first and last lines with an ellipsis between,
    so the page always shows how the beat opens AND how it lands."""
    lines = wrap(text.replace("\n\n", " "), width)
    if len(lines) <= head + tail + 1:
        return lines
    return lines[:head - 1] + [lines[head - 1] + " …"] + ["… " + lines[-tail]] + lines[-tail + 1:]


def fx_words(fx):
    """Effects as ▲/▼ words for a card: '▲ 3 support  ▼ 1 influence'."""
    out = []
    for k, v in (fx or {}).items():
        if k in ("support", "influence"):
            out.append(f"{'▲' if v > 0 else '▼'} {abs(v)} {k}")
        elif k == "rapport":
            out += [f"{'▲' if n > 0 else '▼'} {abs(n)} {who} introducer" for who, n in v.items()]
        elif k == "revenueK":
            a = abs(v)
            amt = f"${a // 1000}M" if a % 1000 == 0 else f"${a}K"
            out.append(f"{'▲' if v > 0 else '▼'} {amt} revenue")
        elif k == "flag":
            out.append(f"⚑ {v}")
        elif k == "skill":
            out.append(f"▲ {LONG.get(v, v)} pip")
        elif k == "unlock":
            out += [f"opens talk {c}" for c in v.get("talks", {})]
            out += [f"opens {a}" for a in v.get("actions", [])]
    return "   ".join(out)


def node_pages(did, dlg, skills, chars, where=""):
    """One page per node, laid out like the game's own reader so it needs
    no legend: who is talking, what happens, each instinct's line (silent
    ones as a dashed slot to write in), each choice as a numbered card with
    its reply, effects and next node, checks as a fork, and an empty card
    for a new choice. Returns [(letter, svg)]."""
    H, reach = handles(dlg)
    order = sorted(H, key=lambda n: (len(H[n]), H[n]))
    W, X, R = 600, 20, 580
    pages = []
    for nid in order:
        n = dlg[nid]
        S = []

        def t(x, y, s, size=18, bold=False, sans=False, italic=False, fill=INK, anchor=None, ls=None):
            S.append(f'<text x="{x}" y="{y}" font-size="{size}"'
                     + (' font-weight="bold"' if bold else "")
                     + (' font-style="italic"' if italic else "")
                     + (f' font-family="{SANS}"' if sans else "")
                     + (f' text-anchor="{anchor}"' if anchor else "")
                     + (f' letter-spacing="{ls}"' if ls else "")
                     + (f' fill="{fill}"' if fill != INK else "") + f'>{esc(s)}</text>')

        def pill(x, y, w, label, dark=True):
            S.append(f'<rect x="{x}" y="{y}" width="{w}" height="24" rx="12" fill="{INK if dark else PAPER}"'
                     + ("" if dark else f' stroke="{INK}" stroke-width="2"') + "/>")
            t(x + w / 2, y + 17, label, 13, True, True, fill=PAPER if dark else INK, anchor="middle")

        def go(target):
            return f"→ {H[target]}" if target and target in dlg else "ends"

        # where am I: scene line + the node strip
        t(X, 30, clip(where or did, 52), 14, sans=True, fill="#555")
        k = len(order)
        step = min(54, 240 / max(k - 1, 1))
        x0 = R - 12 - step * (k - 1)
        for j in range(k - 1):
            S.append(f'<line x1="{x0 + j * step + 12}" y1="24" x2="{x0 + (j + 1) * step - 14}" y2="24" '
                     f'stroke="{INK}" stroke-width="2" marker-end="url(#a)"/>')
        for j, m in enumerate(order):
            on = m == nid
            S.append(f'<circle cx="{x0 + j * step}" cy="24" r="12" fill="{INK if on else PAPER}" '
                     f'stroke="{INK}" stroke-width="2"/>')
            t(x0 + j * step, 30, H[m], 14, True, True, fill=PAPER if on else INK, anchor="middle")

        # who is talking
        y = 52
        sp = n.get("speaker")
        if sp:
            ch = chars.get(sp, {})
            S.append(f'<rect x="{X}" y="{y}" width="64" height="72" rx="6" fill="#e8e8e8"/>')
            S.append(f'<circle cx="{X + 32}" cy="{y + 26}" r="13" fill="#333"/>')
            S.append(f'<path d="M{X + 8},{y + 72} C{X + 10},{y + 48} {X + 54},{y + 48} {X + 56},{y + 72} Z" fill="#333"/>')
            t(X + 80, y + 32, ch.get("name", sp), 26, True)
            t(X + 80, y + 58, f'{ch.get("role", "")} · node {H[nid]} {nid}', 15, sans=True)
        else:
            t(X, y + 32, "Narration", 26, True, italic=True)
            t(X, y + 58, f"no one speaking · node {H[nid]} {nid}"
              + ("  (unreachable)" if nid not in reach else ""), 15, sans=True)
        y += 108

        # what happens
        for line in passage(n["text"], 46):
            t(X, y, line, 20)
            y += 28
        y += 16

        marks = [(0, 0), (len(S), y)]      # page breaks may fall at a mark
        # instincts
        t(X, y, "YOUR INSTINCTS", 14, True, True, ls=1.5)
        y += 12
        lines = {v["t"]: v["text"] for v in n.get("voices", [])}
        for sid in skills:
            on = sid in lines
            S.append(f'<rect x="{X}" y="{y}" width="96" height="30" rx="15" fill="{INK if on else PAPER}"'
                     + ("" if on else f' stroke="{INK}" stroke-width="2" stroke-dasharray="5 4"') + "/>")
            t(X + 48, y + 20, LONG.get(sid, sid.upper()), 13 if len(LONG.get(sid, "")) < 11 else 12,
              True, True, fill=PAPER if on else INK, anchor="middle")
            if on:
                vl = wrap(lines[sid], 54)
                if len(vl) > 2:
                    vl = vl[:2]
                    vl[1] = clip(vl[1] + " …", 56)
                for j, ln in enumerate(vl):
                    t(X + 108, y + 20 + 22 * j, ln, 16, italic=True)
                y += 22 * (len(vl) - 1)
            else:
                S.append(f'<line x1="{X + 108}" y1="{y + 22}" x2="{R}" y2="{y + 22}" stroke="{INK}" '
                         f'stroke-dasharray="2 5" stroke-width="1.5"/>')
                t(X + 110, y + 16, "silent — write a line here to add it", 12, sans=True, fill="#777")
            y += 40
        y += 22

        marks.append((len(S), y))
        # choices
        t(X, y, "YOU SAY" if n["choices"] else "THEN", 14, True, True, ls=1.5)
        y += 12
        for i, c in enumerate(choices_of(n)):
            lab = wrap(c["label"], 46)[:2]
            p, f = targets(c)
            if c.get("check"):
                rows = []
                for word, o, tg in (("✓ PASS", c.get("success") or {}, p), ("✗ FAIL", c.get("failure") or {}, f)):
                    rows.append((word, first_sentence(o.get("reply", ""), 44), fx_words(o.get("effects")), tg))
                h = 36 + 26 * len(lab) + 30 + (22 if c.get("effects") else 0) + 2 * 44 + 8
            else:
                h = 36 + 26 * len(lab) + (26 if c.get("reply") else 0) + 28
            S.append(f'<rect x="{X}" y="{y}" width="{R - X}" height="{h}" rx="10" fill="{PAPER}" '
                     f'stroke="{INK}" stroke-width="{3 if c.get("check") else 2}"/>')
            S.append(f'<circle cx="{X + 28}" cy="{y + 30}" r="17" fill="{INK}"/>')
            t(X + 28, y + 37, str(i + 1), 19, True, fill=PAPER, anchor="middle")
            yy = y + 37
            for ln in lab:
                t(X + 56, yy, ln, 19)
                yy += 26
            if c.get("check"):
                ck = c["check"]
                S.append(f'<rect x="{X + 56}" y="{yy - 12}" width="22" height="22" rx="4" fill="{PAPER}" '
                         f'stroke="{INK}" stroke-width="2"/>')
                for dx, dy in ((6, 6), (16, 16), (11, 11)):
                    S.append(f'<circle cx="{X + 56 + dx}" cy="{yy - 12 + dy}" r="2"/>')
                t(X + 86, yy + 5, f'ROLL {LONG.get(ck["skill"], ck["skill"])} vs {ck["dc"]} · '
                  + ("one shot" if ck.get("type") == "red" else "can retry"), 14, True, True)
                yy += 30
                if c.get("effects"):
                    t(X + 86, yy, "stake, win or lose:  " + fx_words(c["effects"]), 13, sans=True)
                    yy += 22
                top = yy - 8
                for word, rep, fx, tg in rows:
                    S.append(f'<path d="M{X + 40},{yy - 5} H{X + 56}" stroke="{INK}" stroke-width="2"/>')
                    t(X + 62, yy, word, 14, True, True)
                    t(X + 126, yy, rep, 15, italic=True, fill="#333")
                    t(X + 126, yy + 20, fx or "no change", 13, sans=True)
                    if p != f:
                        pill(R - 96, yy - 16, 84, go(tg))
                    yy += 44
                S.append(f'<path d="M{X + 40},{top} V{yy - 49}" stroke="{INK}" stroke-width="2"/>')
                if p == f:
                    pill(R - 120, y + h - 34, 108, "both " + go(p) if p in dlg else "ends")
            else:
                if c.get("reply"):
                    t(X + 56, yy, first_sentence(c["reply"], 58), 15, italic=True, fill="#333")
                    yy += 26
                if not c.get("_continue"):
                    ft = (f"FORCED at {LONG.get(c['force']['skill'], c['force']['skill'])} "
                          f"{c['force']['min']}+ · ") if c.get("force") else ""
                    t(X + 56, yy, ft + (fx_words(c.get("effects")) or "no change"), 14, True, True)
                pill(R - 120, yy - 16, 108, ("then " + go(p)) if p in dlg else "ends")
            y += h + 12
            marks.append((len(S), y))

        # a new choice
        S.append(f'<rect x="{X}" y="{y}" width="{R - X}" height="74" rx="10" fill="{PAPER}" stroke="{INK}" '
                 f'stroke-width="2" stroke-dasharray="6 5"/>')
        S.append(f'<circle cx="{X + 28}" cy="{y + 37}" r="17" fill="{PAPER}" stroke="{INK}" stroke-width="2" '
                 f'stroke-dasharray="4 3"/>')
        t(X + 28, y + 44, str(len(n["choices"]) + 1), 19, True, anchor="middle")
        t(X + 56, y + 43, "write a new choice here", 16, italic=True, fill="#777")
        y += 74 + 20
        marks.append((len(S), y))
        pages += screens(H[nid], f"{did} · {H[nid]} {nid}", S, marks)
    return pages


SCREEN_W, SCREEN_H = 600, 755      # the tablet panel's shape (642 x 808)


def screens(letter, title, S, marks):
    """Pack a node's blocks onto pages the shape of the screen, so the app
    never has to shrink a page to fit. A block never splits; a later page
    gets a one-line header saying where it is."""
    blocks = [(marks[i][0], marks[i + 1][0], marks[i][1], marks[i + 1][1])
              for i in range(len(marks) - 1) if marks[i + 1][0] > marks[i][0]]
    pages, cur, top = [], [], 0
    for b in blocks:
        head = 0 if not pages else 72
        used = (cur[-1][3] - cur[0][2]) if cur else 0
        if cur and head + used + (b[3] - b[2]) > SCREEN_H - 30:
            pages.append(cur)
            cur = []
        cur.append(b)
    if cur:
        pages.append(cur)
    out = []
    for k, pg in enumerate(pages):
        head = 0 if k == 0 else 72
        dy = head - pg[0][2]
        body = [ln for b in pg for ln in S[b[0]:b[1]]]
        h = max(SCREEN_H, head + pg[-1][3] - pg[0][2] + 30)
        P = svg_open(SCREEN_W, h)
        if k:
            P.append(f'<text x="20" y="30" font-size="14" font-family="{SANS}" fill="#555">'
                     f'{esc(title.upper())} · {k + 1}/{len(pages)}</text>')
        P.append(f'<g transform="translate(0,{dy})">')
        P += body
        P.append("</g>")
        if k < len(pages) - 1:
            P.append(f'<text x="580" y="{h - 12}" text-anchor="end" font-size="14" font-family="{SANS}" '
                     f'fill="#555">continues {k + 2}/{len(pages)} →</text>')
        P.append("</svg>")
        out.append((f"{letter}{k + 1}" if len(pages) > 1 else letter, "\n".join(P)))
    return out
