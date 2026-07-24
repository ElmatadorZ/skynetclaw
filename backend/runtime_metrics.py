"""
runtime_metrics.py — OX-RUNTIME-DISCOVERY-1 Phase 4
===================================================
Benchmark any discovered model and persist measurements to runtime_metrics.db.
Provider-agnostic: speaks Ollama /api/chat OR OpenAI /v1/chat/completions based
on the model's api_type — never on its name. Also probes tool support (the one
capability OpenAI /v1/models doesn't declare).

Stored per run: ttft_s, tokens_per_sec, tool_latency_s, tool_ok, vram_mb, gpu_util.
load_metrics() returns the latest row per model for the registry/router.

Dependency-free (stdlib + nvidia-smi if present).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from typing import Any, Dict, List, Optional

# ADR-0014 P0: the runtime_metrics table now lives in the institutional DB
# (satellite runtime_metrics.db absorbed; original preserved in backups/adr0014_p0_*)
_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skynerclaw.db")
_PROBE_TOOL = [{"type": "function", "function": {
    "name": "ping", "description": "return ok",
    "parameters": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}}]


def _db(path: str = _DB) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE IF NOT EXISTS runtime_metrics(
        ts REAL, model_id TEXT, runtime TEXT, url TEXT, api_type TEXT,
        ttft_s REAL, tokens_per_sec REAL, tool_latency_s REAL, tool_ok INTEGER,
        vram_mb REAL, gpu_util REAL, ok INTEGER, error TEXT)""")
    return c


def _gpu() -> Dict[str, Optional[float]]:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=4).stdout.strip().splitlines()[0]
        used, util = [x.strip() for x in out.split(",")]
        return {"vram_mb": float(used), "gpu_util": float(util)}
    except Exception:
        return {"vram_mb": None, "gpu_util": None}


def _stream_post(url: str, body: dict, timeout: float = 120) -> Any:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def benchmark_model(model: Dict[str, Any], prompt: str = "Say OK.",
                    probe_tools: bool = True) -> Dict[str, Any]:
    """Measure TTFT, tok/s, and tool-call latency for one model. api_type-driven."""
    api = model.get("api_type", "ollama")
    url = model.get("url", "")
    mid = model.get("id", "")
    res: Dict[str, Any] = {"model_id": mid, "runtime": model.get("runtime"),
                           "url": url, "api_type": api, "ts": time.time(),
                           "ttft_s": None, "tokens_per_sec": None,
                           "tool_latency_s": None, "tool_ok": 0, "ok": 0, "error": None}
    try:
        if api == "ollama":
            body = {"model": mid, "messages": [{"role": "user", "content": prompt}],
                    "stream": True, "options": {"num_predict": 32}}
            endpoint = url.rstrip("/") + "/api/chat"
        else:
            body = {"model": mid, "messages": [{"role": "user", "content": prompt}],
                    "stream": True, "max_tokens": 32}
            endpoint = url.rstrip("/") + "/chat/completions"
        t0 = time.time(); first = None; ntok = 0; tlast = t0
        with _stream_post(endpoint, body) as r:
            for line in r:
                s = line.decode("utf-8", "replace").strip()
                if not s:
                    continue
                if api != "ollama":
                    if not s.startswith("data:"):
                        continue
                    s = s[5:].strip()
                    if s == "[DONE]":
                        break
                try: o = json.loads(s)
                except Exception: continue
                content = (o.get("message", {}).get("content")
                           if api == "ollama"
                           else (o.get("choices", [{}])[0].get("delta", {}) or {}).get("content"))
                if content:
                    if first is None: first = time.time() - t0
                    ntok += 1; tlast = time.time()
                if o.get("done") or o.get("choices", [{}])[0].get("finish_reason"):
                    break
        res["ttft_s"] = round(first, 3) if first is not None else None
        gen_dur = max(tlast - (t0 + (first or 0)), 1e-6)
        res["tokens_per_sec"] = round(ntok / gen_dur, 1) if ntok else None
        res["ok"] = 1
    except Exception as e:
        res["error"] = str(e)[:120]

    if probe_tools and model.get("roles") and "Execution" in model.get("roles", []):
        res.update(_probe_tool(model))
    res.update(_gpu())
    return res


def _probe_tool(model: Dict[str, Any]) -> Dict[str, Any]:
    api = model.get("api_type", "ollama"); url = model.get("url", ""); mid = model.get("id", "")
    msg = [{"role": "system", "content": "Call the ping tool with x=ok. No prose."},
           {"role": "user", "content": "ping"}]
    try:
        if api == "ollama":
            body = {"model": mid, "messages": msg, "tools": _PROBE_TOOL,
                    "stream": False, "think": False}
            ep = url.rstrip("/") + "/api/chat"
        else:
            body = {"model": mid, "messages": msg, "tools": _PROBE_TOOL,
                    "tool_choice": "auto", "stream": False}
            ep = url.rstrip("/") + "/chat/completions"
        t0 = time.time()
        with _stream_post(ep, body, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        m = (d.get("message") if api == "ollama" else d.get("choices", [{}])[0].get("message")) or {}
        ok = bool(m.get("tool_calls"))
        return {"tool_latency_s": round(time.time() - t0, 3), "tool_ok": 1 if ok else 0}
    except Exception:
        return {"tool_latency_s": None, "tool_ok": 0}


def store(rows: List[Dict[str, Any]], path: str = _DB) -> int:
    c = _db(path)
    for r in rows:
        c.execute("""INSERT INTO runtime_metrics
            (ts,model_id,runtime,url,api_type,ttft_s,tokens_per_sec,tool_latency_s,
             tool_ok,vram_mb,gpu_util,ok,error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (r.get("ts"), r.get("model_id"), r.get("runtime"), r.get("url"),
                   r.get("api_type"), r.get("ttft_s"), r.get("tokens_per_sec"),
                   r.get("tool_latency_s"), r.get("tool_ok"), r.get("vram_mb"),
                   r.get("gpu_util"), r.get("ok"), r.get("error")))
    c.commit(); c.close()
    return len(rows)


def load_metrics(path: str = _DB) -> Dict[str, Any]:
    """Latest row per model_id → {model_id: {ttft_s, tokens_per_sec, ...}}."""
    if not os.path.exists(path):
        return {}
    c = _db(path); c.row_factory = sqlite3.Row
    rows = c.execute("""SELECT * FROM runtime_metrics WHERE rowid IN
        (SELECT MAX(rowid) FROM runtime_metrics GROUP BY model_id)""").fetchall()
    c.close()
    return {r["model_id"]: {k: r[k] for k in r.keys()} for r in rows}


def benchmark_all(models: List[Dict[str, Any]], limit: int = 0,
                  path: str = _DB) -> Dict[str, Any]:
    rows = []
    for m in (models[:limit] if limit else models):
        rows.append(benchmark_model(m))
    store(rows, path)
    return {"benchmarked": len(rows), "results": rows}
