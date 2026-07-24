"""
mcp_server.py — SkynetClaw as an MCP server (stdio)
====================================================
Exposes SkynetClaw's tool layer to any MCP client (Claude Desktop, Claude Code,
Cursor, ...) as a thin proxy to the running backend at http://localhost:8766.

Design (per MCP best practices):
  - Thin stdio server; ALL execution happens in the backend so the GPS-2
    permission gate, workspace resolution, auto-git, and syntax-verify apply
    identically whether a tool is called from the UI, Telegram, or MCP.
  - Consistent `skynetclaw_` prefix, action-oriented names, typed parameters.
  - Actionable error messages (backend down → how to start it; gated tool →
    how to approve it).

Install:   pip install "mcp[cli]" httpx
Run:       python mcp_server.py            (stdio — spawned by the MCP client)
Override:  set SKYNETCLAW_URL if the backend is not on localhost:8766
"""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("SKYNETCLAW_URL", "http://localhost:8766").rstrip("/")

mcp = FastMCP(
    "skynetclaw",
    instructions=(
        "SkynetClaw agent tools (files, code search, shell, python, dev servers, "
        "Obsidian vault) running on the operator's Windows machine. All calls pass "
        "a deny-by-default permission gate (GPS-2); irreversible tools require a "
        "standing approval granted by the operator in the SkynetClaw UI."
    ),
)


# trust_env=False: the backend is local by design — system proxies must never
# intercept these calls (a SOCKS/HTTP proxy env var would otherwise hijack them).
_client = httpx.Client(trust_env=False)


def _call(name: str, args: dict, timeout: float = 150.0) -> str:
    """Execute a tool through the backend's gated /api/tools/execute endpoint."""
    try:
        r = _client.post(f"{BASE}/api/tools/execute",
                         json={"name": name, "args": args, "operator": "MCP"},
                         timeout=timeout)
    except httpx.ConnectError:
        return (f"ERROR: SkynetClaw backend is not reachable at {BASE}. "
                f"Start it first: python main.py (in the backend folder), "
                f"or set SKYNETCLAW_URL if it runs elsewhere.")
    except httpx.TimeoutException:
        return f"ERROR: backend timed out after {timeout:.0f}s for {name}."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    if r.status_code != 200:
        return f"ERROR: backend returned HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    if not data.get("ok"):
        return f"ERROR: {data.get('error', 'unknown backend error')}"
    return str(data.get("result", ""))


# ── Files ─────────────────────────────────────────────────────────────────────
@mcp.tool()
def skynetclaw_read_file(path: str, offset: int = 1, limit: int = 0,
                         line_numbers: bool = False) -> str:
    """Read a file on the SkynetClaw machine. Large files auto-truncate at 1500
    lines — pass offset (1-based start line) and limit to read a region.
    Use skynetclaw_grep first to find WHERE to read."""
    return _call("read_file", {"path": path, "offset": offset, "limit": limit,
                               "line_numbers": line_numbers})


@mcp.tool()
def skynetclaw_write_file(path: str, content: str) -> str:
    """Write/overwrite a file. Code files (.py/.js/.json/.html) are syntax-checked
    automatically — the result tells you immediately if the write broke the file."""
    return _call("write_file", {"path": path, "content": content})


@mcp.tool()
def skynetclaw_edit_file(path: str, old_text: str, new_text: str,
                         replace_all: bool = False) -> str:
    """Replace exact text in a file (first occurrence unless replace_all). If
    old_text is not found, the error suggests the nearest whitespace-normalized
    match with its line number — re-read and retry with exact text."""
    return _call("edit_file", {"path": path, "old_text": old_text,
                               "new_text": new_text, "replace_all": replace_all})


@mcp.tool()
def skynetclaw_list_files(path: str, show_hidden: bool = False) -> str:
    """List a directory (name/type/size/modified, JSON)."""
    return _call("list_files", {"path": path, "show_hidden": show_hidden})


