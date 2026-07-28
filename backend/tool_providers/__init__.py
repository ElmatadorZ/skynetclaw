"""
tool_providers — the Tool Provider Layer
=========================================
Tools reach the House through providers, the way runtimes reach it through
drivers. Add a module here that exports `PROVIDER = SomeProvider()` and it is
discovered; nothing else changes.

    from tool_providers import registry
    registry.tools()      # schemas from every reachable provider
    registry.status()     # including the ones that could not be reached, and why

See base.py for the contract and the two rules that keep it safe.
"""
from __future__ import annotations

from .base import ToolProvider  # noqa: F401

__all__ = ["ToolProvider", "registry"]
