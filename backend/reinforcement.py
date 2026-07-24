"""
reinforcement.py — OX-REINFORCEMENT-1 CAPABILITY REINFORCEMENT ENGINE
=====================================================================
FIRST PRINCIPLE: knowledge without reinforcement does not evolve. A capability
that consistently improves outcomes should gain influence; one that consistently
harms outcomes should lose it. OX-ATTRIBUTION-1 IDENTIFIED which recalls help
(lift over baseline) but did not INFLUENCE behavior. This engine converts that
attribution into adaptive WEIGHTS that bias capability recall.

It does NOT redesign attribution / control / telemetry / runtime, does NOT
self-initiate, and does NOT create new capability types. It only reads the
attribution report and maintains one new store (capability_weights.json), then
reorders/relabels recalled capabilities by weight.

REINFORCEMENT MODEL:
  positive lift → reinforce   (weight ↑)
  negative lift → demote      (weight ↓, surfaces as a warning)
  neutral lift  → observe     (no significant change)

WEIGHT UPDATE RULES — gradual, bounded, interpretable:
  • weight 1.0 = neutral baseline; >1 trusted, <1 distrusted; clamped [0.5, 1.5]
  • EMA toward a lift-derived target: target = clamp(1 + lift·K), then
    weight += clamp(ALPHA·(target − weight), ±MAX_STEP) — no single mission can
    jump a weight more than MAX_STEP
  • only moves with enough evidence and a real (non-neutral) lift; otherwise observe

CAPABILITY WEIGHT SCHEMA:
  {"capability":"HTML Report Builder","weight":1.25,"lift":0.455,
   "evidence":12,"status":"reinforced"}

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE = Path(__file__).parent / "capability_weights.json"

# interpretable, bounded constants
W_MIN, W_MAX = 0.5, 1.5
W_BASE = 1.0
K = 0.5            # lift → target sensitivity
ALPHA = 0.34       # EMA step (gradual)
MAX_STEP = 0.15    # max weight change per mission (no drastic single-mission move)
MIN_EVIDENCE = 3   # below this, observe only
REINFORCE_AT = 1.10
DEMOTE_AT = 0.90


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _blank(name: str) -> Dict[str, Any]:
    return {"capability": name, "weight": W_BASE, "lift": 0.0, "evidence": 0, "status": "observed"}


# ── store ─────────────────────────────────────────────────────────────────────
def load(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    p = path or _STORE
    try:
        if p.exists():
            return (json.loads(p.read_text(encoding="utf-8")) or {}).get("weights", {})
    except Exception:
        pass
    return {}


def _save(weights: Dict[str, Dict[str, Any]], path: Optional[Path] = None) -> None:
    p = path or _STORE
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "weights": weights}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[Reinforcement] save failed: {e}")


def weight_of(name: str, weights: Optional[Dict[str, Dict[str, Any]]] = None,
              path: Optional[Path] = None) -> float:
    weights = weights if weights is not None else load(path)
    return float((weights.get(name) or {}).get("weight", W_BASE))


# ── the weight update (gradual + bounded) ────────────────────────────────────
def _update_one(old: Dict[str, Any], name: str, lift: float, evidence: int,
                recommendation: str) -> Dict[str, Any]:
    w = float(old.get("weight", W_BASE))
    # observe (no significant change) when evidence is thin or lift is neutral
    if evidence < MIN_EVIDENCE or recommendation in ("neutral", "insufficient_evidence"):
        return {"capability": name, "weight": round(w, 3), "lift": round(lift, 3),
                "evidence": evidence, "status": "observed"}
    target = _clamp(W_BASE + lift * K, W_MIN, W_MAX)
    step = _clamp(ALPHA * (target - w), -MAX_STEP, MAX_STEP)
    w_new = round(_clamp(w + step, W_MIN, W_MAX), 3)
    status = "reinforced" if lift > 0 else "demoted"
    return {"capability": name, "weight": w_new, "lift": round(lift, 3),
            "evidence": evidence, "status": status}


def reinforce(report: Dict[str, Any],
              prior: Optional[Dict[str, Dict[str, Any]]] = None,
              path: Optional[Path] = None, persist: bool = False) -> Dict[str, Dict[str, Any]]:
    """Convert an attribution report into updated capability weights. Pure given
    `prior`; pass persist=True (or call apply via the runtime) to save."""
    weights = dict(prior if prior is not None else load(path))
    caps = (report or {}).get("capabilities", {}) or {}
    for name, st in caps.items():
        old = weights.get(name) or _blank(name)
        weights[name] = _update_one(old, name, float(st.get("lift", 0.0)),
                                    int(st.get("recalled_in", st.get("evidence", 0)) or 0),
                                    st.get("recommendation", "neutral"))
    if persist:
        _save(weights, path)
    return weights


def reinforce_and_save(report: Dict[str, Any], path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    return reinforce(report, path=path, persist=True)


# ── CAPABILITY RECALL — bias the recalled list by weight ─────────────────────
def apply_to_recall(capabilities: List[Dict[str, Any]],
                    weights: Optional[Dict[str, Dict[str, Any]]] = None,
                    path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Bias a recalled capability list: annotate each with its learned weight,
    surface DEMOTED capabilities (weight ≤ DEMOTE_AT) as warnings, and order
    higher-weight capabilities first. Does not add or remove items."""
    weights = weights if weights is not None else load(path)
    out: List[Dict[str, Any]] = []
    for c in capabilities or []:
        rec = weights.get(c.get("name")) or {}
        w = float(rec.get("weight", W_BASE))
        c = dict(c)
        c["weight"] = w
        if w <= DEMOTE_AT and rec.get("status") == "demoted" and c.get("polarity") == "capability":
            c["polarity"] = "warning"            # demoted → surfaces as a caution
            c["demoted"] = True
        out.append(c)
    # higher weight first; warnings (incl. demoted) sink below positive capabilities
    out.sort(key=lambda c: (c.get("polarity") == "capability", c.get("weight", W_BASE)), reverse=True)
    return out


# ── introspection ─────────────────────────────────────────────────────────────
def status(weights: Optional[Dict[str, Dict[str, Any]]] = None,
           path: Optional[Path] = None) -> Dict[str, Any]:
    weights = weights if weights is not None else load(path)
    vals = list(weights.values())
    trusted = sorted([w for w in vals if w["weight"] >= REINFORCE_AT],
                     key=lambda w: w["weight"], reverse=True)
    avoid = sorted([w for w in vals if w["weight"] <= DEMOTE_AT], key=lambda w: w["weight"])
    return {"n": len(vals), "trusted": trusted, "avoid": avoid,
            "reinforced": [w["capability"] for w in vals if w["status"] == "reinforced"],
            "demoted": [w["capability"] for w in vals if w["status"] == "demoted"]}


def summary(weights: Optional[Dict[str, Dict[str, Any]]] = None,
            path: Optional[Path] = None) -> str:
    s = status(weights, path)
    if not s["n"]:
        return "## REINFORCEMENT: no weighted capabilities yet."
    L = [f"## REINFORCEMENT ({s['n']} weighted capabilities):"]
    if s["trusted"]:
        L.append("  TRUST (reinforced): " + ", ".join(
            f"{w['capability']} (w={w['weight']}, lift {w['lift']:+})" for w in s["trusted"][:4]))
    if s["avoid"]:
        L.append("  AVOID (demoted): " + ", ".join(
            f"{w['capability']} (w={w['weight']}, lift {w['lift']:+})" for w in s["avoid"][:4]))
    return "\n".join(L)