@mcp.tool()
def skynetclaw_find_files(path: str, pattern: str, recursive: bool = True) -> str:
    """Find files by glob pattern (e.g. *.py) recursively. Returns paths (max 100)."""
    return _call("find_files", {"path": path, "pattern": pattern, "recursive": recursive})


@mcp.tool()
def skynetclaw_grep(pattern: str, path: str = ".", glob: str = "*",
                    max_results: int = 50, context: int = 0) -> str:
    """Search INSIDE files for a regex/plain text. Returns file:line: matches.
    THE tool for locating code before reading/editing — never read whole big files."""
    return _call("grep_search", {"pattern": pattern, "path": path, "glob": glob,
                                 "max_results": max_results, "context": context})


# ── Code & Shell (GPS-2 escalated — needs standing operator approval) ────────
@mcp.tool()
def skynetclaw_shell(command: str, cwd: str = "", timeout: int = 60) -> str:
    """Run a shell command on the operator's Windows machine (UTF-8, max 120s).
    PowerShell-only syntax is auto-routed to PowerShell. GPS-2: requires a standing
    approval granted by the operator. Don't use for servers — use skynetclaw_dev_server."""
    args = {"command": command, "timeout": timeout}
    if cwd: args["cwd"] = cwd
    return _call("shell_command", args)


@mcp.tool()
def skynetclaw_run_python(code: str, timeout: int = 60) -> str:
    """Execute Python code on the SkynetClaw machine (max 300s). GPS-2: requires
    standing operator approval."""
    return _call("run_python", {"code": code, "timeout": timeout})


@mcp.tool()
def skynetclaw_dev_server(action: str, command: str = "", id: str = "",
                          lines: int = 60, cwd: str = "") -> str:
    """Manage long-running background processes (dev servers): action=start|logs|stop|list.
    start needs command (e.g. 'npm run dev'); logs/stop need the id returned by start.
    Verify web work via http on the local URL, read logs for errors, fix, recheck."""
    args: dict = {"action": action, "lines": lines}
    if command: args["command"] = command
    if id: args["id"] = id
    if cwd: args["cwd"] = cwd
    return _call("dev_server", args)


# ── Obsidian vault (the operator's second brain) ─────────────────────────────
@mcp.tool()
def skynetclaw_obsidian_search(query: str, top_k: int = 5) -> str:
    """Search the operator's Obsidian vault notes."""
    return _call("obsidian_search", {"query": query, "top_k": top_k})


@mcp.tool()
def skynetclaw_obsidian_read_note(name: str) -> str:
    """Read a note from the Obsidian vault by name."""
    return _call("obsidian_read_note", {"name": name})


@mcp.tool()
def skynetclaw_obsidian_write_note(name: str, content: str, folder: str = "") -> str:
    """Create or update a note in the Obsidian vault."""
    return _call("obsidian_write_note", {"name": name, "content": content, "folder": folder})


@mcp.tool()
def skynetclaw_obsidian_list_notes() -> str:
    """List notes in the Obsidian vault."""
    return _call("obsidian_list_notes", {})


# ── System ────────────────────────────────────────────────────────────────────
@mcp.tool()
def skynetclaw_system_info() -> str:
    """Get the SkynetClaw machine's system info (OS, disk, memory, CPU)."""
    return _call("get_system_info", {})


@mcp.tool()
def skynetclaw_governance_status() -> str:
    """Show the GPS-2 permission policy (allow/escalate/deny lists), GOS-0 branch
    map, and any pending human gates — what this MCP connection may and may not do."""
    try:
        r = _client.get(f"{BASE}/api/governance/status", timeout=10)
        return json.dumps(r.json(), ensure_ascii=False, indent=2)[:6000]
    except Exception as e:
        return f"ERROR: cannot read governance status: {e}"


if __name__ == "__main__":
    mcp.run()  # stdio transport — spawned by the MCP client
