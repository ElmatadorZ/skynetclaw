"""
agent_reputation.py — PART 4 / M1.5 (C3): Bayesian Reputation for THE HOUSE
==========================================================================
Replaces unbounded score accumulation with a calibrated, recency-weighted,
bounded skill estimate.

Model: Beta-Bernoulli with exponential forgetting.
  - Each agent holds (alpha, beta). Posterior skill = alpha/(alpha+beta) ∈ [0,1].
  - Before each update, evidence is FORGOTTEN toward the prior by time since the
    agent's last graded outcome: alpha,beta → 1 + (x-1)·0.5^(dt/half_life).
    Recent performance dominates; old performance fades; idle agents revert to
    "unknown" (0.5), never to a stale high score.
  - Calibration tracked via Brier score on stated confidence vs realised outcome.
    Overconfidence (high confidence, wrong) lowers calibration and is penalised.
  - score = 1000·skill·(1 − 0.3·(1−calibration))  →  BOUNDED in [0, 1000].
    50/50 prior with no data = 500 (neutral). No path inflates without bound.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional

import institutional_db as _db

HOUSE = [
    "Elite Commander", "Atlas", "Analyst", "Strategist", "Skeptic", "Auditor",
    "Governor", "Architect", "Scout", "Storyteller", "Concierge", "Forecaster",
    "Sentinel", "Executor",
]

_NEUTRAL_SCORE = 500.0          # skill 0.5 → unknown
_HALF_LIFE_DAYS = 90.0
_OUTCOME_VAL = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
_CONSISTENCY_WINDOW = 20        # recent outcomes only (recency)


# ── Quality scorers (unchanged contract) ──────────────────────────────────────
_NUM_RE = re.compile(r"\d")
_SRC_RE = re.compile(r"https?://|\bsource\b|\bcit|\baccording to\b|\[\d+\]", re.I)
_UNC_RE = re.compile(r"\b(uncertain|unknown|assum|estimat|likely|probab|confidence|may|might|risk)\b", re.I)
_SCEN_RE = re.compile(r"\b(bull|bear|base case|scenario|if .* then|downside|upside)\b", re.I)
_INVAL_RE = re.compile(r"\b(invalidat|falsif|breaks if|fails if|wrong if|stop[- ]?loss)\b", re.I)
_CRIT_RE = re.compile(r"\b(however|but|risk|weak|flaw|counter|objection|disagree|fails|gap)\b", re.I)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_evidence(text: str) -> float:
    t = text or ""
    if not t.strip(): return 0.0
    s = 0.30
    if _NUM_RE.search(t): s += 0.30
    if _SRC_RE.search(t): s += 0.40
    if len(t) > 240:      s += 0.10
    return _clamp(s)


def score_critique(text: str) -> float:
    t = text or ""
    if not t.strip(): return 0.0
    return _clamp(0.2 + 0.2 * len(_CRIT_RE.findall(t)))


def score_forecast(text: str) -> float:
    t = text or ""
    if not t.strip(): return 0.0
    s = 0.1
    if _SCEN_RE.search(t):  s += 0.35
    if _INVAL_RE.search(t): s += 0.40
    if _UNC_RE.search(t):   s += 0.15
    return _clamp(s)


# ── STRUCTURE-FIRST scorers (language-bias fix, audit 2026-07-10) ─────────────
# The text scorers above look for ENGLISH words; identical content scored
# critique 0.4 in English vs 0.2 in Thai — which is why every Thai council
# session's confidence sat at ~0.21. A member that DECLARES the structure
# (fatal_assumption, dissent bool, prediction.invalidation, regime probs)
# has done the epistemic work in any language. Regex stays as the fallback
# for unstructured blocks. Same principle as the prediction extractor:
# protocol over parsing.

def _nonempty(v) -> bool:
    if isinstance(v, list):
        return any(str(x).strip() for x in v)
    return bool(str(v or "").strip())


def score_evidence_block(block) -> float:
    t = json.dumps(block, ensure_ascii=False) if isinstance(block, dict) else str(block or "")
    s = score_evidence(t)
    if isinstance(block, dict):
        if _nonempty(block.get("known")):    s = max(s, 0.6)
        if _nonempty(block.get("known")) and _nonempty(block.get("inferred")):
            s = max(s, 0.7)
    return _clamp(s)


def score_critique_block(block) -> float:
    t = json.dumps(block, ensure_ascii=False) if isinstance(block, dict) else str(block or "")
    s = score_critique(t)
    if isinstance(block, dict):
        st = 0.0
        if _nonempty(block.get("fatal_assumption")):          st += 0.4
        if _nonempty(block.get("counter_evidence_to_seek")):  st += 0.2
        if _nonempty(block.get("rebuild_trigger")):           st += 0.2
        if isinstance(block.get("dissent"), bool):            st += 0.2  # explicit stance
        s = max(s, _clamp(st))
    return _clamp(s)


def score_forecast_block(block) -> float:
    t = json.dumps(block, ensure_ascii=False) if isinstance(block, dict) else str(block or "")
    s = score_forecast(t)
    if isinstance(block, dict):
        st = 0.1 if block else 0.0
        regimes = [block.get(k) for k in ("base_case", "positive_regime", "negative_regime")]
        if any(isinstance(r, dict) and r.get("outcome") for r in regimes):
            st += 0.35                                        # declared scenarios
        pred = block.get("prediction") if isinstance(block.get("prediction"), dict) else {}
        if _nonempty(pred.get("invalidation")):
            st += 0.40                                        # falsifiable, any language
        if _nonempty(block.get("early_warning_1")) or _nonempty(block.get("early_warning_2")):
            st += 0.15                                        # named uncertainty signals
        s = max(s, _clamp(st))
    return _clamp(s)


# ── Derived metrics ───────────────────────────────────────────────────────────
def _skill(alpha: float, beta: float) -> float:
    return alpha / (alpha + beta) if (alpha + beta) > 0 else 0.5


def _calibration(brier_sum: float, brier_n: float) -> float:
    return _clamp(1.0 - (brier_sum / brier_n)) if brier_n > 0 else 0.0


def _score(skill: float, calibration: float, brier_n: float) -> float:
    base = 1000.0 * skill
    if brier_n > 0:
        base *= (1.0 - 0.3 * (1.0 - calibration))   # overconfidence penalty
    return round(base, 2)


def _forget(alpha: float, beta: float, last_at: float, now: float,
            half_life: float) -> tuple:
    if last_at and last_at > 0 and half_life > 0:
        dt = max(0.0, (now - last_at) / 86400.0)
        f = 0.5 ** (dt / half_life)
        alpha = 1.0 + (alpha - 1.0) * f
        beta = 1.0 + (beta - 1.0) * f
    return alpha, beta


# ── Persistence ───────────────────────────────────────────────────────────────
def ensure_agent(agent: str, path: Optional[str] = None) -> None:
    _db.init_once(path)
    with _db.connect(path) as c:
        if not c.execute("SELECT 1 FROM agent_reputation WHERE agent=?", (agent,)).fetchone():
            c.execute("INSERT INTO agent_reputation (agent, score, alpha, beta, updated_at) "
                      "VALUES (?,?,?,?,?)", (agent, _NEUTRAL_SCORE, 1.0, 1.0, time.time()))
            c.commit()


def seed_house(path: Optional[str] = None) -> None:
    for a in HOUSE:
        ensure_agent(a, path)


def _log_history(c, agent: str, score: float, acc: float, consistency: float, event: str) -> None:
    hid = "rh_" + hashlib.sha1(f"{agent}:{event}:{time.time()}:{score}".encode()).hexdigest()[:14]
    c.execute("INSERT OR REPLACE INTO reputation_history "
              "(id, agent, ts, score, accuracy_rate, consistency, event) VALUES (?,?,?,?,?,?,?)",
              (hid, agent, time.time(), float(score), float(acc), float(consistency), event))


def compute_consistency(agent: str, path: Optional[str] = None) -> float:
    """1 − normalised variance of this agent's RECENT outcomes (windowed = recency)."""
    from statistics import pstdev
    with _db.connect(path) as c:
        rows = c.execute(
            "SELECT status FROM predictions WHERE agent=? AND status!='pending' "
            "ORDER BY evaluated_at DESC LIMIT ?", (agent, _CONSISTENCY_WINDOW)).fetchall()
    vals = [_OUTCOME_VAL[r["status"]] for r in rows if r["status"] in _OUTCOME_VAL]
    if len(vals) < 2:
        return 0.0
    return round(_clamp(1.0 - pstdev(vals) / 0.5), 4)


