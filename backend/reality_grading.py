"""
reality_grading.py — RFC-0001: the Reality Grading Loop for missions
====================================================================
Learning Integrity:
  #1 the system SHALL NOT amplify knowledge that has not first been anchored against
     external reality (anchor first, then amplify);
  #2 every validated episode SHALL reference immutable evidence (artifact hashes,
     ledger id, timestamps, judge version) — so a future judge change can never
     silently rewrite what an old verdict meant.

The scientific-method flow (a COMPLETE mission does not "claim" — it proposes):

    Mission → HYPOTHESIS → Reality → EVALUATION → Validated Episode

  W1 record_mission_hypothesis() — at Commander sign-off, a COMPLETE mission stakes a
        FALSIFIABLE hypothesis: "these artifacts will hold". Machine-checkable payload
        (files + sha256 evidence snapshot + workspace + ledger id + judge version)
        rides in `predicted_outcome`.
  W2 judge_mission_hypothesis()  — at the outcome clock's review, reality is the
        FILESYSTEM and the MISSION LEDGER — never any provider's account of itself
        (Evidence Normalization: GPT, Claude, or a human saying "success" carries no
        weight; the judge reads the same filesystem for all):
            correct   = every signed artifact exists (+ ledger entry still COMPLETE)
            partial   = some artifacts exist
            incorrect = none exist, or the ledger entry was overturned
            None      = unverifiable (workspace gone) → left for a human, never guessed
  W3 validated_sessions()        — the Validated Episode layer: episodes whose
        hypotheses graded `correct`. Downstream recall/promotion may amplify ONLY these.

Grading, reputation, minority resolution, and House-Mind belief revision all reuse
`outcome_tracker.evaluate()` — this module adds no new pipeline, only the wiring.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import outcome_tracker as _ot
import institutional_db as _db

_AGENT = "mission_operative"      # reputation account for mission execution hypotheses
_CONFIDENCE = 0.75                # modest stake; reality, not bravado, moves reputation
_METRIC = "mission_artifacts"     # auto_judge dispatches on this prefix
_LEDGER_NAME = "_MISSION_LEDGER.json"

# Learning Integrity #2: the judge is VERSIONED. Bump on any semantic change to
# judge_mission_hypothesis so every episode records which rulebook evaluated it.
JUDGE_VERSION = "rg-1"


# ──────────────────────────────────────────────────────────────────────────────
# W1 — stake the hypothesis at mission sign-off
# ──────────────────────────────────────────────────────────────────────────────
def record_mission_hypothesis(workspace: str, entry: Dict[str, Any],
                              path: Optional[str] = None) -> Optional[str]:
    """Record a falsifiable hypothesis for a COMPLETE mission. Returns the prediction
    id, or None when there is nothing evaluable (not COMPLETE, no artifacts, duplicate)."""
    status = str(entry.get("status") or "")
    files = [str(f) for f in (entry.get("files") or []) if str(f).strip()]
    if status != "COMPLETE" or not files or not workspace:
        return None
    task = str(entry.get("task") or "")[:160]
    statement = f"Mission hypothesis: outcome COMPLETE will hold — {task}"
    if _ot.has_pending(statement, agent=_AGENT, path=path):
        return None                      # one hypothesis per mission — no double staking
    files = files[:20]
    payload = {
        "files": files,
        "workspace": str(workspace),
        "ledger_id": str(entry.get("id") or ""),
        # Learning Integrity #2 — immutable evidence snapshot at stake time:
        # what existed, byte-for-byte, when the hypothesis was proposed.
        "evidence": {
            "sha256": _hash_artifacts(Path(workspace), files),
            "staked_at": time.time(),
            "judge_version_at_stake": JUDGE_VERSION,
        },
    }
    # session_id stays empty: predictions.session_id is an FK to council_sessions;
    # a mission is not a council session. Mission traceability = payload.ledger_id.
    return _ot.record_prediction(
        statement=statement,
        agent=_AGENT,
        session_id="",
        predicted_outcome=json.dumps(payload, ensure_ascii=False),
        invalidation=("any signed artifact missing at review, "
                      "or the mission ledger entry no longer COMPLETE"),
        confidence=_CONFIDENCE,
        extracted_from="mission_ledger",
        horizon_primary="7",
        metric=_METRIC,
        direction="hold",
        evidence_source=str(workspace),
        path=path,
    )


def _hash_artifacts(ws: Path, files: List[str]) -> Dict[str, str]:
    """sha256 per artifact (best-effort; a missing/unreadable file hashes as '')."""
    out: Dict[str, str] = {}
    for f in files:
        p = Path(f) if Path(f).is_absolute() else (ws / f)
        try:
            out[f] = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:
            out[f] = ""
    return out


# ──────────────────────────────────────────────────────────────────────────────
# W2 — the evaluation: filesystem + ledger, never the provider
# ──────────────────────────────────────────────────────────────────────────────
def judge_mission_hypothesis(pred: Dict[str, Any]) -> Optional[str]:
    """Evaluate a mission hypothesis against observable reality. Returns
    correct | partial | incorrect, or None when reality is unverifiable
    (workspace gone) — an honest judge abstains rather than guesses."""
    try:
        payload = json.loads(pred.get("predicted_outcome") or "{}")
    except Exception:
        return None
    files = payload.get("files") or []
    ws = payload.get("workspace") or ""
    if not files or not ws:
        return None
    ws_path = Path(ws)
    if not ws_path.exists():
        return None                      # unverifiable — leave for a human

    # ledger overturn check: the signed entry must still say COMPLETE
    ledger_id = str(payload.get("ledger_id") or "")
    if ledger_id and _ledger_overturned(ws_path, ledger_id):
        return "incorrect"

    existing = sum(1 for f in files if _artifact_exists(ws_path, str(f)))
    if existing == len(files):
        return "correct"
    if existing > 0:
        return "partial"
    return "incorrect"


def _artifact_exists(ws: Path, f: str) -> bool:
    p = Path(f)
    if p.is_absolute():
        return p.exists()
    return (ws / f).exists()


def _ledger_overturned(ws: Path, ledger_id: str) -> bool:
    """True only when the ledger POSITIVELY shows the entry is no longer COMPLETE.
    A missing/unreadable ledger is not an overturn (absence of evidence)."""
    try:
        data = json.loads((ws / _LEDGER_NAME).read_text(encoding="utf-8"))
    except Exception:
        return False
    for m in data.get("missions", []):
        if str(m.get("id") or "") == ledger_id:
            return str(m.get("status") or "") != "COMPLETE"
    return False


# ──────────────────────────────────────────────────────────────────────────────
# W3 — the Validated Episode layer
# ──────────────────────────────────────────────────────────────────────────────
def validated_sessions(limit: int = 50, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Episodes whose mission hypotheses graded `correct` — the ONLY episodes
    downstream recall/promotion should amplify (anchor first, then amplify).
    Each carries its immutable-evidence payload (Learning Integrity #2)."""
    _db.init_once(path)
    with _db.connect(path) as c:
        rows = c.execute(
            "SELECT id, session_id, statement, predicted_outcome, evaluated_at, status "
            "FROM predictions WHERE metric=? AND status='correct' "
            "ORDER BY evaluated_at DESC LIMIT ?",
            (_METRIC, limit)).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["evidence"] = json.loads(d.pop("predicted_outcome") or "{}").get("evidence", {})
        except Exception:
            d["evidence"] = {}
        out.append(d)
    return out


