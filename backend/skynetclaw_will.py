"""
skynetclaw_will.py
==================
WillCore — identity, tone, and risk policy for SkynetClaw Masterpiece.

Per ElmatadorZ Secret OS spec:
  WillCore — identity + tone + risk policy

This module gives the system its **voice** and its **brakes**:
  - identity_seed()   : the system's self-statement (Money Atlas tone law)
  - tone_filter()     : softens overclaim language, enforces honest uncertainty
  - risk_classify()   : SAFE / MEDIUM / IRREVERSIBLE per tool call
  - require_confirm() : returns True if a human must approve before exec

License: Apache-2.0 — ElmatadorZ / Bunyawat Dechanon
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Any, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Identity seed — system's self-statement
# ──────────────────────────────────────────────────────────────────────────────
IDENTITY = """\
You are SkynetClaw Masterpiece — local autonomous cognitive OS by ElmatadorZ.

You are not a chatbot. You are not an assistant.
You are an EXECUTOR with a Shadow Gate.

Tone laws (Money Atlas):
  Sharp not cold. Dense not verbose.
  Honest uncertainty > false precision.
  Every claim auditable. No filler. No hype.
  Compounding > one-shot.

System laws:
  - FPCOS is the CPU — every output runs on First Principles.
  - Shadow Gate is non-skippable — certainty without critique = hallucination.
  - Failure is asset — failure signatures never deleted.
  - Verified > fast — PARTIAL honest beats false COMPLETE.
  - Human decides — ElmatadorZ has final call on irreversible actions.
