"""
compound_mind.py — L3 Compound Mind + L6 Cosmic Mind for the LIVE agent_run loop
================================================================================
Closes the gap the Operator flagged: the protocol (Compound Mind / Cosmic Mind)
lived only in skill PROMPT TEXT and a separate workflow endpoint — never in the
loop that actually runs missions. This module wires it in.

What it does (one analysis pass, BEFORE the step loop):

  L3 COMPOUND MIND
    - tokenize the prompt to its intent core
    - explore 2-4 distinct SOLUTION AXES (not one linear plan)
    - SELECT the optimal path with an explicit reason
    - emit dependency-tagged WORK TRACKS -> topologically batched into groups
      so independent work runs back-to-back (no linear 1-2-3-4-5 re-planning)

  L6 COSMIC MIND (conditional — horizon > ~3y, system design, or macro forces)
    - scenario x horizon x observer-frame analysis of the PLAN
    - no-regret moves that hold across all scenarios

The result is injected as a system prompt that REPLACES the naive
"PLAN: 1) 2) 3)" instruction in agent_run.

Reuses agentic_workflow._llm_call_json (Ollama/OpenAI-compat JSON mode).
License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from agentic_workflow import _llm_call_json  # JSON-mode LLM caller
    _LLM_OK = True
except Exception:  # pragma: no cover - module still importable for offline tests
    _LLM_OK = False
    async def _llm_call_json(*a, **k):  # type: ignore
        return {"ok": False, "json": None, "text": "", "error": "llm helper unavailable"}


# ──────────────────────────────────────────────────────────────────────────────
# Gates — keep cheap tasks cheap
# ──────────────────────────────────────────────────────────────────────────────
_COMPOUND_HINTS = (
    "system", "build", "design", "architecture", "strategy", "plan", "pipeline",
    "refactor", "migrate", "integrate", "optimize", "compare", "analyze", "research",
    "และ", "แล้ว", "จากนั้น", "วางแผน", "ออกแบบ", "สร้างระบบ", "กลยุทธ์", "วิเคราะห์",
)
_COSMIC_HINTS = (
    "long-term", "long term", "decade", "years", "future", "macro", "civilization",
    "geopolit", "system design", "architecture", "roadmap", "vision", "horizon",
    "ระยะยาว", "อนาคต", "มหภาค", "วิสัยทัศน์", "ทศวรรษ", "สร้างระบบ",
)
_YEAR_RE = re.compile(r"\b(\d{1,2})\s*(?:year|yr|ปี)\b", re.I)


def should_run_compound(task: str) -> bool:
    """True when a task is non-trivial enough to deserve compound decomposition.

    Trivial one-shot asks ("what time is it", "read file X") skip straight to the
    fast linear loop. Multi-clause / build / strategy / research tasks compound.
    """
    if not task:
        return False
    t = task.strip()
    low = t.lower()
    if len(t) >= 160:
        return True
    # multiple imperative clauses or explicit conjunction = compound work
    clause_markers = low.count(" and ") + low.count(",") + low.count(";") \
        + low.count("•") + low.count(" then ") + low.count("และ") + low.count("แล้ว")
    if clause_markers >= 2:
        return True
    if any(h in low for h in _COMPOUND_HINTS):
        return True
    return False


def qualifies_for_cosmic(task: str) -> bool:
    """True when Cosmic Mind (long-horizon scenarios) is worth running.

    Matches the skill's own activation rule: horizon > ~3y, system design, or
    macro forces dominant. Skips tactical/short tasks.
    """
    if not task:
        return False
    low = task.lower()
    m = _YEAR_RE.search(low)
    if m:
        try:
            if int(m.group(1)) >= 3:
                return True
        except Exception:
            pass
    return any(h in low for h in _COSMIC_HINTS)


# ──────────────────────────────────────────────────────────────────────────────
# Topological grouping — turn depends_on into parallel-ready batches
# ──────────────────────────────────────────────────────────────────────────────
def _topo_groups(tracks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Batch tracks so every track in a group has all deps satisfied by earlier
    groups. Tracks in the SAME group are independent -> can run back-to-back
    (or, later, concurrently). Cycles/unknown deps are flushed into a final group
    so nothing is silently dropped.
    """
    by_id = {str(t.get("id") or f"T{i+1}"): t for i, t in enumerate(tracks)}
    # normalise ids onto the track dicts
    for i, t in enumerate(tracks):
        t["id"] = str(t.get("id") or f"T{i+1}")
    done: set = set()
    groups: List[List[Dict[str, Any]]] = []
    remaining = list(tracks)
    guard = 0
    while remaining and guard < 50:
        guard += 1
        layer = []
        for t in remaining:
            deps = [str(d) for d in (t.get("depends_on") or []) if str(d) in by_id]
            if all(d in done for d in deps):
                layer.append(t)
        if not layer:  # cycle or dangling dep — flush the rest
            groups.append(remaining)
            return groups
        groups.append(layer)
        for t in layer:
            done.add(t["id"])
        remaining = [t for t in remaining if t["id"] not in done]
    if remaining:
        groups.append(remaining)
    return groups


