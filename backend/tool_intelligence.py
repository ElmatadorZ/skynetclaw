"""
tool_intelligence.py — OX-SKILL-1 TOOL INTELLIGENCE (execution intelligence only)
=================================================================================
The House knew WHAT was asked and WHAT mission was running. It did NOT know which
TOOL is best, which one solved a similar problem before, or whether work should be
RESUMED instead of recreated. So it searched when it should read, planned when it
should execute, and recreated when it should resume.

This module makes the House a TOOL STRATEGIST, not a tool user. It is pure
execution intelligence — NO governance, doctrine, council, UI or architecture
change. Mirrors the OX-1.5 execution_recall convention: a dependency-free,
deterministic, model-free read-model with one small persistent ledger.

Four capabilities (exactly the OX-SKILL-1 spec):

  1. TOOL DISCOVERY     — build_registry(): a READ-ONLY registry derived from the
                          live tool schemas + curated semantics + learned stats.
                          (Tool Name · Purpose · Inputs · Outputs · Failure Modes ·
                          Success Rate)
  2. TOOL MEMORY        — record(): every completed task records
                          {task_type, tool_used, success, execution_time} into the
                          tool_memory.json ledger (the ONLY new state this module
                          owns — no schema change, no DB edit).
  3. TOOL RECOMMENDATION— recommend(): before execution answer
                          {fastest, safest, prior_solution} from the ledger.
  4. ROUTING RULES      — render_brief(): inject the routing
                          doctrine (read>search, resume>recreate, recall>plan,
                          execute>deliberate) + the live recommendation so the
                          agent acts before it deliberates.

Ownership: owns ONLY tool_memory.json (this module's private ledger). Reads the
mission ledger (owned by main._ledger_*) read-only for resume detection.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE = Path(__file__).parent / "tool_memory.json"
_TOK = re.compile(r"[a-zA-Z0-9_]+")

# ── 1. CURATED TOOL SEMANTICS ────────────────────────────────────────────────
# The live schema gives Name/Purpose/Inputs for free. Outputs and Failure Modes
# are not in the schema, so they are curated here for the tools the House uses
# most. Anything not listed still appears in the registry — just with generic
# output/failure text. Success Rate is always learned (never curated).
_CURATED: Dict[str, Dict[str, str]] = {
    "read_file":      {"out": "file contents (optionally a line range)",   "fail": "file not found; binary/too large; wrong path"},
    "write_file":     {"out": "bytes written; created/overwritten file",   "fail": "permission denied; parent dir missing; disk full"},
    "edit_file":      {"out": "patched file (old_text→new_text)",          "fail": "old_text not found / not unique; file missing"},
    "list_files":     {"out": "directory entries",                         "fail": "dir not found; not a directory"},
    "find_files":     {"out": "paths matching a glob",                     "fail": "no matches; bad pattern; dir missing"},
    "grep_search":    {"out": "file:line: matched-line hits",              "fail": "no matches; bad regex (falls back to literal)"},
    "file_info":      {"out": "size, dates, permissions",                  "fail": "file not found"},
    "create_folder":  {"out": "created directory (and parents)",           "fail": "permission denied; path is a file"},
    "move_file":      {"out": "moved/renamed path",                        "fail": "source missing; destination exists"},
    "copy_file":      {"out": "copied path",                               "fail": "source missing; permission denied"},
    "delete_file":    {"out": "deleted confirmation",                      "fail": "not found; dir not empty (need recursive)"},
    "shell_command":  {"out": "stdout/stderr + exit code",                 "fail": "non-zero exit; timeout; command not found; blocks on servers"},
    "run_python":     {"out": "script stdout + return value",              "fail": "exception; timeout; missing import"},
    "dev_server":     {"out": "background process id + first output",      "fail": "port in use; command not found; crash on start"},
    "web_search":     {"out": "ranked web result snippets",                "fail": "rate limit; no results; network down"},
    "http_request":   {"out": "response status, headers, body",            "fail": "4xx/5xx; timeout; bad URL; auth required"},
    "download_file":  {"out": "saved file path",                           "fail": "404; network; disk full"},
    "get_news":       {"out": "latest headlines for a topic",             "fail": "rate limit; topic empty"},
    "get_gold_price": {"out": "XAU/USD spot + Thai GTA baht (live)",       "fail": "provider down; rate limit"},
    "get_crypto_price":{"out": "live crypto prices (CoinGecko)",           "fail": "unknown symbol; rate limit"},
    "get_forex_rate": {"out": "live FX rates",                             "fail": "unknown currency; provider down"},
    "get_current_datetime":{"out": "accurate date/time/tz",               "fail": "bad timezone id"},
    "search_obsidian":{"out": "ranked vault note matches",                 "fail": "vault not configured; no matches"},
    "read_obsidian_note":{"out": "full note content",                      "fail": "note not found"},
    "write_obsidian_note":{"out": "created/updated note",                  "fail": "vault not configured; permission"},
    "query_missions": {"out": "the House's own missions + status",         "fail": "(read-only — rarely fails)"},
    "read_house_mind":{"out": "current cognitive state",                   "fail": "(read-only — rarely fails)"},
    "query_timeline": {"out": "recent belief evolution",                   "fail": "(read-only — rarely fails)"},
    "query_learning": {"out": "institutional lessons",                     "fail": "(read-only — rarely fails)"},
    "recall_archive": {"out": "similar prior missions/deliberations",      "fail": "(read-only — rarely fails)"},
    "ask_user_options":{"out": "halts; waits for the user's choice",       "fail": "(stalls the run — use only when truly blocked)"},
}

# Tools that are read-only / inspection — used to express the routing doctrine
# (read/inspect/recall BEFORE search/plan).
_INSPECT_TOOLS = {"read_file", "list_files", "file_info", "grep_search", "find_files",
                  "read_obsidian_note", "search_obsidian", "query_missions",
                  "read_house_mind", "query_timeline", "query_learning", "recall_archive"}

# ── 2. TASK CLASSIFICATION (deterministic, keyword-based) ────────────────────
# Aligned with main._TOOL_GROUPS so a task_type maps cleanly onto a tool family.
_TASK_RULES: List[tuple] = [
    ("report",    {"report", "รายงาน", "brief", "สรุป", "summar", "dashboard", "pdf", "เอกสาร", "document"}),
    ("research",  {"research", "วิจัย", "news", "ข่าว", "web", "search", "ค้น", "price", "ราคา", "gold",
                   "ทอง", "crypto", "forex", "stock", "หุ้น", "market", "วิเคราะห์", "analy"}),
    ("code",      {"code", "โค้ด", "python", "script", "build", "html", "css", "server", "npm", "node",
                   "deploy", "fix", "แก้", "debug", "test", "ทดสอบ", "app", "แอป", "program", "โปรแกรม"}),
    ("obsidian",  {"obsidian", "vault", "note", "โน้ต", "บันทึก", "second brain", "ความรู้"}),
    ("file_ops",  {"move", "ย้าย", "copy", "delete", "ลบ", "organize", "จัดระเบียบ", "rename", "folder", "โฟลเดอร์"}),
    ("discovery", {"mission", "status", "สถานะ", "history", "ประวัติ", "believe", "learned", "เรียนรู้", "remember", "recall"}),
    ("system",    {"system", "ระบบ", "process", "cpu", "memory", "disk", "screenshot", "clipboard", "browser"}),
    ("social",    {"telegram", "discord", "line", "facebook", "post", "โพสต์", "notify", "แจ้งเตือน", "ส่งข้อความ"}),
]


def classify_task(task: str) -> str:
    t = (task or "").lower()
    for name, kws in _TASK_RULES:
        if any(k in t for k in kws):
            return name
    return "general"


def _tokens(s: str) -> set:
    return {w.lower() for w in _TOK.findall(s or "") if len(w) > 2}


# ── memory ledger I/O (the only state this module owns) ──────────────────────
def load_memory() -> Dict[str, Any]:
    try:
        if _STORE.exists():
            return json.loads(_STORE.read_text(encoding="utf-8")) or {"version": 1, "tools": {}}
    except Exception:
        pass
    return {"version": 1, "tools": {}}


def _save_memory(mem: Dict[str, Any]) -> None:
    try:
        tmp = _STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_STORE)
    except Exception as e:
        print(f"[ToolIntelligence] save failed: {e}")


def _blank_stat() -> Dict[str, Any]:
    return {"uses": 0, "successes": 0, "total_time": 0.0, "task_types": {}, "last_used": 0.0}


def record(task_type: str, tool_used: str, success: bool, execution_time: float,
           mem: Optional[Dict[str, Any]] = None, persist: bool = True) -> Dict[str, Any]:
    """TOOL MEMORY — record one completed tool use. This is exactly the spec
    schema: {task_type, tool_used, success, execution_time}. Aggregated per tool
    and per (tool, task_type) so recommend() can answer fastest/safest/prior."""
    own = mem is None
    mem = mem if mem is not None else load_memory()
    tools = mem.setdefault("tools", {})
    st = tools.setdefault(tool_used, _blank_stat())
    et = max(0.0, float(execution_time or 0.0))
    st["uses"] += 1
    st["successes"] += 1 if success else 0
    st["total_time"] += et
    st["last_used"] = time.time()
    tt = st["task_types"].setdefault(task_type or "general",
                                     {"uses": 0, "successes": 0, "total_time": 0.0})
    tt["uses"] += 1
    tt["successes"] += 1 if success else 0
    tt["total_time"] += et
    if own and persist:
        _save_memory(mem)
    return mem


def success_rate(tool: str, mem: Optional[Dict[str, Any]] = None) -> Optional[float]:
    mem = mem if mem is not None else load_memory()
    st = (mem.get("tools") or {}).get(tool)
    if not st or not st.get("uses"):
        return None
    return round(st["successes"] / float(st["uses"]), 3)


def avg_time(tool: str, mem: Optional[Dict[str, Any]] = None) -> Optional[float]:
    mem = mem if mem is not None else load_memory()
    st = (mem.get("tools") or {}).get(tool)
    if not st or not st.get("uses"):
        return None
    return round(st["total_time"] / float(st["uses"]), 3)


# ── 1. TOOL DISCOVERY — read-only registry ───────────────────────────────────
def build_registry(tool_schemas: List[Dict[str, Any]],
                   mem: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Build the read-only registry from the LIVE tool schemas, enriched with
    curated outputs/failure-modes and learned success rates. Never mutates."""
    mem = mem if mem is not None else load_memory()
    reg: List[Dict[str, Any]] = []
    for t in (tool_schemas or []):
        fn = (t or {}).get("function") or {}
        name = fn.get("name") or ""
        if not name:
            continue
        params = (fn.get("parameters") or {}).get("properties") or {}
        required = (fn.get("parameters") or {}).get("required") or []
        inputs = [(("*" if p in required else "") + p) for p in params.keys()]  # * = required
        cur = _CURATED.get(name, {})
        sr = success_rate(name, mem)
        reg.append({
            "tool": name,
            "purpose": (fn.get("description") or "").split(". ")[0][:160],
            "inputs": inputs,
            "outputs": cur.get("out", "tool result"),
            "failure_modes": cur.get("fail", "error string on failure"),
            "success_rate": sr,            # None until learned
            "uses": (mem.get("tools", {}).get(name, {}) or {}).get("uses", 0),
        })
    return reg


