"""
runtime_plugins/openai_driver.py — OX-RUNTIME-KERNEL-1
Driver for any OpenAI-compatible server: llama.cpp, LM Studio, vLLM, SGLang,
or a hosted OpenAI endpoint. All OpenAI-protocol logic lives here.
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, Iterable, List, Optional

from runtime_plugins.base import RuntimeDriver


class OpenAIDriver(RuntimeDriver):
    name = "openai"
    api_types = ("openai", "llamacpp", "lmstudio", "vllm", "sglang")

    def _get(self, url: str, timeout: float = 3.0):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            return None

    def connect(self, url: str) -> bool:
        # short timeout: offline runtimes (lmstudio/vllm/sglang) must not stall discovery
        return (self._get(url.rstrip("/") + "/models", timeout=1.2) is not None
                or self._get(url.rstrip("/") + "/health", timeout=1.0) is not None)

    def health(self, url: str) -> Dict[str, Any]:
        t0 = time.time()
        ok = self.connect(url)
        lat = time.time() - t0
        return {"alive": ok, "latency_s": round(lat, 3), "healthy": ok and lat < 3.0}

    def list_models(self, url: str) -> List[Dict[str, Any]]:
        import runtime_scanner as sc
        return sc._openai_models(url)

    def capabilities(self, url: str, model: str) -> Dict[str, Any]:
        # OpenAI /v1/models doesn't declare caps → infer minimal; tools proven by benchmark.
        return {"context": None, "tool_calling": None, "vision": None,
                "thinking": None, "embedding": ("embed" in (model or "").lower()) or None}

    def benchmark(self, url: str, model: str) -> Dict[str, Any]:
        import runtime_metrics as rm
        return rm.benchmark_model({"id": model, "url": url, "api_type": "openai",
                                   "runtime": "openai", "roles": ["Execution"]})

    def infer(self, url: str, model: str, messages: List[Dict[str, Any]],
              tools: Optional[list] = None, stream: bool = False,
              options: Optional[dict] = None) -> Iterable[str]:
        body: Dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        if (options or {}).get("temperature") is not None:
            body["temperature"] = options["temperature"]
        if tools:
            body["tools"] = tools; body["tool_choice"] = "auto"
        req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        acc: Dict[int, Dict[str, str]] = {}
        with urllib.request.urlopen(req, timeout=180) as r:
            for line in r:
                s = line.decode("utf-8", "replace").strip()
                if not s.startswith("data:"):
                    continue
                s = s[5:].strip()
                if s == "[DONE]":
                    break
                try: o = json.loads(s)
                except Exception: continue
                ch = (o.get("choices") or [{}])[0]
                delta = ch.get("delta") or ch.get("message") or {}
                if delta.get("content"):
                    yield json.dumps({"type": "text", "text": delta["content"]})
                for tc in (delta.get("tool_calls") or []):
                    i = tc.get("index", 0)
                    a = acc.setdefault(i, {"name": "", "arguments": ""})
                    fn = tc.get("function") or {}
                    if fn.get("name"): a["name"] = fn["name"]
                    if fn.get("arguments"): a["arguments"] += fn["arguments"]
                if ch.get("finish_reason"):
                    break
        if acc:
            calls = []
            for i in sorted(acc):
                v = acc[i]
                try:
                    args = json.loads(v["arguments"] or "{}")
                    if not isinstance(args, dict):
                        args = {"_raw": args}
                except Exception:
                    args = {"_raw": v["arguments"]}
                calls.append({"id": f"call_{i}", "type": "function",
                              "function": {"name": v["name"], "arguments": args}})
            yield json.dumps({"type": "__tool_calls__", "calls": calls})
        yield json.dumps({"type": "done"})

    def embeddings(self, url: str, model: str, texts: List[str]) -> List[List[float]]:
        body = {"model": model, "input": texts}
        req = urllib.request.Request(url.rstrip("/") + "/embeddings",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            return [e.get("embedding") or [] for e in d.get("data", [])]
        except Exception:
            return [[] for _ in texts]


DRIVER = OpenAIDriver()
