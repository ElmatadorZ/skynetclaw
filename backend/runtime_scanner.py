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

import concurrent.futures
import json
import os
import re
import urllib.error
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

# Probes run concurrently, so a runtime that is not there costs the timeout ONCE
# for the whole scan instead of once each. Serial probing meant five absent
# runtimes added ~15s before any answer, and that latency landed on the first
# agent request after boot.
_MAX_PARALLEL = 8


def default_probes() -> List[Dict[str, str]]:
    """The local probe list, plus wherever the deployment says Ollama actually is.

    DEFAULT_PROBES pins 127.0.0.1, which is right on a workstation and wrong
    inside a container, where the model runtime is a sibling service. The address
    is ADDED rather than substituted — someone may run both a local and a remote
    Ollama, and with parallel probing the extra probe is free.
    """
    probes = list(DEFAULT_PROBES)
    base = (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    if base and base not in {p["url"].rstrip("/") for p in probes}:
        probes.insert(0, {"runtime": "ollama", "url": base, "api_type": "ollama"})
    return probes


def _in_parallel(fn, items: List[Any]) -> List[Any]:
    """Map fn over items concurrently, preserving order. Never raises.

    Order is preserved deliberately: probe order is documented as informational,
    but a scan whose output shuffled between runs would make the registry —
    and every ranking built on it — non-reproducible.
    """
    if not items:
        return []
    if len(items) == 1:
        try:
            return [fn(items[0])]
        except Exception:
            return [None]
    out: List[Any] = [None] * len(items)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(_MAX_PARALLEL, len(items))) as ex:
        futures = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for f in concurrent.futures.as_completed(futures):
            i = futures[f]
            try:
                out[i] = f.result()
            except Exception:
                out[i] = None
    return out


# ── http helpers ──────────────────────────────────────────────────────────────
# A runtime may sit behind a key: `vllm serve --api-key`, LM Studio with auth on,
# or any hosted OpenAI-compatible endpoint. Sending no Authorization header meant
# such a runtime answered 401 and was filed as OFFLINE — indistinguishable from
# "not running", so the operator was told to start a server that was already up.
# The key travels with the probe; a refusal is now reported as a refusal.
def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _request(url: str, timeout: float, api_key: Optional[str] = None,
             body: Optional[dict] = None) -> Dict[str, Any]:
    """Returns {data, status, unauthorized, reachable}. Never raises.

    `unauthorized` is the point: it separates "the server said no" from "there was
    no server", which the previous bare `except: return None` collapsed into one.
    """
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(api_key))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"data": json.loads(r.read().decode("utf-8", "replace")),
                    "status": getattr(r, "status", 200),
                    "unauthorized": False, "reachable": True}
    except urllib.error.HTTPError as e:
        # An HTTP error means something answered — the runtime IS reachable.
        return {"data": None, "status": e.code,
                "unauthorized": e.code in (401, 403), "reachable": True}
    except Exception:
        return {"data": None, "status": None, "unauthorized": False,
                "reachable": False}


def _get(url: str, timeout: float = 3.0, api_key: Optional[str] = None) -> Optional[Any]:
    return _request(url, timeout, api_key)["data"]


def _post(url: str, body: dict, timeout: float = 6.0,
          api_key: Optional[str] = None) -> Optional[Any]:
    return _request(url, timeout, api_key, body=body)["data"]


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
def _ollama_models(base: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    tags = _get(base.rstrip("/") + "/api/tags", api_key=api_key)
    out: List[Dict[str, Any]] = []
    if not tags:
        return out
    listed = tags.get("models", [])
    # /api/show is one round trip PER MODEL. Serially, a library of twenty models
    # cost twenty timeouts — minutes on the first request after boot. Concurrently
    # it costs one.
    shows = _in_parallel(
        lambda mid: _post(base.rstrip("/") + "/api/show", {"model": mid},
                          api_key=api_key),
        [(t.get("name") or t.get("model") or "") for t in listed])
    for t, show in zip(listed, shows):
        mid = t.get("name") or t.get("model") or ""
        rec: Dict[str, Any] = {
            "id": mid, "family": family_of(mid),
            "size_gb": round((t.get("size", 0) or 0) / 1e9, 1),
            "quantization": (t.get("details") or {}).get("quantization_level"),
            "parameters": (t.get("details") or {}).get("parameter_size"),
            "context": None, "tool_calling": None, "vision": None,
            "thinking": None, "embedding": None, "api_type": "ollama",
        }
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


def _openai_models(base: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    data = _get(base.rstrip("/") + "/models", api_key=api_key)
    out: List[Dict[str, Any]] = []
    if not data:
        return out
    # llama.cpp exposes richer metadata at /props (single loaded model)
    props = _get(base.rstrip("/") + "/props", api_key=api_key) or {}
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
    """Probe one runtime → {runtime,url,online,api_type,models,...}. Never raises.

    `probe` may carry an `api_key`; a runtime that answers 401/403 is reported as
    online-but-unauthorized rather than offline, because telling the operator to
    restart a server that is running and simply refused the request wastes their
    time and hides the real fix.
    """
    url, api = probe["url"], probe.get("api_type", "openai")
    key = probe.get("api_key") or None
    unauthorized = False
    try:
        if api == "ollama":
            probe_r = _request(url.rstrip("/") + "/api/tags", 3.0, key)
            models = _ollama_models(url, key) if not probe_r["unauthorized"] else []
        else:
            probe_r = _request(url.rstrip("/") + "/models", 3.0, key)
            if not probe_r["reachable"]:
                probe_r = _request(url.rstrip("/") + "/health", 3.0, key)
            models = _openai_models(url, key) if not probe_r["unauthorized"] else []
        unauthorized = bool(probe_r["unauthorized"])
        # Reachable is the honest signal: a refusal proves something is listening.
        online = probe_r["reachable"] or bool(models)
    except Exception:
        models, online = [], False
    out: Dict[str, Any] = {
        "runtime": probe["runtime"], "url": url, "api_type": api,
        "online": bool(online), "models": models,
    }
    if unauthorized:
        out["authorized"] = False
        out["reason"] = ("the runtime is reachable but refused the request (401/403) — "
                         "it needs an API key. Add one to this connection; it is "
                         "running, not down.")
    return out


def scan(extra_probes: Optional[List[Dict[str, str]]] = None,
         include_offline: bool = False) -> List[Dict[str, Any]]:
    """Scan all known runtimes. `extra_probes` merges DB/user connections so a
    new runtime needs only a probe entry — ZERO code change to add one."""
    probes = default_probes() + list(extra_probes or [])
    seen, unique = set(), []
    for p in probes:
        key = p["url"].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    scanned = _in_parallel(scan_runtime, unique)
    return [r for r in scanned
            if r is not None and (r["online"] or include_offline)]


if __name__ == "__main__":
    print(json.dumps(scan(include_offline=True), indent=2))
