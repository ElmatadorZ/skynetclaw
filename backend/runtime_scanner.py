"""
runtime_scanner.py — OX-RUNTIME-DISCOVERY-1 Phases 1-2
======================================================
Discover available LLM runtimes and their models WITHOUT any hardcoded model
name. The House asks each runtime "what do you have?" and reads declared
capabilities. Adding a new runtime = adding a probe endpoint (or a connection
row) — never an `if model == "qwen"`.

Supported providers (probed by their API shape, not their name):
  • Ollama                 native /api/tags + /api/show (rich capabilities)
  • llama.cpp OpenAI server, LM Studio, vLLM, SGLang, any OpenAI-compatible
                           /v1/models  (+ /props or /health where available)

Dependency-free (stdlib only). Pure helpers (classify_*) are unit-tested; the
network probes degrade gracefully (offline runtime → online:false, models:[]).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Dict, List, Optional

# Well-known local runtime endpoints. Order is informational only — every
# online runtime is returned. (User/DB connections are merged in by the caller.)
DEFAULT_PROBES = [
    {"runtime": "ollama",   "url": "http://127.0.0.1:11434", "api_type": "ollama"},
    {"runtime": "llamacpp", "url": "http://127.0.0.1:8080/v1", "api_type": "openai"},
    {"runtime": "lmstudio", "url": "http://127.0.0.1:1234/v1", "api_type": "openai"},
    {"runtime": "vllm",     "url": "http://127.0.0.1:8000/v1", "api_type": "openai"},
    {"runtime": "sglang",   "url": "http://127.0.0.1:30000/v1", "api_type": "openai"},
]


# ── http helpers ──────────────────────────────────────────────────────────────
def _get(url: str, timeout: float = 3.0) -> Optional[Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def _post(url: str, body: dict, timeout: float = 6.0) -> Optional[Any]:
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


# ── pure capability parsers (unit-tested) ─────────────────────────────────────
def parse_param_b(text: str) -> Optional[float]:
    """'9B' / '7.6B' / '26b' / '0.5B' → float billions. No model names."""
    if not text:
        return None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*[bB]\b", str(text))
    return float(m.group(1)) if m else None


def family_of(model_id: str) -> str:
    """Generic family token = leading alpha run of the id (qwen3.5:9b → qwen).
    Used only for grouping/observability, NEVER for routing decisions."""
    m = re.match(r"[a-zA-Z]+", model_id or "")
    return m.group(0).lower() if m else "unknown"


def caps_from_ollama_show(show: dict) -> Dict[str, Any]:
    """Map an Ollama /api/show response → capability record (declared, not guessed)."""
    caps = set(show.get("capabilities") or [])
    info = show.get("model_info") or {}
    details = show.get("details") or {}
    ctx = None
    for k, v in info.items():
        if k.endswith(".context_length"):
            try: ctx = int(v)
            except Exception: pass
    return {
        "context": ctx,
        "tool_calling": "tools" in caps,
        "vision": "vision" in caps,
        "thinking": "thinking" in caps,
        "embedding": "embedding" in caps,
        "parameters": details.get("parameter_size"),
        "quantization": details.get("quantization_level"),
        "family": (details.get("family") or "").lower() or None,
    }


# ── per-runtime model discovery ───────────────────────────────────────────────
def _ollama_models(base: str) -> List[Dict[str, Any]]:
    tags = _get(base.rstrip("/") + "/api/tags")
    out: List[Dict[str, Any]] = []
    if not tags:
        return out
    for t in tags.get("models", []):
        mid = t.get("name") or t.get("model") or ""
        rec: Dict[str, Any] = {
            "id": mid, "family": family_of(mid),
            "size_gb": round((t.get("size", 0) or 0) / 1e9, 1),
            "quantization": (t.get("details") or {}).get("quantization_level"),
            "parameters": (t.get("details") or {}).get("parameter_size"),
            "context": None, "tool_calling": None, "vision": None,
            "thinking": None, "embedding": None, "api_type": "ollama",
        }
        show = _post(base.rstrip("/") + "/api/show", {"model": mid})
        if show:
            c = caps_from_ollama_show(show)
            rec.update({k: c[k] for k in ("context", "tool_calling", "vision",
                                          "thinking", "embedding")})
            rec["parameters"] = rec["parameters"] or c.get("parameters")
            rec["quantization"] = rec["quantization"] or c.get("quantization")
            if c.get("family"):
                rec["family"] = c["family"]
        rec["param_b"] = parse_param_b(rec.get("parameters") or mid)
        out.append(rec)
    return out


def _openai_models(base: str) -> List[Dict[str, Any]]:
    data = _get(base.rstrip("/") + "/models")
    out: List[Dict[str, Any]] = []
    if not data:
        return out
    # llama.cpp exposes richer metadata at /props (single loaded model)
    props = _get(base.rstrip("/") + "/props") or {}
    pctx = None
    try:
        pctx = int((props.get("default_generation_settings") or {}).get("n_ctx")
                   or props.get("n_ctx"))
    except Exception:
        pctx = None
    for m in data.get("data", []):
        mid = m.get("id") or ""
        meta = m.get("meta") or {}
        ctx = m.get("context_length") or meta.get("n_ctx_train") or pctx
        out.append({
            "id": mid, "family": family_of(mid),
            "size_gb": round((meta.get("size", 0) or 0) / 1e9, 1) or None,
            "parameters": None, "param_b": parse_param_b(mid),
            "quantization": None, "context": ctx,
            # OpenAI /v1/models doesn't declare these — probed in metrics phase.
            "tool_calling": None, "vision": None, "thinking": None,
            "embedding": ("embed" in mid.lower()) or None,
            "api_type": "openai",
        })
    return out


def scan_runtime(probe: Dict[str, str]) -> Dict[str, Any]:
    """Probe one runtime → {runtime,url,online,api_type,models}. Never raises."""
    url, api = probe["url"], probe.get("api_type", "openai")
    try:
        if api == "ollama":
            models = _ollama_models(url)
            online = _get(url.rstrip("/") + "/api/tags") is not None
        else:
            models = _openai_models(url)
            online = (_get(url.rstrip("/") + "/models") is not None
                      or _get(url.rstrip("/") + "/health") is not None)
    except Exception:
        models, online = [], False
    return {"runtime": probe["runtime"], "url": url, "api_type": api,
            "online": bool(online or models), "models": models}


def scan(extra_probes: Optional[List[Dict[str, str]]] = None,
         include_offline: bool = False) -> List[Dict[str, Any]]:
    """Scan all known runtimes. `extra_probes` merges DB/user connections so a
    new runtime needs only a probe entry — ZERO code change to add one."""
    probes = list(DEFAULT_PROBES) + list(extra_probes or [])
    seen, results = set(), []
    for p in probes:
        key = p["url"].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        r = scan_runtime(p)
        if r["online"] or include_offline:
            results.append(r)
    return results


if __name__ == "__main__":
    print(json.dumps(scan(include_offline=True), indent=2))
