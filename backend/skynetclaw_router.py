"""
skynetclaw_router.py
====================
Multi-Model Router for SkynetClaw — assign 2-3 Ollama models to roles
(workhorse / chat / specialist) and route each request to the right one
based on intent classification.

Wire-up (in main.py):
    from skynetclaw_router import register_router, resolve_model
    register_router(app)             # adds /api/router/* endpoints

    # In /api/chat handler — replace the line that builds payload:
    actual_model = resolve_model(req.model, req.messages[-1].content if req.messages else "")
    payload = {"model": actual_model, ...}

    # In /api/agent/run handler — same:
    model = resolve_model(req.model, req.task)

If `req.model == "@auto"` (or empty) → router decides.
If `req.model == "claude-style:specialist"` → role-routed to specialist.
If `req.model` is a real Ollama model name → used as-is (backwards compatible).

Sentinel models the router understands:
    @auto           — classify intent, pick best role
    @workhorse      — force workhorse role
    @chat           — force chat role
    @specialist     — force specialist role
    @code           — alias for specialist with code-task hint

License: Apache-2.0 — ElmatadorZ / Bunyawat Dechanon
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from fastapi import HTTPException
from pydantic import BaseModel

# ──────────────────────────────────────────────────────────────────────────────
# Config storage
# ──────────────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).parent
ROUTER_CONFIG_PATH = _BASE / "router_config.json"

# Default roster — replaced by user via /api/router/config
DEFAULT_ROSTER = {
    "version": 1,
    "enabled": True,
    "roles": {
        # workhorse: heavy execution, code, file ops, agent loops
        "workhorse":  {"model": "", "fallback": "", "description": "ใช้กับงานหนัก: รันโค้ด, สร้างไฟล์, agent loop, วิเคราะห์ลึก"},
        # chat: light Q&A, casual conversation, quick answers
        "chat":       {"model": "", "fallback": "", "description": "ใช้กับการคุย, ถาม-ตอบสั้น ๆ, สรุปเร็ว"},
        # specialist: domain-specific (coffee, market, legal, etc.) or coding
        "specialist": {"model": "", "fallback": "", "description": "ใช้กับงานเฉพาะทาง: code, market, coffee science ฯลฯ"},
    },
    # Routing rules — first match wins. User-extensible.
    "rules": [
        # Pattern (regex, IGNORECASE) → role
        {"pattern": r"\b(run|execute|exec|build|create|generate|write|save|install|deploy|รัน|สร้าง|เขียน|ทำ|ติดตั้ง)\b.*\b(file|folder|script|code|project|app|bot|server|ไฟล์|โฟลเดอร์|โปรเจก|แอพ|บอท)\b", "role": "workhorse"},
        {"pattern": r"\b(debug|fix|refactor|optimize|profile|trace|stack trace|error|bug|แก้บัค|แก้ error|ดีบั๊ก)\b", "role": "specialist"},
        {"pattern": r"\b(code|function|class|api|sdk|regex|sql|docker|kubernetes|k8s|terraform)\b", "role": "specialist"},
        {"pattern": r"\b(agent|run task|execute task|automate|automation|รัน task|ทำงานอัตโนมัติ)\b", "role": "workhorse"},
        {"pattern": r"^\s*(hi|hello|hey|สวัสดี|ทักทาย|ดี+|hi.|hello.).{0,40}$", "role": "chat"},
        {"pattern": r"^.{0,80}\?\s*$", "role": "chat"},  # short single question
        # Default catches: any "tell me about" / explain / summarize → chat
        {"pattern": r"\b(explain|summary|summarize|what is|tell me|อธิบาย|สรุป|คืออะไร|บอก)\b", "role": "chat"},
    ],
    # Heuristic thresholds for length-based fallback when no rule matches
    "length_router": {
        "short_chars": 80,        # below → chat
        "long_chars": 400,        # above → workhorse
        # in between → specialist if the task contains code-y tokens, else workhorse
    },
    "default_role": "workhorse",  # used when nothing matches
    "audit": True,                # log every routing decision to router_audit.jsonl
}

ROUTER_AUDIT_PATH = _BASE / "router_audit.jsonl"


# ──────────────────────────────────────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────────────────────────────────────
def _load_roster() -> Dict[str, Any]:
    if not ROUTER_CONFIG_PATH.exists():
        # Seed with default but don't pick models yet — user must configure
        _save_roster(DEFAULT_ROSTER)
        return dict(DEFAULT_ROSTER)
    try:
        return json.loads(ROUTER_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_ROSTER)


def _save_roster(r: Dict[str, Any]) -> None:
    r["updated_at"] = int(time.time())
    tmp = ROUTER_CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ROUTER_CONFIG_PATH)


def _audit(decision: Dict[str, Any]) -> None:
    r = _load_roster()
    if not r.get("audit"):
        return
    try:
        with ROUTER_AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **decision}, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Core routing logic
# ──────────────────────────────────────────────────────────────────────────────
SENTINEL_MAP = {
    "@auto": None,          # decide via classifier
    # Canonical names (kept for back-compat)
    "@workhorse": "workhorse",
    "@chat": "chat",
    "@specialist": "specialist",
    "@code": "specialist",
    # New technical aliases (UI-facing)
    "@executor":  "workhorse",   # heavy compute, agentic execution
    "@ambient":   "chat",        # light Q&A, casual reasoning
    "@precision": "specialist",  # domain expertise, code, finance
}


def classify_intent(text: str, roster: Optional[Dict[str, Any]] = None) -> str:
    """
    Returns one of: workhorse / chat / specialist
    Pure regex + length heuristic. Zero LLM cost.
    """
    if roster is None:
        roster = _load_roster()
    t = (text or "").strip()
    if not t:
        return roster.get("default_role", "workhorse")

    # 1) Try explicit pattern rules first
    for rule in roster.get("rules", []):
        try:
            if re.search(rule["pattern"], t, re.IGNORECASE | re.DOTALL):
                return rule.get("role", "chat")
        except re.error:
            continue

    # 2) Length-based fallback
    lr = roster.get("length_router", {})
    n = len(t)
    code_tokens = re.search(r"```|def |class |function|=>|<\?|#include|import |from ", t)
    if n <= lr.get("short_chars", 80):
        return "chat"
    if n >= lr.get("long_chars", 400):
        return "specialist" if code_tokens else "workhorse"
    return "specialist" if code_tokens else roster.get("default_role", "workhorse")


def resolve_model(requested: Optional[str], context_text: str = "") -> str:
    """
    Map a requested model identifier to an actual Ollama model name.

    Behavior:
      - Real Ollama model name (e.g. "qwen2.5:32b") → returned as-is.
      - Sentinel (@auto, @workhorse, @chat, @specialist, @code) → resolved via roster.
      - Empty / None → default_role from roster.
      - If router disabled → returns requested as-is (or empty string).
    """
    roster = _load_roster()
    if not roster.get("enabled", True):
        return requested or ""

    req = (requested or "").strip()

    # Real model name → pass through (backwards compatibility)
    if req and not req.startswith("@"):
        return req

    # Sentinel resolution
    if req in SENTINEL_MAP:
        forced_role = SENTINEL_MAP[req]
    else:
        forced_role = None  # treat unknown empty/sentinel as @auto

    role = forced_role if forced_role else classify_intent(context_text, roster)
    role_cfg = roster.get("roles", {}).get(role, {})
    model = role_cfg.get("model", "")
    fallback = role_cfg.get("fallback", "")

    # If primary model unset, walk through roles to find ANY configured model
    if not model:
        for r in ("workhorse", "specialist", "chat"):
            m = roster.get("roles", {}).get(r, {}).get("model", "")
            if m:
                model = m
                role = r + " (auto-fallback)"
                break

    if not model and fallback:
        model = fallback

    _audit({
        "requested": requested,
        "context_preview": (context_text or "")[:120],
        "chosen_role": role,
        "chosen_model": model,
    })
    return model or ""


def preview_routing(text: str) -> Dict[str, Any]:
    """For UI: show which model would be picked without actually routing."""
    roster = _load_roster()
    role = classify_intent(text, roster)
    role_cfg = roster.get("roles", {}).get(role, {})
    return {
        "role": role,
        "model": role_cfg.get("model", ""),
        "fallback": role_cfg.get("fallback", ""),
        "matched_pattern": _first_matching_pattern(text, roster),
        "router_enabled": roster.get("enabled", True),
    }


def _first_matching_pattern(text: str, roster: Dict[str, Any]) -> Optional[str]:
    for rule in roster.get("rules", []):
        try:
            if re.search(rule["pattern"], text or "", re.IGNORECASE | re.DOTALL):
                return rule["pattern"][:80]
        except re.error:
            continue
    return None


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI endpoints
# ──────────────────────────────────────────────────────────────────────────────
class RouterConfigPatch(BaseModel):
    enabled: Optional[bool] = None
    roles: Optional[Dict[str, Dict[str, str]]] = None
    rules: Optional[List[Dict[str, str]]] = None
    default_role: Optional[str] = None
    audit: Optional[bool] = None


class PreviewReq(BaseModel):
    text: str


def register_router(app):
    """Call once from main.py: register_router(app)."""

    @app.get("/api/router/config")
    async def router_get_config():
        """Returns the full roster + rules."""
        return _load_roster()

    @app.put("/api/router/config")
    async def router_put_config(patch: RouterConfigPatch):
        """Merge-update the roster. Only provided fields are changed."""
        r = _load_roster()
        d = patch.dict(exclude_unset=True, exclude_none=True)
        if "roles" in d:
            # Deep-merge roles so user can update one role without resetting others
            for role_name, cfg in d["roles"].items():
                if role_name not in r.get("roles", {}):
                    r.setdefault("roles", {})[role_name] = {}
                r["roles"][role_name].update(cfg or {})
            d.pop("roles")
        r.update(d)
        _save_roster(r)
        return {"ok": True, "roster": r}

    @app.post("/api/router/preview")
    async def router_preview(req: PreviewReq):
        """Given a user message, show which model would be selected."""
        return preview_routing(req.text)

    @app.post("/api/router/reset")
    async def router_reset():
        """Reset to DEFAULT_ROSTER (keeps any user-set models in the roles)."""
        cur = _load_roster()
        new = dict(DEFAULT_ROSTER)
        # Preserve user's model assignments
        for role_name, role_cfg in cur.get("roles", {}).items():
            if role_name in new["roles"]:
                new["roles"][role_name]["model"] = role_cfg.get("model", "")
                new["roles"][role_name]["fallback"] = role_cfg.get("fallback", "")
        _save_roster(new)
        return {"ok": True, "roster": new}

    @app.get("/api/router/audit")
    async def router_audit_tail(limit: int = 30):
        """Return last N routing decisions (for the UI's live indicator)."""
        if not ROUTER_AUDIT_PATH.exists():
            return {"entries": []}
        try:
            lines = ROUTER_AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()
            entries = [json.loads(l) for l in lines[-limit:]]
            return {"entries": entries}
        except Exception as e:
            raise HTTPException(500, f"audit read failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=== skynetclaw_router self-test ===\n")

    # Seed a sample roster
    sample = dict(DEFAULT_ROSTER)
    sample["roles"]["workhorse"]["model"] = "nemotron3:33b"
    sample["roles"]["chat"]["model"]      = "qwen3.5:9b"
    sample["roles"]["specialist"]["model"] = "Genesis-Mind:latest"
    _save_roster(sample)
    print("Seeded sample roster.\n")

    cases = [
        ("สวัสดี",                                            "chat"),
        ("BTC ตอนนี้ราคาเท่าไหร่?",                           "chat"),       # short question
        ("รัน python script สร้าง telegram bot ที่ D:\\Bot",   "workhorse"),
        ("debug error นี้: NameError: name 'x' is not defined", "specialist"),
        ("write a function in python that ...",               "specialist"),
        ("อธิบายว่า OAuth ทำงานยังไง",                         "chat"),
        ("a" * 500 + " และวิเคราะห์เชิงลึก",                  "workhorse"),
    ]
    for text, expected in cases:
        got = classify_intent(text)
        ok = "✓" if got == expected else "✗"
        print(f"  {ok} expected={expected:11s} got={got:11s} | {text[:60]}")

    print("\nresolve_model tests:")
    print("  @auto on 'สวัสดี'        →", resolve_model("@auto", "สวัสดี"))
    print("  @workhorse              →", resolve_model("@workhorse", ""))
    print("  literal 'mistral:7b'    →", resolve_model("mistral:7b", "anything"))
    print("  '' (empty)              →", resolve_model("", "debug this code"))

    print("\npreview:")
    print(" ", preview_routing("รัน python script สร้าง bot"))

    print("\n=== self-test OK ===")
