"""
skynetclaw_codex.py — First Principle Codex (programmatic)
============================================================
Ports the FirstPrincipleCodex from the shared SKYNET_GENESIS_MASTERPIECE
reference into SkynetClaw, harmonized with existing skynetclaw_meta + SOUL.md.

Provides:

    AXIOMS               — 8 atomic axioms (causation, constraints, entropy,
                            incentives, feedback, measurement, compounding, variance)

    ariya4_problem_frame(situation)
                          — Buddhist Ariya Sacca 4 reframed as universal problem
                            framework: Problem → Cause → Cessation → Path

    deconstruct(phenomenon)
                          — full structured analysis frame combining axioms +
                            Kalama10 + Ariya4 + measurable proxies + falsification
                            tests. This is what agents consume to think structurally.

    claim_classifier(text)
                          — split text into hard_claims (absolute language) and
                            soft_claims (numeric/probabilistic). Used by the
                            Verifier to flag what needs evidence.

    kalama10()            — the 10 skepticism principles (already in SOUL.md prompt
                            but exposed here for programmatic checks)

This is the L1+L2 cognitive base layer that SOUL.md describes — now executable.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List


# ──────────────────────────────────────────────────────────────────────────────
# 8 ATOMIC AXIOMS
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Axiom:
    key: str
    statement: str
    notes: str


AXIOMS: Dict[str, Axiom] = {
    "causation": Axiom(
        "causation", "Effects trace to ≥1 root cause.",
        "Use for causal graphs. Ask: what produced this? what would NOT have produced this?"),
    "constraints": Axiom(
        "constraints", "Reality is bounded by constraints (time / energy / capital / attention).",
        "Kills magical thinking. Every plan must name its bottleneck."),
    "entropy": Axiom(
        "entropy", "Without directed energy, disorder increases.",
        "Quality decays unless actively defended. Naming this prevents 'maintenance is free' fallacy."),
    "incentives": Axiom(
        "incentives", "Behavior follows reward gradients.",
        "Model humans/markets/orgs by what they're rewarded to do, not what they say."),
    "feedback": Axiom(
        "feedback", "Systems self-regulate via feedback loops.",
        "Second-order effects matter. A change that feels right at step 1 may collapse at step 3."),
    "measurement": Axiom(
        "measurement", "If you cannot measure or proxy it, treat it as uncertain.",
        "Verification > vibes. Always ask: what's the proxy for this claim?"),
    "compounding": Axiom(
        "compounding", "Small edges compounded over time dominate short bursts.",
        "Money Atlas DNA. Daily 1% > monthly 30% spike, when sustained."),
    "variance": Axiom(
        "variance", "Variance and tail risk shape real outcomes — not averages.",
        "Distributions over point estimates. Plan for the bad tail, not the mean."),
}


def list_axioms() -> List[Dict[str, str]]:
    """Return axioms as a list of dicts (for API/UI)."""
    return [{"key": k, "statement": a.statement, "notes": a.notes}
            for k, a in AXIOMS.items()]


# ──────────────────────────────────────────────────────────────────────────────
# KALAMA 10 — skepticism protocol
# ──────────────────────────────────────────────────────────────────────────────
KALAMA_10: List[str] = [
    "Do not accept because it is heard repeatedly (rumor / consensus pressure).",
    "Do not accept because it is tradition.",
    "Do not accept because it is scripture / authority alone.",
    "Do not accept because it is logical reasoning alone (premises may be wrong).",
    "Do not accept because it is inference alone.",
    "Do not accept because it aligns with your preferences (bias).",
    "Do not accept because it fits a theory you like.",
    "Do not accept because the speaker seems credible.",
    "Do not accept because it is said by your teacher or a revered figure.",
    "Test by consequences, evidence, and whether it reduces harm and increases clarity.",
]


def kalama10() -> List[str]:
    return list(KALAMA_10)


# ──────────────────────────────────────────────────────────────────────────────
# ARIYA SACCA 4 — universal Problem Framework
# ──────────────────────────────────────────────────────────────────────────────
def ariya4_problem_frame(situation: str) -> Dict[str, str]:
    """
    Reframe Buddhist Four Noble Truths as a universal problem-solving template.
    Applies to bugs, business problems, life decisions equally.

      1. Problem      (Dukkha)    — what IS the problem (define precisely)
      2. Cause        (Samudaya)  — what causes it (root + sustaining loops)
      3. Cessation    (Nirodha)   — what does "resolved" look like (DoD)
      4. Path         (Magga)     — what steps + system changes get there
    """
    return {
        "problem":   f"What exactly is the problem in: {situation}? "
                     "Strip framing; state the gap between current and desired state.",
        "cause":     "What causes it? Distinguish root causes from symptoms. "
                     "Look at constraints (axiom: constraints), incentives "
                     "(axiom: incentives), and feedback loops (axiom: feedback).",
        "cessation": "What does 'resolved' look like? Definition of done — "
                     "stated as a measurable proxy (axiom: measurement), not a vibe.",
        "path":      "What sequence of steps + system changes leads to cessation "
                     "with least friction? Name the bottleneck (axiom: constraints) and "
                     "the smallest compounding edge (axiom: compounding).",
    }


# ──────────────────────────────────────────────────────────────────────────────
# DECONSTRUCT — full structured analysis frame
# ──────────────────────────────────────────────────────────────────────────────
def _tokenize(text: str) -> List[str]:
    t = re.sub(r"[^\w฀-๿]+", " ", (text or "").lower()).strip()
    return [w for w in t.split() if w]


def deconstruct(phenomenon: str) -> Dict[str, Any]:
    """
    Produce a structured analysis frame: axioms + Kalama10 + Ariya4 +
    measurable proxies + reality-lock questions. This is what the agent
    chews on when reasoning gets nontrivial.
    """
    tokens = _tokenize(phenomenon)
    underspecified = len(tokens) < 6
    text_lower = (phenomenon or "").lower()

    # Domain-aware measurable proxies
    measurable: List[str] = []
    if any(w in text_lower for w in ["กาแฟ", "คั่ว", "สกัด", "temperature", "profile", "roast", "extraction"]):
        measurable += ["roast curve", "ROR", "dev ratio", "TDS", "EY",
                       "CVA descriptors", "water temp (kettle/slurry)", "flow rate"]
    if any(w in text_lower for w in ["เงิน", "ตลาด", "ยอดขาย", "เศรษฐกิจ", "inflation", "policy",
                                       "money", "market", "revenue"]):
        measurable += ["price index", "wage growth", "real purchasing power",
                       "velocity", "credit spread", "default rate"]
    if any(w in text_lower for w in ["btc", "bitcoin", "crypto", "eth", "ethereum"]):
        measurable += ["exchange flows", "funding rates", "open interest",
                       "realized cap", "MVRV", "30d volatility"]
    if any(w in text_lower for w in ["gold", "ทอง", "xau"]):
        measurable += ["XAU/USD spot", "USD/THB", "real yields (10y TIPS)",
                       "ETF holdings", "central bank net buy"]
    if any(w in text_lower for w in ["agent", "bot", "code", "bug", "debug"]):
        measurable += ["error rate / 1000 calls", "p95 latency",
                       "cycle/oscillation count", "Shadow Gate block rate",
                       "TASK_COMPLETE rate"]

    constraints = ["time", "attention", "capital", "energy/physics",
                   "human behavior/incentives"]

    assumptions: List[str] = []
    if underspecified:
        assumptions.append("Underspecified — request environment, constraints, "
                           "definition-of-done, and measurement proxies.")

    return {
        "phenomenon": phenomenon,
        "axioms": list_axioms(),
        "kalama10": kalama10(),
        "ariya4_problem_frame": ariya4_problem_frame(phenomenon),
        "assumptions": assumptions,
        "constraints": constraints,
        "measurable_proxies": measurable or ["(no domain-specific proxies inferred — name them explicitly)"],
        "questions_to_lock_reality": [
            "What outcome matters (definition of done)?",
            "What constraints are non-negotiable?",
            "What variables can we measure or proxy?",
            "What evidence would falsify the working hypothesis?",
            "What is the second-order effect if we succeed?",
        ],
        "underspecified": underspecified,
    }


# ──────────────────────────────────────────────────────────────────────────────
# CLAIM CLASSIFIER — extract sentences requiring verification
# ──────────────────────────────────────────────────────────────────────────────
_HARD_CLAIM_RE = re.compile(
    r"\b(100%|always|never|guaranteed?|certainly|absolutely|"
    r"แน่นอน|รับประกัน|ไม่มีทาง|เป็นไปไม่ได้|ต้องเป็น)\b",
    re.IGNORECASE,
)
_SOFT_CLAIM_RE = re.compile(
    r"\b(\d+(?:\.\d+)?%|\d+\s*(?:ปี|เดือน|วัน|ครั้ง|years?|months?|days?|times?)|"
    r"ประมาณ|คาดว่า|อาจ|น่าจะ|น่าจะเป็น|likely|probably|approximately|about|roughly|maybe)\b",
    re.IGNORECASE,
)


def claim_classifier(text: str) -> Dict[str, List[str]]:
    """
    Split text into hard claims (absolute, need strong evidence) and
    soft claims (probabilistic / numeric, need a citation or proxy).

    Used by Verifier and meta_critique to flag exactly which sentences
    must be backed up.
    """
    if not text:
        return {"hard_claims": [], "soft_claims": [], "neutral": []}

    sents = re.split(r"(?<=[\.\!\?…])\s+|\n+", text.strip())
    hard: List[str] = []
    soft: List[str] = []
    neutral: List[str] = []
    for s in sents:
        s = s.strip()
        if not s:
            continue
        if _HARD_CLAIM_RE.search(s):
            hard.append(s)
        elif _SOFT_CLAIM_RE.search(s):
            soft.append(s)
        else:
            neutral.append(s)
    return {
        "hard_claims": hard[:30],
        "soft_claims": soft[:30],
        "neutral": neutral[:30],
        "summary": {
            "n_hard":    len(hard),
            "n_soft":    len(soft),
            "n_neutral": len(neutral),
            "n_total":   len(hard) + len(soft) + len(neutral),
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, json
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    print("=== skynetclaw_codex self-test ===\n")

    print("[1] Axioms:")
    for a in list_axioms():
        print(f"    • {a['key']:14s} — {a['statement']}")

    print("\n[2] Ariya4 framework on 'SkynetClaw keeps blocking on VALUE-MATCH':")
    a4 = ariya4_problem_frame("SkynetClaw keeps blocking on VALUE-MATCH after fetching gold price")
    for k, v in a4.items():
        print(f"    {k:10s}: {v[:120]}...")

    print("\n[3] deconstruct('ราคาทองวันนี้ส่งผลต่อตลาดยังไง'):")
    d = deconstruct("ราคาทองวันนี้ส่งผลต่อตลาดยังไง")
    print(f"    underspecified: {d['underspecified']}")
    print(f"    measurable_proxies: {d['measurable_proxies'][:5]}")
    print(f"    questions_to_lock_reality: {len(d['questions_to_lock_reality'])} questions")

    print("\n[4] claim_classifier:")
    sample = ("Gold spot is $4,576.80/oz today. The price will definitely double next year. "
              "BTC may rise approximately 30% if ETF inflows continue. "
              "The market is structured around incentives. รับประกันว่าจะได้กำไรแน่นอน 100%.")
    cc = claim_classifier(sample)
    print(f"    summary: {cc['summary']}")
    print(f"    hard claims (need very strong evidence):")
    for c in cc["hard_claims"][:3]:
        print(f"      - {c}")
    print(f"    soft claims (need a citation/proxy):")
    for c in cc["soft_claims"][:3]:
        print(f"      - {c}")

    print("\n=== self-test OK ===")
