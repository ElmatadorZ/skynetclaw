"""
agent_council.py — L5 Six Specialists (Skynet blueprint)
==========================================================
Per ElmatadorZ Secret OS L5 + the shared SKYNET_GENESIS_MASTERPIECE pipeline,
six specialist agents critique a task from independent angles BEFORE
execution. Each returns a focused perspective; together they form a brief
that catches what one mono-perspective would miss.

Six roles:

  Analyst     — facts + data gaps + Known/Inferred/Unknown
  Strategist  — leverage + asymmetry + which move compounds
  Skeptic     — fatal assumption + what breaks the plan
  Forecaster  — probability view + 2 early-warning signals
  Executor    — Stop/Start/Continue + next concrete move
  Storyteller — hook + metaphor + audience framing

Why six (and not one big LLM call)? Each role pulls in a different attention
pattern. One call cannot be Analyst AND Skeptic with full force — the model
averages. Six calls cost ~6× tokens but produce 6× the diverse signal.

Used at L5 of the workflow when complexity ≥ "complex" or user opts in.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import asyncio
import datetime as _dt
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Optional

from agentic_workflow import _llm_call_json, _to_list  # reuse helpers


# ──────────────────────────────────────────────────────────────────────────────
# Council Wiretap (Phase 2A) — make deliberation observable
# ──────────────────────────────────────────────────────────────────────────────
# A short, role-appropriate status label for what each member is doing WHILE it
# runs. This is NOT new reasoning — every label describes an activity that is
# genuinely happening (that role's LLM call is in flight). Wiring is opt-in via
# an on_event callback; when None the council behaves exactly as before.
_ROLE_VERB: Dict[str, str] = {
    "ANALYST":     "reviewing evidence",
    "STRATEGIST":  "forming options",
    "SKEPTIC":     "testing assumptions",
    "FORECASTER":  "estimating risk",
    "EXECUTOR":    "deciding next move",
    "STORYTELLER": "composing narrative",
}

# Optional callback shape: fn({"type", "agent", "message", "timestamp"}) -> None
OnEvent = Optional[Callable[[Dict[str, Any]], None]]


def _wiretap(on_event: OnEvent, etype: str, agent: str, message: str,
             source_field: str = "") -> None:
    """Emit ONE wiretap event (best-effort). No-op when on_event is None, so the
    council has ZERO behavioural change when the wiretap is not wired.

    source_field: present ONLY on Phase-2B reasoning events — the exact JSON
    field the verbatim message was pulled from (provenance). Activity events
    (Phase 2A) omit it."""
    if on_event is None:
        return
    try:
        evt = {
            "type": etype,
            "agent": agent,
            "message": message,
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        if source_field:
            evt["source_field"] = source_field
        on_event(evt)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Reasoning Stream (Phase 2B) — VERBATIM extraction from each member's own JSON
# ──────────────────────────────────────────────────────────────────────────────
# FIXED schema map ONLY: (json field path) -> reasoning event type. The message
# is ALWAYS the verbatim string value at that path — never paraphrased, never
# summarised, never generated. If the field is absent/empty, nothing is emitted.
# Every emitted event carries source_field for provenance. The field->type map
# is static structural metadata, not per-content interpretation.
_REASONING_MAP: Dict[str, List[tuple]] = {
    # (field_path, reasoning_type, is_list)
    "ANALYST": [
        ("known",        "reasoning_evidence",       True),   # verifiable facts
        ("inferred",     "reasoning_hypothesis",     True),   # derived assumptions
        ("unknown",      "reasoning_challenge",      True),   # gaps
        ("data_gaps",    "reasoning_challenge",      True),
    ],
    "STRATEGIST": [
        ("leverage_point",   "reasoning_recommendation", False),
        ("asymmetric_bet",   "reasoning_recommendation", False),
        ("compounding_play", "reasoning_recommendation", False),
    ],
    "SKEPTIC": [
        ("fatal_assumption",        "reasoning_challenge", False),
        ("counter_evidence_to_seek","reasoning_challenge", True),
        ("rebuild_trigger",         "reasoning_challenge", False),
        ("verdict",                 "reasoning_revision",  False),
    ],
    "FORECASTER": [
        ("scenario",               "reasoning_hypothesis",  False),
        ("base_case.outcome",      "reasoning_hypothesis",  False),
        ("positive_regime.outcome","reasoning_hypothesis",  False),
        ("negative_regime.outcome","reasoning_hypothesis",  False),
        ("early_warning_1",        "reasoning_observation", False),
        ("early_warning_2",        "reasoning_observation", False),
    ],
    "EXECUTOR": [
        ("start",    "reasoning_recommendation", False),
        ("stop",     "reasoning_recommendation", False),
        ("continue", "reasoning_recommendation", False),
    ],
    "STORYTELLER": [
        ("hook", "reasoning_observation", False),
    ],
}


def _dig(jd: Dict[str, Any], path: str) -> Any:
    """Follow a dotted field path. Returns None if any hop is missing."""
    cur: Any = jd
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _extract_reasoning(agent: str, jd: Dict[str, Any]) -> List[tuple]:
    """Return [(reasoning_type, source_field, verbatim_message)] pulled VERBATIM
    from a member's actual JSON. Emits ONLY string values that genuinely exist.
    Never paraphrases, never invents. Long values are truncated (still verbatim
    prefix); absent/non-string/empty values are skipped (no source_field -> no
    event)."""
    out: List[tuple] = []
    if not isinstance(jd, dict):
        return out
    for field, rtype, is_list in _REASONING_MAP.get(agent, []):
        val = _dig(jd, field)
        if val is None:
            continue
        if is_list:
            items = val if isinstance(val, list) else [val]
            for i, it in enumerate(items):
                if isinstance(it, str) and it.strip():
                    out.append((rtype, f"{field}[{i}]", it.strip()[:240]))
        elif isinstance(val, str) and val.strip():
            out.append((rtype, field, val.strip()[:240]))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Datatype
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class CouncilVerdict:
    analyst:     Dict[str, Any]
    strategist:  Dict[str, Any]
    skeptic:     Dict[str, Any]
    forecaster:  Dict[str, Any]
    executor:    Dict[str, Any]
    storyteller: Dict[str, Any]
    aggregate_recommendation: str
    # M3: the Constitution's binding decision must TRAVEL with the verdict —
    # dropping it here is how the Commander ended up acting on REJECTED advice.
    governance:  Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────────
# Role prompts
# ──────────────────────────────────────────────────────────────────────────────
_ANALYST = """You are the ANALYST member of the SkynetClaw L5 Agent Council.
Your only job: surface facts, label what's known vs inferred vs unknown.
Output STRICT JSON:
{
  "known":      ["verifiable fact 1", ...],          // from the task itself
  "inferred":   ["derived assumption 1 [A:XX%]", ...], // with confidence
  "unknown":    ["data we lack", ...],
  "data_gaps":  ["specific info needed before acting"]
}
Be concrete. No vibes. No advice."""

_STRATEGIST = """You are the STRATEGIST of the L5 Agent Council.
Your only job: name the leverage point. Where does small effort → big result?
Output STRICT JSON:
{
  "leverage_point": "the single highest-leverage move",
  "asymmetric_bet": "where downside is small but upside is large",
  "compounding_play": "the move that pays off again on later tasks",
  "ignore_list":   ["distractions to NOT spend time on"]
}
Sharp not generic. No motivational filler."""

_SKEPTIC = """You are the SKEPTIC of the L5 Agent Council.
Your only job: attack the fatal assumption. Find what would BREAK the plan.
Output STRICT JSON:
{
  "fatal_assumption": "the one belief that, if wrong, collapses everything",
  "counter_evidence_to_seek": ["what would prove the plan wrong"],
  "rebuild_trigger":          "the signal that means STOP and re-plan",
  "verdict": "CONSISTENT" | "FRAGILE" | "REBUILD",
  "dissent": true | false        // true = you formally disagree with where the council is heading
}
A unanimous council every time is a broken council — dissent when you mean it.
You are not negative for its own sake — you save the agent from confident failure."""

_FORECASTER = """You are the FORECASTER of the L5 Agent Council.
Output STRICT JSON:
{
  "base_case":      {"prob": 0.55, "outcome": "..."},
  "positive_regime":{"prob": 0.25, "outcome": "..."},
  "negative_regime":{"prob": 0.20, "outcome": "..."},
  "early_warning_1": "signal that we're heading to negative_regime",
  "early_warning_2": "signal that we're heading to positive_regime",
  "prediction": {                       // your single most FALSIFIABLE claim (Constitution R4)
    "statement":    "one concrete, checkable claim about what will happen",
    "direction":    "up" | "down" | "flat" | "mixed",
    "metric":       "what is being measured",
    "horizon_days": 7 | 30 | 90 | 180,   // prefer 7 for operational claims the House can verify soon
    "invalidation": "the observable condition that proves this claim WRONG",
    "confidence":   0.0-1.0
  }
}
Probabilities must sum to 1.0. Outcomes specific to THIS task. The prediction
block may be written in the task's own language — structure is what matters."""

