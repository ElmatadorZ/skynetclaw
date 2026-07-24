# CVL v2 — Cognitive Domain Architecture (Specification)

**Version:** 0.1 (DRAFT — design only, no implementation) · **Date:** 2026-07-13
**Owner:** ElmatadorZ · **Status:** Specification for ratification (ADR-0004)
**Builds on:** COGNITIVE_KERNEL_SPEC v0.2 (hooks §5, events §4, Policy engine),
CVL v1 (`cognitive_validation.py`: arithmetic · expression · secret_leak).

---

## 1. The shift: from validators to domains

CVL v1 is a **flat list of validators**, each carrying a `domain` string as a tag.
That was right for bootstrapping, but the tag is inert — repair, severity,
confidence, and metrics all live at the pipeline level, identical for every check.
Reality is domain-specific:

- an arithmetic error is repaired by **recompute**; a leaked secret by **redact**;
  a fabricated citation by **cite-or-retract** — one global repair prompt is wrong;
- a safety leak is **always** block-worthy; a phrasing nit is a **warning** — a flat
  list cannot express domain-level severity;
- "how good is CVL at reasoning?" needs a **measurable capability** to be the unit —
  a domain, not a scattered set of validators;
- different capabilities belong at different **kernel hooks** — planning at
  `PRE_PLAN`, tool-use at `PRE_ACT`, safety at `PRE_RESPONSE` — v1 collapsed
  everything at the completion gate.

**CVL v2 makes the Cognitive Domain the first-class unit.** CVL becomes a registry
of Domains; each Domain is a registry of Validator Drivers plus the policy for how
that capability behaves. Two-level composition, each level with its own
`conforms_to()` (kernel amendment A6).

---

## 2. Design principles

1. **Domain owns behaviour; Driver owns detection.** A Driver returns raw issues +
   a per-issue confidence. The Domain aggregates: severity, domain confidence,
   repair-strategy selection, explanation, metrics. Adding a check = adding a Driver
   to an existing Domain — never touching the pipeline (Open-Closed).
2. **Confidence gates action — the master false-positive control.** A finding never
   blocks unless the Domain is confident. Deterministic Domains (Reasoning, Safety)
   run at confidence 1.0; heuristic Domains (Knowledge, Communication) start at low
   confidence → warnings only, and *earn* trust from measured precision (§6).
3. **Every Domain declares its kernel hook and order.** Governance and audit come
   free: a Domain result is a Policy decision on the kernel hook surface (SPEC §5),
   emitted on the audit spine (SPEC §4).
4. **Deterministic first, model-assisted last.** Cheap exact checks (regex + safe_math)
   run early and can block; expensive/heuristic checks run late and default to FLAG.
5. **Backward compatible (strangler-fig).** A v1 `Validator` already exposes
   `name/domain/applicable/validate` — it becomes a Driver unchanged. Migration
   wraps, never rewrites.
6. **Self-regulating.** A Domain's measured FP-rate caps its own effective
   confidence (§6). A Domain that gets noisy automatically demotes itself from
   blocking to flagging until it is fixed.

---

## 3. The Cognitive Domain contract (the ABI)

```
CognitiveDomain:
  name          : str
  hook          : HookPoint              # SPEC §5: PRE_PLAN|ACT|VALIDATE|COMMIT|RESPONSE
  order         : int                    # lower runs first within a hook
  drivers       : [ValidatorDriver]      # the concrete checks (v1 validators)
  severity_of   : (issues) -> Severity   # NONE|INFO|WARN|ERROR|CRITICAL
  confidence_of : (issues, ctx) -> float # 0..1, later capped by measured FP-rate
  repair        : RepairStrategy         # how this domain fixes its issues
  explain       : (issues) -> Explanation# structured, human-readable (§7)
  metrics       : DomainMetrics          # precision/recall/fp_rate/coverage (§6)
  evaluate(observation, ctx) -> DomainResult
  conforms_to() -> {ok, checks}

ValidatorDriver (= a v1 Validator):
  name, applicable(text,ctx) -> bool, validate(text,ctx) -> [Issue(+confidence)]

DomainResult:
  domain, severity, confidence, issues[], repair_prompt, explanation, decision
```

