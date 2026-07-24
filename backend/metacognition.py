"""
metacognition.py — SkynetClaw thinks about its own thinking
============================================================
The piece that turns SkynetClaw from "agent that runs tools" into "agent that
reflects on its own runs". This is the actual self-awareness of cognition,
distinct from self_awareness.py (which is awareness of capabilities).

What this module does (all data is read from existing artifacts):

  reflect_on_run(run_id)
    Reads the trajectory.jsonl of one agent_run + the audit_trail entries +
    the agent_runs DB row. Returns structured reflection:
      - what went well (tool calls that produced new actions)
      - what went wrong (gate_blocks, repeated tool calls, oscillations)
      - hypotheses for why
      - concrete improvement suggestions

  find_recurring_failures(window_hours=72)
    Cross-run pattern analysis: which Shadow Gate reasons recur?
    Which tools fail most often? Which tasks tend to hit MAX_STEPS?

  meta_critique(text)
    Apply own non-negotiables (Money Atlas tone, evidence requirements,
    claim classification) to a piece of output. Returns issues + score.

  propose_self_improvements()
    Looks at recent failure patterns + Genome failure_map + recent diary
    entries → produces a concrete list of improvements to backend code or
    prompts.

  watch_thinking(traj_event)
    Streaming hook — call from agent_run after each event to score:
    is the agent looping? is it making progress? is its reasoning shallow?
    Returns a score + suggested intervention (none / nudge / abort).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import re
import time
import sqlite3
import datetime as _dt
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BASE = Path(__file__).parent
DB_PATH = _BASE / "skynerclaw.db"
SESSIONS_DIR = _BASE / "sessions"
AUDIT_PATH = _BASE / "audit_trail.jsonl"
GENOME_PATH = _BASE / "atlas_genome.json"
META_LOG_PATH = _BASE / "metacognition.jsonl"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — read existing artifacts
# ──────────────────────────────────────────────────────────────────────────────
def _safe_load_jsonl(path: Path, limit: int = 5000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln: continue
                try: out.append(json.loads(ln))
                except: pass
                if len(out) >= limit: break
    except Exception:
        pass
    return out


def _find_trajectory_file(run_id: str) -> Optional[Path]:
    if not SESSIONS_DIR.exists():
        return None
    # filename format: {YYYYMMDD-HHMMSS}_{shortid}.trajectory.jsonl
    short = run_id[:10]
    candidates = list(SESSIONS_DIR.glob(f"*_{short}.trajectory.jsonl"))
    if candidates:
        return candidates[0]
    return None


def _get_run_row(run_id: str) -> Optional[Dict[str, Any]]:
    if not DB_PATH.exists():
        return None
    try:
        with sqlite3.connect(DB_PATH) as c:
            row = c.execute(
                "SELECT id, started_at, ended_at, task, model, status, "
                "n_steps, n_tools, n_blocks, trajectory_path, summary "
                "FROM agent_runs WHERE id=?", (run_id,),
            ).fetchone()
        if not row:
            return None
        keys = ["id","started_at","ended_at","task","model","status",
                "n_steps","n_tools","n_blocks","trajectory_path","summary"]
        return dict(zip(keys, row))
    except Exception:
        return None


def _meta_log(event: str, payload: Dict[str, Any]) -> None:
    """Append a metacognition event to its own log (separate from audit)."""
    try:
        entry = {"ts": time.time(), "event": event, **payload}
        with META_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# 1. REFLECT ON ONE RUN — trajectory replay + diagnosis
# ──────────────────────────────────────────────────────────────────────────────
def reflect_on_run(run_id: str) -> Dict[str, Any]:
    """
    Replay one agent_run trajectory + audit and produce a structured reflection.

    Output keys:
      run            — the agent_runs row
      events         — count by event type
      tool_call_seq  — ordered list of [(step, tool)]
      gate_blocks    — list of (step, name, reason)
      duplicates     — tool calls that were dedupe-blocked
      what_worked    — diagnostic strings
      what_failed    — diagnostic strings
      hypotheses     — root-cause guesses
      suggestions    — concrete next-step suggestions
    """
    row = _get_run_row(run_id) or {}
    traj_path = Path(row.get("trajectory_path", "")) if row.get("trajectory_path") else _find_trajectory_file(run_id)
    if not (traj_path and traj_path.exists()):
        return {
            "run_id": run_id, "found": False,
            "error": "trajectory file not found — run may pre-date OpenClaw port",
            "row": row,
        }

    events = _safe_load_jsonl(traj_path)
    by_event = Counter(e.get("event", "?") for e in events)
    tool_call_seq: List[Tuple[int, str]] = []
    gate_blocks: List[Tuple[int, str, str]] = []
    tool_results: List[Tuple[int, str, bool]] = []
    plan = ""

    for e in events:
        kind = e.get("event")
        step = e.get("step", 0)
        if kind == "tool_call":
            tool_call_seq.append((step, e.get("name", "?")))
        elif kind == "gate_block":
            gate_blocks.append((step, e.get("name", "?"), e.get("reason", "")))
        elif kind == "tool_result":
            tool_results.append((step, e.get("name", "?"), bool(e.get("ok", True))))
        elif kind == "plan":
            plan = e.get("plan", "")

    # ── Pattern analysis ──
    tool_freq = Counter(t for _, t in tool_call_seq)
    duplicates = [t for t, n in tool_freq.items() if n > 1]
    failed_results = [(s, n) for (s, n, ok) in tool_results if not ok]

    # Oscillation detection — A,B,A,B,A pattern
    seq_names = [t for _, t in tool_call_seq]
    oscillating = False
    if len(seq_names) >= 6:
        last6 = seq_names[-6:]
        if len(set(last6)) <= 2 and len(last6) == 6:
            oscillating = True

    # ── Diagnose ──
    what_worked: List[str] = []
    what_failed: List[str] = []

    n_unique = len(set(seq_names))
    if n_unique >= 3:
        what_worked.append(f"used {n_unique} distinct tools — no monoculture")
    if row.get("status") == "TASK_COMPLETE":
        what_worked.append(f"reached TASK_COMPLETE in {row.get('n_steps', '?')} steps")
    if plan:
        what_worked.append(f"emitted explicit PLAN at step 1")

    if gate_blocks:
        what_failed.append(f"{len(gate_blocks)} Shadow Gate block(s) — model tried fabricated values or denylisted commands")
    if duplicates:
        what_failed.append(f"attempted {len(duplicates)} duplicate tool call(s): {', '.join(duplicates[:3])}")
    if oscillating:
        what_failed.append(f"OSCILLATION detected — last 6 calls cycled between {len(set(seq_names[-6:]))} tools")
    if failed_results:
        what_failed.append(f"{len(failed_results)} tool execution(s) returned !ok")
    if row.get("status") in ("limit", "stuck"):
        what_failed.append(f"did not reach TASK_COMPLETE — terminal status: {row.get('status')}")

    # ── Hypotheses ──
    hypotheses: List[str] = []
    if any("live_data_unsatisfied" in r for _, _, r in gate_blocks):
        hypotheses.append("Model attempted to write file with prices/dates without calling live-data tool first — symptom of forgetting LIVE-DATA RULE")
    if any("value_match_failed" in r for _, _, r in gate_blocks):
        hypotheses.append("Model fetched real data but then wrote different numbers (hallucination after fetch) — VALUE-LOCK nudge wasn't strong enough")
    if oscillating:
        hypotheses.append("Likely tool result format confused the model — try inspecting last few tool results for ambiguity")
    if duplicates and not gate_blocks:
        hypotheses.append("Model didn't read COMPLETED_ACTIONS ledger — prompt may be too long, ledger pushed out of attention")
    if not plan:
        hypotheses.append("No PLAN emitted at step 1 — model went tactical, not strategic")

    # ── Suggestions ──
    suggestions: List[str] = []
    if any("live_data_unsatisfied" in r for _, _, r in gate_blocks):
        suggestions.append("Add the failing pattern to LIVE_DATA_PATTERNS regex in skynetclaw_meta if not already")
    if oscillating:
        suggestions.append("Lower MAX_STEPS for similar tasks; tighten cycle-breaker threshold (currently 6 last sigs)")
    if not plan:
        suggestions.append("Strengthen PLAN-FIRST RULE in AGENTS.md — make plan emission a hard prerequisite")
    if duplicates:
        suggestions.append("Verify COMPLETED_ACTIONS ledger is being injected fresh each step (check _format_completed)")
    if not what_failed and row.get("status") == "TASK_COMPLETE":
        suggestions.append("Successful run — extract the tool sequence as a Genome execution_path for replay")

    result = {
        "run_id": run_id,
        "found": True,
        "row": row,
        "events_count": dict(by_event),
        "tool_call_seq": tool_call_seq[:50],
        "gate_blocks": gate_blocks,
        "duplicates": duplicates,
        "oscillating": oscillating,
        "plan_captured": bool(plan),
        "what_worked": what_worked,
        "what_failed": what_failed,
        "hypotheses": hypotheses,
        "suggestions": suggestions,
    }
    _meta_log("reflect.run", {
        "run_id": run_id, "blocks": len(gate_blocks),
        "oscillating": oscillating, "n_suggestions": len(suggestions),
    })
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 2. CROSS-RUN PATTERN ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────
def find_recurring_failures(window_hours: int = 72,
                            min_recurrence: int = 2) -> Dict[str, Any]:
    """
    Mine the agent_runs DB + audit trail for failure patterns over the last
    N hours. Surface ONLY patterns that recurred ≥min_recurrence times.
    """
    cutoff = time.time() - (window_hours * 3600)
    blocks_by_reason: Counter = Counter()
    failures_by_tool: Counter = Counter()
    stuck_tasks: List[str] = []
    all_runs: List[Dict[str, Any]] = []

    if DB_PATH.exists():
        try:
            with sqlite3.connect(DB_PATH) as c:
                rows = c.execute(
                    "SELECT id, started_at, status, n_steps, n_tools, n_blocks, task "
                    "FROM agent_runs WHERE started_at >= ?", (cutoff,),
                ).fetchall()
            for r in rows:
                rid, ts, status, ns, nt, nb, task = r
                all_runs.append({"id": rid, "status": status, "n_steps": ns,
                                  "n_tools": nt, "n_blocks": nb, "task": task})
                if status in ("limit", "stuck"):
                    stuck_tasks.append((task or "")[:80])
        except Exception as e:
            print(f"[meta.recurring] DB read failed: {e}")

    # Walk audit_trail for shadow_gate.block reasons
    for evt in _safe_load_jsonl(AUDIT_PATH, limit=10000):
        if evt.get("ts", 0) < cutoff:
            continue
        if evt.get("event") == "shadow_gate.block":
            payload = evt.get("payload", {})
            reason = payload.get("reason", "?")
            blocks_by_reason[reason] += 1
            tool = payload.get("tool", "?")
            failures_by_tool[tool] += 1

    recurring_blocks = {r: n for r, n in blocks_by_reason.items() if n >= min_recurrence}
    recurring_tool_failures = {t: n for t, n in failures_by_tool.items() if n >= min_recurrence}

    suggestions: List[str] = []
    if recurring_blocks.get("live_data_unsatisfied", 0) >= 3:
        suggestions.append("LIVE-DATA rule violated repeatedly — strengthen the directive in AGENTS.md or extend LIVE_DATA_PATTERNS")
    if recurring_blocks.get("value_match_failed", 0) >= 3:
        suggestions.append("Model keeps fetching real data then writing different numbers — VALUE-LOCK system message needs to be more aggressive (consider injecting BEFORE write_file, not after fetch)")
    if recurring_blocks.get("denylist", 0) >= 2:
        suggestions.append("Multiple denylist hits — model is suggesting destructive commands; review GENESIS_AGENT_PROMPT")
    if len(stuck_tasks) >= 3:
        suggestions.append(f"{len(stuck_tasks)} runs stuck at MAX_STEPS — consider raising step budget or splitting tasks")

    out = {
        "window_hours": window_hours,
        "n_runs_in_window": len(all_runs),
        "recurring_block_reasons": recurring_blocks,
        "recurring_tool_failures": recurring_tool_failures,
        "stuck_task_count": len(stuck_tasks),
        "stuck_task_examples": stuck_tasks[:5],
        "improvement_suggestions": suggestions,
    }
    _meta_log("reflect.recurring", {"window_h": window_hours,
                                      "n_blocks": sum(blocks_by_reason.values()),
                                      "n_runs": len(all_runs)})
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 3. META-CRITIQUE — apply own non-negotiables to arbitrary text
# ──────────────────────────────────────────────────────────────────────────────
_NON_NEGOTIABLES = [
    ("evidence_required", r"(without evidence|trust me|believe me|ฟังผมก่อน)",
     "Claim made without evidence — non-negotiable: 'every claim auditable'"),
    ("absolute_language", r"\b(100%|always|never|definitely|รับประกัน|แน่นอน|ไม่มีทาง)\b",
     "Absolute language — soften to probabilistic"),
    ("filler", r"(I'd be happy to|Great question|Sure thing|Certainly!)",
     "Sycophantic filler — non-negotiable: 'no shallow filler'"),
    ("apology", r"\b(I apologi[sz]e|sorry for the confusion)\b",
     "Excess apologizing — non-negotiable: 'don't collapse into self-abasement'"),
    ("vibe_no_substance", r"\b(amazing|incredible|fantastic|awesome|perfect)\b",
     "Vibe word without measurable referent — non-negotiable: 'truth > aesthetics'"),
]


def meta_critique(text: str) -> Dict[str, Any]:
    """
    Apply SkynetClaw's own quality bar to a piece of text.
    Returns issues + a 0-100 quality score.
    """
    if not text:
        return {"score": 100, "issues": [], "char_count": 0}
    issues: List[Dict[str, Any]] = []
    for tag, pat, hint in _NON_NEGOTIABLES:
        try:
            for m in re.finditer(pat, text, re.IGNORECASE):
                issues.append({
                    "tag": tag,
                    "match": m.group(0),
                    "position": m.start(),
                    "hint": hint,
                })
        except re.error:
            continue
    # Score: start at 100, deduct 8 per issue, floor at 0
    score = max(0, 100 - 8 * len(issues))
    out = {"score": score, "issues": issues[:20], "char_count": len(text)}
    _meta_log("critique", {"score": score, "n_issues": len(issues),
                            "char_count": len(text)})
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 4. PROPOSE SELF-IMPROVEMENTS — synthesize across all signals
# ──────────────────────────────────────────────────────────────────────────────
def propose_self_improvements(window_hours: int = 168) -> Dict[str, Any]:
    """
    Look at: recurring failures + Genome failure_map + recent agent_runs
    Output: prioritized list of improvements with target file + rationale.
    """
    recurring = find_recurring_failures(window_hours=window_hours, min_recurrence=2)
    proposals: List[Dict[str, Any]] = []

    # From Genome failure_map
    try:
        if GENOME_PATH.exists():
            g = json.loads(GENOME_PATH.read_text(encoding="utf-8"))
            for f in (g.get("failure_map") or []):
                sig = f.get("signature", "")
                if "rm -rf" in sig or "format " in sig.lower():
                    proposals.append({
                        "priority": "HIGH",
                        "target": "skynetclaw_meta.py DENYLIST_PATTERNS",
                        "issue": f"Failure signature recurred: {sig[:80]}",
                        "rationale": "Add explicit pattern to denylist if not already covered",
                        "evidence": f.get("rationale", ""),
                    })
    except Exception:
        pass

    # From recurring block reasons
    for reason, n in recurring.get("recurring_block_reasons", {}).items():
        if reason == "live_data_unsatisfied" and n >= 3:
            proposals.append({
                "priority": "HIGH",
                "target": "backend/prompts/AGENTS.md (LIVE-DATA RULE section)",
                "issue": f"LIVE-DATA gate blocked {n} times in {window_hours}h",
                "rationale": "Model not internalizing the fetch-first rule. Make it more emphatic / earlier in prompt",
                "evidence": f"shadow_gate.block × {n}",
            })
        elif reason == "value_match_failed" and n >= 3:
            proposals.append({
                "priority": "HIGH",
                "target": "main.py — agent_run VALUE-LOCK nudge",
                "issue": f"Value-match gate blocked {n} times — model writes wrong numbers after fetch",
                "rationale": "Inject VALUE-LOCK BEFORE write_file (preview content), not just AFTER fetch",
                "evidence": f"shadow_gate.block × {n}",
            })

    # From stuck runs
    if recurring.get("stuck_task_count", 0) >= 3:
        proposals.append({
            "priority": "MEDIUM",
            "target": "main.py — MAX_STEPS or task splitting",
            "issue": f"{recurring['stuck_task_count']} runs hit MAX_STEPS without TASK_COMPLETE",
            "rationale": "Either raise budget for complex tasks OR teach agent to split into sub-tasks",
            "evidence": "agent_runs.status='limit'",
        })

    # From tool failures
    for tool, n in recurring.get("recurring_tool_failures", {}).items():
        if n >= 3:
            proposals.append({
                "priority": "MEDIUM",
                "target": f"main.py — exec_tool '{tool}' implementation",
                "issue": f"{tool} failed {n} times",
                "rationale": "Tool implementation may need hardening (timeout, retry, fallback)",
                "evidence": f"tool_failures × {n}",
            })

    proposals.sort(key=lambda p: 0 if p["priority"] == "HIGH" else 1)
    out = {
        "generated_at": _dt.datetime.now().isoformat(),
        "window_hours": window_hours,
        "proposals": proposals,
        "summary": {
            "n_high":   sum(1 for p in proposals if p["priority"] == "HIGH"),
            "n_medium": sum(1 for p in proposals if p["priority"] == "MEDIUM"),
        },
    }
    _meta_log("propose", {"n_proposals": len(proposals)})
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 5. WATCH-THINKING — streaming hook for live intervention
# ──────────────────────────────────────────────────────────────────────────────
class ThinkingWatcher:
    """
    Live metacognitive observer over a single agent_run. Call observe()
    after each event; it returns a verdict that the loop can use to
    intervene early (nudge, abort) before MAX_STEPS exhausts.
    """
    def __init__(self):
        self.tool_seq: List[str] = []
        self.block_count = 0
        self.duplicate_count = 0
        self.steps_without_progress = 0
        self.last_progress_step = 0

    def observe(self, event: Dict[str, Any]) -> Dict[str, Any]:
        kind = event.get("event")
        step = event.get("step", 0)
        verdict = {"action": "continue", "score": 1.0, "reason": ""}

        if kind == "tool_call":
            name = event.get("name", "")
            self.tool_seq.append(name)
            # Check oscillation
            if len(self.tool_seq) >= 6:
                last6 = self.tool_seq[-6:]
                if len(set(last6)) <= 2:
                    verdict = {
                        "action": "abort",
                        "score": 0.1,
                        "reason": f"oscillation detected — last 6 tools cycle between {len(set(last6))} names",
                    }
        elif kind == "gate_block":
            self.block_count += 1
            if self.block_count >= 3:
                verdict = {
                    "action": "abort",
                    "score": 0.2,
                    "reason": f"3 Shadow Gate blocks in this run — model not learning from critique",
                }
            elif self.block_count >= 2:
                verdict = {
                    "action": "nudge",
                    "score": 0.5,
                    "reason": f"2 blocks so far — inject explicit reminder of LIVE-DATA + VALUE-LOCK rules",
                }
        elif kind == "tool_result":
            self.last_progress_step = step
            self.steps_without_progress = 0
        elif kind == "step":
            if step > self.last_progress_step + 3 and self.last_progress_step > 0:
                self.steps_without_progress = step - self.last_progress_step
                if self.steps_without_progress >= 4:
                    verdict = {
                        "action": "abort",
                        "score": 0.3,
                        "reason": f"{self.steps_without_progress} steps without a tool_result",
                    }
        return verdict


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    print("=== metacognition self-test ===\n")

    # Meta-critique
    print("[1] meta_critique on overclaim text:")
    r = meta_critique("รับประกัน 100% ว่าราคาทองจะขึ้นแน่นอน — perfect prediction! "
                       "I'd be happy to help, sorry for any confusion.")
    print(f"    score: {r['score']}, issues: {len(r['issues'])}")
    for i in r["issues"]:
        print(f"      • {i['tag']}: '{i['match']}' — {i['hint'][:60]}")

    print("\n[2] meta_critique on clean text:")
    r2 = meta_critique("Spot gold price ฿71,300 per บาท (per GTA 2026-05-06). "
                       "Trade-off: tighter spread reduces slippage but lowers fill rate.")
    print(f"    score: {r2['score']}, issues: {len(r2['issues'])}")

    # Recurring failures (over real audit if any)
    print("\n[3] find_recurring_failures (last 168h):")
    rf = find_recurring_failures(window_hours=168, min_recurrence=1)
    print(f"    runs in window: {rf['n_runs_in_window']}")
    print(f"    block reasons:  {rf['recurring_block_reasons']}")
    print(f"    suggestions:    {len(rf['improvement_suggestions'])}")

    # Self-improvement proposals
    print("\n[4] propose_self_improvements:")
    pi = propose_self_improvements(window_hours=168)
    print(f"    proposals: HIGH={pi['summary']['n_high']} MEDIUM={pi['summary']['n_medium']}")
    for p in pi["proposals"][:3]:
        print(f"      [{p['priority']}] {p['target']}")
        print(f"         issue: {p['issue']}")

    # ThinkingWatcher
    print("\n[5] ThinkingWatcher — synthetic oscillation:")
    w = ThinkingWatcher()
    sample = ["A","B","A","B","A","B"]  # oscillation
    for i, t in enumerate(sample, 1):
        v = w.observe({"event": "tool_call", "name": t, "step": i})
        print(f"    after {t} (step {i}): action={v['action']} reason={v['reason'][:60]}")

    print("\n=== self-test OK ===")
