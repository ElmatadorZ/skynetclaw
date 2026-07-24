"""
vault_awareness.py — Obsidian second-brain self-knowledge
=========================================================
Extracted from main.py — God Object decomposition, strangler-fig slice 3. The
configured-vault root (used to exempt the vault from the workspace clamp) and the
runtime self-knowledge banner. Zero coupling to main — only stdlib + a lazy
obsidian_tools import — so path_security can import _vault_root directly from here
instead of reaching back through main.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import time
from pathlib import Path

_vault_root_cache = {"ts": 0.0, "path": None}


def _vault_root():
    """The configured Obsidian vault root as a resolved Path (cached 60s), or
    None. Used to exempt the vault from the workspace clamp."""
    now = time.time()
    if now - _vault_root_cache["ts"] < 60:
        return _vault_root_cache["path"]
    root = None
    try:
        import obsidian_tools as _ot
        v = _ot.get_vault()
        if v:
            root = Path(v).resolve()
    except Exception:
        root = None
    _vault_root_cache.update({"ts": now, "path": root})
    return root


# ── SELF-KNOWLEDGE: the agent must know its OWN Obsidian second brain ──────────
# Bug the operator hit: asked "it's your obsidian", the agent didn't recognize
# its own configured vault and fumbled with find_files (which the workspace clamp
# silently emptied). The vault IS configured (settings.obsidian_vault) and has
# dedicated tools that access it directly — the agent just wasn't told. This
# banner injects the real vault path + note count + the right tools at runtime.
_vault_banner_cache = {"ts": 0.0, "text": ""}


def _vault_awareness_banner() -> str:
    now = time.time()
    if now - _vault_banner_cache["ts"] < 60 and _vault_banner_cache["text"]:
        return _vault_banner_cache["text"]
    text = ""
    try:
        import obsidian_tools as _ot
        v = _ot.get_vault()
        if v:
            n = "?"
            try:
                _lst = _ot.obsidian_list_notes()
                n = len(_lst.get("notes", [])) if isinstance(_lst, dict) else "?"
            except Exception:
                pass
            text = (
                f"## YOUR OBSIDIAN SECOND BRAIN (self-knowledge)\n"
                f"You HAVE an Obsidian vault — it is YOUR own memory, at:\n"
                f"  {v}  ({n} notes)\n"
                f"When the operator says 'your obsidian / your vault / your notes / "
                f"บันทึกของคุณ', they mean THIS vault. To read, search, or write it, use "
                f"your dedicated tools: obsidian_search(query), obsidian_list_notes(), "
                f"obsidian_read_note(rel_path), obsidian_write_note(rel_path, content). "
                f"Do NOT use find_files / grep_search / read_file on the vault — those hit "
                f"the raw filesystem and are clamped to the active workspace, so they return "
                f"nothing. The obsidian_* tools reach the vault directly, regardless of "
                f"workspace."
            )
    except Exception:
        text = ""
    _vault_banner_cache.update({"ts": now, "text": text})
    return text
