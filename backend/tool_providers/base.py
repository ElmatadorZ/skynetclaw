"""
tool_providers/base.py — the Tool Provider contract
====================================================
The House reaches every model runtime through a RuntimeDriver
(runtime_plugins/base.py): one interface, auto-discovered plugins, zero kernel
changes to add a runtime. That pattern has held. Tools never got it — they live
as 53 hardcoded branches inside a 1300-line `exec_tool`, so every new tool
source means editing the largest function in the codebase.

This is the same contract, for tools.

A provider answers three questions and does one job:

    available()   can I actually be reached right now?
    why()         if not, what must the operator do about it?
    tools()       which schemas may the agent see?
    dispatch()    execute one call, return a string

Two rules make the layer safe to grow:

  1. **A provider that cannot be reached offers nothing.** `tools()` is only
     consulted when `available()` is True. The agent is never shown a schema
     that would fail — a missing capability is reported, never simulated.

  2. **A provider namespaces its tools.** External sources must not be able to
     present a tool called `write_file` and inherit the trust the House extends
     to its own. Namespacing is checked by the registry, not left to good
     manners.

Providers are additive. This layer does not replace the native branches in
`exec_tool`; it grows beside them (strangler-fig), and native tools migrate one
group at a time or never. Nothing here changes governance: a provider returns a
string to `exec_tool`, so every call still passes the GPS-2 gate, the PRE_ACT
hook, and the audit chain.

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import abc
from typing import Any, Dict, List


class ToolProvider(abc.ABC):
    """One source of tools. Stateless between calls."""

    #: provider id, also the namespace segment (a-z0-9_)
    name: str = "base"

    #: short human description, shown in status output
    description: str = ""

    #: keywords that should surface this provider's tools for a task
    keywords: frozenset = frozenset()

    # ── reachability ─────────────────────────────────────────────────────────
    @abc.abstractmethod
    def available(self) -> bool:
        """True only when a call would genuinely be attempted.

        Must not raise. A provider whose dependency is missing, whose config is
        absent, or whose backing process is down returns False — it does not
        return True and fail later.
        """

    def why(self) -> str:
        """Actionable reason for `available() is False`. Empty when available."""
        return ""

    # ── surface ──────────────────────────────────────────────────────────────
    @abc.abstractmethod
    def tools(self) -> List[Dict[str, Any]]:
        """OpenAI-format function schemas. Only consulted when available()."""

    def tool_names(self) -> set:
        out = set()
        for t in self.tools():
            fn = t.get("function") or {}
            if fn.get("name"):
                out.add(fn["name"])
        return out

    def owns(self, name: str) -> bool:
        """Does this provider handle `name`? Override for prefix routing."""
        return name in self.tool_names()

    # ── execution ────────────────────────────────────────────────────────────
    @abc.abstractmethod
    async def dispatch(self, name: str, args: Dict[str, Any]) -> str:
        """Execute one tool call and return a compact string.

        Never raises: an error is a *returned* string, because the agent loop
        treats tool output as data and must be able to read the failure.
        """

    # ── introspection ────────────────────────────────────────────────────────
    def status(self) -> Dict[str, Any]:
        ok = False
        try:
            ok = bool(self.available())
        except Exception:
            ok = False
        return {
            "name": self.name,
            "description": self.description,
            "available": ok,
            "tools": len(self.tools()) if ok else 0,
            "reason": (self.why() or None) if not ok else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ToolProvider {self.name} available={self.available()}>"
