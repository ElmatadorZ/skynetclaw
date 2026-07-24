"""
agentic_workflow.py — 4-Phase Comprehension-First Orchestrator
================================================================
The piece that turns SkynetClaw from "tool-spamming labor" into "agent that
understands what it's doing". Instead of jumping straight into tool calls,
the agent first comprehends → plans → executes → reflects.

Pipeline:

    PHASE 1: COMPREHEND
        LLM call → JSON{restated, intent, assumptions, gaps, success_criteria}
        ↓
    PHASE 2: PLAN
        LLM call → JSON{steps[], checkpoints[], risks[], rollback_plan}
        ↓
    PHASE 3: EXECUTE
        Delegate to existing /api/agent/run with comprehend+plan injected
        as system context (streams agent events)
        ↓
    PHASE 4: REFLECT
        metacognition.reflect_on_run + LLM synthesis → JSON{lessons,
        genome_proposals, what_to_improve}

Each phase is a separate LLM call returning STRUCTURED JSON. This makes the
agent's reasoning auditable, replayable, and reviewable BEFORE expensive
execution. Cheap to run — 3-4 LLM calls add ~10-30s but save 5-10min of
brute-force tool spam.

If the model doesn't follow JSON format, we fall back to plain-text parsing
with regex — best-effort, never crashes.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

import httpx


# ──────────────────────────────────────────────────────────────────────────────
# Datatypes
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Comprehension:
    restated: str               # task in agent's own words
    intent: str                 # core_drive — what user actually wants
    assumptions: List[str]      # what we're taking for granted
    gaps: List[str]             # what we DON'T know but need
    success_criteria: List[str] # what "done" looks like — measurable
    estimated_complexity: str   # "trivial" | "moderate" | "complex" | "ambiguous"
    raw_response: str = ""      # for debugging

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanStep:
    n: int
    action: str                 # what to do
    tool_hint: str              # which tool likely needed
    success_signal: str         # how to verify this step worked

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    steps: List[PlanStep]
    checkpoints: List[str]      # where to pause and verify mid-execution
    risks: List[str]            # what could go wrong
    rollback_plan: str          # what to do if it does
    estimated_steps: int
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps":           [s.to_dict() for s in self.steps],
            "checkpoints":     self.checkpoints,
            "risks":           self.risks,
            "rollback_plan":   self.rollback_plan,
            "estimated_steps": self.estimated_steps,
        }


@dataclass
class Reflection:
    what_worked: List[str]
    what_failed: List[str]
    lessons: List[str]
    genome_proposals: List[Dict[str, Any]]   # candidate Genome rules to learn
    improvement_targets: List[str]
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────────
# Auto-apply Genome proposals (Phase 4 → Genome update)
# ──────────────────────────────────────────────────────────────────────────────
import os
from pathlib import Path as _Path

_GENOME_PATH = _Path(__file__).parent / "atlas_genome.json"


def apply_genome_proposals(reflection: Reflection,
                            confidence_threshold: float = 0.7) -> Dict[str, Any]:
    """
    Take reflection.genome_proposals and write the high-confidence ones into
    atlas_genome.json.strategy_rules. Skips proposals below threshold.

    Returns {applied: [...], skipped: [...], errors: [...]}.
    """
    out = {"applied": [], "skipped": [], "errors": []}
    if not reflection.genome_proposals:
        return out
    try:
        if _GENOME_PATH.exists():
            g = json.loads(_GENOME_PATH.read_text(encoding="utf-8"))
        else:
            g = {"version": 1, "strategy_rules": [], "execution_paths": [],
                 "failure_map": [], "scenario_weights": {}, "updated_at": 0}
        rules = g.setdefault("strategy_rules", [])
        existing_keys = {(r.get("if", ""), r.get("then", "")) for r in rules}
        for p in reflection.genome_proposals:
            if not isinstance(p, dict):
                continue
            conf = float(p.get("confidence", 0.5) or 0.5)
            if conf < confidence_threshold:
                out["skipped"].append({"reason": f"confidence {conf:.2f} < {confidence_threshold}",
                                        "proposal": p})
                continue
            if_pat = str(p.get("if", "")).strip()
            then_act = str(p.get("then", "")).strip()
            if not if_pat or not then_act:
                out["skipped"].append({"reason": "missing if/then", "proposal": p})
                continue
            key = (if_pat, then_act)
            if key in existing_keys:
                out["skipped"].append({"reason": "duplicate rule already in Genome", "proposal": p})
                continue
            rules.append({
                "id": f"rule_{abs(hash(key)) % 10**8:08d}",
                "if": if_pat,
                "then": then_act,
                "confidence": conf,
                "evidence_count": 1,
                "source": "auto:workflow.reflect",
                "created_at": int(__import__("time").time()),
            })
            existing_keys.add(key)
            out["applied"].append(p)
        g["updated_at"] = int(__import__("time").time())
        # Atomic write
        tmp = _GENOME_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_GENOME_PATH)
    except Exception as e:
        out["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
    return out


# ──────────────────────────────────────────────────────────────────────────────
# LLM call helper — Ollama JSON mode
# ──────────────────────────────────────────────────────────────────────────────
async def _llm_call_json(system: str, user: str, model: str,
                          base_url: str = "http://localhost:11434",
                          api_key: str = "", timeout: int = 90,
                          temperature: float = 0.15) -> Dict[str, Any]:
    """
    Call Ollama (or OpenAI-compat) with JSON format hint.
    Returns {ok, json (if parseable), text, error}.
    """
    out: Dict[str, Any] = {"ok": False, "json": None, "text": "", "error": ""}
    msgs = [
        {"role": "system", "content": system + "\n\nIMPORTANT: respond with VALID JSON only. No prose before or after."},
        {"role": "user",   "content": user},
    ]
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    # Adapter-aware: an OpenAI-compatible runtime (e.g. the llama.cpp GPU server at
    # /v1) doesn't speak Ollama's /api/chat. Route by endpoint so the 4-phase
    # workflow works on whichever runtime is active — no hardcoded provider.
    _b = base_url.rstrip("/")
    is_openai = _b.endswith("/v1") or "/v1/" in _b
    if is_openai:
        url = _b + "/chat/completions"
        payload = {"model": model or "", "messages": msgs, "stream": False,
                   "temperature": temperature, "response_format": {"type": "json_object"}}
    else:
        url = _b + "/api/chat"
        payload = {"model": model or "", "messages": msgs, "stream": False,
                   "format": "json", "options": {"temperature": temperature, "num_ctx": 16384}}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            out["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
            return out
        data = r.json()
        if is_openai:
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        else:
            text = (data.get("message") or {}).get("content", "") or data.get("response", "") or ""
        out["text"] = text
        # Try to parse as JSON
        parsed = _extract_json(text)
        if parsed is not None:
            out["json"] = parsed
            out["ok"] = True
        else:
            out["error"] = "response not parseable as JSON"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


def _extract_json(text: str) -> Optional[Any]:
    """Robust JSON extraction — handles leading/trailing prose, markdown fences."""
    if not text:
        return None
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Find largest balanced {...} or [...]
    for open_c, close_c in [("{", "}"), ("[", "]")]:
        i = text.find(open_c)
        if i < 0:
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == open_c: depth += 1
            elif text[j] == close_c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:j+1])
                    except Exception:
                        break
    return None


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1: COMPREHEND — does the agent actually understand the task?
# ──────────────────────────────────────────────────────────────────────────────
COMPREHEND_SYSTEM = """You are SkynetClaw in COMPREHENSION phase. Your only job: prove you understand the user's task BEFORE doing any work.

