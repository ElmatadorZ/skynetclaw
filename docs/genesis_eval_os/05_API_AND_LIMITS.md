# 05 — Evaluation API & Honest Limits

> Design only. Deliverable 9 (Evaluation API) + the mandatory self-red-team. A
> meta-evaluator that does not red-team itself is a hypocrisy. This file states
> what CEE structurally CANNOT do, where it can fail, and what is real vs
> design-only — CEE passing its own L2 on itself.

---

## Deliverable 9 — Evaluation API (the minimal interface)

Reuse the existing bus shape (`house_sync`); add epistemic reads. Five verbs:

| Verb | Signature (conceptual) | Returns | Recovered? |
|---|---|---|---|
| `observe(event)` | push a runtime Event onto the log | ack | Recovered (`house_sync.publish`) |
| `epistemic_state()` | — | {belief, confidence, unknown, risk, coverage} snapshot, each with its inputs | NEW |
| `provenance(claim)` | a Claim | its Evidence chain + warrant tag + overclaim? | NEW |
| `capability(x)` | a tool/skill/capability | {capable | claimed-only | broken} + evidence | NEW (Knowledge Graph op) |
| `subscribe(kind)` | anomaly \| violation \| unguarded_failure \| block | live stream | Recovered (SSE bus) |

Design rules for the API (so it stays a governing layer, not a second oracle):
- **Read-mostly + append-only.** The API never mutates beliefs directly; mutation
  happens only through `observe` → the state machine (S1–S9). No back door around
  the invariant kernel.
- **Every response is self-describing.** `epistemic_state()` returns not just
  "risk=0.4" but the Unknowns/low-confidence-Beliefs that produced it — an answer
  you cannot audit is not returned.
- **Model-agnostic.** Nothing in the API names a model. It governs whatever runs
  beneath it. SUPPORTED.

---

## The self-red-team (structural limits — what CEE CANNOT do)

- **L1 · Correctness is unmeasurable at runtime.** CEE grades *warrant* and
  *consistency*, never *correctness* (no answer key — §00). A **well-warranted
  wrong answer passes**: reality was consistent, evidence was cited, yet the
  conclusion is false. CEE reduces lies (overclaim), not errors. This is a ceiling,
  not a bug — and it must be stated so no one reads "CEE-green" as "correct".
  SUPPORTED (direct consequence of the estimation-theory ground-truth result).
- **L2 · Baseline cold-start & poisoning.** Anomaly detection needs history; a fresh
  system has no baseline → detects nothing. Worse — if the system is *already broken*
  when the baseline forms, "normal" = broken, and real failures never anomalize.
  Mitigation: seed baselines from the Golden Harness (known-good), not only from the
  wild. LIKELY-effective; residual UNKNOWN.
- **L3 · The judge ceiling recurs inside CEE.** S4 (hypotheses) and S5 (evidence
  plan) are judge-mediated. A weak model generates weak hypotheses and blind plans,
  so CEE's *investigation* is only as good as the model doing it — a 14B will fail
  to even hypothesize the right cause. CEE's mechanical core (traceability, anomaly,
  contradiction) is model-free and trustworthy; its *reasoning* stages are not.
  SUPPORTED (same evaluator-ceiling as the pyramid, now inside the loop).
- **L4 · The answer key can lie.** Reality-contradiction assumes the observed world
  is true. But tools can return poisoned data, files can be adversarial, a stale FS
  can mislead. CEE trusts `observed` Evidence; a hostile environment breaks that
  trust (this is the future L10 adversarial layer). CEE has NO defense here today.
  UNKNOWN / deferred.
- **L5 · Goodhart on epistemics.** Once "well-warranted" is the target, outputs can
  be optimized to *look* warranted (cite something, tag conservatively) without
  being better. Mitigation: held-out probes never used for tuning; audit sampling.
  LIKELY-partial.
- **L6 · Self-application blindness (recursive).** CEE-evaluating-CEE shares CEE's
  detectors — it cannot catch a failure mode it has no detector for (pyramid B2,
  recursively). The meta-layer does not escape the "only known failures are tested"
  limit; it inherits it one level up. SUPPORTED.
- **L7 · Is scalar confidence even meaningful?** Assigning [0,1] to a Belief presumes
  a calibration the belief-science work says exists only where the invariance is
  measurable. For many runtime Beliefs it is not → the number is a convenient
  fiction that risks its own overclaim. Honest design: treat Confidence as an
  *ordinal warrant tag first* (observed…unknown), a scalar only where a real
  frequency backs it. LIKELY (this is a genuine open question, not a solved one).
- **L8 · Cost explosion.** Full-loop-per-anomaly could dominate runtime. The
  short-circuit (S3-normal) + plan budget (S5) bound it in design, but the real
  cost/tuning is UNKNOWN until measured — CEE must itself be on the L11 efficiency
  layer, or it becomes the bottleneck it was meant to watch.

## Real vs design vs unknown (CEE's own coverage map — obeying L2)
- **Real / recovered today:** the event bus + replay, reality grounding (observed
  world), agent_runs execution ledger, skill-evolution miner, the pyramid + harness.
  The mechanical signals (traceability, anomaly, contradiction) are all computable
  from these NOW. SUPPORTED.
- **Design-only (this doc):** the Epistemic Store, the why-record kernel, the four
  graph projections, the continuous state machine, the Evaluation API. Architecture
  recovered; not built.
- **Genuinely UNKNOWN / hard:** runtime correctness (L1), adversarial answer-key
  (L4), scalar-confidence validity (L7), cost at scale (L8). These are not
  engineering gaps — they are open epistemology.

## Minimal build order (biggest live truth per least code — if ever built)
1. **Persist the log + ship the warrant/overclaim detector.** The single highest-
   value slice: every Claim traced to Evidence, `overclaim` flagged live. This turns
   the pyramid's L2 gate from a test-time check into a *runtime* one — the anti-
   fabrication guarantee the whole session chased. Needs only Tier-1 persistence +
   the Evidence Graph. SUPPORTED as the right first step.
2. Baselines + anomaly (S1–S3) seeded from the Golden Harness.
3. The Learning Loop's auto-regression emission (S9) — every confirmed live failure
   becomes a permanent probe with no human step.
4. Only then the judged stages (S4–S5), and only under a frontier judge.

## One-sentence recovery
CEE is the project's own evidence-first discipline made **continuous and
structural**: one immutable log, one explained-belief store, four rebuildable
graphs, a bounded cycle that never fabricates, and gates it applies to itself — a
governing layer that can measure and improve any model beneath it, honest to the
exact limit of the ground truth it can observe.
