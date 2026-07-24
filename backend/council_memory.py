"""
council_memory.py — PART 1: Council Memory Engine for THE HOUSE
==============================================================
Persists every council session so THE HOUSE remembers what it decided, who
argued, how confident it was, what evidence it held, and who dissented.

CouncilSession:
    id · timestamp · directive · participants · verdict · confidence ·
    evidence_summary · dissent_summary

Also stores per-agent contributions (feeding agent_reputation) and exposes
the Historical Recall Layer (PART 6 of the mission): recall(directive) finds
prior sessions on a similar question so the House can compare against itself.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import institutional_db as _db
import agent_reputation as _rep
import recall_quality as _rq


@dataclass
class CouncilSession:
    directive: str
    participants: List[str] = field(default_factory=list)
    verdict: str = ""
    confidence: float = 0.0
    evidence_summary: str = ""
    dissent_summary: str = ""
    model: str = ""
    id: str = ""
    ts: float = 0.0

    def __post_init__(self):
        if not self.ts:
            self.ts = time.time()
        if not self.id:
            self.id = "cs_" + hashlib.sha1(
                f"{self.directive[:80]}:{self.ts}".encode("utf-8", "ignore")
            ).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────────
# Save
# ──────────────────────────────────────────────────────────────────────────────
def save_session(session: CouncilSession,
                 contributions: Optional[List[Dict[str, Any]]] = None,
                 path: Optional[str] = None,
                 verdict_json: Optional[Dict[str, Any]] = None) -> str:
    """Persist a session (+ optional per-agent contributions). Returns session id.

    verdict_json: the FULL verdict dict. Summary-only storage made predictions
    unrecoverable after the fact — the falsifiable payload must survive."""
    _db.init_once(path)
    now = time.time()
    with _db.connect(path) as c:
        c.execute(
            "INSERT OR REPLACE INTO council_sessions "
            "(id, ts, directive, participants, verdict, confidence, "
            " evidence_summary, dissent_summary, model, created_at, verdict_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (session.id, session.ts, session.directive,
             json.dumps(session.participants, ensure_ascii=False),
             session.verdict, float(session.confidence),
             session.evidence_summary, session.dissent_summary,
             session.model, now,
             json.dumps(verdict_json or {}, ensure_ascii=False)[:60000]))
        for con in (contributions or []):
            cid = "cc_" + hashlib.sha1(
                f"{session.id}:{con.get('agent','')}:{now}".encode()).hexdigest()[:12]
            c.execute(
                "INSERT OR REPLACE INTO council_contributions "
                "(id, session_id, agent, role, stance, confidence, "
                " evidence_quality, critique_quality, forecast_quality, note, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (cid, session.id, con.get("agent", ""), con.get("role", ""),
                 con.get("stance", "neutral"), float(con.get("confidence", 0.0)),
                 float(con.get("evidence_quality", 0.0)),
                 float(con.get("critique_quality", 0.0)),
                 float(con.get("forecast_quality", 0.0)),
                 str(con.get("note", ""))[:1000], now))
        c.commit()
    # fold contribution quality into reputation (immediate signal)
    for con in (contributions or []):
        if con.get("agent"):
            _rep.record_contribution(
                con["agent"], float(con.get("evidence_quality", 0.0)),
                float(con.get("critique_quality", 0.0)),
                float(con.get("forecast_quality", 0.0)), path=path)
    return session.id


# ──────────────────────────────────────────────────────────────────────────────
# Build a session straight from an agent_council CouncilVerdict-style dict
# ──────────────────────────────────────────────────────────────────────────────
_ROLE_TO_AGENT = {
    "analyst": "Analyst", "strategist": "Strategist", "skeptic": "Skeptic",
    "forecaster": "Forecaster", "executor": "Executor", "storyteller": "Storyteller",
}


def from_verdict(directive: str, verdict: Dict[str, Any], model: str = "",
                 path: Optional[str] = None) -> str:
    """Turn an L5 council verdict dict into a persisted CouncilSession.

    Scores each role's contribution quality and detects dissent (Skeptic
    REBUILD/BLOCKED stance is preserved as a minority opinion — Constitution R5).
    """
    participants: List[str] = []
    contributions: List[Dict[str, Any]] = []
    evidence_bits: List[str] = []
    dissent_bits: List[str] = []

    for role, agent in _ROLE_TO_AGENT.items():
        block = verdict.get(role)
        if not isinstance(block, dict):
            continue
        participants.append(agent)
        text = json.dumps(block, ensure_ascii=False)
        # structure-first (language-bias fix): a member that declares the
        # structure has done the epistemic work in any language
        ev = _rep.score_evidence_block(block)
        cr = _rep.score_critique_block(block)
        fc = _rep.score_forecast_block(block)
        stance = "neutral"
        vlabel = str(block.get("verdict", "")).upper()
        if role == "skeptic" and (vlabel in ("REBUILD", "BLOCKED", "VETO")
                                  or block.get("dissent") is True):
            stance = "dissent"
            dissent_bits.append(f"Skeptic: {block.get('verdict','') or 'DISSENT'} — "
                                f"{str(block.get('fatal_assumption') or block.get('reason') or block)[:160]}")
        if role == "analyst":
            for k in ("known", "data_gaps", "unknown"):
                if block.get(k):
                    evidence_bits.append(f"{k}: {block[k]}")
        contributions.append({
            "agent": agent, "role": role, "stance": stance,
            "confidence": float(block.get("confidence", 0.0)) if isinstance(block.get("confidence"), (int, float)) else 0.0,
            "evidence_quality": ev, "critique_quality": cr, "forecast_quality": fc,
            "note": text[:800],
        })

    agg = verdict.get("aggregate_recommendation") or verdict.get("verdict") or ""
    conf = _aggregate_confidence(contributions)
    session = CouncilSession(
        directive=directive, participants=participants, verdict=str(agg)[:2000],
        confidence=conf,
        evidence_summary=" | ".join(str(e) for e in evidence_bits)[:2000],
        dissent_summary=" | ".join(dissent_bits)[:2000] or "(unanimous — no dissent recorded)",
        model=model,
    )
    return save_session(session, contributions, path=path, verdict_json=verdict)


def _aggregate_confidence(contributions: List[Dict[str, Any]]) -> float:
    if not contributions:
        return 0.0
    qual = sum((c["evidence_quality"] + c["critique_quality"] + c["forecast_quality"]) / 3
               for c in contributions) / len(contributions)
    return round(qual, 4)


# ──────────────────────────────────────────────────────────────────────────────
# Read / Historical Recall Layer
# ──────────────────────────────────────────────────────────────────────────────
def get_session(session_id: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM council_sessions WHERE id=?", (session_id,)).fetchone()
        if not r:
            return None
        out = dict(r)
        out["participants"] = json.loads(out.get("participants") or "[]")
        try:
            out["verdict_json"] = json.loads(out.get("verdict_json") or "{}")
        except Exception:
            out["verdict_json"] = {}
        out["contributions"] = [dict(x) for x in c.execute(
            "SELECT * FROM council_contributions WHERE session_id=?", (session_id,)).fetchall()]
        return out


def recent(limit: int = 20, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        rows = c.execute("SELECT * FROM council_sessions ORDER BY ts DESC LIMIT ?",
                         (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["participants"] = json.loads(d.get("participants") or "[]")
            try:
                d["verdict_json"] = json.loads(d.get("verdict_json") or "{}")
            except Exception:
                d["verdict_json"] = {}
            out.append(d)
        return out


_WORD = re.compile(r"[\w฀-๿]+")


def _tokens(s: str) -> set:
    return {t.lower() for t in _WORD.findall(s or "") if len(t) > 2}


# Recall scans a bounded recent window (retrieval). Scoring/validity/ranking are
# delegated to recall_quality so every recalled memory is JUSTIFIED. NOTE (audit H2):
# at very large scale this window must become an FTS5/vector index — scheduled debt.
_RECALL_SCAN = 1000


def recall(directive: str, limit: int = 5, path: Optional[str] = None,
           now: Optional[float] = None) -> List[Dict[str, Any]]:
    """VALIDITY-AWARE HISTORICAL RECALL (M2 Recall Quality Layer).

    Retrieval lives here (bounded token match); the Recall Quality Layer attaches
    similarity · accuracy · calibration · outcome_status · validity and produces a
    JUSTIFIED ranking. Untrustworthy memories (DISPROVEN / OUTDATED / PARTIALLY_VALID)
    always carry a warning and never outrank validated precedent.
    """
    _db.init_once(path)
    want = _tokens(directive)
    if not want:
        return []
    cand: List[Dict[str, Any]] = []
    with _db.connect(path) as c:
        for r in c.execute("SELECT * FROM council_sessions ORDER BY ts DESC LIMIT ?",
                           (_RECALL_SCAN,)).fetchall():
            have = _tokens(r["directive"])
            if not (want & have):
                continue
            d = dict(r)
            d["participants"] = json.loads(d.get("participants") or "[]")
            cand.append(d)
    return _rq.annotate(cand, directive, now=now, path=path, limit=limit)


def stats(path: Optional[str] = None) -> Dict[str, Any]:
    _db.init_once(path)
    with _db.connect(path) as c:
        n = c.execute("SELECT COUNT(*) n FROM council_sessions").fetchone()["n"]
        avg = c.execute("SELECT AVG(confidence) a FROM council_sessions").fetchone()["a"]
        dissent = c.execute("SELECT COUNT(*) n FROM council_sessions "
                            "WHERE dissent_summary NOT LIKE '%unanimous%'").fetchone()["n"]
        return {"sessions": n, "avg_confidence": round(avg or 0.0, 4),
                "sessions_with_dissent": dissent}


if __name__ == "__main__":
    import os, tempfile, sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    os.environ["INSTITUTIONAL_DB"] = tempfile.mktemp(suffix=".db")
    sid = from_verdict("Should the House go risk-on into Q3?", {
        "analyst": {"known": ["BTC 64000"], "data_gaps": ["Fed dot plot"]},
        "skeptic": {"verdict": "REBUILD", "reason": "liquidity thin, risk high"},
        "forecaster": {"scenario": "bull if cuts; invalidation below 58k"},
        "aggregate_recommendation": "Phase in, hedge tail risk.",
    }, model="test")
    print("saved:", sid)
    print("recall:", [s["id"] for s in recall("risk-on Q3 House")])
    print("stats:", stats())
