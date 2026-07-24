"""
governance_engine.py — M3: the Governance Engine for THE HOUSE
==============================================================
The Constitution must not advise. It must GOVERN.

This engine turns the seven House rules into enforced law. Every council session
is required to produce five records, is checked against the rules, and receives a
binding decision (PASS / FLAGGED / REJECTED). Dissent is captured as a first-class
artifact and tracked over time, so the House learns when a minority was right.

Required records (every session):
  majority_position · minority_positions · evidence_record ·
  confidence_record · uncertainty_record

Enforcement:
  forecast without invalidation  → REJECT  (R4)
  claim without evidence         → REJECT  (R1/R7)
  minority opinion omitted       → REJECT  (R5)
  uncertainty not stated         → FLAG    (R3)
  (rules may be explicitly WAIVED with a recorded reason)

Minority tracking: who disagreed, why, and — once outcomes land — whether they
were proven correct. A vindicated dissenter is rewarded; a dissenter who turned
out wrong is NEVER punished (the House does not suppress minority viewpoints).

Governance record per session → constitution_audits (+ minority_positions).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional

import institutional_db as _db
import house_constitution as _con
import agent_reputation as _rep

# decision outcomes
PASS = "PASS"
FLAGGED = "FLAGGED"
REJECTED = "REJECTED"

# severity of a rule violation
REJECT = "reject"
FLAG = "flag"

_ROLE_AGENT = {
    "analyst": "Analyst", "strategist": "Strategist", "skeptic": "Skeptic",
    "forecaster": "Forecaster", "executor": "Executor", "storyteller": "Storyteller",
    "atlas": "Atlas",
}
_DISSENT_VERDICTS = {"REBUILD", "BLOCKED", "VETO", "FRAGILE", "DISAGREE"}

_INVAL_RE = re.compile(r"(invalidat\w*|falsif\w*|breaks? if|fails? if|wrong if|"
                       r"stop[- ]?loss|below\s+[\d.,]+|above\s+[\d.,]+|unless\b|early[_ ]warning)", re.I)
_SRC_RE = re.compile(r"https?://|\[\d+\]|\bsource\b|\bper\b|\baccording\b|\bdata\b|\bcit", re.I)
_DISAGREE_RE = re.compile(r"\b(disagree|dissent|object|minority|oppos|against the)\b", re.I)
_FORWARD_RE = re.compile(r"\b(will|expect|forecast|scenario|project|outlook|target|into\b|by\s+\d)\b", re.I)
_VINDICATION_WEIGHT = 0.5


def _txt(block: Any) -> str:
    return json.dumps(block, ensure_ascii=False) if isinstance(block, dict) else str(block or "")


def _gist(s: str, n: int = 160) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().strip('"{}'))[:n]


# ══════════════════════════════════════════════════════════════════════════════
# 1) Extract the five required records from a council verdict
# ══════════════════════════════════════════════════════════════════════════════
def extract_records(verdict: Dict[str, Any]) -> Dict[str, Any]:
    majority = str(verdict.get("aggregate_recommendation") or verdict.get("verdict") or "").strip()

    minority: List[Dict[str, str]] = []
    skeptic = verdict.get("skeptic") or {}
    sk_verdict = str(skeptic.get("verdict", "")).upper()
    if sk_verdict in _DISSENT_VERDICTS or skeptic.get("dissent") is True:
        minority.append({
            "agent": "Skeptic", "position": sk_verdict or "DISSENT",
            "reason": _gist(skeptic.get("rebuild_trigger") or skeptic.get("fatal_assumption")
                            or skeptic.get("reason") or skeptic),
        })
    # any other role explicitly dissenting
    for role, block in verdict.items():
        if role in ("skeptic", "aggregate_recommendation"):
            continue
        if isinstance(block, dict) and _DISAGREE_RE.search(_txt(block)):
            minority.append({"agent": _ROLE_AGENT.get(role, role.title()),
                             "position": "dissent", "reason": _gist(block)})

    evidence: List[str] = []
    analyst = verdict.get("analyst") or {}
    for k in ("known", "inferred"):
        v = analyst.get(k)
        if v:
            evidence.extend([_gist(x, 120) for x in (v if isinstance(v, list) else [v])])
    for role, block in verdict.items():
        if isinstance(block, dict) and _SRC_RE.search(_txt(block)):
            evidence.append(f"{_ROLE_AGENT.get(role, role)}: cited source/data")

    confidence: Dict[str, Any] = {}
    for role, block in verdict.items():
        if isinstance(block, dict) and isinstance(block.get("confidence"), (int, float)):
            confidence[_ROLE_AGENT.get(role, role)] = block["confidence"]

    uncertainty: List[str] = []
    for k in ("unknown", "data_gaps"):
        v = analyst.get(k)
        if v:
            uncertainty.extend([_gist(x, 120) for x in (v if isinstance(v, list) else [v])])
    forecaster = verdict.get("forecaster") or {}
    for k in ("early_warning_1", "early_warning_2"):
        if forecaster.get(k):
            uncertainty.append(_gist(forecaster[k], 120))
    if _con._PAT["R3"].search(_txt(verdict)):  # any uncertainty language anywhere
        pass

    return {
        "majority_position": majority,
        "minority_positions": minority,
        "evidence_record": evidence,
        "confidence_record": confidence,
        "uncertainty_record": uncertainty,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2) Enforce the Constitution → violations + binding decision
# ══════════════════════════════════════════════════════════════════════════════
def enforce(verdict: Dict[str, Any], records: Optional[Dict[str, Any]] = None,
            waivers: Optional[List[str]] = None) -> Dict[str, Any]:
    records = records or extract_records(verdict)
    waivers = [w.upper() for w in (waivers or [])]
    violations: List[Dict[str, str]] = []

    forecaster = verdict.get("forecaster") or {}
    ftext = _txt(forecaster)
    full = _txt(verdict)

    # R4 — forecasts require an invalidation condition. STRUCTURE FIRST: a
    # declared prediction.invalidation or early_warning field satisfies R4 in
    # any language; the regex is an English-only fallback that false-rejected
    # every Thai deliberation.
    is_forecast = bool(forecaster) and bool(_FORWARD_RE.search(ftext) or forecaster.get("scenario")
                                            or forecaster.get("base_case"))
    _pred = forecaster.get("prediction") if isinstance(forecaster.get("prediction"), dict) else {}
    has_invalidation = bool(
        str(_pred.get("invalidation") or "").strip()
        or str(forecaster.get("early_warning_1") or "").strip()
        or str(forecaster.get("early_warning_2") or "").strip()
        or _INVAL_RE.search(ftext) or _INVAL_RE.search(full))
    if is_forecast and not has_invalidation:
        violations.append({"rule": "R4", "severity": REJECT,
                           "reason": "forecast present with no invalidation/falsification condition"})

    # R1 / R7 — claims require evidence / source traceability
    if records["majority_position"] and not records["evidence_record"]:
        violations.append({"rule": "R1", "severity": REJECT,
                           "reason": "a position was reached with no evidence on record"})

    # R5 — minority opinions must be preserved when dissent exists
    # STRUCTURE FIRST: an explicit skeptic `dissent` bool is a declaration —
    # the regex is a fallback for verdicts that never declared, and must not
    # fire on the field name itself ("dissent": false is NOT dissent).
    _sk = verdict.get("skeptic") or {}
    if isinstance(_sk.get("dissent"), bool):
        dissent_detected = (_sk.get("dissent") is True
                            or str(_sk.get("verdict", "")).upper() in _DISSENT_VERDICTS)
    else:
        dissent_detected = (str(_sk.get("verdict", "")).upper() in _DISSENT_VERDICTS
                            or bool(_DISAGREE_RE.search(full)))
    if dissent_detected and not records["minority_positions"]:
        violations.append({"rule": "R5", "severity": REJECT,
                           "reason": "dissent was present but no minority position was recorded"})

    # R3 — uncertainty must be stated (flag, not reject)
    if not records["uncertainty_record"] and not _con._PAT["R3"].search(full):
        violations.append({"rule": "R3", "severity": FLAG,
                           "reason": "no uncertainty/unknowns stated"})

    # apply waivers
    waived = [v for v in violations if v["rule"] in waivers]
    active = [v for v in violations if v["rule"] not in waivers]

    rejects = [v for v in active if v["severity"] == REJECT]
    flags = [v for v in active if v["severity"] == FLAG]
    decision = REJECTED if rejects else (FLAGGED if flags else PASS)

    # governance score: fraction of the 7 rules not actively violated
    violated_rules = {v["rule"] for v in active}
    score = round((len(_con.RULES) - len(violated_rules)) / len(_con.RULES), 3)

    return {
        "decision": decision,
        "violations": active,
        "waivers": [{"rule": v["rule"], "severity": v["severity"], "reason": v["reason"]} for v in waived],
        "governance_score": score,
        "rejects": rejects,
        "flags": flags,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3) Govern a session: persist the governance record + minority positions
# ══════════════════════════════════════════════════════════════════════════════
def govern(session_id: str, verdict: Dict[str, Any], waivers: Optional[List[str]] = None,
           ts: Optional[float] = None, path: Optional[str] = None) -> Dict[str, Any]:
    _db.init_once(path)
    ts = ts if ts is not None else time.time()
    records = extract_records(verdict)
    enf = enforce(verdict, records, waivers)
    aid = "ga_" + hashlib.sha1(f"{session_id}:{ts}".encode()).hexdigest()[:12]
    record = {"id": aid, "session_id": session_id, "ts": ts, **records, **enf}

    with _db.connect(path) as c:
        c.execute(
            "INSERT OR REPLACE INTO constitution_audits "
            "(id, session_id, ts, score, violations, blocked, waivers, decision, "
            " n_minority, governance_score, record_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (aid, (session_id or None), ts, enf["governance_score"],
             json.dumps(enf["violations"], ensure_ascii=False),
             1 if enf["decision"] == REJECTED else 0,
             json.dumps(enf["waivers"], ensure_ascii=False), enf["decision"],
             len(records["minority_positions"]), enf["governance_score"],
             json.dumps(record, ensure_ascii=False)[:8000]))
        c.commit()

    for m in records["minority_positions"]:
        record_minority(session_id, m["agent"], m.get("position", ""), m.get("reason", ""),
                        ts=ts, path=path)
    return record


# ══════════════════════════════════════════════════════════════════════════════
# 4) Minority tracking
# ══════════════════════════════════════════════════════════════════════════════
def record_minority(session_id: str, agent: str, position: str, reason: str,
                    stance: str = "dissent", ts: Optional[float] = None,
                    path: Optional[str] = None) -> str:
    _db.init_once(path)
    ts = ts if ts is not None else time.time()
    mid = "mp_" + hashlib.sha1(f"{session_id}:{agent}:{ts}".encode()).hexdigest()[:12]
    with _db.connect(path) as c:
        c.execute(
            "INSERT OR REPLACE INTO minority_positions "
            "(id, session_id, agent, position, reason, stance, ts, resolved, proven_correct, "
            " resolved_at, vindication_applied) VALUES (?,?,?,?,?,?,?,0,NULL,0.0,0)",
            (mid, (session_id or None), agent, position[:300], reason[:500], stance, ts))
        c.commit()
    return mid


def _session_accuracy(c, session_id: str) -> Optional[float]:
    rows = c.execute("SELECT status FROM predictions WHERE session_id=? AND status!='pending'",
                     (session_id,)).fetchall()
    vals = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
    s = [vals[r["status"]] for r in rows if r["status"] in vals]
    return (sum(s) / len(s)) if s else None


def on_outcome(session_id: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Called when a session's predictions are graded. Resolves that session's
    minorities: if the MAJORITY proved wrong, the dissenters were RIGHT — mark them
    proven_correct and reward them. A dissenter who turned out wrong is NOT punished."""
    _db.init_once(path)
    with _db.connect(path) as c:
        pending = c.execute("SELECT COUNT(*) n FROM predictions WHERE session_id=? AND status='pending'",
                            (session_id,)).fetchone()["n"]
        if pending:
            return {"session": session_id, "resolved": 0, "reason": "session not fully graded yet"}
        acc = _session_accuracy(c, session_id)
        if acc is None:
            return {"session": session_id, "resolved": 0, "reason": "no graded outcomes yet"}
        majority_correct = acc >= _rq_ACC_VALID()
        mins = [dict(r) for r in c.execute(
            "SELECT * FROM minority_positions WHERE session_id=? AND resolved=0", (session_id,)).fetchall()]
    vindicated = []
    now = time.time()
    for m in mins:
        proven_correct = 0 if majority_correct else 1   # majority wrong ⇒ dissent right
        with _db.connect(path) as c:
            c.execute("UPDATE minority_positions SET resolved=1, proven_correct=?, resolved_at=? "
                      "WHERE id=?", (proven_correct, now, m["id"]))
            c.commit()
        if proven_correct and not m["vindication_applied"]:
            # reward the agent who correctly dissented; never punish a wrong dissent
            try:
                _rep.apply_outcome(m["agent"], "correct", confidence=0.0,
                                   weight=_VINDICATION_WEIGHT, path=path)
            except Exception:
                pass
            with _db.connect(path) as c:
                c.execute("UPDATE minority_positions SET vindication_applied=1 WHERE id=?", (m["id"],))
                c.commit()
            vindicated.append(m["agent"])
    return {"session": session_id, "resolved": len(mins), "majority_correct": majority_correct,
            "vindicated": vindicated, "session_accuracy": round(acc, 3)}


