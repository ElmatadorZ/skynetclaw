"""
deliberation_archive.py — PART 2: Deliberation Archive
======================================================
Every council run is archived to SQLite AND Obsidian. The Obsidian note lives at
    Council Archive/YYYY/MM/YYYY-MM-DD-<session>.md
so the House's reasoning is browsable as a knowledge base.

Record: date · question · agents · reasoning_summary · final_verdict ·
        confidence · predicted_outcome

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import institutional_db as _db

# Obsidian writer is optional — degrade gracefully when the vault is unavailable
try:
    from obsidian_tools import obsidian_write_note as _obs_write, get_vault as _get_vault
    _OBS = True
except Exception:
    _OBS = False
    def _obs_write(rel_path: str, content: str, **k): return {"ok": False, "error": "obsidian unavailable"}
    def _get_vault(): return None


def _fmt_note(rec: Dict[str, Any]) -> str:
    agents = rec.get("agents") or []
    fm = [
        "---",
        f"date: {rec['date']}",
        f"session: {rec.get('session_id','')}",
        f"verdict_confidence: {rec.get('confidence',0)}",
        "type: council-deliberation",
        f"agents: [{', '.join(agents)}]",
        "tags: [house, council-archive]",
        "---",
        "",
        f"# Council Deliberation — {rec['date']}",
        "",
        f"## Question\n{rec.get('question','')}",
        "",
        f"## Participants\n{', '.join(agents) or '(none)'}",
        "",
        f"## Reasoning Summary\n{rec.get('reasoning_summary','')}",
        "",
        f"## Final Verdict\n{rec.get('final_verdict','')}",
        "",
        f"## Confidence\n{rec.get('confidence',0)}",
        "",
        f"## Predicted Outcome\n{rec.get('predicted_outcome','') or '(none stated)'}",
        "",
        "## Links",
        "[[Council Archive MOC]] — up to the index of all deliberations.",
    ]
    return "\n".join(fm)


def archive(question: str, agents: List[str], reasoning_summary: str,
            final_verdict: str, confidence: float = 0.0,
            predicted_outcome: str = "", session_id: str = "",
            ts: Optional[float] = None, path: Optional[str] = None,
            obsidian_writer: Optional[Callable] = None) -> Dict[str, Any]:
    """Persist one deliberation to SQLite + Obsidian. Returns the archive record."""
    _db.ensure_schema(path)
    ts = ts if ts is not None else time.time()
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    date_s = dt.strftime("%Y-%m-%d")
    aid = "ar_" + hashlib.sha1(f"{question[:80]}:{ts}".encode()).hexdigest()[:12]
    rel_path = f"Council Archive/{dt.strftime('%Y')}/{dt.strftime('%m')}/{date_s}-{aid}.md"

    rec = {
        "id": aid, "session_id": session_id or None, "date": date_s,
        "question": question, "agents": agents,
        "reasoning_summary": reasoning_summary, "final_verdict": final_verdict,
        "confidence": float(confidence), "predicted_outcome": predicted_outcome,
        "obsidian_path": rel_path,
    }

    # Obsidian (best-effort). A custom `path` means a NON-production database
    # (tests, sandboxes) — those must not write into the real second brain:
    # one pytest run was found to have deposited 39 fake deliberations
    # ("Q?", session None) into the production vault. Export to Obsidian only
    # on the default DB, or when the caller explicitly supplies a writer.
    obs_ok = False
    if path is None or obsidian_writer is not None:
        writer = obsidian_writer or _obs_write
        try:
            res = writer(rel_path, _fmt_note(rec))
            obs_ok = bool(res and res.get("ok"))
        except Exception:
            obs_ok = False

    with _db.connect(path) as c:
        c.execute(
            "INSERT OR REPLACE INTO deliberation_archive "
            "(id, session_id, date, question, agents, reasoning_summary, "
            " final_verdict, confidence, predicted_outcome, obsidian_path, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (aid, rec["session_id"], date_s, question,
             json.dumps(agents, ensure_ascii=False), reasoning_summary,
             final_verdict, float(confidence), predicted_outcome,
             rec["obsidian_path"], time.time()))
        c.commit()
    rec["obsidian_written"] = obs_ok
    return rec


def get_archive(aid: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    _db.ensure_schema(path)
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM deliberation_archive WHERE id=?", (aid,)).fetchone()
        if not r:
            return None
        d = dict(r); d["agents"] = json.loads(d.get("agents") or "[]")
        return d


def recent(limit: int = 20, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.ensure_schema(path)
    with _db.connect(path) as c:
        rows = c.execute("SELECT * FROM deliberation_archive ORDER BY date DESC, "
                         "created_at DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r); d["agents"] = json.loads(d.get("agents") or "[]"); out.append(d)
        return out


def by_month(year: str, month: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.ensure_schema(path)
    like = f"{year}-{month}-%"
    with _db.connect(path) as c:
        rows = c.execute("SELECT * FROM deliberation_archive WHERE date LIKE ? "
                         "ORDER BY date DESC", (like,)).fetchall()
        return [dict(r) for r in rows]
