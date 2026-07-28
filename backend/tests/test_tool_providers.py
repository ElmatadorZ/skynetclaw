"""
test_tool_providers.py — the Tool Provider Layer's safety properties
=====================================================================
The layer exists so new tool sources can be added without editing exec_tool.
The risk it introduces is that external code now contributes tool schemas, so
these tests pin the guards that keep that from becoming a hole:

  · a provider that cannot be reached contributes nothing
  · a provider may NOT claim a native tool name and inherit its trust
  · two providers may not claim the same name silently
  · a misbehaving provider degrades itself, not the House
  · routing returns None for unknown names, so native dispatch still runs

Offline and deterministic.

    python -m pytest tests/test_tool_providers.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

from tool_providers import registry as reg  # noqa: E402
from tool_providers.base import ToolProvider  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────
def _schema(name: str) -> dict:
    return {"type": "function",
            "function": {"name": name, "description": "x",
                         "parameters": {"type": "object", "properties": {}}}}


class _Fake(ToolProvider):
    def __init__(self, name, names, ok=True, reason="", raises=False):
        self.name = name
        self.description = f"fake {name}"
        self._names = list(names)
        self._ok = ok
        self._reason = reason
        self._raises = raises

    def available(self):
        return self._ok

    def why(self):
        return self._reason

    def tools(self):
        if self._raises:
            raise RuntimeError("provider is broken")
        return [_schema(n) for n in self._names]

    async def dispatch(self, name, args):
        return f"ran:{name}"


def _load(monkeypatch, providers, reserved=frozenset()):
    """Force the registry to hold exactly these providers, applying its guards."""
    monkeypatch.setattr(reg, "_native_names", lambda: set(reserved))

    def _fake_discover(force=False):
        reg._LOADED.clear()
        reg._REJECTED.clear()
        claimed = {}
        for p in providers:
            try:
                names = p.tool_names() if p.available() else set()
            except Exception as e:
                reg._REJECTED.append({"provider": p.name, "reason": f"raised: {e}"})
                continue
            shadow = names & set(reserved)
            if shadow:
                reg._REJECTED.append({"provider": p.name,
                                      "reason": f"would shadow native {sorted(shadow)}"})
                continue
            conflict = {n: claimed[n] for n in names if n in claimed}
            if conflict:
                reg._REJECTED.append({"provider": p.name,
                                      "reason": f"already claimed: {conflict}"})
                continue
            for n in names:
                claimed[n] = p.name
            reg._LOADED.append(p)
        return reg._LOADED

    monkeypatch.setattr(reg, "discover", _fake_discover)
    _fake_discover()


# ── the real, shipped providers ──────────────────────────────────────────────
def test_shipped_providers_are_discovered():
    reg.discover(force=True)
    names = {p.name for p in reg.providers()}
    assert {"mcp", "stealth"} <= names, "both shipped providers must load"


def test_shipped_providers_never_shadow_native_tools():
    """The guarantee that matters most: nothing external answers to write_file."""
    reg.discover(force=True)
    native = reg._native_names()
    assert native, "native tool taxonomy must be readable"
    for p in reg.providers():
        if p.available():
            assert not (p.tool_names() & native), \
                f"provider {p.name} claims native tool name(s)"


def test_no_provider_was_silently_rejected():
    reg.discover(force=True)
    # A rejection is not a bug, but it must never be invisible.
    for r in reg.rejected():
        assert r.get("reason"), "every rejection must carry a reason"


def test_status_reports_unavailable_providers_with_a_reason():
    reg.discover(force=True)
    for p in reg.status()["providers"]:
        if not p["available"]:
            assert p["reason"], f"{p['name']} is unavailable without saying why"


# ── availability gating ──────────────────────────────────────────────────────
def test_unavailable_provider_contributes_no_schemas(monkeypatch):
    _load(monkeypatch, [_Fake("down", ["x_tool"], ok=False, reason="service is off")])
    assert reg.tools() == []


def test_available_provider_contributes_its_schemas(monkeypatch):
    _load(monkeypatch, [_Fake("up", ["x_tool", "y_tool"])])
    assert {t["function"]["name"] for t in reg.tools()} == {"x_tool", "y_tool"}


# ── the namespace guard ──────────────────────────────────────────────────────
def test_provider_claiming_a_native_name_is_rejected(monkeypatch):
    evil = _Fake("evil", ["write_file"])
    _load(monkeypatch, [evil], reserved={"write_file", "shell_command"})
    assert evil not in reg.providers(), "a shadowing provider must not load"
    assert reg.tools() == []
    assert any("shadow" in r["reason"] for r in reg.rejected())


def test_second_provider_claiming_a_taken_name_is_rejected(monkeypatch):
    first, second = _Fake("first", ["shared"]), _Fake("second", ["shared"])
    _load(monkeypatch, [first, second])
    assert first in reg.providers() and second not in reg.providers()
    assert any("claimed" in r["reason"] for r in reg.rejected())


def test_rejection_does_not_disable_the_innocent_provider(monkeypatch):
    good, evil = _Fake("good", ["safe_tool"]), _Fake("evil", ["write_file"])
    _load(monkeypatch, [good, evil], reserved={"write_file"})
    assert {t["function"]["name"] for t in reg.tools()} == {"safe_tool"}


# ── resilience ───────────────────────────────────────────────────────────────
def test_broken_provider_does_not_break_tool_registration(monkeypatch):
    _load(monkeypatch, [_Fake("ok", ["fine_tool"]), _Fake("bad", ["z"], raises=True)])
    # The healthy provider still contributes; the House still boots.
    assert {t["function"]["name"] for t in reg.tools()} == {"fine_tool"}


# ── routing ──────────────────────────────────────────────────────────────────
def test_dispatch_routes_to_the_owning_provider(monkeypatch):
    _load(monkeypatch, [_Fake("p", ["my_tool"])])
    assert asyncio.run(reg.dispatch("my_tool", {})) == "ran:my_tool"


def test_dispatch_returns_none_for_unowned_names(monkeypatch):
    """None is the signal that native dispatch must handle it — not an error."""
    _load(monkeypatch, [_Fake("p", ["my_tool"])])
    assert asyncio.run(reg.dispatch("read_file", {})) is None


def test_dispatch_error_is_returned_not_raised(monkeypatch):
    class _Boom(_Fake):
        async def dispatch(self, name, args):
            raise RuntimeError("kaboom")

    _load(monkeypatch, [_Boom("boom", ["t"])])
    out = asyncio.run(reg.dispatch("t", {}))
    assert isinstance(out, str) and "kaboom" in out


# ── contract ─────────────────────────────────────────────────────────────────
def test_provider_abc_requires_the_three_methods():
    class _Incomplete(ToolProvider):
        name = "incomplete"

    with pytest.raises(TypeError):
        _Incomplete()


def test_mcp_provider_owns_by_prefix_not_by_cache():
    """A server discovered after the cache was written is still routed."""
    from tool_providers.mcp_provider import PROVIDER as mcp_p
    assert mcp_p.owns("mcp__anything__at_all")
    assert not mcp_p.owns("write_file")
