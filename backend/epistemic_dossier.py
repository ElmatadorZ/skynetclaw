"""
epistemic_dossier.py — "prove it": a receipt for anything the House believes
=============================================================================
Ask any assistant why it believes something and it will produce a fluent
justification, generated on the spot, indistinguishable from one it would have
produced for the opposite claim. The confidence is a rendering choice.

The House keeps the bookkeeping to answer differently. For a claim it holds it
can name: which agent asserted it, on what evidence, who dissented and why,
whether that dissent was ever resolved, what would falsify it, whether reality
has checked it, and what the asserting agent's calibrated track record is.

This module reads that record and returns it as a **dossier** — deliberately
unflattering where the record is thin.

The central number is `trust_basis`:

    EARNED     the asserting agent has graded predictions, and a calibration
               score computed from them
    UNEARNED   the belief carries a confidence figure, but nobody who asserted
               it has ever been graded against reality. The number is an
               assertion about an assertion.

Most of the House's beliefs are currently UNEARNED, and saying so is the point.
A system that reports unearned confidence as unearned is doing the thing that
cannot be faked; one that always sounds justified has told you nothing.

Read-only: opens the institutional DB for SELECT and writes nothing. Stdlib +
the existing institutional_db layer.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import math
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB = Path(__file__).parent / "skynerclaw.db"

# A belief the House has not re-examined in this long is reported as aging. Not
# wrong — aging. The distinction matters: staleness is a reason to re-check, not
# a reason to discard.
_STALE_DAYS = 90.0

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "in", "on",
    "for", "and", "or", "it", "this", "that", "with", "at", "by", "from", "as",
    "we", "i", "you", "do", "does", "did", "has", "have", "had", "what", "why",
    "how", "which", "should", "would", "could", "can", "will",
}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _tokens(text: str) -> set:
    """Words that carry meaning. Thai has no spaces, so CJK/Thai runs are kept
    whole and matched as substrings rather than tokenised badly."""
    lowered = (text or "").lower()
    words = {w for w in re.findall(r"[a-z0-9_./\-]{3,}", lowered) if w not in _STOP}
    thai = {t for t in re.findall(r"[฀-๿]{3,}", lowered)}
    return words | thai


def _relevance(query_tokens: set, content: str) -> float:
    """Deterministic overlap score. No model in the loop: a dossier that needed
    a model to decide what is relevant could not be used to audit that model."""
    if not query_tokens:
        return 0.0
    text = (content or "").lower()
    hits = sum(1 for t in query_tokens if t in text)
    return hits / len(query_tokens)


# ── the record ───────────────────────────────────────────────────────────────
def _beliefs(c, qt: set, limit: int) -> List[Dict[str, Any]]:
    rows = c.execute(
        "SELECT id, kind, content, confidence, agent, evidence, status, "
        "       superseded, ts, state_id "
        "FROM state_items WHERE kind IN ('belief','known_fact','minority') "
        "ORDER BY ts DESC LIMIT 4000").fetchall()
    scored = []
    for r in rows:
        rel = _relevance(qt, r["content"])
        if rel <= 0:
            continue
        age_days = (time.time() - float(r["ts"] or 0)) / 86400.0
        scored.append({
            "id": r["id"],
            "kind": r["kind"],
            "content": r["content"],
            "confidence": r["confidence"],
            "asserted_by": r["agent"],
            "evidence": r["evidence"] or None,
            "status": r["status"],
            "superseded": bool(r["superseded"]),
            "age_days": round(age_days, 1),
            "aging": age_days > _STALE_DAYS,
            "relevance": round(rel, 3),
        })
    scored.sort(key=lambda x: (-x["relevance"], -x["confidence"] if x["confidence"] else 0))
    return scored[:limit]


def _contradictions(c, qt: set, limit: int) -> List[Dict[str, Any]]:
    out = []
    for r in c.execute("SELECT id, content, agent, ts FROM state_items "
                       "WHERE kind='contradiction' ORDER BY ts DESC LIMIT 500"):
        if _relevance(qt, r["content"]) > 0:
            out.append({"id": r["id"], "content": r["content"],
                        "raised_by": r["agent"], "ts": r["ts"]})
    return out[:limit]


def _unknowns(c, qt: set, limit: int) -> List[str]:
    out = []
    for r in c.execute("SELECT content FROM state_items WHERE kind='unknown_fact' "
                       "ORDER BY ts DESC LIMIT 500"):
        if _relevance(qt, r["content"]) > 0:
            out.append(r["content"])
    return out[:limit]


def _dissent(c, qt: set, limit: int) -> List[Dict[str, Any]]:
    """Who disagreed, and whether the House ever went back to find out if they
    were right. An unresolved dissent is an open debt, and it is reported as one."""
    out = []
    for r in c.execute(
            "SELECT id, session_id, agent, position, reason, stance, ts, "
            "       resolved, proven_correct, vindication_applied "
            "FROM minority_positions ORDER BY ts DESC LIMIT 500"):
        if _relevance(qt, f"{r['reason']} {r['position']}") <= 0:
            continue
        out.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "dissenter": r["agent"],
            "position": r["position"],
            "reason": r["reason"],
            "resolved": bool(r["resolved"]),
            "proven_correct": (bool(r["proven_correct"])
                               if r["proven_correct"] is not None else None),
            "vindication_applied": bool(r["vindication_applied"]),
            "ts": r["ts"],
        })
    return out[:limit]


def _falsifiers(c, qt: set, limit: int) -> List[Dict[str, Any]]:
    """What the House committed to as disproof, before knowing the answer."""
    out = []
    for r in c.execute(
            "SELECT id, agent, statement, invalidation, confidence, status, "
            "       made_at, due_7, evaluated_at "
            "FROM predictions ORDER BY made_at DESC LIMIT 500"):
        if _relevance(qt, f"{r['statement']} {r['invalidation'] or ''}") <= 0:
            continue
        out.append({
            "id": r["id"],
            "staked_by": r["agent"],
            "claim": r["statement"],
            "would_be_wrong_if": r["invalidation"] or None,
            "stated_confidence": r["confidence"],
            "verdict": r["status"],
            "graded": r["status"] not in (None, "", "pending"),
            "graded_at": r["evaluated_at"],
        })
    return out[:limit]


def _revisions(c, qt: set, limit: int) -> List[Dict[str, Any]]:
    out = []
    for r in c.execute(
            "SELECT item_id, previous, new, prev_confidence, new_confidence, "
            "       reason, agent, ts FROM belief_changes ORDER BY ts DESC LIMIT 500"):
        if _relevance(qt, f"{r['previous']} {r['new']} {r['reason'] or ''}") <= 0:
            continue
        out.append({
            "from": r["previous"], "to": r["new"],
            "confidence_moved": [r["prev_confidence"], r["new_confidence"]],
            "reason": r["reason"], "revised_by": r["agent"], "ts": r["ts"],
            # A revision driven by an outcome is worth more than one driven by
            # further deliberation: only the first is reality talking back.
            "driven_by_reality": (r["agent"] or "").lower().startswith("reality"),
        })
    return out[:limit]


# ── the number that matters ──────────────────────────────────────────────────
def _track_record(c, agents: List[str]) -> Dict[str, Any]:
    """Calibration of whoever asserted the belief.

    `n_graded` is the whole story: an agent with zero graded predictions has no
    track record, so any confidence it states is unearned — not wrong, unearned.
    """
    records = {}
    for a in {x for x in agents if x}:
        r = c.execute(
            "SELECT agent, score, n_predictions, n_correct, accuracy_rate, "
            "       calibration, brier_n, alpha, beta "
            "FROM agent_reputation WHERE agent = ?", (a,)).fetchone()
        if not r:
            records[a] = {"known_to_reputation_system": False, "n_graded": 0,
                          "note": "this agent has no reputation record at all"}
            continue
        n = int(r["n_predictions"] or 0)
        records[a] = {
            "known_to_reputation_system": True,
            "score": r["score"],
            "n_graded": n,
            "n_correct": r["n_correct"],
            "accuracy": r["accuracy_rate"],
            "calibration": r["calibration"] if (r["brier_n"] or 0) else None,
            "at_neutral_prior": bool(r["alpha"] == 1.0 and r["beta"] == 1.0),
            "note": ("no prediction has ever been graded for this agent — its "
                     "score is the neutral prior, not a measurement"
                     if n == 0 else None),
        }
    return records


def _standing(beliefs, dissent, falsifiers, revisions, contradictions) -> Dict[str, Any]:
    """The honest one-word status, and why."""
    if not beliefs and not falsifiers:
        return {"standing": "NO_RECORD",
                "because": "the House holds no belief matching this claim"}

    refuted = [f for f in falsifiers if f["verdict"] == "incorrect"]
    if refuted:
        return {"standing": "REFUTED",
                "because": f"reality graded {len(refuted)} matching claim(s) incorrect"}

    if any(r["driven_by_reality"] for r in revisions):
        return {"standing": "REVISED_BY_REALITY",
                "because": "an outcome changed what the House believes here"}

    open_dissent = [d for d in dissent if not d["resolved"]]
    if open_dissent or contradictions:
        return {"standing": "CONTESTED",
                "because": (f"{len(open_dissent)} unresolved dissent(s) and "
                            f"{len(contradictions)} recorded contradiction(s) stand "
                            "against it")}

    validated = [f for f in falsifiers if f["verdict"] == "correct"]
    if validated:
        return {"standing": "VALIDATED",
                "because": f"reality graded {len(validated)} matching claim(s) correct"}

    if any(b["superseded"] for b in beliefs):
        return {"standing": "SUPERSEDED",
                "because": "a later belief replaced this one"}

    return {"standing": "UNTESTED",
            "because": ("the House holds this belief but reality has never "
                        "checked it — no graded prediction covers it")}


def dossier(claim: str, limit: int = 6) -> Dict[str, Any]:
    """The receipt. Read-only; never raises on missing data."""
    qt = _tokens(claim)
    if not qt:
        return {"claim": claim, "standing": "NO_QUERY",
                "because": "the claim contained no searchable terms",
                "honest_summary": "Nothing to look up."}

    try:
        c = _conn()
    except Exception as e:
        return {"claim": claim, "standing": "UNAVAILABLE",
                "because": f"institutional memory unreadable: {type(e).__name__}",
                "honest_summary": "The House cannot reach its own record."}

    with c:
        beliefs = _beliefs(c, qt, limit)
        contradictions = _contradictions(c, qt, limit)
        unknowns = _unknowns(c, qt, limit)
        dissent = _dissent(c, qt, limit)
        falsifiers = _falsifiers(c, qt, limit)
        revisions = _revisions(c, qt, limit)
        record = _track_record(c, [b["asserted_by"] for b in beliefs]
                               + [f["staked_by"] for f in falsifiers])

    st = _standing(beliefs, dissent, falsifiers, revisions, contradictions)

    graded_total = sum(r.get("n_graded", 0) for r in record.values())
    stated = [b["confidence"] for b in beliefs if b["confidence"] is not None]
    trust = "EARNED" if graded_total > 0 else "UNEARNED"

    return {
        "claim": claim,
        **st,
        "trust_basis": trust,
        "stated_confidence": (round(sum(stated) / len(stated), 3) if stated else None),
        "graded_predictions_behind_it": graded_total,

        "what_the_house_believes": beliefs,
        "what_it_admits_it_does_not_know": unknowns,
        "who_disagreed": dissent,
        "what_would_prove_it_wrong": falsifiers,
        "how_the_belief_has_moved": revisions,
        "contradictions_on_record": contradictions,
        "track_record_of_the_asserters": record,

        "honest_summary": _summary(st, trust, beliefs, dissent, falsifiers,
                                   unknowns, graded_total),
        "ts": time.time(),
    }


def _summary(st, trust, beliefs, dissent, falsifiers, unknowns, graded) -> str:
    """Plain language, written to be unflattering when the record is thin."""
    if st["standing"] == "NO_RECORD":
        return ("The House holds no recorded belief about this. It is not "
                "declining to answer — it has nothing on file, and saying so "
                "beats inventing a position.")

    bits = [f"Standing: {st['standing']} — {st['because']}."]

    if trust == "UNEARNED":
        bits.append(
            "Trust basis: UNEARNED. Whoever asserted this has never had a "
            "prediction graded against reality, so the stated confidence is an "
            "assertion, not a measurement. Weigh it accordingly.")
    else:
        bits.append(f"Trust basis: EARNED — {graded} graded prediction(s) stand "
                    "behind the agents who asserted this.")

    unresolved = [d for d in dissent if not d["resolved"]]
    if unresolved:
        who = ", ".join(sorted({d["dissenter"] for d in unresolved}))
        bits.append(f"{len(unresolved)} dissent(s) by {who} were recorded and "
                    "never resolved. The House does not know whether the "
                    "minority was right, and has not gone back to find out.")

    ungraded = [f for f in falsifiers if not f["graded"]]
    if ungraded:
        bits.append(f"{len(ungraded)} falsifiable claim(s) are staked and still "
                    "awaiting their horizon.")

    if unknowns:
        bits.append(f"{len(unknowns)} relevant unknown(s) are on record — the "
                    "House is tracking what it does not know here.")

    if not falsifiers:
        bits.append("No falsifier is on record for this belief: nothing was "
                    "committed to in advance that would prove it wrong.")

    return " ".join(bits)


def self_audit() -> Dict[str, Any]:
    """The House's epistemic vital signs, stated against itself.

    Not a scoreboard — a confession. Every ratio here can be embarrassing, and
    is reported anyway, because a number that can only flatter measures nothing.
    """
    try:
        c = _conn()
    except Exception as e:
        return {"available": False, "reason": f"{type(e).__name__}: {e}"}

    with c:
        def one(sql, *a):
            try:
                return c.execute(sql, a).fetchone()[0]
            except Exception:
                return None

        beliefs = one("SELECT COUNT(*) FROM state_items WHERE kind='belief'") or 0
        dissents = one("SELECT COUNT(*) FROM minority_positions") or 0
        resolved = one("SELECT COUNT(*) FROM minority_positions WHERE resolved=1") or 0
        vindicated = one("SELECT COUNT(*) FROM minority_positions "
                         "WHERE COALESCE(proven_correct,0)=1") or 0
        staked = one("SELECT COUNT(*) FROM predictions") or 0
        graded = one("SELECT COUNT(*) FROM predictions "
                     "WHERE status NOT IN ('pending','')") or 0
        revisions = one("SELECT COUNT(*) FROM belief_changes") or 0
        by_reality = one("SELECT COUNT(*) FROM belief_changes "
                         "WHERE LOWER(agent) LIKE 'reality%'") or 0
        agents = one("SELECT COUNT(*) FROM agent_reputation") or 0
        agents_graded = one("SELECT COUNT(*) FROM agent_reputation "
                            "WHERE n_predictions > 0") or 0

    def ratio(num, den):
        # Honest null over a fabricated zero: "none of nothing" is not 0%.
        return round(num / den, 3) if den else None

    # Findings are PROPORTIONAL, not binary.
    #
    # The First Evidence Review (RFC-0001, 2026-07-30) caught this instrument
    # lying by omission. The conditions read `if dissents and not resolved`, so
    # the moment ONE of nine dissents was resolved the finding vanished — 1/9
    # reported identically to 9/9. A single success silenced a systemic warning,
    # and the system's self-report stopped mentioning a pattern that had barely
    # changed. Q5 exists to grade interpretation rather than bookkeeping, and
    # this is what it found.
    #
    # A gap is now reported until it is CLOSED, and the wording tracks how far
    # along it is, so the reader can tell "never happened" from "happened once".
    findings = []

    def _gap(label: str, done: int, total: int, never: str, partial: str) -> None:
        if not total or done >= total:
            return
        findings.append(never if done == 0
                        else f"{partial} ({done} of {total} so far — "
                             f"{round(100.0 * done / total)}%)")

    _gap("dissent", resolved, dissents,
         never=(f"{dissents} dissent(s) recorded, none ever resolved. The machinery "
                "to find out whether a minority was right exists and has never run."),
         partial=("dissent resolution has run but is not routine — most recorded "
                  "disagreements are still unexamined"))
    _gap("reality-driven revision", by_reality, revisions,
         never=(f"{revisions} belief revision(s), none driven by an outcome. Beliefs "
                "change here by deliberation, not yet by reality."),
         partial=("beliefs still change mostly by deliberation rather than by "
                  "outcome"))
    _gap("agent track record", agents_graded, agents,
         never=(f"none of {agents} agents has a graded prediction — every score is "
                "the neutral prior, not a measurement"),
         partial=(f"{agents - agents_graded} of {agents} agents sit at the neutral "
                  "prior with no graded prediction — their scores are placeholders"))
    # Claims nobody can judge as recorded (a corrupt invalidation, no metric) sit
    # in the denominator forever, so grading_rate can never reach 1.0. Reported
    # SEPARATELY rather than quietly excluded: dropping them would flatter the
    # rate, and hiding them would lose the defect they are evidence of.
    unjudgeable = 0
    try:
        c2 = _conn()
        with c2:
            import judgment_queue as _jq
            rows = [dict(r) for r in c2.execute(
                "SELECT * FROM predictions ORDER BY made_at DESC LIMIT 500")]
        unjudgeable = sum(1 for p in rows
                          if _jq.classify(p)["state"] == "MALFORMED")
    except Exception:
        unjudgeable = 0

    _gap("grading", graded, staked,
         never=f"{staked} claim(s) staked, none graded — nothing has met reality yet.",
         partial=f"{staked - graded} staked claim(s) are still awaiting reality")
    if unjudgeable:
        findings.append(
            f"{unjudgeable} staked claim(s) are MALFORMED and can never be graded by "
            "anyone — they hold a corrupt invalidation or no metric. They stay in the "
            "denominator on purpose: removing them would flatter the grading rate, and "
            "deleting them would lose the evidence of the defect that produced them.")

    return {
        "available": True,
        "beliefs_held": beliefs,
        "dissents_recorded": dissents,
        "dissents_resolved": resolved,
        "minority_vindicated": vindicated,
        "dissent_resolution_rate": ratio(resolved, dissents),
        "claims_staked": staked,
        "claims_graded": graded,
        "grading_rate": ratio(graded, staked),
        "belief_revisions": revisions,
        "revisions_driven_by_reality": by_reality,
        "reality_driven_share": ratio(by_reality, revisions),
        "agents_tracked": agents,
        "agents_with_a_track_record": agents_graded,
        "uncomfortable_findings": findings,
        "ts": time.time(),
    }
