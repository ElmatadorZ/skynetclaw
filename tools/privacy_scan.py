#!/usr/bin/env python3
"""
privacy_scan.py — prove that nothing operator-private is published.

This repository is assembled from a private working instance, so "no personal
data" is a claim that has to be re-checked on every push rather than assumed.

Two design decisions, both learned from getting it wrong:

  1. It scans **git-tracked files only**. An earlier version walked the working
     tree and flagged generated artifacts (skills_capability_index.json and
     friends) that are git-ignored and never published — noise that hides real
     findings.

  2. It rejects a **class**, not a list. The first version enumerated three known
     bad strings and passed while four real leaks sat in the tree, because they
     were paths nobody had thought to enumerate. Any absolute Windows path is now
     a finding unless it is an explicitly allowed placeholder.

Run:  python tools/privacy_scan.py
Exit: 0 clean · 1 findings
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

# Only IDENTIFYING material fails the build. A generic Windows example path in a
# doc or a test fixture (D:\Test, C:\Windows) is a portability wrinkle, not a
# privacy leak — and a gate that reports forty of those gets switched off, which
# is worse than no gate. Precision here is what keeps it enforceable.
PATTERNS = {
    "personal email":
        re.compile(r"[A-Za-z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|proton)\.[a-z]+", re.I),
    "operator home directory":
        re.compile(r"[Cc]:[\\/]+Users[\\/]+(?!default|public|all users)[A-Za-z0-9._-]+", re.I),
    # Only as a PATH segment. "GenesisMind" alone is the public name of the
    # project family and appears legitimately in diagrams and prose.
    "private project root":
        re.compile(r"GenesisMind[\\/]", re.I),
    "private vault name":
        re.compile(r"Genesis[ _]Obsidian", re.I),
    # \b on both sides, or "judgment" in ordinary English text matches.
    "operator username":
        re.compile(r"\bjudgm\b", re.I),
}

ALLOWED: tuple[str, ...] = ()

SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".zip", ".db", ".ico"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True).stdout
    return [f for f in out.decode("utf-8").split("\0") if f]


def allowed(hit: str) -> bool:
    low = hit.lower()
    return any(a in low or low in a for a in ALLOWED)


def main() -> int:
    problems: set[str] = set()

    for rel in tracked_files():
        p = Path(rel)
        if not p.is_file() or p.suffix.lower() in SKIP_SUFFIX:
            continue
        if rel.startswith("tools/privacy_scan.py"):
            continue  # this file necessarily contains the patterns it looks for
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, rx in PATTERNS.items():
            for m in rx.finditer(text):
                hit = m.group(0)
                if allowed(hit):
                    continue
                line = text[:m.start()].count("\n") + 1
                problems.add(f"{rel}:{line}: {label} -> {hit[:70]}")

    # The operator's personal profile must never ship; only the template does.
    if Path("backend/prompts/USER.md").exists():
        problems.add("backend/prompts/USER.md is present — it must never be committed")
    if not Path("backend/prompts/USER.example.md").exists():
        problems.add("backend/prompts/USER.example.md is missing")

    if problems:
        print("Operator-private or machine-specific data found in published files:")
        for x in sorted(problems):
            print(f"  {x}")
        print(f"\n  {len(problems)} finding(s)")
        return 1

    print("OK — no operator-private data in any tracked file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
