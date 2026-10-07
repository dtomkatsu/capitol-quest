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
        for c in dlg[x]["choices"]:
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
        for c in dlg[nid]["choices"]:
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
        for i, c in enumerate(n["choices"]):
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
def node_pages(did, dlg, skills, chars):
    """One page per node, sized for a small e-ink panel: big type, the
    node's full text, chips you can circle, each choice in its own box with
    where it goes, and a notes area at the bottom. Returns [(letter, svg)]."""
    H, reach = handles(dlg)
    order = sorted(H, key=lambda n: (len(H[n]), H[n]))
    W, X = 600, 20
    out = []
    for nid in order:
        n = dlg[nid]
        S, y = [], 0

        def t(x, yy, s, size=22, bold=False, sans=False, fill=INK, anchor=None, italic=False):
            S.append(f'<text x="{x}" y="{yy}" font-size="{size}"'
                     + (' font-weight="bold"' if bold else "")
                     + (' font-style="italic"' if italic else "")
                     + (f' font-family="{SANS}"' if sans else "")
                     + (f' text-anchor="{anchor}"' if anchor else "")
                     + (f' fill="{fill}"' if fill != INK else "") + f'>{esc(s)}</text>')
        # header: big handle, node id, who
        S.append(f'<circle cx="{X + 28}" cy="40" r="26" fill="{INK}"/>')
        t(X + 28, 50, H[nid], 30, True, anchor="middle", fill=PAPER)
        who = (chars.get(n["speaker"], {}).get("name", n["speaker"])
               if n.get("speaker") else "narration")
        t(X + 66, 36, nid + ("  (unreachable)" if nid not in reach else ""), 26, True)
        t(X + 66, 62, f"{did} · {who}", 17, sans=True, italic=False)
        y = 104
        for para in n["text"].split("\n\n"):
            for line in wrap(para, 44):
                t(X, y, line, 22)
                y += 30
            y += 8
        # chips, 3 x 2, big enough to circle
        y += 6
        voiced = {v["t"] for v in n.get("voices", [])}
        cw, chh = 178, 42
        for i, sid in enumerate(skills):
            cx = X + (i % 3) * (cw + 12)
            cy = y + (i // 3) * (chh + 12)
            on = sid in voiced
            S.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{chh}" rx="21" '
                     f'fill="{INK if on else PAPER}" stroke="{INK}" stroke-width="2"/>')
            t(cx + cw / 2, cy + 28, SHORT.get(sid, sid), 19, True, True,
              PAPER if on else INK, "middle")
        y += 2 * (chh + 12) + 14
        # choices
        for i, c in enumerate(n["choices"]):
            hd = f"{H[nid]}{i + 1}"
            lab = wrap(c["label"], 38)
            p, f = targets(c)
            go = lambda x: f"→ {H[x]} {x}" if x and x in dlg else "■ ends"
            lines = []
            if c.get("check"):
                ck = c["check"]
                lines.append(f'CHECK {SHORT.get(ck["skill"], ck["skill"])} {ck["dc"]}'
                             + (" RED" if ck.get("type") == "red" else "")
                             + (f'  stake {fx_short(c.get("effects"))}' if c.get("effects") else ""))
                lines.append(f'✓ {go(p)}  {fx_short(c["success"].get("effects"))}')
                lines.append(f'✗ {go(f)}  {fx_short(c["failure"].get("effects"))}')
            else:
                lines.append(f'{go(p)}  {fx_short(c.get("effects"))}')
            bh = 20 + 28 * len(lab) + 26 * len(lines) + 8
            S.append(f'<rect x="{X}" y="{y}" width="{W - 2 * X}" height="{bh}" rx="8" '
                     f'fill="{PAPER}" stroke="{INK}" stroke-width="2"/>')
            t(X + 14, y + 36, hd, 26, True)
            ly = y + 34
            for ln in lab:
                t(X + 76, ly, ln, 21)
                ly += 28
            for ln in lines:
                t(X + 76, ly, ln, 17, True if ln.startswith("CHECK") else False, True)
                ly += 26
            y += bh + 12
        # notes area
        y += 8
        S.append(f'<rect x="{X}" y="{y}" width="{W - 2 * X}" height="170" rx="8" fill="none" '
                 f'stroke="{INK}" stroke-dasharray="4 6"/>')
        t(X + 12, y + 24, f"notes for {H[nid]}: rewrite, new choice, arrows to a letter", 15,
          sans=True, fill=GREY)
        y += 170 + 20
        out.append((H[nid], "\n".join(svg_open(W, y) + S + ["</svg>"])))
    return out
