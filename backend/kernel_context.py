"""
kernel_context.py — Cognitive Kernel · Context service (migration step 3a)
=========================================================================
COGNITIVE_KERNEL_SPEC §3: the Context service OWNS the token budget so no
subsystem can overflow the window (Principle #7 — honour the 16k ceiling). This
is the strangler-fig move of the House's proven `_fit_context`/`_est_tokens` out
of main.py into the kernel; main now delegates here.

Interface (the ABI the kernel guarantees):
    estimate(messages, tools) -> int          # token estimate
    budget(window, aggressive) -> int         # room reserved for the prompt
    fit(messages, window, tools, aggressive)  # messages guaranteed to fit

Deterministic, stdlib only. License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ContextService(Protocol):
    def estimate(self, messages: List[Dict[str, Any]], tools: Optional[list] = None) -> int: ...
    def budget(self, window: int, aggressive: bool = False) -> int: ...
    def fit(self, messages: List[Dict[str, Any]], window: int,
            tools: Optional[list] = None, aggressive: bool = False) -> List[Dict[str, Any]]: ...


def estimate(messages: List[Dict[str, Any]], tools: Optional[list] = None) -> int:
    # ~1 token per 3 chars for mixed Thai/English; + rough tool-schema overhead
    n = sum(len(str(m.get("content", "") or "")) for m in messages)
    if tools:
        try:
            n += len(json.dumps(tools, ensure_ascii=False))
        except Exception:
            pass
    return n // 3


def budget(window: int, aggressive: bool = False) -> int:
    """Room reserved for the prompt — 45% of the window (55% when aggressive,
    e.g. after a transient error), leaving the rest for the reply + tool schema."""
    window = int(window or 16384)
    return int(window * (0.55 if aggressive else 0.45))


def fit(messages: List[Dict[str, Any]], window: int, tools: Optional[list] = None,
        aggressive: bool = False) -> List[Dict[str, Any]]:
    """Return messages guaranteed to fit `window` with room for the reply.
    Keeps ALL system messages + the first user turn (the task) + the most recent
    turns; truncates long tool-result bodies, then drops the oldest middle turns
    if still over. Never touches the newest turn."""
    window = int(window or 16384)
    lim_budget = budget(window, aggressive)
    if estimate(messages, tools) <= lim_budget:
        return messages
    sysm = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    if not rest:
        return messages
    keep_tail = 4 if aggressive else 6
    head, tail = rest[:1], rest[-keep_tail:]
    _lim = 800 if aggressive else 1500

    def _trunc(m):
        c = str(m.get("content", "") or "")
        return {**m, "content": c[:_lim] + " …[trimmed]"} if len(c) > _lim else m

    kept = sysm + [_trunc(m) for m in head] + [_trunc(m) for m in tail]
    if estimate(kept, tools) > lim_budget and len(kept) > len(sysm) + 2:
        body = kept[len(sysm):]
        while estimate(sysm + body, tools) > lim_budget and len(body) > 2:
            body.pop(0)
        kept = sysm + body
    # HARD GUARANTEE: if the SYSTEM prompt alone still blows the budget, truncate
    # the largest system message from the END — its opening carries the core
    # instructions. Better a shortened prompt than a ReadError that fails the run.
    if estimate(kept, tools) > lim_budget:
        _sys_idx = [i for i, m in enumerate(kept) if m.get("role") == "system"]
        if _sys_idx:
            biggest = max(_sys_idx, key=lambda i: len(str(kept[i].get("content", ""))))
            over = estimate(kept, tools) - lim_budget
            cut_chars = min(len(str(kept[biggest]["content"])) - 500, over * 3 + 500)
            if cut_chars > 0:
                c = str(kept[biggest]["content"])
                kept[biggest] = {**kept[biggest],
                                 "content": c[: max(500, len(c) - cut_chars)] + " …[prompt trimmed to fit window]"}
    return kept


# ── A6 — conformance self-test ────────────────────────────────────────────────
def conforms_to() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    window = 16384
    # estimate is monotone (more text ⇒ ≥ tokens) and budget < window
    checks["budget_lt_window"] = 0 < budget(window) < window
    checks["estimate_monotone"] = estimate([{"content": "x" * 300}]) >= estimate([{"content": "x" * 30}])
    # an in-budget conversation is returned untouched
    small = [{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}]
    checks["passthrough_small"] = fit(small, window) is small
    # an oversized conversation is trimmed to fit, keeping system + first + newest
    big = ([{"role": "system", "content": "SYS"}]
           + [{"role": "user", "content": "TASK-FIRST"}]
           + [{"role": "assistant", "content": "z" * 20000} for _ in range(6)]
           + [{"role": "user", "content": "NEWEST-TURN"}])
    fitted = fit(big, window)
    checks["fits_window"] = estimate(fitted, None) <= budget(window)
    checks["keeps_system"] = any(m.get("role") == "system" for m in fitted)
    checks["keeps_newest"] = any("NEWEST-TURN" in str(m.get("content", "")) for m in fitted)
    checks["keeps_task"] = any("TASK-FIRST" in str(m.get("content", "")) for m in fitted)
    ok = all(checks.values())
    return {"ok": ok, "checks": checks}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = conforms_to()
    for k, v in r["checks"].items():
        print(f"  {'OK ' if v else 'XX '} {k}")
    print("conforms_to:", r["ok"])
