# Evolution Map — Genesis V1 → SkynetClaw (current)

> Per-component classification: **UNCHANGED · EVOLVED · SPLIT · MERGED · REMOVED · SUPERSEDED**.
> Evidence points to real files in the current repo. Tags: SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.
> Naming fact (SUPPORTED): a grep for the V1 identifiers `CompoundMind, Evaluator,
> self_critique, FactFlagger, StyleProfile, SEED_BRANDS, brand_bias, Resonance` returns
> **zero matches** in the current backend — no V1 construct survived *by name*. Survival is
> by *responsibility*, traced below.

| V1 component | Verdict | Where it went (evidence) | Tag |
|---|---|---|---|
| `CompoundMind` (route + domain-agent ensemble) | **EVOLVED (name reused, role changed)** | `compound_mind.py` now = "L3 Compound Mind + L6 Cosmic Mind" — multi-axis **planning/decomposition**, not domain routing (`compound_mind.py:1-25`). Its docstring states the protocol "lived only in skill PROMPT TEXT and a separate workflow endpoint" before being re-wired. | SUPPORTED |
| Domain-agent **routing** (`route(Domain)→agent`) | **SPLIT / DUPLICATED** | ≥5 routers now: `discovery.route`, `runtime_router.route/route_with_registry`, `skynetclaw_router`, `skills_auto_router`, `knowledge_frontier.route_source`, plus `main._select_tools_for_task`. | SUPPORTED |
| "Resonance Loop" (Plan→Compose→Evaluate→Refine) | **EVOLVED** | `agentic_workflow.py` = 4-phase **comprehend→plan→execute→reflect** (boot log; `reflect` present). Production loop = `main.agent_run` step loop. | SUPPORTED |
| `Agent` personas (Content Sage / Market Analyst / Growth Strategist / Sales Coach) | **SUPERSEDED** | 14-agent council organized by **cognitive role** not business domain (`system_graph.AGENT_ROSTER`: elite_commander, atlas, analyst, strategist, skeptic, forecaster, governor, sentinel, architect, auditor, scout, storyteller, concierge, executor). | SUPPORTED |
| `*Skill` **code** blocks (pure functions) | **SUPERSEDED** | Skills are now **prompt folders** `skills/*/SKILL.md` + `skills_auto_router.py`, plus 50 `BUILTIN_TOOLS`. Cognition moved from Python fns → prompt+tools. | SUPPORTED |
| `Evaluator` (self_critique + refine) | **SPLIT** | Critique/eval scattered: `calibration.py` (confidence), council **Skeptic/Auditor** (`agent_council.py`), `skynetclaw_meta.shadow_gate` (anti-hallucination/anti-loop), `decision.py`, `completion_evidence.py`, `self_debug.py`. | SUPPORTED (existence); split=LIKELY |
| `FactFlagger` (keyword → human review) | **SUPERSEDED / EVOLVED** | Truth handling is now enforced + expanded: `shadow_gate` LIVE-DATA gate (blocks writes lacking live data), `skynetclaw_codex` (classify-claims/axioms/deconstruct), and an **epistemic suite**: `first_principles.py, belief_revision.py, theory.py, experiment.py, causal.py, unknowns.py, curiosity.py, paradigm.py, research_agenda.py, calibration.py`. | SUPPORTED (existence); lineage=LIKELY |
| `StyleProfile` / `SEED_BRANDS` (science/story ratio, brand voice) | **REMOVED as a structured engine; SUPERSEDED by prose** | No `StyleProfile/SEED_BRANDS` anywhere (grep=0). "Money Atlas"/brand survives only as **persona prose** (`prompts/SOUL.md, IDENTITY.md, USER.md`) and **skills** (e.g. money-atlas skill). The numeric style-ratio mechanism is gone. | SUPPORTED |
| `Memory` (dict + list, in-proc, non-persistent) | **SPLIT + EVOLVED (persistent)** | Fragmented into persistent stores: `house_state.py` (missions), `lesson_synthesis.py`, `calibration.py`, `belief_revision.py`, `institutional_db.py`, `chat_history.db`, `agent_memory.json`, `metacognition.py`. | SUPPORTED |
| `LLMBridge` (single stochastic point; deterministic core) | **EVOLVED; DNA partially LOST** | `llm_adapter.py` + `runtime_kernel.py` + `connections` + `main._llm_stream` = multi-provider runtime. But the "**deterministic core**" invariant is **no longer system-wide** — stochastic LLM calls pervade cognition (council, planning, reflection). Determinism survives only in narrow gates (`shadow_gate` parsing, `news_report.py`). | SUPPORTED |
| `TaskSpec / Result / Domain` (typed contract) | **SUPERSEDED** | `Mission`/`house_state`, `AgentReq/ChatReq` (`main.py`), workflow_runs. `Domain` enum (4 verticals) is gone — replaced by open-ended tasks + skills. | SUPPORTED |
| "Compound / Cosmic Mind" *protocol* | **MERGED into the loop** | Per `compound_mind.py` docstring: previously duplicated across skill prompt text + a workflow endpoint; now merged into the live `agent_run` pre-step analysis. | SUPPORTED |

## Summary of verdicts
- **UNCHANGED:** none by name; the *idea* of a single-orchestrator loop persists only loosely.
- **EVOLVED:** the loop (Resonance→4-phase), CompoundMind (routing→planning), LLMBridge, Memory (→persistent).
- **SPLIT:** routing, evaluation, memory — each became *many* subsystems (see [DUPLICATION_AUDIT](DUPLICATION_AUDIT.md)).
- **SUPERSEDED:** domain agents→council roles, code-skills→prompt-skills, StyleProfile→prose, FactFlagger→epistemic suite.
- **REMOVED:** the numeric style-ratio engine; the `Domain`-coupled business verticals as core types.
- **MERGED:** the Compound/Cosmic protocol back into the run loop.
- **DNA LOST (flag):** "deterministic core, one stochastic point" — see [COGNITIVE_DNA](COGNITIVE_DNA.md).