_EXECUTOR = """You are the EXECUTOR of the L5 Agent Council.
Your only job: turn the council into actionable Stop / Start / Continue.
Output STRICT JSON:
{
  "stop":   "what to NOT do (highest-priority anti-action)",
  "start":  "what to do NEXT (concrete tool call or sub-task)",
  "continue":"what's already on track to keep doing",
  "runtime_decision": "auto" | "ask_user" | "abort"
}
Be operational. Name actual tools where relevant."""

_STORYTELLER = """You are the STORYTELLER of the L5 Agent Council.
Your only job: make the council's findings memorable + shareable.
Output STRICT JSON:
{
  "hook":      "one-line opening that captures the paradox or core tension",
  "metaphor":  "cross-domain analogy that makes it click",
  "audience_frame": "how to communicate this to the user in their language"
}
Use Money Atlas tone: calm, sharp, no shouting."""


# ──────────────────────────────────────────────────────────────────────────────
# Single role caller
# ──────────────────────────────────────────────────────────────────────────────
async def _ask_role(role_system: str, task: str, context: Dict[str, Any],
                     model: str, base_url: str, api_key: str,
                     timeout: int = 45, role_name: str = "",
                     on_event: OnEvent = None) -> Dict[str, Any]:
    """One LLM call for one role. Returns parsed JSON dict (or fallback {})."""
    agent = (role_name or "").upper()
    _wiretap(on_event, "agent_started", agent, "engaged")
    # M2: surface the Historical Brief first (the council reasons WITH its history)
    preamble = ""
    ctx = context
    if isinstance(context, dict) and (context.get("operator_intent") or
                                      context.get("house_mind") or context.get("historical_brief")):
        # OPERATOR INTENT first (what the Operator MEANS), then HOUSE MIND
        # (current shared understanding), then the historical brief.
        if context.get("operator_intent"):
            preamble += str(context["operator_intent"]) + "\n\n"
        if context.get("house_mind"):
            preamble += str(context["house_mind"]) + "\n\n"
        if context.get("historical_brief"):
            preamble += str(context["historical_brief"]) + "\n\n"
        ctx = {k: v for k, v in context.items()
               if k not in ("historical_brief", "house_mind", "operator_intent")
               and not k.startswith("_")}
    user_msg = (
        preamble +
        f"TASK:\n{task}\n\n"
        f"CONTEXT (from prior phases):\n"
        f"{json.dumps(ctx, ensure_ascii=False, indent=2)[:3000]}\n\n"
        "Respond as your role."
    )
    _wiretap(on_event, "agent_thinking", agent, _ROLE_VERB.get(agent, "deliberating"))
    res = await _llm_call_json(role_system, user_msg, model=model,
                                base_url=base_url, api_key=api_key,
                                timeout=timeout, temperature=0.2)
    if res.get("ok") and isinstance(res.get("json"), dict):
        # SYNC: emit each reasoning fact EXACTLY ONCE (single source of truth).
        # reasoning_* is the canonical council reasoning event; every UI surface
        # (seats, chamber, deliberation map, reasoning chain, mission) consumes
        # this same event id. The former agent_* duplicate is removed so the
        # House never emits two events for one fact.
        for _rtype, _sfield, _msg in _extract_reasoning(agent, res["json"]):
            _wiretap(on_event, _rtype, agent, _msg, source_field=_sfield)
        _wiretap(on_event, "agent_completed", agent, "done")
        return res["json"]
    # Fallback: empty role
    _wiretap(on_event, "agent_completed", agent, "done (no JSON)")
    return {"_error": res.get("error", "json parse failed"),
            "_raw": (res.get("text") or "")[:500]}


