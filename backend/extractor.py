"""
extractor.py — M1 + M1.5 (C1): Prediction Extractor with attribution integrity
==============================================================================
Closes the learning loop AND attributes every prediction to the agent(s) who
actually made it. The originating agent is derived from WHICH council block the
falsifiable claim came from — never hard-coded. Participating agents are those
who supplied the invalidation or evidence. Constitution R4 still enforced: a
claim with no invalidation condition is unfalsifiable and rejected.

Every extracted prediction carries:
  originating_agent · participants · confidence · evidence_source

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import outcome_tracker as _out

# Council role -> Council member (the actual agent on record)
ROLE_AGENT = {
    "analyst": "Analyst", "strategist": "Strategist", "skeptic": "Skeptic",
    "forecaster": "Forecaster", "executor": "Executor", "storyteller": "Storyteller",
    "atlas": "Atlas", "auditor": "Auditor", "governor": "Governor",
    "architect": "Architect", "scout": "Scout", "sentinel": "Sentinel",
    "concierge": "Concierge", "commander": "Elite Commander",
}
# Roles whose blocks can contain a forward-looking, falsifiable claim
_FORWARD_ROLES = ("forecaster", "atlas", "strategist", "analyst", "skeptic")

_INVAL_RE = re.compile(
    r"(invalidat\w*|falsif\w*|breaks? if|fails? if|wrong if|stop[- ]?loss|"
    r"below\s+[\d.,]+|above\s+[\d.,]+|unless\b)", re.I)
_UP_RE = re.compile(r"\b(up|ris\w*|rall\w*|bull\w*|higher|increas\w*|grow\w*|expand\w*|reclaim\w*|breakout|surg\w*)\b", re.I)
_DOWN_RE = re.compile(r"\b(down|fall\w*|drop\w*|bear\w*|lower|decreas\w*|declin\w*|contract\w*|crash\w*|breakdown|selloff)\b", re.I)
_FWD_RE = re.compile(r"\b(will|expect|forecast|scenario|project|into\b|by\s+\d|next\b|outlook|target|reach\w*)\b", re.I)
_METRIC_RE = re.compile(
    r"\b(BTC|bitcoin|ETH|gold|XAU|silver|oil|WTI|brent|DXY|SPX|NDX|US10Y|yields?|"
    r"copper|USDJPY|EURUSD|liquidity|inflation|rates?)\b", re.I)
_SRC_RE = re.compile(r"https?://|\[\d+\]|\bsource\b|\bdata\b|\bper\b|\baccording\b", re.I)
_YEAR_RE = re.compile(r"\b(\d{1,2})\s*(year|yr|ปี)", re.I)
_MONTH_RE = re.compile(r"\b(\d{1,2})\s*(month|เดือน)", re.I)


def _txt(block: Any) -> str:
    return json.dumps(block, ensure_ascii=False) if isinstance(block, dict) else str(block or "")


# Debris left when a character window is sliced out of serialised JSON: a
# dangling key fragment, a stray quote-colon, a trailing comma-brace.
_JSON_DEBRIS = re.compile(r'^[^"\w฀-๿]*(?:[\w]*"\s*:\s*[\d.]+\s*,\s*)?'
                          r'"?[\w_]*"?\s*:\s*"?')


def _clean_fragment(s: str) -> str:
    """Salvage a human-readable condition from a slice of serialised text.

    `_txt()` renders a dict with json.dumps, so any window cut out of it lands
    mid-token and yields things like `s": 7, "invalidation": "user declines`.
    Two such rows reached the predictions table and could never have been judged
    by anyone. Strip the JSON scaffolding and end on a real boundary.
    """
    s = (s or "").strip()
    s = _JSON_DEBRIS.sub("", s)
    s = s.strip().strip('",{}[]:').strip()
    # Stop at the next key/value boundary rather than running into the next field.
    cut = re.search(r'"\s*,\s*"[\w_]+"\s*:', s)
    if cut:
        s = s[:cut.start()]
    return s.strip().strip('",{}[]').strip()


def _find_invalidation(*texts: str) -> str:
    """The condition that would prove the claim wrong.

    Reads the field structurally when the text is JSON — slicing a window out of
    serialised data is how corrupt conditions got recorded in the first place.
    """
    for t in texts:
        t = t or ""
        if not t:
            continue
        # Structured first: if this is JSON, take the field, not a substring.
        stripped = t.lstrip()
        if stripped[:1] in "{[":
            try:
                obj = json.loads(t)
            except Exception:
                obj = None
            found = _invalidation_from_obj(obj)
            if found:
                return found[:200]

        m = _INVAL_RE.search(t)
        if m:
            frag = _clean_fragment(t[m.end():m.end() + 220])
            if len(frag) < 8:  # nothing meaningful followed the label
                frag = _clean_fragment(t[max(0, m.start() - 8):m.end() + 220])
            if len(frag) >= 8:
                return frag[:200]
    return ""


def _invalidation_from_obj(obj: Any, depth: int = 0) -> str:
    """Walk a parsed structure for an invalidation field, at any nesting."""
    if depth > 4 or obj is None:
        return ""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _INVAL_RE.search(str(k)) and isinstance(v, str) and v.strip():
                return v.strip()
        for v in obj.values():
            got = _invalidation_from_obj(v, depth + 1)
            if got:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = _invalidation_from_obj(v, depth + 1)
            if got:
                return got
    return ""


def _direction(text: str) -> str:
    up, down = bool(_UP_RE.search(text)), bool(_DOWN_RE.search(text))
    if up and not down: return "up"
    if down and not up: return "down"
    if up and down:     return "mixed"
    return "flat"


def _metric(text: str) -> str:
    m = _METRIC_RE.search(text)
    return m.group(0) if m else ""


def _horizon(text: str) -> str:
    y = _YEAR_RE.search(text)
    if y: return "180" if int(y.group(1)) >= 1 else "90"
    mo = _MONTH_RE.search(text)
    if mo:
        n = int(mo.group(1)); return "30" if n <= 1 else "90" if n <= 3 else "180"
    return "90"


# Where the readable claim lives inside a nested scenario object.
_CLAIM_KEYS = ("outcome", "scenario", "statement", "claim", "text", "description")


def _readable(v: Any) -> str:
    """A claim a person can read, or "" — never a stringified object.

    `map(str, ...)` over a list of scenario dicts produced Python reprs like
    `{'prob': 0.55, 'outcome': '...'}` and staked them as the claim. A prediction
    nobody can read is a prediction nobody can judge, so it must be rejected at
    the gate rather than recorded and left to rot as `pending`.
    """
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        for k in _CLAIM_KEYS:
            got = v.get(k)
            if isinstance(got, str) and got.strip():
                return got.strip()
        return ""
    if isinstance(v, list):
        parts = [p for p in (_readable(x) for x in v) if p]
        return ", ".join(parts)
    if isinstance(v, (int, float)):
        return str(v)
    return ""


def _claim_statement(role: str, block: Any) -> str:
    if isinstance(block, dict):
        for k in ("scenario", "base_case", "forecast", "prediction", "outlook",
                  "leverage_point", "asymmetric_bet", "known", "early_warning_1"):
            if block.get(k):
                got = _readable(block[k])
                if got:
                    return got
        return ""   # structured but unreadable → skipped, never stringified
    return _txt(block)[:160]


_HORIZONS = ("7", "30", "90", "180")


def _structured_predictions(verdict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prefer the council's own structured `prediction` blocks (protocol over
    parsing). Members declare statement/direction/metric/horizon/invalidation as
    JSON fields, so extraction is language-agnostic — the regex path below is
    English-only and silently dropped every Thai deliberation (16 sessions,
    0 predictions). Constitution R4 still binds: no invalidation → rejected."""
    out: List[Dict[str, Any]] = []
    for role in _FORWARD_ROLES:
        block = verdict.get(role)
        if not isinstance(block, dict):
            continue
        p = block.get("prediction")
        if not isinstance(p, dict):
            continue
        statement = str(p.get("statement") or "").strip()
        invalidation = str(p.get("invalidation") or "").strip()
        if not statement or not invalidation:
            continue   # unfalsifiable → rejected (R4)
        direction = str(p.get("direction") or "").lower()
        if direction not in ("up", "down", "flat", "mixed"):
            direction = _direction(statement)
        horizon = str(p.get("horizon_days") or "").strip()
        if horizon not in _HORIZONS:
            horizon = _horizon(statement)
        conf = p.get("confidence")
        origin = ROLE_AGENT.get(role, role.title())
        out.append({
            "statement": statement[:300],
            "originating_agent": origin,
            "participants": [origin],
            "invalidation": invalidation[:200],
            "metric": str(p.get("metric") or _metric(statement))[:80],
            "direction": direction,
            "horizon_primary": horizon,
            "confidence": float(conf) if isinstance(conf, (int, float)) else 0.0,
            "evidence_source": f"{origin}:structured",
        })
    return out


