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


def _find_invalidation(*texts: str) -> str:
    for t in texts:
        m = _INVAL_RE.search(t or "")
        if m:
            s = max(0, m.start() - 8)
            return t[s:m.end() + 40].strip().strip('"{}')
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


def _claim_statement(role: str, block: Any) -> str:
    if isinstance(block, dict):
        for k in ("scenario", "base_case", "forecast", "prediction", "outlook",
                  "leverage_point", "asymmetric_bet", "known", "early_warning_1"):
            if block.get(k):
                v = block[k]
                return (", ".join(map(str, v)) if isinstance(v, list) else str(v))
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