Output STRICT JSON with these keys:
{
  "restated": "task in your own words, 1-2 sentences",
  "intent": "the core drive — what does the user REALLY want? (one phrase)",
  "assumptions": ["thing 1 I'm taking for granted", "thing 2", ...],
  "gaps": ["info I need but don't have", ...],
  "success_criteria": ["measurable signal of 'done' #1", "...", "..."],
  "estimated_complexity": "trivial" | "moderate" | "complex" | "ambiguous"
}

Rules:
- restated must be in the user's language
- gaps must be SPECIFIC (file paths, model names, sources, numbers) — not "more info"
- success_criteria must be VERIFIABLE — not "user is happy"
- If task is ambiguous, mark estimated_complexity="ambiguous" and put the disambiguation in gaps
- DO NOT propose tools or steps yet — that's phase 2
- DO NOT execute anything — this is reasoning only
"""

async def comprehend(task: str, model: str, base_url: str = "",
                     api_key: str = "") -> Comprehension:
    """Phase 1: extract intent + assumptions + gaps + success criteria."""
    base = base_url or "http://localhost:11434"
    res = await _llm_call_json(COMPREHEND_SYSTEM, f"Task:\n{task}",
                                model=model, base_url=base, api_key=api_key,
                                timeout=60, temperature=0.15)
    if res.get("ok") and isinstance(res.get("json"), dict):
        j = res["json"]
        return Comprehension(
            restated=str(j.get("restated", "") or task[:200])[:500],
            intent=str(j.get("intent", "") or "build")[:200],
            assumptions=_to_list(j.get("assumptions"))[:10],
            gaps=_to_list(j.get("gaps"))[:10],
            success_criteria=_to_list(j.get("success_criteria"))[:10],
            estimated_complexity=str(j.get("estimated_complexity", "moderate")),
            raw_response=res.get("text", "")[:2000],
        )
    # Fallback — heuristic comprehension when LLM JSON fails
    return Comprehension(
        restated=task[:300],
        intent="(LLM JSON parse failed — fall back to direct execution)",
        assumptions=["LLM did not return structured comprehension"],
        gaps=[res.get("error", "JSON parse failed")],
        success_criteria=["TASK_COMPLETE event from agent loop"],
        estimated_complexity="moderate",
        raw_response=res.get("text", "")[:1000],
    )


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 2: PLAN — structured steps with checkpoints + risk model
# ──────────────────────────────────────────────────────────────────────────────
PLAN_SYSTEM = """You are SkynetClaw in PLANNING phase. The COMPREHENSION is given. Now design the path — but DO NOT execute.

