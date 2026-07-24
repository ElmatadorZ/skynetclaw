"""
context_budget.py — CONTEXT BUDGET MANAGER (Phase P0 · Reliability)
===================================================================
The agent loop in main.py appends to `cur` (the messages list) every step and
never evicts. With a fixed model window (num_ctx=16384) the conversation
eventually exceeds the budget, the model degrades, stops emitting tool calls,
and the run halts as "operative went silent (likely context overload)".

This module measures the live context so the loop can compress BEFORE the model
degrades. It reads real message content — it estimates, it never fabricates.

Token estimate: tiktoken if available, else a ~4-chars/token heuristic (good
enough for budgeting; deliberately conservative).

assess(cur) -> {
    prompt_tokens, tool_tokens, reasoning_tokens, history_tokens,
    total, usable, remaining, ratio, level: ok|warning|critical
}
events(assessment) -> [(budget_warning|budget_critical, payload), ...]

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_LIMIT = 16384       # must match the loop's num_ctx
DEFAULT_RESERVE = 2048      # headroom kept for the model's own response
WARNING_RATIO = 0.70
CRITICAL_RATIO = 0.88

try:
    import tiktoken as _tk
    _ENC = _tk.get_encoding("cl100k_base")
except Exception:
    _ENC = None


# ── PROTOCOL PRIMITIVE — resolve the window from the connection, not a constant ─
# "Models are temporary. Protocols endure." (ElmatadorZ). The context budget must
# be a property of whatever model is behind the active connection — read, not
# assumed. This is the one place a model-specific constant (16384, the llama.cpp
# VRAM ceiling) had leaked into the model-agnostic protocol layer; resolve() lifts
# it out so swapping to Ollama or a cloud API adapts automatically.
_CLOUD_MODEL_WINDOWS = (
    ("claude", 200000), ("gpt-4.1", 1000000), ("gpt-4o", 128000), ("gpt-4", 128000),
    ("o1", 200000), ("o3", 200000), ("gemini", 1000000), ("command-r", 128000),
    ("mistral", 32768), ("llama-3.1", 131072), ("qwen2.5", 32768),
)
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0", "::1", "[::1]")


def _is_local(base_url: str) -> bool:
    b = (base_url or "").lower()
    return any(h in b for h in _LOCAL_HOSTS)


def resolve_window(conn: Optional[Dict[str, Any]] = None, api_type: Optional[str] = None,
                   model: str = "", base_url: str = "",
                   default: int = DEFAULT_LIMIT, cloud_default: int = 128000) -> int:
    """Resolve the usable context window for a connection.

    Precedence (protocol-pure): explicit connection declaration > local-host safe
    default > model-name hint > per-cloud default. Zero-regression: an undeclared
    LOCAL connection keeps `default` (16384) regardless of api_type — so the local
    llama.cpp server (which speaks OpenAI-compat yet is 16k-capped) is unchanged,
    while a cloud model auto-gains its real window.
    """
    conn = conn or {}
    base_url = base_url or conn.get("base_url") or ""
    model = model or conn.get("model") or ""
    api_type = api_type or conn.get("api_type") or conn.get("type")
    # 1. explicit declaration on the connection wins — the right, protocol-pure path
    for k in ("context_window", "n_ctx", "num_ctx", "context"):
        v = conn.get(k)
        if v:
            try:
                return max(2048, int(v))
            except Exception:
                pass
    # 2. any loopback host = a LOCAL server (llama.cpp/ollama) → keep the safe default,
    #    independent of api_type (this is the OpenAI-compat-yet-local trap)
    if _is_local(base_url):
        return default
    # 3. remote: model-name hint, else per-cloud default
    m = (model or "").lower()
    for sub, w in _CLOUD_MODEL_WINDOWS:
        if sub in m:
            return w
    try:
        import llm_adapter as _la
        remote_cloud = _la.is_cloud(api_type)
    except Exception:
        remote_cloud = bool(api_type) and api_type not in ("", "ollama", "local")
    return cloud_default if remote_cloud else default


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    if _ENC is not None:
        try:
            return len(_ENC.encode(text))
        except Exception:
            pass
    # conservative heuristic: ~4 chars/token, +1 so empty-ish strings count
    return (len(text) + 3) // 4


def _content(m: Dict[str, Any]) -> str:
    c = m.get("content")
    return c if isinstance(c, str) else ("" if c is None else str(c))


def assess(cur: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
           limit: int = DEFAULT_LIMIT, reserve: int = DEFAULT_RESERVE) -> Dict[str, Any]:
    """Measure the live context split by role.

    `tools` is the function-calling schema list sent in the same request
    (payload["tools"]). It is serialized exactly as it goes over the wire and
    counted — the model's chat template renders these schemas into the actual
    prompt, so omitting them here means the budget can read "ok" while the
    real request already overflows num_ctx (found in production: a 49-tool
    fallback schema alone is ~4.4k tokens, invisible to a `cur`-only assess).
    """
    prompt = tool = reasoning = history = 0
    for m in cur or []:
        n = estimate_tokens(_content(m))
        role = m.get("role")
        if role == "system":
            prompt += n
        elif role == "tool":
            tool += n
        elif role == "assistant":
            reasoning += n
        else:  # user (task, nudges, ledger)
            history += n
    schema = estimate_tokens(json.dumps(tools)) if tools else 0
    total = prompt + tool + reasoning + history + schema
    usable = max(1, limit - reserve)
    ratio = total / usable
    level = "critical" if ratio >= CRITICAL_RATIO else ("warning" if ratio >= WARNING_RATIO else "ok")
    return {
        "prompt_tokens": prompt, "tool_tokens": tool,
        "reasoning_tokens": reasoning, "history_tokens": history,
        "schema_tokens": schema,
        "total": total, "usable": usable, "remaining": usable - total,
        "ratio": round(ratio, 3), "level": level,
        "limit": limit, "reserve": reserve,
    }


def events(a: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Translate an assessment into bus events (only when warning/critical)."""
    if a["level"] == "ok":
        return []
    etype = "budget_critical" if a["level"] == "critical" else "budget_warning"
    payload = {"total": a["total"], "usable": a["usable"], "remaining": a["remaining"],
               "ratio": a["ratio"], "tool_tokens": a["tool_tokens"],
               "reasoning_tokens": a["reasoning_tokens"], "history_tokens": a["history_tokens"],
               "schema_tokens": a.get("schema_tokens", 0)}
    return [(etype, payload)]
