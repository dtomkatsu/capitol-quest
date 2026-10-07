#!/usr/bin/env python3
"""Scene scripts <-> session.json dialogues.

Dialogue content is written as plain-text `.scene` files in
`content/scenes/` (one dialogue per file) and compiled into the
`dialogues` block of `site/map/session.json`. Every other key of
session.json is left alone. Format reference: content/scenes/README.md.

    python3 tools/scenes.py build            # scenes -> session.json (lints first)
    python3 tools/scenes.py check            # lint only
    python3 tools/scenes.py stats            # skill-voice balance, flag ledger
    python3 tools/scenes.py tree <id> [-o f] # decision tree to mark up with a pen
    python3 tools/scenes.py map [-o f]       # whole session: weeks, scenes, flag lines
    python3 tools/scenes.py new <id>         # scaffold a scene with every skill's slot
    python3 tools/scenes.py export           # session.json -> scenes (one-time / recovery)
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION = ROOT / "site/map/session.json"
SCENES = ROOT / "content/scenes"
ART = ROOT / "site/assets/events"

# Short aliases on top of each skill's id and display name. Display
# names are what the exporter writes, because they are what the player
# sees beside the line.
SKILL_ALIASES = {"BRAIN": "fiscal", "TALK": "talkstory", "BASE": "basebuilding",
                 "MOB": "mobilizing", "EDU": "educator", "PROC": "procedure"}
# Named, but must never speak (CLAUDE.md: the Souza asymmetry is the content).
SILENT = {"souza"}
DIALOGUE_FIELDS = ("_note", "art", "at")   # header order the builder emits
NAME_RE = re.compile(r"^([A-Z][A-Z0-9 \-]*[A-Z0-9]):\s+(.*)$")
FIELD_RE = re.compile(r"^(_[A-Za-z]+|art|at|talks|actions|mods|unlocks\._note):\s*(.*)$")
CHECK_RE = re.compile(r"^\[([A-Za-z][A-Za-z \-]*?)\s+(\d+)(?:\s+(red|white))?\]\s*(.*)$")


class SceneError(Exception):
    pass


# ------------------------------------------------------------- vocabulary
class Vocab:
    def __init__(self, data):
        self.skills = data["skills"]
        self.chars = {k for k in data["characters"] if not k.startswith("_")}
        # "push" is built in: it opens the work-the-chair rows (CLAUDE.md)
        self.actions = set(data.get("actions", {})) | {"push"}
        self.skill_by_name = {}
        for sid, s in self.skills.items():
            self.skill_by_name[sid.upper()] = sid
            self.skill_by_name[s["name"].upper()] = sid
        for a, sid in SKILL_ALIASES.items():
            if sid in self.skills:
                self.skill_by_name[a] = sid
        self.char_by_name = {c.upper(): c for c in self.chars}

    def skill(self, name):
        return self.skill_by_name.get(name.strip().upper())

    def skill_label(self, sid):
        return self.skills[sid]["name"].upper()


# ------------------------------------------------------------- small codecs
def fmt_n(n):
    return ("+" if n > 0 else "") + str(n)


def fmt_money(k):
    sign = "+" if k > 0 else "-"
    a = abs(k)
    if a % 1_000_000 == 0:
        return f"{sign}${a // 1_000_000}B"
    if a % 1000 == 0:
        return f"{sign}${a // 1000}M"
    return f"{sign}${a}K"


def parse_money(s):
    m = re.fullmatch(r"([+-])\$(\d+(?:\.\d+)?)([KMB])", s)
    if not m:
        raise SceneError(f"bad revenue amount {s!r} (want e.g. -$25M)")
    v = float(m.group(2)) * {"K": 1, "M": 1000, "B": 1_000_000}[m.group(3)]
    return int(round(v)) * (1 if m.group(1) == "+" else -1)


def split_items(s):
    """Comma-split that leaves quoted labels alone."""
    return [x.strip() for x in re.findall(r'(?:[^,"]|"[^"]*")+', s) if x.strip()]


def scalar(v, key=""):
    v = v.strip()
    if key.startswith("_") or key == "art":
        return v
    if v[:1] in "{[" or v in ("true", "false", "null") or re.fullmatch(r"-?\d+(\.\d+)?", v):
        return json.loads(v)
    return v


def fmt_scalar(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def fmt_effects(fx, V):
    out = []
    for k, v in fx.items():
        if k in ("support", "influence"):
            out.append(f"{fmt_n(v)} {k}")
        elif k == "revenueK":
            out.append(f"{fmt_money(v)} revenue")
        elif k == "flag":
            out.append(f"flag {v}")
        elif k == "rapport":
            out += [f"{fmt_n(n)} {who}" for who, n in v.items()]
        elif k == "skill":
            out.append(f"+1 {V.skill_label(v)}")
        elif k == "unlock":
            out += [f"unlock talk {c}={d}" for c, d in v.get("talks", {}).items()]
            out += [f"unlock action {a}" for a in v.get("actions", [])]
        else:
            raise SceneError(f"exporter: unknown effect {k!r}")
    return "{" + ", ".join(out) + "}"


def parse_effects(s, V, where):
    inner = s.strip()[1:-1].strip()
    fx = {}
    for item in split_items(inner):
        m = re.fullmatch(r"([+-]\d+)\s+(.+)", item)
        if m:
            n, what = int(m.group(1)), m.group(2).strip()
            if what in ("support", "influence"):
                fx[what] = n
            elif what in ("house", "senate"):
                fx.setdefault("rapport", {})[what] = n
            elif V.skill(what):
                if n != 1:
                    raise SceneError(f"{where}: a skill effect is always +1 ({item!r})")
                fx["skill"] = V.skill(what)
            else:
                raise SceneError(f"{where}: unknown effect {item!r}")
            continue
        m = re.fullmatch(r"([+-]\$\S+)\s+revenue", item)
        if m:
            fx["revenueK"] = parse_money(m.group(1))
            continue
        m = re.fullmatch(r"flag\s+(\S+)", item)
        if m:
            fx["flag"] = m.group(1)
            continue
        m = re.fullmatch(r"unlock\s+talk\s+(\S+?)=(\S+)", item)
        if m:
            fx.setdefault("unlock", {}).setdefault("talks", {})[m.group(1)] = m.group(2)
            continue
        m = re.fullmatch(r"unlock\s+action\s+(\S+)", item)
        if m:
            fx.setdefault("unlock", {}).setdefault("actions", []).append(m.group(1))
            continue
        raise SceneError(f"{where}: can't read effect {item!r}")
    return fx


def fmt_mods(mods, V):
    out = []
    for m in mods:
        f = m["from"]
        if f in ("support", "influence"):
            out.append(f"{f}/{m['per']}")
        elif f == "skill":
            out.append(f"{V.skill_label(m['id'])}/{m['per']}")
        elif f == "flag":
            s = f"flag {m['id']}"
            if "add" in m:
                s += f" {fmt_n(m['add'])}"
            if "label" in m:
                s += f' "{m["label"]}"'
            out.append(s)
        elif f == "chair":
            s = f"chair {m['id']}/{m['per']}"
            if "label" in m:
                s += f' "{m["label"]}"'
            out.append(s)
        else:
            raise SceneError(f"exporter: unknown mod source {f!r}")
    return ", ".join(out)


def parse_mods(s, V, where):
    mods = []
    for item in split_items(s):
        m = re.fullmatch(r'flag\s+(\S+)(?:\s+([+-]\d+))?(?:\s+"([^"]*)")?', item)
        if m:
            mod = {"from": "flag", "id": m.group(1)}
            if m.group(2):
                mod["add"] = int(m.group(2))
            if m.group(3) is not None:
                mod["label"] = m.group(3)
            mods.append(mod)
            continue
        m = re.fullmatch(r'chair\s+(\S+)/(\d+)(?:\s+"([^"]*)")?', item)
        if m:
            mod = {"from": "chair", "id": m.group(1), "per": int(m.group(2))}
            if m.group(3) is not None:
                mod["label"] = m.group(3)
            mods.append(mod)
            continue
        m = re.fullmatch(r"(.+?)/(\d+)", item)
        if m:
            src, per = m.group(1).strip(), int(m.group(2))
            if src.lower() in ("support", "influence"):
                mods.append({"from": src.lower(), "per": per})
            elif V.skill(src):
                mods.append({"from": "skill", "id": V.skill(src), "per": per})
            else:
                raise SceneError(f"{where}: unknown modifier source {src!r}")
            continue
        raise SceneError(f"{where}: can't read modifier {item!r}")
    return mods


# ------------------------------------------------------------- export
def export_dialogue(did, dlg, V):
    L = [f"=== {did}"]
    nodes = [(k, v) for k, v in dlg.items() if isinstance(v, dict) and "choices" in v]
    for k, v in dlg.items():
        if k == "unlocks" or (isinstance(v, dict) and "choices" in v):
            continue
        L.append(f"{k}: {fmt_scalar(v)}")
    if "unlocks" in dlg:
        u = dlg["unlocks"]
        extra = set(u) - {"talks", "actions", "_note"}
        if extra:
            raise SceneError(f"{did}: exporter can't express unlocks keys {extra}")
        if "_note" in u:
            L.append(f"unlocks._note: {u['_note']}")
        L.append("talks: " + ", ".join(
            c if d == f"talk-{c}" else f"{c}={d}" for c, d in u.get("talks", {}).items()))
        L.append("actions: " + ", ".join(u.get("actions", [])))
    for nid, n in nodes:
        L += ["", f"--- {nid}"]
        for k in n:
            if k not in ("speaker", "text", "voices", "choices"):
                L.append(f"{k}: {fmt_scalar(n[k])}")
        paras = n["text"].split("\n\n")
        if n.get("speaker"):
            paras[0] = f"{n['speaker'].upper()}: {paras[0]}"
        L += paras
        L += [f"{V.skill_label(v['t'])}: {v['text']}" for v in n.get("voices", [])]
        for c in n["choices"]:
            L.append("")
            L += export_choice(c, V)
    return "\n".join(L) + "\n"


def export_body(o, V, ind):
    """reply / effects / voices / goto, shared by plain choices and outcomes."""
    L = []
    if "effects" in o:
        L.append(ind + fmt_effects(o["effects"], V))
    if "reply" in o:
        L += [ind + p for p in o["reply"].split("\n\n")]
    L += [f"{ind}{V.skill_label(v['t'])}: {v['text']}" for v in o.get("voices", [])]
    if "goto" in o:
        L.append(f"{ind}-> {o['goto']}")
    return L


def export_choice(c, V):
    known = {"label", "check", "effects", "reply", "voices", "goto", "success", "failure"}
    if "check" in c:
        ck = c["check"]
        L = [f"* [{V.skill_label(ck['skill'])} {ck['dc']} {ck.get('type', 'white')}] {c['label']}"]
        if ck.get("mods"):
            L.append("  mods: " + fmt_mods(ck["mods"], V))
        for k in c:
            if k not in known:
                L.append(f"  {k}: {fmt_scalar(c[k])}")
        if "effects" in c:
            L.append("  " + fmt_effects(c["effects"], V))
        for key, word in (("success", "pass"), ("failure", "fail")):
            if key in c:
                L.append(f"  {word}:")
                L += export_body(c[key], V, "    ")
        if "goto" in c:
            L.append(f"  -> {c['goto']}")
        return L
    L = [f"* {c['label']}"]
    for k in c:
        if k not in known:
            L.append(f"  {k}: {fmt_scalar(c[k])}")
    return L + export_body(c, V, "  ")


# ------------------------------------------------------------- parse
class Line:
    def __init__(self, no, raw):
        self.no = no
        self.indent = len(raw) - len(raw.lstrip(" "))
        self.s = raw.strip()


def parse_scene(text, V, fname="<scene>"):
    lines = [Line(i + 1, r) for i, r in enumerate(text.splitlines())]
    lines = [ln for ln in lines if ln.s and not ln.s.startswith("//")]
    if not lines or not lines[0].s.startswith("=== "):
        raise SceneError(f"{fname}: first line must be '=== <dialogue-id>'")
    did = lines[0].s[4:].strip()
    dlg, unlocks = {}, None
    i = 1
    at = lambda ln: f"{fname}:{ln.no}"

    # dialogue header
    while i < len(lines) and not lines[i].s.startswith("--- "):
        ln = lines[i]
        m = FIELD_RE.match(ln.s)
        if not m:
            raise SceneError(f"{at(ln)}: expected a header field or '--- <node>' — got {ln.s[:40]!r}")
        k, v = m.groups()
        if k in ("talks", "actions", "unlocks._note"):
            unlocks = unlocks or {}
            if k == "unlocks._note":
                unlocks["_note"] = v
            elif k == "talks":
                unlocks["talks"] = {}
                for item in split_items(v):
                    c, _, d = item.partition("=")
                    unlocks["talks"][c.strip()] = d.strip() or f"talk-{c.strip()}"
            else:
                unlocks["actions"] = split_items(v)
        else:
            dlg[k] = scalar(v, k)
        i += 1
    if unlocks is not None:
        dlg["unlocks"] = {k: unlocks[k] for k in ("_note", "talks", "actions") if k in unlocks}

    # nodes
    while i < len(lines):
        head = lines[i]
        nid = head.s[4:].strip()
        if nid in dlg:
            raise SceneError(f"{at(head)}: duplicate node {nid!r}")
        i += 1
        j = i
        while j < len(lines) and not lines[j].s.startswith("--- "):
            j += 1
        dlg[nid] = parse_node(lines[i:j], V, fname, nid)
        i = j
    return did, order_dialogue(dlg)


def order_dialogue(dlg):
    head = [k for k in DIALOGUE_FIELDS if k in dlg]
    head += [k for k in dlg if k.startswith("_") and k not in head]
    tail = ["unlocks"] if "unlocks" in dlg else []
    rest = [k for k in dlg if k not in head and k not in tail]
    # nodes first ("start" leads), then anything non-node a writer added
    nodes = [k for k in rest if isinstance(dlg[k], dict) and "choices" in dlg[k]]
    nodes.sort(key=lambda k: k != "start")
    other = [k for k in rest if k not in nodes]
    return {k: dlg[k] for k in head + other + nodes + tail}


def parse_node(lines, V, fname, nid):
    at = lambda ln: f"{fname}:{ln.no}"
    node, paras, voices, choices = {}, [], [], []
    i = 0
    while i < len(lines) and not lines[i].s.startswith("* "):
        ln = lines[i]
        if ln.indent:
            raise SceneError(f"{at(ln)}: indented line outside a choice")
        m = NAME_RE.match(ln.s)
        f = FIELD_RE.match(ln.s)
        if f and not paras and f.group(1) not in ("talks", "actions", "mods"):
            node[f.group(1)] = scalar(f.group(2), f.group(1))
        elif m and V.skill(m.group(1)):
            voices.append({"t": V.skill(m.group(1)), "text": m.group(2)})
        elif m and m.group(1) in V.char_by_name:
            if paras:
                raise SceneError(f"{at(ln)}: the speaker tag goes on the node's FIRST line "
                                 "(one speaker per node — start a new '--- node' for a new speaker)")
            node["speaker"] = V.char_by_name[m.group(1)]
            paras.append(m.group(2))
        elif m:
            raise SceneError(f"{at(ln)}: {m.group(1)!r} is not a skill or a character")
        else:
            if voices:
                raise SceneError(f"{at(ln)}: narration after a skill voice — voices come after the text")
            paras.append(ln.s)
        i += 1
    if not paras:
        raise SceneError(f"{fname}: node {nid!r} has no text")
    out = {k: node[k] for k in node if k != "speaker"}
    if "speaker" in node:
        out["speaker"] = node["speaker"]
    out["text"] = "\n\n".join(paras)
    out["voices"] = voices
    while i < len(lines):
        head = lines[i]
        if not head.s.startswith("* ") or head.indent:
            raise SceneError(f"{at(head)}: expected a choice ('* ...') — choice bodies are indented")
        j = i + 1
        while j < len(lines) and lines[j].indent > head.indent:
            j += 1
        choices.append(parse_choice(head, lines[i + 1:j], V, fname))
        i = j
    if not choices:
        raise SceneError(f"{fname}: node {nid!r} has no choices (the engine needs at least one)")
    out["choices"] = choices
    return out


def parse_body(lines, V, fname, allow_outcomes=False):
    at = lambda ln: f"{fname}:{ln.no}"
    body, paras, voices, extra, outcomes = {}, [], [], {}, {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.s
        if allow_outcomes and s in ("pass:", "fail:"):
            j = i + 1
            while j < len(lines) and lines[j].indent > ln.indent:
                j += 1
            key = "success" if s == "pass:" else "failure"
            outcomes[key] = parse_body(lines[i + 1:j], V, fname)[0]
            i = j
            continue
        m = NAME_RE.match(s)
        f = FIELD_RE.match(s)
        if s.startswith("{") and s.endswith("}"):
            body["effects"] = parse_effects(s, V, at(ln))
        elif s.startswith("->"):
            tgt = s[2:].strip()
            if tgt != "end":
                body["goto"] = tgt
        elif f and (allow_outcomes or f.group(1).startswith("_")):
            extra[f.group(1)] = f.group(2)
        elif m and V.skill(m.group(1)):
            voices.append({"t": V.skill(m.group(1)), "text": m.group(2)})
        elif m and m.group(1) in V.char_by_name:
            raise SceneError(f"{at(ln)}: a reply can't have a speaker — open a new node with "
                             f"'--- <id>' and '-> <id>' to it")
        else:
            paras.append(s)
        i += 1
    if paras:
        body["reply"] = "\n\n".join(paras)
    if voices:
        body["voices"] = voices
    # canonical key order, whatever order the lines were written in
    body = {k: body[k] for k in ("reply", "effects", "voices", "goto") if k in body}
    return body, extra, outcomes


def parse_choice(head, lines, V, fname):
    label = head.s[2:].strip()
    m = CHECK_RE.match(label)
    if not m:
        body, extra, _ = parse_body(lines, V, fname)
        c = {"label": label}
        c.update(extra)
        for k in ("effects", "reply", "voices", "goto"):
            if k in body:
                c[k] = body[k]
        return c
    sname, dc, typ, label = m.groups()
    sid = V.skill(sname)
    if not sid:
        raise SceneError(f"{fname}:{head.no}: unknown skill {sname!r} in check")
    body, extra, outcomes = parse_body(lines, V, fname, allow_outcomes=True)
    check = {"skill": sid, "dc": int(dc), "type": typ or "white",
             "mods": parse_mods(extra.pop("mods", ""), V, f"{fname}:{head.no}")}
    c = {"label": label, "check": check}
    c.update({k: v for k, v in extra.items()})
    if "effects" in body:
        c["effects"] = body["effects"]
    if "reply" in body or "voices" in body:
        raise SceneError(f"{fname}:{head.no}: a checked choice's text goes under pass:/fail:")
    for k in ("success", "failure"):
        if k not in outcomes:
            raise SceneError(f"{fname}:{head.no}: checked choice is missing "
                             f"{'pass:' if k == 'success' else 'fail:'}")
        c[k] = outcomes[k]
    if "goto" in body:
        c["goto"] = body["goto"]
    return c


# ------------------------------------------------------------- lint
def walk_choices(dlg):
    for nid, n in dlg.items():
        if isinstance(n, dict) and "choices" in n:
            for i, c in enumerate(n["choices"]):
                yield nid, i, c


def all_effects(c):
    yield c.get("effects") or {}
    for k in ("success", "failure"):
        yield (c.get(k) or {}).get("effects") or {}


def lint(data, dialogues, V):
    errs, warns = [], []
    refs = defaultdict(list)
    for cal in data.get("calendar", []):
        for k in ("event", "pre"):
            if cal.get(k):
                refs[cal[k]].append(f"week {cal['week']} {k}")
    for g in data.get("genericEvents", []):
        refs[g].append("generic event")
    flags_set, flags_read = defaultdict(list), defaultdict(list)

    def check_unlock(did, u, where):
        for cid, tgt in (u.get("talks") or {}).items():
            refs[tgt].append(f"talk slot in {did}")
            if cid not in V.chars:
                errs.append(f"{where}: unlock talk for unknown character {cid!r}")
            if tgt not in dialogues:
                errs.append(f"{where}: unlock talk {cid} -> missing dialogue {tgt!r}")
        for a in u.get("actions") or []:
            if a not in V.actions:
                errs.append(f"{where}: unknown action {a!r}")

    for did, dlg in dialogues.items():
        nodes = {k for k, v in dlg.items() if isinstance(v, dict) and "choices" in v}
        if "start" not in nodes:
            errs.append(f"{did}: no 'start' node")
        if dlg.get("unlocks"):
            check_unlock(did, dlg["unlocks"], did)
        for art in [dlg.get("art")] + [dlg[n].get("art") for n in nodes]:
            if art and not (ART / f"{art}.png").exists():
                errs.append(f"{did}: art {art!r} has no site/assets/events/{art}.png")
        for nid in nodes:
            n = dlg[nid]
            sp = n.get("speaker")
            if sp and sp not in V.chars:
                errs.append(f"{did}/{nid}: unknown speaker {sp!r}")
            if sp in SILENT:
                errs.append(f"{did}/{nid}: {sp} never speaks (CLAUDE.md)")
            if not n.get("voices"):
                warns.append(f"{did}/{nid}: no skill voices (every node should carry some)")
            for v in n.get("voices", []):
                if v["t"] not in V.skills:
                    errs.append(f"{did}/{nid}: unknown skill {v['t']!r}")
        # reachability
        seen, todo = set(), ["start"]
        for nid, i, c in walk_choices(dlg):
            where = f"{did}/{nid} choice {i + 1}"
            gotos = [c.get("goto")] + [(c.get(k) or {}).get("goto") for k in ("success", "failure")]
            for g in gotos:
                if g and g not in nodes:
                    errs.append(f"{where}: -> {g!r} is not a node in this scene")
            if c.get("check"):
                ck = c["check"]
                if ck["skill"] not in V.skills:
                    errs.append(f"{where}: check on unknown skill {ck['skill']!r}")
                if ck.get("type") not in ("red", "white"):
                    errs.append(f"{where}: check type must be red or white")
                for m in ck.get("mods", []):
                    if m["from"] == "flag":
                        flags_read[m["id"]].append(where)
            for fx in all_effects(c):
                if fx.get("flag"):
                    flags_set[fx["flag"]].append(where)
                if fx.get("unlock"):
                    check_unlock(did, fx["unlock"], where)
                if fx.get("skill") and fx["skill"] not in V.skills:
                    errs.append(f"{where}: unknown skill {fx['skill']!r}")
        edges = defaultdict(set)
        for nid, i, c in walk_choices(dlg):
            for g in [c.get("goto")] + [(c.get(k) or {}).get("goto") for k in ("success", "failure")]:
                if g:
                    edges[nid].add(g)
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            todo += list(edges[x])
        for nid in nodes - seen:
            warns.append(f"{did}/{nid}: unreachable — nothing points here")
    for g in data.get("genericEvents", []):
        u = (dialogues.get(g) or {}).get("unlocks") or {}
        if not u.get("talks") and not u.get("actions"):
            warns.append(f"{g}: generic event grants nothing — its week is dead air (CLAUDE.md)")
    for did in dialogues:
        if did not in refs:
            warns.append(f"{did}: never scheduled — not on the calendar, a generic event or a talk slot")
    for f, where in flags_read.items():
        if f not in flags_set:
            warns.append(f"flag {f!r} is read ({where[0]}) but nothing sets it")
    return errs, warns, refs, flags_set, flags_read


# ------------------------------------------------------------- io
def load():
    raw = SESSION.read_text()
    return raw, json.loads(raw)


def dump(data):
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def read_scenes(V):
    out, files = {}, sorted(SCENES.glob("*.scene"))
    if not files:
        raise SceneError(f"no .scene files in {SCENES.relative_to(ROOT)} — run export first")
    for f in files:
        did, dlg = parse_scene(f.read_text(), V, str(f.relative_to(ROOT)))
        if did != f.stem:
            raise SceneError(f"{f.name}: '=== {did}' must match the file name")
        out[did] = dlg
    return out


def merged(data, scenes):
    """Existing dialogue order first, new scenes appended — keeps diffs small."""
    order = [k for k in data["dialogues"] if k in scenes] + \
            [k for k in scenes if k not in data["dialogues"]]
    new = dict(data)
    new["dialogues"] = {k: scenes[k] for k in order}
    return new


def report(errs, warns):
    for w in warns:
        print("  warn  " + w)
    for e in errs:
        print("  ERROR " + e)
    print(f"{len(errs)} error(s), {len(warns)} warning(s)")


NEW_TEMPLATE = """=== {id}
// Scene stub. Lines starting with // are notes to yourself and never ship.
// Schedule it: calendar event/pre or genericEvents in session.json, or a talk slot.
talks:
actions:

