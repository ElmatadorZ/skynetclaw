"""
learning_engine.py — INSTITUTIONAL LEARNING ENGINE (Phase 6)
============================================================
Answers: What did we learn? Why did we learn it? What changed because of it?

A PROJECTION over already-persisted REALITY artifacts. No new store, no new
memory. A lesson exists ONLY when the full chain exists:

    Prediction -> Outcome -> Evaluation -> Behavior Change

That chain is already wired: outcome_tracker.evaluate() grades a prediction
(correct/partial/incorrect) and then house_state.revise_from_outcome() folds the
graded result back into the belief, writing a belief_changes row attributed to
"Reality (outcome)". THOSE rows — and only those — are lessons.

CRITICAL RULE (enforced here):
  Lessons come from REALITY, never from beliefs/reasoning/confidence.
  -> we read belief_changes WHERE agent='Reality (outcome)'.
  -> reasoning-caused revisions (agent='Council') are EXCLUDED.
  -> if there are no graded outcomes, there are no lessons (empty, honest).

Registries:
  lessons           — outcome-caused belief revisions (the learning)
  failures          — predictions graded 'incorrect'
  successes         — predictions graded 'correct'
  behavior_changes  — lessons where the belief/confidence actually moved
  repeat_failures   — clusters of similar 'incorrect' predictions (>=2)

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

import institutional_db as _idb

_OUTCOME_AGENT = "Reality (outcome)"
_WORD = re.compile(r"[\w฀-๿]+")

# diff baselines (reset on process restart -> re-emits current set once)
_SEEN: Dict[str, set] = {"lessons": set(), "behavior": set(),
                         "invalidated": set(), "repeat_fail": set(), "repeat_succ": set()}


def _result_of(reason: str) -> str:
    r = (reason or "").upper()
    if "DISPROVEN" in r or "INCORRECT" in r:
        return "incorrect"
    if "CONFIRMED" in r or "CORRECT" in r:
        return "correct"
    if "PARTIAL" in r:
        return "partial"
    return ""


def _tokens(s: str) -> set:
    return {t.lower() for t in _WORD.findall(s or "") if len(t) > 2}


def _cluster(rows: List[Dict[str, Any]], key: str = "statement",
             thresh: float = 0.5) -> List[Dict[str, Any]]:
    """Greedy jaccard clustering of similar statements. Returns groups of size>=2."""
    toks = [(_tokens(r.get(key, "")), r) for r in rows]
    used = [False] * len(toks)
    groups: List[Dict[str, Any]] = []
    for i in range(len(toks)):
        if used[i] or not toks[i][0]:
            continue
        members = [toks[i][1]]
        used[i] = True
        for k in range(i + 1, len(toks)):
            if used[k] or not toks[k][0]:
                continue
            a, b = toks[i][0], toks[k][0]
            j = len(a & b) / len(a | b) if (a | b) else 0.0
            if j >= thresh:
                members.append(toks[k][1])
                used[k] = True
        if len(members) >= 2:
            ids = sorted(m["id"] for m in members)
            groups.append({"key": "rg_" + "_".join(ids)[:60], "count": len(members),
                           "statements": [m.get(key, "") for m in members],
                           "members": ids})
    return groups


def snapshot(limit: int = 50, path: Optional[str] = None) -> Dict[str, Any]:
    """Assemble the learning registries from real outcome artifacts. Empty when
    nothing has actually been graded by reality."""
    _idb.init_once(path)
    with _idb.connect(path) as c:
        lessons = [dict(r) for r in c.execute(
            "SELECT bc.id, bc.state_id, bc.previous, bc.new, bc.prev_confidence, "
            "bc.new_confidence, bc.reason, bc.evidence, bc.ts, hs.question "
            "FROM belief_changes bc LEFT JOIN house_state hs ON bc.state_id=hs.id "
            "WHERE bc.agent=? ORDER BY bc.ts DESC LIMIT ?", (_OUTCOME_AGENT, limit)).fetchall()]
        failures = [dict(r) for r in c.execute(
            "SELECT id, statement, agent, status, confidence, made_at, evaluated_at, "
            "predicted_outcome, evidence_source FROM predictions WHERE status='incorrect' "
            "ORDER BY evaluated_at DESC LIMIT ?", (limit,)).fetchall()]
        successes = [dict(r) for r in c.execute(
            "SELECT id, statement, agent, status, confidence, made_at, evaluated_at, "
            "predicted_outcome, evidence_source FROM predictions WHERE status='correct' "
            "ORDER BY evaluated_at DESC LIMIT ?", (limit,)).fetchall()]

    # enrich lessons: classify result + confidence impact + "what changed"
    for ln in lessons:
        ln["result"] = _result_of(ln.get("reason", ""))
        ln["confidence_impact"] = round((ln.get("new_confidence") or 0)
                                        - (ln.get("prev_confidence") or 0), 3)
        ln["behavior_changed"] = bool(
            (ln.get("previous") or "") != (ln.get("new") or "")
            or ln["confidence_impact"] != 0)

    behavior_changes = [ln for ln in lessons if ln["behavior_changed"]]
    repeat_failures = _cluster(failures)
    repeat_successes = _cluster(successes)

    return {
        "lessons": lessons,
        "failures": failures,
        "successes": successes,
        "behavior_changes": behavior_changes,
        "repeat_failures": repeat_failures,
        "repeat_successes": repeat_successes,
        "counts": {
            "lessons": len(lessons), "failures": len(failures),
            "successes": len(successes), "behavior_changes": len(behavior_changes),
            "repeat_failures": len(repeat_failures), "repeat_successes": len(repeat_successes),
        },
    }


def diff_and_emit(publish: Callable[..., Any], path: Optional[str] = None) -> List[tuple]:
    """Emit learning events for GENUINE new outcomes only. Nothing is emitted
    without a real graded outcome behind it."""
    snap = snapshot(path=path)
    emitted: List[tuple] = []

    def emit(etype: str, payload: Dict[str, Any]) -> None:
        try:
            publish(etype, payload, source="learning")
        except Exception:
            pass
        emitted.append((etype, payload.get("id") or payload.get("key")))

    for ln in snap["lessons"]:
        lid = ln["id"]
        if lid not in _SEEN["lessons"]:
            _SEEN["lessons"].add(lid)
            emit("lesson_learned", {"id": lid, "result": ln["result"],
                                    "lesson": ln.get("reason", ""), "what_changed": ln.get("new", ""),
                                    "from": ln.get("previous", ""), "confidence_impact": ln["confidence_impact"],
                                    "question": ln.get("question", "")})
            if ln["result"] == "incorrect" and lid not in _SEEN["invalidated"]:
                _SEEN["invalidated"].add(lid)
                emit("lesson_invalidated", {"id": lid, "lesson": ln.get("reason", ""),
                                            "question": ln.get("question", "")})
        if ln["behavior_changed"] and lid not in _SEEN["behavior"]:
            _SEEN["behavior"].add(lid)
            emit("behavior_changed", {"id": lid, "from": ln.get("previous", ""),
                                      "to": ln.get("new", ""), "confidence_impact": ln["confidence_impact"]})

    for g in snap["repeat_failures"]:
        if g["key"] not in _SEEN["repeat_fail"]:
            _SEEN["repeat_fail"].add(g["key"])
            emit("repeat_failure_detected", {"key": g["key"], "count": g["count"],
                                             "statements": g["statements"]})
    for g in snap["repeat_successes"]:
        if g["key"] not in _SEEN["repeat_succ"]:
            _SEEN["repeat_succ"].add(g["key"])
            emit("repeat_success_detected", {"key": g["key"], "count": g["count"],
                                             "statements": g["statements"]})
    return emitted


def reset() -> None:
    for k in _SEEN:
        _SEEN[k] = set()
