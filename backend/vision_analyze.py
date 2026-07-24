"""
vision_analyze.py — read an image with a LOCAL multimodal model
================================================================
Surfaces the House's real Vision capability (the Ollama Vision-role pool) as a
callable primitive: give an image + a question, get an answer. Fully offline.

Grounded in verified evidence (2026-07-13): elmatadorz:latest / qwen3.5:9b /
nemotron3:33b genuinely read images (digits, letters, colours); some declared-
vision models (e.g. gemma4:26b) 500 on image input — so we try the verified
default first and FALL BACK across the pool on any error. No fabrication: if no
vision model answers, we say so.

Stdlib only; the kernel is a lazy import. License: Apache-2.0.
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Tuple

DEFAULT_MODEL = "elmatadorz:latest"     # verified working (reads text/shape/colour)
_TIMEOUT = 90


def _broken() -> set:
    """Models a probe DEFINITIVELY showed cannot do vision (no hardcoding)."""
    try:
        import vision_probe
        return {m for m, ok in vision_probe.cache().items() if ok is False}
    except Exception:
        return set()
_B64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")


def _vision_endpoints() -> List[Tuple[str, str]]:
    """[(model, ollama_base_url)] from the kernel Vision pool — verified default
    first, known-bad models last. Falls back to the default endpoint if the
    kernel is unavailable."""
    out: List[Tuple[str, str]] = []
    try:
        import runtime_kernel as rk
        for m in rk.get_kernel(rediscover=False).pools().get("Vision", []):
            url = (m.get("url") or "").rstrip("/")
            if url.endswith("/v1"):
                url = url[:-3]                       # Ollama images API lives at /api/chat
            out.append((m["model"], url or "http://localhost:11434"))
    except Exception:
        pass
    if not out:
        out = [(DEFAULT_MODEL, "http://localhost:11434")]

    broken = _broken()
    def rank(t: Tuple[str, str]) -> int:
        if t[0] == DEFAULT_MODEL:
            return 0
        if t[0] in broken:
            return 2
        return 1
    # de-dup preserving order, then rank
    seen = set(); uniq = []
    for t in out:
        if t[0] not in seen:
            seen.add(t[0]); uniq.append(t)
    uniq.sort(key=rank)
    return uniq


def _load_b64(image: str) -> str:
    """`image` is a file path (preferred) or an already-base64 string."""
    s = str(image or "").strip()
    if not s:
        raise FileNotFoundError("no image given")
    if os.path.exists(s):
        with open(s, "rb") as f:
            return base64.b64encode(f.read()).decode()
    stripped = re.sub(r"\s", "", s)
    if len(stripped) > 100 and _B64_RE.match(s):
        return stripped                              # looks like raw base64
    raise FileNotFoundError(f"image not found: {s[:80]}")


def analyze(image: str, question: str = "Describe this image in detail.",
            model: str = "") -> Dict[str, Any]:
    """Answer `question` about `image` using a local vision model. Returns
    {ok, text, model} or {ok:False, error}. Never raises for model/IO errors."""
    try:
        b64 = _load_b64(image)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    eps = _vision_endpoints()
    if model:
        eps = [(model, eps[0][1])] + [(m, u) for m, u in eps if m != model]
    errors: List[str] = []
    for m, base in eps:
        body = json.dumps({
            "model": m, "stream": False, "options": {"temperature": 0},
            "messages": [{"role": "user", "content": question, "images": [b64]}],
        }).encode()
        req = urllib.request.Request(base + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=_TIMEOUT).read())
            txt = ((r.get("message") or {}).get("content") or "").strip()
            if txt:
                return {"ok": True, "text": txt, "model": m}
            errors.append(f"{m}: empty reply")
        except Exception as e:
            errors.append(f"{m}: {str(e)[:60]}")
            continue
    return {"ok": False, "error": "; ".join(errors[:3]) or "no vision model available"}


def available() -> List[str]:
    """Vision model ids the kernel currently exposes (for status/diagnostics)."""
    return [m for m, _ in _vision_endpoints()]
