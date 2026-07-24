"""
runtime_router.py — OX-RUNTIME-DISCOVERY-1 Phases 6 & 7
=======================================================
Route a task to the best runtime+model+endpoint by CAPABILITY, never by name.
No `if model == "qwen"` anywhere — the router maps a task to a ROLE, then picks
the top-ranked healthy model for that role from the registry.

Also the health monitor: liveness + latency probe per runtime; unhealthy
runtimes are auto-excluded from routing.

Pure routing (route_with_registry) is unit-tested; route() does a live scan.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import time
import urllib.request
from typing import Any, Dict, List, Optional

# Task-INTENT keywords → role. These describe the WORK, not any model.
_ROLE_HINTS = {
    "Execution": ("create", "read", "write", "edit", "modify", "delete", "run",
                  "execute", "file", "folder", "search", "fetch", "download",
                  "list", "find", "save", "tool", "call", "open", "move"),
    "Reasoning": ("analyze", "plan", "design", "explain", "summarize", "compare",
                  "evaluate", "reason", "why", "strategy", "comprehend", "synthesize"),
    "Council":   ("debate", "council", "deliberate", "review board", "multi-agent",
                  "consensus", "deep research", "critique panel"),
    "Vision":    ("image", "photo", "picture", "screenshot", "diagram", "ocr",
                  "look at", "see", "visual"),
    "Embedding": ("embed", "embedding", "vector", "similarity", "semantic index"),
}
_DEFAULT_ROLE = "Execution"   # the House is execution-first


def task_to_role(task: str) -> str:
    """Map task intent → role by keyword. Execution-first default. No model names."""
    t = (task or "").lower()
    best, best_hits = _DEFAULT_ROLE, 0
    for role, kws in _ROLE_HINTS.items():
        hits = sum(1 for k in kws if k in t)
        if hits > best_hits:
            best, best_hits = role, hits
    return best


def route_with_registry(task_or_role: str, registry: Dict[str, Any],
                        is_role: bool = False) -> Dict[str, Any]:
    """Pick the best model for the task/role from a prebuilt registry. Pure."""
    role = task_or_role if is_role else task_to_role(task_or_role)
    ranked = (registry.get("rankings") or {}).get(role, [])
    if not ranked:
        # graceful fallback: any Execution model, else any model at all
        for fb in ("Execution", "Reasoning", "Utility"):
            ranked = (registry.get("rankings") or {}).get(fb, [])
            if ranked:
                role = fb
                break
    if not ranked:
        return {"role": role, "model": None, "runtime": None, "url": None,
                "api_type": None, "endpoint": None, "reason": "no runtime available"}
    top = ranked[0]
    api = top.get("api_type", "ollama")
    url = (top.get("url") or "").rstrip("/")
    endpoint = url + ("/api/chat" if api == "ollama" else "/chat/completions")
    return {"role": role, "model": top["id"], "runtime": top["runtime"],
            "url": url, "api_type": api, "endpoint": endpoint,
            "score": top.get("score"), "alternatives": ranked[1:4]}


# ── health monitor (Phase 7) ──────────────────────────────────────────────────
def probe_health(runtime: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
    url = (runtime.get("url") or "").rstrip("/")
    api = runtime.get("api_type", "ollama")
    check = url + ("/api/tags" if api == "ollama" else "/models")
    t0 = time.time()
    try:
        with urllib.request.urlopen(check, timeout=timeout) as r:
            alive = r.status == 200
        latency = time.time() - t0
        healthy = alive and latency < timeout
        return {"runtime": runtime.get("runtime"), "url": url, "alive": alive,
                "latency_s": round(latency, 3), "healthy": healthy,
                "models": len(runtime.get("models", []))}
    except Exception as e:
        return {"runtime": runtime.get("runtime"), "url": url, "alive": False,
                "latency_s": None, "healthy": False, "error": str(e)[:80]}


def health_report(scan_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    checks = [probe_health(rt) for rt in scan_results]
    return {"runtimes": checks,
            "healthy": [c["runtime"] for c in checks if c.get("healthy")],
            "unhealthy": [c["runtime"] for c in checks if not c.get("healthy")]}


def healthy_scan(scan_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop unhealthy runtimes before building the registry (auto-disable)."""
    hr = {c["runtime"]: c for c in health_report(scan_results)["runtimes"]}
    return [rt for rt in scan_results if hr.get(rt.get("runtime"), {}).get("healthy")]


# ── live convenience (does a real scan) ───────────────────────────────────────
def route(task: str, extra_probes: Optional[List[Dict[str, str]]] = None,
          use_health: bool = True) -> Dict[str, Any]:
    import runtime_scanner as scanner
    import runtime_registry as registry
    import runtime_metrics as metrics
    scanned = scanner.scan(extra_probes=extra_probes)
    if use_health:
        scanned = healthy_scan(scanned) or scanned
    reg = registry.build_registry(scanned, metrics.load_metrics())
    return route_with_registry(task, reg)