# ──────────────────────────────────────────────────────────────────────────────
# Public API — run all six in parallel
# ──────────────────────────────────────────────────────────────────────────────
# ── INSTITUTIONAL MEMORY hook — every council run is remembered + archived ──
try:
    import council_memory as _imem
    import deliberation_archive as _iarc
    import extractor as _iext
    _IMEM = True
except Exception as _ie:        # institutional memory optional; never break the council
    _IMEM = False

# M2: the council is briefed with its own graded history BEFORE deliberating
try:
    import deliberation_briefing as _dbrief
    _BRIEF = True
except Exception as _be:
    _BRIEF = False

# M3: the Constitution GOVERNS every verdict (enforce + record minority)
try:
    import governance_engine as _gov
    _GOV = True
except Exception as _ge:
    _GOV = False

# HOUSE MIND: a shared cognitive state every member reads before / updates after
try:
    import house_state as _hstate
    _HSTATE = True
except Exception as _hse:
    _HSTATE = False

# OPERATOR INTENT: the ASK stage — recover what the Operator MEANS from working
# context before the council reasons (short/deictic directives are not ambiguity).
try:
    import operator_intent as _ointent
    _OINTENT = True
except Exception as _oie0:
    _OINTENT = False


def _persist_council(task: str, verdict_dict: Dict[str, Any], model: str) -> None:
    """Persist a council run to the Memory Engine + Deliberation Archive (best-effort)."""
    if not _IMEM:
        return
    try:
        sid = _imem.from_verdict(task, verdict_dict, model=model)
        sess = _imem.get_session(sid) or {}
        _iarc.archive(
            question=task,
            agents=sess.get("participants", []),
            reasoning_summary=str(verdict_dict.get("aggregate_recommendation", ""))[:1500],
            final_verdict=str(verdict_dict.get("aggregate_recommendation", ""))[:500],
            confidence=float(sess.get("confidence", 0.0)),
            predicted_outcome=str((verdict_dict.get("forecaster") or {}))[:400],
            session_id=sid,
        )
        # M1: extract falsifiable predictions → Outcome Clock will review them
        try:
            pids = _iext.record_from_verdict(verdict_dict, session_id=sid)
            if pids:
                print(f"[InstitutionalMemory] extracted {len(pids)} prediction(s) from {sid}")
        except Exception as _xe:
            print(f"[InstitutionalMemory] prediction extraction skipped: {_xe}")
        # M3: the Constitution governs — persist the governance record + minority positions
        if _GOV:
            try:
                _grec = _gov.govern(sid, verdict_dict)
                print(f"[Governance] {_grec['decision']} (score {_grec['governance_score']}) "
                      f"— {len(_grec['minority_positions'])} minority position(s) recorded")
            except Exception as _gpe:
                print(f"[Governance] govern skipped: {_gpe}")
    except Exception as _pe:
        print(f"[InstitutionalMemory] council persist skipped: {_pe}")