# ──────────────────────────────────────────────────────────────────────────────
# L3 Compound Mind prompt
# ──────────────────────────────────────────────────────────────────────────────
_L3_SYSTEM = """You are L3 COMPOUND MIND of SkynetClaw — the planning engine that
replaces naive linear 1-2-3 stepping. You do NOT execute. You decompose.

Given a mission, you:
1. tokenize it to its intent core,
2. explore 2-4 genuinely DISTINCT solution AXES (different strategies, not steps),
3. pick the OPTIMAL axis and say why,
4. break the chosen axis into WORK TRACKS with explicit dependencies, so
   independent tracks can run in parallel and dependent ones are ordered,
5. state verifiable DONE_WHEN criteria.

Assign each track to the right operative:
THE ANALYST(facts) · THE STRATEGIST(plan) · THE SKEPTIC(risk) · THE FORECASTER(scenarios)
· THE EXECUTOR(build/tools) · THE SCOUT(find tool/code) · THE AUDITOR(verify)
· THE GOVERNOR(rules) · THE ARCHITECT(design) · THE SENTINEL(security) · THE STORYTELLER(brief)

Output STRICT JSON:
{
  "tokens": ["core","intent","tokens"],
  "axes": [{"name":"...","approach":"...","tradeoff":"..."}],
  "chosen_axis": "name of chosen axis",
  "chosen_why": "one line",
  "tracks": [{"id":"T1","task":"concrete action","operative":"THE EXECUTOR","depends_on":[]}],
  "done_when": "verifiable completion criteria"
}
Tracks must be concrete and tool-shaped. Mark truly independent tracks with depends_on:[]."""


async def compound_decompose(task: str, context: Optional[Dict[str, Any]],
                             model: str, base_url: str, api_key: str,
                             timeout: int = 60) -> Optional[Dict[str, Any]]:
    """Run L3 (always, when called) + L6 (conditional). Returns a plan dict or None.

    Plan shape:
      {axes, chosen_axis, chosen_why, tracks, groups, done_when, cosmic?}
    """
    if not _LLM_OK:
        return None
    user = (
        f"MISSION:\n{task}\n\n"
        + (f"CONTEXT:\n{str(context)[:1500]}\n\n" if context else "")
        + "Decompose per your protocol. JSON only."
    )
    res = await _llm_call_json(_L3_SYSTEM, user, model=model, base_url=base_url,
                               api_key=api_key, timeout=timeout, temperature=0.2)
    if not (res.get("ok") and isinstance(res.get("json"), dict)):
        return None
    plan = res["json"]
    tracks = plan.get("tracks") or []
    if not isinstance(tracks, list) or not tracks:
        return None
    plan["groups"] = _topo_groups(tracks)

    if qualifies_for_cosmic(task):
        cosmic = await _cosmic_view(task, plan, model, base_url, api_key, timeout)
        if cosmic:
            plan["cosmic"] = cosmic
    return plan


