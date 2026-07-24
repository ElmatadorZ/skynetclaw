# CVL v3 — From Validation to Assurance (Specification)

**Version:** 0.1 (DRAFT — design only, no implementation) · **Date:** 2026-07-13
**Owner:** ElmatadorZ · **Status:** First-principles architecture review for ratification (ADR-0005)
**Supersedes the framing of:** ADR-0002 (CVL v1), ADR-0004 (CVL v2 domains).
**Mandate:** determine whether *Validation* is still the correct abstraction for a
Cognitive Operating System. Challenge every assumption. Prefer elegant architecture
over backward compatibility. The goal is not to preserve CVL — it is to find the
correct long-term architecture.

---

## 1. First principles: is "Validation" the right abstraction?

### 1.1 What CVL mechanically does (strip the name away)
It observes a candidate output/act, runs checks that produce findings, weighs them
(severity × confidence), decides (allow/repair/flag/block), optionally repairs, and
audits. Notice what this *is*: it is producing **justified confidence that certain
properties hold about the system's cognition, and acting on that confidence.**
"Validation" is the name we gave the checkpoint — it is not the thing itself.

### 1.2 The six candidates are not synonyms — they are different layers
Engineering has precise distinctions here; using them loosely is the trap.

| Term | Precise meaning | What it presupposes |
|---|---|---|
| **Evidence** | facts/observations that bear on a claim, with provenance & weight | nothing — it is the substrate |
| **Verification** | checking a claim against a **spec / ground truth** (deterministic) | a spec exists to check against |
| **Validation** | checking a claim against **intent / need** (fuzzier) | a stakeholder need to satisfy |
| **Diagnosis** | explaining **what is wrong and why** (causal) | something is already suspect |
| **Assurance** | a continuous, lifecycle argument yielding **justified, demonstrable confidence** | claims worth being confident about |
| **Quality** | the emergent **property/goal** ("fitness for purpose") | — it is an outcome, not a mechanism |

Read top-to-bottom this is a **stack**, not a menu:
- **Evidence** is the atom.
- **Verification** and **Validation** are two *methods of producing evidence*
  (against a spec vs against intent). CVL's arithmetic/secret-leak checks are
  actually **verification** (ground-truth), which means "Cognitive *Validation* Layer"
  was already a slight misnomer.
- **Diagnosis** is the interpretive engine that turns disconfirming evidence into a
  cause and a targeted fix.
- **Assurance** is the *architecture*: it composes evidence + diagnosis into a
  standing argument and carries confidence through the lifecycle.
- **Quality** is the goal the whole stack serves — never the organizing noun (it
  says *what* we want, never *how*).

### 1.3 Why "Validation" specifically fails at OS scale
Validation is a **checkpoint** abstraction: pass/fail, here, now. An operating system
does not "validate" memory safety once — it *maintains* an invariant continuously and
provides a standing guarantee. A Cognitive OS needs the same: standing guarantees
about its own cognition. Validation, as a gate, has four structural deficits:
1. **No memory.** It re-decides every turn; confidence earned at step 3 is thrown
   away by step 10. Assurance *carries confidence forward*.
2. **No argument.** It emits a verdict, not a justification. A superhuman agent's
   outputs must be *auditable arguments*, because humans cannot re-derive them.
3. **Binary framing.** Valid/invalid collapses a graded, evidential reality. Real
   cognition is degrees of justified belief.
4. **Doesn't scale to open-ended claims.** You can validate `1200*5`; you cannot
   "validate" a novel strategy. You can *assure* it — assemble evidence and argue a
   confidence.

### 1.4 Steelman: keep "Validation" (and rebuttal)
*For:* it is simple, testable, and most current checks are deterministic gates;
"Assurance" risks grandiosity and ceremony. *Rebuttal:* the simplicity is real only
because today's claims are trivial (arithmetic). The mandate is the **long-term**
architecture for an increasingly autonomous, eventually superhuman agent. For that
regime, a gate is the wrong primitive; a standing, evidence-based argument is the
right one. Elegance here means choosing the abstraction that *degenerates* to a cheap
gate when the claim is trivial but *scales* to an argument when it is not (§2.3).
Validation cannot scale up; Assurance degenerates down. **Prefer the one that spans
the range.**

