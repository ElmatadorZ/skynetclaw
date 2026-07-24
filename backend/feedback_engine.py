"""
feedback_engine.py — Ecosystem self-improvement loop
======================================================
Reads bridge_log.jsonl + continental_audit.jsonl + chat_history.db
Generates ecosystem insights:
  - slowest operatives (avg ms to first text)
  - most-fired skills
  - most-called tools
  - failure patterns (errors, blocks, aborts)
  - hot directives (clustered by first 3 tokens)
  - suggested patches (rule-of-thumb, no LLM needed)

Endpoints:
  GET /api/feedback/insights — full report (json)
  GET /api/feedback/issues   — open issues only
"""
from __future__ import annotations
import json, sqlite3, time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

_BASE   = Path(__file__).parent
BLOG    = _BASE / "bridge_log.jsonl"
AUDIT   = _BASE / "continental_audit.jsonl"
CHATDB  = _BASE / "chat_history.db"


def _load_bridge(limit_lines: int = 10000) -> List[Dict[str, Any]]:
    if not BLOG.exists(): return []
    out = []
    try:
        with BLOG.open("r", encoding="utf-8") as f:
            for line in f:
                try: out.append(json.loads(line))
                except Exception: continue
    except Exception: return []
    return out[-limit_lines:]


def _load_audit(limit_lines: int = 1000) -> List[Dict[str, Any]]:
    if not AUDIT.exists(): return []
    out = []
    try:
        with AUDIT.open("r", encoding="utf-8") as f:
            for line in f:
                try: out.append(json.loads(line))
                except Exception: continue
    except Exception: return []
    return out[-limit_lines:]


def _load_conv_meta() -> List[Dict[str, Any]]:
    if not CHATDB.exists(): return []
    try:
        with sqlite3.connect(CHATDB) as c:
            rows = c.execute(
                "SELECT id, started_at, last_at, directive_preview, operative_routed, tools_invoked, status "
                "FROM continental_conversations ORDER BY last_at DESC LIMIT 200"
            ).fetchall()
        return [{"id":r[0],"started_at":r[1],"last_at":r[2],"directive":r[3],
                 "operative":r[4],"tools":r[5],"status":r[6]} for r in rows]
    except Exception:
        return []


def analyze() -> Dict[str, Any]:
    bridge = _load_bridge()
    audit  = _load_audit()
    convs  = _load_conv_meta()

    # ── Per-conversation timing: from DIRECTIVE → first TEXT_DELTA ──
    first_text: Dict[str, float] = {}
    directive_ts: Dict[str, float] = {}
    tools_per_conv: Dict[str, int] = defaultdict(int)
    tools_called: Counter = Counter()
    skills_fired: Counter = Counter()
    operatives_on: Counter = Counter()
    errors: List[Dict[str, Any]] = []
    verdicts: Counter = Counter()
    phases_reached: Counter = Counter()

    for env in bridge:
        cid = env.get("conv_id","")
        t   = env.get("type")
        ts  = env.get("ts", 0)
        p   = env.get("payload", {})
        if t == "DIRECTIVE":
            directive_ts[cid] = ts
        elif t == "TEXT_DELTA" and cid not in first_text:
            first_text[cid] = ts
        elif t == "TOOL_CALL":
            tools_per_conv[cid] += 1
            tools_called[p.get("name","?")] += 1
        elif t == "SKILL_FIRE":
            skills_fired[p.get("name","?")] += 1
        elif t == "OPERATIVE_ON":
            operatives_on[p.get("code","?")] += 1
        elif t == "ERROR":
            errors.append({"conv_id":cid, "ts":ts, "msg":p.get("message","")[:200]})
        elif t == "VERDICT":
            verdicts[p.get("verdict","?")] += 1
        elif t == "PHASE":
            phases_reached[p.get("phase","?")] += 1

    # Time-to-first-token per conv (only those with both)
    ttft = []
    for cid, dts in directive_ts.items():
        if cid in first_text:
            ttft.append({"conv_id": cid, "ms": int((first_text[cid]-dts)*1000)})
    ttft.sort(key=lambda r: -r["ms"])

    # ── Issue detection (rule-of-thumb patterns) ──
    issues: List[Dict[str, Any]] = []
    if ttft and ttft[0]["ms"] > 30000:
        issues.append({"severity":"high","kind":"slow_response",
                       "msg":f"slowest TTFT {ttft[0]['ms']}ms (conv {ttft[0]['conv_id']})",
                       "suggest":"check model size · use compact prompt · check ollama warmup"})
    if len(errors) > 5:
        issues.append({"severity":"high","kind":"error_burst",
                       "msg":f"{len(errors)} errors in recent bridge log",
                       "suggest":"check backend logs · verify endpoint health · review last 5 errors"})
    if any(v.startswith("REBUILD") or v.startswith("FAIL") for v in verdicts.keys()):
        bad = sum(c for v,c in verdicts.items() if v.startswith(("REBUILD","FAIL")))
        if bad >= 3:
            issues.append({"severity":"med","kind":"shadow_gate_rejections",
                           "msg":f"{bad} REBUILD/FAIL verdicts — SKEPTIC is rejecting outputs",
                           "suggest":"review value_match_gate · check evidence-output alignment"})
    if tools_called and tools_called.most_common(1)[0][1] > 50:
        top, n = tools_called.most_common(1)[0]
        issues.append({"severity":"low","kind":"tool_hotspot",
                       "msg":f"{top} called {n}× — most-used tool",
                       "suggest":"consider caching · or extracting as a skill"})
    avg_tools = (sum(tools_per_conv.values())/max(1,len(tools_per_conv)))
    if avg_tools > 8:
        issues.append({"severity":"med","kind":"tool_chattering",
                       "msg":f"avg {avg_tools:.1f} tool calls per mission",
                       "suggest":"plan phase may be skipped · operatives spamming · review workflow"})

    # ── Directive hot-cluster (first 3 tokens) ──
    hot_directives: Counter = Counter()
    for c in convs:
        words = (c.get("directive","")[:120]).split()[:3]
        if words: hot_directives[" ".join(words)] += 1

    return {
        "generated_at":     time.time(),
        "totals": {
            "bridge_messages":  len(bridge),
            "audit_entries":    len(audit),
            "conversations":    len(convs),
            "errors":           len(errors),
        },
        "ttft_ms": {
            "p50":   _percentile([r["ms"] for r in ttft], 50),
            "p95":   _percentile([r["ms"] for r in ttft], 95),
            "slowest_3": ttft[:3],
        },
        "operatives_engaged": operatives_on.most_common(10),
        "tools_called":       tools_called.most_common(10),
        "skills_fired":       skills_fired.most_common(10),
        "phases_reached":     dict(phases_reached),
        "verdicts":           dict(verdicts),
        "hot_directives":     hot_directives.most_common(10),
        "recent_errors":      errors[-10:],
        "issues":             issues,
    }


def _percentile(arr: List[int], p: int) -> int:
    if not arr: return 0
    arr = sorted(arr)
    k = max(0, min(len(arr)-1, int(len(arr)*p/100)))
    return arr[k]


def mount(app):
    @app.get("/api/feedback/insights")
    def _insights():
        return analyze()

    @app.get("/api/feedback/issues")
    def _issues():
        r = analyze()
        return {"ok": True, "issues": r["issues"], "totals": r["totals"]}

    print("[FeedbackEngine] mounted at /api/feedback/*")


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    r = analyze()
    print(json.dumps(r, indent=2, ensure_ascii=False, default=str)[:2500])
