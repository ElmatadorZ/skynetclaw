"""
a11y_regression_test.py — static regression guard for the WCAG 2.1 AA fixes in
index.html. This locks the specific accessibility fixes so a future edit cannot
silently revert them. It is a STATIC check (grep-level); a full automated axe /
Playwright pass is Future Work (see docs/KNOWN_RISKS.md).

Run:  python a11y_regression_test.py
Exit: non-zero if any locked a11y fix is missing.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

HTML = (Path(__file__).parent.parent / "index.html").read_text(encoding="utf-8")
_fail = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond: _fail.append(name)


# WCAG 3.1.1 — language of page
check("lang is Thai (3.1.1)", '<html lang="th">' in HTML)

# WCAG 1.4.3 — contrast tokens must be the lifted (AA-passing) values
check("--text2 lifted to #7a91b3 (contrast)", "--text2:#7a91b3" in HTML)
check("--text3 lifted to #7590b0 (contrast on cards)", "--text3:#7590b0" in HTML)
check("seg mode buttons use --text2 (not the dim text3)", ".chat-toolbar .seg .tb-btn{" in HTML and "color:var(--text2)" in HTML)
check("proc-title uses --accent2 (was 4.3:1 accent)", ".proc-title{color:var(--accent2)}" in HTML)

# WCAG 2.4.7 — visible keyboard focus
check("focus-visible ring present (2.4.7)", ":focus-visible{outline:" in HTML)

# WCAG 4.1.2 / 3.3.2 — accessible names for control that lack visible text
for cid in ["model-sel", "conn-sel", "upload-input", "nc-preset", "nc-type",
            "pkg-mgr", "obs-model-sel", "agent-max-steps", "intg-svc"]:
    check(f"aria-label mapped for #{cid} (4.1.2)", f"'{cid}':" in HTML)

# WCAG 1.3.1 / 2.4.1 — page structure & landmarks
check("sr-only <h1> present (2.4.6)", re.search(r'<h1 class="sr-only">', HTML) is not None)
check("one <main> landmark set on active page (1.3.1)", "setAttribute('role','main')" in HTML)

# WCAG 2.5.8 — target size for the process-log close button
check("proc-close min target size >=24px (2.5.8)", ".proc-close{min-width:24px;min-height:24px}" in HTML)

# WCAG 2.3.3 — respect reduced motion
check("prefers-reduced-motion honored (2.3.3)", "prefers-reduced-motion" in HTML)

# WCAG 4.1.3 — status messages via live region
check("aria-live status region present (4.1.3)", 'id="a11y-live"' in HTML and 'aria-live="polite"' in HTML)

if __name__ == "__main__":
    print("=" * 56); print("  A11Y REGRESSION (static, WCAG 2.1 AA fixes)"); print("=" * 56)
    print()
    if _fail:
        print(f"\nRESULT: {len(_fail)} A11Y REGRESSION(S) FAILED — {_fail}")
        sys.exit(1)
    print("\nRESULT: ALL A11Y REGRESSIONS PASS")