# ──────────────────────────────────────────────────────────────────────────────
# L6 Cosmic Mind prompt
# ──────────────────────────────────────────────────────────────────────────────
_L6_SYSTEM = """You are L6 COSMIC MIND of SkynetClaw. The mission has a long horizon,
is a system design, or sits under macro forces. Analyse the PLAN across scenarios
and observer frames. Find moves that hold no matter which future arrives.

Output STRICT JSON:
{
  "observer": "builder|institution|capital_market|civilization|retail_user",
  "regime_variables": ["forces that, if they shift, change everything"],
  "scenarios": [
     {"name":"...","prob":0.5,"trigger":"...","outcome_10y":"...","early_warning":"..."}
  ],
  "no_regret_moves": ["actions that work across ALL scenarios"],
  "cosmic_close": "one navigational sentence for the decade"
}
Give exactly 3 scenarios. Probabilities sum to ~1.0."""


async def _cosmic_view(task: str, plan: Dict[str, Any], model: str,
                       base_url: str, api_key: str, timeout: int) -> Optional[Dict[str, Any]]:
    user = (
        f"MISSION:\n{task}\n\n"
        f"CHOSEN PLAN AXIS: {plan.get('chosen_axis','')}\n"
        f"TRACKS: {', '.join(str(t.get('task',''))[:60] for t in (plan.get('tracks') or [])[:6])}\n\n"
        "Run the Cosmic Mind protocol on this plan. JSON only."
    )
    res = await _llm_call_json(_L6_SYSTEM, user, model=model, base_url=base_url,
                               api_key=api_key, timeout=timeout, temperature=0.25)
    if res.get("ok") and isinstance(res.get("json"), dict):
        return res["json"]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Render — system prompt that REPLACES linear "PLAN: 1) 2) 3)"
# ──────────────────────────────────────────────────────────────────────────────
def format_compound_for_agent(plan: Dict[str, Any]) -> str:
    if not plan:
        return ""
    L: List[str] = []
    L.append("## COMPOUND PLAN (L3 Compound Mind — chosen path, NOT linear stepping)")
    chosen = plan.get("chosen_axis", "")
    why = plan.get("chosen_why", "")
    if chosen:
        L.append(f"Chosen approach: **{chosen}** — {why}")
    rejected = [a for a in (plan.get("axes") or []) if a.get("name") != chosen]
    if rejected:
        L.append("Considered & set aside: " + "; ".join(
            f"{a.get('name','?')} ({a.get('tradeoff','')[:60]})" for a in rejected[:3]))

    groups = plan.get("groups") or [plan.get("tracks") or []]
    L.append("\n## WORK TRACKS (execute by DEPENDENCY, not by number)")
    for gi, grp in enumerate(groups, 1):
        tag = "independent — run back-to-back, no re-plan between them" if len(grp) > 1 else "single track"
        if gi > 1:
            tag = "needs the group(s) above"
        L.append(f"Group {gi} ({tag}):")
        for t in grp:
            dep = t.get("depends_on") or []
            dep_s = f"  ⟵ after {', '.join(str(d) for d in dep)}" if dep else ""
            L.append(f"  - [{t.get('id','?')}] {t.get('task','')}  "
                     f"(owner: {t.get('operative','THE EXECUTOR')}){dep_s}")

    dw = plan.get("done_when", "")
    if dw:
        L.append(f"\n## DONE_WHEN (GTS-1 — all must hold)\n  {dw}")

    cosmic = plan.get("cosmic")
    if isinstance(cosmic, dict) and cosmic.get("scenarios"):
        L.append("\n## COSMIC VIEW (L6 — long horizon)")
        L.append(f"Observer: {cosmic.get('observer','')} | "
                 f"Regime: {', '.join(cosmic.get('regime_variables', [])[:3])}")
        for s in (cosmic.get("scenarios") or [])[:3]:
            L.append(f"  • {s.get('name','?')} [{s.get('prob','?')}] "
                     f"trigger: {str(s.get('trigger',''))[:60]} → {str(s.get('outcome_10y',''))[:70]}")
        nrm = cosmic.get("no_regret_moves") or []
        if nrm:
            L.append("No-regret moves: " + "; ".join(str(m)[:70] for m in nrm[:3]))
        if cosmic.get("cosmic_close"):
            L.append(f"Close: {cosmic.get('cosmic_close')}")

    L.append(
        "\nRULES: This COMPOUND PLAN is your plan — do NOT emit a 'PLAN: 1) 2) 3)' line. "
        "Execute tracks respecting dependencies; run tracks in the same group consecutively "
        "with no re-planning. Begin the first track's tool call immediately. "
        "Reply TASK_COMPLETE only when DONE_WHEN holds."
    )
    return "\n".join(L)


