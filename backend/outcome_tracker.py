"""outcome_tracker.py — PART 5 / M1 / M1.5 / M3: Decision Outcome Tracking."""
from __future__ import annotations
import hashlib, json, time
from typing import Any, Dict, List, Optional
import institutional_db as _db
import agent_reputation as _rep
DAY = 86400.0
# "7" (v7): operational claims get their first reality check within a week —
# a learning loop that stays silent for 30 days teaches nothing this quarter.
HORIZONS = {"7": 7 * DAY, "30": 30 * DAY, "90": 90 * DAY, "180": 180 * DAY}
VALID_RESULTS = ("correct", "partial", "incorrect")
_PARTICIPANT_WEIGHT = 0.5


def record_prediction(statement: str, agent: str = "", session_id: str = "",
                      predicted_outcome: str = "", invalidation: str = "",
                      confidence: float = 0.0, made_at: Optional[float] = None,
                      extracted_from: str = "", horizon_primary: str = "",
                      metric: str = "", direction: str = "",
                      participants: Optional[List[str]] = None, evidence_source: str = "",
                      path: Optional[str] = None) -> str:
    _db.init_once(path)
    t0 = made_at if made_at is not None else time.time()
    pid = "pr_" + hashlib.sha1(f"{agent}:{statement[:80]}:{t0}".encode()).hexdigest()[:12]
    parts = json.dumps(participants if participants is not None else ([agent] if agent else []),
                       ensure_ascii=False)
    with _db.connect(path) as c:
        c.execute(
            "INSERT OR REPLACE INTO predictions "
            "(id, session_id, agent, statement, predicted_outcome, invalidation, "
            " confidence, made_at, due_7, due_30, due_90, due_180, status, "
            " extracted_from, horizon_primary, metric, direction, participants, evidence_source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?,?,?,?,?,?)",
            (pid, (session_id or None), agent, statement, predicted_outcome, invalidation,
             float(confidence), t0,
             t0 + HORIZONS["7"], t0 + HORIZONS["30"], t0 + HORIZONS["90"], t0 + HORIZONS["180"],
             extracted_from, horizon_primary, metric, direction, parts, evidence_source))
        c.commit()
    return pid


def has_pending(statement: str, agent: str = "",
                path: Optional[str] = None) -> bool:
    """True when an identical claim by the same agent is already on the clock.
    One claim = one grading — a re-deliberated mission must not double an
    agent's reputation stake on the same prediction (C1 attribution integrity)."""
    _db.init_once(path)
    with _db.connect(path) as c:
        r = c.execute(
            "SELECT 1 FROM predictions WHERE status='pending' AND agent=? "
            "AND statement=? LIMIT 1", (agent, statement)).fetchone()
        return r is not None


