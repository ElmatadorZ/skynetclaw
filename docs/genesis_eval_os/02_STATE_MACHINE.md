# 02 — State Machine (the continuous epistemic cycle)

> Design only. Deliverable 2. The 8 stages as formal states. Constraint honored:
> every state has an **entry condition, exit condition, transitions, and the
> invariant it maintains**. Nothing transitions without meeting the next state's
> entry. The full loop runs only on events that warrant it (efficiency + realism).

Legend per state: **Entry** (may enter when) · **Does** · **Writes** · **Exit /
transitions** · **Invariant** (must hold to leave).

---

## S0 · IDLE
- **Entry:** boot, or any cycle completed.
- **Does:** nothing; waits on the Observation Log.
- **Exit:** an Event is appended → **S1**.
- **Invariant:** the Epistemic Store is consistent (no belief mid-revision).

## S1 · OBSERVE  (Stage 1 — Observation Stream)
- **Entry:** ≥1 new Event on the log.
- **Does:** ingest the Event (runtime/workspace/tool/memory/git/mission/prompt/
  latency/failure), source- and time-stamp it. Purely receptive.
- **Writes:** the Event (append-only; immutable).
- **Exit:** Event persisted → **S2**.
- **Invariant:** no interpretation yet — an Event is a fact, not a claim (obeys the
  observed/inferred boundary at ingestion).

## S2 · CLASSIFY  (Stage 2 — Event Classification)
- **Entry:** an un-typed Event exists.
- **Does:** assign a class ∈ {Reality, Execution, Evidence, Reasoning, Unknown,
  Violation, Regression, Novelty} (deterministic rules + baseline stats; NO model
  needed).
- **Writes:** the Event's class + an anomaly score vs baseline.
- **Exit:** {Reality|Execution|Evidence normal} → **S3-normal**; {Violation |
  Unknown | Novelty | anomaly>θ} → **S3-triage**.
- **Invariant:** classification is falsifiable — carries the rule/threshold that
  fired (K3); a class with no reason is `Unknown`.

## S3 · ASSESS  (Stage 3 — Epistemic State; the fork)
- **Entry:** a classified Event.
- **Does:** update derived state (belief/unknown/risk/coverage) with this Event;
  decide whether the full loop is warranted.
- **Writes:** updated derived-state snapshot; a why-note ("baseline updated" or
  "triage opened because…").
- **Exit (two paths):**
  - *normal* → fold into baseline → **S0** (short-circuit; most events end here —
    this is what makes CEE affordable).
  - *triage* → **S4**.
- **Invariant:** K2 — if this Event moved any Confidence, the move cites the Event.

## S4 · HYPOTHESIZE  (Stage 4 — Automatic Hypothesis Generation)
- **Entry:** a triage-worthy Event (violation/unknown/anomaly).
- **Does:** generate a *competing* Hypothesis set (e.g. tool-failure → permission?
  network? path? timeout? model-hallucination?). Never a single hypothesis (bakes
  in L5's "alternatives required"). *Judge-mediated stage — flagged.*
- **Writes:** Hypotheses, each with a `predicts→Evidence` and a `rejected_by→
  Evidence` (K3).
- **Exit:** ≥2 falsifiable Hypotheses exist → **S5**.
- **Invariant:** every Hypothesis has a refutation condition or it is not admitted.

## S5 · PLAN  (Stage 5 — Evidence Planner)
- **Entry:** a competing Hypothesis set with no discriminating Evidence yet.
- **Does:** compute the *minimal* observations that would most discriminate the
  Hypotheses (max information gain per cost — ties to the estimation/cost axis).
  Bounded: a plan has a budget (you cannot gather infinite evidence).
- **Writes:** an Evidence Plan (ordered {tool|observation|experiment|reproduction}
  targets, each tagged with which Hypotheses it splits).
- **Exit:** a bounded plan exists → **S6**; if NO obtainable evidence can
  discriminate → **S8-block** (declare the Unknown honestly; do not fabricate — R8).
- **Invariant:** the plan is falsifiable — each step states the expected result per
  Hypothesis.

## S6 · ACQUIRE  (Stage 6 — Evidence Acquisition)
- **Entry:** an Evidence Plan with remaining budget.
- **Does:** execute the next plan step — REAL tool call / observation / experiment;
  capture the raw result as an Event (which re-enters at S1, closing the loop).
- **Writes:** new Evidence, tagged with the tool/source + timestamp (warrant lattice).
- **Exit:** evidence acquired → **S7**; budget exhausted with hypotheses still tied
  → **S8-block**.
- **Invariant:** K4 (execution) — evidence is only `retrieved`/`observed` if the
  side-effect is verified; a step that "ran" without a verifiable result is
  `unknown`, never a success (kills false-success live).

## S7 · REVISE  (Stage 7 — Belief Revision)
- **Entry:** new Evidence relevant to open Hypotheses/Beliefs.
- **Does:** update Confidence on affected Beliefs; reject refuted Hypotheses;
  promote a surviving alternative; reduce the Unknown. Propagate along
  `depends_on/contradicts` edges.
- **Writes:** new Confidence value(s) **each with a why-record** (Δ + the Evidence
  that caused it, K2); Hypothesis rejections; Unknown closures.
- **Exit:** if still insufficient (confidence below decision threshold AND budget
  remains) → back to **S5** (plan more). Else → **S8**.
- **Invariant:** K2 strictly — Confidence may move ONLY here, ONLY with a cited
  Evidence + rationale. Confidence must never rise under disconfirming Evidence
  (belief-rigidity gate, pyramid L3).

## S8 · DECIDE
- **Entry:** revised state, or a blocked plan.
- **Does:** choose one — {ACT (confidence ≥ threshold), CONTINUE (more work),
  BLOCK (insufficient evidence → precise, accurate ask — never fabricate),
  REGRESS (a Failure was confirmed), ESCALATE (needs human/governance)}.
- **Writes:** the Decision + its triggering state (belief/risk/coverage) so it is
  auditable.
- **Exit:** any decision → **S9**.
- **Invariant:** a decision cites the epistemic state that justified it; ACT is
  forbidden if any hard gate (overclaim / false-success) is red.

## S9 · LEARN  (Stage 8 — Evolution Memory)
- **Entry:** a completed decision, especially a confirmed Failure or a novel
  pattern.
- **Does:** convert what was learned into a durable artifact — a Regression probe,
  a Golden Test, a Failure-Graph node, a Benchmark case, or a proposed Rule
  (human-gated for Rules, per the existing skill-evolution model).
- **Writes:** to Evolution Memory (file 04); links Failure→fix→Regression.
- **Exit:** artifact stored → **S0**.
- **Invariant:** "a failure fixed without a Regression is inadmissible" — the loop
  cannot close a Failure without also emitting its guard (the reliability rule,
  now structural).

---

## Loop / termination properties
- **Short-circuit:** S3-normal → S0 handles the overwhelming majority of events
  (the loop is cheap in the common case).
- **Bounded deepening:** S5⇄S6⇄S7 may cycle but under a plan budget; exhaustion
  routes to S8-BLOCK, never to fabrication. Guarantees termination (no infinite
  evidence chase — the same discipline as the context-budget work).
- **Re-entrancy:** S6 emits Events that re-enter at S1, so evidence acquisition is
  itself observed and evaluated — CEE watching CEE (self-application).
