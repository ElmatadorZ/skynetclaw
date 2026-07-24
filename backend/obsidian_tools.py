"""
obsidian_tools.py — Obsidian vault access for SkynetClaw / Continental Division
================================================================================
4 callable tools assigned to THE SCOUT (OPV-007):
  - obsidian_list_notes(folder='', limit=100) -> list of .md files
  - obsidian_read_note(rel_path)              -> file content
  - obsidian_write_note(rel_path, content,
                        mode='create')        -> create / overwrite / append
  - obsidian_search(query, max_hits=20)       -> grep across notes

Vault discovery (in order):
  1. settings.json → 'obsidian_vault'
  2. settings.json → 'obsidian_vaults' (list, first entry)
  3. cross-platform conventional locations under $HOME
  4. host-specific locations (OneDrive on Windows, iCloud on macOS,
     Nextcloud/Dropbox and container mounts on Linux)

A vault is optional — SkynetClaw runs without one; the Scout's four tools
simply report that none is configured.
"""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE = Path(__file__).parent
SETTINGS = _BASE / "settings.json"


def _read_settings() -> Dict[str, Any]:
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def get_vault() -> Optional[Path]:
    """Returns the active Obsidian vault path, or None."""
    s = _read_settings()
    candidates: List[str] = []
    if isinstance(s.get("obsidian_vault"), str):
        candidates.append(s["obsidian_vault"])
    if isinstance(s.get("obsidian_vaults"), list) and s["obsidian_vaults"]:
        candidates.append(s["obsidian_vaults"][0])

    # OS-typical paths. The same Obsidian install lives somewhere different on
    # each platform, so probe the host's conventions rather than assuming one.
    home = Path.home()
    candidates += [
        str(home / "Documents" / "Obsidian Vault"),
        str(home / "Obsidian"),
        str(home / "Notes"),
        str(home / "vault"),
    ]
    if os.name == "nt":                                     # Windows
        candidates += [
            str(home / "OneDrive" / "Documents" / "Obsidian Vault"),
            str(home / "OneDrive" / "Obsidian"),
            "D:/Obsidian",
            "D:/Notes",
        ]
    elif sys.platform == "darwin":                          # macOS
        candidates += [
            str(home / "Library" / "Mobile Documents"
                / "iCloud~md~obsidian" / "Documents"),      # iCloud-synced vaults
            str(home / "Documents" / "Obsidian"),
        ]
    else:                                                    # Linux / BSD
        candidates += [
            str(home / "Nextcloud" / "Obsidian"),
            str(home / "Dropbox" / "Obsidian"),
            str(home / "Sync" / "Obsidian"),
            "/vault",                                        # docker-compose mount
            "/data/obsidian",
        ]
    for c in candidates:
        p = Path(c)
        if p.exists() and p.is_dir():
            return p
    return None


def set_vault(path: str) -> Dict[str, Any]:
    """Update settings to lock in a vault path."""
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return {"ok": False, "error": f"path not found: {path}"}
    s = _read_settings()
    s["obsidian_vault"] = str(p.resolve())
    SETTINGS.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "vault": s["obsidian_vault"]}