def _rq_ACC_VALID() -> float:
    try:
        import recall_quality as _rq
        return _rq.ACC_VALID
    except Exception:
        return 0.6


# ══════════════════════════════════════════════════════════════════════════════
# 5) Read the governance record / minority scoreboard
# ══════════════════════════════════════════════════════════════════════════════
def governance_record(session_id: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM constitution_audits WHERE session_id=? ORDER BY ts DESC LIMIT 1",
                      (session_id,)).fetchone()
        if not r:
            return None
        out = dict(r)
        for k in ("violations", "waivers", "record_json"):
            try: out[k] = json.loads(out.get(k) or ("[]" if k != "record_json" else "{}"))
            except Exception: pass
        out["minority_positions"] = [dict(x) for x in c.execute(
            "SELECT * FROM minority_positions WHERE session_id=? ORDER BY ts", (session_id,)).fetchall()]
        return out


def minorities(session_id: Optional[str] = None, only_vindicated: bool = False,
               limit: int = 100, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.init_once(path)
    where, args = [], []
    if session_id:
        where.append("session_id=?"); args.append(session_id)
    if only_vindicated:
        where.append("proven_correct=1")
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    with _db.connect(path) as c:
        return [dict(r) for r in c.execute(
            f"SELECT * FROM minority_positions{wsql} ORDER BY ts DESC LIMIT ?", (*args, limit))]


def minority_scoreboard(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Per-agent dissent record — how often a member's minority view was vindicated.
    This is how the House learns whose disagreement to weight."""
    _db.init_once(path)
    with _db.connect(path) as c:
        rows = c.execute(
            "SELECT agent, COUNT(*) n_dissents, "
            "SUM(CASE WHEN resolved=1 THEN 1 ELSE 0 END) n_resolved, "
            "SUM(CASE WHEN proven_correct=1 THEN 1 ELSE 0 END) n_vindicated "
            "FROM minority_positions GROUP BY agent").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["vindication_rate"] = round(d["n_vindicated"] / d["n_resolved"], 3) if d["n_resolved"] else None
        out.append(d)
    out.sort(key=lambda x: -(x["vindication_rate"] or 0))
    return out


def stats(path: Optional[str] = None) -> Dict[str, Any]:
    _db.init_once(path)
    with _db.connect(path) as c:
        by_decision = {r["decision"]: r["n"] for r in c.execute(
            "SELECT decision, COUNT(*) n FROM constitution_audits GROUP BY decision")}
        n_min = c.execute("SELECT COUNT(*) n FROM minority_positions").fetchone()["n"]
        n_vind = c.execute("SELECT COUNT(*) n FROM minority_positions WHERE proven_correct=1").fetchone()["n"]
        avg = c.execute("SELECT AVG(governance_score) a FROM constitution_audits").fetchone()["a"]
    return {"by_decision": by_decision, "minorities": n_min, "vindicated": n_vind,
            "avg_governance_score": round(avg or 0.0, 3)}


def format_governance_for_council(record: Dict[str, Any]) -> str:
    if not record:
        return ""
    L = [f"## GOVERNANCE — decision: {record.get('decision')}"]
    if record.get("violations"):
        L.append("Rule violations: " + "; ".join(
            f"{v['rule']} ({v['severity']}) {v['reason']}" for v in record["violations"]))
    if record.get("minority_positions"):
        L.append("Minority on record (preserved): " + "; ".join(
            f"{m['agent']}: {m.get('reason','')[:80]}" for m in record["minority_positions"]))
    return "\n".join(L)
