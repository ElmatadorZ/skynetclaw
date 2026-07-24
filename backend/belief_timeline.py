"""
belief_timeline.py — BELIEF EVOLUTION TIMELINE (Phase 4)
========================================================
A PROJECTION over the already-persisted House Mind artifacts. It builds the
causal chain that answers "I believe X because of Y":

    Question -> Evidence -> Hypothesis -> Challenge -> Belief Revision -> Decision

It creates NO new storage, NO second House State, NO new memory system. Every
node is read from real rows in house_state (state_items) and belief_changes,
each of which carries timestamp + agent (provenance). Nothing is narrated; if a
stage has no real artifact, it is reported as a GAP — never invented.

Provenance per node (all real DB columns, audited Phase 4):
  question  <- house_state.question / created_at
  evidence  <- state_items kind=known_fact|evidence  (agent, evidence, ts)
  hypothesis<- state_items kind=hypothesis           (agent, confidence, ts)
  challenge <- state_items kind=contradiction|unknown_fact|minority|blind_spot
  revision  <- belief_changes (previous->new, prev/new confidence, reason, agent, ts)
  decision  <- current belief item (content == aggregate_recommendation)

Note on field-index provenance ("ANALYST.known[0]"): the array index is NOT
persisted into house_state (only agent + kind are). We therefore report the
real available provenance (agent + kind) and never fabricate an index.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Optional

import house_state as _hs

# canonical flow order for nodes sharing a timestamp
_RANK = {"question": 0, "evidence": 1, "hypothesis": 2, "challenge": 3,
         "revision": 4, "decision": 5}
_STAGES = ("question", "evidence", "hypothesis", "challenge", "revision", "decision")
_EVT = {s: f"timeline_{s}" for s in _STAGES}

# Last-emitted node ids PER House state, for change-diffing. Keyed by state_id
# so concurrent missions keep independent timelines (no cross-talk). Resets on
# process restart.
_LAST_IDS: Dict[str, set] = {}


def _nid(*parts: Any) -> str:
    return "tn_" + hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8", "ignore")).hexdigest()[:14]


def _node(stage: str, content: str, source: str, provenance: str, ts: Any,
          **extra: Any) -> Dict[str, Any]:
    n = {
        "id": _nid(stage, content[:120], source, ts),
        "node": stage,
        "content": content,
        "source": (source or "?").upper(),
        "provenance": provenance,
        "timestamp": ts,
    }
    n.update({k: v for k, v in extra.items() if v is not None})
    return n


def timeline(state_id: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
    """Project the belief-evolution chain for a House state (the current one if
    state_id is None). Returns nodes + the list of missing stages (gaps)."""
    st_id = state_id
    if not st_id:
        try:
            cur = _hs.current(path)
        except Exception:
            cur = None
        st_id = cur["id"] if cur else None
    if not st_id:
        return {"state_id": "", "question": "", "nodes": [], "gaps": list(_STAGES), "confidence": 0.0}

    st = _hs.read_state(st_id, path)
    if not st:
        return {"state_id": st_id, "question": "", "nodes": [], "gaps": list(_STAGES), "confidence": 0.0}

    g = st.get("items", {})
    nodes: List[Dict[str, Any]] = []

    # Question
    if st.get("question"):
        nodes.append(_node("question", st["question"], "house_state", "question",
                           st.get("created_at")))

    # Evidence — verifiable facts the House holds
    for it in (g.get("known_fact", []) + g.get("evidence", [])):
        nodes.append(_node("evidence", it["content"], it.get("agent") or it.get("evidence") or "?",
                           f"{it['kind']}", it.get("ts"), confidence=it.get("confidence")))

    # Hypothesis
    for it in g.get("hypothesis", []):
        nodes.append(_node("hypothesis", it["content"], it.get("agent") or "?",
                           "hypothesis", it.get("ts"), confidence=it.get("confidence")))

    # Challenge — contradictions / open gaps / preserved minority / blind spots
    for it in (g.get("contradiction", []) + g.get("unknown_fact", [])
               + g.get("minority", []) + g.get("blind_spot", [])):
        nodes.append(_node("challenge", it["content"], it.get("agent") or "?",
                           it["kind"], it.get("ts")))

    # Belief Revision — the actual "what changed my mind", with confidence impact
    for ch in _hs.recent_changes(st_id, limit=50, path=path):
        prev = (ch.get("previous") or "").strip()
        new = (ch.get("new") or "").strip()
        impact = round((ch.get("new_confidence") or 0) - (ch.get("prev_confidence") or 0), 3)
        content = (f'"{prev[:60]}" → "{new[:60]}"' if prev else new[:90])
        nodes.append(_node("revision", content, ch.get("agent") or "?", "belief_change",
                           ch.get("ts"), confidence_impact=impact,
                           reason=(ch.get("reason") or None),
                           evidence=(ch.get("evidence") or None)))

    # Decision — the House's current belief (== aggregate_recommendation)
    beliefs = g.get("belief", [])
    if beliefs:
        b = beliefs[-1]
        nodes.append(_node("decision", b["content"], b.get("agent") or "aggregate_recommendation",
                           "belief", b.get("ts"), confidence=b.get("confidence")))

    nodes.sort(key=lambda n: (n.get("timestamp") or 0, _RANK.get(n["node"], 9)))

    present = {n["node"] for n in nodes}
    gaps = [s for s in _STAGES if s not in present]
    return {"state_id": st_id, "question": st.get("question", ""),
            "nodes": nodes, "gaps": gaps, "confidence": st.get("confidence", 0.0)}


def diff_and_emit(publish: Callable[..., Any], state_id: Optional[str] = None,
                  path: Optional[str] = None) -> List[tuple]:
    """Emit timeline_* events for NEW nodes only. Stable when nothing changed
    (returns [])."""
    tl = timeline(state_id, path)
    _key = tl.get("state_id", "")            # per-state baseline — concurrent-safe
    seen = _LAST_IDS.get(_key) or set()
    cur_ids = set()
    emitted: List[tuple] = []
    for n in tl["nodes"]:
        cur_ids.add(n["id"])
        if n["id"] in seen:
            continue
        payload = {k: v for k, v in n.items() if k != "id"}
        payload["state_id"] = tl["state_id"]
        try:
            publish(_EVT[n["node"]], payload, source="timeline")
        except Exception:
            pass
        emitted.append((_EVT[n["node"]], n))
    _LAST_IDS[_key] = cur_ids
    return emitted


def reset() -> None:
    global _LAST_IDS
    _LAST_IDS = {}
