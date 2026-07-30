"""
state_ownership.py — P1 / ADR-0014 D3: one authoritative writer per state file
==============================================================================
The Constitution carries this as the **State Ownership Principle**:

    Every mutable state SHALL have exactly one authoritative writer.
    Derived projections MAY exist. Additional authoritative writers SHALL NOT.

Auditing the three co-owned files named in ADR-0014 D3 found the principle
already satisfied in practice — each has one module that actually writes it. What
was missing is that the property was **undeclared and unenforced**: nothing said
which module held the authority, and nothing stopped a second writer appearing.

That is the failure mode this instrument exists to prevent. An invariant that
holds by luck reads exactly like one that holds by design, right up until someone
adds a convenient `json.dump` and nobody notices for a month.

So P1's deliverable is not a refactor of code that is already correct. It is to
**write the ownership down and make CI keep it true.**

`verify()` is deliberately conservative: it reports a module that writes a file it
does not own, and it does NOT try to judge intent. A false positive here is a
one-line addition to a declared exemption with a reason recorded beside it, which
is cheap. A false negative is a silent second writer, which is what D3 exists to
forbid.

    python state_ownership.py        # report
    verify() -> {"ok": bool, "violations": [...]}

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE = Path(__file__).resolve().parent

# ── the declaration ──────────────────────────────────────────────────────────
# file -> the ONE module permitted to write it, and why it holds the authority.
OWNERS: Dict[str, Dict[str, str]] = {
    # Ownership is AUTHORITY, not whichever call touches the bytes. An earlier
    # draft named the backup chain as owner, which made main.save_settings() — the
    # declared API — trip its own guard. The authority is the function operators
    # and modules are told to call; the chain is its mechanism.
    "settings.json": {
        "owner": "main.py",
        "api": "main.save_settings()  (delegates to _SETTINGS_CHAIN.safe_save)",
        "why": ("the backup chain rotates .bak/.last-good before every write, so a "
                "second writer would bypass corruption recovery"),
    },
    "governance_config.json": {
        "owner": "governance.py",
        "api": "GPS2Gate (loads, migrates on version bump, saves)",
        "why": ("the permission policy is the security boundary; a second writer "
                "could widen it without passing the migration that records why"),
    },
    "atlas_genome.json": {
        "owner": "agentic_workflow.py",
        "api": "atomic write via tmp.replace()",
        "why": ("strategy rules accumulate across reflections; a non-atomic second "
                "writer could interleave and lose a rule"),
    },
}

# Writers permitted despite not being the owner, each with a stated reason. This
# list is short on purpose: every entry is a hole in the principle.
EXEMPT: Dict[str, str] = {
    "chaos_test.py": ("a fault-injection harness — it corrupts settings.json on "
                      "purpose to prove the backup chain recovers. Test-only; not "
                      "imported by the running House."),
    "state_ownership.py": "this file names the paths in order to guard them",
    "openclaw_port_tier2.py": ("the backup-chain MECHANISM that main.save_settings() "
                               "delegates to — it is how the owner writes, not a "
                               "second authority. Nothing else may call it for "
                               "settings.json."),
    "skynetclaw_meta.py": ("quarantines a CORRUPT atlas_genome.json by renaming it "
                           "aside; it never writes genome content"),
}

# Writes THROUGH a name bound to a declared path. Resolving the binding is the
# whole point.
#
# A first version looked for the filename literal and then for any write within
# eight lines of it. That found the real violation in obsidian_tools.py — by luck.
# The line it matched was an *error message* containing "settings.json", and a
# genuine write happened to sit nearby. Re-inject the same violation using the
# module's path constant and the check sailed through, because a module that binds
# `SETTINGS = _BASE / "settings.json"` on line 24 and writes it on line 200 has no
# filename literal anywhere near the write.
#
# An instrument that passes by luck is the exact failure this whole guard exists to
# forbid, so the binding is resolved first and writes are then matched through the
# NAME, anywhere in the module.
_BINDING = re.compile(
    r"^\s*([A-Z_][A-Z0-9_]*|_?[a-z_][a-z0-9_]*)\s*=\s*[^=\n]*?['\"]{fname}['\"]")

_WRITE_TMPL = (
    r"\b{n}\s*\.\s*(?:write_text|write_bytes|open)\s*\(|"
    r"json\.dump\s*\([^)]*?,\s*(?:open\s*\(\s*)?{n}\b|"
    r"_save_json\s*\(\s*{n}\b|"
    r"\.\s*replace\s*\(\s*{n}\b|"
    r"open\s*\(\s*{n}\s*,\s*['\"][wa]"
)

# A literal write with no binding at all: open("settings.json", "w").
_LITERAL_WRITE_TMPL = (
    r"\b(?:write_text|write_bytes)\s*\([^)]*['\"]{fname}['\"]|"
    r"open\s*\(\s*['\"][^'\"]*{fname}['\"]\s*,\s*['\"][wa]|"
    r"_save_json\s*\([^)]*['\"]{fname}['\"]"
)


def _bound_names(lines: List[str], fname: str) -> List[str]:
    """Names bound to the declared path, WITH scope.

    A regex could not do this correctly. `self_awareness.py` binds
    `p = _BASE / "settings.json"` inside one function and reuses `p` as an
    unrelated local in another that writes SELF.md — a name-only match reported
    that as a violation of settings.json ownership. It was a false positive, and a
    guard that cries wolf is a guard that gets switched off.

    So scope is resolved with the parser instead of guessed: a binding inside a
    function is visible only within that function, and only a module-level
    binding is global. Returns names paired with the scope they are visible in.
    """
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return []

    found: List[str] = []

    def mentions(node) -> bool:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and fname in sub.value:
                return True
        return False

    def scan(scope, qualifier: str) -> None:
        for node in ast.iter_child_nodes(scope):
            if isinstance(node, ast.Assign) and mentions(node.value):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        found.append(f"{qualifier}{t.id}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scan(node, f"{qualifier}{node.name}.")
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                scan(node, qualifier)

    scan(tree, "")
    return found


def _write_sites(lines: List[str], fname: str, names: List[str]) -> Optional[int]:
    """First line that writes the declared path, or None.

    Scope-aware: a name bound inside `foo` is only a write if the write is also
    inside `foo`.
    """
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return None

    lit = re.compile(_LITERAL_WRITE_TMPL.format(fname=re.escape(fname)))
    for i, ln in enumerate(lines):
        if not ln.lstrip().startswith("#") and lit.search(ln):
            return i + 1

    by_scope: Dict[str, List[str]] = {}
    for q in names:
        scope, _, leaf = q.rpartition(".")
        by_scope.setdefault(scope, []).append(leaf)

    def check_scope(scope_node, qualifier: str) -> Optional[int]:
        visible = list(by_scope.get("", []))            # module-level names
        visible += by_scope.get(qualifier.rstrip("."), [])
        if visible:
            pats = [re.compile(_WRITE_TMPL.format(n=re.escape(n))) for n in visible]
            for node in ast.walk(scope_node):
                ln_no = getattr(node, "lineno", None)
                if not ln_no or ln_no > len(lines):
                    continue
                src = lines[ln_no - 1]
                if src.lstrip().startswith("#"):
                    continue
                if any(p.search(src) for p in pats):
                    return ln_no
        for node in ast.iter_child_nodes(scope_node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                got = check_scope(node, f"{qualifier}{node.name}.")
                if got:
                    return got
        return None

    return check_scope(tree, "")


def verify(base: Path = None) -> Dict[str, Any]:
    """Report modules that write a declared file they do not own."""
    base = base or _BASE
    violations: List[Dict[str, str]] = []
    checked = 0

    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(base).as_posix()
        name = path.name
        if name in EXEMPT or rel.startswith("tests/"):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        checked += 1

        for fname, spec in OWNERS.items():
            if name == spec["owner"]:
                continue                       # the owner may write it
            if fname not in "\n".join(lines):
                continue

            hit = _write_sites(lines, fname, _bound_names(lines, fname))
            if hit:
                violations.append({
                    "module": rel, "file": fname, "line": hit,
                    "owner": spec["owner"],
                    "remedy": f"call {spec['api']} instead of writing {fname}",
                })

    return {"ok": not violations, "modules_checked": checked,
            "declared_files": len(OWNERS), "violations": violations}


def report() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("\nSTATE OWNERSHIP (ADR-0014 D3 · Constitution: one authoritative writer)")
    for f, s in OWNERS.items():
        print(f"\n  {f}")
        print(f"    owner : {s['owner']}")
        print(f"    api   : {s['api']}")
        print(f"    why   : {s['why']}")
    r = verify()
    print(f"\n  {r['modules_checked']} modules checked · "
          f"{r['declared_files']} declared files")
    if r["ok"]:
        print("  OK — no module writes a file it does not own")
        return 0
    print(f"\n  {len(r['violations'])} VIOLATION(S):")
    for v in r["violations"]:
        print(f"    {v['module']}:{v['line']} writes {v['file']} "
              f"(owner: {v['owner']})")
        print(f"      → {v['remedy']}")
    return 1


if __name__ == "__main__":
    sys.exit(report())
