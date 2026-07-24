"""
backend/prompts/ — modular system prompt assembly
==================================================
Ports OpenClaw's pattern of file-based prompt composition into SkynetClaw.

Files (all .md, human-editable):
    IDENTITY.md  — who SkynetClaw is
    AGENTS.md    — operating rules + Genesis Mind protocol + memory
    TOOLS.md     — tool catalog + intent→tool routing
    SOUL.md      — response tone + FPCOS L0–L8 cognitive style
    USER.md      — about the operator (optional; copy USER.example.md)

Wire-in (one block in main.py, replacing the inline GENESIS_AGENT_PROMPT):

    try:
        from prompts import compose_genesis_prompt
        GENESIS_AGENT_PROMPT = compose_genesis_prompt()
    except Exception as _e:
        print(f"[Prompts] modular prompts unavailable: {_e} — using inline fallback")
        # GENESIS_AGENT_PROMPT remains as the existing inline string

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

_DIR = Path(__file__).parent

# Order matters — IDENTITY first (who), AGENTS second (rules), then context
DEFAULT_ORDER = ["IDENTITY", "AGENTS", "TOOLS", "SOUL", "USER"]

# Section banners that wrap each file's content (helps the model identify boundaries)
_BANNER = "═" * 72


def _read(name: str) -> Optional[str]:
    """Read a single .md file. Returns None if missing or unreadable."""
    p = _DIR / f"{name}.md"
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _read_external(rel_path: str) -> Optional[str]:
    """Read a file from outside the prompts/ dir. Used for SELF.md (auto-generated)."""
    p = _DIR.parent / rel_path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return None


# Compact mode: only the essentials (IDENTITY + AGENTS + SOUL).
# Saves ~10KB of context for short tasks → much faster first-token on local models.
COMPACT_ORDER = ["IDENTITY", "AGENTS", "SOUL"]


def compose_genesis_prompt(order: Optional[List[str]] = None,
                           include_files: Optional[List[str]] = None,
                           include_self: bool = True,
                           compact: bool = False) -> str:
    """
    Compose the unified Genesis system prompt from modular .md files.

    Args:
        order: list of file basenames in the order to compose.
               Defaults: full mode = IDENTITY → AGENTS → TOOLS → SOUL → USER
                          compact mode = IDENTITY → AGENTS → SOUL
        include_files: if set, only include files whose basenames are in this list.
        include_self: if True (default), append backend/SELF.md.
                       Set False in compact mode for self-reporting tasks (the
                       agent already knows itself from IDENTITY+AGENTS).
        compact: if True, use COMPACT_ORDER and skip SELF.md by default.
                 Reduces ~16KB prompt → ~6KB for faster local-model latency.

    Returns:
        A single string ready as system message.
        Raises FileNotFoundError if NO files readable (caller can fall back).
    """
    if compact:
        seq = order or COMPACT_ORDER
        # In compact mode, default skip SELF.md unless caller explicitly forces include_self
        if include_self is True:    # default value — don't include in compact
            include_self = False
    else:
        seq = order or DEFAULT_ORDER

    if include_files is not None:
        seq = [f for f in seq if f in include_files]

    parts: List[str] = []
    found_any = False
    for name in seq:
        body = _read(name)
        if body is None:
            continue
        found_any = True
        parts.append(f"{_BANNER}\n# {name}\n{_BANNER}\n\n{body}")

    # Append SELF.md if available + requested
    if include_self:
        self_body = _read_external("SELF.md")
        if self_body:
            parts.append(f"{_BANNER}\n# SELF (current capability snapshot — auto-generated)\n"
                         f"{_BANNER}\n\n{self_body}")
            found_any = True

    if not found_any:
        raise FileNotFoundError(
            f"No prompt files found in {_DIR}. "
            f"Expected at least one of: {[f + '.md' for f in seq]}"
        )

    parts.append(
        f"{_BANNER}\n"
        + ("[COMPACT MODE]  " if compact else "")
        + "You are SkynetClaw. Apply the rules above. Execute relentlessly.\n"
        "Each tool call is one step closer to TASK_COMPLETE.\n"
        f"{_BANNER}"
    )
    return "\n\n".join(parts)


def list_loaded_files() -> List[str]:
    """For diagnostics — which files are present and readable."""
    out = []
    for name in DEFAULT_ORDER:
        if _read(name) is not None:
            out.append(name)
    return out


# ────────────────────────────────────────────────────────────────────────
# Self-test — `python -m prompts` from backend/
# ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== prompts compose self-test ===\n")
    loaded = list_loaded_files()
    print(f"Loaded files: {loaded}")
    if not loaded:
        print("  (no .md files found — composition will fall back)")
        sys.exit(0)
    try:
        prompt = compose_genesis_prompt()
        print(f"\nComposed prompt: {len(prompt):,} chars across {len(loaded)} files")
        print(f"Preview (first 400 chars):")
        print("-" * 72)
        print(prompt[:400])
        print("-" * 72)
        print(f"...\n(total {len(prompt):,} chars)")
        print("\n=== self-test OK ===")
    except FileNotFoundError as e:
        print(f"FALLBACK: {e}")
        sys.exit(1)