def extract_predictions(verdict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return FALSIFIABLE predictions, each attributed to the agent who made it.

    Structured `prediction` blocks are extracted first (language-agnostic);
    then the legacy regex scan over every forward-capable council block. The
    invalidation may be supplied by another member (e.g. the Skeptic) — that
    member becomes a participating agent and the evidence source.
    """
    skeptic_txt = _txt(verdict.get("skeptic"))
    agg = str(verdict.get("aggregate_recommendation") or "")
    out: List[Dict[str, Any]] = list(_structured_predictions(verdict))
    seen = {p["statement"].strip().lower()[:80] for p in out}

    for role in _FORWARD_ROLES:
        block = verdict.get(role)
        if not block:
            continue
        btext = _txt(block)
        # must be a forward-looking claim with a direction or explicit scenario
        if not (_FWD_RE.search(btext) or _UP_RE.search(btext) or _DOWN_RE.search(btext)):
            continue

        # invalidation: prefer this block's own, else the Skeptic's, else aggregate
        own_inval = _find_invalidation(btext)
        ext_inval = _find_invalidation(skeptic_txt, agg)
        invalidation = own_inval or ext_inval
        if not invalidation:
            continue   # unfalsifiable → rejected (Constitution R4)

        statement = _claim_statement(role, block)
        if not statement.strip():
            continue
        key = statement.strip().lower()[:80]
        if key in seen:
            continue
        seen.add(key)

        origin = ROLE_AGENT.get(role, role.title())
        participants = [origin]
        # whoever supplied the invalidation/evidence participates
        evidence_bits = []
        if not own_inval and ext_inval:
            if "Skeptic" not in participants:
                participants.append("Skeptic")
            evidence_bits.append("Skeptic:invalidation")
        if _SRC_RE.search(btext):
            evidence_bits.append(f"{origin}:cited")
        if verdict.get("analyst") and _SRC_RE.search(_txt(verdict.get("analyst"))):
            if "Analyst" not in participants:
                participants.append("Analyst")
            evidence_bits.append("Analyst:data")
        evidence_source = "; ".join(evidence_bits) or "unsourced"

        conf = block.get("confidence") if isinstance(block, dict) else None
        blob = f"{statement} {btext} {agg}"
        out.append({
            "statement": statement[:300],
            "originating_agent": origin,
            "participants": participants,
            "invalidation": invalidation[:200],
            "metric": _metric(blob),
            "direction": _direction(blob),
            "horizon_primary": _horizon(blob),
            "confidence": float(conf) if isinstance(conf, (int, float)) else 0.0,
            "evidence_source": evidence_source,
        })
    return out


# Debris that betrays a mis-parse: a serialised object, or a JSON key fragment
# where a human-readable condition should be.
_LOOKS_SERIALISED = re.compile(r"^\s*[\[{]|'\s*:\s*|\"\w+\"\s*:\s*")


def _rejects(p: Dict[str, Any]) -> str:
    """Why this extracted prediction must not be staked. "" means it is sound."""
    stmt = str(p.get("statement") or "").strip()
    inval = str(p.get("invalidation") or "").strip()
    if len(stmt) < 8:
        return "statement too short to judge"
    if _LOOKS_SERIALISED.search(stmt):
        return "statement is a serialised object, not a readable claim"
    if len(inval) < 8:
        return "invalidation too short to judge"
    if _LOOKS_SERIALISED.search(inval):
        return "invalidation is a fragment of serialised data"
    return ""


def record_from_verdict(verdict: Dict[str, Any], session_id: str = "",
                        made_at: Optional[float] = None,
                        path: Optional[str] = None) -> List[str]:
    """Extract + persist attributed predictions. Returns recorded prediction ids.

    Idempotent per claim: an identical pending statement by the same agent is
    skipped — a re-deliberated mission must not put the same prediction on the
    clock twice (observed 2026-07-10: a double deliberation recorded one
    forecast as two rows → double reputation stake for one claim)."""
    pids: List[str] = []
    for p in extract_predictions(verdict):
        # Constitution R4 already rejects an unfalsifiable claim. A CORRUPT claim
        # is worse: it looks falsifiable, sits on the clock as `pending`, and —
        # because on_outcome() waits for its session to be fully graded — blocks
        # every dissent recorded beside it. Two such rows did exactly that.
        bad = _rejects(p)
        if bad:
            print(f"[Extractor] rejected malformed prediction ({bad}): "
                  f"{str(p.get('statement'))[:70]!r}")
            continue
        try:
            if _out.has_pending(p["statement"][:300], agent=p["originating_agent"], path=path):
                continue
        except Exception:
            pass
        pid = _out.record_prediction(
            statement=p["statement"], agent=p["originating_agent"], session_id=session_id,
            predicted_outcome=p["direction"], invalidation=p["invalidation"],
            confidence=p["confidence"], made_at=made_at, extracted_from=session_id,
            horizon_primary=p["horizon_primary"], metric=p["metric"], direction=p["direction"],
            participants=p["participants"], evidence_source=p["evidence_source"], path=path)
        pids.append(pid)
    return pids
