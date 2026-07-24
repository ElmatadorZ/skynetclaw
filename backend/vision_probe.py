"""
vision_probe.py — verify a model can ACTUALLY do vision (don't trust the label)
==============================================================================
Ollama's /api/show declares a `vision` capability, but declaration != reality:
verified 2026-07-13 that gemma4:26b advertises vision yet HTTP-500s on image
input, while elmatadorz:latest / qwen3.5:9b / nemotron3:33b genuinely read images.
Trusting the label makes the Vision role pool (and the Intel "Vision:N" count)
over-claim.

This probes a model with a tiny image and records the verdict:
  True  → responded to an image without error   (real vision)
  False → rejected the image (HTTP 4xx/5xx)      (declared but broken)
  None  → timeout / connection error             (unknown — do NOT penalise)

Results persist in vision_probe_cache.json. `is_broken()` is a cheap file read
(no network) used on the discovery path; `refresh()` does the networked probing
and is run opportunistically, never per request. Stdlib only.
License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision_probe_cache.json")
_TIMEOUT = 60          # allow a cold model to load; only a definitive HTTP error = broken
# a valid 8x8 white PNG fallback (used only if PIL is unavailable)
_TINY_PNG_B64_FALLBACK = ("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFUlEQVR4nGP8"
                          "//8/AzbAhFV00EoAAFbUAw037MyjAAAAAElFTkSuQmCC")


def _tiny_png_b64() -> str:
    """Build a valid tiny PNG deterministically (PIL) so the probe never sends a
    corrupt image; fall back to a known-good constant if PIL is absent."""
    try:
        import base64 as _b64, io as _io
        from PIL import Image
        buf = _io.BytesIO(); Image.new("RGB", (8, 8), "white").save(buf, "PNG")
        return _b64.b64encode(buf.getvalue()).decode()
    except Exception:
        return _TINY_PNG_B64_FALLBACK


def _load() -> Dict[str, object]:
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: Dict[str, object]) -> None:
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def cache() -> Dict[str, bool]:
    """Definitive verdicts only ({model: True|False}); unknowns are omitted."""
    out: Dict[str, bool] = {}
    for k, v in _load().items():
        if isinstance(v, dict) and isinstance(v.get("ok"), bool):
            out[k] = v["ok"]
    return out


def is_broken(model: str) -> bool:
    """True only when a probe DEFINITIVELY showed the model rejects images.
    Unprobed or timed-out models are never treated as broken (fail-safe)."""
    return cache().get(model) is False


def probe_model(model: str, base: str, timeout: int = _TIMEOUT) -> Optional[bool]:
    """Send a tiny image; True=accepted, False=HTTP-rejected, None=unknown."""
    base = (base or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    body = json.dumps({
        "model": model, "stream": False, "options": {"num_predict": 1, "temperature": 0},
        "messages": [{"role": "user", "content": "reply ok", "images": [_tiny_png_b64()]}],
    }).encode()
    req = urllib.request.Request(base + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=timeout).read()
        return True
    except urllib.error.HTTPError:
        return False                     # model rejected the image input → not vision
    except Exception:
        return None                      # timeout / offline → unknown, keep declared


def refresh(endpoints: List[Tuple[str, str]]) -> Dict[str, Optional[bool]]:
    """Probe each (model, base_url) once, persist verdicts. Returns {model: verdict}."""
    data = _load()
    out: Dict[str, Optional[bool]] = {}
    for model, base in endpoints:
        verdict = probe_model(model, base)
        out[model] = verdict
        if verdict is None:
            continue                     # don't overwrite a known verdict with unknown
        data[model] = {"ok": verdict, "ts": round(time.time(), 0), "url": base}
    _save(data)
    return out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # probe whatever the kernel currently lists as vision-declaring
    try:
        import vision_analyze
        eps = vision_analyze._vision_endpoints()
    except Exception:
        eps = [("elmatadorz:latest", "http://localhost:11434")]
    print("probing:", [m for m, _ in eps])
    print("verdicts:", refresh(eps))
    print("broken:", [m for m in cache() if cache()[m] is False])
