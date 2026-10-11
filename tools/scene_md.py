"""Markdown drafts <-> scene scripts.

A draft is a plain Markdown file you can TYPE dialogue into, laid out like
the tablet pages: a heading per beat, the speaker in bold, instincts as
bullets, each choice as a numbered sub-heading with its reply, effect and
where it goes next. `md_to_scene()` turns one into .scene text (which
scenes.parse_scene then reads); `dlg_to_md()` goes the other way.

    ---                                  front matter: header lines, verbatim
    talks: grange, office
    actions: lobby
    ---

    ## A · start                          a beat (letter optional, id required)
    **Yamamoto:** You enter the office…  speaker on the first line (optional)
    Another paragraph.                   blank line = new paragraph
    - **Talk Story:** A voice line.      an instinct

    ### 1. [Brain 4+] Lead with…         a choice ([Skill N+] forced,
    She furrows her eyebrows.            [Skill DC red|white] a dice check)
    - effect: +1 influence, flag x       same words as the scene file
    - then: B                            a beat's letter or id, or "end"

    ### 2. [Talk Story 12 red] Call him.
    - mods: influence/25
    Pass:                                for a check, everything after
    He picks up the phone.               Pass:/Fail: belongs to that outcome
    - then: B
    Fail:
    "In my own office?"

    -> B                                 a beat with no choices: Continue to B

Blank `- effect:` / `- then:` lines and lone placeholders (…, ?, TBD) are
ignored, so a half-written draft still converts. The bold is optional:
`Yamamoto: …` and `- Talk Story: …` work too. `// …` lines are notes.
"""
import re

BEAT_RE = re.compile(r"^##\s+(?:([A-Z]{1,2})\s*[·.:\-]\s*)?([A-Za-z0-9_\-]+)\s*$")
CHOICE_RE = re.compile(r"^###\s+\d+[.)]\s*(.*)$")
SPEAKER_RE = re.compile(r"^(?:\*\*([^*]+?):\*\*|([A-Z][A-Za-z.\- ]{1,24}):)\s*(.*)$")
VOICE_RE = re.compile(r"^[-*]\s+(?:\*\*([^*]+?):\*\*|([A-Za-z][A-Za-z \-]{1,20}):)\s*(.*)$")
FIELD_RE = re.compile(r"^[-*]\s+([A-Za-z_]+):\s*(.*)$")
PLACEHOLDER = {"", "…", "...", "?", "tbd", "todo", "-", "—"}


def _vm(s, V):
    """An instinct line: '- **Talk Story:** …' or '- Talk Story: …'."""
    m = VOICE_RE.match(s)
    if not m:
        return None
    sid = V.skill(m.group(1) or m.group(2))
    return (sid, m.group(3)) if sid else None


def _blank(v):
    return v.strip().lower() in PLACEHOLDER


def _paras(lines):
    """Consecutive non-blank lines are one paragraph (typed text wraps)."""
    out, cur = [], []
    for ln in lines + [""]:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            out.append(" ".join(cur))
            cur = []
    return [p for p in out if not _blank(p)]