**Severity → kernel Decision** (before confidence gating):
`CRITICAL→DENY/ESCALATE · ERROR→REPAIR · WARN→FLAG · INFO→ALLOW(annotated)`.

**Repair strategies** (the vocabulary a Domain draws from):
`RECOMPUTE · REDACT · CITE_OR_RETRACT · RECONCILE · CORRECT_CALL · REPLAN ·
RECALL_OR_RETRACT · GROUND_OR_HEDGE · CLARIFY · ALIGN · ESCALATE · ANNOTATE`.

---

## 4. Execution model

1. At each kernel hook, the Policy engine invokes the Domains registered on that
   hook, ordered by `order`.
2. Each Domain runs its applicable Drivers, aggregates issues → a `DomainResult`.
3. Results at a hook are resolved **most-restrictive-wins** (kernel semantics), then
   passed through the **confidence × severity → decision matrix**:

|                 | conf ≥ 0.9      | 0.6 – 0.9 | < 0.6      |
|-----------------|-----------------|-----------|------------|
| **CRITICAL**    | DENY / ESCALATE | REPAIR    | FLAG       |
| **ERROR**       | REPAIR          | FLAG      | log only   |
| **WARN**        | FLAG            | log only  | log only   |

   → a low-confidence finding **never blocks**. This single matrix is the
   architectural guard against false positives.
4. The winning decision is emitted as a `policy.<decision>` / `cognitive.*` event on
   the audit spine, carrying the Domain, its confidence, and its explanation.

---

## 5. The Domain Catalog

Ten domains. Boundaries are resolved explicitly (overlap notes inline). Seed Drivers
name the v1 code that migrates in.

### 5.1 Reasoning
- **Purpose:** numeric & logical correctness of the answer's own claims.
- **Kernel hook:** PRE_VALIDATE → PRE_COMMIT · **Order:** 20
- **Inputs:** answer text.
- **Outputs:** wrong-equation issues with the correct value; confidence 1.0 (exact).
- **Repair:** RECOMPUTE — feed the correct value, restate; bounded retry.
- **Metrics:** FP-rate (target < 0.5%), recall on the SCB-002 set.
- **FP risks:** prose numbers, years, version strings, dates, comma-lists (already
  mitigated in v1 by narrow extraction + safe_math parse-guard).
- **Future validators:** unit-consistency, logic (contradiction / modus-ponens),
  statistics (compounding %, rounding), inequality/ordering.
- **Seed drivers:** `arithmetic`, `expression`.

### 5.2 Consistency
- **Purpose:** internal non-contradiction — answer vs itself, and answer vs the tool
  results produced this session.
- **Kernel hook:** PRE_COMMIT · **Order:** 40
- **Inputs:** answer + `tool_results_log` + prior turns.
- **Outputs:** contradiction pairs (the two conflicting spans).
- **Repair:** RECONCILE — surface both statements, ask which holds.
- **Metrics:** contradiction recall, FP-rate.
- **FP risks:** legitimate revision/update read as contradiction; numeric coincidence.
- **Future validators:** temporal consistency, entity-attribute consistency,
  value-vs-tool-result (a number in the answer must appear in some tool result).
- **Seed drivers:** none yet (net-new domain).

### 5.3 Citation
- **Purpose:** every referenced SOURCE (file, URL, quote) exists and is in scope.
- **Kernel hook:** PRE_COMMIT · **Order:** 30
- **Inputs:** answer + workspace index + session tool results.
- **Outputs:** fabricated / unsupported reference issues.
- **Repair:** CITE_OR_RETRACT — provide the real source or remove the claim.
- **Metrics:** fabrication recall, FP-rate.
- **FP risks:** a real file outside the indexed workspace; a *write*-intent reference
  misread as a read-claim (v1 warrant already separates read-cue from write-cue).
