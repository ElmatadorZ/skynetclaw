"""
runtime_registry.py — OX-RUNTIME-DISCOVERY-1 Phases 3 & 5
=========================================================
Turn discovered models (from runtime_scanner) into ROLES and RANKINGS using
measured capability only — NEVER a model name. A model named "frobozz-42x"
classifies exactly like any other model with the same capabilities.

Roles: Execution · Reasoning · Council · Vision · Embedding · Utility
(Speech reserved — surfaced when a runtime declares an audio capability.)

Classification signals (all capability/measurement, no names):
  tool_calling · thinking · vision · embedding · param_b · context · api_type
  · runtime (GPU vs CPU) · measured TTFT / tok-s (from runtime_metrics).

Pure & deterministic → fully unit-tested.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

ROLES = ["Execution", "Reasoning", "Council", "Vision", "Embedding", "Utility"]

# capability thresholds (parameters in billions) — tunable, name-free
_EXEC_MAX_B = 14.0      # execution wants small+fast
_REASON_MIN_B = 18.0    # reasoning starts here (or any 'thinking' model)
_COUNCIL_MIN_B = 30.0   # council = the heaviest models


# Roles a text model physically CANNOT stand in for. Substituting here does not
# degrade quality — it produces confident nonsense, so the router must refuse.
HARD_CAPABILITY_ROLES = ("Vision", "Embedding")


def classify(model: Dict[str, Any]) -> List[str]:
    """Capability → roles. A model may hold several roles. No model names used."""
    roles: List[str] = []
    pb = model.get("param_b")
    tools = model.get("tool_calling")
    thinking = model.get("thinking")
    vision = model.get("vision")
    embedding = model.get("embedding")

    if embedding:
        return ["Embedding"]            # embedders are single-purpose
    if vision:
        roles.append("Vision")

    # Execution: can call tools (or unknown→eligible pending probe) AND is small
    # enough to be fast. Unknown tool support (OpenAI /v1/models) stays eligible.
    small = (pb is None) or (pb <= _EXEC_MAX_B)
    if tools is not False and small:
        roles.append("Execution")

    # Reasoning / Council: size is the signal, but an UNDECLARED size is not a
    # disqualification. /v1/models states no parameter count, so every
    # OpenAI-compatible and cloud model arrives with param_b=None — and excluding
    # those meant a frontier hosted model could never hold a reasoning role while
    # a local 8B could. That is backwards.
    #
    # This mirrors the decision already made for tool_calling three lines up:
    # unknown stays eligible, and `_score` gives it no size credit, so a model
    # whose size is KNOWN to qualify always outranks one that merely might.
    # Nothing is lost either way — an empty role already fell back to Execution
    # and returned the same small model, just without saying so.
    undeclared = pb is None
    if thinking or undeclared or pb >= _REASON_MIN_B:
        roles.append("Reasoning")
    if undeclared or pb >= _COUNCIL_MIN_B:
        roles.append("Council")

    if not roles:
        roles.append("Utility")
    return roles


def _is_gpu_runtime(runtime: str, api_type: str) -> bool:
    # llama.cpp/vllm/sglang local servers are GPU-backed in this deployment;
    # Ollama may be CPU. Treated as a soft signal, refined by measured metrics.
    return api_type == "openai"


def flatten(scan_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """scan() output → flat list of model records annotated with runtime+roles."""
    out: List[Dict[str, Any]] = []
    for rt in scan_results:
        for m in rt.get("models", []):
            rec = dict(m)
            rec["runtime"] = rt.get("runtime")
            rec["url"] = rt.get("url")
            rec["api_type"] = rt.get("api_type") or m.get("api_type")
            rec["online"] = rt.get("online", True)
            rec["roles"] = classify(rec)
            # Say on what grounds it qualified. A role held because the size is
            # undeclared is not the same claim as one held because the size was
            # read and met the bar, and the operator-facing registry should not
            # present them as if they were.
            rec["role_basis"] = ("declared-capability" if rec.get("param_b") is not None
                                 or rec.get("thinking") or rec.get("vision")
                                 or rec.get("embedding")
                                 else "undeclared-size (eligible, unproven)")
            # A runtime that answered but refused us is NOT offline, and saying
            # "offline" would send the operator to restart a server that is running.
            if rt.get("authorized") is False:
                rec["authorized"] = False
                rec["unavailable_reason"] = rt.get("reason") or "authentication required"
            out.append(rec)
    return out


def _score(model: Dict[str, Any], role: str, metrics: Dict[str, Any]) -> float:
    """Higher = better for `role`. Blends measured metrics with capability."""
    mid = model.get("id", "")
    met = metrics.get(mid, {}) if metrics else {}
    ttft = met.get("ttft_s")
    tps = met.get("tokens_per_sec")
    gpu = _is_gpu_runtime(model.get("runtime", ""), model.get("api_type", ""))
    pb = model.get("param_b") or 0.0
    ctx = model.get("context") or 0
    tools = bool(model.get("tool_calling"))
    s = 0.0

    if role == "Execution":
        # speed-first: reward low TTFT, high tok/s, GPU, tool support, small size
        if ttft is not None: s += max(0.0, 30.0 - ttft)        # <15s strongly rewarded
        if tps: s += min(tps, 3000) / 100.0
        if gpu: s += 15.0
        if tools: s += 10.0
        if model.get("tool_calling") is None: s += 3.0          # eligible, unproven
        s += max(0.0, 15.0 - pb)                                # smaller is faster
    elif role in ("Reasoning", "Council"):
        # capability-first: reward size, context, thinking; mild speed bonus
        s += pb * 2.0
        s += min(ctx, 131072) / 8192.0
        if model.get("thinking"): s += 8.0
        if tps: s += min(tps, 3000) / 300.0
    elif role == "Vision":
        s += 10.0 + pb
        if tps: s += min(tps, 3000) / 300.0
    elif role == "Embedding":
        s += 10.0
        if ttft is not None: s += max(0.0, 5.0 - ttft)
    else:  # Utility
        if gpu: s += 5.0
        s += max(0.0, 10.0 - pb)
    if not model.get("online", True):
        s -= 1000.0                                             # offline → bottom
    return round(s, 3)


def rank_for_role(models: List[Dict[str, Any]], role: str,
                  metrics: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    metrics = metrics or {}
    elig = [m for m in models if role in m.get("roles", [])]
    return sorted(elig, key=lambda m: _score(m, role, metrics), reverse=True)


def build_registry(scan_results: List[Dict[str, Any]],
                   metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full registry: every model + per-role rankings (best first). No names baked in."""
    models = flatten(scan_results)
    rankings = {role: [
        {"id": m["id"], "runtime": m["runtime"], "url": m["url"],
         "api_type": m["api_type"], "score": _score(m, role, metrics or {})}
        for m in rank_for_role(models, role, metrics)
    ] for role in ROLES}
    return {"models": models, "rankings": rankings,
            "counts": {role: len(rankings[role]) for role in ROLES}}
