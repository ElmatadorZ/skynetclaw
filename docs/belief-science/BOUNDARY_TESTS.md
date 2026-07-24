# Boundary Tests — behavioural + conceptual tests that separate belief from each neighbour

> For each neighbour, the test (behavioural where possible, conceptual where not) that draws the
> line, and what result assigns a case to which side. Built on the operational cuts from
> BOUNDARY_MATRIX. Tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN.

## The master tests (each cut is one manipulation)
- **T-FIT · Direction-of-fit** (SUPPORTED): create a content↔world mismatch. *Belief* revises to
  fit the world; *desire/preference/goal* drives action to change the world. → cognitive vs conative.
- **T-DEVAL · Outcome-devaluation** (SUPPORTED): devalue the outcome / degrade contingency.
  *Belief-guided (goal-directed) action* drops; *habit* persists. → belief vs habit.
- **T-NOVEL · Novel-state generalization** (LIKELY): probe an unseen, content-entailed situation.
  *Belief(+model)* transfers; *cached policy/skill* fails off-distribution. → belief vs policy/skill.
- **T-ODDS · Odds elicitation** (SUPPORTED): elicit betting quotients. Graded → *credence*;
  categorical/threshold commitment → *flat-out belief*. → belief vs credence.
- **T-UPDATE · Evidence intervention** (SUPPORTED): present decisive evidence. *Belief* updates to
  the present; *memory* keeps its (past) content even when disbelieved. → belief vs memory.
- **T-ENDORSE · Endorsement / avowal-under-reflection** (LIKELY): can the subject reflectively
  endorse or disavow it? *Belief* is endorsable; automatic *expectation/intuition/alief* persists
  against disavowal. → belief vs expectation/intuition/alief.
- **T-BRACKET · Context discharge** (SUPPORTED): does it drop when a purpose ends? *Assumption/
  hypothesis* is bracketed-for-purpose; *belief* persists across contexts. → belief vs
  assumption/hypothesis.
- **T-ATTITUDE · Attitude vs content** (SUPPORTED): hold content fixed, vary the attitude
  (believe / desire / imagine / suppose the same proposition). Different downstream dispositions
  from the *same* content → the *attitude* (belief) is what's isolated, not the *meaning/
  representation*. → belief vs meaning/representation.
- **T-NORM · Normative-vulnerability** (SUPPORTED): violate it. A broken *trust* warrants
  **betrayal/resentment** (a normative response, Baier); a broken factual *belief* warrants
  **updating** (no betrayal). → belief vs trust.
- **T-SPAN · Counterfactual-span** (LIKELY): probe "what if component X changed?" across a system.
  *Understanding* answers a broad dependency-space; an isolated *belief* answers one proposition.
  → belief vs understanding.

## Assignment table
| Boundary | Test | Result → belief | Result → neighbour |
|---|---|---|---|
| belief / desire·preference·goal | T-FIT | state yields to world | state drives world-change |
| belief / habit | T-DEVAL | action drops on devaluation | action persists |
| belief / policy·skill | T-NOVEL | transfers to novel states / avowable | performance-only, breaks off-distribution |
| belief / credence | T-ODDS | categorical commitment | graded odds |
| belief / memory | T-UPDATE | revises to present evidence | retains past content, provenance-bearing |
| belief / expectation·intuition·alief | T-ENDORSE | endorsable/disavowable at personal level | persists against disavowal (automatic) |
| belief / hypothesis·assumption | T-BRACKET | persists across contexts | discharged when purpose ends |
| belief / meaning·representation | T-ATTITUDE | the *holding-true* disposition | the content/vehicle alone |
| belief / trust | T-NORM | violation → update | violation → betrayal (normative) |
| belief / understanding | T-SPAN | one proposition | broad dependency grasp |
| belief / knowledge | (conceptual) | internal state | + truth + anti-luck justification (world-side, **not** behaviourally testable) |

## The one boundary no behavioural test can draw (SUPPORTED)
**belief / knowledge.** Knowledge = belief + **truth** + **justification/safety** — the added
conditions are **world-side** (whether P is true; whether the belief is non-luckily connected to
the fact). No black-box behavioural probe reaches them (BELIEF_OBSERVABILITY established that
observation reaches *belief*, never *knowledge*). → this boundary is **conceptual/external, not
behavioural.** UNKNOWN whether any purely internal test could ever separate them (likely not).

## What the tests do *not* deliver (SUPPORTED)
- **Sharpness at the periphery:** each test has a failure case (BOUNDARY_MATRIX) where the result
  is graded, not binary (over-learned belief ≈ habit; prior ≈ assumption; alief ≈ expectation).
  The tests **order** cases along a cut; they do not place a **fence**. This gradedness is the
  evidence weighed in FAMILY_RESEMBLANCE / REDTEAM_OF_BOUNDARIES.
