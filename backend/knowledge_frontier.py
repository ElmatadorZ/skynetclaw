"""
knowledge_frontier.py — H3 KNOWLEDGE FRONTIER ENGINE (projection-registry)
==========================================================================
FIRST PRINCIPLE: a cognitive system exists to REDUCE UNCERTAINTY. The frontier
is the live map of that uncertainty for a mission:

  KNOWN              ← what is verified
  KNOWN UNKNOWNS     ← questions we know we cannot yet answer
  UNKNOWN UNKNOWNS   ← blind spots the House has surfaced (the honest proxy;
                       true unknown-unknowns are, by definition, unenumerable —
                       we track the ones the House has BECOME aware of)
  ASSUMPTIONS        ← unverified hypotheses / low-confidence beliefs
  DISCOVERY TARGETS  ← for each known-unknown: WHERE the answer likely lives and
                       which source reduces uncertainty fastest

This is a PROJECTION over house_state (which is already updated by every mission,
learning event and discovery) — NOT a new shadow store. The "registry" is the
continuously-recomputed view + the change events it emits. The only genuinely
NEW knowledge it adds is the DISCOVERY TARGET routing and the FRONTIER METRICS
(knowledge debt, coverage, velocities) — neither of which exists elsewhere.

Stateless, deterministic, no model call. Mirrors house_cognition / discovery.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional

import house_state as _hs

try:
    import learning_engine as _le
    _LE = True
except Exception:
    _LE = False

# ── DISCOVERY SOURCE ROUTER ──────────────────────────────────────────────────
# Deterministic: map an open question to the source that reduces its uncertainty
# fastest. Ordered — first match wins.
_SRC_RULES = [
    ("filesystem", re.compile(r"\b(file|path|directory|folder|code|repo|workspace|\.py|\.js|\.json|\.md|\.csv)\b", re.I),
     "the answer is a concrete artifact on disk — read/list/grep it"),
    ("obsidian", re.compile(r"\b(note|vault|obsidian|knowledge ?base|wiki|journal)\b", re.I),
     "prior knowledge likely already captured in the vault"),
    ("web", re.compile(r"\b(price|market|news|latest|current|today|recent|trend|stock|crypto|forex|weather|online|website|url|2024|2025|2026)\b", re.I),
     "time-sensitive / external fact — a live source is authoritative"),
    ("council", re.compile(r"\b(believe|opinion|recommend|should we|strategy|risk|forecast|trade-?off|decision)\b", re.I),
     "a judgement, not a fact — deliberation resolves it"),
    ("tool", re.compile(r"\b(calculate|compute|run|execute|convert|measure|simulate|api)\b", re.I),
     "a deterministic computation — a tool produces the answer"),
]


def route_source(question: str) -> Dict[str, Any]:
    """Where would the missing knowledge most likely exist + fastest source."""
    q = question or ""
    for src, rx, reason in _SRC_RULES:
        if rx.search(q):
            return {"source": src, "reason": reason, "confidence": 0.7}
    return {"source": "web", "reason": "no strong signal — a broad search casts the widest net", "confidence": 0.4}


def _metrics(known: List, kunk: List, blind: List, assumptions: List, confidence: float) -> Dict[str, Any]:
    nk, nu, nb, na = len(known), len(kunk), len(blind), len(assumptions)
    debt = nu + nb                      # KNOWLEDGE DEBT: unresolved uncertainty
    denom = nk + nu
    coverage = round(nk / denom, 3) if denom else 0.0
    learning_velocity = 0
    if _LE:
        try:
            learning_velocity = int(_le.snapshot().get("stats", {}).get("lessons", 0))
        except Exception:
            learning_velocity = 0
    return {
        "known_count": nk,
        "knowledge_debt": debt,            # ↓ the House must drive this toward 0
        "assumption_load": na,             # unverified beliefs in play
        "coverage": coverage,              # known / (known + known_unknowns)
        "confidence": round(float(confidence or 0.0), 3),
        "learning_velocity": learning_velocity,   # cumulative lessons (proxy)
        "frontier_size": nu + nb + na,     # total open surface to reduce
    }


def _empty_metrics() -> Dict[str, Any]:
    return {"known_count": 0, "knowledge_debt": 0, "assumption_load": 0,
            "coverage": 0.0, "confidence": 0.0, "learning_velocity": 0, "frontier_size": 0}


def frontier(state_id: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
    """The full knowledge frontier for a mission (current state if state_id is None)."""
    base = {"state_id": "", "mission": "", "known": [], "known_unknowns": [],
            "unknown_unknowns": [], "assumptions": [], "discovery_targets": [],
            "open_questions": [], "metrics": _empty_metrics()}
    try:
        st = _hs.read_state(state_id, path) if state_id else _hs.current(path)
    except Exception:
        st = None
    if not st:
        return base
    sid = st.get("id", "")
    try:
        ans = _hs.answer(sid, path) or {}
    except Exception:
        return base

    known = list(ans.get("what_we_know") or [])
    kunk = list(ans.get("what_we_dont_know") or [])
    blind = list(ans.get("blind_spots") or [])
    hyps = [h.get("hypothesis", "") for h in (ans.get("hypotheses") or []) if h.get("hypothesis")]
    low_conf = [b["belief"] for b in (ans.get("what_we_believe") or [])
                if b.get("belief") and float(b.get("confidence", 0) or 0) < 0.5]
    assumptions = hyps + low_conf
    targets = [{"question": u, **route_source(u)} for u in kunk]

    return {
        "state_id": sid,
        "mission": ans.get("question", ""),
        "known": known,
        "known_unknowns": kunk,
        "unknown_unknowns": blind,
        "assumptions": assumptions,
        "discovery_targets": targets,
        "open_questions": kunk,
        "metrics": _metrics(known, kunk, blind, assumptions, float(ans.get("overall_confidence", 0) or 0)),
    }


def render(state_id: Optional[str] = None, path: Optional[str] = None, fr: Optional[Dict] = None) -> str:
    """A KNOWLEDGE FRONTIER prompt block — directs the next move toward the
    highest-value discovery. Empty when there is no frontier."""
    fr = fr if fr is not None else frontier(state_id, path)
    ku, uu, asm, tg = fr["known_unknowns"], fr["unknown_unknowns"], fr["assumptions"], fr["discovery_targets"]
    if not (ku or uu or asm):
        return ""
    L = [f"## KNOWLEDGE FRONTIER (reduce uncertainty — debt={fr['metrics']['knowledge_debt']}, "
         f"coverage={fr['metrics']['coverage']}):"]
    if ku:
        L.append("  KNOWN UNKNOWNS (answer these next):")
        for t in tg[:6]:
            L.append(f"    • {t['question']}  →  look in {t['source'].upper()} ({t['reason']})")
    if uu:
        L.append("  BLIND SPOTS (surfaced unknown-unknowns — verify):")
        for b in uu[:4]:
            L.append(f"    ⚠ {b}")
    if asm:
        L.append("  ASSUMPTIONS IN PLAY (validate before relying on them):")
        for a in asm[:4]:
            L.append(f"    ? {a}")
    return "\n".join(L)


# ── change-emit (registry behaviour without shadow state) ────────────────────
_LAST: Dict[str, Dict[str, Any]] = {}


def diff_and_emit(publish: Callable[..., Any], state_id: Optional[str] = None,
                  path: Optional[str] = None) -> List[tuple]:
    """Emit `frontier_updated` when the frontier materially changes. Keyed by
    state_id (concurrent-safe). Fires only on real change — generates nothing."""
    fr = frontier(state_id, path)
    key = fr.get("state_id", "")
    prev = _LAST.get(key) or {}
    emitted: List[tuple] = []
    sig = (len(fr["known"]), len(fr["known_unknowns"]), len(fr["unknown_unknowns"]),
           len(fr["assumptions"]), fr["metrics"]["knowledge_debt"])
    psig = (len(prev.get("known", [])), len(prev.get("known_unknowns", [])),
            len(prev.get("unknown_unknowns", [])), len(prev.get("assumptions", [])),
            (prev.get("metrics") or {}).get("knowledge_debt"))
    if sig != psig and (fr["known"] or fr["known_unknowns"]):
        try:
            publish("frontier_updated", {"state_id": key, "metrics": fr["metrics"],
                                         "discovery_targets": fr["discovery_targets"][:6]}, source="house")
        except Exception:
            pass
        emitted.append(("frontier_updated", fr["metrics"]))
    _LAST[key] = fr
    return emitted


def reset() -> None:
    global _LAST
    _LAST = {}
