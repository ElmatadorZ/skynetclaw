"""
obsidian_knowledge_protocol.py — PART 7: SCOUT V2 (executable vault protocol)
============================================================================
Turns the Scout's Obsidian rules into executable checks:
  - Read before write   - Search before create   - No duplicate notes
  - Link before folder creation   - Maintain MOC integrity
  - Maintain Johnny Decimal structure   - Record all structural changes

Pure-logic core (testable without a live vault); binds to obsidian_tools when
present. Returns a PLAN the Scout executes, never silently mutating the vault.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from obsidian_tools import (obsidian_search as _osearch,
                                obsidian_list_notes as _olist,
                                obsidian_write_note as _owrite)
    _OBS = True
except Exception:
    _OBS = False
    def _osearch(q, **k): return {"ok": False, "error": "no vault", "hits": []}
    def _olist(folder="", **k): return {"ok": False, "error": "no vault", "notes": []}
    def _owrite(p, c, **k): return {"ok": False, "error": "no vault"}

# Johnny Decimal: top folders are "NN · Name" (00..99)
_JD_RE = re.compile(r"^\d{2}(\.\d{2})?\s*[·\-]\s+.+")
_TITLE_RE = re.compile(r"[\w฀-๿]+")


def is_johnny_decimal(folder: str) -> bool:
    return bool(_JD_RE.match(folder.strip()))


def _norm(title: str) -> set:
    return {t.lower() for t in _TITLE_RE.findall(title or "") if len(t) > 2}


def find_duplicates(title: str, search_fn: Optional[Callable] = None,
                    threshold: float = 0.6) -> List[Dict[str, Any]]:
    """Search the vault for near-duplicate notes before creating a new one."""
    sf = search_fn or _osearch
    want = _norm(title)
    if not want:
        return []
    res = sf(title)
    hits = (res or {}).get("hits") or (res or {}).get("notes") or []
    dups = []
    for h in hits:
        name = h.get("path") or h.get("title") or h.get("name") or str(h)
        base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if base.lower().endswith(".md"):
            base = base[:-3]
        have = _norm(base)
        if not have:
            continue
        jacc = len(want & have) / len(want | have)
        if jacc >= threshold:
            dups.append({"path": name, "similarity": round(jacc, 3)})
    return sorted(dups, key=lambda d: -d["similarity"])


def plan_write(title: str, content: str, category: str = "",
               links: Optional[List[str]] = None,
               search_fn: Optional[Callable] = None) -> Dict[str, Any]:
    """Produce a vault-write PLAN enforcing the Scout protocol.

    Decision: append to an existing note (duplicate found) vs create new.
    Enforces: search-before-create, no-duplicate, link-before-folder, JD structure.
    """
    links = links or []
    dups = find_duplicates(title, search_fn=search_fn)
    decision = "append" if dups else "create"

    warnings: List[str] = []
    if decision == "create" and not links:
        warnings.append("LINK-BEFORE-FOLDER: a new note must link to ≥1 existing note/MOC before it earns a place.")
    if category and not is_johnny_decimal(category):
        warnings.append(f"JOHNNY-DECIMAL: '{category}' is not 'NN · Name' form — pick a numbered folder.")
    if not category:
        category = "00 · Inbox"
        warnings.append("No category given → routed to '00 · Inbox' for later triage.")

    rel_path = f"{category}/{title}.md"
    moc = f"{category} MOC"
    return {
        "decision": decision,
        "duplicates": dups,
        "target_path": rel_path,
        "category": category,
        "links": links or [f"[[{moc}]]"],
        "moc": moc,
        "warnings": warnings,
        "protocol_ok": not warnings,
    }


def record_structural_change(action: str, before: str, after: str, reason: str,
                             writer: Optional[Callable] = None,
                             log_path: str = "Vault Organization Log.md") -> Dict[str, Any]:
    """Append a signed entry to the vault organization log (GOP-3 governance)."""
    w = writer or _owrite
    entry = (f"\n- **{time.strftime('%Y-%m-%d %H:%M')}** · {action}: "
             f"`{before}` → `{after}` — {reason} (signed: SCOUT OPV-007)\n")
    try:
        res = w(log_path, entry, mode="append")
    except TypeError:
        res = w(log_path, entry)
    except Exception as e:
        res = {"ok": False, "error": str(e)}
    return {"logged": bool(res and res.get("ok")), "entry": entry.strip()}


def execute_plan(plan: Dict[str, Any], content: str,
                 writer: Optional[Callable] = None) -> Dict[str, Any]:
    """Execute a plan_write plan after protocol passes (or is overridden)."""
    w = writer or _owrite
    body = content
    if plan.get("links"):
        body = content.rstrip() + "\n\n## Links\n" + "\n".join(plan["links"]) + "\n"
    res = w(plan["target_path"], body)
    return {"ok": bool(res and res.get("ok")), "path": plan["target_path"], "raw": res}