async def run_council(task: str, context: Dict[str, Any], model: str,
                       base_url: str = "http://localhost:11434",
                       api_key: str = "", on_event: OnEvent = None) -> CouncilVerdict:
    """
    Spin all six specialists in parallel asyncio.gather.
    Returns CouncilVerdict with each role's perspective + aggregated recommendation.

    on_event (optional): callback invoked with wiretap events
        {type: agent_started|agent_thinking|agent_completed, agent, message, timestamp}
        as each member runs. Default None → zero behavioural change.
    """
    roles = [
        ("analyst",     _ANALYST),
        ("strategist",  _STRATEGIST),
        ("skeptic",     _SKEPTIC),
        ("forecaster",  _FORECASTER),
        ("executor",    _EXECUTOR),
        ("storyteller", _STORYTELLER),
    ]
    # ── M2: BRIEF THE COUNCIL with its own graded history BEFORE deliberation ──
    # Atlas/Analyst/Strategist/Skeptic must enter already informed — never
    # rediscovering learned lessons or repeating disproven reasoning. Best-effort.
    if _BRIEF and isinstance(context, dict) and "historical_brief" not in context:
        try:
            _brief = _dbrief.build_brief(task)
            context = {**context, "historical_brief": _dbrief.format_brief_for_council(_brief),
                       "_brief_meta": {"n_cases": _brief.get("n_cases", 0),
                                       "repeated_errors": len(_brief.get("repeated_errors", []))}}
        except Exception as _bge:
            print(f"[Briefing] generation skipped: {_bge}")
    # ── HOUSE MIND: READ the shared cognitive state BEFORE deliberation ──
    # (consciousness rule). Open/reuse the living state for this directive and
    # inject it so all fourteen members reason as ONE mind, not fourteen.
    _state_id = None
    if _HSTATE and isinstance(context, dict):
        try:
            # OX-H1 IDENTITY SEPARATION: never let an assembled prompt become the
            # mission's question. `task` is the clean directive on the normal path;
            # this guard keeps it clean even if a caller passes a model prompt.
            try:
                import mission_identity as _mid
                _ident = _mid.clean_identity(task) or task
            except Exception:
                _ident = task
            _state_id = _hstate.open_state(_ident)
            _st = _hstate.read_state(_state_id)
            if _st:
                context = {**context, "house_mind": _hstate.format_state_for_council(_st)}
        except Exception as _hre:
            print(f"[HouseMind] read skipped: {_hre}")
    # ── ASK: recover the OPERATOR'S intent from working context (ถาม) ──
    # A short/deictic directive ("ไหนอะ", "ดูดิ", "อันนี้") is resolved against
    # the House's live context (House Mind + recent deliberations) BEFORE the
    # council reasons — so it answers what the Operator MEANS, not the literal
    # words. Only escalated to clarification when recovery confidence is low.
    _intent_meta = None
    if _OINTENT and isinstance(context, dict):
        try:
            _ri = _ointent.from_house(task, path=None)
            context = {**context, "operator_intent": _ointent.format_for_council(_ri)}
            _intent_meta = {"directive": _ri.directive, "intent_type": _ri.intent_type,
                            "recovered_intent": _ri.recovered_intent,
                            "confidence": _ri.confidence,
                            "clarification_need": _ri.clarification_need,
                            "clarification_question": _ri.clarification_question}
        except Exception as _oie:
            print(f"[OperatorIntent] recovery skipped: {_oie}")
    coros = [_ask_role(prompt, task, context, model, base_url, api_key,
                       role_name=name, on_event=on_event)
             for name, prompt in roles]
    results = await asyncio.gather(*coros, return_exceptions=True)
    out: Dict[str, Any] = {}
    for (name, _), res in zip(roles, results):
        if isinstance(res, Exception):
            out[name] = {"_error": f"{type(res).__name__}: {str(res)[:120]}"}
        else:
            out[name] = res

    # Aggregate one-line recommendation
    skeptic_verdict = (out.get("skeptic", {}) or {}).get("verdict", "CONSISTENT")
    exec_decision   = (out.get("executor", {}) or {}).get("runtime_decision", "auto")
    hook            = (out.get("storyteller", {}) or {}).get("hook", "")
    if skeptic_verdict == "REBUILD":
        agg = f"⚠ REBUILD: {(out.get('skeptic',{}) or {}).get('rebuild_trigger','re-plan now')}"
    elif exec_decision == "ask_user":
        agg = "⚑ ASK_USER first — see analyst.data_gaps"
    elif skeptic_verdict == "FRAGILE":
        agg = f"FRAGILE — proceed with caveat. Watch: {(out.get('forecaster',{}) or {}).get('early_warning_1','—')}"
    else:
        agg = hook or "Council CONSISTENT — proceed per executor.start"

    verdict_dict = dict(out)
    verdict_dict["aggregate_recommendation"] = agg
    if _intent_meta is not None:
        verdict_dict["operator_intent"] = _intent_meta   # the recovered ASK (ถาม)
    # ── M3: GOVERN — the Constitution enforces, it does not advise ──
    # A verdict that violates a binding rule is REJECTED before it ships.
    if _GOV:
        try:
            _enf = _gov.enforce(verdict_dict)
            verdict_dict["governance"] = {"decision": _enf["decision"],
                                          "governance_score": _enf["governance_score"],
                                          "violations": _enf["violations"]}
            if _enf["decision"] == _gov.REJECTED:
                _rules = ", ".join(v["rule"] for v in _enf["rejects"])
                agg = f"⚖ GOVERNANCE REJECTED ({_rules}) — fix before acting: " + agg
                verdict_dict["aggregate_recommendation"] = agg
        except Exception as _gee:
            print(f"[Governance] enforce skipped: {_gee}")
    # ── HOUSE MIND: UPDATE the shared state with the verdict (flow: …→update→verdict) ──
    if _HSTATE and _state_id:
        try:
            _hstate.update_from_verdict(_state_id, verdict_dict)
            verdict_dict["house_state_id"] = _state_id
        except Exception as _hue:
            print(f"[HouseMind] update skipped: {_hue}")
    _persist_council(task, verdict_dict, model)   # remember + archive + govern (best-effort)

    return CouncilVerdict(
        analyst=out.get("analyst", {}),
        strategist=out.get("strategist", {}),
        skeptic=out.get("skeptic", {}),
        forecaster=out.get("forecaster", {}),
        executor=out.get("executor", {}),
        storyteller=out.get("storyteller", {}),
        aggregate_recommendation=agg,
        governance=verdict_dict.get("governance"),
    )