### 1.5 Decision
> **Replace Validation with Assurance.** CVL becomes the **CAE — Cognitive Assurance
> Engine**: a continuous, evidence-based process that maintains justified confidence
> that the system's *cognitive invariants* hold, and acts on that confidence.
> Evidence is its substrate; Diagnosis is its engine; Verification and Validation are
> two of its evidence-producing methods; Quality is the goal it serves.

This is not a rename. It changes the unit of record (from *finding* to *claim + its
assurance case*), makes confidence **persistent and calibrated** rather than a
per-turn threshold, makes **human oversight** an evidence input rather than an escape
hatch, and — most importantly — is designed to **dissolve** as the model internalizes
the invariants (§11). Backward compatibility with `validate()` is explicitly *not* a
goal.

---

## 2. Architectural philosophy

### 2.1 The atom is the Claim
Every output, sub-conclusion, and proposed act is a **claim** the system is making
("the total is 6000", "file X supports this", "this plan will work", "this act is
safe"). The CAE's job is not to "check the answer" — it is to hold every claim to an
appropriate standard of justification.

### 2.2 The structure is the Assurance Case
For each claim the engine assembles a lightweight, computable **assurance case**:
`Claim ⟵ Argument ⟵ Evidence`, producing a **calibrated confidence** and a
**decision**. (This is Goal-Structuring-Notation / safety-case thinking, made
runtime and cheap — an argument graph, not a document.)

### 2.3 Graceful degeneration (the elegance test)
Complexity is paid **proportional to uncertainty**:
- a deterministic claim with one decisive evidence source (safe_math says 6000, stated
  6000) → a one-node case, confidence 1.0, ~free — exactly as cheap as v2;
- an uncertain factual/strategic claim → a richer case with multiple weighed evidence
  sources and an explicit confidence.
The architecture is heavy only where reality is hard. A checkpoint cannot do this;
an assurance case does it natively.

### 2.4 Cognitive invariants (the OS analogy)
An OS maintains invariants (memory isolation, no double-free). The CAE maintains
**cognitive invariants** — properties that must hold about the system's beliefs and
acts, e.g.: *no asserted number is uncomputed · no claim exceeds its evidence · no act
without warrant · no contradiction shipped · no secret emitted · no plan with a
dangling dependency.* Assurance is the process of continuously keeping these true.
CVL v2's "domains" become the **owners of invariant families**.

### 2.5 The dissolving-scaffold principle
The deepest design commitment. External assurance exists because the model cannot yet
self-maintain these invariants. As models improve, assurance should migrate from an
external **enforcer** → an **auditor** → a **teacher** (a calibration/training signal),
and finally become *intrinsic* to cognition (metacognition). The correct long-term
architecture is therefore one **explicitly designed to make itself progressively
unnecessary**, governed by measured evidence that the model has earned autonomy (the
*assurance dividend*, §6). This is the opposite of a gate that entrenches itself.

---

## 3. Domain model

CVL v2's Cognitive Domains survive but are **re-cast** as **Assurance Domains**. A
Domain is no longer "a bundle of validators"; it is **the owner of an invariant
family**, bringing three things to the engine:
1. **Evidence Sources** — producers of evidence for/against claims in its scope.
   Verification sources (deterministic: `safe_math`, schema-check), validation
   sources (intent/spec), retrieval sources (vault/web), provenance sources (does the
   cited artifact exist), cross-check sources (answer vs tool-results), and the
   **human** (a high-authority source, §10).
2. **Diagnostic models** — how to explain a disconfirmed claim in this family and
   pick the repair (recompute / redact / cite-or-retract / replan …).
3. **Calibrated confidence** — each of its evidence sources carries a *measured*
   likelihood ratio (§8), not a hand-set number.

The ten v2 domains (Reasoning, Consistency, Citation, Safety, Tool Use, Planning,
Memory, Knowledge, Communication, Policy) remain the invariant families and keep their
kernel-hook placement and execution order from CVL_V2 §5 — v3 changes what a domain
*is*, not the catalog. Verification vs Validation is now an attribute of an *evidence
source*, not a layer name.

---

## 4. Runtime lifecycle

CVL v2 pipeline was `Observe → Diagnose → Repair → Explain → Validate → Accept`. CAE
generalizes and adds persistence:

```
Claim-detect → Assemble-evidence → Diagnose → Argue&score → Decide → Repair
     ↑                                                                  │
     └──────────────── Carry-forward (persist assurance) ◀── Reflect/learn
```

- **Claim-detect:** extract the claims in a candidate output/act (numeric, factual,
  procedural, safety, provenance).
- **Assemble-evidence:** each relevant Domain's evidence sources fire (deterministic
  first, retrieval/heuristic last), producing weighted evidence.
