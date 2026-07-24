"""
recall_quality.py — M2 Foundation: the Recall Quality Layer for THE HOUSE
========================================================================
The House must not recall information — it must recall JUSTIFIED information.

Before any recalled memory reaches a deliberation, this layer answers, per item:
  • Why was it recalled?     → matched terms (retrieval reason)
  • Why is it relevant?      → similarity score
  • Was it correct?          → accuracy + calibration over its graded predictions
  • Does it remain valid?    → current validity state

Five scores attached to every recalled session:
  similarity · accuracy · calibration · outcome_status · validity

Five validity states:
  VALIDATED        — graded, accurate, current, not superseded
  PARTIALLY_VALID  — mixed outcomes, or correct-but-aging
  OUTDATED         — superseded by a newer ruling, or past the staleness horizon
  DISPROVEN        — graded predictions resolved incorrect
  UNKNOWN          — no graded outcomes yet (untested)

This layer is pure (its only I/O is reading outcomes via a passed DB path) so the
Convener (built later) can consume it deterministically.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import institutional_db as _db

# ── validity states ───────────────────────────────────────────────────────────
VALIDATED = "VALIDATED"
PARTIALLY_VALID = "PARTIALLY_VALID"
OUTDATED = "OUTDATED"
DISPROVEN = "DISPROVEN"
UNKNOWN = "UNKNOWN"
STATES = (VALIDATED, PARTIALLY_VALID, OUTDATED, DISPROVEN, UNKNOWN)

# states that must always carry a warning (never surfaced as unqualified authority)
WARN = {DISPROVEN, OUTDATED, PARTIALLY_VALID}

# ── thresholds (tunable) ──────────────────────────────────────────────────────
ACC_VALID = 0.6
ACC_DISPROVEN = 0.4
STALE_SOFT_DAYS = 270.0      # correct-but-aging → PARTIALLY_VALID
STALE_HARD_DAYS = 540.0      # too old to be authoritative → OUTDATED
SUPERSEDE_SIM = 0.6          # a newer near-duplicate ruling supersedes the older
DAY = 86400.0

# how much each validity state is trusted in ranking
VALIDITY_FACTOR = {
    VALIDATED: 1.0, PARTIALLY_VALID: 0.6, UNKNOWN: 0.5, OUTDATED: 0.25, DISPROVEN: 0.1,
}

_WORD = re.compile(r"[\w฀-๿]+")


def _tokens(s: str) -> set:
    return {t.lower() for t in _WORD.findall(s or "") if len(t) > 2}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# ── outcomes ──────────────────────────────────────────────────────────────────
def gather_outcomes(c, session_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Per-session outcome roll-up from graded predictions."""
    out: Dict[str, Dict[str, Any]] = {}
    if not session_ids:
        return out
    q = ",".join("?" * len(session_ids))
    rows = c.execute(
        f"SELECT session_id, status FROM predictions "
        f"WHERE session_id IN ({q}) AND status!='pending'", session_ids).fetchall()
    for r in rows:
        o = out.setdefault(r["session_id"], {"n_evaluated": 0, "n_correct": 0,
                                             "n_partial": 0, "n_incorrect": 0, "score": 0.0})
        o["n_evaluated"] += 1
        if r["status"] == "correct":   o["n_correct"] += 1; o["score"] += 1.0
        elif r["status"] == "partial": o["n_partial"] += 1; o["score"] += 0.5
        else:                          o["n_incorrect"] += 1
    for o in out.values():
        o["accuracy"] = round(o["score"] / o["n_evaluated"], 3) if o["n_evaluated"] else None
    return out


# ── supersession ──────────────────────────────────────────────────────────────
def detect_supersession(candidates: List[Dict[str, Any]],
                        outcomes: Optional[Dict[str, Any]] = None,
                        sim_threshold: float = SUPERSEDE_SIM) -> Dict[str, str]:
    """A session is superseded if a MORE RECENT, NON-DISPROVEN candidate covers the
    same ground. A proven-wrong newer take does NOT supersede earlier rulings.
    Returns {old_session_id: newer_session_id}."""
    outcomes = outcomes or {}
    def _disproven(sid: str) -> bool:
        o = outcomes.get(sid, {})
        acc = o.get("accuracy")
        return bool(o.get("n_evaluated", 0) and acc is not None and acc < ACC_DISPROVEN)
    superseded: Dict[str, str] = {}
    toks = {d["id"]: _tokens(d.get("directive", "")) for d in candidates}
    order = sorted(candidates, key=lambda d: d.get("ts", 0.0) or 0.0)  # oldest first
    for i, older in enumerate(order):
        ot = toks[older["id"]]
        if not ot:
            continue
        for newer in order[i + 1:]:
            nt = toks[newer["id"]]
            if not nt or _disproven(newer["id"]):
                continue                       # disproven rulings cannot supersede
            jacc = len(ot & nt) / len(ot | nt)
            if jacc >= sim_threshold:
                superseded[older["id"]] = newer["id"]   # newest valid wins
    return superseded


