"""
house_constitution.py — PART 3: The House Constitution
======================================================
Eight permanent rules every council member loads automatically. The constitution
is injected into agent context (load_constitution) and used to score whether a
deliberation honoured the rules (check_compliance).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

VERSION = "1.0"

RULES: List[Dict[str, str]] = [
    {"id": "R1", "name": "Evidence before opinion",
     "text": "State the evidence before any judgement. No conclusion without a basis."},
    {"id": "R2", "name": "No fabricated data",
     "text": "Never invent numbers, prices, dates, or quotes. Fetch live data with tools or say it is unknown."},
    {"id": "R3", "name": "State uncertainty explicitly",
     "text": "Mark confidence and name what is assumed vs known vs unknown."},
    {"id": "R4", "name": "Forecasts require invalidation conditions",
     "text": "Every forecast must state the condition that would prove it wrong."},
    {"id": "R5", "name": "Minority opinions preserved",
     "text": "Dissent is recorded, never erased. A minority view survives the verdict."},
    {"id": "R6", "name": "Historical comparisons required",
     "text": "Compare against the House's own prior sessions on similar questions."},
    {"id": "R7", "name": "Source traceability mandatory",
     "text": "Every claim is traceable to a source, a tool result, or an explicit assumption."},
    {"id": "R8", "name": "No invented targets, no fake tool use",
     "text": "Never invent an observation target — a file, path, URL, API, note, id, "
             "or evidence source not present in the runtime or the user's request. Never "
             "narrate a tool call you did not actually execute, nor report a tool result "
             "you did not receive. If a required target is missing, do NOT create a "
             "placeholder or an example: reply BLOCKED and list exactly what must be "
             "supplied before observation can begin. Inventing a target to make a report "
             "look complete is hallucination and a mission FAILURE — never TASK_COMPLETE."},
]

_RULE_BY_ID = {r["id"]: r for r in RULES}


def load_constitution() -> str:
    """Full text — injected into every agent's context automatically."""
    lines = [f"# THE HOUSE CONSTITUTION v{VERSION} (binding on all council members)"]
    for r in RULES:
        lines.append(f"{r['id']} — {r['name']}: {r['text']}")
    lines.append("These rules are permanent. A verdict that breaks them is invalid.")
    return "\n".join(lines)


def constitution_header() -> str:
    """Compact one-liner for tight token budgets."""
    return ("HOUSE CONSTITUTION: " +
            " · ".join(f"{r['id']} {r['name']}" for r in RULES))


# ──────────────────────────────────────────────────────────────────────────────
# Compliance scoring — heuristic, deterministic, 0..1 per rule
# ──────────────────────────────────────────────────────────────────────────────
_PAT = {
    "R1": re.compile(r"\b(evidence|because|data|fact|observ)", re.I),
    "R2": re.compile(r"\b(source|tool|fetched|live|per |according)", re.I),
    "R3": re.compile(r"\b(uncertain|assum|confidence|likely|probab|unknown|estimat)", re.I),
    "R4": re.compile(r"\b(invalidat|wrong if|fails if|falsif|breaks if)", re.I),
    "R5": re.compile(r"\b(dissent|minority|however|disagree|but )", re.I),
    "R6": re.compile(r"\b(prior|history|historical|previously|last time|compared)", re.I),
    "R7": re.compile(r"\b(source|\[\d+\]|https?://|cit|trace)", re.I),
    "R8": re.compile(r"\b(blocked|missing target|no (target|object)|not (executed|supplied)|cannot begin)\b", re.I),
}


def check_compliance(text: str) -> Dict[str, Any]:
    """Return per-rule pass/fail + overall score for a deliberation text."""
    t = text or ""
    results = {}
    passed = 0
    for r in RULES:
        ok = bool(_PAT[r["id"]].search(t))
        results[r["id"]] = {"name": r["name"], "pass": ok}
        passed += 1 if ok else 0
    score = round(passed / len(RULES), 3)
    violations = [rid for rid, v in results.items() if not v["pass"]]
    return {"score": score, "passed": passed, "total": len(RULES),
            "violations": violations, "rules": results,
            "valid": score >= 0.5}


def rule(rid: str) -> Dict[str, str]:
    return _RULE_BY_ID.get(rid, {})
