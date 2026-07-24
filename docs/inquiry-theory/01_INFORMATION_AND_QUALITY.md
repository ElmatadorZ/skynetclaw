# 01 — Information Gain & Question Quality

> Pure epistemology. Deliverables 3 (Information Theory) & 5 (Quality Metrics) +
> Questions 5 (how much a question reduces Unknown) & 4 (how question quality is
> measured). Recovered, falsifiable, tagged.

---

## Q5 / D3 · Information gain — how much does a question reduce the Unknown?

The recovered measure is **Shannon**, applied to the answer-partition (file 00, I1).
A question's epistemic value is the *expected reduction in uncertainty* its answer
brings.

- **The measure (SUPPORTED).** For a target variable X (what we want to know) and a
  question whose answer is a variable A:
  ```
  ExpectedInfoGain(Q) = H(X) − E_A[ H(X | A) ]  =  I(X ; A)     (mutual information)
  ```
  A question is worth asking, epistemically, exactly to the extent that its answer is
  *informative about the target* — its mutual information with X. A question whose
  answer is independent of X (I=0) reduces nothing, however articulate. SUPPORTED
  (this is Lindley's expected-information / Bayesian experimental-design measure).
- **The "twenty questions" optimum.** Maximum expected gain per question = the one
  whose answer-partition splits the *current* probability mass most evenly — ideally
  in half (1 bit). Optimal inquiry is entropy-halving; a question that rules out a
  near-impossible answer gains almost nothing. SUPPORTED (Huffman/decision-tree
  connection).
- **Expected vs realized gain.** EIG is computed *before* the answer (a property of
  the question + prior); realized gain is *after*. A question can have high EIG yet
  low realized gain on a given run (the informative answer didn't obtain). Judge
  *questions* by EIG (ex ante), *not* by whether this particular answer helped.
  SUPPORTED — the analog of the estimation-lineage "grade the method, not the sample."
- **The unit is relative to the target and the prior.** There is no absolute
  information content of a question — only information *about X, given a prior*. The
  same question is brilliant or worthless depending on what is already known. This is
  the erotetic form of the estimation result "no measurement without a frame."
  SUPPORTED.

**Corollary (recovered) — value ≠ certainty.** The best question is *not* the one
whose answer you can most confidently predict (that answer is already known, EIG≈0).
The best question is the one you can *least* predict but whose answer *most*
discriminates the target — maximal surprise that is maximally relevant. A system that
only asks questions it can already answer learns nothing. LIKELY.

## Q4 / D5 · Question quality — the metric

Information gain is necessary but not the whole of quality. Recovered, a question's
quality is a **conjunction of gates plus a graded score**:

**Gates (a failure zeroes quality — a defective question is not a low-quality one, it
is a non-question, file 00):**
- **G1 · Presupposition-soundness.** The presupposition must be (believed) true. A
  loaded question with a false presupposition has *no* true direct answer — quality
  undefined, not low. SUPPORTED.
- **G2 · Well-posedness.** A nontrivial, exhaustive, mutually-exclusive partition
  (a real set of alternatives). Ill-posed → no gate pass. SUPPORTED.
- **G3 · Answer-recognizability.** A criterion exists to know the answer when found
  (Meno/Bromberger). Without it, no possible response resolves the question.

**Graded score (given the gates pass):**
```
Quality(Q) ∝  ExpectedInfoGain(Q about the aim)  ×  ValueOfInformation(Q)
              ───────────────────────────────────────────────────────────
                                Cost(answering Q)
```
- **ValueOfInformation (Howard; decision theory):** how much the answer would change
  the *decision/aim* it serves. A question with high EIG but no bearing on any aim
  (idle curiosity relative to π) is well-formed but low-value. VoI ties the question
  to purpose. SUPPORTED.
- **Cost:** the effort/observation/experiment needed to obtain the answer. Quality is
  *information-and-value per unit cost* — the same cost axis as the estimation
  lineage. A high-EIG question that is unanswerable-in-practice is low quality.
  SUPPORTED.

**Recovered synthesis:** a *good* question is one that (gates: sound, well-posed,
recognizable) then maximizes **relevant expected information gain per unit cost**.
This single formula is the quality metric — and, read forward, it is precisely the
objective a question-generating inquiry system would optimize. SUPPORTED as the
recovered target; the *estimation* of EIG/VoI/Cost themselves inherits all the
ground-truth limits of the estimation and warrant theories (you can only optimize
*expected* gain against a prior that may be wrong).

## The two failure modes of questioning (recovered, symmetric)
- **Over-asking / idle inquiry:** high-cost questions with low VoI to the aim — motion
  without progress (the questioner is busy, the Unknown unmoved).
- **Under-asking / premature closure:** stopping while high-EIG, in-budget questions
  remain — a decision made on avoidable ignorance.
These are the dual of over-/under-claiming in warrant, one level earlier: the vices
are now about *which questions*, not *which beliefs*. The stopping rule (file 03)
adjudicates between them. LIKELY.