def md_to_scene(text, did, V):
    # `// …` lines are notes to yourself: they stay in the file, never ship
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("//")]
    i, header = 0, []
    # front matter
    if lines and lines[0].strip() == "---":
        j = 1
        while j < len(lines) and lines[j].strip() != "---":
            if lines[j].strip():
                header.append(lines[j].strip())
            j += 1
        i = j + 1
    # skip a top-level title and anything else before the first beat
    while i < len(lines) and not BEAT_RE.match(lines[i].strip()):
        i += 1
    beats = []          # [(letter, id, [lines])]
    while i < len(lines):
        m = BEAT_RE.match(lines[i].strip())
        j = i + 1
        while j < len(lines) and not BEAT_RE.match(lines[j].strip()):
            j += 1
        beats.append((m.group(1), m.group(2), lines[i + 1:j]))
        i = j
    letters = {b[0]: b[1] for b in beats if b[0]}

    def target(v):
        v = v.strip()
        if _blank(v) or v.lower() == "end":
            return None
        return letters.get(v.upper(), v) if len(v) <= 2 and v.upper() in letters else v

    S = [f"=== {did}"] + header
    for _, nid, body in beats:
        S += ["", f"--- {nid}"]
        k = 0
        while k < len(body) and not CHOICE_RE.match(body[k].strip()):
            k += 1
        head, rest = body[:k], body[k:]
        # node: fields, speaker, paragraphs, voices, continue arrow
        text_lines, voices, fields, cont = [], [], [], None
        for ln in head:
            s = ln.strip()
            if s.startswith("->"):
                cont = target(s[2:])
                cont = cont or "end"
                continue
            vm = _vm(s, V)
            if vm:
                if not _blank(vm[1]):
                    voices.append(f"{V.skill_label(vm[0])}: {vm[1].strip()}")
                continue
            fm = FIELD_RE.match(s)
            if fm and fm.group(1) in ("art", "_note") or (fm and fm.group(1).startswith("_")):
                fields.append(f"{fm.group(1)}: {fm.group(2).strip()}")
                continue
            text_lines.append(ln)
        paras = _paras(text_lines)
        if paras:
            sm = SPEAKER_RE.match(paras[0])
            who = sm and (sm.group(1) or sm.group(2)).strip()
            if who and who.upper() in V.char_by_name:
                paras[0] = f"{who.upper()}: {sm.group(3)}"
            elif who:
                cid = next((c for c, name in V.char_names.items()
                            if name.lower() == who.lower()
                            or name.lower().endswith(" " + who.lower())), None)
                if cid:
                    paras[0] = f"{cid.upper()}: {sm.group(3)}"
                elif sm.group(1):
                    raise ValueError(f"beat {nid}: no character called {who!r}")
        S += fields + paras + voices
        if cont:
            S.append(f"-> {cont}")
        # choices
        k = 0
        while k < len(rest):
            m = CHOICE_RE.match(rest[k].strip())
            j = k + 1
            while j < len(rest) and not CHOICE_RE.match(rest[j].strip()):
                j += 1
            S += [""] + _choice(m.group(1).strip(), rest[k + 1:j], V, target)
            k = j
    return "\n".join(S) + "\n"


def _choice(label, body, V, target):
    tag = re.match(r"^\[([A-Za-z][A-Za-z \-]*?)\s+(\d+)(\+|\s+(?:red|white))?\]\s*(.*)$", label)
    checked = False
    if tag:
        sid = V.skill(tag.group(1))
        if not sid:
            raise ValueError(f"unknown skill {tag.group(1)!r} in choice {label!r}")
        name = V.skill_label(sid)
        if tag.group(3) == "+":
            label = f"[{name} {tag.group(2)}+] {tag.group(4)}"
        else:
            checked = True
            typ = (tag.group(3) or " white").strip()
            label = f"[{name} {tag.group(2)} {typ}] {tag.group(4)}"
    out = [f"* {label}"]
    # split into the choice's own part and pass/fail parts
    parts, cur = {"own": []}, "own"
    for ln in body:
        s = ln.strip()
        low = s.lower().rstrip(":")
        if checked and low in ("pass", "fail"):
            cur = low
            parts[cur] = []
            continue
        parts[cur].append(ln)

    def block(lines, ind):
        res, text, voices, fx, then, extra = [], [], [], None, None, []
        for ln in lines:
            s = ln.strip()
            vm = _vm(s, V)
            if vm:
                if not _blank(vm[1]):
                    voices.append(f"{V.skill_label(vm[0])}: {vm[1].strip()}")
                continue
            fm = FIELD_RE.match(s)
            if fm:
                key, val = fm.group(1).lower(), fm.group(2).strip()
                if key in ("effect", "effects"):
                    fx = "{}" if _blank(val) or val.lower() == "none" else "{" + val.strip("{} ") + "}"
                elif key in ("then", "next", "goto"):
                    then = target(val)
                elif not _blank(val):
                    extra.append(f"{fm.group(1)}: {val}")
                continue
            text.append(ln)
        res += [ind + e for e in extra]
        if fx:
            res.append(ind + fx)
        res += [ind + p for p in _paras(text)]
        res += [ind + v for v in voices]
        if then:
            res.append(f"{ind}-> {then}")
        return res

    out += block(parts["own"], "  ")
    for k in ("pass", "fail"):
        if k in parts:
            out.append(f"  {k}:")
            out += block(parts[k], "    ")
    return out