def loop_summary(path: Optional[str] = None) -> Dict[str, Any]:
    """Observability for the RFC's pilot success criteria: hypotheses by status."""
    _db.init_once(path)
    with _db.connect(path) as c:
        by = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM predictions WHERE metric=? GROUP BY status",
            (_METRIC,)).fetchall()}
    return {"mission_hypotheses": by,
            "validated_episodes": len(validated_sessions(path=path)),
            "judge_version": JUDGE_VERSION}


# ──────────────────────────────────────────────────────────────────────────────
# Canonical Health API — the SINGLE observation surface for the learning loop.
# Subsystems do not invent their own metrics; the dashboard, evidence review,
# and governance all read THIS. (Operator ruling 2026-07-19: vital signs, not KPIs.)
# ──────────────────────────────────────────────────────────────────────────────
def vital_signs(path: Optional[str] = None) -> Dict[str, Any]:
    """The learning loop's pulse. Answers ONE question: is the loop alive?
    Every number is derived from loop data — no self-reported provider metrics
    (Evidence Normalization applies to observability too)."""
    _db.init_once(path)
    with _db.connect(path) as c:
        staked = c.execute("SELECT COUNT(*) n FROM predictions WHERE metric=?",
                           (_METRIC,)).fetchone()["n"]
        first_staked = c.execute("SELECT MIN(made_at) t FROM predictions WHERE metric=?",
                                 (_METRIC,)).fetchone()["t"]
        by_status = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM predictions WHERE metric=? GROUP BY status",
            (_METRIC,)).fetchall()}
        # belief revisions driven by REALITY (the marker house_state writes)
        try:
            revisions = c.execute("SELECT COUNT(*) n FROM belief_changes WHERE agent=?",
                                  ("Reality (outcome)",)).fetchone()["n"]
        except Exception:
            revisions = None
        # reality coverage: COMPLETE missions since the pilot began that staked
        try:
            complete_runs = (c.execute(
                "SELECT COUNT(*) n FROM agent_runs WHERE status='TASK_COMPLETE' "
                "AND started_at >= ?", (first_staked,)).fetchone()["n"]
                if first_staked else None)
        except Exception:
            complete_runs = None

    # due-for-review + live abstain probe (read-only dry-run of the judge)
    due: List[Dict[str, Any]] = []
    for h in _ot.HORIZONS:
        try:
            due += [p for p in _ot.due_reviews(h, limit=200, path=path)
                    if str(p.get("metric") or "") == _METRIC]
        except Exception:
            pass
    seen = set()
    due = [p for p in due if not (p["id"] in seen or seen.add(p["id"]))]
    abstains = sum(1 for p in due if judge_mission_hypothesis(p) is None)
    abstain_rate = (abstains / len(due)) if due else None

    validated = len(validated_sessions(limit=10_000, path=path))
    promoted = _promoted_capability_count()
    coverage = ((staked / complete_runs) if complete_runs else None)

    # How long has the oldest due hypothesis been waiting for someone to ask?
    # The First Evidence Review (2026-07-28) found the House could not tell
    # "reality has not answered yet" from "nobody asked reality": a hypothesis
    # sat 26 hours past its horizon while the dashboard reported AWAITING_REALITY,
    # because the outcome clock only ticks inside a running process and the House
    # had been switched off. Both states were true statements about the loop and
    # only one was a true statement about the world. They are now distinct.
    now = time.time()
    overdue_by = []
    for p in due:
        for h in _ot.HORIZONS:
            ts = p.get(f"due_{h}")
            if ts and float(ts) <= now:
                overdue_by.append(now - float(ts))
                break
    oldest_overdue_h = (max(overdue_by) / 3600.0) if overdue_by else None

    # RETROSPECTIVE lateness. `oldest_overdue_hours` measures answers still
    # uncollected; nothing measured how late the collected ones were. The First
    # Evidence Review's Q1 found the pilot verdict landed ~27h after its horizon —
    # the Outcome Clock ticks every 10 minutes but only while the House is running,
    # so grading is gated on process liveness rather than on wall-clock time. The
    # loop was autonomous and unpunctual, and nothing said so.
    #
    # Null when nothing has been graded yet: "never late" and "never measured" are
    # different claims.
    lateness_h: List[float] = []
    try:
        with _db.connect(path) as c:
            for row in c.execute(
                    "SELECT due_7, due_30, due_90, due_180, evaluated_at "
                    "FROM predictions WHERE evaluated_at IS NOT NULL "
                    "AND status NOT IN ('pending','')"):
                ev = float(row["evaluated_at"] or 0)
                if not ev:
                    continue
                # The horizon it was actually answered against: the latest one that
                # had already elapsed when the verdict landed.
                elapsed = [float(row[f"due_{h}"] or 0) for h in _ot.HORIZONS
                           if row[f"due_{h}"] and float(row[f"due_{h}"]) <= ev]
                if elapsed:
                    lateness_h.append((ev - max(elapsed)) / 3600.0)
    except Exception:
        lateness_h = []

    if staked == 0:
        verdict = "WAITING_FIRST_HYPOTHESIS"
    elif due:
        # Reality's answer is available and uncollected. This is the House's
        # fault, not reality's, and it must not read as patience.
        verdict = "REALITY_UNCOLLECTED"
    elif validated == 0:
        verdict = "AWAITING_REALITY"          # staked; the horizon is still running
    elif revisions:
        verdict = "ALIVE"                     # full cycle observed: reality changed a belief
    else:
        verdict = "VALIDATING"                # episodes exist; belief revision not yet seen

    return {
        "verdict": verdict,
        "hypotheses_staked": staked,
        "due_for_review": len(due),
        # Age of the oldest uncollected answer. None means nothing is overdue —
        # honestly null, never a fabricated 0, because "no backlog" and "a
        # backlog aged zero hours" are different claims.
        "oldest_overdue_hours": (round(oldest_overdue_h, 1)
                                 if oldest_overdue_h is not None else None),
        # How late the ANSWERED ones were. A loop can be autonomous and still
        # chronically behind its own horizons; without this the two are
        # indistinguishable.
        "grading_lateness_hours_max": (round(max(lateness_h), 1) if lateness_h else None),
        "grading_lateness_hours_avg": (round(sum(lateness_h) / len(lateness_h), 1)
                                       if lateness_h else None),
        "graded_on_time": (sum(1 for x in lateness_h if x <= 1.0) if lateness_h else None),
        "validated_episodes": validated,
        "belief_revisions_from_reality": revisions,
        "promotion_candidates": validated,     # promotion dormant → all validated are candidates
        "promoted_capabilities": promoted,
        # Public-only guard, do not lose again: `promoted` is None when the
        # promotion path is dormant, and None/int raises. "No promotions" and
        # "promotion not measured" are different claims, so this stays null.
        "promotion_rate": ((promoted / validated)
                           if (validated and promoted is not None) else None),
        "abstain_rate": abstain_rate,
        "reality_coverage": coverage,
        "by_status": by_status,
        "judge_version": JUDGE_VERSION,
        "ts": time.time(),
    }


def _promoted_capability_count() -> Optional[int]:
    try:
        store = Path(__file__).parent / "capabilities.json"
        return len(json.loads(store.read_text(encoding="utf-8")).get("capabilities", []))
    except Exception:
        return None


# ── Back-compat aliases (pre-rename callers; remove after the pilot) ──────────
record_mission_prediction = record_mission_hypothesis
judge_mission_prediction = judge_mission_hypothesis