- **Diagnose:** for disconfirmed claims, produce root cause + repair strategy.
- **Argue & score:** build the assurance case; combine evidence into a calibrated
  confidence (§8).
- **Decide:** confidence × severity → kernel Decision (the CVL_V2 matrix, now with
  calibrated confidence). Emitted on the audit spine as the assurance record.
- **Repair:** route through the kernel's bounded repair loop, targeted by the
  diagnosis.
- **Carry-forward:** a claim assured at confidence *c* is **cached with its case**;
  it is not re-assured next turn unless its supporting evidence changed. This is the
  OS-like standing guarantee and a real runtime departure from v2.
- **Reflect/learn:** outcomes feed calibration and the assurance memory (§8–9).

---

## 5. Contracts (ABI — specification, not code)

```
Claim        : { id, content, type, scope, owner_domain, asserted_confidence? }
Evidence     : { source_id, polarity(+/−), strength, likelihood_ratio, provenance, ts }
EvidenceSource: produce(claim, ctx) -> [Evidence]        # verification|validation|
                                                          # retrieval|provenance|cross|human
                reliability : CalibratedReliability        # learned (§8)
Diagnosis    : { claim, root_cause, repair_strategy, rationale }
AssuranceCase: { claim, evidence[], argument, confidence, decision, explanation }
Decision     : ALLOW | FLAG | REPAIR | ESCALATE | DENY     # kernel vocabulary (unchanged)
AssuranceDomain:
    invariants[], evidence_sources[], diagnostic_model, hook, order,
    assure(claims, ctx) -> [AssuranceCase]
    conforms_to() -> {ok, checks}
```

The kernel contracts are **unchanged**: decisions are still kernel `policy.*` /
`cognitive.*` events on the audit spine; repair still uses the bounded loop; the CAE
is exposed at the existing hooks by a policy that generalizes `CognitiveValidationPolicy`
from "run validators" to "assure this hook's claims". **No new kernel primitives** —
which is why an elegance-first rewrite here stays low-risk at the kernel boundary.

---

## 6. Metrics

Assurance is measured as a *system property*, not a pass count.

- **Assurance coverage:** fraction of shipped claims that carried an explicit case.
- **Calibration error (ECE / Brier):** do claims asserted at confidence 0.9 turn out
  right ~90% of the time? This is the headline metric — an *assured* system must be
  *calibrated*, not just accurate.
- **Per-source likelihood ratio & reliability:** measured, not assumed (§8).
- **Repair success rate:** fraction of diagnoses whose repair actually fixed the claim.
- **Assurance dividend:** the trend of *external* assurance effort needed per claim as
  intrinsic model reliability rises — the governing metric for the dissolving scaffold
  (§2.5, §11). A healthy system's dividend rises over time.
- **False-intervention rate:** claims the CAE blocked/repaired that were actually
  fine — the successor to v2's FP-rate, now per evidence source.

Each metric is a live SCB dimension, fed by the existing nightly evaluation loop.

---

## 7. Self-improvement

