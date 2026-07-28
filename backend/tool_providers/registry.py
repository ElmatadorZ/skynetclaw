"""
tool_providers/registry.py — discovery, routing, and the namespace guard
=========================================================================
Mirrors the runtime kernel's plugin discovery: drop a module in this package
that exports `PROVIDER = SomeProvider()`, and it is found. No registry edit, no
main.py edit.

What the registry adds beyond a list:

  · **Availability gating.** Only reachable providers contribute schemas, so the
    agent is never offered a tool whose backing service is absent.

  · **A namespace guard that is enforced, not requested.** A provider claiming a
    tool name that a native tool already owns is REJECTED at load time. External
    code must not be able to present `write_file` and inherit the trust the
    House extends to its own filesystem tool. Collisions between two providers
    are rejected the same way — first loaded wins, the second is dropped and the
    conflict is reported rather than silently resolved.

  · **Honest status.** `status()` reports every provider including the ones that
    are unavailable, with the reason. A capability that is missing should be
    visible as missing.

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict, List, Optional

from .base import ToolProvider

_LOADED: List[ToolProvider] = []
_REJECTED: List[Dict[str, str]] = []
_DISCOVERED = False


def _native_names() -> set:
    """Tool names the House owns natively. A provider may never claim one.

    Read from tool_registry (the taxonomy), not from main, so the registry has
    no import cycle with the module that consumes it.
    """
    try:
        import tool_registry
        return set(getattr(tool_registry, "TOOL_CATEGORY", {}) or {})
    except Exception:
        return set()


def discover(force: bool = False) -> List[ToolProvider]:
    """Import every sibling module and collect its PROVIDER, with guards."""
    global _DISCOVERED
    if _DISCOVERED and not force:
        return _LOADED

    _LOADED.clear()
    _REJECTED.clear()

    reserved = _native_names()
    claimed: Dict[str, str] = {}

    # __path__ belongs to the package, not to this module.
    pkg_name = __name__.rsplit(".", 1)[0]
    pkg_path = importlib.import_module(pkg_name).__path__

    for mod in pkgutil.iter_modules(pkg_path):
        if mod.name in ("base", "registry") or mod.name.startswith("_"):
            continue
        try:
            m = importlib.import_module(f"{pkg_name}.{mod.name}")
        except Exception as e:
            _REJECTED.append({"provider": mod.name,
                              "reason": f"import failed: {type(e).__name__}: {e}"})
            continue

        provider = getattr(m, "PROVIDER", None)
        if not isinstance(provider, ToolProvider):
            _REJECTED.append({"provider": mod.name,
                              "reason": "module exports no PROVIDER of type ToolProvider"})
            continue

        # Namespace guard. A provider that cannot be reached is not inspected
        # for collisions — it offers nothing, so it can collide with nothing.
        try:
            names = provider.tool_names() if provider.available() else set()
        except Exception as e:
            _REJECTED.append({"provider": provider.name,
                              "reason": f"tool_names() raised: {type(e).__name__}: {e}"})
            continue

        shadowed = names & reserved
        if shadowed:
            _REJECTED.append({
                "provider": provider.name,
                "reason": ("refuses to load: would shadow native tool(s) "
                           f"{sorted(shadowed)} and inherit their trust"),
            })
            continue

        conflict = {n: claimed[n] for n in names if n in claimed}
        if conflict:
            _REJECTED.append({
                "provider": provider.name,
                "reason": f"tool name(s) already claimed by another provider: {conflict}",
            })
            continue

        for n in names:
            claimed[n] = provider.name
        _LOADED.append(provider)

    _DISCOVERED = True
    return _LOADED


def providers() -> List[ToolProvider]:
    return discover()


def rejected() -> List[Dict[str, str]]:
    """Providers that did NOT load, and why. Never silently empty a failure."""
    discover()
    return list(_REJECTED)


def tools() -> List[Dict[str, Any]]:
    """Every schema from every reachable provider."""
    out: List[Dict[str, Any]] = []
    for p in discover():
        try:
            if p.available():
                out.extend(p.tools())
        except Exception:
            # A provider that misbehaves contributes nothing rather than
            # breaking tool registration for the whole House.
            continue
    return out


def tool_groups() -> List[tuple]:
    """(keywords, tool_names) pairs, for task-based tool selection."""
    groups = []
    for p in discover():
        try:
            if p.available() and p.keywords:
                names = p.tool_names()
                if names:
                    groups.append((set(p.keywords), names))
        except Exception:
            continue
    return groups


def find(name: str) -> Optional[ToolProvider]:
    """Which provider owns this tool call, if any."""
    for p in discover():
        try:
            if p.available() and p.owns(name):
                return p
        except Exception:
            continue
    return None


async def dispatch(name: str, args: Dict[str, Any]) -> Optional[str]:
    """Route one call. Returns None when no provider owns the name, so the
    caller can fall through to the native dispatcher."""
    p = find(name)
    if p is None:
        return None
    try:
        return await p.dispatch(name, args or {})
    except Exception as e:
        return f"[{p.name} provider error] {type(e).__name__}: {e}"


def status() -> Dict[str, Any]:
    """Operator-facing summary, including what failed to load and why."""
    discover()
    return {
        "providers": [p.status() for p in _LOADED],
        "rejected": list(_REJECTED),
        "tools_total": len(tools()),
    }
