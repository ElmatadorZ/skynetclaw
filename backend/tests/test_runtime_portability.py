"""
test_runtime_portability.py — the scanner must serve machines that are not the author's
=======================================================================================
An audit across realistic model sets found three ways the discovery layer was
calibrated to one box.

1. Every OpenAI-compatible and cloud model was barred from Reasoning and
   Council. `/v1/models` states no parameter count, so those arrive with
   param_b=None, and the rule read `pb is not None and pb >= 18` — so GPT-4o was
   Execution-only while a local 8B could hold the same role. The asymmetry was
   accidental: the very next branch up already treats unknown tool_calling as
   ELIGIBLE, not disqualified.

2. The role fallback was capability-blind. Asked for Vision with no vision model
   installed, it returned a code model. That is not degradation — a text model
   handed an image answers wrongly or errors.

3. A runtime behind an API key answered 401 and was filed as OFFLINE,
   indistinguishable from "not running", so the operator was told to restart a
   server that was already up.

    python -m pytest tests/test_runtime_portability.py -q
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import runtime_registry as reg  # noqa: E402
import runtime_router as rt  # noqa: E402
import runtime_scanner as sc  # noqa: E402


def mdl(mid, pb, **k):
    return {"id": mid, "param_b": pb, "tool_calling": k.get("tools"),
            "thinking": k.get("thinking"), "vision": k.get("vision"),
            "embedding": k.get("embedding"), "context": k.get("ctx", 8192),
            "api_type": k.get("api", "ollama")}


def registry_of(models):
    return reg.build_registry(
        [{"runtime": "r", "url": "http://x", "api_type": "ollama",
          "online": True, "models": models}], {})


# ── 1. undeclared size is not a disqualification ─────────────────────────────
def test_cloud_model_can_hold_a_reasoning_role():
    """A hosted model states no parameter count; that is not evidence of being small."""
    roles = reg.classify(mdl("gpt-4o", None, ctx=128000, api="openai"))
    assert "Reasoning" in roles
    assert "Council" in roles


def test_a_known_small_model_still_cannot_be_council():
    """The fix must not turn the threshold off — a measured 8B is genuinely not
    council-class, and saying otherwise would be the flattering answer."""
    roles = reg.classify(mdl("llama3.1:8b", 8.0, tools=True))
    assert "Execution" in roles
    assert "Council" not in roles
    assert "Reasoning" not in roles


def test_a_declared_thinking_model_reasons_regardless_of_size():
    assert "Reasoning" in reg.classify(mdl("deepseek-r1:7b", 7.0, thinking=True))


def test_known_size_outranks_undeclared_for_council():
    """Eligibility widened; preference did not. A model measured above the bar must
    still beat one that merely might be."""
    r = registry_of([mdl("nemotron:33b", 33.0, tools=True, thinking=True),
                     mdl("mystery-hosted", None, ctx=32000, api="openai")])
    assert r["rankings"]["Council"][0]["id"] == "nemotron:33b"


def test_role_basis_distinguishes_measured_from_assumed():
    r = registry_of([mdl("mystery-hosted", None, api="openai")])
    assert "undeclared" in r["models"][0]["role_basis"]
    r2 = registry_of([mdl("llama3.1:8b", 8.0, tools=True)])
    assert r2["models"][0]["role_basis"] == "declared-capability"


# ── 2. hard capabilities are never substituted ───────────────────────────────
def test_vision_request_refuses_rather_than_returning_a_text_model():
    r = rt.route_with_registry("Vision", registry_of([mdl("llama3.1:8b", 8.0, tools=True)]),
                               is_role=True)
    assert r["model"] is None
    assert "declares the Vision capability" in r["reason"]


def test_embedding_request_refuses_rather_than_substituting():
    r = rt.route_with_registry("Embedding", registry_of([mdl("llama3.1:8b", 8.0, tools=True)]),
                               is_role=True)
    assert r["model"] is None


def test_a_real_vision_model_is_still_routed():
    r = rt.route_with_registry("Vision", registry_of([mdl("llava:7b", 7.0, vision=True)]),
                               is_role=True)
    assert r["model"] == "llava:7b"


# ── 3. a quality substitution is reported, not hidden ────────────────────────
def test_council_substitution_is_flagged_and_explained():
    r = rt.route_with_registry("Council", registry_of([mdl("llama3.1:8b", 8.0, tools=True)]),
                               is_role=True)
    assert r["model"] == "llama3.1:8b"
    assert r["substituted"] is True
    assert r["requested_role"] == "Council"
    assert "expect lower quality" in r["reason"]


def test_no_substitution_flag_when_the_role_was_filled():
    r = rt.route_with_registry("Council", registry_of([mdl("big:70b", 70.0, tools=True)]),
                               is_role=True)
    assert r.get("substituted") is None


# ── 4. a refusal is not an absence ───────────────────────────────────────────
def _fake_http(code):
    def _urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "no", {}, None)
    return _urlopen


def test_a_401_reports_unauthorized_and_still_online(monkeypatch):
    monkeypatch.setattr(sc.urllib.request, "urlopen", _fake_http(401))
    out = sc.scan_runtime({"runtime": "vllm", "url": "http://127.0.0.1:8000/v1",
                           "api_type": "openai"})
    assert out["online"] is True, "something answered — it is not offline"
    assert out["authorized"] is False
    assert "running, not down" in out["reason"]


def test_a_connection_refusal_is_offline(monkeypatch):
    def _boom(req, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(sc.urllib.request, "urlopen", _boom)
    out = sc.scan_runtime({"runtime": "vllm", "url": "http://127.0.0.1:8000/v1",
                           "api_type": "openai"})
    assert out["online"] is False
    assert "authorized" not in out


def test_the_api_key_is_sent_when_provided():
    assert sc._headers("sk-abc")["Authorization"] == "Bearer sk-abc"
    assert "Authorization" not in sc._headers(None)


def test_an_unauthorized_runtime_is_marked_on_its_models():
    r = reg.build_registry([{
        "runtime": "vllm", "url": "http://x", "api_type": "openai", "online": True,
        "authorized": False, "reason": "needs a key",
        "models": [mdl("served", None, api="openai")],
    }], {})
    assert r["models"][0]["authorized"] is False
    assert r["models"][0]["unavailable_reason"] == "needs a key"


# ── the property that must not regress ───────────────────────────────────────
def test_no_model_name_influences_classification():
    """Rename a model and nothing about its roles may change."""
    a = mdl("qwen2.5-coder:7b", 7.0, tools=True)
    b = dict(a, id="frobozz-42x")
    assert reg.classify(a) == reg.classify(b)
