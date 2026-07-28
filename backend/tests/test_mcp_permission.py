"""
test_mcp_permission.py — an external tool is known, not trusted
===============================================================
Before this, every discovered MCP tool fell through to the unknown-capability
branch and was DENIED. That is the wrong word: an mcp__ tool was enumerated from
a server the operator declared, is namespaced so it cannot shadow a native tool,
and has its output quarantined. DENY means "never"; the honest verdict is "ask
the human".

The only thing that may lower that bar is the server's own per-tool
`readOnlyHint`/`destructiveHint`. Those hints are a claim, not proof, so the
asymmetry is deliberate and load-bearing:

    declared read-only AND non-destructive  → ALLOW
    anything else, including NO declaration → ESCALATE

An absent hint is treated as dangerous. The reference filesystem server declares
none, so not even `read_file` is auto-allowed — the House does not infer safety
from a tool's name.

    python -m pytest tests/test_mcp_permission.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import governance as g  # noqa: E402
import mcp_client as mc  # noqa: E402


@pytest.fixture()
def gate(tmp_path):
    return g.GPS2Gate(config_path=tmp_path / "cfg.json",
                      pending_path=tmp_path / "pending.json")


def _cached(monkeypatch, name, safety):
    monkeypatch.setattr(mc, "cached_tools", lambda: [
        {"type": "function", "function": {"name": name, "description": "", "parameters": {}},
         "x_mcp_safety": safety, "x_mcp_server": "srv"}])


# ── the default posture ──────────────────────────────────────────────────────
def test_undeclared_mcp_tool_escalates_rather_than_denies(gate, monkeypatch):
    _cached(monkeypatch, "mcp__srv__read_file",
            {"read_only": None, "destructive": None, "declared_safe": False})
    decision, why = gate.evaluate("mcp__srv__read_file", {})
    assert decision == "ESCALATE"
    assert "no read-only guarantee" in why


def test_a_read_sounding_name_is_not_enough(gate, monkeypatch):
    """Safety is never inferred from the name — only from a declaration."""
    _cached(monkeypatch, "mcp__srv__list_directory",
            {"read_only": None, "destructive": None, "declared_safe": False})
    assert gate.evaluate("mcp__srv__list_directory", {})[0] == "ESCALATE"


def test_declared_read_only_is_allowed(gate, monkeypatch):
    _cached(monkeypatch, "mcp__srv__get_weather",
            {"read_only": True, "destructive": False, "declared_safe": True})
    decision, why = gate.evaluate("mcp__srv__get_weather", {})
    assert decision == "ALLOW"
    assert "declared read-only" in why


def test_read_only_but_destructive_still_escalates(gate, monkeypatch):
    """Both conditions must hold; a contradictory declaration is not a licence."""
    _cached(monkeypatch, "mcp__srv__odd",
            {"read_only": True, "destructive": True, "declared_safe": False})
    assert gate.evaluate("mcp__srv__odd", {})[0] == "ESCALATE"


def test_a_tool_missing_from_the_cache_escalates(gate, monkeypatch):
    """Unknown to discovery ⇒ certainly not declared safe."""
    monkeypatch.setattr(mc, "cached_tools", lambda: [])
    assert gate.evaluate("mcp__srv__ghost", {})[0] == "ESCALATE"


def test_a_broken_cache_does_not_open_the_gate(gate, monkeypatch):
    def boom():
        raise RuntimeError("cache unreadable")
    monkeypatch.setattr(mc, "cached_tools", boom)
    # Fail closed: an error while checking safety must never read as safe.
    assert gate.evaluate("mcp__srv__anything", {})[0] == "ESCALATE"


# ── the rest of the policy is untouched ──────────────────────────────────────
def test_native_tools_are_unaffected(gate):
    assert gate.evaluate("read_file", {})[0] == "ALLOW"
    assert gate.evaluate("shell_command", {})[0] == "ESCALATE"


def test_a_genuinely_unknown_tool_is_still_denied(gate):
    """The unknown-capability rule must survive: only mcp__ was carved out."""
    decision, why = gate.evaluate("totally_made_up_tool", {})
    assert decision == "DENY"
    assert "unknown capability" in why


def test_mcp_prefix_cannot_be_spoofed_into_allow(gate, monkeypatch):
    """A native-looking name under the mcp__ prefix gets external treatment,
    never native trust."""
    _cached(monkeypatch, "mcp__srv__write_file",
            {"read_only": None, "destructive": None, "declared_safe": False})
    assert gate.evaluate("mcp__srv__write_file", {})[0] == "ESCALATE"