- **Evidence-source reliability is learned.** Each source accrues a track record
  (how often its + / − evidence matched the eventual truth) → a measured likelihood
  ratio and a reliability weight. A source that proves noisy is *automatically
  down-weighted* in the argument — the generalization of v2's domain auto-demotion,
  now at the granularity of individual evidence.
- **Diagnosis → repair reinforcement.** Diagnoses whose repairs succeed are
  reinforced; ones that don't are retired. The CAE learns *which explanation leads to
  a fix*, not just which check fires.
- **Invariant discovery.** Recurring outcome failures with no owning invariant suggest
  a *missing* invariant/domain — the system proposes new assurance targets from its
  own failure history (human-ratified before activation).

## 8. Confidence calibration

v2 used fixed thresholds (0.9 / 0.6). v3 makes confidence **Bayesian and calibrated**:
- each evidence source contributes a **likelihood ratio** (how much its verdict should
  shift belief), *measured* from its track record;
- the assurance case combines independent evidence into a posterior confidence;
- **calibration is trained from outcomes**: the Outcome Clock (7-day horizon, already
  in the system) judges whether assured claims held; systematic over/under-confidence
  recalibrates the mapping. The target is *low calibration error*, not high raw
  confidence.
- The confidence × severity → decision matrix from CVL_V2 §4 is retained but now
  consumes a *calibrated* posterior — a low-calibration source cannot manufacture a
  blocking confidence.

## 9. Learning

- **Assurance memory:** every claim + case + outcome is recorded (extends the existing
  institutional memory + `predictions`/Outcome Clock tables). This is the corpus for
  calibration, reliability estimation, and repair reinforcement.
- **Per-claim ledger:** the unit of institutional learning shifts from "which
  validator fired" to "which claims we made, how we justified them, and how they turned
  out" — a far richer signal, and the natural substrate for the system to improve its
  own reasoning, not just its checking.

## 10. Human override

In a gate, the human is an escape hatch that bypasses the check (and loses the
signal). In an assurance architecture the human is a **first-class evidence source
with the highest authority weight** and a *tracked* reliability:
- an override = the human **adds or retracts evidence / adjusts a warrant**, and the
  assurance case **recomputes** — the decision changes because the *argument* changed,
  transparently, on the audit spine (never a silent bypass);
- overrides are **calibration gold**: a human correction is the strongest training
  signal for evidence-source reliability and diagnosis quality;
- authority is bounded by the kernel: a human can add evidence and lift an ESCALATE
  (the authenticated operator role already does this, audited) but **cannot forge
  ground truth** — human evidence against `safe_math` on `1200*5` is recorded and
  visible, not silently obeyed. Even the human is inside the argument.

## 11. Future AGI compatibility

This is where Validation and Assurance diverge most.
- **Auditable arguments, not re-derivable answers.** Oversight of a superhuman agent
  cannot mean re-checking its outputs — humans can't. It must mean *auditing the
  assurance case*: the argument and its evidence. Assurance is the native oversight
  interface for superhuman cognition; validation (a verdict) is not.
- **Invariants are the stable core.** Model capabilities will change beyond
  recognition; the cognitive invariants (no claim beyond its evidence, no act without
  warrant, no contradiction shipped) are far more durable. Architecting around
  *invariants + evidence* rather than *specific validators* is what survives capability
  jumps.
- **The dissolving scaffold (the thesis).** The CAE must be built to hand
  responsibility back to the model as the model earns it — enforcer → auditor →
  teacher → intrinsic. The **assurance dividend** (§6) is the measured, governed signal
  for that handover. An architecture that entrenches an external gate forever is
  *misaligned with its own success*; the correct one is designed to fade into a
  calibration signal. This is only expressible in an assurance frame — a validation
  gate has no notion of "becoming unnecessary."

## 12. Challenging my own design

- **"Assurance cases are over-engineered for arithmetic."** → Answered by graceful
  degeneration (§2.3): trivial claims yield trivial cases, as cheap as v2. If a future
  audit shows the case machinery adds measurable overhead to deterministic claims, the
  engine must special-case them — a real risk to monitor, not dismiss.