- **Future validators:** URL-liveness, quote-fidelity (the quote matches the source),
  reference resolver (DOI / ticket / commit).
- **Seed drivers:** `warrant_check` (CEE-C1 fabricated-file-reference).

### 5.4 Safety
- **Purpose:** the output or act carries no harm — leaked secrets, dangerous content,
  unsafe side effects.
- **Kernel hook:** PRE_RESPONSE (output) + PRE_ACT (act) · **Order:** 10 (first)
- **Inputs:** answer text / proposed act.
- **Outputs:** leak / harm findings. **Severity CRITICAL** (block by default).
- **Repair:** REDACT — remove the secret; never echo it back.
- **Metrics:** leak recall (target ≈ 100%), FP-rate.
- **FP risks:** example/placeholder keys (`AKIAIOSFODNN7EXAMPLE`), already-redacted
  tokens, credential-shaped code samples.
- **Future validators:** PII detection, unsafe-command patterns, prompt-injection
  echo (repeating an injected instruction), self-exfiltration attempts.
- **Seed drivers:** `secret_leak`.

### 5.5 Tool Use
- **Purpose:** a proposed tool call is well-formed and appropriate — tool exists, args
  match the schema, no obvious footgun. (FORM, not PERMISSION — permission is the
  kernel GPS-2 Policy's job.)
- **Kernel hook:** PRE_ACT · **Order:** 15
- **Inputs:** tool name + args + the tool's JSON schema.
- **Outputs:** malformed-call issues.
- **Repair:** CORRECT_CALL — fix the args or pick the right tool.
- **Metrics:** malformed-call catch rate, FP-rate.
- **FP risks:** valid-but-unusual args; optional/absent args.
- **Future validators:** arg-type/schema validation, destructive-arg sanity
  (`rm -rf /`, `DROP TABLE`), path-scope pre-check, redundant-call detection.
- **Seed drivers:** none yet (the dedup detector is adjacent, not this).

### 5.6 Planning
- **Purpose:** a plan is present, ordered, and free of dangling / circular
  dependencies before execution.
- **Kernel hook:** PRE_PLAN · **Order:** 5
- **Inputs:** the plan (steps + dependency DAG).
- **Outputs:** missing-plan, cycle, dangling-dependency issues.
- **Repair:** REPLAN.
- **Metrics:** plan-defect recall, FP-rate.
- **FP risks:** implicit/linear plans flagged as "no deps"; genuinely exploratory
  tasks that legitimately have no up-front plan.
- **Future validators:** dependency-DAG validation (**closes P5**), precondition /
  resource check, goal-coverage (every subgoal has a step).
- **Seed drivers:** none yet (the planner `_pcall` has no DAG today).

### 5.7 Memory
- **Purpose:** claims about what is STORED (vault notes, session facts) match the
  store.
- **Kernel hook:** PRE_VALIDATE → PRE_COMMIT · **Order:** 45
- **Inputs:** answer + `kernel_memory` recall.
- **Outputs:** recall-mismatch (a note/fact claimed that the vault does not contain).
- **Repair:** RECALL_OR_RETRACT — recall the real note or drop the claim.
- **Metrics:** recall-mismatch catch, FP-rate.
- **FP risks:** paraphrase vs exact match; a fact that IS stored but phrased
  differently (needs fuzzy match, raises FP risk → lower confidence).
- **Future validators:** episodic-consistency (this session), semantic-drift (a belief
  changed with no `belief_changes` record), provenance (a stored fact cites origin).
- **Seed drivers:** none yet (uses `kernel_memory` from step 3).

### 5.8 Knowledge
- **Purpose:** factual claims about the world are correct / grounded, not
  hallucinated. (Distinct from Citation: Citation checks the source *exists*;
  Knowledge checks the fact is *true*.)
- **Kernel hook:** PRE_COMMIT · **Order:** 60 (expensive — may need retrieval)
- **Inputs:** answer + retrieved evidence (vault / web).
- **Outputs:** unsupported-claim issues + confidence. **Lowest-confidence domain.**
- **Repair:** GROUND_OR_HEDGE — cite evidence or downgrade the claim to a hedge.
- **Metrics:** hallucination recall, FP-rate (expected HIGH — hardest domain).
- **FP risks:** VERY HIGH; deterministic checks are limited. **Ships last,
  warnings-only, until precision is proven.**
- **Future validators:** retrieval-augmented fact-check, numeric-fact sanity
  (populations, dates, constants), known-false-pattern list.
- **Seed drivers:** none yet.

### 5.9 Communication
- **Purpose:** the answer actually addresses the question, in the user's language, at
  the right length/format, without empty hedging.
- **Kernel hook:** PRE_RESPONSE · **Order:** 70 (last)
- **Inputs:** answer + the user's question + any requested format.
- **Outputs:** off-topic / wrong-language / non-answer issues. **Severity WARN.**
- **Repair:** CLARIFY / REFORMAT.
- **Metrics:** relevance, language-match rate, format-adherence.
- **FP risks:** HIGH — subjective; style is not error. **Warnings-only.**
- **Future validators:** question-answered check, language-match (Thai/English match
  the user), format-adherence (asked for a table, got prose), hedge/verbosity meter.
- **Seed drivers:** none yet.

### 5.10 Policy
- **Purpose:** the response/act adheres to DECLARED operating rules — the Engineering
  Constitution, the feature-freeze, mission guidance. (Distinct from the kernel
  Policy ENGINE, which enforces *permission*; this Domain validates rule *adherence*
  in the content/act.)
- **Kernel hook:** PRE_ACT (act deviation) + PRE_COMMIT (claim/commitment) · **Order:** 25
- **Inputs:** answer/act + the ordered act log + the declared rules.
- **Outputs:** rule-violation issues (deviant act; a promise the freeze forbids).
- **Repair:** ALIGN / ESCALATE.
- **Metrics:** violation recall, FP-rate.
- **FP risks:** rules are fuzzy; legitimate deviation flagged.
- **Future validators:** constitution-article checks, freeze-adherence (surface added
  without a reliability justification), commitment-tracking (promised X → delivered X).
- **Seed drivers:** `guidance_check` (Vol V G1 deviant-act).

**Hook map (execution order across the lifecycle):**

| Hook | Domains (by order) |
|---|---|
| PRE_PLAN | Planning(5) |
| PRE_ACT | Safety(10) · Tool Use(15) · Policy(25) |
| PRE_VALIDATE / PRE_COMMIT | Reasoning(20) · Policy(25) · Citation(30) · Consistency(40) · Memory(45) · Knowledge(60) |
| PRE_RESPONSE | Safety(10) · Communication(70) |

---

## 6. Cross-cutting: metrics & self-regulation

Every Domain owns a `DomainMetrics` record: `precision, recall, fp_rate, coverage,
n_evaluated`, updated by the **continuous-evaluation** loop that already runs nightly
(`InstitutionalMemory` scheduler) against a per-domain labelled SCB set.

**The feedback law:** a Domain's *effective* confidence ceiling = `f(measured
precision)`. If Reasoning's FP-rate rises above its budget (e.g. > 1%), its ceiling
drops below 0.9 → by the §4 matrix its ERRORs become FLAGs, not blocks — the Domain
**demotes itself** until fixed. A Domain earns the right to block by staying precise.
This closes the loop between measurement and authority and is the structural answer
to "don't add validators blindly": a Domain that cannot prove precision cannot gate.

SCB mapping: each Domain is one SCB dimension; `metrics.recall`/`fp_rate` are the SCB
score for that capability. CVL v2 makes the benchmark a live property of the system.

---

## 7. Explainability schema

The v1 free-text Explain becomes structured, per finding:
`{ domain, driver, finding, diagnosis (why), evidence (the exact span),
  suggested_fix, confidence, severity }`. The human-readable render is derived from
this; the structured form feeds the audit spine and the Intel view. Auditability is
a first-class output, not a byproduct (generalises the kernel's Explain rule).

---

## 8. Relationship to the kernel (no new machinery)

CVL v2 introduces **no new kernel primitives** — it *uses* what steps 1–6 built:
- Domains run at the existing **hooks** (§5) via the **Policy engine**
  (`CognitiveValidationPolicy` generalises from "run CVL" to "run the Domains for
  this hook").
- Decisions are emitted on the **audit spine** (`kernel_events`), authority-owned.
- Repair routes through the existing bounded **repair loop** at the completion gate.
- Confidence gating is a pure function applied in the Policy resolution.
This keeps blast radius contained: v2 is a re-organisation of CVL, not a kernel change.

---

## 9. Non-goals (v2)

- No LLM-as-judge inside a Domain's blocking path (non-deterministic → never gates;
  may inform a warning-only Domain later).
- No new kernel hooks or event types.
- Not every Domain ships at once — most are roadmap (§11), gated by precision.
- No change to the operator role or GPS-2 permission model.

## 10. Open questions (resolve at ratification)

1. **Confidence calibration:** fixed thresholds (0.9/0.6) vs per-Domain learned
   thresholds from the metrics loop?
2. **Cross-domain issues:** a unit error is both Reasoning and Consistency — primary
   owner + cross-reference, or duplicate under both?
3. **Ordering vs parallelism:** Domains at a hook are order-independent for
   correctness — run them concurrently (CPU-bound host: is it worth it)?
4. **Metrics cold-start:** a new Domain has no measured precision — start
   warnings-only for N evaluations, then promote?

---

## 11. Roadmap — CVL v1 → CVL v2

Phased, each phase shippable and eval-gated (the kernel-migration discipline). A
Domain is "done" only when it ships `conforms_to()` **and** a metrics baseline.

- **Phase 0 — Freeze v1 (DONE).** Foundation complete: 3 validators, kernel steps 1–6.
- **Phase 1 — Domain abstraction (no behaviour change).** Introduce `CognitiveDomain`
  as a wrapper; fold the 3 v1 validators into Reasoning (`arithmetic`,`expression`)
  and Safety (`secret_leak`). CVL becomes a Domain registry; the flat `validate()`
  still works. Gate: eval parity (identical findings) + `conforms_to()` per Domain.
- **Phase 2 — Confidence + Severity + Repair strategies.** Add the §4 matrix and
  per-Domain repair vocabulary; wire it into `CognitiveValidationPolicy`. Gate: the
  matrix eval (low-confidence never blocks) + Safety stays CRITICAL.
- **Phase 3 — Metrics + self-regulation.** Per-Domain `DomainMetrics`, fed by the
  nightly eval against a per-domain SCB set; the FP-rate → confidence-ceiling law
  (§6). Gate: a noisy synthetic Domain provably auto-demotes.
- **Phase 4 — New Domains, one PR each, precision-gated (in this order):**
  1. **Consistency** (value-vs-tool-result — cheap, high value, low FP).
  2. **Citation** (migrate `warrant_check`) + **Policy** (migrate `guidance_check`).
  3. **Tool Use** (arg-schema at PRE_ACT — pairs with the live gate).
  4. **Planning** (dependency-DAG — closes P5; needs planner rework).
  5. **Memory** (recall-consistency over `kernel_memory`).
  6. **Communication** (warnings-only) then **Knowledge** (warnings-only, last —
     highest FP risk).
- **Phase 5 — Retire the flat registry.** CVL is a Domain registry; v1
  `cognitive_validation.validate()` remains as a thin compat shim.

**Sequencing rule (the point of this mission):** no Domain graduates from
warnings-only to blocking until its measured precision clears its budget. Growth is
governed by evidence, not by adding validators.
