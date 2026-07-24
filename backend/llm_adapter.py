"""
llm_adapter.py — Universal cloud-LLM adapter for SkynetClaw
============================================================
One adapter covers every major provider because they all speak the
OpenAI-compatible /chat/completions dialect (incl. Anthropic and Gemini
via their official OpenAI-compat endpoints).

Event contract = identical to stream_ollama_chat in main.py:
  {"type":"text","text":...} {"type":"think","text":...}
  {"type":"__tool_calls__","calls":[{"id","type","function":{"name","arguments":<dict>}}]}
  {"type":"keepalive"} {"type":"error","msg":...} {"type":"done"}

So the agent loop, relay, UI, GPS-2 gate, and shadow gate all work unchanged.
"""
from __future__ import annotations

import json
import time
import asyncio
from typing import Any, AsyncGenerator, Dict, List

import httpx

# ── Provider presets (api_type → endpoint + fallback models) ─────────────────
PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "openai":     {"label": "OpenAI",          "base_url": "https://api.openai.com/v1",
                   "fallback_models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o3-mini"]},
    "anthropic":  {"label": "Anthropic Claude", "base_url": "https://api.anthropic.com/v1",
                   "fallback_models": ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5-20251001", "claude-fable-5"]},
    "gemini":     {"label": "Google Gemini",   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                   "fallback_models": ["gemini-2.0-flash", "gemini-1.5-pro"]},
    "groq":       {"label": "Groq",            "base_url": "https://api.groq.com/openai/v1",
                   "fallback_models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]},
    "openrouter": {"label": "OpenRouter",      "base_url": "https://openrouter.ai/api/v1",
                   "fallback_models": ["openrouter/auto"]},
    "deepseek":   {"label": "DeepSeek",        "base_url": "https://api.deepseek.com/v1",
                   "fallback_models": ["deepseek-chat", "deepseek-reasoner"]},
    "xai":        {"label": "xAI Grok",        "base_url": "https://api.x.ai/v1",
                   "fallback_models": ["grok-3", "grok-3-mini"]},
    "mistral":    {"label": "Mistral",         "base_url": "https://api.mistral.ai/v1",
                   "fallback_models": ["mistral-large-latest", "mistral-small-latest"]},
    "together":   {"label": "Together AI",     "base_url": "https://api.together.xyz/v1",
                   "fallback_models": []},
    "custom":     {"label": "Custom (OpenAI-compatible)", "base_url": "",
                   "fallback_models": []},
    "ollama":     {"label": "Local Ollama",    "base_url": "http://localhost:11434",
                   "fallback_models": []},
}

_LOCAL_TYPES = {"", "ollama", "local"}


def is_cloud(api_type: str | None) -> bool:
    return (api_type or "").strip().lower() not in _LOCAL_TYPES


def fallback_models(api_type: str | None) -> List[str]:
    p = PROVIDER_PRESETS.get((api_type or "").strip().lower())
    return list(p["fallback_models"]) if p else []


# ── Message sanitizer: Ollama-shaped history → strict OpenAI shape ────────────
def sanitize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ollama allows tool messages without ids and dict arguments; OpenAI does not.
    Pair role:tool messages to the preceding assistant tool_calls sequentially."""
    out: List[Dict[str, Any]] = []
    pending_ids: List[str] = []
    counter = 0
    for m in messages:
        role = m.get("role", "user")
        if role == "assistant" and m.get("tool_calls"):
            tcs = []
            pending_ids = []
            for tc in m["tool_calls"]:
                fn = (tc.get("function") or {})
                args = fn.get("arguments", {})
                if not isinstance(args, str):
                    args = json.dumps(args, ensure_ascii=False)
                counter += 1
                cid = tc.get("id") or f"call_{counter:06d}"
                pending_ids.append(cid)
                tcs.append({"id": cid, "type": "function",
                            "function": {"name": fn.get("name", ""), "arguments": args}})
            out.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": tcs})
        elif role == "tool":
            cid = pending_ids.pop(0) if pending_ids else f"call_orphan_{counter}"
            out.append({"role": "tool", "tool_call_id": cid,
                        "content": str(m.get("content", ""))})
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return out


# ── Streaming chat (OpenAI dialect) — same timeouts/keepalive policy as ollama ─
FIRST_CHUNK_TIMEOUT_S = 120.0   # cloud providers answer fast; still generous
NEXT_CHUNK_TIMEOUT_S = 90.0
STREAM_READ_TIMEOUT_S = 300.0


async def stream_openai_chat(payload: dict, base_url: str, api_key: str = "") -> AsyncGenerator[str, None]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: Dict[str, Any] = {
        "model": payload.get("model", ""),
        "messages": sanitize_messages(payload.get("messages", [])),
        "stream": True,
    }
    if payload.get("tools"):
        body["tools"] = payload["tools"]
    opts = payload.get("options") or {}
    if "temperature" in opts:
        body["temperature"] = opts["temperature"]
    # Anthropic's API (incl. its OpenAI-compatible endpoint) needs an explicit
    # max_tokens; OpenAI defaults it (and newer models reject the legacy field),
    # so scope this to Anthropic only to avoid a 400 on the first real call.
    if "anthropic.com" in (base_url or "") and "max_tokens" not in body:
        body["max_tokens"] = int(opts.get("max_tokens", 8192))

    url = base_url.rstrip("/") + "/chat/completions"
    first_token = False
    last_keepalive = time.time()
    tool_acc: Dict[int, Dict[str, str]] = {}

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=STREAM_READ_TIMEOUT_S, write=30.0, pool=10.0)
        ) as sc:
            async with sc.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    raw = await resp.aread()
                    yield json.dumps({"type": "error",
                                      "msg": f"{resp.status_code} from {url}: {raw[:400].decode(errors='replace')}"})
                    yield json.dumps({"type": "done"})
                    return
                yield json.dumps({"type": "keepalive", "note": "connected"})

                aiter = resp.aiter_lines()
                _pending = None
                _wait_started = time.time()
                while True:
                    line_timeout = NEXT_CHUNK_TIMEOUT_S if first_token else FIRST_CHUNK_TIMEOUT_S
                    # task-keeping watchdog — heartbeat while the provider thinks
                    if _pending is None:
                        _pending = asyncio.ensure_future(aiter.__anext__())
                        _wait_started = time.time()
                    try:
                        _done, _ = await asyncio.wait({_pending}, timeout=8.0)
                    except (GeneratorExit, asyncio.CancelledError):
                        try: _pending.cancel()
                        except Exception: pass
                        return
                    if not _done:
                        if time.time() - _wait_started > line_timeout:
                            try: _pending.cancel()
                            except Exception: pass
                            yield json.dumps({"type": "error",
                                              "msg": f"⏳ provider timeout {int(line_timeout)}s — เช็ค API key/credit หรือเปลี่ยน model"})
                            yield json.dumps({"type": "done"})
                            return
                        yield json.dumps({"type": "keepalive"})
                        last_keepalive = time.time()
                        continue
                    _task = _pending; _pending = None
                    try:
                        line = _task.result()
                    except StopAsyncIteration:
                        break
                    except (GeneratorExit, asyncio.CancelledError):
                        return

                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        ev = json.loads(data)
                    except Exception:
                        continue
                    ch = (ev.get("choices") or [{}])[0]
                    delta = ch.get("delta") or {}

                    rsn = delta.get("reasoning_content") or delta.get("reasoning")
                    if rsn:
                        first_token = True
                        yield json.dumps({"type": "think", "text": rsn})
                    if delta.get("content"):
                        first_token = True
                        yield json.dumps({"type": "text", "text": delta["content"]})
                    for tc in (delta.get("tool_calls") or []):
                        first_token = True
                        idx = int(tc.get("index", 0) or 0)
                        acc = tool_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            acc["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            acc["name"] += fn["name"]
                        if fn.get("arguments"):
                            acc["args"] += fn["arguments"]

                    now = time.time()
                    if now - last_keepalive > 8:
                        yield json.dumps({"type": "keepalive"})
                        last_keepalive = now

        if tool_acc:
            calls = []
            for idx in sorted(tool_acc):
                a = tool_acc[idx]
                try:
                    args = json.loads(a["args"] or "{}")
                    if not isinstance(args, dict):
                        args = {"_raw": args}
                except Exception:
                    args = {"_raw": a["args"]}
                calls.append({"id": a["id"] or f"call_{idx}", "type": "function",
                              "function": {"name": a["name"], "arguments": args}})
            yield json.dumps({"type": "__tool_calls__", "calls": calls})
        yield json.dumps({"type": "done"})

    except (GeneratorExit, asyncio.CancelledError):
        return
    except httpx.ConnectError as e:
        yield json.dumps({"type": "error", "msg": f"❌ ต่อ {url} ไม่ได้: {e}"})
        yield json.dumps({"type": "done"})
    except Exception as e:
        yield json.dumps({"type": "error", "msg": f"Adapter error [{type(e).__name__}]: {e}"})
        yield json.dumps({"type": "done"})


# ── Model listing (GET /models — same shape across providers) ────────────────
async def list_openai_models(base_url: str, api_key: str = "") -> List[str]:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=10) as cx:
        r = await cx.get(base_url.rstrip("/") + "/models", headers=headers)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", data if isinstance(data, list) else [])
        out = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
        return sorted(out)
