"""
scheduler.py — M0: durable Outcome Clock for THE HOUSE
=====================================================
Time-based institutional behaviour (review reminders, reputation decay, archive
integrity) cannot live in in-memory timers — the process is not always up. Jobs
are rows in `scheduled_jobs`; `tick()` runs whatever is due and is safe to call
on every boot (catch-up). Recurring jobs re-enqueue themselves.

No business logic here — handlers are registered by the modules that own them
(M1 registers 'outcome_review' and 'reputation_decay').

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional

import institutional_db as _db

# kind -> handler(payload: dict) -> Optional[dict]  (return {"reschedule_in": secs} to repeat)
_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = {}


def register_handler(kind: str, fn: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]) -> None:
    _HANDLERS[kind] = fn


def enqueue(kind: str, run_at: Optional[float] = None,
            payload: Optional[Dict[str, Any]] = None,
            job_id: Optional[str] = None, path: Optional[str] = None) -> str:
    """Schedule a job. Stable job_id makes (re)enqueue idempotent."""
    _db.ensure_schema(path)
    now = time.time()
    run_at = run_at if run_at is not None else now
    jid = job_id or ("job_" + hashlib.sha1(
        f"{kind}:{run_at}:{json.dumps(payload or {}, sort_keys=True)}".encode()).hexdigest()[:12])
    with _db.connect(path) as c:
        c.execute(
            "INSERT OR REPLACE INTO scheduled_jobs (id, kind, run_at, last_run, status, payload, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (jid, kind, float(run_at), 0.0, "pending",
             json.dumps(payload or {}, ensure_ascii=False), now))
        c.commit()
    return jid


def due_jobs(now: Optional[float] = None, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.ensure_schema(path)
    now = now if now is not None else time.time()
    with _db.connect(path) as c:
        rows = c.execute("SELECT * FROM scheduled_jobs WHERE status='pending' AND run_at<=? "
                         "ORDER BY run_at ASC", (now,)).fetchall()
        return [dict(r) for r in rows]


def _set_status(jid: str, status: str, run_at: Optional[float] = None,
                path: Optional[str] = None) -> None:
    with _db.connect(path) as c:
        if run_at is not None:
            c.execute("UPDATE scheduled_jobs SET status=?, last_run=?, run_at=? WHERE id=?",
                      (status, time.time(), float(run_at), jid))
        else:
            c.execute("UPDATE scheduled_jobs SET status=?, last_run=? WHERE id=?",
                      (status, time.time(), jid))
        c.commit()


def tick(now: Optional[float] = None, path: Optional[str] = None) -> Dict[str, Any]:
    """Run all due jobs via their registered handlers. Idempotent & safe on boot."""
    now = now if now is not None else time.time()
    ran, failed, skipped = 0, 0, 0
    for job in due_jobs(now, path):
        fn = _HANDLERS.get(job["kind"])
        if not fn:
            skipped += 1
            continue
        try:
            payload = json.loads(job["payload"] or "{}")
            res = fn(payload) or {}
            if res.get("reschedule_in"):
                _set_status(job["id"], "pending", run_at=now + float(res["reschedule_in"]), path=path)
            else:
                _set_status(job["id"], "done", path=path)
            ran += 1
        except Exception as e:
            _set_status(job["id"], "failed", path=path)
            print(f"[scheduler] job {job['id']} ({job['kind']}) failed: {e}")
            failed += 1
    return {"now": now, "ran": ran, "failed": failed, "skipped_no_handler": skipped}


def catch_up(path: Optional[str] = None) -> Dict[str, Any]:
    """Call on app boot — runs anything that came due while the process was down."""
    return tick(path=path)


def pending(path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.ensure_schema(path)
    with _db.connect(path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM scheduled_jobs WHERE status='pending' ORDER BY run_at ASC")]


def stats(path: Optional[str] = None) -> Dict[str, Any]:
    _db.ensure_schema(path)
    with _db.connect(path) as c:
        by = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM scheduled_jobs GROUP BY status")}
    return {"by_status": by, "handlers": sorted(_HANDLERS)}
