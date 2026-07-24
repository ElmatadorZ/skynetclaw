"""
mission_command.py — MISSION COMMAND CENTER (Phase 5)
=====================================================
A PROJECTION over the two real, already-persisted mission sources:

  * house_state   — council/cognitive missions (objective, confidence, agents,
                    belief) ; status open -> ACTIVE, closed -> COMPLETED
  * agent_runs    — agent execution missions ; status running -> ACTIVE,
                    complete/TASK_COMPLETE -> COMPLETED,
                    error/limit/stuck/cancelled -> FAILED

It creates NO new mission store, NO duplicate tracking, NO new memory. Both
tables already live in the one institutional DB; this module only reads them
and folds them into one unified mission view + change events.

HONESTY (audited Phase 5):
  PAUSED        — no real pause mechanism exists -> the bucket stays EMPTY.
  owner         — not persisted per mission        -> left blank.
  confidence    — real for council missions; blank for agent runs (none stored).
  progress      — real counts only (steps/tools or facts/beliefs); never a %.
  assigned_agents — council: distinct agents that actually wrote state items;
                    agent runs: blank (not persisted).
  next_action   — open council mission: soonest scheduler job; running agent:
                  "executing"; else blank. Never invented.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import institutional_db as _idb

try:
    import scheduler as _sched
    _SCHED = True
except Exception:
    _SCHED = False

# status -> bucket. ATTRIBUTION (audit 2026-07-10): only a SYSTEM-attributable
# terminal state is a failure. An operator context switch (interrupted /
# cancelled) says nothing about the mission — 82/200 recent runs were
# 'interrupted' and the old map counted them COMPLETED (else-branch), while
# 'blocked_awaiting_gate' (waiting on a human gate) missed the exact-match
# 'blocked' and ALSO landed in completed. Both misreports fed House Mind and
# the skill-ledger base rate.
_ACTIVE_AGENT = {"running"}
_DONE_AGENT = {"complete", "task_complete", "done", "success"}
# FAILED = a real error (the system did the wrong thing). INCOMPLETE = ran out of
# steps (limit) — often a deliberation with nothing to "execute", or partial work;
# not an error. Reporting them together as "N failed" made the House look broken
# when most were step-limit deliberations from testing (audit 2026-07-12).
_FAIL_AGENT = {"error", "stuck", "failed"}
_INCOMPLETE_AGENT = {"limit"}
_INTERRUPT_AGENT = {"interrupted", "cancelled"}
_PAUSED_AGENT = {"blocked", "blocked_awaiting_gate"}

_LAST: Dict[str, Dict[str, Any]] = {}   # mission id -> last (status, progress_sig, next_action)


def _house_next_action() -> str:
    if not _SCHED:
        return ""
    try:
        pend = _sched.pending() or []
    except Exception:
        return ""
    if not pend:
        return ""
    soonest = min(pend, key=lambda j: j.get("run_at", 9e18))
    return str(soonest.get("kind", "") or "")


def snapshot(path: Optional[str] = None) -> Dict[str, Any]:
    """Unified mission view, read from house_state + agent_runs. Empty buckets
    when there are genuinely no missions."""
    missions: List[Dict[str, Any]] = []
    _idb.init_once(path)
    nxt = _house_next_action()
    with _idb.connect(path) as c:
        # ── Council / cognitive missions (house_state) ───────────────────────
        try:
            hs_rows = c.execute(
                "SELECT id, question, confidence, status, created_at, updated_at "
                "FROM house_state ORDER BY updated_at DESC LIMIT 40").fetchall()
        except Exception:
            hs_rows = []
        for r in hs_rows:
            sid = r["id"]
            agents = [x["agent"] for x in c.execute(
                "SELECT DISTINCT agent FROM state_items WHERE state_id=? AND agent!='' "
                "AND superseded=0", (sid,)).fetchall()]
            counts = {x["kind"]: x["n"] for x in c.execute(
                "SELECT kind, COUNT(*) n FROM state_items WHERE state_id=? AND superseded=0 "
                "GROUP BY kind", (sid,)).fetchall()}
            is_open = (r["status"] == "open")
            # OX-HOUSE-GUARD-1: an OPEN row that is error-generated / punctuation-
            # only / zero-information is NOT active work — keep it out of the
            # active view (it stays in the DB for audit, just invisible here).
            if is_open:
                try:
                    import runtime_integrity as _ri
                    if not _ri.valid_mission_row(r["question"], r["confidence"], sum(counts.values())):
                        continue
                except Exception:
                    pass
            missions.append({
                "id": sid, "kind": "council",
                "objective": r["question"] or "",
                "status": "active" if is_open else "completed",
                "raw_status": r["status"],
                "confidence": round(float(r["confidence"] or 0.0), 3),
                "progress": {"known": counts.get("known_fact", 0),
                             "beliefs": counts.get("belief", 0),
                             "unknown": counts.get("unknown_fact", 0)},
                # mission HEALTH (real item counts) — first-class metrics
                "health": {"evidence": counts.get("known_fact", 0),
                           "reasoning": counts.get("hypothesis", 0) + counts.get("belief", 0),
                           "risks": counts.get("contradiction", 0),
                           "uncertainties": counts.get("unknown_fact", 0),
                           "hypotheses": counts.get("hypothesis", 0),
                           "beliefs": counts.get("belief", 0)},
                "assigned_agents": agents,
                "owner": "",
                "last_activity": r["updated_at"] or r["created_at"] or 0.0,
                "next_action": (nxt if is_open else ""),
                "updated_at": r["updated_at"] or r["created_at"] or 0.0,
            })
        # ── Agent execution missions (agent_runs) ────────────────────────────
        try:
            ar_rows = c.execute(
                "SELECT id, started_at, ended_at, task, model, status, n_steps, n_tools "
                "FROM agent_runs ORDER BY started_at DESC LIMIT 40").fetchall()
        except Exception:
            ar_rows = []
        for r in ar_rows:
            raw = str(r["status"] or "").lower()
            if raw in _ACTIVE_AGENT:
                bucket = "active"
            elif raw in _DONE_AGENT:
                bucket = "completed"
            elif raw in _INTERRUPT_AGENT:
                bucket = "interrupted"
            elif raw in _PAUSED_AGENT:
                bucket = "paused"
            elif raw in _INCOMPLETE_AGENT:
                bucket = "incomplete"
            elif raw in _FAIL_AGENT:
                bucket = "failed"
            else:
                # an unknown terminal status is NOT silently a success —
                # misreporting completed was how interrupted runs hid for weeks
                bucket = "interrupted"
            missions.append({
                "id": r["id"], "kind": "agent",
                "objective": r["task"] or "",
                "status": bucket,
                "raw_status": r["status"],
                "confidence": None,   # agent runs carry no confidence — honest blank
                "progress": {"steps": r["n_steps"] or 0, "tools": r["n_tools"] or 0},
                "health": {"steps": r["n_steps"] or 0, "tools": r["n_tools"] or 0},
                "assigned_agents": [],
                "owner": "",
                "model": r["model"] or "",
                "last_activity": r["ended_at"] or r["started_at"] or 0.0,
                "next_action": ("executing" if bucket == "active" else ""),
                "updated_at": r["ended_at"] or r["started_at"] or 0.0,
            })

    buckets = {"active": [], "paused": [], "completed": [], "failed": [],
               "incomplete": [], "interrupted": []}
    for m in missions:
        buckets.setdefault(m["status"], buckets["completed"]).append(m)
    for k in buckets:
        buckets[k].sort(key=lambda m: m.get("updated_at") or 0, reverse=True)
    return {
        "active": buckets["active"],
        "paused": buckets["paused"],          # runs waiting at a human gate
        "completed": buckets["completed"],
        "failed": buckets["failed"],          # a real error (system did the wrong thing)
        "incomplete": buckets["incomplete"],  # ran out of steps (limit) — not an error
        "interrupted": buckets["interrupted"],  # operator context switches — neither win nor loss
        "counts": {k: len(v) for k, v in buckets.items()},
        "house_next_action": nxt,
    }


def _flat(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for k in ("active", "paused", "completed", "failed", "incomplete", "interrupted"):
        out.extend(snap.get(k, []))
    return out


def _progress_sig(m: Dict[str, Any]) -> str:
    p = m.get("progress") or {}
    return ",".join(f"{k}={p[k]}" for k in sorted(p))


def diff_and_emit(publish: Callable[..., Any], path: Optional[str] = None) -> List[tuple]:
    """Emit mission_* events for GENUINE changes only. mission_paused /
    mission_resumed are never emitted — no real pause mechanism exists."""
    global _LAST
    snap = snapshot(path)
    emitted: List[tuple] = []

    def emit(etype: str, m: Dict[str, Any]) -> None:
        payload = {"id": m["id"], "kind": m["kind"], "objective": m["objective"],
                   "status": m["status"], "progress": m.get("progress"),
                   "confidence": m.get("confidence"),
                   "assigned_agents": m.get("assigned_agents"),
                   "next_action": m.get("next_action"), "updated_at": m.get("updated_at")}
        try:
            publish(etype, payload, source="mission")
        except Exception:
            pass
        emitted.append((etype, m["id"]))

    cur: Dict[str, Dict[str, Any]] = {}
    for m in _flat(snap):
        cur[m["id"]] = m
        prev = _LAST.get(m["id"])
        sig = _progress_sig(m)
        if prev is None:
            emit("mission_created", m)
            if m["status"] == "active":
                emit("mission_started", m)
        else:
            if prev["status"] != m["status"]:
                if m["status"] == "active":
                    emit("mission_started", m)
                elif m["status"] == "completed":
                    emit("mission_completed", m)
                elif m["status"] == "failed":
                    emit("mission_failed", m)
            if prev.get("sig") != sig and m["status"] == "active":
                emit("mission_progress", m)
            if prev.get("next_action", "") != m.get("next_action", ""):
                emit("mission_next_action_changed", m)
        _LAST[m["id"]] = {"status": m["status"], "sig": sig,
                          "next_action": m.get("next_action", "")}
    return emitted


def reset() -> None:
    global _LAST
    _LAST = {}
