# Selective Pressures — WHY the organism mutated

> Archaeology of *cause*, from **historical evidence only** (git chronology + commit
> messages), not from current code layout. Companion to the immutable
> RESPONSIBILITY_EVOLUTION_GRAPH / WORLD_MODEL / ARCHITECTURAL_INVARIANTS.
> Tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN. No redesign, no proposals.
>
> **Evidence base (SUPPORTED):** 136 commits, 2026-06-15 → 2026-07-01 (~16 days).
> Genesis V1 is **not** in this git history (it is an external pasted artifact) — so all
> pre-2026-06-15 evolution is **UNKNOWN from git**. Commit dates reveal 6 bursts:
> 06-15/16 (41 commits), 06-17/18, 06-22/23 (40 commits), 06-24/25, 06-26/29, 06-30/07-01.

## The master pressure (the finding that explains most mutations)
**P-ADD — Additive / non-invasive growth pressure.** The dominant recorded growth method
was *"add a new read-only/additive protocol per capability; do not modify existing
owners."* **Evidence (SUPPORTED):** ≥10 commits tagged verbatim **"(additive, read-only)"**
and many more **"(additive)" / "(read-side)"** across 2026-06-22/23 (OX-LEARNING, OX-CAPABILITY,
OX-TELEMETRY, OX-ATTRIBUTION, OX-REINFORCEMENT, OX-COMPLIANCE, OX-ACQUISITION, OX-METALEARNING,
OX-EXPLORATION, OX-CAUSAL, OX-CURIOSITY, OX-BELIEF-REVISION, OX-FIRST-PRINCIPLE, OX-DECISION,
OX-CONFIDENCE, OX-EXPERIMENT, OX-THEORY, OX-RESEARCH-AGENDA, OX-UNKNOWNS, OX-PARADIGM).
This one policy structurally produces **ownership fragmentation** (each capability → its own
module) and structurally **blocks** anything requiring invasive core surgery.

**P-CONS — Consolidation counter-pressure (weaker, lost most battles).** Evidence (SUPPORTED):
`a9d76f5 "ONE event per fact - single source of truth"`, `bb7c75b OX-INTENT-1 "Unified Intent
Protocol (shared interpretation layer)"`, `3924495 OX-WORKFLOW-ENGINE-1 "single orchestration
layer"`, `6386e78 "eliminate the final shadow state"`. Consolidation won for *events/
orchestration/intent*; it lost for *evaluation/memory/routing/epistemics*.

---

## M-1 — Dispatch: 1 → 5+
- **Responsibility:** decide who/what handles a task.
- **Before:** one static router (Genesis V1 `route(Domain)`).
- **After:** multiple routers (runtime, skill, intent, source, tool).
- **Observed evidence (SUPPORTED):** `6a17cf5 OX-RUNTIME-DISCOVERY-1 "capability-based
  runtime discovery + routing"` (a *runtime* router, 06-25); `bb7c75b OX-INTENT-1 "Unified
  Intent Protocol (shared interpretation layer)"` (an *intent* layer); skills auto-router
  (06-26/29 skills commits). Each router entered as a **separate additive** commit on a
  **different axis**.
- **Possible evolutionary pressure (LIKELY):** *new routing axes appeared* (runtime vs
  skill vs intent vs source) and P-ADD meant each was solved as its own module rather than
  extended into one dispatcher.
- **Confidence:** LIKELY (axes are SUPPORTED by commits; non-unification-by-policy is inferred).
- **Counter-evidence:** `OX-INTENT-1` and `OX-WORKFLOW-ENGINE-1` show real attempts at a
  single interpretation/orchestration layer — so this was not pure neglect.
- **Unknowns:** whether any two routers actually decide the *same* axis (needs call-graph). **UNKNOWN.**

## M-2 — Evaluator: 1 → many
- **Responsibility:** judge quality / correctness / done-ness.
- **Before:** one rule-based `Evaluator.self_critique`.
- **After:** many evaluators.
- **Observed evidence (SUPPORTED):** each *question* got its own additive protocol:
  `6f0e72f OX-1.3 "Execution Confidence — measure execution quality"` (06-17),
  `69dec5f OX-1.6 "Evidence-Based Completion — prove completion, don't assert it"`,
  `c0636ba OX-CONFIDENCE-1 "Confidence Calibration"` (06-23),
  `517b8e3 OX-DECISION-1 "Decision Framework"` (06-23),
  `df6c77b OX-COMPLIANCE-1 "Capability Compliance Verification (read-side)"`,
  `c6d4a56 H6 "Artifact Factory — no artifact, no completion"`.
