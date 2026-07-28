"""
judgment_queue.py — the loop's missing half: what is waiting on a human
=======================================================================
The Reality Grading loop grades a claim, and a graded claim then resolves that
session's dissents (`governance_engine.on_outcome`) and revises what the House
believes (`house_state.revise_from_outcome`). Both are wired and both work.

Neither had ever run, and the reason was not a broken judge.

`auto_judge` only recognises two kinds of claim: mission hypotheses, graded
against the filesystem, and claims whose metric names the eval scoreboard.
Everything else "stays human-judged" — which was true, except that nothing ever
told the human. A claim like *"THE HOUSE's overall efficiency will improve"* came
due, found no automatic judge, returned `None` (correctly: the judge abstains
rather than guesses), and stayed `pending`.

Forever. And because `on_outcome` refuses to resolve a session's dissents until
that session is fully graded, **one unanswerable claim silently blocked every
dissent recorded alongside it.** Nine dissents, none resolved, and no error
anywhere — the House was waiting on a person it had never asked.

This module makes the wait legible. It does not judge anything: it separates

    AWAITING_HORIZON        the clock has not run out; reality has not answered
    AWAITING_AUTO_JUDGE     due, and a judge exists that will grade it
    AWAITING_HUMAN          due, no automatic judge — the operator must rule
    MALFORMED               the record is corrupt; nobody can judge it as stored
    JUDGED                  a verdict is in

so that "reality has not answered" stops being confused with "nobody was asked",
which is the same confusion the liveness fix removed from `vital_signs()`.

A verdict submitted here goes through `outcome_tracker.evaluate()` — the ordinary
path — so it moves reputation, resolves dissents, and revises beliefs exactly as
an automatic verdict would. The human is the judge; the loop is unchanged.

Read-only except `submit()`, which is the operator's explicit act.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import institutional_db as _db
import outcome_tracker as _ot

# A stored invalidation that is a fragment of raw JSON means the extractor
# mis-parsed the forecaster's output. Such a row cannot be judged as recorded —
# calling it "pending" would imply someone could answer it.
_JSON_FRAGMENT = re.compile(r'^\s*[\w"]*"?\s*:\s*\d|"invalidation"\s*:', re.I)

TERMINAL = {"correct", "partial", "incorrect"}


def _malformed_reason(p: Dict[str, Any]) -> Optional[str]:
    inv = str(p.get("invalidation") or "")
    if not inv.strip():
        return "no invalidation condition — nothing was committed to as disproof"
    if _JSON_FRAGMENT.search(inv):
        return ("the invalidation field holds a fragment of raw JSON — the "
                "forecaster's structured output was mis-parsed when this was staked")
    if not str(p.get("metric") or "").strip():
        return "no metric declared — there is nothing to measure it against"
    return None


def classify(pred: Dict[str, Any], now: Optional[float] = None) -> Dict[str, Any]:
    """Why is this claim still open? Deterministic; grades nothing."""
    now = now if now is not None else time.time()
    status = str(pred.get("status") or "pending")
    if status in TERMINAL:
        return {"state": "JUDGED", "verdict": status,
                "because": f"reality returned '{status}'"}

    bad = _malformed_reason(pred)
    if bad:
        return {"state": "MALFORMED", "because": bad}

    # Earliest horizon that has actually elapsed.
    due_at, overdue_h = None, None
    for h in _ot.HORIZONS:
        ts = pred.get(f"due_{h}")
        if ts and float(ts) > 0 and float(ts) <= now:
            due_at = float(ts)
            overdue_h = round((now - due_at) / 3600.0, 1)
            break

    if due_at is None:
        return {"state": "AWAITING_HORIZON",
                "because": "the horizon has not elapsed — reality has not answered yet"}

    # Due. Would any judge take it?
    try:
        verdict = _ot.auto_judge(dict(pred))
    except Exception:
        verdict = None

    if verdict:
        return {"state": "AWAITING_AUTO_JUDGE", "overdue_hours": overdue_h,
                "because": "due, and an automatic judge will grade it on the next tick"}

    metric = str(pred.get("metric") or "")
    return {
        "state": "AWAITING_HUMAN",
        "overdue_hours": overdue_h,
        "because": (f"due {overdue_h}h ago, and no automatic judge recognises the "
                    f"metric {metric[:60]!r}. Only the operator can rule on this, "
                    "and until they do it blocks its session's dissents."),
    }


def _blocked_dissents(c, session_id: Optional[str]) -> int:
    if not session_id:
        return 0
    try:
        return c.execute(
            "SELECT COUNT(*) FROM minority_positions WHERE session_id=? AND resolved=0",
            (session_id,)).fetchone()[0]
    except Exception:
        return 0


def queue(limit: int = 50, path: Optional[str] = None) -> Dict[str, Any]:
    """Everything still open, sorted by what it is blocking."""
    _db.init_once(path)
    items: List[Dict[str, Any]] = []
    tally: Dict[str, int] = {}

    with _db.connect(path) as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM predictions ORDER BY made_at DESC LIMIT 500")]
        for p in rows:
            cl = classify(p)
            tally[cl["state"]] = tally.get(cl["state"], 0) + 1
            if cl["state"] == "JUDGED":
                continue
            items.append({
                "id": p["id"],
                "claim": str(p.get("statement") or "")[:220],
                "staked_by": p.get("agent"),
                "session_id": p.get("session_id"),
                "metric": p.get("metric"),
                "would_be_wrong_if": p.get("invalidation"),
                "stated_confidence": p.get("confidence"),
                "blocking_dissents": _blocked_dissents(c, p.get("session_id")),
                **cl,
            })

    # What blocks a dissent matters most: that is the loop that cannot close.
    items.sort(key=lambda x: (-(x.get("blocking_dissents") or 0),
                              -(x.get("overdue_hours") or 0)))

    awaiting_human = [i for i in items if i["state"] == "AWAITING_HUMAN"]
    blocked = sum(i["blocking_dissents"] for i in awaiting_human)

    note = None
    if blocked:
        note = (f"{blocked} dissent(s) cannot be resolved until a human rules on "
                f"{len(awaiting_human)} claim(s). The House is not waiting on "
                "reality here — it is waiting on you.")

    return {"by_state": tally, "open": items[:limit],
            "dissents_blocked_on_a_human": blocked, "note": note,
            "ts": time.time()}


def submit(pid: str, verdict: str, horizon: str = "7",
           note: str = "", path: Optional[str] = None) -> Dict[str, Any]:
    """Record the operator's ruling through the ordinary grading path.

    Deliberately thin: it calls `outcome_tracker.evaluate()` rather than writing
    a status itself, so a human verdict moves reputation, resolves the session's
    dissents, and revises the House's beliefs by exactly the same code an
    automatic verdict uses. A separate write path would be a second, untested
    way to change what the House believes.
    """
    if verdict not in TERMINAL:
        raise ValueError(f"verdict must be one of {sorted(TERMINAL)}")

    result = _ot.evaluate(pid, horizon, verdict, path=path)

    # Report what the ruling actually moved, so the operator sees the loop close.
    out = {"prediction": pid, "verdict": verdict, "judged_by": "human (operator)",
           "note": note or None}
    for key in ("minority", "belief_change", "reputation"):
        if isinstance(result, dict) and key in result:
            out[key] = result[key]
    return out