def get_prediction(pid: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM predictions WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None


def due_reviews(horizon: str, now: Optional[float] = None, limit: int = 500,
                offset: int = 0, path: Optional[str] = None) -> List[Dict[str, Any]]:
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {list(HORIZONS)}")
    _db.init_once(path)
    now = now if now is not None else time.time()
    col_due, col_rev = f"due_{horizon}", f"review_{horizon}"
    with _db.connect(path) as c:
        # {col_due} > 0: a zero due-date marks rows created before the column
        # existed — they must never become retroactively due
        rows = c.execute(
            f"SELECT * FROM predictions WHERE {col_due} > 0 AND {col_due} <= ? AND {col_rev}='' "
            f"ORDER BY {col_due} ASC LIMIT ? OFFSET ?", (now, limit, offset)).fetchall()
        return [dict(r) for r in rows]


def due_count(horizon: str, now: Optional[float] = None, path: Optional[str] = None) -> int:
    if horizon not in HORIZONS:
        raise ValueError(f"bad horizon {horizon}")
    _db.init_once(path)
    now = now if now is not None else time.time()
    col_due, col_rev = f"due_{horizon}", f"review_{horizon}"
    with _db.connect(path) as c:
        return c.execute(f"SELECT COUNT(*) n FROM predictions WHERE {col_due}>0 AND {col_due}<=? AND {col_rev}=''",
                         (now,)).fetchone()["n"]


def evaluate(pid: str, horizon: str, result: str,
             path: Optional[str] = None) -> Dict[str, Any]:
    if horizon not in HORIZONS:
        raise ValueError(f"bad horizon {horizon}")
    if result not in VALID_RESULTS:
        raise ValueError(f"result must be one of {VALID_RESULTS}")
    _db.init_once(path)
    col_rev = f"review_{horizon}"
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM predictions WHERE id=?", (pid,)).fetchone()
        if not r:
            raise KeyError(f"no prediction {pid}")
        c.execute(f"UPDATE predictions SET {col_rev}=?, status=?, evaluated_at=? WHERE id=?",
                  (result, result, time.time(), pid))
        c.commit()
        origin = r["agent"]
        conf = r["confidence"] or 0.0
        sid = r["session_id"]
        try:
            participants = json.loads(r["participants"] or "[]")
        except Exception:
            participants = []
    reps = {}
    targets = {origin: 1.0}
    for a in participants:
        if a and a != origin:
            targets[a] = _PARTICIPANT_WEIGHT
    for agent, weight in targets.items():
        if agent:
            reps[agent] = _rep.apply_outcome(agent, result, confidence=conf,
                                             weight=weight, path=path)
    # M3: resolve the session's minority positions once fully graded (best-effort)
    minority = None
    if sid:
        try:
            import governance_engine as _gov
            minority = _gov.on_outcome(sid, path=path)
        except Exception:
            minority = None
    # CLOSE THE LOOP: a graded outcome revises the House Mind's belief
    # (ผิด/ถูก → เรียนรู้ → เปลี่ยนความเชื่อ). Reality, not another verdict,
    # changes the House's mind. Best-effort — never breaks grading.
    # ADR-0016: a mission outcome revises belief WITHOUT borrowing a session's
    # identity. revise_from_outcome() locates the House State by DIRECTIVE TEXT, so
    # it never needed a session_id — but this block fetched the directive *through*
    # council_sessions, and a mission has no session row. The whole `if sid:` guard
    # was therefore a silent no-op for every mission: graded correct, Validated
    # Episode written, and the House learned nothing. That was Q2's finding in the
    # First Evidence Review.
    #
    # The prediction already carries what the revision needs. Prefer the session's
    # directive when there is one (it is the fuller text) and fall back to the
    # claim's own statement, which for a mission hypothesis embeds the directive.
    #
    # Note deliberately NOT changed: on_outcome() above stays session-gated. A
    # mission has no council deliberation and therefore no dissent to resolve —
    # skipping it there is correct, not a second instance of this bug.
    belief_change = None
    directive = ""
    if sid:
        try:
            with _db.connect(path) as c2:
                srow = c2.execute("SELECT directive FROM council_sessions WHERE id=?",
                                  (sid,)).fetchone()
            directive = (srow["directive"] if srow else "") or ""
        except Exception:
            directive = ""
    if not directive:
        # ADR-0016 · Single Canonical Identity. The stake recorded the key the House
        # Mind is filed under; use it, rather than resolving anything. `statement`
        # stays a display label and may be reworded without breaking learning.
        try:
            payload = json.loads((r["predicted_outcome"] or "{}") if r else "{}")
            directive = str(payload.get("mission_identity") or "")
        except Exception:
            directive = ""
    if not directive:
        # Predictions staked before ADR-0016 carry no identity field. The statement
        # is a poor key — it wraps and truncates — but it is what those rows have,
        # and a missing revision is better than a wrong one.
        directive = (r["statement"] or "") if r else ""
    if directive:
        try:
            import house_state as _hs
            belief_change = _hs.revise_from_outcome(directive, result,
                                                    horizon=horizon, path=path)
        except Exception:
            belief_change = None
    return {"prediction": pid, "horizon": horizon, "result": result,
            "attributed_to": list(targets), "reputation": reps, "minority": minority,
            "belief_change": belief_change}


def review_summary(path: Optional[str] = None) -> Dict[str, Any]:
    _db.init_once(path)
    with _db.connect(path) as c:
        total = c.execute("SELECT COUNT(*) n FROM predictions").fetchone()["n"]
        by_status = {row["status"]: row["n"] for row in c.execute(
            "SELECT status, COUNT(*) n FROM predictions GROUP BY status").fetchall()}
    pending = {h: due_count(h, path=path) for h in HORIZONS}
    return {"total": total, "by_status": by_status, "due_now": pending}


def recent_outcomes(limit: int = 20, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        rows = c.execute("SELECT * FROM predictions WHERE status!='pending' "
                         "ORDER BY evaluated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def all_due(now: Optional[float] = None, path: Optional[str] = None) -> Dict[str, int]:
    return {h: due_count(h, now=now, path=path) for h in HORIZONS}


_EVAL_BAR = 0.9   # the House's own quality bar (matches the eval scoreboard)


def auto_judge(pred: Dict[str, Any], eval_trend: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Grade a due prediction WITHOUT a human when its metric is one the House
    measures itself — the eval scoreboard is the judge. Narrow by design:
    only predictions whose declared metric names the eval score qualify;
    everything else stays human-judged. Returns correct/incorrect or None."""
    metric = str(pred.get("metric") or "").lower()
    # RFC-0001: mission hypotheses are evaluated against the FILESYSTEM + LEDGER
    # (observable reality), never any provider's account of itself. Delegated so
    # this module stays pipeline-only; an unverifiable hypothesis returns None
    # (left for a human — the judge abstains rather than guesses).
    if metric.startswith("mission"):
        try:
            import reality_grading as _rg
            return _rg.judge_mission_hypothesis(pred)
        except Exception:
            return None
    if "eval" not in metric:
        return None
    if eval_trend is None:
        try:
            import eval_suite as _ev
            eval_trend = _ev.trend()
        except Exception:
            return None
    latest = (eval_trend or {}).get("latest")
    if not isinstance(latest, (int, float)):
        return None
    holding = latest >= _EVAL_BAR
    direction = str(pred.get("direction") or "").lower()
    if direction in ("flat", "up"):
        return "correct" if holding else "incorrect"
    if direction == "down":
        return "incorrect" if holding else "correct"
    return None


def outcome_clock_handler(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    counts = all_due()
    # AUTO-JUDGE (v7): self-measurable claims are graded by the scoreboard the
    # moment they come due — reputation moves in days, not quarters.
    judged = 0
    for h in HORIZONS:
        for pred in due_reviews(h, limit=50):
            verdict = auto_judge(pred)
            if verdict:
                try:
                    evaluate(pred["id"], h, verdict)
                    judged += 1
                    print(f"[OutcomeClock] auto-judged {pred['id']} @{h}d → {verdict} "
                          f"(metric={pred.get('metric','')[:40]}, judge=eval_scoreboard)")
                except Exception as _aje:
                    print(f"[OutcomeClock] auto-judge failed for {pred['id']}: {_aje}")
    counts = all_due()   # recount after judging
    if sum(counts.values()):
        print(f"[OutcomeClock] reviews due — 7d:{counts['7']} 30d:{counts['30']} "
              f"90d:{counts['90']} 180d:{counts['180']}")
    return {"reschedule_in": DAY, "due": counts, "auto_judged": judged}

# loop: graded outcome → House Mind belief revision (see evaluate → revise_from_outcome)
