"""
workflow_runs.py — OX-WORKFLOW-1 WORKFLOW PERSISTENCE PROTOCOL (additive store)
==============================================================================
Closes the "attempt gap" from OX-WORKFLOW-LIFECYCLE-AUDIT: ~30% of dispatches
left NO trace because persistence began only at COUNCIL/EXECUTE, so a stall in
COMPREHEND/PLAN vanished. This is a SEPARATE, additive lifecycle store — it does
NOT touch runtime, house_state, agent_runs, learning, capability, attribution or
reinforcement. Every dispatch gets a durable workflow_runs row the moment it is
issued, and always reaches a terminal status.

Lifecycle (status / phase):
  DISPATCH   → status=created   phase=dispatch
  COMPREHEND → status=active    phase=comprehend
  PLAN       → status=active    phase=plan
  COUNCIL    → status=active    phase=council
  EXECUTE    → status=active    phase=execute
  COMPLETE   → status=completed phase=complete
  any failure→ status=failed|interrupted|timeout (+termination_reason)

Correlation: house_state_id + agent_run_id link
  dispatch → workflow → mission(house_state) → execution(agent_run) → outcome.

Stored in skynerclaw.db (new table only — additive; no schema change elsewhere).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_DB = Path(__file__).parent / "skynerclaw.db"

# non-terminal vs terminal
ACTIVE_STATUSES = ("created", "active")
TERMINAL_STATUSES = ("completed", "failed", "interrupted", "timeout")

# phase ordering (for "average phase reached" + failure distribution)
PHASE_ORDER = ["dispatch", "comprehend", "plan", "council", "execute", "reflect", "complete"]
_PHASE_IX = {p: i for i, p in enumerate(PHASE_ORDER)}


class WorkflowRunsDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or _DEFAULT_DB)
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _ensure_schema(self) -> None:
        try:
            with self._conn() as c:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_runs(
                        workflow_id         TEXT PRIMARY KEY,
                        created_at          REAL NOT NULL,
                        updated_at          REAL,
                        directive           TEXT,
                        status              TEXT,
                        phase               TEXT,
                        termination_reason  TEXT,
                        house_state_id      TEXT,
                        agent_run_id        TEXT
                    )
                """)
                c.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_created ON workflow_runs(created_at DESC)")
                c.commit()
        except Exception as e:
            print(f"[workflow_runs.schema] {e}")

    # ── lifecycle writes ─────────────────────────────────────────────────────
    def start(self, workflow_id: str, directive: str = "") -> bool:
        """DISPATCH — durable record the instant a dispatch is issued."""
        try:
            now = time.time()
            with self._conn() as c:
                c.execute(
                    "INSERT OR IGNORE INTO workflow_runs"
                    "(workflow_id, created_at, updated_at, directive, status, phase, "
                    " termination_reason, house_state_id, agent_run_id) "
                    "VALUES(?,?,?,?, 'created', 'dispatch', '', NULL, NULL)",
                    (workflow_id, now, now, (directive or "")[:1000]),
                )
            return True
        except Exception as e:
            print(f"[workflow_runs.start] {e}")
            return False

    def set_phase(self, workflow_id: str, phase: str) -> bool:
        """Advance the phase; keeps status='active' while non-terminal. Never
        moves a workflow that has already reached a terminal status."""
        try:
            with self._conn() as c:
                c.execute(
                    "UPDATE workflow_runs SET phase=?, "
                    "status=CASE WHEN status IN ('created','active') THEN 'active' ELSE status END, "
                    "updated_at=? WHERE workflow_id=?",
                    (phase, time.time(), workflow_id),
                )
            return True
        except Exception as e:
            print(f"[workflow_runs.set_phase] {e}")
            return False

    def link(self, workflow_id: str, house_state_id: Optional[str] = None,
             agent_run_id: Optional[str] = None) -> bool:
        """Correlate to the mission (house_state) and execution (agent_run).
        COALESCE so the first non-null id wins and is never overwritten."""
        try:
            with self._conn() as c:
                c.execute(
                    "UPDATE workflow_runs SET "
                    "house_state_id=COALESCE(house_state_id, ?), "
                    "agent_run_id=COALESCE(agent_run_id, ?), updated_at=? "
                    "WHERE workflow_id=?",
                    (house_state_id, agent_run_id, time.time(), workflow_id),
                )
            return True
        except Exception as e:
            print(f"[workflow_runs.link] {e}")
            return False

    def complete(self, workflow_id: str, status: str = "completed",
                 termination_reason: str = "") -> bool:
        """Terminal close. status ∈ completed|failed|interrupted|timeout."""
        phase = "complete" if status == "completed" else None
        try:
            with self._conn() as c:
                if phase:
                    c.execute(
                        "UPDATE workflow_runs SET status=?, phase=?, termination_reason=?, "
                        "updated_at=? WHERE workflow_id=?",
                        (status, phase, (termination_reason or "")[:300], time.time(), workflow_id),
                    )
                else:
                    c.execute(
                        "UPDATE workflow_runs SET status=?, termination_reason=?, "
                        "updated_at=? WHERE workflow_id=?",
                        (status, (termination_reason or "")[:300], time.time(), workflow_id),
                    )
            return True
        except Exception as e:
            print(f"[workflow_runs.complete] {e}")
            return False

    def complete_if_open(self, workflow_id: str, status: str = "interrupted",
                         termination_reason: str = "") -> bool:
        """Idempotent terminal close — only writes if still non-terminal. Safe in
        a finally/disconnect path; never clobbers a real terminal status."""
        try:
            with self._conn() as c:
                cur = c.execute(
                    "UPDATE workflow_runs SET status=?, termination_reason=?, updated_at=? "
                    "WHERE workflow_id=? AND status IN ('created','active')",
                    (status, (termination_reason or "")[:300], time.time(), workflow_id),
                )
                return cur.rowcount > 0
        except Exception as e:
            print(f"[workflow_runs.complete_if_open] {e}")
            return False

    # ── startup reconciliation ───────────────────────────────────────────────
    def reconcile_stale(self, max_age_seconds: float = 1800.0,
                        status: str = "interrupted") -> int:
        """No workflow may remain active after process termination. Flip
        created/active rows older than max_age_seconds to a terminal status."""
        try:
            cutoff = time.time() - float(max_age_seconds)
            with self._conn() as c:
                cur = c.execute(
                    "UPDATE workflow_runs SET status=?, "
                    "termination_reason=CASE WHEN termination_reason IS NULL OR termination_reason='' "
                    "THEN '[reconciled: orphaned workflow]' ELSE termination_reason END, "
                    "updated_at=? WHERE status IN ('created','active') AND created_at < ?",
                    (status, time.time(), cutoff),
                )
                n = cur.rowcount
            if n:
                print(f"[workflow_runs.reconcile] flipped {n} stale workflow(s) → '{status}'")
            return n
        except Exception as e:
            print(f"[workflow_runs.reconcile] {e}")
            return 0

    # ── reads ──────────────────────────────────────────────────────────────--
    def get(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._conn() as c:
                r = c.execute("SELECT * FROM workflow_runs WHERE workflow_id=?", (workflow_id,)).fetchone()
            return dict(r) if r else None
        except Exception:
            return None

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with self._conn() as c:
                return [dict(r) for r in c.execute(
                    "SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT ?",
                    (max(1, int(limit)),))]
        except Exception:
            return []

    # ── telemetry ──────────────────────────────────────────────────────────--
    def metrics(self) -> Dict[str, Any]:
        """Workflow metrics: completion rate, abandonment rate, average phase
        reached, and the phase-failure distribution (where non-completed
        workflows died)."""
        rows = self.recent(limit=100000)
        n = len(rows)
        if not n:
            return {"total": 0, "completion_rate": 0.0, "abandonment_rate": 0.0,
                    "avg_phase_reached": 0.0, "avg_phase_label": "—",
                    "by_status": {}, "phase_failure_distribution": {}}
        by_status: Dict[str, int] = {}
        completed = 0
        phase_ix_sum = 0
        fail_dist: Dict[str, int] = {}
        for r in rows:
            st = r.get("status") or "unknown"
            by_status[st] = by_status.get(st, 0) + 1
            phase_ix_sum += _PHASE_IX.get(r.get("phase") or "dispatch", 0)
            if st == "completed":
                completed += 1
            else:  # non-completed → record where it stalled
                ph = r.get("phase") or "dispatch"
                fail_dist[ph] = fail_dist.get(ph, 0) + 1
        avg_ix = phase_ix_sum / n
        avg_label = PHASE_ORDER[min(len(PHASE_ORDER) - 1, round(avg_ix))]
        abandoned = sum(by_status.get(s, 0) for s in ("interrupted", "timeout", "failed"))
        return {
            "total": n,
            "completion_rate": round(completed / n, 3),
            "abandonment_rate": round(abandoned / n, 3),
            "avg_phase_reached": round(avg_ix, 2),
            "avg_phase_label": avg_label,
            "by_status": by_status,
            "phase_failure_distribution": fail_dist,
        }
