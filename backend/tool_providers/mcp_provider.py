"""
tool_providers/mcp_provider.py — the MCP ecosystem as one provider
==================================================================
Wraps mcp_client. All behaviour lives there (discovery, namespacing, the
untrusted-content quarantine); this only presents it through the ToolProvider
contract so the registry can route to it.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import ToolProvider


class MCPProvider(ToolProvider):
    name = "mcp"
    description = "External MCP servers (filesystem, github, postgres, ...)"
    keywords = frozenset({
        "mcp", "external tool", "external server", "เครื่องมือภายนอก",
        "integration", "connector", "เชื่อมต่อ",
    })

    def _mod(self):
        import mcp_client
        return mcp_client

    def available(self) -> bool:
        try:
            return bool(self._mod().available())
        except Exception:
            return False

    def why(self) -> str:
        try:
            return self._mod().why_unavailable()
        except Exception as e:
            return f"mcp_client unavailable: {type(e).__name__}: {e}"

    def tools(self) -> List[Dict[str, Any]]:
        try:
            return list(self._mod().cached_tools())
        except Exception:
            return []

    def owns(self, name: str) -> bool:
        # Prefix routing: every MCP tool is mcp__<server>__<tool>, so ownership
        # is decided by the namespace rather than by a cached name list. A
        # server discovered after the cache was read is still routed correctly.
        return name.startswith("mcp__")

    async def dispatch(self, name: str, args: Dict[str, Any]) -> str:
        return await self._mod().dispatch(name, args)


PROVIDER = MCPProvider()