"""


def identity_seed() -> str:
    """Return the IDENTITY anchor. Inject as system message at session start."""
    return IDENTITY


# ──────────────────────────────────────────────────────────────────────────────
# Tone filter — soften overclaim language (FPCOS Safety Gate)
# ──────────────────────────────────────────────────────────────────────────────
_OVERCLAIM_MAP = [
    # Thai
    (r"\bรับประกัน(ว่า|)\b", "มีโอกาสสูงว่า"),
    (r"\b100\s*%\b",         "เกือบทั้งหมด"),
    (r"\bแน่นอน\b",          "มีแนวโน้ม"),
    (r"\bไม่มีทาง\b",         "ยากมาก"),
    (r"\bเป็นไปไม่ได้\b",     "มีโอกาสน้อยมาก"),
    (r"\bต้องเป็น\b",         "น่าจะเป็น"),
    # English
    (r"\bguaranteed?\b",     "very likely"),
    (r"\b100\s*%\b",         "near-total"),
    (r"\b(always|never)\b",  lambda m: "almost always" if m.group(1).lower()=="always" else "almost never"),
    (r"\bdefinitely\b",      "very likely"),
    (r"\bimpossible\b",      "extremely unlikely"),
    (r"\bcertainly\b",       "very likely"),
]


def tone_filter(text: str) -> Tuple[str, list]:
    """
    Apply Money Atlas tone law: soften overclaim language.
    Returns (filtered_text, list_of_changes).
    """
    if not text:
        return text, []
    changes = []
    out = text
    for pat, repl in _OVERCLAIM_MAP:
        if callable(repl):
            new = re.sub(pat, repl, out, flags=re.IGNORECASE)
        else:
            new = re.sub(pat, repl, out, flags=re.IGNORECASE)
        if new != out:
            changes.append(pat)
            out = new
    return out, changes


# ──────────────────────────────────────────────────────────────────────────────
# Risk policy — classify each tool call
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class RiskAssessment:
    level: str           # SAFE / MEDIUM / IRREVERSIBLE
    reason: str
    require_confirm: bool


# Tools that are always safe (read-only, stateless)
_SAFE_TOOLS = {
    "read_file", "list_files", "find_files", "file_info",
    "get_system_info", "list_processes", "get_current_datetime",
    "get_crypto_price", "get_gold_price", "get_forex_rate", "get_news",
    "web_search", "search_obsidian", "read_obsidian_note",
    "clipboard_read", "ask_user_options",
    "http_request",  # GET-ish; classified deeper below
}

# Tools that are reversible-with-effort (write to user workspace)
_MEDIUM_TOOLS = {
    "write_file", "edit_file", "create_folder", "copy_file",
    "write_obsidian_note", "clipboard_write", "take_screenshot",
    "open_browser", "download_file",
}

# Tools that are IRREVERSIBLE or can affect external systems
_IRREVERSIBLE_TOOLS = {
    "delete_file", "move_file", "shell_command", "run_python",
    "install_package", "kill_process",
    "telegram_send", "discord_send", "line_notify", "facebook_post",
    "call_integration",
}

# Patterns inside command/code text that escalate risk
_ESCALATE_PATTERNS = [
    r"\brm\s+-rf\b", r"\bformat\s+[a-z]:", r"\bshutdown\b", r"\breboot\b",
    r"\bmkfs\b", r"\bdd\s+if=", r"\b:>\s*/etc/", r"\breg\s+delete\b",
    r"\bnet\s+user\b", r"\bdrop\s+(table|database)\b",
]
_ESCALATE_RE = re.compile("|".join(_ESCALATE_PATTERNS), re.IGNORECASE)


def risk_classify(tool_name: str, args: Dict[str, Any]) -> RiskAssessment:
    """
    Classify a proposed tool call into SAFE / MEDIUM / IRREVERSIBLE.
    require_confirm = True for IRREVERSIBLE on system folders or matching escalation patterns.
    """
    args = args or {}

    # Bucket by tool
    if tool_name in _SAFE_TOOLS:
        # Special case: http_request with method != GET → MEDIUM
        if tool_name == "http_request" and (args.get("method") or "GET").upper() != "GET":
            return RiskAssessment("MEDIUM", "non-GET HTTP request", require_confirm=False)
        return RiskAssessment("SAFE", "read-only tool", require_confirm=False)

    if tool_name in _MEDIUM_TOOLS:
        return RiskAssessment("MEDIUM", "writes to user workspace (reversible)", require_confirm=False)

    if tool_name in _IRREVERSIBLE_TOOLS:
        # Inspect command/code body
        body = (args.get("command") or args.get("code") or "")
        if _ESCALATE_RE.search(body):
            return RiskAssessment(
                "IRREVERSIBLE",
                f"matches escalation pattern: {_ESCALATE_RE.search(body).group(0)[:40]}",
                require_confirm=True,
            )
        # Outbound messaging — always confirm
        if tool_name in ("telegram_send", "discord_send", "line_notify", "facebook_post"):
            return RiskAssessment("IRREVERSIBLE", "outbound message", require_confirm=True)
        # delete on system folder
        if tool_name in ("delete_file", "move_file"):
            target = (args.get("path") or args.get("source") or "").lower()
            sys_prefixes = ("c:\\windows", "c:\\program files", "/etc", "/usr", "/bin", "/var")
            if any(target.startswith(s) for s in sys_prefixes):
                return RiskAssessment("IRREVERSIBLE", "destructive on system folder", require_confirm=True)
        return RiskAssessment("IRREVERSIBLE", "irreversible tool", require_confirm=False)

    # Unknown tool — treat as MEDIUM by default (don't BLOCK new tools, but flag)
    return RiskAssessment("MEDIUM", "unknown tool — defaulting to MEDIUM", require_confirm=False)


def require_confirm(tool_name: str, args: Dict[str, Any]) -> bool:
    """Convenience: returns True if WillCore says human must approve."""
    return risk_classify(tool_name, args).require_confirm


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=== skynetclaw_will self-test ===\n")

    print("[IDENTITY]")
    print(identity_seed()[:200], "...\n")

    print("[TONE FILTER]")
    cases = [
        "ผมรับประกันว่า BTC จะขึ้นแน่นอน 100%",
        "This is guaranteed to always work — definitely the best approach",
        "ทำไม่ได้แน่ๆ มันเป็นไปไม่ได้",
    ]
    for c in cases:
        out, changes = tone_filter(c)
        print(f"  in : {c}")
        print(f"  out: {out}")
        print(f"  changes: {changes}\n")

    print("[RISK CLASSIFY]")
    tests = [
        ("read_file",     {"path": "x.txt"}),
        ("write_file",    {"path": "x.py", "content": "..."}),
        ("shell_command", {"command": "ls -la"}),
        ("shell_command", {"command": "rm -rf /"}),
        ("telegram_send", {"message": "hi"}),
        ("delete_file",   {"path": "C:\\Windows\\notepad.exe"}),
        ("delete_file",   {"path": "D:\\my_project\\old.log"}),
        ("http_request",  {"url": "https://api.x.com", "method": "DELETE"}),
        ("unknown_tool",  {}),
    ]
    for name, args in tests:
        r = risk_classify(name, args)
        flag = "⚠ CONFIRM" if r.require_confirm else "  ok    "
        print(f"  [{r.level:13s}] {flag} {name:18s} — {r.reason}")

    print("\n=== self-test OK ===")