# ── 3. TOOL RECOMMENDATION ────────────────────────────────────────────────────
def _stat_for(mem: Dict[str, Any], tool: str, task_type: str) -> Optional[Dict[str, Any]]:
    """Stats for a tool scoped to a task_type if present, else its global stats."""
    st = (mem.get("tools") or {}).get(tool)
    if not st or not st.get("uses"):
        return None
    tt = (st.get("task_types") or {}).get(task_type)
    if tt and tt.get("uses"):
        return {"uses": tt["uses"], "successes": tt["successes"],
                "total_time": tt["total_time"], "scoped": True}
    return {"uses": st["uses"], "successes": st["successes"],
            "total_time": st["total_time"], "scoped": False}


def recommend(task_type: str, candidate_tools: List[str],
              mem: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Before execution, answer the three strategist questions from memory:
        fastest        — lowest avg execution_time (min 1 success)
        safest         — highest success rate (tie → more uses)
        prior_solution — what solved this task_type before (most successes,
                         prefers task-scoped evidence)
    Returns {} fields as None when there is no evidence yet (cold start)."""
    mem = mem if mem is not None else load_memory()
    cands = set(candidate_tools or []) or set((mem.get("tools") or {}).keys())
    rows = []
    for tool in cands:
        s = _stat_for(mem, tool, task_type)
        if not s:
            continue
        sr = s["successes"] / float(s["uses"])
        at = s["total_time"] / float(s["uses"])
        rows.append({"tool": tool, "uses": s["uses"], "success_rate": round(sr, 3),
                     "avg_time": round(at, 3), "successes": s["successes"],
                     "scoped": s["scoped"]})
    if not rows:
        return {"task_type": task_type, "fastest": None, "safest": None,
                "prior_solution": None, "evidence": 0}

    fastest = min((r for r in rows if r["successes"] > 0), default=None,
                  key=lambda r: r["avg_time"])
    safest = max(rows, key=lambda r: (r["success_rate"], r["uses"]))
    # prior solution: prefer task-scoped, then most successes, then success rate
    prior = max(rows, key=lambda r: (r["scoped"], r["successes"], r["success_rate"]))
    return {"task_type": task_type,
            "fastest": fastest, "safest": safest,
            "prior_solution": prior if prior["successes"] > 0 else None,
            "evidence": sum(r["uses"] for r in rows)}


# ── 4. ROUTING RULES — resume detection REMOVED (OX-INTENT-1) ────────────────
# Artifact-resume detection used to live here (detect_resume), duplicating the
# Artifact Registry's resolve_resume over the same mission-ledger files (audit
# DUP-1). OX-INTENT-1 makes the Artifact Registry the SINGLE SOURCE OF TRUTH for
# resume; Tool Intelligence now CONSUMES the shared Intent Object instead of
# re-detecting. The routing DOCTRINE text below still teaches "resume>recreate",
# but Tool Intelligence no longer performs the detection.


# ── prompt rendering ──────────────────────────────────────────────────────────
def _fmt_pick(label: str, r: Optional[Dict[str, Any]], extra: str = "") -> str:
    if not r:
        return ""
    return (f"  {label}: {r['tool']} "
            f"({int(r['success_rate']*100)}% over {r['uses']} use(s)"
            + (f", ~{r['avg_time']}s" if extra == "time" else "") + ")")


def render_brief(task: str, candidate_tools: List[str],
                 intent: Optional[Dict[str, Any]] = None,
                 mem: Optional[Dict[str, Any]] = None) -> str:
    """The TOOL INTELLIGENCE prompt block injected BEFORE execution. Carries the
    routing doctrine + the learned tool recommendation. OX-INTENT-1: it CONSUMES
    the shared Intent Object (uses intent['task_type'] instead of re-classifying)
    and performs NO resume detection — resume is owned by the Artifact Registry."""
    mem = mem if mem is not None else load_memory()
    task_type = (intent or {}).get("task_type") or classify_task(task)
    rec = recommend(task_type, candidate_tools, mem)

    L = ["## TOOL INTELLIGENCE (act as a tool STRATEGIST, not a tool user):"]
    # Routing doctrine — the four spec rules, always present.
    L.append("  ROUTING DOCTRINE — decide the move before you pick a tool:")
    L.append("   • file exists      → READ/inspect it before you search.")
    L.append("   • artifact exists  → RESUME it before you recreate.")
    L.append("   • answer exists    → RECALL it before you plan.")
    L.append("   • known solution   → EXECUTE it before you deliberate.")

    if rec.get("evidence"):
        L.append(f"  LEARNED for task-type '{task_type}' (from prior runs):")
        fs = _fmt_pick("FASTEST", rec.get("fastest"), extra="time")
        sf = _fmt_pick("SAFEST", rec.get("safest"))
        pr = _fmt_pick("SOLVED THIS BEFORE", rec.get("prior_solution"))
        for line in (pr, sf, fs):
            if line:
                L.append(line)
        L.append("   → Prefer the tool that already solved this; don't re-discover.")
    else:
        L.append(f"  (No prior tool evidence for task-type '{task_type}' yet — "
                 "this run will teach the House which tool wins.)")
    return "\n".join(L)
