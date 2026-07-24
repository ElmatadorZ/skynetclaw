"""
deliberation_briefing.py — M2: the Deliberation Briefing Engine for THE HOUSE
============================================================================
The Council must never consume raw memories. It consumes a BRIEFING.

This engine turns Recall Quality results (validity-graded prior sessions) into
institutional guidance — a synthesized Historical Brief — so the Council enters
deliberation already informed by its own history, does not rediscover lessons it
already learned, and does not repeat disproven reasoning.

It SYNTHESIZES (patterns, lessons, errors, trends, blind spots). It never dumps a
raw session. Synthesis is deterministic and testable; the Council's LLM then
reasons over the brief.

Brief sections:
  executive_summary · relevant_historical_cases · validated_lessons ·
  failed_lessons · common_patterns · repeated_errors · confidence_trends ·
  agent_performance_trends · recommended_focus_areas · known_blind_spots

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional

import institutional_db as _db
import council_memory as _cm
import recall_quality as _rq
import agent_reputation as _rep

# audience: the thinking members the brief must precede
COUNCIL_AUDIENCE = ("Atlas", "Analyst", "Strategist", "Skeptic")

_WORD = re.compile(r"[\w฀-๿]+")
_STOP = {"the", "and", "for", "with", "should", "house", "into", "this", "that",
         "are", "was", "will", "from", "our", "we", "to", "of", "in", "on", "a",
         "go", "be", "is", "it", "now", "วัน", "การ", "ของ", "และ", "ให้"}


def _terms(s: str) -> List[str]:
    return [t.lower() for t in _WORD.findall(s or "")
            if len(t) > 2 and t.lower() not in _STOP]


def _gist(text: str, n: int = 110) -> str:
    """Compress a verdict/statement to a short lesson gist (never the raw record)."""
    t = re.sub(r"\s+", " ", (text or "").strip().strip('"{}'))
    return (t[:n] + "…") if len(t) > n else t


# ──────────────────────────────────────────────────────────────────────────────
# Mine predictions of the recalled sessions (lessons / errors / patterns)
# ──────────────────────────────────────────────────────────────────────────────
def _predictions_for(c, session_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    if not session_ids:
        return out
    q = ",".join("?" * len(session_ids))
    for r in c.execute(
            f"SELECT session_id, statement, status, metric, direction, invalidation, agent "
            f"FROM predictions WHERE session_id IN ({q})", session_ids).fetchall():
        out.setdefault(r["session_id"], []).append(dict(r))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Build the brief
# ──────────────────────────────────────────────────────────────────────────────
def build_brief(directive: str, path: Optional[str] = None,
                now: Optional[float] = None, k: int = 8) -> Dict[str, Any]:
    now = now if now is not None else time.time()
    cases = _cm.recall(directive, limit=k, path=path, now=now)

    # empty-history guard: never invent a past
    if not cases:
        return _empty_brief(directive, now)

    ids = [c["id"] for c in cases]
    with _db.connect(path) as conn:
        preds = _predictions_for(conn, ids)

    coverage = Counter(c["validity"] for c in cases)
    validated = [c for c in cases if c["validity"] == _rq.VALIDATED]
    disproven = [c for c in cases if c["validity"] == _rq.DISPROVEN]
    outdated = [c for c in cases if c["validity"] == _rq.OUTDATED]
    unknown = [c for c in cases if c["validity"] == _rq.UNKNOWN]

    brief = {
        "directive": directive,
        "generated_at": now,
        "n_cases": len(cases),
        "coverage": dict(coverage),
        "relevant_historical_cases": _cases(cases),
        "validated_lessons": _validated_lessons(validated),
        "failed_lessons": _failed_lessons(disproven, preds),
        "common_patterns": _common_patterns(cases),
        "repeated_errors": _repeated_errors(disproven, preds),
        "confidence_trends": _confidence_trends(cases),
        "agent_performance_trends": _agent_trends(cases, path),
        "known_blind_spots": _blind_spots(cases, unknown, outdated),
    }
    brief["recommended_focus_areas"] = _focus_areas(brief, disproven, unknown)
    brief["executive_summary"] = _exec_summary(directive, cases, brief)
    return brief


def _empty_brief(directive: str, now: float) -> Dict[str, Any]:
    return {
        "directive": directive, "generated_at": now, "n_cases": 0, "coverage": {},
        "executive_summary": "No prior deliberations on this topic. THE HOUSE has no "
                             "history here — reason from first principles and treat this "
                             "as a new baseline to be recorded and reviewed.",
        "relevant_historical_cases": [],
        "validated_lessons": [], "failed_lessons": [], "common_patterns": [],
        "repeated_errors": [], "confidence_trends": {"status": "no_history"},
        "agent_performance_trends": [], "recommended_focus_areas": [
            "Establish a falsifiable forecast with an explicit invalidation condition "
            "so this baseline can be graded later."],
        "known_blind_spots": ["The entire topic is untested by the House — every "
                              "conclusion here is unvalidated."],
    }


# ── sections ──────────────────────────────────────────────────────────────────
def _cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Synthesized references — gist + judgement, NOT the raw session."""
    out = []
    for c in cases:
        out.append({
            "ref": c["id"],
            "validity": c["validity"],
            "warning": c.get("warning", False),
            "gist": _gist(c.get("verdict", "")),
            "accuracy": c.get("accuracy_score"),
            "why_relevant": c.get("justification", {}).get("why_recalled", ""),
        })
    return out