Output STRICT JSON with these keys:
{
  "steps": [
    {"n": 1, "action": "describe what to do", "tool_hint": "tool name expected", "success_signal": "how to verify"},
    ...
  ],
  "checkpoints": ["mid-execution review points — e.g. 'after step 3, verify file X was created'"],
  "risks": ["concrete failure modes"],
  "rollback_plan": "what to do if execution fails halfway",
  "estimated_steps": <integer>
}

Rules:
- Use ONLY tools that exist: read_file, write_file, edit_file, delete_file, list_files, find_files,
  shell_command, run_python, install_package, get_*_price, get_news, web_search, http_request,
  search_obsidian, read_obsidian_note, write_obsidian_note, ask_user_options, telegram_send, etc.
- Live-data tool MUST come BEFORE write_file when content has prices/dates/rates
- Each step's success_signal must be checkable from the tool's return value
- estimated_steps ≤ 15 — if more, the task is too big; split it
- risks must be SPECIFIC (e.g. "network might be down", not "errors")
- rollback_plan must be actionable (e.g. "delete created files in workspace folder")
"""

async def build_plan(task: str, comprehension: Comprehension,
                      model: str, base_url: str = "",
                      api_key: str = "") -> Plan:
    """Phase 2: produce a structured plan from the comprehension."""
    base = base_url or "http://localhost:11434"
    user_msg = (
        f"TASK:\n{task}\n\n"
        f"COMPREHENSION:\n{json.dumps(comprehension.to_dict(), ensure_ascii=False, indent=2)}\n\n"
        "Design the plan."
    )
    res = await _llm_call_json(PLAN_SYSTEM, user_msg, model=model,
                                base_url=base, api_key=api_key,
                                timeout=90, temperature=0.15)
    if res.get("ok") and isinstance(res.get("json"), dict):
        j = res["json"]
        steps = []
        for i, s in enumerate(_to_list(j.get("steps", [])), 1):
            if isinstance(s, dict):
                steps.append(PlanStep(
                    n=int(s.get("n", i)),
                    action=str(s.get("action", ""))[:300],
                    tool_hint=str(s.get("tool_hint", ""))[:60],
                    success_signal=str(s.get("success_signal", ""))[:200],
                ))
        return Plan(
            steps=steps[:15],
            checkpoints=_to_list(j.get("checkpoints"))[:6],
            risks=_to_list(j.get("risks"))[:6],
            rollback_plan=str(j.get("rollback_plan", ""))[:500],
            estimated_steps=int(j.get("estimated_steps", len(steps)) or len(steps)),
            raw_response=res.get("text", "")[:2000],
        )
    # Fallback
    return Plan(
        steps=[PlanStep(n=1, action=task[:200],
                        tool_hint="unknown",
                        success_signal="TASK_COMPLETE")],
        checkpoints=["LLM plan-phase failed — proceed with direct execution"],
        risks=["No structured plan available"],
        rollback_plan="manual review",
        estimated_steps=10,
        raw_response=res.get("text", "")[:1000],
    )


def format_plan_for_agent(comp: Comprehension, plan: Plan) -> str:
    """Render comprehension + plan as a system message for /api/agent/run."""
    L = [
        "## 🎯 WORKFLOW CONTEXT (Phase 1 + 2 already executed)",
        "",
        "### YOU UNDERSTAND THE TASK AS:",
        f"  {comp.restated}",
        f"  Core intent: {comp.intent}",
        f"  Complexity:  {comp.estimated_complexity}",
        "",
    ]
    if comp.assumptions:
        L.append("### YOUR ASSUMPTIONS:")
        for a in comp.assumptions: L.append(f"  • {a}")
        L.append("")
    if comp.gaps:
        L.append("### KNOWN GAPS (call ask_user_options if any of these block you):")
        for g in comp.gaps: L.append(f"  ⚠ {g}")
        L.append("")
    if comp.success_criteria:
        L.append("### SUCCESS = ALL OF:")
        for c in comp.success_criteria: L.append(f"  ✓ {c}")
        L.append("")
    L.append("### YOUR PLAN:")
    for s in plan.steps:
        L.append(f"  {s.n}) {s.action}")
        if s.tool_hint:      L.append(f"       tool: {s.tool_hint}")
        if s.success_signal: L.append(f"       verify: {s.success_signal}")
    L.append("")
    if plan.checkpoints:
        L.append("### MID-EXECUTION CHECKPOINTS (re-verify here):")
        for c in plan.checkpoints: L.append(f"  ⚑ {c}")
        L.append("")
    if plan.risks:
        L.append("### KNOWN RISKS:")
        for r in plan.risks: L.append(f"  ⚠ {r}")
        L.append("")
    if plan.rollback_plan:
        L.append(f"### ROLLBACK IF FAILED: {plan.rollback_plan}")
        L.append("")
    L.append("Now EXECUTE the plan above. Follow the steps in order. At each checkpoint, "
             "verify the success signal before moving on. If a step fails, use the rollback "
             "plan rather than improvising.")
    return "\n".join(L)


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 4: REFLECT — what did we learn?
# ──────────────────────────────────────────────────────────────────────────────
REFLECT_SYSTEM = """You are SkynetClaw in REFLECTION phase. A task just finished. Look at:
- The COMPREHENSION you produced
- The PLAN you made
- The TRAJECTORY summary (what actually happened)