def record_contribution(agent: str, evidence: float, critique: float,
                        forecast: float, path: Optional[str] = None) -> None:
    """Quality signal only — does NOT touch score/last_outcome_at (decoupled from
    the outcome clock so decay stays keyed to real graded outcomes)."""
    ensure_agent(agent, path)
    with _db.connect(path) as c:
        r = c.execute("SELECT n_predictions, evidence_quality, critique_quality, "
                      "forecast_quality FROM agent_reputation WHERE agent=?", (agent,)).fetchone()
        n = (r["n_predictions"] or 0) + 1
        w = min(n, 20)
        def roll(old, new): return (old * (w - 1) + new) / w
        c.execute("UPDATE agent_reputation SET evidence_quality=?, critique_quality=?, "
                  "forecast_quality=? WHERE agent=?",
                  (round(roll(r["evidence_quality"], evidence), 4),
                   round(roll(r["critique_quality"], critique), 4),
                   round(roll(r["forecast_quality"], forecast), 4), agent))
        c.commit()


def apply_outcome(agent: str, result: str, confidence: float = 0.0, weight: float = 1.0,
                  now: Optional[float] = None, half_life_days: float = _HALF_LIFE_DAYS,
                  path: Optional[str] = None) -> Dict[str, Any]:
    """Bayesian update with forgetting + calibration. SINGLE transaction (atomic)."""
    ensure_agent(agent, path)
    now = now if now is not None else time.time()
    a = _OUTCOME_VAL.get(result, 0.5)
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM agent_reputation WHERE agent=?", (agent,)).fetchone()
        # forget stale evidence relative to last graded outcome (recency)
        alpha, beta = _forget(r["alpha"] or 1.0, r["beta"] or 1.0,
                              r["last_outcome_at"] or 0.0, now, half_life_days)
        alpha += weight * a
        beta += weight * (1.0 - a)
        # calibration: only when a confidence was actually stated (>0)
        brier_sum, brier_n = r["brier_sum"] or 0.0, r["brier_n"] or 0.0
        if confidence and confidence > 0:
            brier_sum += weight * (confidence - a) ** 2
            brier_n += weight
        wins, losses, draws = r["wins"], r["losses"], r["draws"]
        if result == "correct":     wins += 1
        elif result == "incorrect": losses += 1
        else:                        draws += 1
        n_pred = (r["n_predictions"] or 0) + 1
        n_corr = (r["n_correct"] or 0) + (1 if result == "correct" else 0)
        acc = n_corr / n_pred if n_pred else 0.0
        skill = _skill(alpha, beta)
        cal = _calibration(brier_sum, brier_n)
        score = _score(skill, cal, brier_n)
        # consistency over recent window (read within txn is fine)
        from statistics import pstdev
        recent = [_OUTCOME_VAL[x["status"]] for x in c.execute(
            "SELECT status FROM predictions WHERE agent=? AND status!='pending' "
            "ORDER BY evaluated_at DESC LIMIT ?", (agent, _CONSISTENCY_WINDOW)).fetchall()
            if x["status"] in _OUTCOME_VAL]
        consistency = round(_clamp(1.0 - pstdev(recent) / 0.5), 4) if len(recent) >= 2 else 0.0
        c.execute(
            "UPDATE agent_reputation SET score=?, alpha=?, beta=?, wins=?, losses=?, draws=?, "
            "n_predictions=?, n_correct=?, accuracy_rate=?, consistency=?, brier_sum=?, brier_n=?, "
            "calibration=?, last_outcome_at=?, updated_at=? WHERE agent=?",
            (score, round(alpha, 5), round(beta, 5), wins, losses, draws, n_pred, n_corr,
             round(acc, 4), consistency, round(brier_sum, 5), round(brier_n, 3),
             round(cal, 4), now, now, agent))
        _log_history(c, agent, score, acc, consistency, "outcome")
        c.commit()
    return {"agent": agent, "score": score, "skill": round(skill, 4), "calibration": round(cal, 4),
            "wins": wins, "losses": losses, "draws": draws, "accuracy_rate": round(acc, 4),
            "consistency": consistency}