def _validated_lessons(validated: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for c in validated:
        g = _gist(c.get("verdict", ""))
        if g:
            out.append({"lesson": g, "from_case": c["id"], "accuracy": c.get("accuracy_score")})
    return out


def _failed_lessons(disproven: List[Dict[str, Any]],
                    preds: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out = []
    for c in disproven:
        why = ""
        for p in preds.get(c["id"], []):
            if p.get("invalidation"):
                why = _gist(p["invalidation"], 80); break
        out.append({
            "lesson": _gist(c.get("verdict", "")),
            "why_failed": why or "graded predictions resolved incorrect",
            "from_case": c["id"],
        })
    return out


def _common_patterns(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recurring themes across the recalled set (term + verdict-direction frequency)."""
    terms = Counter()
    for c in cases:
        terms.update(set(_terms(c.get("directive", "")) + _terms(c.get("verdict", ""))))
    patterns = [{"pattern": t, "occurrences": n} for t, n in terms.most_common(12) if n >= 2]
    # validity skew is itself a pattern
    vc = Counter(c["validity"] for c in cases)
    for state, n in vc.items():
        if n >= 2:
            patterns.append({"pattern": f"{n} prior cases ended {state}", "occurrences": n})
    return patterns[:10]


def _repeated_errors(disproven: List[Dict[str, Any]],
                     preds: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Failures the House has made MORE THAN ONCE — the costliest thing to surface."""
    signatures = Counter()
    examples: Dict[str, str] = {}
    for c in disproven:
        for p in preds.get(c["id"], []):
            if p["status"] == "incorrect":
                metric = (p.get("metric") or "?").lower()
                direction = (p.get("direction") or "?").lower()
                sig = f"predicted {metric} {direction}"
                signatures[sig] += 1
                examples.setdefault(sig, _gist(p.get("statement", ""), 70))
        # also a topic-level repeated error: same directive theme failing
    out = [{"error": sig, "occurrences": n, "example": examples.get(sig, "")}
           for sig, n in signatures.most_common() if n >= 2]
    # if no metric-level repeat, surface a topic-level one when >=2 disproven cases
    if not out and len(disproven) >= 2:
        out.append({"error": "the House has reached an incorrect verdict on this topic "
                             f"{len(disproven)} times", "occurrences": len(disproven),
                    "example": _gist(disproven[0].get("verdict", ""), 70)})
    return out


def _confidence_trends(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    graded = [c for c in cases if c.get("accuracy_score") is not None]
    if not graded:
        return {"status": "insufficient_graded_history"}
    stated = sum((c.get("confidence") or 0.0) for c in graded) / len(graded)
    realized = sum(c["accuracy_score"] for c in graded) / len(graded)
    gap = stated - realized
    # direction: newer vs older stated confidence
    ordered = sorted(graded, key=lambda c: c.get("ts", 0.0))
    half = max(1, len(ordered) // 2)
    older = sum((c.get("confidence") or 0.0) for c in ordered[:half]) / half
    newer = sum((c.get("confidence") or 0.0) for c in ordered[-half:]) / half
    direction = "rising" if newer > older + 0.05 else "falling" if newer < older - 0.05 else "flat"
    note = ("the House has been OVERCONFIDENT here — stated confidence exceeded realised accuracy"
            if gap > 0.15 else
            "the House has been UNDERCONFIDENT here" if gap < -0.15 else
            "the House has been roughly calibrated here")
    return {"stated_avg": round(stated, 3), "realized_accuracy": round(realized, 3),
            "calibration_gap": round(gap, 3), "direction": direction, "note": note}


def _agent_trends(cases: List[Dict[str, Any]], path: Optional[str]) -> List[Dict[str, Any]]:
    agents = []
    seen = set()
    for c in cases:
        for a in c.get("participants", []):
            if a and a not in seen:
                seen.add(a)
    out = []
    for a in seen:
        rep = _rep.get(a, path)
        if not rep or (rep["wins"] + rep["losses"] + rep["draws"]) == 0:
            continue
        skill = round(rep.get("alpha", 1.0) / (rep.get("alpha", 1.0) + rep.get("beta", 1.0)), 3)
        cal = rep.get("calibration", 0.0)
        reliable = "reliable" if (skill >= 0.6 and cal >= 0.6) else \
                   "unreliable" if (skill < 0.45 or (rep.get("brier_n", 0) and cal < 0.4)) else "mixed"
        out.append({"agent": a, "skill": skill, "calibration": round(cal, 3),
                    "accuracy_rate": rep.get("accuracy_rate", 0.0), "reliability": reliable})
    out.sort(key=lambda x: -x["skill"])
    return out


def _blind_spots(cases: List[Dict[str, Any]], unknown: List[Dict[str, Any]],
                 outdated: List[Dict[str, Any]]) -> List[str]:
    spots: List[str] = []
    if unknown:
        spots.append(f"{len(unknown)} recalled case(s) are UNTESTED (no graded outcome) — "
                     "their conclusions are unproven.")
    if outdated:
        spots.append(f"{len(outdated)} recalled case(s) are OUTDATED (superseded or stale) — "
                     "do not treat as current authority.")
    # data gaps mined from evidence summaries (analyst recorded gaps)
    gaps = []
    for c in cases:
        es = c.get("evidence_summary", "") or ""
        m = re.search(r"data_gaps?:\s*(\[[^\]]*\]|[^|]+)", es, re.I)
        if m:
            gaps.append(_gist(m.group(1), 80))
    for g in gaps[:3]:
        spots.append(f"Previously-flagged data gap: {g}")
    if not spots:
        spots.append("No explicit blind spots flagged in prior cases — remain alert for "
                     "unstated assumptions.")
    return spots


def _focus_areas(brief: Dict[str, Any], disproven, unknown) -> List[str]:
    areas: List[str] = []
    for e in brief["repeated_errors"][:2]:
        areas.append(f"Do NOT repeat: {e['error']} (failed {e['occurrences']}×). Require a "
                     "fresh invalidation condition before reasserting it.")
    ct = brief["confidence_trends"]
    if isinstance(ct, dict) and ct.get("calibration_gap", 0) > 0.15:
        areas.append("Counter known overconfidence: demand evidence and state uncertainty explicitly.")
    if unknown:
        areas.append("Validate the untested prior conclusions before relying on them.")
    weak = [a for a in brief["agent_performance_trends"] if a["reliability"] == "unreliable"]
    if weak:
        areas.append("Weight contributions from agents with weak track records on this topic "
                     f"({', '.join(a['agent'] for a in weak[:3])}) more skeptically.")
    if not areas:
        areas.append("History is consistent here — confirm conditions still hold, then proceed.")
    return areas


def _exec_summary(directive: str, cases: List[Dict[str, Any]], brief: Dict[str, Any]) -> str:
    cov = brief["coverage"]
    parts = [f"{len(cases)} prior deliberation(s) bear on this directive"]
    bits = []
    for state in (_rq.VALIDATED, _rq.DISPROVEN, _rq.OUTDATED, _rq.UNKNOWN, _rq.PARTIALLY_VALID):
        if cov.get(state):
            bits.append(f"{cov[state]} {state.lower()}")
    if bits:
        parts.append("(" + ", ".join(bits) + ")")
    head = " ".join(parts) + "."
    if brief["repeated_errors"]:
        head += f" ⚠ Repeated error on record: {brief['repeated_errors'][0]['error']}."
    if brief["validated_lessons"]:
        head += f" Established lesson: {brief['validated_lessons'][0]['lesson']}"
    ct = brief["confidence_trends"]
    if isinstance(ct, dict) and ct.get("note"):
        head += f" Calibration: {ct['note']}."
    return head


# ──────────────────────────────────────────────────────────────────────────────
# Render for council injection (compact system message)
# ──────────────────────────────────────────────────────────────────────────────
def format_brief_for_council(brief: Dict[str, Any]) -> str:
    if not brief or brief.get("n_cases", 0) == 0:
        return ("## HISTORICAL BRIEF (THE HOUSE memory)\n" +
                brief.get("executive_summary", "No prior history on this topic."))
    L = ["## HISTORICAL BRIEF — THE HOUSE has deliberated on this before",
         "(synthesized from the House's own graded history — do not rediscover these lessons)",
         "", f"### Executive Summary\n{brief['executive_summary']}"]
    if brief["validated_lessons"]:
        L.append("\n### Validated Lessons (proved correct)")
        L += [f"  ✓ {x['lesson']}" for x in brief["validated_lessons"][:4]]
    if brief["failed_lessons"]:
        L.append("\n### Failed Lessons (proved WRONG — do not repeat)")
        L += [f"  ✗ {x['lesson']}  — failed: {x['why_failed']}" for x in brief["failed_lessons"][:4]]
    if brief["repeated_errors"]:
        L.append("\n### Repeated Errors (more than once)")
        L += [f"  ⚠ {x['error']} ({x['occurrences']}×)" for x in brief["repeated_errors"][:3]]
    if brief["common_patterns"]:
        L.append("\n### Common Patterns")
        L.append("  " + ", ".join(f"{p['pattern']} ({p['occurrences']})" for p in brief["common_patterns"][:6]))
    ct = brief["confidence_trends"]
    if isinstance(ct, dict) and ct.get("note"):
        L.append(f"\n### Confidence Trend\n  {ct['note']} (stated {ct.get('stated_avg')} vs realised {ct.get('realized_accuracy')}, {ct.get('direction')}).")
    if brief["agent_performance_trends"]:
        L.append("\n### Agent Performance (on related history)")
        L += [f"  {a['agent']}: skill {a['skill']}, calibration {a['calibration']} — {a['reliability']}"
              for a in brief["agent_performance_trends"][:6]]
    if brief["known_blind_spots"]:
        L.append("\n### Known Blind Spots")
        L += [f"  • {s}" for s in brief["known_blind_spots"][:4]]
    if brief["recommended_focus_areas"]:
        L.append("\n### Recommended Focus")
        L += [f"  → {s}" for s in brief["recommended_focus_areas"][:4]]
    L.append("\nReason WITH this history. Do not repeat disproven reasoning; do not "
             "rediscover validated lessons; surface any new uncertainty explicitly.")
    return "\n".join(L)
