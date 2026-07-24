"""
completion_evidence.py — OX-1.6 EVIDENCE-BASED COMPLETION (stateless)
=====================================================================
The House must PROVE completion, not merely assert it. Today a run ends the
instant the model emits "TASK_COMPLETE" — no check that the DONE_WHEN criteria
actually hold. This module verifies the claim against REAL evidence the run
already produced:

  * world_model snapshot  — which paths are verified EXISTS / ABSENT
  * files_touched         — paths a write/create/edit tool actually wrote
  * tool_results          — the real text returned by tools

It is deliberately CONSERVATIVE to avoid false-fails on legitimate work:
  * it only checks artifacts it can extract from DONE_WHEN — concrete file
    names / paths (an extension or a path separator). Prose with no checkable
    artifact is UNCHECKABLE → accepted (never gate a pure-text answer).
  * proven   — every extracted artifact is evidenced (exists / touched / in a
               successful tool result).
  * disproven— an extracted artifact is verified ABSENT in the world model
               (strong disproof: it was claimed but provably is not there).
  * else UNPROVEN — named but not yet evidenced (weak; may be a checker miss).

Stateless, deterministic, no model call, no persistence, owns no state.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# A checkable artifact = quoted name, or a token with a path separator, or a
# token ending in a known file extension.
_QUOTED = re.compile(r"[\"'`]([^\"'`\n]{1,120})[\"'`]")
_PATHY = re.compile(r"[A-Za-z0-9_./\\-]*[/\\][A-Za-z0-9_./\\-]+")
_EXT = re.compile(r"\b[A-Za-z0-9_.\-]+\.(?:py|js|ts|tsx|jsx|json|md|txt|csv|html?|ya?ml|toml|ini|cfg|sh|sql|xml|pdf|png|jpg|svg|c|cpp|h|go|rs|java|rb|php)\b")

_WRITE_OK = ("written:", "created:", "saved:", "wrote ", "moved:", "copied:")


def _basename(p: str) -> str:
    return re.split(r"[/\\]", (p or "").strip().strip("\"'`"))[-1].lower()


def extract_artifacts(done_when: str) -> List[str]:
    """Pull concrete, checkable artifacts out of a DONE_WHEN string."""
    s = done_when or ""
    found: List[str] = []
    for m in _QUOTED.findall(s):
        if _EXT.search(m) or "/" in m or "\\" in m:
            found.append(m.strip())
    found += _PATHY.findall(s)
    found += _EXT.findall(s)
    # de-dup, keep order, drop trivial
    seen, out = set(), []
    for a in found:
        a = a.strip().strip("\"'`")
        k = a.lower()
        if a and len(a) > 2 and k not in seen:
            seen.add(k)
            out.append(a)
    return out


def _evidenced(artifact: str, exists: List[str], touched: List[str],
               result_blob: str) -> bool:
    b = _basename(artifact)
    al = artifact.lower()
    for p in list(exists) + list(touched):
        pl = (p or "").lower()
        if al == pl or _basename(p) == b:
            return True
    # the artifact's basename appears in a SUCCESSFUL write/create tool result
    if b and b in result_blob:
        return True
    return False


def verify(done_when: str, world_snapshot: Optional[Dict[str, Any]],
           files_touched: Optional[List[str]],
           tool_results: Optional[List[Tuple[str, str]]]) -> Dict[str, Any]:
    """Return an evidence verdict for a TASK_COMPLETE claim against DONE_WHEN."""
    snap = world_snapshot or {}
    exists = list(snap.get("exists", []) or [])
    absent = [(_basename(p), p) for p in (snap.get("absent", []) or [])]
    touched = list(files_touched or [])
    # only successful write/create/edit results count as positive evidence text
    blob_parts: List[str] = []
    for nm, res in (tool_results or []):
        rl = (res or "").lower()
        if any(rl.lstrip().startswith(w) or w in rl[:80] for w in _WRITE_OK):
            blob_parts.append(rl)
    result_blob = "\n".join(blob_parts)

    artifacts = extract_artifacts(done_when)
    if not artifacts:
        return {"proven": True, "uncheckable": True, "disproven": False,
                "missing": [], "checked": []}

    missing, disproven_hits = [], []
    abs_base = {b for b, _ in absent}
    for a in artifacts:
        if _evidenced(a, exists, touched, result_blob):
            continue
        missing.append(a)
        if _basename(a) in abs_base:
            disproven_hits.append(a)

    return {
        "proven": len(missing) == 0,
        "disproven": len(disproven_hits) > 0,
        "missing": missing,
        "disproven_hits": disproven_hits,
        "checked": artifacts,
    }


def render_rejection(verdict: Dict[str, Any], attempt: int, max_attempts: int) -> str:
    """A concrete COMPLETION REJECTED block injected when proof is missing."""
    missing = verdict.get("missing", []) or []
    strong = verdict.get("disproven_hits", []) or []
    L = [f"## COMPLETION REJECTED ({attempt}/{max_attempts}) — DONE_WHEN is NOT yet evidenced.",
         "You asserted TASK_COMPLETE, but these criteria have no proof in this run:"]
    for m in missing[:8]:
        tag = "  ✗ VERIFIED ABSENT" if m in strong else "  ✗ no evidence"
        L.append(f"{tag}: {m}")
    L.append("Do the real work now: produce each artifact with a tool, then "
             "READ IT BACK to confirm it exists, THEN reply TASK_COMPLETE again. "
             "Do not re-assert completion without proof.")
    return "\n".join(L)