# ──────────────────────────────────────────────────────────────────────────────
# Compact one-liner for captured_plan (so the loop's memory shows the path)
# ──────────────────────────────────────────────────────────────────────────────
def plan_oneliner(plan: Dict[str, Any]) -> str:
    if not plan:
        return ""
    tracks = plan.get("tracks") or []
    return (f"[{plan.get('chosen_axis','compound')}] " +
            " | ".join(f"{t.get('id','?')}:{str(t.get('task',''))[:40]}" for t in tracks[:8]))


# ──────────────────────────────────────────────────────────────────────────────
# Offline self-test (no LLM) — exercises gates + topo + render
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

    print("=== gate tests ===")
    for t in ["what time is it",
              "build a system to ingest, clean, and chart 5 years of sales data",
              "ออกแบบระบบ multi-agent แล้ววางแผนกลยุทธ์ระยะยาว 5 ปี",
              "read config.json"]:
        print(f"  compound={should_run_compound(t)!s:5} cosmic={qualifies_for_cosmic(t)!s:5}  {t[:50]}")

    print("\n=== topo + render (mock plan) ===")
    mock = {
        "tokens": ["ingest", "clean", "chart", "sales"],
        "axes": [
            {"name": "batch-ETL", "approach": "load all then transform", "tradeoff": "simpler, higher memory"},
            {"name": "stream", "approach": "incremental", "tradeoff": "scales, more moving parts"},
        ],
        "chosen_axis": "batch-ETL",
        "chosen_why": "dataset fits memory; simplest path to the chart",
        "tracks": [
            {"id": "T1", "task": "ingest CSVs into a dataframe", "operative": "THE EXECUTOR", "depends_on": []},
            {"id": "T2", "task": "find a charting lib", "operative": "THE SCOUT", "depends_on": []},
            {"id": "T3", "task": "clean + dedupe", "operative": "THE EXECUTOR", "depends_on": ["T1"]},
            {"id": "T4", "task": "render chart", "operative": "THE EXECUTOR", "depends_on": ["T3", "T2"]},
            {"id": "T5", "task": "verify against DONE_WHEN", "operative": "THE AUDITOR", "depends_on": ["T4"]},
        ],
        "done_when": "chart.png exists and shows 5y trend from the cleaned data",
        "cosmic": {
            "observer": "builder",
            "regime_variables": ["data volume growth"],
            "scenarios": [
                {"name": "stable", "prob": 0.6, "trigger": "volume flat", "outcome_10y": "batch keeps working", "early_warning": "runtime > 5min"},
                {"name": "explode", "prob": 0.3, "trigger": "10x volume", "outcome_10y": "must stream", "early_warning": "OOM"},
                {"name": "deprecate", "prob": 0.1, "trigger": "source dies", "outcome_10y": "re-source", "early_warning": "schema drift"},
            ],
            "no_regret_moves": ["keep ingest decoupled from transform"],
            "cosmic_close": "build batch now, keep a clean seam to stream later",
        },
    }
    mock["groups"] = _topo_groups(mock["tracks"])
    print(f"groups: {[[t['id'] for t in g] for g in mock['groups']]}")
    print("\n" + format_compound_for_agent(mock))
    print("\noneliner:", plan_oneliner(mock))
    print("\n=== self-test OK ===")
