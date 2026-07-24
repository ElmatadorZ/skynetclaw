"""
runtime_plugins/ollama_driver.py — OX-RUNTIME-KERNEL-1
Driver for Ollama's native API. All Ollama-specific protocol lives here.
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, Iterable, List, Optional

from runtime_plugins.base import RuntimeDriver


class OllamaDriver(RuntimeDriver):
    name = "ollama"
    api_types = ("ollama",)

    def _get(self, url: str, timeout: float = 3.0):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            return None

    def connect(self, url: str) -> bool:
        return self._get(url.rstrip("/") + "/api/tags") is not None

    def health(self, url: str) -> Dict[str, Any]:
        t0 = time.time()
        ok = self.connect(url)
        lat = time.time() - t0
        return {"alive": ok, "latency_s": round(lat, 3), "healthy": ok and lat < 3.0}

    def list_models(self, url: str) -> List[Dict[str, Any]]:
        import runtime_scanner as sc            # reuse generic parsing helpers
        return sc._ollama_models(url)

    def capabilities(self, url: str, model: str) -> Dict[str, Any]:
        import runtime_scanner as sc
        show = sc._post(url.rstrip("/") + "/api/show", {"model": model}) or {}
        return sc.caps_from_ollama_show(show)

    def benchmark(self, url: str, model: str) -> Dict[str, Any]:
        import runtime_metrics as rm
        return rm.benchmark_model({"id": model, "url": url, "api_type": "ollama",
                                   "runtime": "ollama", "roles": ["Execution"]})

    def infer(self, url: str, model: str, messages: List[Dict[str, Any]],
              tools: Optional[list] = None, stream: bool = False,
              options: Optional[dict] = None) -> Iterable[str]:
        body: Dict[str, Any] = {"model": model, "messages": messages,
                                "stream": stream, "options": options or {}}
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(url.rstrip("/") + "/api/chat",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            for line in r:
                s = line.decode("utf-8", "replace").strip()
                if not s:
                    continue
                try: o = json.loads(s)
                except Exception: continue
                msg = o.get("message", {}) or {}
                if msg.get("content"):
                    yield json.dumps({"type": "text", "text": msg["content"]})
                if msg.get("tool_calls"):
                    calls = []
                    for j, tc in enumerate(msg["tool_calls"]):
                        fn = tc.get("function", {}) or {}
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try: args = json.loads(args or "{}")
                            except Exception: args = {"_raw": args}
                        calls.append({"id": tc.get("id") or f"call_{j}", "type": "function",
                                      "function": {"name": fn.get("name"), "arguments": args}})
                    yield json.dumps({"type": "__tool_calls__", "calls": calls})
                if o.get("done"):
                    yield json.dumps({"type": "done"})
                    break

    def embeddings(self, url: str, model: str, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            body = {"model": model, "input": t}
            req = urllib.request.Request(url.rstrip("/") + "/api/embeddings",
                                         data=json.dumps({"model": model, "prompt": t}).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read().decode("utf-8", "replace"))
                out.append(d.get("embedding") or [])
            except Exception:
                out.append([])
        return out


DRIVER = OllamaDriver()
