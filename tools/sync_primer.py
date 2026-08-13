#!/usr/bin/env python3
"""Mirror budget data from the BudgetPrimerFinal repo into capitol-quest.

capitol-quest is explicitly downstream of ~/BudgetPrimerFinal: the
FY2027 enacted-budget extracts (departments + summary stats for Act 175)
are snapshotted into data/raw/ and drive site/map/budget.json via
tools/build_budget.py. This script is THE update path:

  python3 tools/sync_primer.py              # snapshot if changed + rebuild
  python3 tools/sync_primer.py --commit     # …and commit the result here
  python3 tools/sync_primer.py --install-hook

--install-hook writes a post-commit hook into BudgetPrimerFinal's
.git/hooks/ so any commit there that touches the extracts re-runs this
script with --commit automatically (the global ~/.config/git-hooks
dispatcher chains to repo-local hooks — same pattern primer-editor uses
to vendor its engine into BudgetPrimerFinal). Sync activity is logged to
~/.config/capitol-quest-sync.log.

The auto-commit stages ONLY the synced snapshots + rebuilt budget.json,
so a dirty capitol-quest working tree is never swept into it.
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIMER = Path.home() / "BudgetPrimerFinal"
SRC = PRIMER / "docs" / "js"
RAW = ROOT / "data" / "raw"
FILES = ["departments_act175_fy2027.json", "summary_stats_act175_fy2027.json"]

HOOK_MARKER = "capitol-quest sync_primer hook v1"
HOOK = f"""#!/bin/bash
# {HOOK_MARKER} — installed by ~/capitol-quest/tools/sync_primer.py.
# When a commit touches the enacted-budget extracts, mirror them into
# ~/capitol-quest (which rebuilds budget.json and makes its own local
# commit). The global ~/.config/git-hooks dispatcher chains to this file.
changed=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null)
case "$changed" in
  *departments_act175_fy2027.json*|*summary_stats_act175_fy2027.json*)
    python3 "$HOME/capitol-quest/tools/sync_primer.py" --commit \\
      >>"$HOME/.config/capitol-quest-sync.log" 2>&1 || true ;;
esac
exit 0
"""


def install_hook():
    path = PRIMER / ".git" / "hooks" / "post-commit"
    if path.exists() and HOOK_MARKER not in path.read_text():
        raise SystemExit(f"REFUSING: {path} exists and is not ours — "
                         "merge by hand")
    path.write_text(HOOK)
    path.chmod(0o755)
    print(f"installed {path}")


def main():
    if "--install-hook" in sys.argv:
        install_hook()
        return

    changed = []
    for f in FILES:
        src, dst = SRC / f, RAW / f
        if not src.exists():
            raise SystemExit(f"missing source {src} — BudgetPrimerFinal "
                             "moved or the extract was renamed?")
        if not dst.exists() or not filecmp.cmp(src, dst, shallow=False):
            shutil.copy(src, dst)
            changed.append(f)
    if not changed:
        print("primer snapshots already current")
        return

    print("changed:", ", ".join(changed))
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_budget.py")], check=True)

    if "--commit" in sys.argv:
        paths = [str(RAW / f) for f in FILES] + \
            [str(ROOT / "site" / "map" / "budget.json")]
        subprocess.run(["git", "-C", str(ROOT), "add", *paths], check=True)
        if subprocess.run(["git", "-C", str(ROOT), "diff", "--cached",
                           "--quiet"]).returncode:
            subprocess.run(
                ["git", "-C", str(ROOT), "commit", "-m",
                 "Auto-sync budget data from BudgetPrimerFinal\n\n"
                 "(tools/sync_primer.py via the BudgetPrimerFinal "
                 "post-commit hook)"], check=True)
            print("committed in capitol-quest")


if __name__ == "__main__":
    main()
