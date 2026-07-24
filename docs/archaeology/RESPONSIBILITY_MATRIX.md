# Responsibility Matrix — V1 responsibility → current owner(s)

> Compares **responsibilities, not features** (per mission Step 4). For each V1
> responsibility: who owns it today, and whether ownership is *single* or *scattered*.
> Tags: SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.

| V1 responsibility | V1 owner | Today's owner(s) (evidence) | Ownership | Tag |
|---|---|---|---|---|
| Decide **who handles a task** | `CompoundMind.route` (1) | `skills_auto_router` + `runtime_router` + `skynetclaw_router` + `discovery.route` + `main._select_tools_for_task` | **scattered (≥5)** | SUPPORTED |
| **Plan** the work | `ContentSkill.plan` (static outline) | `compound_mind` (L3 axes) + `agentic_workflow` (plan phase) + `workflow/` engine + `deliberation_briefing` + agent-loop PLAN marker | **scattered** | SUPPORTED |
| **Produce** the output | `*Skill.compose/analyze/render` | `main.agent_run` loop + tools (`BUILTIN_TOOLS`) + `skills/*/SKILL.md` | evolved (loop+tools) | SUPPORTED |
| **Critique / evaluate** | `Evaluator.self_critique` (1, rule-based) | council **Skeptic/Auditor** + `shadow_gate` + `calibration` + `decision` + `completion_evidence` + `self_debug` | **scattered (≥6)** | SUPPORTED (existence) |
| **Refine** the draft | `Evaluator.refine` (1) | agent-loop iteration + `agentic_workflow.reflect` + `lesson_synthesis` | scattered | LIKELY |
| **Guard truth / flag claims** | `FactFlagger` (1, advisory) | `shadow_gate` LIVE-DATA gate (enforcing) + `skynetclaw_codex` classify-claims + epistemic suite (`first_principles/belief_revision/theory/experiment/causal`) | **expanded + enforcing** | SUPPORTED (existence); lineage LIKELY |
| **Voice / brand style** | `StyleProfile`+`SEED_BRANDS` (1, numeric) | `prompts/SOUL.md·IDENTITY.md·USER.md` (prose persona) + skills | superseded (prose) | SUPPORTED |
| **Remember** | `Memory` (1, in-proc) | `house_state` + `lesson_synthesis` + `calibration` + `belief_revision` + `institutional_db` + `chat_history.db` + `agent_memory.json` + `metacognition` | **scattered (≥8)** | SUPPORTED |
| **Reason to first principles / truth** | *(seed only: FactFlagger)* | `skynetclaw_codex` (deconstruct/axioms) + `first_principles.py` (epistemic engine) | **new lineage** | SUPPORTED |
| **Bound stochasticity** | `LLMBridge` (1, sole stochastic point) | `llm_adapter`+`runtime_kernel`+`_llm_stream` (many call-sites) | evolved; invariant lost | SUPPORTED |
| **Persist state** | *(none — in-memory)* | SQLite (`skynerclaw.db`, `chat_history.db`, `institutional_db`, WAL) + JSON stores | new (persistence) | SUPPORTED |
| **Govern / permit actions** | *(none)* | `governance.py` GPS-2 + `shadow_gate` + `os_permissions` + Constitution seed | new | SUPPORTED |

## The six probe mappings requested (Step 4)
- **ContentSkill →** prompt-skills (`skills/*/SKILL.md`) + the agent loop + tools. *(SUPPORTED)*
- **Evaluator →** *no single successor*: split across Skeptic/Auditor, `shadow_gate`, `calibration`, `decision`, `completion_evidence`. *(SUPPORTED existence / split LIKELY)*
- **CompoundMind →** name kept, role changed to L3/L6 **planning**; original routing role scattered to the routers. *(SUPPORTED)*
- **Memory →** *no single successor*: 8+ stores (missions/lessons/calibration/beliefs/DBs). *(SUPPORTED)*
- **FactFlagger →** `shadow_gate` (enforcing) + `skynetclaw_codex` + epistemic suite. *(SUPPORTED existence; lineage LIKELY)*
- **Route() →** 5+ routers. *(SUPPORTED)*

## Reading of the matrix (LIKELY)
V1 gave **one owner per responsibility** (one Evaluator, one Memory, one route, one loop).
The current system has **many owners per responsibility** for evaluation, memory, routing,
and planning. This is the central archaeological finding and the basis of
[DUPLICATION_AUDIT](DUPLICATION_AUDIT.md).
