"""
test_resolve_window.py — PROTOCOL over MODEL: context window from the connection
================================================================================
"Models are temporary. Protocols endure." The context budget must be a property of
whatever model is behind the active connection, not a hardcoded 16384 constant.
This locks the resolution + the two invariants that matter most:
  * ZERO REGRESSION on local (llama.cpp/ollama on loopback stay 16384), including
    the OpenAI-compat-yet-local trap (llama.cpp speaks api_type "openai" but is
    16k-capped — distinguished by the loopback host, not the api_type).
  * a cloud model auto-gains its real window; an explicit connection declaration
    always wins; a truly-unknown remote falls back optimistically to the modern
    cloud floor (the user declares the window to override).

    python backend/tests/test_resolve_window.py
"""
from __future__ import annotations
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import context_budget as cb

RESULTS = {}

CASES = [
    # (name, kwargs, expected)
    ("local llama.cpp @ loopback (openai-compat, 16k-capped)",
     dict(conn={"base_url": "http://127.0.0.1:8080/v1", "api_type": "openai"}, model="qwen2.5-14b"), 16384),
    ("local ollama @ loopback",
     dict(conn={"base_url": "http://127.0.0.1:11434", "api_type": "ollama"}, model="llama3"), 16384),
    ("remote openai-compat, known model gpt-4o",
     dict(conn={"base_url": "https://api.openai.com/v1", "api_type": "openai"}, model="gpt-4o"), 128000),
    ("remote openai-compat, UNKNOWN model -> modern cloud floor",
     dict(conn={"base_url": "https://api.provider.com/v1", "api_type": "openai"}, model="mystery-1"), 128000),
    ("cloud claude by model hint",
     dict(conn={"base_url": "https://api.anthropic.com/v1", "api_type": "anthropic"}, model="claude-opus-4-8"), 200000),
    ("explicit connection declaration WINS over everything",
     dict(conn={"base_url": "https://api.openai.com/v1", "api_type": "openai", "context_window": 8000}, model="gpt-4o"), 8000),
    ("explicit declaration on a LOCAL conn raises its window",
     dict(conn={"base_url": "http://127.0.0.1:11434", "api_type": "ollama", "num_ctx": 32768}, model="qwen"), 32768),
]


def main():
    ok = True
    for name, kw, expect in CASES:
        got = cb.resolve_window(**kw)
        good = got == expect
        ok = ok and good
        print(f"  {'OK ' if good else 'FAIL'} {name[:56]:56} -> {got} (expect {expect})")
    # invariant assertions
    local = cb.resolve_window(conn={"base_url": "http://127.0.0.1:8080/v1", "api_type": "openai"}, model="qwen2.5-14b")
    assert local == 16384, "REGRESSION: local llama.cpp must stay 16384"
    RESULTS["all"] = ok
    print("\n  " + ("ALL RESOLVE-WINDOW TESTS PASS — protocol reads the model, zero regression on local"
                    if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
