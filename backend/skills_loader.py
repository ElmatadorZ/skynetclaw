"""skills_loader.py - discover folder-based skills and sync to skynerclaw.db"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE      = Path(__file__).parent
SKILLS_DIR = _BASE / "skills"
DB_PATH    = _BASE / "skynerclaw.db"


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    out: Dict[str, Any] = {}
    current_key = None
    current_list: Optional[List[str]] = None
    multi: Optional[List[str]] = None
    for raw in text[4:end].splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if current_list is not None and line.startswith("  -"):
            v = line.strip()[1:].strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            current_list.append(v); continue
        if multi is not None and (line.startswith("  ") or line.startswith("\t")):
            multi.append(line.strip()); continue
        if multi is not None and current_key:
            out[current_key] = " ".join(multi).strip(); multi = None
        if ":" in line and not line.startswith(" "):
            current_list = None
            k, _, v = line.partition(":")
            k = k.strip(); v = v.strip()
            current_key = k
            if v == "" or v == "|":
                if v == "|": multi = []
                else:
                    current_list = []
                    out[k] = current_list
                continue
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k] = v
    if multi is not None and current_key:
        out[current_key] = " ".join(multi).strip()
    return out


def discover_skills() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not SKILLS_DIR.exists():
        return out
    for sub in sorted(SKILLS_DIR.iterdir()):
        if not sub.is_dir():
            continue
        sk_md = sub / "SKILL.md"
        if not sk_md.exists():
            continue
        try:
            text = sk_md.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = _parse_frontmatter(text) or {}
        name = meta.get("name", sub.name)
        triggers = meta.get("triggers", []) or []
        description = meta.get("description") or ""
        version = meta.get("version", "1.0")
        if text.startswith("---"):
            end = text.find("\n---", 4)
            body = text[end+4:].strip() if end >= 0 else text
        else:
            body = text
        out.append({
            "id":            "skill_" + name.replace("-", "_"),
            "name":          name,
            "version":       version,
            "triggers":      triggers,
            "description":   description[:1500],
            "system_prompt": body[:8000],
            "has_tool":      (sub / "tool.py").exists(),
            "folder":        str(sub),
        })
    return out


def _ensure_table(c: sqlite3.Connection) -> None:
    c.execute("CREATE TABLE IF NOT EXISTS skills (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(skills)").fetchall()}
    need = {"version": "TEXT", "triggers": "TEXT", "description": "TEXT",
            "system_prompt": "TEXT", "folder": "TEXT", "updated_at": "REAL"}
    for col, sqltype in need.items():
        if col not in existing_cols:
            try:
                c.execute("ALTER TABLE skills ADD COLUMN " + col + " " + sqltype)
            except Exception:
                pass


def sync_skills_to_db() -> Dict[str, Any]:
    import time
    skills = discover_skills()
    new = 0
    updated = 0
    ids: List[str] = []
    with sqlite3.connect(DB_PATH) as c:
        _ensure_table(c)
        for sk in skills:
            ids.append(sk["id"])
            existing = c.execute("SELECT id FROM skills WHERE id=?", (sk["id"],)).fetchone()
            triggers_json = json.dumps(sk["triggers"], ensure_ascii=False)
            if existing:
                c.execute(
                    "UPDATE skills SET name=?, version=?, triggers=?, description=?, "
                    "system_prompt=?, folder=?, updated_at=? WHERE id=?",
                    (sk["name"], sk["version"], triggers_json, sk["description"],
                     sk["system_prompt"], sk["folder"], time.time(), sk["id"]))
                updated += 1
            else:
                c.execute(
                    "INSERT INTO skills (id, name, version, triggers, description, "
                    "system_prompt, folder, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (sk["id"], sk["name"], sk["version"], triggers_json,
                     sk["description"], sk["system_prompt"], sk["folder"], time.time()))
                new += 1
        c.commit()
    return {"ok": True, "discovered": len(skills), "new": new,
            "updated": updated, "skill_ids": ids}
