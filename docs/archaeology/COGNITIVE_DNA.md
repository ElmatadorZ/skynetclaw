# Cognitive DNA — Genesis V1 design intent vs implementation

> Mission Step 3: infer V1's original design philosophy, separating **Design Intent**
> (what the artifact aspired to) from **Implementation** (what the code actually did).
> Then: what DNA *survived*, and what *should never return*. Tags:
> SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.

## 1. The assumptions V1 encoded
| Assumption | Design Intent (docstring) | Implementation (code) | Gap |
|---|---|---|---|
| **Single stochastic point** | "Deterministic core. LLMBridge is the only stochastic component." (SUPPORTED) | True in V1 — all logic deterministic; only `LLMBridge.generate` varies. (SUPPORTED) | none in V1 |
| **Reflection** | "Resonance Loop … with self-critique" (SUPPORTED) | Only the **Content** path critiques/refines; Finance/Marketing/Sales do not. (SUPPORTED) | intent > impl |
| **Grounding** | loop = "Plan → **Ground** → Compose…" (SUPPORTED) | **No grounding step exists.** (SUPPORTED) | intent only |
| **Truth** | "Detect claims that require references; mark for human review" (SUPPORTED) | Keyword flags, advisory, never verifies/blocks. (SUPPORTED) | advisory only |
| **Multi-agent** | "ensembles of specialized agents" (SUPPORTED) | One agent per task, static route; no deliberation/ensemble voting. (SUPPORTED) | intent > impl |
| **Memory** | resonance/learning implied | `Memory.note` writes a one-line trace; never read back into reasoning. (SUPPORTED) | vestigial |
| **Planning** | per-domain plans | Only a **static** 5-bullet outline (Content); others skip planning. (SUPPORTED) | shallow |
| **Interpretable skills** | "pure functions with interpretable outputs" (SUPPORTED) | True — skills are deterministic pure fns. (SUPPORTED) | honored |
| **Domain coupling** | four business verticals | `Domain` enum hardcodes Content/Finance/Marketing/Sales into the type system. (SUPPORTED) | rigid |

## 2. The true DNA (what V1 *was*, distilled) — LIKELY
1. **Deterministic-core / thin-stochastic-shell.** Cognition = interpretable code;
   the LLM is a bounded I/O device, not the reasoner.
2. **One owner per responsibility.** Exactly one Evaluator, one Memory, one route, one loop.
3. **Human-in-the-loop truth.** The machine *flags*; the human *judges*.
4. **Production-as-cognition.** The purpose is to *produce* branded artifacts
   (content/analysis/playbooks), not to *establish truth*.
5. **Reflection as aspiration, grounding as vaporware.** The loop names more than it runs.

## 3. What survived into SkynetClaw (SUPPORTED unless noted)
- **The loop shape** Plan→…→Reflect (→ `agentic_workflow` 4-phase). *(EVOLVED)*
- **Interpretable pure blocks** (→ tools; deterministic `news_report`, `shadow_gate` parsing). *(partial)*
- **The truth-flagging instinct** (→ `shadow_gate` + epistemic suite). *(EVOLVED, now enforcing)*
- **Persona/brand voice** (→ `prompts/*`, skills). *(SUPERSEDED)*

## 4. What DIED (SUPPORTED)
- **"One stochastic point."** LLM calls now pervade council/planning/reflection — the
  deterministic-core invariant is gone. *(major DNA loss)*
- **"One owner per responsibility."** Evaluation and memory are now scattered
  (see DUPLICATION_AUDIT).
- **The numeric StyleProfile** (science/story ratios). *(REMOVED)*
- **The `Domain` business-vertical coupling.** *(REMOVED — replaced by open tasks + skills)*

## 5. What should never return (Red-Team judgment)
- **`Domain`-as-a-type business verticals** baked into the core — coupled cognition to
  four industries; correctly superseded by general skills. **Should not return.** *(SUPPORTED reasoning)*
- **Magic-number style ratios** (`science_ratio=0.45` …) — un-evidenced pseudo-metrics
  presented as configuration. **Should not return** without evidence. *(LIKELY)*
- **Truth-as-keyword-flagging as the *only* mechanism** — advisory keyword hits are too
  weak to be the truth layer; the epistemic suite/shadow_gate is the correct successor.
  The *instinct* should stay; the *implementation* should not return. *(LIKELY)*
- **Aspirational loop stages that don't run** (V1's phantom "Ground") — naming a stage
  without implementing it. **Should never return.** *(SUPPORTED — it caused the very
  grounding gap re-discovered in the current Reality-Awareness audit.)*

## 6. The one-line DNA verdict (LIKELY)
> Genesis V1's DNA was **"interpretable deterministic cognition that produces branded
> artifacts, with truth deferred to humans."** SkynetClaw kept the *loop* and the
> *truth-instinct*, inverted the *determinism* (now stochastic-throughout), and shattered
> the *single-owner* discipline into many subsystems. The healthiest surviving gene is
> the **truth-flagging instinct**; the most damaged is **single-owner determinism**.