# ── validity ──────────────────────────────────────────────────────────────────
def assess_validity(accuracy: Optional[float], n_eval: int, age_days: float,
                    superseded_by: Optional[str]) -> tuple:
    """Return (state, reason). Priority: DISPROVEN > OUTDATED > UNKNOWN > VALIDATED/PARTIAL."""
    if n_eval and accuracy is not None and accuracy < ACC_DISPROVEN:
        return DISPROVEN, f"predictions resolved incorrect (acc {accuracy})"
    if superseded_by:
        return OUTDATED, f"superseded by {superseded_by}"
    if n_eval and age_days > STALE_HARD_DAYS:
        return OUTDATED, f"older than staleness horizon ({int(age_days)}d > {int(STALE_HARD_DAYS)}d)"
    if not n_eval:
        return UNKNOWN, "no graded outcomes yet"
    if accuracy is not None and accuracy >= ACC_VALID:
        if age_days > STALE_SOFT_DAYS:
            return PARTIALLY_VALID, f"accurate but aging ({int(age_days)}d)"
        return VALIDATED, f"accurate (acc {accuracy}) and current"
    return PARTIALLY_VALID, f"mixed outcomes (acc {accuracy})"


# ── per-candidate assessment ──────────────────────────────────────────────────
def assess(cand: Dict[str, Any], outcomes: Dict[str, Any], query_tokens: set,
           now: float, superseded_by: Optional[str]) -> Dict[str, Any]:
    o = outcomes.get(cand["id"], {})
    n_eval = o.get("n_evaluated", 0)
    accuracy = o.get("accuracy")
    age_days = max(0.0, (now - (cand.get("ts") or now)) / DAY)

    have = _tokens(cand.get("directive", ""))
    matched = sorted(query_tokens & have)
    similarity = round(len(query_tokens & have) / len(query_tokens | have), 3) if (query_tokens | have) else 0.0

    calibration = (1.0 - abs((cand.get("confidence") or 0.0) - accuracy)) if (n_eval and accuracy is not None) else 0.5
    calibration = round(max(0.0, calibration), 3)

    state, reason = assess_validity(accuracy, n_eval, age_days, superseded_by)
    warning = state in WARN

    acc_factor = (0.1 + 0.9 * accuracy) if (n_eval and accuracy is not None) else 0.5
    rank = round(similarity * acc_factor * (0.5 + 0.5 * calibration) * VALIDITY_FACTOR[state], 5)

    cand.update({
        "similarity": similarity,
        "accuracy_score": accuracy,
        "calibration_score": calibration,
        "outcome_status": {
            "n_evaluated": n_eval, "n_correct": o.get("n_correct", 0),
            "n_partial": o.get("n_partial", 0), "n_incorrect": o.get("n_incorrect", 0),
        },
        "validity": state,
        "warning": warning,
        "superseded_by": superseded_by,
        "age_days": round(age_days, 1),
        "rank": rank,
        # legacy aliases (M1.5 back-compat)
        "label": {VALIDATED: "validated", DISPROVEN: "DISPROVEN", PARTIALLY_VALID: "mixed",
                  UNKNOWN: "unverified", OUTDATED: "outdated"}[state],
        "historical_accuracy": accuracy,
        "n_evaluated": n_eval,
        "justification": {
            "why_recalled": f"matched terms: {', '.join(matched[:6]) or '(none)'}",
            "why_relevant": f"similarity {similarity}",
            "whether_correct": f"{state}: accuracy {accuracy} over {n_eval} graded prediction(s)"
                               if n_eval else "no graded predictions yet",
            "whether_valid": f"{state} — {reason}",
        },
    })
    return cand


def annotate(candidates: List[Dict[str, Any]], query: str,
             now: Optional[float] = None, path: Optional[str] = None,
             limit: int = 5) -> List[Dict[str, Any]]:
    """Full quality pass over retrieved candidates → justified, ranked results.
    Untrustworthy states (DISPROVEN/OUTDATED/PARTIALLY_VALID) always carry a
    warning and sink below trusted ones."""
    if not candidates:
        return []
    now = now if now is not None else time.time()
    qtok = _tokens(query)
    with _db.connect(path) as c:
        outcomes = gather_outcomes(c, [d["id"] for d in candidates])
    superseded = detect_supersession(candidates, outcomes)
    annotated = [assess(d, outcomes, qtok, now, superseded.get(d["id"])) for d in candidates]
    # trusted (no warning) first; then by justified rank, then similarity
    annotated.sort(key=lambda x: (-(0 if x["warning"] else 1), -x["rank"], -x["similarity"]))
    return annotated[:limit]
