#!/usr/bin/env python3
"""Check the UI colour tokens for drift. Exit non-zero on the first lie.

Two places hold a colour twice ON PURPOSE, because the platform forces it,
and both are exactly the kind of copy that drifts silently:

  1. site/css/style.css :root carries every translucent colour's rgb as a
     TRIPLET (`--gold-rgb: 242, 193, 78`) beside its hex (`--gold`),
     because a hex token cannot take an alpha — `rgba(var(--gold-rgb), .5)`
     is how the sheet says "the house gold at half strength". Re-point
     `--gold` and forget `--gold-rgb` and every translucent gold in the game
     stays the old colour while the solid ones move.
  2. site/js/main.js flowColors() carries a fallback hex for each
     `--flow-*` token, used only if the stylesheet has not loaded. A
     fallback that disagrees with the token is a map whose motes change
     colour depending on load order.

Run it after any edit to the :root block or to flowColors():

    python3 tools/check_tokens.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS = (ROOT / "site/css/style.css").read_text()
JS = (ROOT / "site/js/main.js").read_text()


def root_tokens():
    a = CSS.index(":root {")
    b = CSS.index("\n}", a)
    block = re.sub(r"/\*.*?\*/", "", CSS[a:b], flags=re.S)
    return {k: v.strip() for k, v in
            re.findall(r"--([a-z0-9-]+):\s*([^;]+);", block)}


def main():
    t = root_tokens()
    bad = []
    for name, val in t.items():
        if not name.endswith("-rgb"):
            continue
        base = name[:-4]
        hx = t.get(base, "")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", hx):
            bad.append(f"--{name} has no hex token --{base}")
            continue
        want = ", ".join(str(int(hx[i:i + 2], 16)) for i in (1, 3, 5))
        if re.sub(r"\s+", "", val) != want.replace(" ", ""):
            bad.append(f"--{name}: {val} but --{base} is {hx} ({want})")
    # every triplet used in the sheet must exist
    code = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for used in set(re.findall(r"var\(--([a-z0-9-]+-rgb)\)", code)):
        if used not in t:
            bad.append(f"var(--{used}) is used but never defined")
    # flowColors() fallbacks
    for name, hx in re.findall(r'cssVar\("--(flow-[a-z]+)", "(#[0-9a-f]{6})"\)', JS):
        if t.get(name, "").lower() != hx.lower():
            bad.append(f"main.js fallback for --{name} is {hx}, "
                       f"style.css says {t.get(name)}")
    if bad:
        print("\n".join(bad))
        sys.exit(1)
    n = sum(1 for k in t if k.endswith("-rgb"))
    print(f"ok — {n} rgb triplets and the flow-map fallbacks match their tokens")


main()
