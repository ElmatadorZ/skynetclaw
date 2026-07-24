# Truth Engine — what actually changes when evidence arrives

> For each candidate target, does *new evidence* actually change it? Probed by persistence +
> the "MEASURE ONLY / no behavior change" comments in the live loop. Tags: SUPPORTED /
> LIKELY / UNKNOWN / FALSIFIED.

| Target | Does evidence change it? | Evidence | Tag |
|---|---|---|---|
| **Belief** (theory/axiom/principle) | **NO — not persistently.** Re-derived each run, injected as advisory text, discarded. | belief organs state-writes = 0; `render_brief → cur.append`; belief_revision "no promotion/demotion/correction" | **FALSIFIED** (as a change) |
| **Capability** | **YES.** Positive/negative lift → weight↑/↓ persisted to `capability_weights.json`, re-orders recalled tools. | reinforcement `_STORE`; "reorders/relabels recalled capabilities by weight" | **SUPPORTED** (but = capability, excluded from belief) |
| **Policy** | **NO.** No evidence-driven policy store found; governance/Constitution are static rules, not learned. | no policy-write path in belief organs; Constitution = signed static | **UNKNOWN → LIKELY-none** |
| **Prompt** | **YES — ephemerally.** Briefs are appended to the current run's system prompt. Gone next run (recomputed). | main.py 4653/4666/4679/4692/4706/4719 `cur.append` | **SUPPORTED** (ephemeral only) |
| **Memory** | **NO — for beliefs.** Beliefs/theories persist nowhere; only lessons/capabilities/strategies persist. | belief_timeline writes = 0; only capability_weights + learning_strategies persist | **SUPPORTED** (belief-memory absent) |
| **Weights** | **YES.** capability_weights + learning_strategies are updated by outcome. | reinforcement + metalearning `_STORE` | **SUPPORTED** (weights = capability/strategy) |
| **Knowledge** | **NO — reconstructed each run.** No independent knowledge store; recomputed from logs on demand. | state-writes = 0 across belief organs; live loop recomputes every run | **FALSIFIED** (as persistent knowledge) |
| **Document** | **YES — but human-written.** The durable epistemic record is the docs (archaeology, DecisionLog, KNOWN_RISKS, TRUST_SCOREBOARD), authored by a human, not by the organism. | this doc set; Trust docs | **SUPPORTED** (external, not autonomous) |

## What actually changes when evidence arrives (SUPPORTED)
1. **This run's prompt** gains an advisory brief (ephemeral). 2. **capability_weights** may
nudge (rate-limited). 3. **learning_strategies** may update. 4. An **event count** is emitted
to the bus (`house_sync.publish`), which records that a drift/theory count occurred — the
*count*, not the *content*.

## What does NOT change (FALSIFIED as changeable by evidence)
Belief, theory, axiom, policy, and persistent knowledge. Evidence arrives, is measured,
rendered, and — for everything the earlier reports called "belief" — **discarded.**

## Consequence for the hypothesis
The "operational epistemology" is **operational only for capability weights and learning
strategies** (both excluded from belief by the mission). For **belief/theory/axiom** — the
thing the hypothesis is actually about — evidence changes **nothing that persists.** The
truth engine, as it pertains to *belief*, is **FALSIFIED.**
