"""
benchmark_execution.py — OX-EXECUTION-RECOVERY-1 Execution Benchmark Suite
==========================================================================
Execution is the source of truth. This harness proves the House can actually
COMPLETE real-world tool tasks — not think about them. Every deployment must
pass it before any cognitive work resumes.

Tasks (from the mission's success criteria):
  A  Create a file                      → 100%
  B  Read an existing file              → 100%
  C  Modify an existing file            → 100%
  D  Search information and save results→ 100%
  E  10 consecutive tool tasks          → >= 90%
  F  First-tool-call latency            → < 15s

Pure functions (build_tasks / evaluate / TARGETS) are unit-tested; run_suite()
hits the live /api/agent/run. No cognitive systems involved — execution only.

Usage:
  python benchmark_execution.py [--base http://127.0.0.1:8766] [--model qwen3.5:9b]
Exit code 0 = all criteria pass, 1 = any fail.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import urllib.request
from typing import Any, Dict, List, Optional

# success targets (criterion → (min_rate, latency_max_s))
TARGETS = {
    "A_create":  {"min_rate": 1.00},
    "B_read":    {"min_rate": 1.00},
    "C_modify":  {"min_rate": 1.00},
    "D_search":  {"min_rate": 1.00},
    "E_consecutive": {"min_rate": 0.90},
    "F_latency": {"max_latency_s": 15.0},
}


# ── task definitions (pure) ──────────────────────────────────────────────────
def build_tasks(workspace: str) -> List[Dict[str, Any]]:
    f = os.path.join(workspace, "bench_file.txt")
    rf = os.path.join(workspace, "bench_read.txt")
    sf = os.path.join(workspace, "bench_search.md")
    return [
        {"id": "A_create", "task": f"Create a file at {f} containing exactly: Hello World",
         "verify": {"path": f, "contains": "Hello World"}},
        {"id": "B_read", "task": f"Read the file {rf} and report its contents.",
         "prep": {"path": rf, "content": "the secret is 42"}, "verify": {"tool_used": True}},
        {"id": "C_modify", "task": f"In the file {rf}, change the number 42 to 99.",
         "prep": {"path": rf, "content": "the secret is 42"}, "verify": {"path": rf, "contains": "99"}},
        {"id": "D_search", "task": f"Search the web for the current Bitcoin price and save a short "
                                   f"note to {sf}.", "verify": {"path": sf, "exists": True}},
    ]


# ── evaluation (pure — unit-tested) ──────────────────────────────────────────
def evaluate(results: Dict[str, Any]) -> Dict[str, Any]:
    """results: {criterion: {rate?|latency?}} → {criterion: {target, actual, pass}}."""
    out: Dict[str, Any] = {}
    overall = True
    for crit, tgt in TARGETS.items():
        r = results.get(crit, {})
        if "min_rate" in tgt:
            actual = r.get("rate")
            ok = actual is not None and actual >= tgt["min_rate"]
            out[crit] = {"target": f">={tgt['min_rate']:.0%}",
                         "actual": (f"{actual:.0%}" if actual is not None else "n/a"), "pass": ok}
        else:
            actual = r.get("latency")
            ok = actual is not None and actual < tgt["max_latency_s"]
            out[crit] = {"target": f"<{tgt['max_latency_s']}s",
                         "actual": (f"{actual:.1f}s" if actual is not None else "n/a"), "pass": ok}
        overall = overall and ok
    out["_overall_pass"] = overall
    return out


# ── live runner ──────────────────────────────────────────────────────────────
def run_agent_task(base: str, task: str, model: str, workspace: str,
                   max_steps: int = 6, timeout: int = 120) -> Dict[str, Any]:
    body = json.dumps({"task": task, "model": model, "max_steps": max_steps,
                       "workspace_folder": workspace}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/api/agent/run", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time(); first_tool = None; tools = 0; status = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for line in r:
                s = line.decode("utf-8", "replace").strip()
                if not s.startswith("data:"):
                    continue
                try: ev = json.loads(s[5:].strip())
                except Exception: continue
                et = ev.get("type")
                if et in ("agent_tool_call", "__tool_calls__"):
                    tools += 1
                    if first_tool is None: first_tool = time.time() - t0
                elif et == "agent_complete": status = "complete"
                elif et == "agent_error": status = "error"
                elif et == "agent_stuck": status = "stuck"
                elif et == "agent_limit": status = "limit"
        return {"first_tool_latency": first_tool, "tools_used": tools,
                "status": status, "elapsed": time.time() - t0}
    except Exception as e:
        return {"first_tool_latency": first_tool, "tools_used": tools,
                "status": f"exc:{type(e).__name__}", "elapsed": time.time() - t0, "error": str(e)[:120]}


def _verify(task: Dict[str, Any], run: Dict[str, Any]) -> bool:
    v = task.get("verify", {})
    if v.get("tool_used"):
        return run.get("tools_used", 0) > 0 and run.get("status") not in ("error", "stuck")
    p = v.get("path")
    if p and v.get("exists"):
        return os.path.exists(p) and os.path.getsize(p) > 0
    if p and "contains" in v:
        try:
            return v["contains"] in open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            return False
    return run.get("status") == "complete"


def run_suite(base: str = "http://127.0.0.1:8766", model: str = "qwen3.5:9b",
              consecutive: int = 10) -> Dict[str, Any]:
    ws = tempfile.mkdtemp(prefix="ox_bench_")
    tasks = build_tasks(ws)
    detail = {}
    latencies = []
    for t in tasks:
        prep = t.get("prep")
        if prep:
            open(prep["path"], "w", encoding="utf-8").write(prep["content"])
        run = run_agent_task(base, t["task"], model, ws)
        ok = _verify(t, run)
        if run.get("first_tool_latency") is not None:
            latencies.append(run["first_tool_latency"])
        detail[t["id"]] = {"rate": 1.0 if ok else 0.0, "run": run}
    # E: consecutive create tasks
    succ = 0
    for i in range(consecutive):
        fp = os.path.join(ws, f"seq_{i}.txt")
        run = run_agent_task(base, f"Create a file at {fp} containing the text item-{i}", model, ws)
        if os.path.exists(fp):
            succ += 1
        if run.get("first_tool_latency") is not None:
            latencies.append(run["first_tool_latency"])
    results = {k: {"rate": v["rate"]} for k, v in detail.items()}
    results["E_consecutive"] = {"rate": succ / consecutive}
    results["F_latency"] = {"latency": (min(latencies) if latencies else None)}
    return {"results": results, "scorecard": evaluate(results), "detail": detail,
            "workspace": ws, "model": model}


if __name__ == "__main__":
    base = "http://127.0.0.1:8766"; model = "qwen3.5:9b"
    for i, a in enumerate(sys.argv):
        if a == "--base" and i + 1 < len(sys.argv): base = sys.argv[i + 1]
        if a == "--model" and i + 1 < len(sys.argv): model = sys.argv[i + 1]
    rep = run_suite(base, model)
    print(json.dumps(rep["scorecard"], indent=2))
    sys.exit(0 if rep["scorecard"]["_overall_pass"] else 1)
