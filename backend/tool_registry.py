"""
tool_registry.py — tool taxonomy: category map + parallel-safe set
==================================================================
Extracted from main.py — God Object decomposition, strangler-fig slice 2. Pure
data + one pure function, zero coupling. main re-exports these names, so every
call site (main + eval_suite + system_graph) is unchanged.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

# ── TOOL CATEGORY MAP ────────────────────────────────────────────────────────
TOOL_CATEGORY = {
    "read_file": "filesystem", "write_file": "filesystem", "edit_file": "filesystem", "read_document": "filesystem",
    "delete_file": "filesystem", "move_file": "filesystem", "copy_file": "filesystem",
    "create_folder": "filesystem", "list_files": "filesystem", "find_files": "filesystem", "file_info": "filesystem",
    "shell_command": "code", "run_python": "code", "install_package": "code",
    "get_system_info": "system", "list_processes": "system", "kill_process": "system",
    "take_screenshot": "system", "open_browser": "system", "clipboard_read": "system", "clipboard_write": "system",
    "web_search": "network", "http_request": "network", "download_file": "network", "build_news_report": "network",
    "get_current_datetime": "realtime", "get_crypto_price": "realtime",
    "get_gold_price": "realtime", "get_forex_rate": "realtime", "get_news": "realtime",
    "search_obsidian": "obsidian", "read_obsidian_note": "obsidian", "write_obsidian_note": "obsidian",
    "telegram_send": "social", "discord_send": "social", "line_notify": "social",
    "facebook_post": "social", "call_integration": "social",
    "grep_search": "fs",
    "dev_server": "code",
    "ask_user_options": "elicitation",
    "system_diagnostics": "system",   # read-only OS diagnosis (Wi-Fi/net/drivers)
    "system_repair": "system",        # curated state-changing repair — ESCALATE
    "calculator": "math",             # deterministic exact arithmetic (safe_math)
    "analyze_image": "vision",        # read an image with a local multimodal model
}


def get_tool_cat(name: str) -> str:
    return TOOL_CATEGORY.get(name, "other")


# PARALLEL-SAFE tools (Claude Code borrow): pure read-only, no side effects,
# order-independent → multiple such calls in one step run CONCURRENTLY instead
# of one-at-a-time. Anything that writes, sends, executes, or has ordering
# effects is deliberately excluded and stays sequential.
_PARALLEL_SAFE = {
    "read_file", "read_document", "list_files", "find_files", "grep_search", "file_info",
    "get_system_info", "system_diagnostics", "get_current_datetime",
    "get_crypto_price", "get_gold_price", "get_forex_rate", "get_news", "web_search",
    "search_obsidian", "read_obsidian_note", "obsidian_list_notes", "obsidian_read_note",
    "obsidian_search", "query_missions", "query_learning", "query_timeline",
    "read_house_mind", "recall_archive", "calculator",
}
