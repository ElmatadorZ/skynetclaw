"""
test_runtime_discovery.py — OX-RUNTIME-DISCOVERY-1 Phase 11
Unit tests for the capability-based runtime layer. NO model names drive logic —
these tests prove a model classifies/routes purely by capability. Network probes
are exercised live elsewhere; here everything is pure/deterministic.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runtime_scanner as S
import runtime_registry as R
import runtime_router as RT


# ── scanner pure parsers ──────────────────────────────────────────────────────
def test_parse_param_b():
    assert S.parse_param_b("9B") == 9.0
    assert S.parse_param_b("7.6B") == 7.6
    assert S.parse_param_b("26b") == 26.0
    assert S.parse_param_b("frobozz") is None


def test_caps_from_ollama_show():
    show = {"capabilities": ["completion", "tools", "thinking"],
            "model_info": {"general.context_length": 32768},
            "details": {"parameter_size": "9B", "quantization_level": "Q4_K_M", "family": "frob"}}
    c = S.caps_from_ollama_show(show)
    assert c["tool_calling"] and c["thinking"] and not c["vision"] and not c["embedding"]
    assert c["context"] == 32768 and c["parameters"] == "9B" and c["family"] == "frob"


# ── classification (capability → role, name-agnostic) ─────────────────────────
def test_classify_execution_small_tools():
    m = {"id": "anything-x", "param_b": 7.0, "tool_calling": True}
    assert "Execution" in R.classify(m)


def test_classify_reasoning_and_council_by_size():
    assert "Reasoning" in R.classify({"id": "z", "param_b": 26.0})
    assert "Council" in R.classify({"id": "z", "param_b": 33.0})
    assert "Council" not in R.classify({"id": "z", "param_b": 9.0})


def test_classify_thinking_is_reasoning():
    assert "Reasoning" in R.classify({"id": "z", "param_b": 4.0, "thinking": True})


def test_classify_embedding_is_exclusive():
    assert R.classify({"id": "z", "embedding": True, "param_b": 1.0}) == ["Embedding"]


def test_classify_unknown_tools_still_execution_eligible():
    # OpenAI /v1/models leaves tool_calling=None → still eligible (not False)
    assert "Execution" in R.classify({"id": "z", "param_b": 7.0, "tool_calling": None})


def test_classify_name_irrelevance():
    # identical capabilities → identical roles regardless of id
    a = R.classify({"id": "qwen3.5:9b", "param_b": 9.0, "tool_calling": True})
    b = R.classify({"id": "totally-made-up-name", "param_b": 9.0, "tool_calling": True})
    assert a == b


# ── ranking + routing ─────────────────────────────────────────────────────────
def _registry():
    scan = [
        {"runtime": "llamacpp", "url": "http://h:8080/v1", "api_type": "openai", "online": True,
         "models": [{"id": "exec-gpu", "param_b": 7.0, "tool_calling": True}]},
        {"runtime": "ollama", "url": "http://h:11434", "api_type": "ollama", "online": True,
         "models": [{"id": "big-reasoner", "param_b": 33.0, "thinking": True,
                     "tool_calling": True, "context": 32768},
                    {"id": "embedder", "param_b": 0.3, "embedding": True}]},
    ]
    return R.build_registry(scan, metrics={"exec-gpu": {"ttft_s": 0.9, "tokens_per_sec": 2000}})


def test_execution_prefers_gpu_fast_model():
    r = RT.route_with_registry("create a file", _registry())
    assert r["role"] == "Execution" and r["model"] == "exec-gpu" and r["runtime"] == "llamacpp"
    assert r["endpoint"].endswith("/chat/completions")


def test_reasoning_routes_to_large_model():
    r = RT.route_with_registry("analyze and plan the strategy", _registry())
    assert r["role"] == "Reasoning" and r["model"] == "big-reasoner"
    assert r["endpoint"].endswith("/api/chat")


def test_task_to_role_intent():
    assert RT.task_to_role("create and save a file") == "Execution"
    assert RT.task_to_role("analyze why this failed") == "Reasoning"
    assert RT.task_to_role("embed these vectors") == "Embedding"
    assert RT.task_to_role("") == "Execution"   # execution-first default


def test_route_no_runtime_graceful():
    r = RT.route_with_registry("create a file", {"rankings": {}})
    assert r["model"] is None and "no runtime" in r["reason"]


def test_health_report_partition():
    scan = [{"runtime": "ollama", "url": "http://127.0.0.1:1/x", "api_type": "ollama", "models": []}]
    hr = RT.health_report(scan)   # unreachable port → unhealthy
    assert "ollama" in hr["unhealthy"]


def test_paths_describe():
    import importlib
    p = importlib.import_module("config.paths")
    d = p.describe()
    assert d["mode"] in ("source", "portable", "installed", "exe")
    assert "user_data" in d and "runtime" in d