- **Possible pressure (SUPPORTED for existence; LIKELY for cause):** a **prove-don't-assert**
  drive (OX-1.6's message states it) spawned a distinct judge per evaluation question, under P-ADD.
- **Confidence:** SUPPORTED (organs exist, dated) / LIKELY (that they duplicate vs partition).
- **Counter-evidence:** the questions differ (confidence ≠ decision ≠ completion ≠ compliance),
  so some "duplication" may be legitimate partition.
- **Unknowns:** actual overlap between them. **UNKNOWN** (this is DEC-1 in DECISIONS_REQUIRING_EVIDENCE).

## M-3 — Memory: 1 → multiple stores
- **Responsibility:** hold state.
- **Before:** one ephemeral in-process `Memory`.
- **After:** many persistent stores.
- **Observed evidence (SUPPORTED):** `d3d7c23 OX-1.5 "Execution Memory — carry knowledge
  forward"` (06-17); `6e13f48 OX-LEARNING-1 "Lesson Synthesis Engine"` (06-22);
  `9bd1b20 OX-BELIEF-REVISION-1` (06-23); `700b09d/f173bb0 Phase 6 "Institutional Learning
  Engine — lessons from reality"` (06-16); `1dc6191 Phase 5 "Mission Command Center"`;
  `b30f900 OX-ATTRIBUTION-1`.
- **Possible pressure (LIKELY):** **persistence pressure** (Phase 4-6 built durable
  belief/mission/lesson UIs on 06-16 that needed durable stores) + P-ADD (each memory *kind*
  = its own store).
- **Confidence:** SUPPORTED (organs+dates) / LIKELY (cause).
- **Counter-evidence:** `a9d76f5 "single source of truth across both UIs"` shows a
  single-source *event* discipline existed — memory sprawl was not for lack of the idea.
- **Unknowns:** cross-store data redundancy. **UNKNOWN** (DEC-2).

## M-4 — Truth → Epistemic
- **Responsibility:** handle claims / establish truth.
- **Before:** advisory keyword FactFlagger (human-adjudicated).
- **After:** an enforced gate + a scientific-method suite.
- **Observed evidence (SUPPORTED):** a single 06-22/23 burst created the epistemic organs
  additively: `8587eec OX-THEORY-1`, `856600a OX-EXPERIMENT-1`, `5316902 OX-CAUSAL-1`,
  `9bd1b20 OX-BELIEF-REVISION-1`, `5d4ee6d OX-FIRST-PRINCIPLE-1`, `33d9532 OX-UNKNOWNS-1`,
  `39b0fd0 OX-PARADIGM-1`, `ef6dbf2 OX-CURIOSITY-1`. Plus the *stated motive*:
  `69dec5f OX-1.6 "prove completion, don't assert it"` and `9e353b2 OX-H1 "prompt text can
  never become mission identity"`, and truth-guard fixes `39c5478/003c279 shadow_gate`.
- **Possible pressure (SUPPORTED):** **anti-hallucination / prove-don't-claim pressure** —
  the commit messages themselves name the intent (prove, verify, don't assert).
- **Confidence:** SUPPORTED (motive is written in the commits).
- **Counter-evidence:** none material; the direction is consistent across the burst.
- **Unknowns:** whether these descend from V1's FactFlagger or were conceived fresh. **UNKNOWN** (no commit links them).

## M-5 — Council appeared
- **Responsibility:** multi-mind deliberation.
- **Before:** V1 single-agent route (no council).
- **After:** a multi-member council.
- **Observed evidence (SUPPORTED):** the **earliest** git commits already *instrument* an
  existing council — `b5b687f Phase 2A "Council Wiretap — per-member events during
  deliberation"` and `5d187bc Phase 2B "Reasoning Stream — verbatim council reasoning"`
  (both 2026-06-15). The council is being *observed*, i.e. it already existed.
- **Possible pressure:** **UNKNOWN** — the council's *birth* predates the first commit; git
  shows only the later addition of **observability** to it (P-OBS). Its creation motive is
  not recoverable from this history.
- **Confidence:** SUPPORTED (council predates history) / **UNKNOWN** (why it was created).
- **Counter-evidence:** none.
- **Unknowns:** the entire pre-2026-06-15 origin. **UNKNOWN.**

## M-6 — World became "live"
- **Responsibility:** perceive external reality (time/data/hardware).
- **Before:** closed, offline, mock data.
- **After:** live internet/time + real GPU runtime.
- **Observed evidence (SUPPORTED):** `04e9ccc OX-1.1 "World Model — verify before acting"`
  (06-17); GPU/execution arc `18f662d OX-EXECUTION-RECOVERY-1 "separate execution from
  reasoning"`, `2be22b6 STABILIZATION "exact GPU root cause"`, `1c06775 "route EXECUTION to
  llama.cpp GPU"`, `fecac6d "switch GPU model to Qwen2.5-14B (ElmatadorZ)"` (06-24/25);
  live data `eb0f373 "get_news → Google News RSS — real ranked headlines"`.
- **Possible pressure (SUPPORTED):** **grounding pressure** ("verify before acting";
  training data is stale → fetch live) + **performance/hardware pressure** (CPU too slow →
  real GPU runtime). Both stated in commit messages.
- **Confidence:** SUPPORTED.
- **Counter-evidence:** none.
- **Unknowns:** none material.

## M-7 — Reality Awareness emerged
- **Responsibility:** perceive current runtime context before answering.
- **Before:** none (V1 had no runtime world).
- **After:** an emerging (but partial) reality-awareness concern.
- **Observed evidence (SUPPORTED):** `b841c4b OX-1 "Discovery Architecture — investigate
  first, plan second, ask last"` + `04e9ccc OX-1.1 "World Model — verify before acting"`
  (06-17); `8b0835f Phase P0 "Context Reliability + Mission Recovery"` (06-16);
  `79603cd OX-ARTIFACT-1 "Artifact Awareness Protocol (read-side)"`.
- **Possible pressure (SUPPORTED):** **grounding pressure** — repeated action on ungrounded
  assumptions forced an "investigate/verify before acting" stance.
- **Confidence:** SUPPORTED (the intent is in the commit messages).
- **Counter-evidence:** none.
- **Unknowns:** none material.

## M-8 — Proprioception remained incomplete
- **Responsibility:** know the organism's *own* current state (files/model/net/mission it holds).
- **Before:** absent.
- **After:** still absent as shipped code (audits/designs only).
- **Observed evidence (SUPPORTED):** there is **no commit implementing a self-state
  aggregator**; reality-awareness stayed at audit/design level (this session's docs, marked
  N/A/PENDING). Outward-perception protocols shipped (M-6/M-7) but self-perception did not.
- **Possible pressure — and why it was RESISTED (LIKELY):** self-perception must be woven
  **invasively** into the hot loop (chat/agent) to be authoritative; the dominant **P-ADD**
  policy ("additive, read-only, don't touch existing owners") **structurally disfavors**
  invasive core surgery. So the same policy that grew everything else *blocked* proprioception.
- **Confidence:** SUPPORTED (no impl commit exists) / LIKELY (the causal link to P-ADD).
- **Counter-evidence:** `8b0835f "Context Reliability"` shows *some* self-context work at the
  engine level — so it is not zero, only incomplete.
- **Unknowns:** whether an invasive attempt was ever made and reverted. **UNKNOWN.**

## Pressure ledger (summary)
| Pressure | Evidence strength | Effect |
|---|---|---|
| **P-ADD** additive/non-invasive growth | SUPPORTED (≥10 verbatim tags) | fragmented dispatch/judge/memory/epistemics; blocked proprioception |
| **P-TRUST** prove-don't-assert | SUPPORTED (commit messages) | Truth → Epistemic suite |
| **P-GROUND** verify-before-acting | SUPPORTED | World-Model + Reality-Awareness |
| **P-PERF** CPU/latency/hardware | SUPPORTED | execution split; world went live/GPU |
| **P-OBS** observability | SUPPORTED (Phase 1-6 wiretap) | council/house-mind visibility |
| **P-CONC** concurrency/safety | SUPPORTED | shadow-state elimination; concurrent-mission safety |
| **P-CONS** consolidation (counter-force) | SUPPORTED but weaker | won for events/orchestration/intent only |