def apply_decay(agent: str, now: Optional[float] = None,
                half_life_days: float = _HALF_LIFE_DAYS, path: Optional[str] = None) -> Dict[str, Any]:
    """Forget stale evidence (keyed to last_outcome_at, NOT updated_at). Idle skill
    reverts toward the 0.5 prior — the House stops trusting old proof."""
    ensure_agent(agent, path)
    now = now if now is not None else time.time()
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM agent_reputation WHERE agent=?", (agent,)).fetchone()
        alpha, beta = _forget(r["alpha"] or 1.0, r["beta"] or 1.0,
                              r["last_outcome_at"] or 0.0, now, half_life_days)
        skill = _skill(alpha, beta)
        cal = _calibration(r["brier_sum"] or 0.0, r["brier_n"] or 0.0)
        score = _score(skill, cal, r["brier_n"] or 0.0)
        # decay advances the forgetting clock so it isn't re-applied next call
        c.execute("UPDATE agent_reputation SET score=?, alpha=?, beta=?, last_outcome_at=?, "
                  "updated_at=? WHERE agent=?",
                  (score, round(alpha, 5), round(beta, 5), now, now, agent))
        _log_history(c, agent, score, r["accuracy_rate"] or 0.0, r["consistency"] or 0.0, "decay")
        c.commit()
    return {"agent": agent, "score": score, "skill": round(skill, 4)}


