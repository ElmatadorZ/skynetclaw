"""
kernel_memory.py — Cognitive Kernel · Memory subsystem (migration step 3b)
=========================================================================
COGNITIVE_KERNEL_SPEC §7: the Memory subsystem — recall/persist over the House's
second brain (the Obsidian vault). A thin, deterministic markdown store so the
kernel has a stable Memory ABI; richer semantic search (obsidian_tools) can back
it later without changing the interface.

Interface (the ABI):
    recall(query, k) -> list[Recollection]     # semantic-ish keyword recall
    persist(record)  -> {ok, path}             # write a note into the vault

The store root defaults to the configured vault, but is injectable — so
conforms_to() runs against a TEMP directory and never pollutes the real vault.

Stdlib only; obsidian_tools is a lazy import for the default root.
License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class Recollection:
    title: str
    path: str
    snippet: str
    score: float


@dataclass
class MemoryRecord:
    title: str
    text: str
    tags: List[str] = field(default_factory=list)
    kind: str = "note"


@runtime_checkable
class MemorySubsystem(Protocol):
    def recall(self, query: str, k: int = 5) -> List[Recollection]: ...
    def persist(self, record: MemoryRecord) -> Dict[str, Any]: ...


def _default_vault_root() -> Optional[str]:
    try:
        import obsidian_tools as _ot
        v = _ot.get_vault()
        return str(v) if v else None
    except Exception:
        return None


_SANITIZE = re.compile(r"[^0-9A-Za-z฀-๿ _\-]+")
_WORD = re.compile(r"[0-9A-Za-z฀-๿]+")


class VaultMemory:
    """Markdown-file memory over a vault root (defaults to the configured vault)."""

    def __init__(self, root: Optional[str] = None, max_scan: int = 2000):
        self.root = root or _default_vault_root()
        self.max_scan = max_scan

    # — Observe/recall —
    def recall(self, query: str, k: int = 5) -> List[Recollection]:
        if not self.root or not os.path.isdir(self.root):
            return []
        terms = [t.lower() for t in _WORD.findall(query or "")]
        if not terms:
            return []
        hits: List[Recollection] = []
        scanned = 0
        for dirpath, _dirs, files in os.walk(self.root):
            for fn in files:
                if not fn.lower().endswith(".md"):
                    continue
                scanned += 1
                if scanned > self.max_scan:
                    break
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        body = f.read()
                except Exception:
                    continue
                low = body.lower()
                score = sum(low.count(t) for t in terms)
                if score <= 0:
                    continue
                # a snippet around the first hit
                idx = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
                snip = body[max(0, idx - 60): idx + 140].replace("\n", " ").strip()
                hits.append(Recollection(title=fn[:-3], path=fp, snippet=snip, score=float(score)))
            if scanned > self.max_scan:
                break
        hits.sort(key=lambda r: r.score, reverse=True)
        return hits[:max(1, k)]

    # — Persist —
    def persist(self, record: MemoryRecord) -> Dict[str, Any]:
        if not self.root:
            return {"ok": False, "error": "no vault root configured"}
        try:
            os.makedirs(self.root, exist_ok=True)
            safe = _SANITIZE.sub("", record.title).strip() or f"note_{int(time.time())}"
            path = os.path.join(self.root, safe + ".md")
            fm = ["---",
                  f"kind: {record.kind}",
                  f"tags: [{', '.join(record.tags)}]",
                  f"created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                  "---", ""]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(fm) + record.text + "\n")
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# module-level default instance (bound to the real vault) for convenient callers
_default: Optional[VaultMemory] = None


def get_memory() -> VaultMemory:
    global _default
    if _default is None:
        _default = VaultMemory()
    return _default


# ── A6 — conformance self-test (isolated temp vault, never touches the real one) ─
def conforms_to() -> Dict[str, Any]:
    import tempfile, shutil
    checks: Dict[str, bool] = {}
    tmp = tempfile.mkdtemp(prefix="ck_mem_")
    try:
        mem = VaultMemory(root=tmp)
        token = f"ZZQ{int(time.time()*1000)}"
        # empty store recalls nothing (no fabrication)
        checks["empty_recall"] = mem.recall(token) == []
        # persist writes a real note
        r = mem.persist(MemoryRecord(title=f"kernel selftest {token}",
                                     text=f"the secret marker is {token} inside the body.",
                                     tags=["selftest"], kind="test"))
        checks["persist_ok"] = r.get("ok") and os.path.exists(r.get("path", ""))
        # recall finds what was persisted, and returns a Recollection with a snippet
        got = mem.recall(token, k=3)
        checks["recall_finds"] = bool(got) and token.lower() in (got[0].snippet.lower() if got else "")
        checks["recall_typed"] = bool(got) and isinstance(got[0], Recollection) and got[0].score > 0
        # a non-existent term recalls nothing
        checks["no_false_recall"] = mem.recall("NOPEnonexistentXYZ") == []
        ok = all(checks.values())
        return {"ok": ok, "checks": checks}
    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = conforms_to()
    for k, v in r["checks"].items():
        print(f"  {'OK ' if v else 'XX '} {k}")
    print("conforms_to:", r["ok"], "| real vault root:", _default_vault_root())