Output STRICT JSON:
{
  "what_worked": ["concrete things that went well"],
  "what_failed": ["concrete things that didn't"],
  "lessons": ["short, transferable insights"],
  "genome_proposals": [
    {"if": "trigger pattern", "then": "behavior to adopt", "confidence": 0.0-1.0}
  ],
  "improvement_targets": ["which module / prompt / rule to refine next"]
}

Rules:
- Be specific. "It worked" is useless. "get_gold_price succeeded after CoinGecko fallback" is useful.
- Lessons must be GENERAL — applicable to future tasks, not just this one.
- Genome proposals must have testable triggers (regex-able, not vibes).
- improvement_targets must name an actual artifact (file, prompt, rule).
"""

async def reflect(task: str, comprehension: Comprehension, plan: Plan,
                   trajectory_summary: Dict[str, Any], model: str,
                   base_url: str = "", api_key: str = "") -> Reflection:
    """Phase 4: synthesize lessons + Genome proposals."""
    base = base_url or "http://localhost:11434"
    user_msg = (
        f"TASK:\n{task}\n\n"
        f"COMPREHENSION:\n{json.dumps(comprehension.to_dict(), ensure_ascii=False, indent=2)}\n\n"
        f"PLAN:\n{json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)}\n\n"
        f"TRAJECTORY SUMMARY:\n{json.dumps(trajectory_summary, ensure_ascii=False, indent=2)}\n\n"
        "Reflect now."
    )
    res = await _llm_call_json(REFLECT_SYSTEM, user_msg, model=model,
                                base_url=base, api_key=api_key,
                                timeout=60, temperature=0.2)
    if res.get("ok") and isinstance(res.get("json"), dict):
        j = res["json"]
        return Reflection(
            what_worked=_to_list(j.get("what_worked"))[:8],
            what_failed=_to_list(j.get("what_failed"))[:8],
            lessons=_to_list(j.get("lessons"))[:8],
            genome_proposals=[g for g in _to_list(j.get("genome_proposals")) if isinstance(g, dict)][:6],
            improvement_targets=_to_list(j.get("improvement_targets"))[:6],
            raw_response=res.get("text", "")[:2000],
        )
    # OX-STABILITY-1 Phase 2: a FAILED reflection is an ERROR, not a lesson.
    # Emitting a sentinel "lesson" leaked error text into learning + mission
    # identities. Return NO learnings; record the failure only in what_failed
    # (a diagnostic channel), never in lessons/objectives.
    return Reflection(
        what_worked=[], what_failed=["reflection_phase_error: model returned no valid JSON"],
        lessons=[],
        genome_proposals=[], improvement_targets=[],
        raw_response=res.get("text", "")[:1000],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _to_list(x) -> List[Any]:
    if x is None:           return []
    if isinstance(x, list): return x
    if isinstance(x, str):  return [x] if x.strip() else []
    return [x]


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, asyncio
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

    print("=== agentic_workflow self-test ===\n")
    print("(needs Ollama running at localhost:11434 with a model loaded)")
    print()

    async def _test():
        task = "สร้างไฟล์ market_brief.md ใน workspace ที่มีราคาทองวันนี้และ USD/THB"
        # Try to find any local model
        model = "nemotron3:33b"
        print(f"[1] COMPREHEND for: {task[:80]}")
        comp = await comprehend(task, model=model)
        print(f"    restated   : {comp.restated[:120]}")
        print(f"    intent     : {comp.intent}")
        print(f"    complexity : {comp.estimated_complexity}")
        print(f"    assumptions: {len(comp.assumptions)} items")
        print(f"    gaps       : {len(comp.gaps)} items")
        print(f"    success    : {len(comp.success_criteria)} items")
        if not comp.intent or "fail" in comp.intent.lower():
            print(f"    raw       : {comp.raw_response[:200]}")
            print("    (LLM not reachable — that's OK for self-test)")
            return

        print(f"\n[2] PLAN ...")
        plan = await build_plan(task, comp, model=model)
        print(f"    steps      : {len(plan.steps)} (estimated {plan.estimated_steps})")
        for s in plan.steps[:3]:
            print(f"      {s.n}) {s.action[:80]} [{s.tool_hint}]")
        print(f"    checkpoints: {len(plan.checkpoints)}")
        print(f"    risks      : {len(plan.risks)}")

        print(f"\n[3] format_plan_for_agent — system message preview:")
        sysmsg = format_plan_for_agent(comp, plan)
        print(sysmsg[:600] + "..." if len(sysmsg) > 600 else sysmsg)

        print(f"\n[4] REFLECT on simulated trajectory:")
        sim_traj = {"n_steps": 5, "n_tools": 7, "n_blocks": 1,
                    "status": "TASK_COMPLETE",
                    "tools_used": ["get_gold_price","get_forex_rate","write_file"]}
        refl = await reflect(task, comp, plan, sim_traj, model=model)
        print(f"    worked   : {refl.what_worked[:2]}")
        print(f"    failed   : {refl.what_failed[:2]}")
        print(f"    lessons  : {refl.lessons[:2]}")
        print(f"    proposals: {len(refl.genome_proposals)} Genome rule(s)")

    try:
        asyncio.run(_test())
        print("\n=== self-test OK ===")
    except Exception as e:
        print(f"\n(self-test skipped — {type(e).__name__}: {str(e)[:150]})")
        print("=== module syntax OK ===")
