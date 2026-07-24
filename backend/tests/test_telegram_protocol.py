"""
test_telegram_protocol.py — Telegram reply protocol adapter (regression)
========================================================================
Reproduces and locks the fix for a real incident: the Telegram bot reused the
globally-active connection but hardcoded the Ollama chat protocol
(POST {base}/api/chat). With an OpenAI-compatible active connection whose
base_url ends in /v1 (llama.cpp on :8080, alias ElmatadorZ), every reply hit
    http://127.0.0.1:8080/v1/api/chat  -> HTTP 404 File Not Found
so the bot received messages but could never answer. Verified live before the
fix (404) and after (200 + reply).

These tests are hermetic — they exercise the pure protocol helpers, no server
or network needed:

    python backend/tests/test_telegram_protocol.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as m

RESULTS = {}


def t_protocol_detection():
    print("== T1: _tg_is_openai protocol detection ==")
    cases = [
        # (base_url, api_type, expected_openai)
        ("http://127.0.0.1:8080/v1", "openai", True),    # the execution connection
        ("http://127.0.0.1:8080/v1", "",       True),    # /v1 fallback when api_type blank
        ("http://127.0.0.1:8080/v1/", "",      True),    # trailing slash tolerated
        ("http://localhost:11434",   "ollama", False),   # the Local Ollama connection
        ("http://localhost:11434",   "",       False),   # no /v1, no api_type -> Ollama
        ("https://api.openai.com/v1","openai", True),
        ("http://x:9/v1",            "custom", True),
        ("http://x:9",               "vllm",   True),    # api_type wins over missing /v1
    ]
    ok = True
    for base, at, exp in cases:
        got = m._tg_is_openai(base, at)
        flag = "OK " if got == exp else "FAIL"
        if got != exp: ok = False
        print(f"  {flag} is_openai({base!r},{at!r}) = {got} (exp {exp})")
    RESULTS["T1"] = ok
    assert ok, "protocol detection wrong"


def t_request_build():
    print("== T2: _tg_build_request URL + payload per protocol ==")
    ok = True
    msgs = [{"role": "user", "content": "hi"}]

    # OpenAI / execution connection — THE regression case
    url, pl = m._tg_build_request("http://127.0.0.1:8080/v1", "openai", "ElmatadorZ", msgs)
    checks = {
        "openai url is /v1/chat/completions": url == "http://127.0.0.1:8080/v1/chat/completions",
        "openai url is NOT the broken /v1/api/chat": url != "http://127.0.0.1:8080/v1/api/chat",
        "openai url does not contain /api/chat": "/api/chat" not in url,
        "openai payload has max_tokens": "max_tokens" in pl,
        "openai payload has no ollama 'options'": "options" not in pl,
        "openai carries model+messages": pl.get("model") == "ElmatadorZ" and pl.get("messages") == msgs,
    }
    for k, v in checks.items():
        if not v: ok = False
        print(f"  {'OK ' if v else 'FAIL'} {k}")

    # Ollama connection
    url2, pl2 = m._tg_build_request("http://localhost:11434", "ollama", "SkynetClaw:latest", msgs)
    checks2 = {
        "ollama url is /api/chat": url2 == "http://localhost:11434/api/chat",
        "ollama payload has options.num_ctx": pl2.get("options", {}).get("num_ctx") == 2048,
        "ollama payload has no openai max_tokens": "max_tokens" not in pl2,
    }
    for k, v in checks2.items():
        if not v: ok = False
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = ok
    assert ok, "request build wrong"


def t_reply_extraction():
    print("== T3: _tg_extract_reply parses both response shapes ==")
    cases = [
        ("openai message", {"choices": [{"message": {"content": " hi "}}]}, "hi"),
        ("openai text",    {"choices": [{"text": " legacy "}]},            "legacy"),
        ("ollama message", {"message": {"content": " yo "}},               "yo"),
        ("ollama response",{"response": " old "},                          "old"),
        ("empty choices",  {"choices": []},                                ""),
        ("garbage",        {"unexpected": 1},                              ""),
        ("not a dict",     "boom",                                         ""),
    ]
    ok = True
    for name, data, exp in cases:
        got = m._tg_extract_reply(data)
        if got != exp: ok = False
        print(f"  {'OK ' if got == exp else 'FAIL'} {name}: {got!r} (exp {exp!r})")
    RESULTS["T3"] = ok
    assert ok, "reply extraction wrong"


def main():
    t_protocol_detection()
    t_request_build()
    t_reply_extraction()
    print("\n== SUMMARY ==")
    allok = all(RESULTS.get(k) for k in ("T1", "T2", "T3"))
    for k in ("T1", "T2", "T3"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL TELEGRAM PROTOCOL TESTS PASS" if allok else "FAILURES PRESENT"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
