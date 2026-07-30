"""
test_scanner_parallel.py — discovery must not cost a timeout per absent runtime
==============================================================================
Five well-known local endpoints are probed, and each absent one used to cost its
own 3s connect timeout serially — ~15s before the scan returned anything, landing
on the first agent request after boot. An Ollama library made it worse: /api/show
is one round trip PER MODEL, so twenty models meant twenty more timeouts.

Probing concurrently makes an absent runtime cost the timeout once for the whole
scan rather than once each, which in turn makes it free to ALSO probe wherever
OLLAMA_BASE_URL points — the address a container or a remote host actually uses,
which DEFAULT_PROBES pins to 127.0.0.1 and cannot know.

    python -m pytest tests/test_scanner_parallel.py -q
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import runtime_scanner as sc  # noqa: E402


# ── OLLAMA_BASE_URL is honoured, and adds rather than replaces ───────────────
def test_default_probes_is_localhost_only_without_the_env(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    urls = [p["url"] for p in sc.default_probes()]
    assert urls == [p["url"] for p in sc.DEFAULT_PROBES]


def test_ollama_base_url_is_added_first(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    probes = sc.default_probes()
    assert probes[0]["url"] == "http://ollama:11434"
    assert probes[0]["api_type"] == "ollama"
    # Added, not substituted: someone may run a local AND a remote runtime, and
    # with parallel probing the extra probe costs nothing.
    assert "http://127.0.0.1:11434" in [p["url"] for p in probes]


def test_a_duplicate_env_value_does_not_double_the_probe(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/")
    assert len(sc.default_probes()) == len(sc.DEFAULT_PROBES)


def test_an_empty_env_value_is_ignored(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "   ")
    assert len(sc.default_probes()) == len(sc.DEFAULT_PROBES)


# ── concurrency ──────────────────────────────────────────────────────────────
def test_probes_run_concurrently_not_serially(monkeypatch):
    """Six slow probes must take about one delay, not six."""
    DELAY = 0.25

    def _slow(probe):
        time.sleep(DELAY)
        return {"runtime": probe["runtime"], "url": probe["url"],
                "api_type": probe["api_type"], "online": True, "models": []}

    monkeypatch.setattr(sc, "scan_runtime", _slow)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    t0 = time.time()
    out = sc.scan()
    elapsed = time.time() - t0

    assert len(out) == len(sc.DEFAULT_PROBES)
    serial = DELAY * len(sc.DEFAULT_PROBES)
    assert elapsed < serial / 2, (
        f"took {elapsed:.2f}s; serial would be ~{serial:.2f}s — probes are not "
        "running concurrently")


def test_order_is_preserved_so_the_registry_is_reproducible(monkeypatch):
    """Probe order is documented as informational, but a scan that shuffled
    between runs would make every ranking built on it non-reproducible."""
    import random

    def _jittery(probe):
        time.sleep(random.uniform(0, 0.05))
        return {"runtime": probe["runtime"], "url": probe["url"],
                "api_type": probe["api_type"], "online": True, "models": []}

    monkeypatch.setattr(sc, "scan_runtime", _jittery)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    expected = [p["runtime"] for p in sc.DEFAULT_PROBES]
    for _ in range(4):
        assert [r["runtime"] for r in sc.scan()] == expected


def test_one_failing_probe_does_not_lose_the_others(monkeypatch):
    def _mixed(probe):
        if probe["runtime"] == "vllm":
            raise RuntimeError("probe blew up")
        return {"runtime": probe["runtime"], "url": probe["url"],
                "api_type": probe["api_type"], "online": True, "models": []}

    monkeypatch.setattr(sc, "scan_runtime", _mixed)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    got = [r["runtime"] for r in sc.scan()]
    assert "vllm" not in got
    assert len(got) == len(sc.DEFAULT_PROBES) - 1


def test_duplicate_urls_are_probed_once(monkeypatch):
    calls = []

    def _count(probe):
        calls.append(probe["url"])
        return {"runtime": probe["runtime"], "url": probe["url"],
                "api_type": probe["api_type"], "online": True, "models": []}

    monkeypatch.setattr(sc, "scan_runtime", _count)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    sc.scan(extra_probes=[{"runtime": "dup", "url": "http://127.0.0.1:11434",
                           "api_type": "ollama"}])
    assert calls.count("http://127.0.0.1:11434") == 1


# ── the /api/show fan-out ────────────────────────────────────────────────────
def test_per_model_show_calls_run_concurrently(monkeypatch):
    """A library of models must not cost one timeout each."""
    DELAY, N = 0.15, 8
    monkeypatch.setattr(sc, "_get", lambda *a, **k: {
        "models": [{"name": f"m{i}:7b", "size": 1} for i in range(N)]})

    def _slow_post(url, body, timeout=6.0, api_key=None):
        time.sleep(DELAY)
        return {"capabilities": ["tools"], "details": {"parameter_size": "7B"}}

    monkeypatch.setattr(sc, "_post", _slow_post)
    t0 = time.time()
    models = sc._ollama_models("http://127.0.0.1:11434")
    elapsed = time.time() - t0

    assert len(models) == N
    assert all(m["tool_calling"] is True for m in models), \
        "capabilities must still be attached to the right model"
    assert elapsed < (DELAY * N) / 2, (
        f"took {elapsed:.2f}s; serial would be ~{DELAY * N:.2f}s")


def test_show_results_stay_matched_to_their_model(monkeypatch):
    """Concurrency must not cross-wire capabilities onto the wrong model."""
    monkeypatch.setattr(sc, "_get", lambda *a, **k: {"models": [
        {"name": "vision-one:7b", "size": 1},
        {"name": "tools-two:7b", "size": 1},
    ]})

    def _post(url, body, timeout=6.0, api_key=None):
        if body["model"].startswith("vision"):
            return {"capabilities": ["vision"], "details": {"parameter_size": "7B"}}
        return {"capabilities": ["tools"], "details": {"parameter_size": "7B"}}

    monkeypatch.setattr(sc, "_post", _post)
    a, b = sc._ollama_models("http://x")
    assert a["id"] == "vision-one:7b" and a["vision"] is True and a["tool_calling"] is False
    assert b["id"] == "tools-two:7b" and b["tool_calling"] is True and b["vision"] is False