--- start
Narration goes here — one paragraph per line.
// Uncomment the instincts that would have something to say (2+ is the norm):
{slots}

* A plain choice.
  {{+1 support}}
  What happens.
  -> next

* [TALK STORY 10 white] A checked choice.
  mods: influence/25
  pass:
    It works.
    {{+2 influence}}
  fail:
    It doesn't.
    {{-1 influence}}

--- next
KAWAGUCHI: A speaker's line opens the node.
PROCEDURE: A voice on it.

* Leave.
  {{}}
"""


# ------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("check")
    sub.add_parser("stats")
    e = sub.add_parser("export")
    e.add_argument("--force", action="store_true", help="overwrite existing .scene files")
    nw = sub.add_parser("new")
    nw.add_argument("id")
    mp = sub.add_parser("map")
    mp.add_argument("-o", "--out")
    t = sub.add_parser("tree")
    t.add_argument("id")
    t.add_argument("-o", "--out")
    a = ap.parse_args()

    raw, data = load()
    V = Vocab(data)
    try:
        if a.cmd == "export":
            SCENES.mkdir(parents=True, exist_ok=True)
            for did, dlg in data["dialogues"].items():
                f = SCENES / f"{did}.scene"
                if f.exists() and not a.force:
                    sys.exit(f"{f.name} exists — refusing to overwrite (use --force)")
                text = export_dialogue(did, dlg, V)
                back = parse_scene(text, V, f.name)[1]
                if back != dlg:
                    sys.exit(f"{did}: round trip is not lossless — fix the exporter first")
                f.write_text(text)
            print(f"exported {len(data['dialogues'])} scenes to {SCENES.relative_to(ROOT)}")
            return
        if a.cmd == "new":
            f = SCENES / f"{a.id}.scene"
            if f.exists():
                sys.exit(f"{f.name} exists")
            slots = "\n".join(f"// {V.skill_label(k)}: ({s['desc']})" for k, s in V.skills.items())
            f.write_text(NEW_TEMPLATE.format(id=a.id, slots=slots))
            print(f.relative_to(ROOT))
            return
        scenes = read_scenes(V)
        errs, warns, refs, fset, fread = lint(data, scenes, V)
        if a.cmd in ("tree", "map"):
            import scenes_viz as viz
            skills = list(V.skills)
            if a.cmd == "tree":
                if a.id not in scenes:
                    sys.exit(f"no scene {a.id!r}")
                f = viz.scene_facts(scenes[a.id])
                svg = viz.tree_svg(a.id, scenes[a.id], skills, data["characters"],
                                   sched=sorted(set(refs.get(a.id, []))),
                                   flags_here={"set": sorted(f["sets"]), "read": sorted(f["reads"])})
                out = Path(a.out) if a.out else ROOT / "build" / f"tree-{a.id}.svg"
            else:
                svg = viz.map_svg(data, scenes, skills)
                out = Path(a.out) if a.out else ROOT / "build" / "session-map.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(svg)
            print(out)
            return
        if a.cmd == "stats":
            print("skill voice lines (nodes + outcomes):")
            per = Counter()
            per_scene = defaultdict(Counter)

            def tally(did, vs):
                for v in vs or []:
                    per[v["t"]] += 1
                    per_scene[did][v["t"]] += 1
            for did, dlg in scenes.items():
                for k, n in dlg.items():
                    if isinstance(n, dict) and "choices" in n:
                        tally(did, n.get("voices"))
                for _, _, c in walk_choices(dlg):
                    tally(did, c.get("voices"))
                    for o in ("success", "failure"):
                        tally(did, (c.get(o) or {}).get("voices"))
            for sid in V.skills:
                print(f"  {V.skills[sid]['name']:<14} {per[sid]:>4}  {'#' * per[sid]}")
            print("\nchecks by skill:")
            ck = Counter(c["check"]["skill"] for d in scenes.values() for _, _, c in walk_choices(d) if c.get("check"))
            for sid in V.skills:
                print(f"  {V.skills[sid]['name']:<14} {ck[sid]:>4}")
            print("\nflags (set -> read):")
            for f in sorted(set(fset) | set(fread)):
                print(f"  {f}\n      set:  {', '.join(fset.get(f, ['—']))}\n      read: {', '.join(fread.get(f, ['—']))}")
            print("\nskills absent per scene:")
            for did in scenes:
                miss = [V.skills[s]["name"] for s in V.skills if not per_scene[did][s]]
                print(f"  {did:<16} {', '.join(miss)}")
            return
        report(errs, warns)
        if a.cmd == "check":
            sys.exit(1 if errs else 0)
        if errs:
            sys.exit("not building — fix the errors above")
        new = dump(merged(data, scenes))
        if new == raw:
            print("session.json unchanged")
        else:
            SESSION.write_text(new)
            print(f"wrote {SESSION.relative_to(ROOT)} ({len(scenes)} dialogues)")
            # the pre-commit hook only bumps ?v= inside HTML; main.js loads this one
            js = ROOT / "site/js/main.js"
            src = js.read_text()
            m = re.search(r'map/session\.json\?v=(\d+)', src)
            if m:
                js.write_text(src.replace(m.group(0), f"map/session.json?v={int(m.group(1)) + 1}", 1))
                print(f"bumped map/session.json?v= to {int(m.group(1)) + 1} in main.js")
    except SceneError as err:
        sys.exit(f"error: {err}")


if __name__ == "__main__":
    main()