_DELIBERATION_HINTS = (
    # Thai
    "ตัดสินใจ", "ควรหรือไม่", "หรือไม่ดี", "ชั่งน้ำหนัก", "ข้อดีข้อเสีย", "คุ้มไหม",
    "ทางเลือก", "เปรียบเทียบ", "กลยุทธ", "ความเสี่ยง", "ทิศทาง", "สภา", "ถกเถียง",
    "วิเคราะห์และตัดสินใจ", "แลกกับ", "trade-off",
    # English
    "should we", "should i", "decide", "decision", "weigh", "pros and cons",
    "tradeoff", "trade off", "strategy", "direction for", "worth it", "council",
    "deliberate", "compare options", "which option", "risk of",
)


def looks_like_deliberation_task(task: str) -> bool:
    """Cheap deterministic gate for the /api/agent/run council auto-route —
    same pattern as task_planner.looks_like_build_task. True when the task is a
    judgement/decision question (weighing, strategy, risk) rather than a
    do-this action. Deliberation earns the council; actions don't wait for it."""
    t = (task or "").strip().lower()
    if len(t) < 20:            # deictic/short commands never need six specialists
        return False
    return any(h in t for h in _DELIBERATION_HINTS)


def format_council_for_agent(verdict: CouncilVerdict) -> str:
    """Render council output as a system message for /api/agent/run."""
    L = [
        "## 🏛️ L5 AGENT COUNCIL (six specialists ran in parallel)",
        "",
        f"### 📊 ANALYST: ",
    ]
    a = verdict.analyst
    if a.get("known"):    L.append(f"  Known:    {', '.join(_to_list(a.get('known'))[:5])[:300]}")
    if a.get("inferred"): L.append(f"  Inferred: {', '.join(_to_list(a.get('inferred'))[:5])[:300]}")
    if a.get("unknown"):  L.append(f"  Unknown:  {', '.join(_to_list(a.get('unknown'))[:5])[:300]}")
    if a.get("data_gaps"):L.append(f"  Gaps:     {', '.join(_to_list(a.get('data_gaps'))[:5])[:300]}")

    s = verdict.strategist
    L.append("\n### 🎯 STRATEGIST:")
    if s.get("leverage_point"):    L.append(f"  Leverage: {s.get('leverage_point')}")
    if s.get("asymmetric_bet"):    L.append(f"  Asym bet: {s.get('asymmetric_bet')}")
    if s.get("compounding_play"):  L.append(f"  Compound: {s.get('compounding_play')}")
    if s.get("ignore_list"):       L.append(f"  Ignore:   {', '.join(_to_list(s.get('ignore_list')))[:200]}")

    k = verdict.skeptic
    L.append("\n### 🪞 SKEPTIC:")
    if k.get("fatal_assumption"):  L.append(f"  Fatal:    {k.get('fatal_assumption')}")
    if k.get("rebuild_trigger"):   L.append(f"  Rebuild if: {k.get('rebuild_trigger')}")
    L.append(f"  Verdict:  {k.get('verdict','—')}")

    f = verdict.forecaster
    L.append("\n### 🔮 FORECASTER:")
    for label, key in [("Base","base_case"),("Pos+","positive_regime"),("Neg-","negative_regime")]:
        c = f.get(key) or {}
        if c.get("outcome"):
            L.append(f"  {label} [{c.get('prob','—')}]: {c.get('outcome','')[:200]}")
    if f.get("early_warning_1"):  L.append(f"  EW1: {f.get('early_warning_1')}")
    if f.get("early_warning_2"):  L.append(f"  EW2: {f.get('early_warning_2')}")

    e = verdict.executor
    L.append("\n### ⚡ EXECUTOR:")
    if e.get("stop"):     L.append(f"  Stop:     {e.get('stop')}")
    if e.get("start"):    L.append(f"  Start:    {e.get('start')}")
    if e.get("continue"): L.append(f"  Continue: {e.get('continue')}")
    L.append(f"  Decision: {e.get('runtime_decision','auto')}")

    st = verdict.storyteller
    L.append("\n### 📖 STORYTELLER:")
    if st.get("hook"):     L.append(f"  Hook:    {st.get('hook')}")
    if st.get("metaphor"): L.append(f"  Metaphor:{st.get('metaphor')}")

    L.append("")
    L.append(f"### 🎯 AGGREGATE: {verdict.aggregate_recommendation}")
    L.append("")
    L.append("Use the council's findings when executing the plan. "
             "If SKEPTIC verdict = REBUILD, re-plan instead of pushing through. "
             "If EXECUTOR.stop is listed, DO NOT do it.")
    return "\n".join(L)


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    print("=== agent_council self-test ===\n")
    print("(needs Ollama running at localhost:11434)")

    async def _t():
        task = "ตัดสินใจว่าควรลงทุนทองเดือนนี้ไหม"
        ctx = {"current_gold_thb_baht": 71300, "user_capital_thb": 100000}
        v = await run_council(task, ctx, model="nemotron3:33b")
        print(f"\nAggregate: {v.aggregate_recommendation}")
        print(f"Skeptic verdict: {(v.skeptic or {}).get('verdict','—')}")
        print(f"Executor decision: {(v.executor or {}).get('runtime_decision','—')}")
        print(f"\nFormatted (preview):")
        msg = format_council_for_agent(v)
        print(msg[:800] + "..." if len(msg) > 800 else msg)

    try:
        asyncio.run(_t())
        print("\n=== self-test OK ===")
    except Exception as e:
        print(f"\n(skipped — {type(e).__name__}: {str(e)[:120]})")
        print("=== module syntax OK ===")
