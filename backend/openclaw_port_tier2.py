"""
openclaw_port_tier2.py
======================
Tier 2 OpenClaw → SkynetClaw ports (3 utilities, 1 module):

  6. SettingsBackupChain — rotate settings.json backups + safe load with
                            auto-rollback to last-good on parse failure
  7. AgentRunsDB         — SQL table for agent_run history (queryable, dashboardable)
  8. ModelCostOverlay    — multi-provider cost data; Router can pick cheapest
                            in @auto/AMBIENT mode

Each utility is independent. Designed to be wired into main.py with minimal
churn. Self-test runs all three end-to-end.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import time
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BASE = Path(__file__).parent

# ──────────────────────────────────────────────────────────────────────────────
# 6. SETTINGS BACKUP CHAIN
#    OpenClaw pattern:  openclaw.json  +  .bak  .bak.1  .bak.2  .bak.3  .last-good
# ──────────────────────────────────────────────────────────────────────────────
class SettingsBackupChain:
    """
    Rotate settings.json backups through a fixed chain on every save.
    On load, fall back through the chain if the primary fails to parse.

    Layout (newest → oldest):
        settings.json          ← current
        settings.json.bak      ← previous save
        settings.json.bak.1
        settings.json.bak.2
        settings.json.bak.3
        settings.json.last-good ← updated only when load+parse succeeds

    Public API:
        chain = SettingsBackupChain(settings_path)
        chain.safe_load(default)   → dict
        chain.safe_save(data)      → bool (True if saved + chain rotated)
    """

    BAK_DEPTH = 3   # .bak, .bak.1, .bak.2, .bak.3 → keep last 4 + last-good

    def __init__(self, settings_path: Path):
        self.path = Path(settings_path)
        self.last_good = self.path.with_name(self.path.name + ".last-good")

    def _bak(self, n: Optional[int] = None) -> Path:
        if n is None:
            return self.path.with_name(self.path.name + ".bak")
        return self.path.with_name(self.path.name + f".bak.{n}")

    def _rotate(self) -> None:
        """Shift .bak.2 → .bak.3, .bak.1 → .bak.2, .bak → .bak.1, current → .bak"""
        try:
            for n in range(self.BAK_DEPTH, 0, -1):
                src = self._bak(n - 1) if n > 1 else self._bak()
                dst = self._bak(n)
                if src.exists():
                    try:
                        if dst.exists():
                            dst.unlink()
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
            if self.path.exists():
                try:
                    bak = self._bak()
                    if bak.exists():
                        bak.unlink()
                    shutil.copy2(self.path, bak)
                except Exception:
                    pass
        except Exception as e:
            print(f"[settings.rotate] failed: {e}")

    def safe_save(self, data: Dict[str, Any]) -> bool:
        """Atomic-ish save: rotate previous → write tmp → replace → update last-good.
        On any failure the good file is left untouched AND the stray .tmp is cleaned
        up (chaos EXP-2 regression: an interrupted save must not leak a .tmp)."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self._rotate()
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            tmp.replace(self.path)
            # Confirm round-trip parse before promoting last-good
            try:
                json.loads(self.path.read_text(encoding="utf-8"))
                shutil.copy2(self.path, self.last_good)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[settings.safe_save] failed: {e}")
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            return False

    def safe_load(self, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Try primary → .bak → .bak.1..N → .last-good → default. Returns dict + writes
        recovered version back to primary if primary was unreadable."""
        default = default or {}
        candidates: List[Path] = [self.path, self._bak()]
        candidates += [self._bak(n) for n in range(1, self.BAK_DEPTH + 1)]
        candidates.append(self.last_good)

        for i, p in enumerate(candidates):
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if i > 0:
                    # Primary was bad — recover from this fallback
                    print(f"[settings.safe_load] primary corrupt, recovered from {p.name}")
                    try:
                        shutil.copy2(p, self.path)
                    except Exception:
                        pass
                return data
            except Exception as e:
                print(f"[settings.safe_load] {p.name} unreadable: {e}")
                continue
        return dict(default)


# ──────────────────────────────────────────────────────────────────────────────
# 7. AGENT RUNS DATABASE
#    OpenClaw pattern:  tasks/runs.sqlite — every agent run persisted as a row
# ──────────────────────────────────────────────────────────────────────────────
class AgentRunsDB:
    """
    Persists per-run agent execution history into the existing skynerclaw.db.
    Dashboard / reporting / Genome consumes from here.

    Schema:
        agent_runs(
          id TEXT PRIMARY KEY,
          started_at REAL,
          ended_at REAL,
          task TEXT,
          model TEXT,
          status TEXT,           -- TASK_COMPLETE | limit | stuck | error
          n_steps INTEGER,
          n_tools INTEGER,
          n_blocks INTEGER,      -- how many Shadow Gate blocks
          trajectory_path TEXT,  -- path to trajectory.jsonl (for replay)
          summary TEXT
        )

    Methods:
        db.start_run(...)        → returns run_id
        db.end_run(run_id, ...)  → updates row
        db.recent(limit=50)      → list of dicts
        db.get(run_id)           → dict or None
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _ensure_schema(self) -> None:
        try:
            with self._conn() as c:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS agent_runs(
                        id              TEXT PRIMARY KEY,
                        started_at      REAL NOT NULL,
                        ended_at        REAL,
                        task            TEXT,
                        model           TEXT,
                        status          TEXT,
                        n_steps         INTEGER DEFAULT 0,
                        n_tools         INTEGER DEFAULT 0,
                        n_blocks        INTEGER DEFAULT 0,
                        trajectory_path TEXT,
                        summary         TEXT
                    )
                """)
                c.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at "
                          "ON agent_runs(started_at DESC)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status "
                          "ON agent_runs(status)")
                c.commit()
        except Exception as e:
            print(f"[agent_runs.schema] failed: {e}")

    def start_run(self, run_id: str, task: str, model: str = "",
                  trajectory_path: str = "") -> bool:
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO agent_runs(id, started_at, task, model, "
                    "status, n_steps, n_tools, n_blocks, trajectory_path, summary) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (run_id, time.time(), (task or "")[:1000], model or "",
                     "running", 0, 0, 0, trajectory_path or "", ""),
                )
            return True
        except Exception as e:
            print(f"[agent_runs.start] {e}")
            return False

    def end_run(self, run_id: str, status: str, n_steps: int = 0,
                n_tools: int = 0, n_blocks: int = 0, summary: str = "") -> bool:
        try:
            with self._conn() as c:
                c.execute(
                    "UPDATE agent_runs SET ended_at=?, status=?, n_steps=?, "
                    "n_tools=?, n_blocks=?, summary=? WHERE id=?",
                    (time.time(), status, int(n_steps), int(n_tools),
                     int(n_blocks), (summary or "")[:2000], run_id),
                )
            return True
        except Exception as e:
            print(f"[agent_runs.end] {e}")
            return False

    # ── OX-STABILITY-1 Phase 1: orphan-run guarantees ─────────────────────────
    # A run is TERMINAL once its status is anything other than 'running'. Only
    # 'running' rows are orphans-in-waiting.
    TERMINAL_STATUSES = ("TASK_COMPLETE", "failed", "limit", "blocked",
                         "blocked_awaiting_gate", "interrupted", "error",
                         "cancelled", "stuck")

    def end_run_if_open(self, run_id: str, status: str = "interrupted",
                        summary: str = "") -> bool:
        """Idempotent terminal close — only writes if the run is still 'running'.
        Safe to call from a finally/except catch-all without clobbering a real
        terminal status set on the normal path."""
        try:
            with self._conn() as c:
                cur = c.execute(
                    "UPDATE agent_runs SET ended_at=?, status=?, summary=? "
                    "WHERE id=? AND status='running'",
                    (time.time(), status, (summary or "")[:2000], run_id),
                )
                return cur.rowcount > 0
        except Exception as e:
            print(f"[agent_runs.end_if_open] {e}")
            return False

    def reconcile_stale_runs(self, max_age_seconds: float = 1800.0,
                             status: str = "interrupted") -> int:
        """STARTUP RECONCILIATION — no run may stay 'running' after process
        termination. Flip every 'running' row older than max_age_seconds to a
        terminal status. Returns how many were reconciled. Default 30 min: a run
        still 'running' that old cannot belong to a live in-process request."""
        try:
            cutoff = time.time() - float(max_age_seconds)
            with self._conn() as c:
                cur = c.execute(
                    "UPDATE agent_runs SET ended_at=COALESCE(ended_at, ?), status=?, "
                    "summary=CASE WHEN summary IS NULL OR summary='' "
                    "THEN '[reconciled: orphaned running run]' ELSE summary END "
                    "WHERE status='running' AND started_at < ?",
                    (time.time(), status, cutoff),
                )
                n = cur.rowcount
            if n:
                print(f"[agent_runs.reconcile] flipped {n} stale 'running' → '{status}'")
            return n
        except Exception as e:
            print(f"[agent_runs.reconcile] {e}")
            return 0

    def recent(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        try:
            with self._conn() as c:
                if status:
                    rows = c.execute(
                        "SELECT id, started_at, ended_at, task, model, status, "
                        "n_steps, n_tools, n_blocks, trajectory_path, summary "
                        "FROM agent_runs WHERE status=? "
                        "ORDER BY started_at DESC LIMIT ?",
                        (status, limit),
                    ).fetchall()
                else:
                    rows = c.execute(
                        "SELECT id, started_at, ended_at, task, model, status, "
                        "n_steps, n_tools, n_blocks, trajectory_path, summary "
                        "FROM agent_runs ORDER BY started_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            keys = ["id", "started_at", "ended_at", "task", "model", "status",
                    "n_steps", "n_tools", "n_blocks", "trajectory_path", "summary"]
            return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            print(f"[agent_runs.recent] {e}")
            return []

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._conn() as c:
                row = c.execute(
                    "SELECT id, started_at, ended_at, task, model, status, "
                    "n_steps, n_tools, n_blocks, trajectory_path, summary "
                    "FROM agent_runs WHERE id=?", (run_id,),
                ).fetchone()
            if not row:
                return None
            keys = ["id", "started_at", "ended_at", "task", "model", "status",
                    "n_steps", "n_tools", "n_blocks", "trajectory_path", "summary"]
            return dict(zip(keys, row))
        except Exception:
            return None

    def stats(self, since_seconds: int = 86400) -> Dict[str, Any]:
        """Aggregate stats over the last N seconds (default 24h)."""
        cutoff = time.time() - since_seconds
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT status, COUNT(*), SUM(n_tools), SUM(n_blocks) "
                    "FROM agent_runs WHERE started_at >= ? GROUP BY status",
                    (cutoff,),
                ).fetchall()
            return {
                "since_seconds": since_seconds,
                "by_status": {r[0]: {"count": r[1], "tools": r[2] or 0,
                                     "blocks": r[3] or 0} for r in rows},
            }
        except Exception:
            return {"since_seconds": since_seconds, "by_status": {}}


# ──────────────────────────────────────────────────────────────────────────────
# 8. MODEL COST OVERLAY
#    OpenClaw pattern: openclaw.json.models.providers — cost per token per model
#    SkynetClaw use:   Multi-Model Router can pick cheapest in @auto/AMBIENT mode
# ──────────────────────────────────────────────────────────────────────────────
COST_OVERLAY_PATH = _BASE / "model_costs.json"

# Default cost data (USD per 1M tokens — input / output) for common models.
# User can edit model_costs.json to override or extend.
DEFAULT_MODEL_COSTS = {
    # Local Ollama models — effectively zero cost
    "nemotron3:33b":             {"input": 0.0,  "output": 0.0,  "ctx": 131072, "local": True},
    "Genesis-Mind:latest":       {"input": 0.0,  "output": 0.0,  "ctx": 16384,  "local": True},
    "ElmatadorZ-AI:latest":      {"input": 0.0,  "output": 0.0,  "ctx": 16384,  "local": True},
    "Alternative-LLM:latest":    {"input": 0.0,  "output": 0.0,  "ctx": 16384,  "local": True},
    "SkynetClaw:latest":         {"input": 0.0,  "output": 0.0,  "ctx": 16384,  "local": True},
    "Skynet-Agent:latest":       {"input": 0.0,  "output": 0.0,  "ctx": 16384,  "local": True},
    "gemma4:26b":                {"input": 0.0,  "output": 0.0,  "ctx": 8192,   "local": True},
    "qwen3.5:9b":                {"input": 0.0,  "output": 0.0,  "ctx": 32768,  "local": True},
    # Together.ai — example cloud rates (sample, user can edit)
    "moonshotai/Kimi-K2.5":                       {"input": 0.5,  "output": 2.8,  "ctx": 262144, "local": False},
    "deepseek-ai/DeepSeek-V3.1":                  {"input": 0.6,  "output": 1.25, "ctx": 131072, "local": False},
    "deepseek-ai/DeepSeek-R1":                    {"input": 3.0,  "output": 7.0,  "ctx": 131072, "local": False},
    "meta-llama/Llama-3.3-70B-Instruct-Turbo":    {"input": 0.88, "output": 0.88, "ctx": 131072, "local": False},
    "meta-llama/Llama-4-Scout-17B-16E-Instruct":  {"input": 0.18, "output": 0.59, "ctx": 10000000, "local": False},
    "zai-org/GLM-4.7":                            {"input": 0.45, "output": 2.0,  "ctx": 202752, "local": False},
}


class ModelCostOverlay:
    """Read/write cost data for models. Used by Router to pick cheapest."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or COST_OVERLAY_PATH
        self._data = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            try:
                self.path.write_text(
                    json.dumps(DEFAULT_MODEL_COSTS, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return dict(DEFAULT_MODEL_COSTS)
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return dict(DEFAULT_MODEL_COSTS)

    def cost(self, model: str) -> Dict[str, Any]:
        """Get cost record for a model. Falls back to {input:0, output:0, local:True}."""
        return self._data.get(model, {"input": 0.0, "output": 0.0, "local": True})

    def is_local(self, model: str) -> bool:
        return bool(self.cost(model).get("local", False))

    def cheapest(self, candidates: List[str], prefer_local: bool = True) -> Optional[str]:
        """Pick the cheapest model from a candidate list. Local zero-cost wins."""
        if not candidates:
            return None
        scored: List[Tuple[float, bool, str]] = []
        for m in candidates:
            c = self.cost(m)
            avg = (float(c.get("input", 0)) + float(c.get("output", 0))) / 2.0
            local = bool(c.get("local", False))
            # Local with zero cost gets priority when prefer_local=True
            score = avg if not (prefer_local and local) else -1.0
            scored.append((score, local, m))
        scored.sort(key=lambda x: (x[0], 0 if x[1] else 1, x[2]))
        return scored[0][2] if scored else None

    def update(self, model: str, **fields) -> Dict[str, Any]:
        """Set/merge cost fields for a model. Persists to disk."""
        self._data.setdefault(model, {})
        self._data[model].update({k: v for k, v in fields.items() if v is not None})
        try:
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[model_costs.update] {e}")
        return self._data[model]

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._data)


# ──────────────────────────────────────────────────────────────────────────────
# Self-test  —  python openclaw_port_tier2.py
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, tempfile, os
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== openclaw_port_tier2 self-test ===\n")

    # 6. Settings backup chain
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "settings.json"
        chain = SettingsBackupChain(sp)
        chain.safe_save({"vault_path": "D:\\v1", "n": 1})
        chain.safe_save({"vault_path": "D:\\v2", "n": 2})
        chain.safe_save({"vault_path": "D:\\v3", "n": 3})
        chain.safe_save({"vault_path": "D:\\v4", "n": 4})
        files = sorted(p.name for p in Path(tmp).iterdir())
        print(f"[6] backup chain files after 4 saves: {files}")
        # Corrupt primary, ensure load recovers
        sp.write_text("{this is not json", encoding="utf-8")
        recovered = chain.safe_load(default={"vault_path": "(none)"})
        print(f"    recovered after corruption: n={recovered.get('n')} vault={recovered.get('vault_path')}")
        assert recovered.get("n") == 4, "should have recovered from .last-good or .bak"

    # 7. AgentRunsDB
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        db = AgentRunsDB(db_path)
        db.start_run("run_001", "test task", model="nemotron3:33b",
                     trajectory_path="/tmp/traj.jsonl")
        db.start_run("run_002", "another task", model="qwen3.5:9b")
        db.end_run("run_001", "TASK_COMPLETE", n_steps=5, n_tools=8, n_blocks=1,
                   summary="finished cleanly")
        db.end_run("run_002", "stuck", n_steps=3, n_tools=4, n_blocks=2)
        recent = db.recent(limit=10)
        print(f"[7] agent_runs after 2 inserts + 2 ends: {len(recent)} rows")
        for r in recent:
            print(f"    {r['id']}: status={r['status']} steps={r['n_steps']} tools={r['n_tools']} blocks={r['n_blocks']}")
        s = db.stats(since_seconds=3600)
        print(f"    stats(1h): {s}")

    # 8. ModelCostOverlay
    with tempfile.TemporaryDirectory() as tmp:
        overlay = ModelCostOverlay(path=Path(tmp) / "costs.json")
        cands = ["nemotron3:33b", "deepseek-ai/DeepSeek-R1",
                 "moonshotai/Kimi-K2.5", "qwen3.5:9b"]
        cheapest_local = overlay.cheapest(cands, prefer_local=True)
        cheapest_strict = overlay.cheapest(cands, prefer_local=False)
        print(f"[8] cheapest (prefer_local):  {cheapest_local}")
        print(f"    cheapest (strict cost):   {cheapest_strict}")
        # Custom model update
        overlay.update("custom-model:7b", input=0.0, output=0.0, local=True, ctx=4096)
        print(f"    after update — list size: {len(overlay.list_all())}")

    print("\n=== self-test OK ===")