# ------------------------------------------------------------- scene -> md
def dlg_to_md(did, dlg, V, chars, export_choice, fmt_effects, fmt_mods):
    from scenes_viz import handles      # same letters as the tablet pages
    H, _ = handles(dlg)
    order = sorted(H, key=lambda n: (len(H[n]), H[n]))
    head = []
    for k, v in dlg.items():
        if isinstance(v, dict) and "choices" in v:
            continue
        if k == "unlocks":
            u = v
            if "_note" in u:
                head.append(f"unlocks._note: {u['_note']}")
            head.append("talks: " + ", ".join(
                c if d == f"talk-{c}" else f"{c}={d}" for c, d in u.get("talks", {}).items()))
            head.append("actions: " + ", ".join(u.get("actions", [])))
        else:
            head.append(f"{k}: {v if isinstance(v, str) else __import__('json').dumps(v, ensure_ascii=False)}")
    L = [f"# {did}", ""]
    if head:
        L = ["---"] + head + ["---", ""] + L
    go = lambda t: H.get(t, t) if t else "end"
    for nid in order:
        n = dlg[nid]
        L += [f"## {H[nid]} · {nid}"]
        for k in n:
            if k not in ("speaker", "text", "voices", "choices", "goto"):
                L.append(f"- {k}: {n[k]}")
        paras = n["text"].split("\n\n")
        if n.get("speaker"):
            name = chars.get(n["speaker"], {}).get("name", n["speaker"])
            paras[0] = f"**{name}:** {paras[0]}"
        for p in paras:
            L += [p, ""]
        for v in n.get("voices", []):
            L.append(f"- **{V.skills[v['t']]['name']}:** {v['text']}")
        if n.get("voices"):
            L.append("")
        if not n["choices"]:
            L += [f"-> {go(n.get('goto'))}", ""]
        for i, c in enumerate(n["choices"]):
            lab = c["label"]
            if c.get("force"):
                lab = f"[{V.skills[c['force']['skill']]['name']} {c['force']['min']}+] {lab}"
            if c.get("check"):
                ck = c["check"]
                lab = f"[{V.skills[ck['skill']]['name']} {ck['dc']} {ck.get('type', 'white')}] {lab}"
            L += [f"### {i + 1}. {lab}"]
            if c.get("check") and c["check"].get("mods"):
                L.append(f"- mods: {fmt_mods(c['check']['mods'], V)}")
            for k in c:
                if k.startswith("_"):
                    L.append(f"- {k}: {c[k]}")

            def outcome(o):
                res = []
                for p in (o.get("reply") or "").split("\n\n"):
                    if p:
                        res += [p, ""]
                for v in o.get("voices", []):
                    res.append(f"- **{V.skills[v['t']]['name']}:** {v['text']}")
                if "effects" in o:
                    res.append(f"- effect: {fmt_effects(o['effects'], V)[1:-1]}")
                return res
            if c.get("check"):
                if "effects" in c:
                    L.append(f"- effect: {fmt_effects(c['effects'], V)[1:-1]}")
                if c.get("goto"):
                    L.append(f"- then: {go(c['goto'])}")
                for key, word in (("success", "Pass:"), ("failure", "Fail:")):
                    o = c.get(key) or {}
                    L += [word] + outcome(o)
                    if o.get("goto"):
                        L.append(f"- then: {go(o['goto'])}")
            else:
                L += outcome(c)
                L.append(f"- then: {go(c.get('goto'))}")
            L.append("")
    return "\n".join(L).rstrip() + "\n"