def decay_all(half_life_days: float = _HALF_LIFE_DAYS, now: Optional[float] = None,
              path: Optional[str] = None) -> int:
    _db.init_once(path)
    with _db.connect(path) as c:
        agents = [r["agent"] for r in c.execute("SELECT agent FROM agent_reputation")]
    for a in agents:
        apply_decay(a, now=now, half_life_days=half_life_days, path=path)
    return len(agents)


def reputation_decay_handler(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"reschedule_in": 7 * 86400.0, "decayed_agents": decay_all()}


def get(agent: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        r = c.execute("SELECT * FROM agent_reputation WHERE agent=?", (agent,)).fetchone()
        return dict(r) if r else None


def history(agent: str, limit: int = 50, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM reputation_history WHERE agent=? ORDER BY ts DESC LIMIT ?",
            (agent, limit))]


def scorecard(agent: str, path: Optional[str] = None) -> Dict[str, Any]:
    rep = get(agent, path) or {}
    hist = history(agent, limit=20, path=path)
    scores = [h["score"] for h in hist]
    trend = "flat"
    if len(scores) >= 2:
        trend = "rising" if scores[0] > scores[-1] + 1 else "falling" if scores[0] < scores[-1] - 1 else "flat"
    return {"agent": agent, "reputation": rep, "trend": trend,
            "skill": round(_skill(rep.get("alpha", 1.0), rep.get("beta", 1.0)), 4),
            "history_points": len(hist), "history": hist}


def leaderboard(path: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM agent_reputation ORDER BY score DESC, accuracy_rate DESC LIMIT ?",
            (limit,))]


def best_and_worst(path: Optional[str] = None) -> Dict[str, Any]:
    lb = leaderboard(path, limit=100)
    rated = [a for a in lb if (a["wins"] + a["losses"] + a["draws"]) > 0]
    return {"best": rated[:3], "worst": list(reversed(rated))[:3] if rated else []}
