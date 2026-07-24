"""
recovery.py — OX-1.2 RECOVERY ENGINE (stateless)
================================================
When a tool FAILS, the House should not blindly retry the same call — it should
try a DIFFERENT, concrete strategy. This module classifies a real failure and
returns alternate approaches as next-action options.

Stateless and deterministic: a classifier over the real result text + a fixed
strategy table. No persistence, no state, no model call.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List

FILE_NOT_FOUND = "file_not_found"
TIMEOUT = "timeout"
NETWORK = "network"
NONZERO_EXIT = "nonzero_exit"
CODE_ERROR = "code_error"
UNKNOWN_TOOL = "unknown_tool"
GENERIC = "generic"


def classify(name: str, result: str) -> str:
    """Map a real failure result to a recovery class."""
    r = (result or "").lstrip()
    low = r[:400].lower()
    if low.startswith("[unknown tool"):
        return UNKNOWN_TOOL
    if r.startswith("[file not found") or r.startswith("[not found") or \
       (r.startswith("[") and "not found" in low):
        return FILE_NOT_FOUND
    if "timeout" in low:
        return TIMEOUT
    if ("connecterror" in low or "getaddrinfo" in low or "connection attempts failed" in low
            or "name or service not known" in low or "network is unreachable" in low):
        return NETWORK
    if "syntaxerror" in low or "syntax error" in low or "traceback (most recent call last)" in low:
        return CODE_ERROR
    if r.startswith("[exit "):
        try:
            if int(r[6:r.index("]")].split()[0]) != 0:
                return NONZERO_EXIT
        except Exception:
            pass
    return GENERIC


_STRATEGIES: Dict[str, List[str]] = {
    FILE_NOT_FOUND: [
        "grep_search the relevant pattern to LOCATE the correct path before reading",
        "find_files with a glob (e.g. *name*) to discover the real filename",
        "list_files on the parent directory to see what actually exists",
    ],
    TIMEOUT: [
        "reduce the scope — smaller input, fewer lines, a shorter range",
        "raise the timeout argument (run_python / shell_command 'timeout')",
        "split the work into several smaller tool calls",
    ],
    NETWORK: [
        "retry ONCE after a brief wait",
        "use an alternate source / endpoint or a different data tool",
        "fall back to web_search or a cached/local source",
    ],
    NONZERO_EXIT: [
        "read the STDERR shown in the result and fix the command",
        "try an alternate command or tool that achieves the same goal",
        "verify prerequisites exist (paths/binaries) before re-running",
    ],
    CODE_ERROR: [
        "re-read the exact file region before editing (get the precise text)",
        "fix the reported syntax/line, then re-run",
        "write a minimal reproduction first to isolate the error",
    ],
    UNKNOWN_TOOL: [
        "choose a REAL tool from the available set that matches the need",
    ],
    GENERIC: [
        "change approach — do NOT repeat the same call",
        "gather more information with a read/search tool before acting again",
    ],
}


def strategies(failure_class: str) -> List[str]:
    return _STRATEGIES.get(failure_class, _STRATEGIES[GENERIC])


def render(name: str, args: Dict[str, Any], result: str) -> str:
    """A concrete RECOVERY OPTIONS block to inject after a failed tool call."""
    cls = classify(name, result)
    opts = strategies(cls)
    return (f"## RECOVERY OPTIONS — tool '{name}' FAILED ({cls}). "
            "Do NOT repeat it; pick a DIFFERENT next move:\n"
            + "\n".join(f"  • {o}" for o in opts))
