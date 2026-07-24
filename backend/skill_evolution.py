"""
skill_evolution.py — H5 SKILL EVOLUTION ENGINE (projection over the ledger)
===========================================================================
FIRST PRINCIPLE: a system that only EXECUTES skills cannot grow; a cognitive
system must CREATE capability. The House already records every run as a tool
sequence (agent_runs + trajectory.jsonl). This engine mines those sequences for
recurring, SUCCESSFUL chains and proposes them as new reusable skills.

  search → read → extract → summarize → html_export   ⇒   "Research Dashboard Builder"

It owns NO new state — usage_count / success_rate / last_used are computed LIVE
from the execution ledger (the data already exists). Promotion of a candidate
into a real skill is a separate, human-gated action (uses the existing skills
API); this engine's job is to SURFACE the candidates with evidence.

Deterministic, model-free. Mirrors execution_recall / workflow_memory.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

_MIN_LEN = 3          # a skill is a chain of at least 3 steps
_MAX_LEN = 6
_MIN_SUPPORT = 2      # must recur in >= 2 runs to be a pattern, not a one-off
_SUCCESS = {"task_complete", "success", "complete", "done"}

# Deterministic namer: signature traits → a human capability name.
_NAME_TRAITS = [
    (("write_file", "html"), "Dashboard Builder"),
    (("export", "html"), "Dashboard Builder"),
    (("summarize", "write_file"), "Research Report Builder"),
    (("grep_search", "read_file", "edit_file"), "Code Refactor Runner"),
    (("web_search", "extract"), "Web Research Collector"),
    (("read_file", "edit_file", "run_python"), "Iterative Code Fixer"),
    (("get_", "write_file"), "Live-Data Asset Builder"),
]


def _seq_from_trajectory(events: Sequence[Dict[str, Any]]) -> List[str]:
    """Extract the ordered tool-call names from a trajectory's events."""
    out: List[str] = []
    for e in events or []:
        if (e.get("type") in ("tool_call", "tool")) and e.get("name"):
            out.append(str(e["name"]))
        elif e.get("event") == "tool_call" and e.get("name"):
            out.append(str(e["name"]))
    return out


def _ngrams(seq: List[str], lo: int, hi: int):
    n = len(seq)
    for size in range(lo, min(hi, n) + 1):
        for i in range(0, n - size + 1):
            yield tuple(seq[i:i + size])


def _suggest_name(sig: Tuple[str, ...]) -> str:
    blob = " ".join(sig).lower()
    for traits, name in _NAME_TRAITS:
        if all(t in blob for t in traits):
            return name
    head = sig[0].replace("_", " ").title().split()[0]
    tail = sig[-1].replace("_", " ").title().split()[-1]
    return f"{head}-to-{tail} Workflow"


def mine(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mine candidate skills from runs.

    Each run dict: {id, status, sequence: [tool,...], ended_at}. (The endpoint
    fills `sequence` from each run's trajectory; tests pass it directly.)
    Returns candidate skills sorted by score (support × success_rate).
    """
    support: Dict[Tuple[str, ...], int] = defaultdict(int)
    succ: Dict[Tuple[str, ...], int] = defaultdict(int)
    last: Dict[Tuple[str, ...], float] = defaultdict(float)

    for r in runs or []:
        seq = list(r.get("sequence") or [])
        if len(seq) < _MIN_LEN:
            continue
        is_success = str(r.get("status", "")).lower() in _SUCCESS
        seen_in_run = set()
        for g in _ngrams(seq, _MIN_LEN, _MAX_LEN):
            if g in seen_in_run:        # count each pattern once per run
                continue
            seen_in_run.add(g)
            support[g] += 1
            if is_success:
                succ[g] += 1
            last[g] = max(last[g], float(r.get("ended_at") or 0.0))

    candidates: List[Dict[str, Any]] = []
    for sig, n in support.items():
        if n < _MIN_SUPPORT:
            continue
        s = succ[sig]
        rate = round(s / n, 3) if n else 0.0
        # prefer maximal patterns: skip a sig fully contained in a higher-support one
        candidates.append({
            "signature": list(sig),
            "suggested_name": _suggest_name(sig),
            "usage_count": n,
            "success_count": s,
            "failure_count": n - s,
            "success_rate": rate,
            "last_used": last[sig],
            "derived_workflow": " → ".join(sig),
            "score": round(n * rate, 3),
            "length": len(sig),
        })
    # rank: score desc, then longer (more specific) chains first
    candidates.sort(key=lambda c: (c["score"], c["length"]), reverse=True)
    # de-duplicate sub-chains of an already-listed higher-ranked candidate
    kept: List[Dict[str, Any]] = []
    for c in candidates:
        sub = tuple(c["signature"])
        if any(_is_subseq(sub, tuple(k["signature"])) and k["score"] >= c["score"] for k in kept):
            continue
        kept.append(c)
    return kept


def _is_subseq(a: Tuple[str, ...], b: Tuple[str, ...]) -> bool:
    """True if contiguous tuple a appears inside b (and a != b)."""
    if a == b or len(a) >= len(b):
        return False
    for i in range(len(b) - len(a) + 1):
        if b[i:i + len(a)] == a:
            return True
    return False


def render(candidates: List[Dict[str, Any]], top: int = 5) -> str:
    if not candidates:
        return ""
    L = ["## SKILL EVOLUTION — candidate skills mined from successful runs:"]
    for c in candidates[:top]:
        L.append(f"  ★ {c['suggested_name']}  (used {c['usage_count']}×, "
                 f"{int(c['success_rate']*100)}% success)\n      {c['derived_workflow']}")
    return "\n".join(L)
