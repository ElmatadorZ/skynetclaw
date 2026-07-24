# Genesis Mind V1 — Architecture Archaeology

> Recovered from the V1 artifact (`genesis_mind_compound.py`, provided as historical
> input). Confidence tags: **SUPPORTED** (direct in V1 source) · **LIKELY** · **SPECULATIVE** · **UNKNOWN**.
> This recovers *what V1 was* — not what it should be.

## 1. Core concepts (SUPPORTED — all present in V1 source)
| Concept | V1 construct | Role |
|---|---|---|
| Orchestrator | `CompoundMind` (route + agent ensemble) | pick a domain agent, run it, note memory |
| Cognitive loop | "Resonance Loop" in `Agent.act` (Content path) | Plan → Compose → Evaluate(self-critique) → Refine → FactFlag |
| Agents | `Agent` × 4 personas | Content Sage / Market Analyst / Growth Strategist / Sales Coach |
| Skills | `ContentSkill/FinanceSkill/MarketingSkill/SalesSkill` | pure functional blocks (plan/compose/analyze/render) |
| Evaluation | `Evaluator.self_critique` + `Evaluator.refine` | rule-based critique → LLM refine |
| Fact model | `FactFlagger` | keyword triggers → mark claims for **human review** |
| Style model | `StyleProfile` + `SEED_BRANDS` | brand voice via `science_ratio/story_ratio/tone/signature` |
| Memory | `Memory` (long_term dict + short_term list, cap 50) | `remember/recall/note` |
| Routing | `CompoundMind.route` | `Domain` enum → agent name (static map) |
| LLM boundary | `LLMBridge` | **the only stochastic component** ("Deterministic core") |
| Task contract | `TaskSpec` / `Result` / `Domain` | typed request/response |

## 2. The cognitive loop (SUPPORTED — `Agent.act`, Content branch)
```
TaskSpec ─▶ route(Domain) ─▶ Agent
             │
             ▼   (Content path = the ONLY branch with a full loop)
   ContentSkill.plan(spec, StyleProfile)     # Plan   (static 5-part outline)
        └▶ ContentSkill.compose(...LLM)       # Compose
             └▶ Evaluator.self_critique(draft) # Evaluate (rule-based: length, risk-disclosure)
                  └▶ Evaluator.refine(...LLM)  # Refine  (only if issues)
                       └▶ FactFlagger.flag()   # FactFlag (keyword → human review)
   Finance/Marketing/Sales = analyze/compute → render (NO critique/refine loop)
   CompoundMind.run ─▶ Memory.note("<agent> handled <domain>: <goal>")
```
**SUPPORTED note:** the docstring advertises "Plan → Ground → Compose → Evaluate → Refine",
but **"Ground" is not implemented** — no grounding/retrieval step exists in code. The
loop is Plan→Compose→Evaluate→Refine. (Evidence: `Agent.act` has no grounding call.)

## 3. Sub-models
- **Memory model (SUPPORTED):** in-process, non-persistent. `long_term` = flat dict (key→value),
  `short_term` = rolling list (cap 50). No embeddings, no retrieval, no persistence.
- **Agent model (SUPPORTED):** static personas bound to a `skill` instance + `brand_bias`.
  Single-orchestrator, single-agent-per-task (no multi-agent deliberation).
- **Evaluation model (SUPPORTED):** deterministic rule critique (`len<200`, missing
  risk-disclosure) → numeric `score = 10 - 2·issues` → conditional LLM refine.
- **Style model (SUPPORTED):** two seed brands with numeric `science_ratio/story_ratio`
  + tone/signature/guardrails; injected as prompt text (not enforced structurally).
- **Fact model (SUPPORTED):** 13 Thai/English keyword triggers (%, เพิ่มขึ้น, ผลตอบแทน…)
  → returns hit list to **flag for human**, never blocks or verifies.
- **Routing model (SUPPORTED):** pure static `Domain → agent-name` map; no scoring, no LLM.

## 4. Architecture diagram (SUPPORTED)
```
                        ┌───────────────── GenesisMind ─────────────────┐
   TaskSpec ─▶ CompoundMind.run ─▶ route(Domain) ─▶ Agent(persona+skill) │
                    │                                     │              │
                    │                        ┌────────────┴───────────┐  │
                    │                        │ Skill (pure fn)         │  │
                    │                        │  plan/compose/analyze   │  │
                    │                        └───────────┬────────────┘  │
                    │        ┌── Evaluator (critique/refine) ─┐ (Content) │
                    │        └── FactFlagger (human-review flags) ─┘      │
                    │                        │                            │
                    ▼                        ▼                            │
                 Memory.note            LLMBridge (only stochastic)       │
                        └───────────────────────────────────────────────┘
   Cross-cutting: StyleProfile/SEED_BRANDS · TaskSpec/Result/Domain · deterministic core
```

## 5. What the artifact explicitly claims about itself (SUPPORTED — docstring/comments)
- "Deterministic core. LLMBridge is the only stochastic component."
- "CompoundMind: routers + ensembles of specialized agents."
- "Resonance Loop: Plan → Ground → Compose → Evaluate → Refine (with self-critique)."
- "Fact Flags: Detect claims that require references; mark for human review."
- "Style Engine: Switch voice (Alternative Slowbar / Money Atlas / Neutral)."
- "Tools/Skills: Reusable, pure functions with interpretable outputs."

## 6. Immediate archaeological observations (LIKELY)
- V1 is a **business-vertical compound** (Content/Finance/Marketing/Sales baked into a
  `Domain` enum) — cognition is *coupled to four business domains* at the type level.
- The **only true reflective loop is in Content**; the other three domains are
  compute-then-render (no self-critique). Reflection was *aspirational, not uniform*.
- Truth handling is **advisory** (flag for humans), not enforced.
