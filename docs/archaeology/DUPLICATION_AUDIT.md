# Duplication Audit — where the current system rebuilt what V1 already had once

> Mission Step 6: did SkynetClaw accidentally rebuild single V1 responsibilities as
> *multiple* subsystems? For each duplication: **location · reason (inferred) ·
> recommended owner**. **No fixes proposed** (per mission). Tags:
> SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.
>
> Context: this mirrors the **"Kernel Inflation"** risk already recorded in
> `docs/v3/DecisionLog.md` and the **Epic Trust** freeze — so it is not a new claim,
> it is the same pattern seen from the archaeology side.

## D-1 — Multiple routers (SUPPORTED)
- **Location:** `discovery.route`, `runtime_router.route`/`route_with_registry`,
  `skynetclaw_router.py`, `skills_auto_router.py`, `knowledge_frontier.route_source`,
  `main._select_tools_for_task`.
- **Reason (LIKELY):** routing was needed at different layers (skill, runtime, tool,
  source, knowledge) and each was solved locally instead of via one dispatcher.
- **Recommended owner (SPECULATIVE — not a fix):** one dispatch surface; V3 names the
  Runtime Orchestrator + Skill registry as the intended homes.

## D-2 — Multiple evaluators / critics (SUPPORTED existence; overlap LIKELY)
- **Location:** council **Skeptic** + **Auditor** (`agent_council.py`),
  `skynetclaw_meta.shadow_gate`, `calibration.py`, `decision.py`,
  `completion_evidence.py`, `self_debug.py`.
- **Reason (LIKELY):** "is this good/true/done?" got re-answered per subsystem
  (deliberation, anti-hallucination, confidence, decision, completion, self-test).
- **Recommended owner (SPECULATIVE):** V3 Epistemic Kernel + governance gate as the
  evaluation authority; council roles consume, not re-implement.

## D-3 — Multiple memories (SUPPORTED)
- **Location:** `house_state.py`, `lesson_synthesis.py`, `calibration.py`,
  `belief_revision.py`, `institutional_db.py`, `chat_history.db`, `agent_memory.json`,
  `metacognition.py`.
- **Reason (LIKELY):** each cognitive module persisted its own slice; no shared memory
  service. V1 had exactly one `Memory`.
- **Recommended owner (SPECULATIVE):** V3 Knowledge Graph + Memory tiers (design-only).

## D-4 — Multiple planners (SUPPORTED)
- **Location:** `compound_mind.py` (L3 axes), `agentic_workflow.py` (plan phase),
  `workflow/` engine (ir→compiler), `deliberation_briefing.py`, agent-loop PLAN marker.
- **Reason (LIKELY):** planning exists as a prompt-analysis, a workflow phase, a DAG
  compiler, and an inline loop instruction simultaneously.
- **Recommended owner (SPECULATIVE):** one planning stage feeding the execution engine.

## D-5 — Multiple reflection / learning loops (SUPPORTED existence)
- **Location:** `agentic_workflow.reflect`, `metacognition.py`, `lesson_synthesis.py`,
  `belief_revision.py`, `calibration.py`.
- **Reason (LIKELY):** "learn from the run" is implemented several times over different
  stores. V1 had one `self_critique`.
- **Recommended owner (SPECULATIVE):** V3 Reflection Engine (design-only).

## D-6 — Multiple style / persona sources (LIKELY)
- **Location:** `prompts/SOUL.md·IDENTITY.md·USER.md`, `skills/*/SKILL.md`, brand text
  inside `skynetclaw_codex.py`/`metacognition.py`.
- **Reason (LIKELY):** persona/voice is asserted in several prompt sources; V1 had one
  `StyleProfile`.
- **Recommended owner (SPECULATIVE):** a single persona source.

## D-7 — Multiple "mind" protocols (SUPPORTED)
- **Location:** `compound_mind.py` states the Compound/Cosmic protocol previously
  existed **twice** — in skill prompt text *and* a workflow endpoint — before being
  merged into the loop.
- **Reason (SUPPORTED by docstring):** protocol drift between prompt and code.
- **Status:** partially resolved (merged into the loop) per its own docstring.

## Severity reading (LIKELY)
The heaviest duplication is **evaluation (D-2)** and **memory (D-3)** — precisely the two
responsibilities V1 kept singular. This is evidence that growth added *breadth* faster
than it consolidated *ownership*. This audit is descriptive only; consolidation is a
decision for [DECISIONS_REQUIRING_EVIDENCE](DECISIONS_REQUIRING_EVIDENCE.md), not this doc.
