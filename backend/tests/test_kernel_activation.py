"""
test_kernel_activation.py — OX-KERNEL-ACTIVATION-1 Phase 10
Regression guards for the activation: the feature flag defaults OFF (legacy
untouched), the flag wiring exists, and the agent execution dispatch is
flag-gated. No model/runtime names appear in the activated path.
"""
from __future__ import annotations
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_flag_defaults_off(monkeypatch):
    import main
    monkeypatch.setattr(main, "load_settings", lambda: {})
    assert main._kernel_enabled() is False           # default OFF → legacy path


def test_flag_on_when_set(monkeypatch):
    import main
    monkeypatch.setattr(main, "load_settings", lambda: {"runtime_kernel_enabled": True})
    assert main._kernel_enabled() is True


def test_agent_dispatch_is_flag_gated():
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    # the agent loop must choose kernel vs legacy by the flag
    assert "if _kernel_enabled():" in src
    assert "_kernel_exec_stream(" in src
    # legacy path must still be present (compatibility)
    assert "_llm_stream(payload, base, key, api_type=_exec_api_type)" in src


def test_kernel_bridge_exists_and_is_async():
    import main, inspect
    assert inspect.isasyncgenfunction(main._kernel_exec_stream)


def test_activated_path_has_no_hardcoded_model_or_runtime_names():
    """The bridge passes role+messages+tools only — never a model/runtime name."""
    import main, inspect
    src = inspect.getsource(main._kernel_exec_stream)
    for banned in ("qwen", "gemma", "nemotron", "ollama", "llamacpp", "SkynetClaw"):
        assert banned.lower() not in src.lower(), f"activated path must not name {banned}"
