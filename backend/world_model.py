"""
world_model.py — OX-1.1 WORLD MODEL (per-run, in-memory)
========================================================
The House must VERIFY before it acts — never assume a path, file, directory or
tool exists. This is a per-run ledger of what the run has actually OBSERVED to
exist or be absent, populated from REAL tool results (not assumptions).

It is runtime EXECUTION context, NOT institutional memory:
  * in-memory, per agent run — never persisted, no DB, no shadow state.
  * derived entirely from tool outputs the run already produced.

Used by the agent loop to (a) inject a VERIFIED WORLD block into the prompt so
the model stops guessing, and (b) gate actions that target a known-absent path.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

EXISTS = "verified_exists"
ABSENT = "verified_absent"
UNVERIFIED = "unverified"


class WorldModel:
    """Per-run verified-entity ledger. entity -> {status, kind, source, ts}."""

    def __init__(self) -> None:
        self._e: Dict[str, Dict[str, Any]] = {}

    # ── core ──────────────────────────────────────────────────────────────
    def observe(self, entity: str, status: str, kind: str = "path", source: str = "") -> None:
        entity = (entity or "").strip()
        if not entity:
            return
        # a later verified observation supersedes; never downgrade exists->unverified
        prev = self._e.get(entity)
        if prev and prev["status"] in (EXISTS, ABSENT) and status == UNVERIFIED:
            return
        self._e[entity] = {"status": status, "kind": kind, "source": source, "ts": time.time()}

    def status(self, entity: str) -> str:
        return self._e.get((entity or "").strip(), {}).get("status", UNVERIFIED)

    def exists(self, entity: str) -> bool:
        return self.status(entity) == EXISTS

    def absent(self, entity: str) -> bool:
        return self.status(entity) == ABSENT

    def verified_paths(self) -> List[str]:
        return [k for k, v in self._e.items() if v["status"] == EXISTS and v["kind"] == "path"]

    def absent_paths(self) -> List[str]:
        return [k for k, v in self._e.items() if v["status"] == ABSENT and v["kind"] == "path"]

    def absent_tools(self) -> List[str]:
        return [k for k, v in self._e.items() if v["status"] == ABSENT and v["kind"] == "tool"]

    # ── population from REAL tool results ────────────────────────────────
    def observe_tool(self, name: str, args: Dict[str, Any], result: str) -> None:
        """Map a tool's real output onto entity observations. Read-only logic —
        records only what the result actually proves."""
        r = result or ""
        head = r[:200]
        path = str((args or {}).get("path") or "")
        src = name

        if name in ("read_file", "edit_file", "file_info"):
            if path:
                self.observe(path, ABSENT if head.startswith("[File not found") or head.startswith("[Not found") else EXISTS, source=src)
        elif name in ("write_file", "create_folder"):
            if path and (head.startswith("Written:") or head.startswith("Created:")):
                self.observe(path, EXISTS, source=src)
        elif name == "delete_file":
            if path and head.startswith("Deleted:"):
                self.observe(path, ABSENT, source=src)
        elif name in ("list_files", "find_files", "grep_search"):
            if path:
                self.observe(path, ABSENT if head.startswith("[Not found") else EXISTS, source=src)
        elif name in ("move_file", "copy_file"):
            dst = str((args or {}).get("destination") or "")
            if dst and head.startswith(("Moved:", "Copied:")):
                self.observe(dst, EXISTS, source=src)
            srcp = str((args or {}).get("source") or "")
            if srcp and name == "move_file" and head.startswith("Moved:"):
                self.observe(srcp, ABSENT, source=src)
        # tool existence (OX-0 returns "[Unknown tool: name]")
        if head.startswith("[Unknown tool:"):
            self.observe("tool:" + name, ABSENT, kind="tool", source=src)

    # ── pre-action gate ──────────────────────────────────────────────────
    def gate(self, name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """Return (ok, reason). Blocks acting on a KNOWN-ABSENT path with a
        read/edit/delete/move tool — those calls would fail anyway."""
        if name in ("read_file", "edit_file", "delete_file", "move_file", "file_info"):
            p = str((args or {}).get("path") or (args or {}).get("source") or "")
            if p and self.absent(p):
                return (False, f"path '{p}' was already verified ABSENT this run — "
                               "do not re-read it; create it or choose another path")
        return (True, "")

    # ── prompt injection ─────────────────────────────────────────────────
    def render(self, max_each: int = 12) -> str:
        ve = self.verified_paths()[-max_each:]
        va = self.absent_paths()[-max_each:]
        vt = self.absent_tools()
        if not (ve or va or vt):
            return ""
        L = ["## VERIFIED WORLD (only act on what is confirmed — do not assume):"]
        if ve:
            L.append("  EXISTS:  " + ", ".join(ve))
        if va:
            L.append("  ABSENT:  " + ", ".join(va) + "  ← do NOT re-read; create or pick another")
        if vt:
            L.append("  NO SUCH TOOL: " + ", ".join(t[5:] for t in vt))
        return "\n".join(L)

    def snapshot(self) -> Dict[str, Any]:
        return {"exists": self.verified_paths(), "absent": self.absent_paths(),
                "absent_tools": [t[5:] for t in self.absent_tools()], "n": len(self._e)}
