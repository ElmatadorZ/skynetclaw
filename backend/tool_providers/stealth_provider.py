"""
tool_providers/stealth_provider.py — the stealth browser as a provider
=======================================================================
Wraps stealth_bridge, which reaches a real-Chrome automation surface running in
its own process and virtualenv. Behaviour stays in the bridge; this presents it
through the ToolProvider contract.

Note on availability: the bridge's `is_up()` performs a network probe. Schema
registration must not depend on a live probe at import time — the browser is
routinely started after the House — so availability here means "the bridge
module is loadable", and an offline shim is reported by dispatch with
instructions to start it. That is the behaviour the House already had; the
provider preserves it rather than quietly changing when tools appear.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import ToolProvider


class StealthProvider(ToolProvider):
    name = "stealth"
    description = "Undetectable real-Chrome browser (Cloudflare/antibot capable)"
    keywords = frozenset({
        "cloudflare", "antibot", "anti-bot", "stealth", "scrape", "ขูด", "ขูดข้อมูล",
        "bypass", "captcha", "undetect", "บล็อก", "เว็บบล็อก", "โดนบล็อก", "real browser",
        "instagram", "linkedin", "twitter", "โซเชียล", "ดึงหน้าเว็บ", "หน้าเว็บที่บล็อก",
    })

    def _mod(self):
        import stealth_bridge
        return stealth_bridge

    def available(self) -> bool:
        try:
            self._mod()
            return True
        except Exception:
            return False

    def why(self) -> str:
        try:
            self._mod()
            return ""
        except Exception as e:
            return f"stealth_bridge not importable: {type(e).__name__}: {e}"

    def tools(self) -> List[Dict[str, Any]]:
        try:
            return list(self._mod().TOOLS)
        except Exception:
            return []

    def owns(self, name: str) -> bool:
        try:
            return name in self._mod().TOOL_NAMES
        except Exception:
            return False

    async def dispatch(self, name: str, args: Dict[str, Any]) -> str:
        # The bridge's dispatch is synchronous; it performs blocking HTTP to a
        # localhost shim. Kept off the event loop so a slow page cannot stall
        # the agent loop.
        import asyncio
        mod = self._mod()
        return await asyncio.to_thread(mod.dispatch, name, args)


PROVIDER = StealthProvider()
