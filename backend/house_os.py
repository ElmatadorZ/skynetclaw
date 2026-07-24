"""
house_os.py — HOUSE OPERATING SYSTEM (Phase P3)
===============================================
House Mind already stores beliefs / confidence / reasoning / lessons. This adds
the institution's OPERATING layer: POLICIES and RULES — codified, persistent,
and traceable to the reality that produced them.

The chain the House must prove:
    Reality -> Lesson -> Behavior Change -> Policy -> Rule

A policy is NOT generated from opinion or by an LLM. It is codified explicitly
(by engineering or operator) and MUST carry provenance: what_happened / why /
what_changed, plus an origin pointing at the lesson (learning_engine) or the
code/behavior that enforces it. Honesty rule: if there is no real lesson or
enforced behavior behind a policy, it is not created.

Tables (additive, in the existing institutional DB — no new database):
  house_policies(id, statement, what_happened, why, what_changed, origin, status, created_at, updated_at)
  house_rules(id, statement, policy_id, enforcement, status, created_at, updated_at)

Events: policy_created, policy_updated, rule_created, rule_updated.
(behavior_changed is emitted by learning_engine from real outcomes.)

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Callable, Dict, List, Optional

import institutional_db as _idb

_SEEDED = False


def _ensure(path: Optional[str] = None) -> None:
    _idb.init_once(path)
    with _idb.connect(path) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS house_policies(
            id TEXT PRIMARY KEY, statement TEXT NOT NULL,
            what_happened TEXT DEFAULT '', why TEXT DEFAULT '',
            what_changed TEXT DEFAULT '', origin TEXT DEFAULT '',
            status TEXT DEFAULT 'active', created_at REAL, updated_at REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS house_rules(
            id TEXT PRIMARY KEY, statement TEXT NOT NULL, policy_id TEXT DEFAULT '',
            enforcement TEXT DEFAULT '', status TEXT DEFAULT 'active',
            created_at REAL, updated_at REAL)""")
        c.commit()


def _pid(statement: str) -> str:
    return "pol_" + hashlib.sha1(statement[:120].encode("utf-8", "ignore")).hexdigest()[:12]


def _rid(statement: str) -> str:
    return "rul_" + hashlib.sha1(statement[:120].encode("utf-8", "ignore")).hexdigest()[:12]


def create_policy(statement: str, what_happened: str = "", why: str = "",
                  what_changed: str = "", origin: str = "",
                  publish: Optional[Callable[..., Any]] = None,
                  path: Optional[str] = None) -> Dict[str, Any]:
    """Codify a policy with provenance. Idempotent by statement (re-call updates)."""
    _ensure(path)
    pid = _pid(statement)
    now = time.time()
    with _idb.connect(path) as c:
        exists = c.execute("SELECT id FROM house_policies WHERE id=?", (pid,)).fetchone()
        if exists:
            c.execute("UPDATE house_policies SET statement=?, what_happened=?, why=?, "
                      "what_changed=?, origin=?, updated_at=? WHERE id=?",
                      (statement, what_happened, why, what_changed, origin, now, pid))
            etype = "policy_updated"
        else:
            c.execute("INSERT INTO house_policies(id, statement, what_happened, why, "
                      "what_changed, origin, status, created_at, updated_at) "
                      "VALUES(?,?,?,?,?,?, 'active', ?, ?)",
                      (pid, statement, what_happened, why, what_changed, origin, now, now))
            etype = "policy_created"
        c.commit()
    payload = {"id": pid, "statement": statement, "origin": origin,
               "what_happened": what_happened, "why": why, "what_changed": what_changed}
    if publish:
        try: publish(etype, payload, source="house_os")
        except Exception: pass
    return {"id": pid, "event": etype, **payload}


def create_rule(statement: str, policy_id: str = "", enforcement: str = "",
                publish: Optional[Callable[..., Any]] = None,
                path: Optional[str] = None) -> Dict[str, Any]:
    _ensure(path)
    rid = _rid(statement)
    now = time.time()
    with _idb.connect(path) as c:
        exists = c.execute("SELECT id FROM house_rules WHERE id=?", (rid,)).fetchone()
        if exists:
            c.execute("UPDATE house_rules SET statement=?, policy_id=?, enforcement=?, "
                      "updated_at=? WHERE id=?", (statement, policy_id, enforcement, now, rid))
            etype = "rule_updated"
        else:
            c.execute("INSERT INTO house_rules(id, statement, policy_id, enforcement, "
                      "status, created_at, updated_at) VALUES(?,?,?,?, 'active', ?, ?)",
                      (rid, statement, policy_id, enforcement, now, now))
            etype = "rule_created"
        c.commit()
    payload = {"id": rid, "statement": statement, "policy_id": policy_id, "enforcement": enforcement}
    if publish:
        try: publish(etype, payload, source="house_os")
        except Exception: pass
    return {"id": rid, "event": etype, **payload}


def seed_reliability(publish: Optional[Callable[..., Any]] = None,
                     path: Optional[str] = None) -> None:
    """Codify the ONE policy the system genuinely enforces in code today (Phase
    P0 context reliability). Real provenance, idempotent — not fabricated."""
    global _SEEDED
    if _SEEDED:
        return
    try:
        pol = create_policy(
            statement="max_context_budget = 80% of the model window",
            what_happened="Runs halted as 'operative went silent' once cur[] exceeded num_ctx.",
            why="The agent loop appended tool output every step and never evicted, overflowing the window.",
            what_changed="On budget-critical the loop compresses old tool output into a factual snapshot and continues.",
            origin="context_budget.py + mission_snapshot.py (Phase P0)",
            publish=publish, path=path)
        create_rule(
            statement="Never exceed the context budget; recover instead of halting.",
            policy_id=pol["id"],
            enforcement="context_budget.assess() + mission_snapshot.compress() -> mission_recovered",
            publish=publish, path=path)
        _SEEDED = True
    except Exception as e:
        print(f"[HouseOS] seed skipped: {e}")


def snapshot(path: Optional[str] = None) -> Dict[str, Any]:
    """The operating-system view: policies + rules (+ the lessons / behavior
    changes they answer to, from learning_engine)."""
    _ensure(path)
    seed_reliability(path=path)
    with _idb.connect(path) as c:
        policies = [dict(r) for r in c.execute(
            "SELECT * FROM house_policies WHERE status='active' ORDER BY created_at DESC").fetchall()]
        rules = [dict(r) for r in c.execute(
            "SELECT * FROM house_rules WHERE status='active' ORDER BY created_at DESC").fetchall()]
    lessons: List[Dict[str, Any]] = []
    behavior_changes: List[Dict[str, Any]] = []
    try:
        import learning_engine as _le
        ls = _le.snapshot(path=path)
        lessons = ls.get("lessons", [])
        behavior_changes = ls.get("behavior_changes", [])
    except Exception:
        pass
    return {
        "policies": policies, "rules": rules,
        "lessons": lessons, "behavior_changes": behavior_changes,
        "counts": {"policies": len(policies), "rules": len(rules),
                   "lessons": len(lessons), "behavior_changes": len(behavior_changes)},
    }


def reset_seed() -> None:
    global _SEEDED
    _SEEDED = False
