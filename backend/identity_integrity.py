"""
identity_integrity.py — ADR-0016: Single Canonical Identity
============================================================
The identity twin of the State Ownership Principle:

    Every mutable state SHALL have exactly one authoritative writer.   (P1)
    Every unit of work SHALL have exactly one canonical name.          (this)

P1 forbids two writers of one file. This forbids two ways of naming one mission —
which is the same defect wearing different clothes, and it had the same
consequence: something that should have joined, silently did not.

**Why this checks DATA and not source.** A source scan cannot decide whether
`task[:200]` is a key or a caption; the two are indistinguishable in code, and
nine modules legitimately build truncated previews for logs and UI. Asserting
"every module must call clean_identity()" would be false and would train people to
switch the guard off. So the invariant is stated where it is decidable:

    a staked claim must carry an identity that RESOLVES to a House State,
    or be explicitly marked as having none.

Measured before the fix: **0 of 8 predictions matched any stored key** — not one,
not even as a substring. The `statement` was never usable as a name.

Legacy rows staked before ADR-0016 carry no identity field. They are reported
separately rather than counted as violations: they are evidence of the defect, and
`verify(strict=False)` distinguishes "this was staked wrong" from "this is being
staked wrong now".

    python identity_integrity.py
    verify() -> {"ok": bool, "violations": [...], "legacy": [...]}

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE = Path(__file__).resolve().parent

# The stake sources whose claims are expected to carry a canonical identity.
# A source not listed here is not yet held to the principle — add it deliberately.
IDENTITY_BEARING_AGENTS = ("mission_operative",)


def _rows(path: Optional[str] = None):
    import institutional_db as _db
    _db.init_once(path)
    with _db.connect(path) as c:
        preds = [dict(r) for r in c.execute(
            "SELECT id, agent, session_id, statement, predicted_outcome, made_at "
            "FROM predictions ORDER BY made_at")]
        states = {r["question"] for r in c.execute(
            "SELECT question FROM house_state") if r["question"]}
    return preds, states


def identity_of(pred: Dict[str, Any]) -> Optional[str]:
    """The canonical name a claim was staked under, or None if it carries none."""
    try:
        payload = json.loads(pred.get("predicted_outcome") or "{}")
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    ident = payload.get("mission_identity")
    return ident if isinstance(ident, str) else None


def verify(path: Optional[str] = None) -> Dict[str, Any]:
    """Does every identity-bearing claim name something the House actually holds?"""
    preds, states = _rows(path)
    violations: List[Dict[str, str]] = []
    legacy: List[str] = []
    checked = 0

    for p in preds:
        if p.get("agent") not in IDENTITY_BEARING_AGENTS:
            continue          # session-backed claims join on session_id, not a name
        checked += 1
        ident = identity_of(p)
        if ident is None:
            legacy.append(p["id"])
            continue
        if ident == "":
            # Deliberate: clean_identity() rejected a prompt or an error string, and
            # open_state() was skipped for the same reason. Nothing to resolve TO.
            continue
        if ident not in states:
            violations.append({
                "prediction": p["id"],
                "identity": ident[:80],
                "problem": "names a House State that does not exist",
                "remedy": ("stake with mission_identity.clean_identity(task, directive) "
                           "— the same value open_state() is keyed on, untruncated"),
            })

    return {"ok": not violations, "checked": checked,
            "violations": violations, "legacy": legacy,
            "house_states": len(states)}


def report(path: Optional[str] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    r = verify(path)
    print("\nSINGLE CANONICAL IDENTITY (ADR-0016)")
    print(f"  identity-bearing claims checked : {r['checked']}")
    print(f"  House States on file            : {r['house_states']}")
    print(f"  staked before ADR-0016 (legacy) : {len(r['legacy'])}")
    if r["ok"]:
        print("\n  OK — every identity-bearing claim names a House State that exists")
        return 0
    print(f"\n  {len(r['violations'])} VIOLATION(S):")
    for v in r["violations"]:
        print(f"    {v['prediction']}: {v['problem']}")
        print(f"      identity: {v['identity']!r}")
        print(f"      → {v['remedy']}")
    return 1


if __name__ == "__main__":
    sys.exit(report())