# ──────────────── TOOL IMPLEMENTATIONS ────────────────
def obsidian_list_notes(folder: str = "", limit: int = 100) -> Dict[str, Any]:
    v = get_vault()
    if not v:
        return {"ok": False, "error": "no vault configured (set obsidian_vault in settings.json)"}
    root = (v / folder).resolve() if folder else v
    if v not in root.parents and root != v:
        return {"ok": False, "error": "folder escapes vault"}
    if not root.exists():
        return {"ok": False, "error": f"folder not found: {folder}"}
    out: List[Dict[str, Any]] = []
    for p in root.rglob("*.md"):
        rel = p.relative_to(v).as_posix()
        try:
            stat = p.stat()
            out.append({
                "path": rel,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        except Exception:
            pass
        if len(out) >= limit:
            break
    out.sort(key=lambda r: -r["modified"])
    return {"ok": True, "vault": str(v), "count": len(out), "notes": out}


def obsidian_read_note(rel_path: str) -> Dict[str, Any]:
    v = get_vault()
    if not v:
        return {"ok": False, "error": "no vault configured"}
    p = (v / rel_path).resolve()
    if v not in p.parents:
        return {"ok": False, "error": "path escapes vault"}
    if not p.exists():
        return {"ok": False, "error": f"note not found: {rel_path}"}
    try:
        content = p.read_text(encoding="utf-8")
        return {"ok": True, "path": rel_path, "size": len(content),
                "content": content[:20000],
                "truncated": len(content) > 20000}
    except Exception as e:
        return {"ok": False, "error": f"read failed: {e}"}


def obsidian_write_note(rel_path: str, content: str,
                         mode: str = "create") -> Dict[str, Any]:
    v = get_vault()
    if not v:
        return {"ok": False, "error": "no vault configured"}
    if not rel_path.endswith(".md"):
        rel_path = rel_path + ".md"
    p = (v / rel_path).resolve()
    if v not in p.parents:
        return {"ok": False, "error": "path escapes vault"}
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        if mode == "overwrite":
            p.write_text(content, encoding="utf-8")
            action = "overwritten"
        elif mode == "append":
            existing = p.read_text(encoding="utf-8") if p.exists() else ""
            sep = "\n\n" if existing and not existing.endswith("\n") else ""
            p.write_text(existing + sep + content, encoding="utf-8")
            action = "appended"
        else:  # create
            if p.exists():
                return {"ok": False, "error": "note already exists (use mode='overwrite' or 'append')"}
            p.write_text(content, encoding="utf-8")
            action = "created"
        return {"ok": True, "path": rel_path, "action": action,
                "size": p.stat().st_size}
    except Exception as e:
        return {"ok": False, "error": f"write failed: {e}"}


def obsidian_search(query: str, max_hits: int = 20) -> Dict[str, Any]:
    v = get_vault()
    if not v:
        return {"ok": False, "error": "no vault configured"}
    if not query.strip():
        return {"ok": False, "error": "empty query"}
    rx = re.compile(re.escape(query), re.IGNORECASE)
    hits: List[Dict[str, Any]] = []
    for p in v.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if rx.search(text):
            # find first line containing match
            for i, line in enumerate(text.splitlines()):
                if rx.search(line):
                    hits.append({
                        "path": p.relative_to(v).as_posix(),
                        "line": i + 1,
                        "preview": line.strip()[:200],
                    })
                    break
            if len(hits) >= max_hits:
                break
    return {"ok": True, "query": query, "count": len(hits), "hits": hits}


# ──────────────── TOOL CATALOG for BUILTIN_TOOLS ────────────────
OBSIDIAN_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "obsidian_list_notes",
            "description": "List markdown notes in the Obsidian vault. Returns recent .md files with size+modified time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "subfolder under vault root (empty = whole vault)"},
                    "limit":  {"type": "integer", "description": "max files (default 100)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_read_note",
            "description": "Read the content of a markdown note in the Obsidian vault.",
            "parameters": {
                "type": "object",
                "properties": {"rel_path": {"type": "string", "description": "path relative to vault root, e.g. 'Projects/idea.md'"}},
                "required": ["rel_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_write_note",
            "description": "Create / overwrite / append a markdown note in the Obsidian vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rel_path": {"type": "string"},
                    "content":  {"type": "string"},
                    "mode":     {"type": "string", "enum": ["create", "overwrite", "append"]},
                },
                "required": ["rel_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_search",
            "description": "Search all notes in the Obsidian vault for a phrase. Returns matches with file + line + preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":    {"type": "string"},
                    "max_hits": {"type": "integer", "description": "default 20"},
                },
                "required": ["query"],
            },
        },
    },
]


def dispatch_obsidian(name: str, args: Dict[str, Any]) -> Any:
    if name == "obsidian_list_notes":
        return obsidian_list_notes(folder=args.get("folder", ""), limit=int(args.get("limit", 100)))
    if name == "obsidian_read_note":
        return obsidian_read_note(rel_path=args["rel_path"])
    if name == "obsidian_write_note":
        return obsidian_write_note(rel_path=args["rel_path"], content=args["content"],
                                    mode=args.get("mode", "create"))
    if name == "obsidian_search":
        return obsidian_search(query=args["query"], max_hits=int(args.get("max_hits", 20)))
    return {"ok": False, "error": f"unknown obsidian tool: {name}"}


# ──────────────── self-test ────────────────
if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    v = get_vault()
    print(f"vault: {v}")
    if v:
        r = obsidian_list_notes(limit=5)
        print(f"list: count={r.get('count')}, first 3:")
        for n in (r.get("notes") or [])[:3]:
            print(f"  {n['path']}  ({n['size']:,}b)")