- **"Is this philosophy theater — does the code actually change?"** → Substantive
  changes: persistent carry-forward confidence (§4), calibrated Bayesian confidence
  (§8), evidence sources with learned likelihood ratios (§7), human-as-evidence (§10),
  and the claim+case as the unit of record. These are behavioral, not cosmetic.
- **"Why not Diagnosis as the top-level?"** → Diagnosis is reactive (presupposes a
  suspect claim) and cannot express proactive evidence-gathering, confidence-carrying,
  or the dissolving scaffold. Diagnosis is the *engine inside* assurance, not the
  architecture. Honest weighing, not a foregone conclusion.
- **"Why not Evidence as the base name?"** → Evidence is the substrate, but a substrate
  is not an architecture: evidence alone neither decides nor guarantees. Assurance is
  the argument layer *over* evidence. Naming the whole after the substrate would hide
  the argument, which is the point.
- **"Calibration needs outcome labels the system rarely gets."** → Real limitation.
  Many claims never receive ground-truth feedback. Mitigation: calibrate aggressively
  where outcomes *are* observable (deterministic claims, Outcome-Clock-judged
  predictions, human overrides) and keep unobservable-claim confidence conservative
  and warnings-only. Calibration coverage itself becomes a tracked metric.
- **"Biggest risk."** → An assurance frame can rot into safety-case *bureaucracy*
  (arguments nobody reads). The guard: the case is a *computable runtime object* with a
  live decision and metrics, never a document; if a case isn't influencing a decision
  or a metric, it should not exist.

## 13. Non-goals

- No LLM-as-judge in a *blocking* path (may be a warnings-only evidence source with a
  measured, low likelihood ratio).
- No new kernel primitives; the CAE lives on the existing hooks/events/policy/repair.
- Not a document-based assurance-case process; strictly runtime objects.
- No preservation of the v1/v2 `validate()` surface where it obstructs the model
  (elegance over compatibility, per the mandate).

## 14. Recommendation & roadmap (v2 → v3)

**Recommendation:** adopt **Assurance** as the organizing abstraction; rename CVL →
**CAE (Cognitive Assurance Engine)**. Validation and Verification demote to
*evidence-source types*. Preserve the v2 domain catalog and kernel wiring; replace the
*core loop and unit of record*.

Phased (each shippable, eval-gated; elegance over compat — breaking `validate()` is
acceptable behind a thin shim only if it costs nothing):
- **P1 — Claim & Evidence core.** Introduce Claim / Evidence / AssuranceCase as the
  unit; wrap v2 validators as deterministic verification evidence sources. Behaviour
  parity; the case for a deterministic claim is trivial. Gate: identical decisions to
  v2 + `conforms_to()`.
- **P2 — Calibrated confidence.** Replace fixed thresholds with likelihood-ratio
  combination; wire outcome-based calibration to the Outcome Clock. Gate: measured
  calibration error beats the v2 fixed-threshold baseline.
- **P3 — Carry-forward assurance.** Persist assured claims; re-assure only on evidence
  change. Gate: no re-litigation of unchanged claims; audit shows carry-forward.
- **P4 — Human-as-evidence + assurance memory.** Overrides recompute the case and feed
  calibration; per-claim ledger lands in institutional memory. Gate: an override is
  visible in the case and measurably improves source reliability.
- **P5 — The dividend & the fade.** Instrument the assurance dividend; let proven
  domains migrate enforcer→auditor as intrinsic reliability rises. Gate: at least one
  domain provably transitions to advisory without a rise in escaped defects.

**Ratification gate:** accept the abstraction shift (ADR-0005) before P1. Until then,
CVL v2 stands and implementation stays paused.

---

*The goal was never to preserve CVL. If a Cognitive OS is to be trustworthy at and
beyond human level, it must not merely check its outputs — it must maintain a living,
calibrated, auditable argument for why they can be trusted, and be humble enough to
hand that job back to the mind it guards. That is Assurance, not Validation.*
