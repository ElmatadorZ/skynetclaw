# Agency — Volume IV · 03 — Failure Taxonomy

> Pure philosophy. Objective 6. Ten failures, each localized to a broken primitive or
> edge of the planning graph (file 01). The taxonomy does double duty: it classifies
> failures **and** it *validates the primitive set* — because a primitive is real iff it
> owns failure modes the others cannot produce (file 01's decisive argument for adding
> Irreversibility).

---

## The principle + the validation test

`Plan = Commitment ⊕ Dependency ⊕ Irreversibility` (Temporal induced). If this is the
right primitive set, then (a) every failure localizes to one of these or to a graph edge,
and (b) **each primitive owns at least one failure the others cannot generate** — else it
is not independent. The table shows both; the right-hand column is the validation.

| # | Failure | Broken element | Validates |
|---|---|---|---|
| PF1 | **Missing dependency** | Dependency graph incomplete | Dependency |
| PF2 | **Circular dependency** | Dependency graph not a DAG | Dependency |
| PF3 | **Resource collapse** | Resource/Irreversibility exceeded | **Irreversibility** ★ |
| PF4 | **Temporal inconsistency** | induced order contradictory | *(reduces — see below)* |
| PF5 | **Dead plan** | Goal→Commitment→Plan link stale | Commitment |
| PF6 | **Goal drift** | Goal changes, plan doesn't | Goal/Commitment edge |
| PF7 | **Plan drift** | Revision degrades means-end coherence | Revision edge |
| PF8 | **Local-optimum trap** | irreversible step forecloses the goal | **Irreversibility** ★ |
| PF9 | **Overplanning** | closure/stopping rule fires too late | Commitment (timing) |
| PF10 | **Frozen planning** | never commit to execute | Commitment (timing) |

★ = a failure only the Irreversibility primitive can produce — the evidence it is
irreducible.

## Dependency failures — PF1, PF2
- **Missing dependency (PF1):** a real precondition is absent from the graph, so the plan
  is executed in an order that fails (bake before mix). The plan was structurally
  incomplete. Localizes to the Dependency primitive.
- **Circular dependency (PF2):** A requires B requires A — the dependency graph has a
  cycle, so *no* valid ordering exists and the induced temporal order is undefined. The
  plan is unrealizable in principle. Localizes to Dependency (the DAG condition).
Both are failures of the *positive/enabling* structure — and neither can arise from
resource scarcity or weak commitment. Dependency owns them.

## Irreversibility failures — PF3, PF8 (the decisive validation)
- **Resource collapse (PF3):** aggregate demand exceeds a finite, consumable resource
  (two actions need the one tool; the budget/time runs out). This failure **cannot be
  produced** by any dependency structure (the graph can be a perfect DAG) or by commitment
  (the agent can be perfectly resolute). It exists *only because* resources are consumed —
  i.e. only because Irreversibility is a real primitive.
- **Local-optimum / corner-painting trap (PF8):** a locally-good but irreversible step
  moves the world into an **absorbing state** from which the goal is unreachable — the
  agent "paints itself into a corner." This is the *non-ergodic* signature (file 01). It
  **cannot occur** in a free/replayable field (you would simply back out), so it too
  exists only because action is irreversible.

**These two failures are the empirical proof of file 01's addition.** A primitive earns
its place by owning failures; Irreversibility owns PF3 and PF8, which Commitment and
Dependency provably cannot generate. Had the mission's three-term formula been complete,
resource collapse and corner-painting would be inexpressible — and they are the two most
characteristic ways real plans die. SUPPORTED, decisively.

## The Temporal failure that *reduces* — PF4 (validating the demotion)
**Temporal inconsistency (PF4):** the plan's ordering constraints contradict (A-before-B
and B-before-A). One might read this as a failure of a *Temporal* primitive — but on
inspection it is **always** the symptom of *conflicting dependency or resource
constraints* (A-before-B *because* B needs A; B-before-A *because* a deadline/resource
forces it). There is **no temporal inconsistency that is not, at root, a dependency or
resource conflict.** So PF4 does *not* validate an independent Temporal primitive — it
**reduces** to PF1–PF3. This is the failure-side confirmation of file 01's demotion:
**Temporal has no failure mode of its own**, exactly as it has no primitive status of its
own. A primitive with no owned failure is not a primitive. FALSIFIED as independent,
consistently on both the structure side and the failure side.

## Commitment failures — PF5, PF9, PF10 (the timing axis, inherited from Inquiry)
- **Dead plan (PF5):** the goal the plan served is gone, achieved, or impossible, yet the
  plan persists and is executed — action toward nothing (the mirror of inquiry's *dead
  question*, and Vol III's stale commitment). Localizes to a stale Goal→Commitment→Plan
  spine.
- **Overplanning (PF9):** planning continues past the point where the marginal value of
  more planning falls below its cost — the **stopping rule fires too late**. This is
  *literally* Inquiry's stopping rule mis-firing (Vol III DF2 evidence-paralysis, one
  layer up): analysis-paralysis in plan-space.
- **Frozen planning (PF10):** the agent never commits to *executing* — plans forever, acts
  never (the mirror of Vol III's *indecision* DF1). The closure into execution never fires.

PF9 and PF10 array on the **same timing-vs-warrant axis** Vol III found for decision, and
they are governed by the **same stopping rule Inquiry supplies** — direct evidence that
Planning inherits Part I's forward machinery (the symmetry's live core, file 05):

```
   plan too long ◀────────── commit-to-execute at ──────────▶ execute too soon
   Overplanning /            sufficient plan-warrant          (premature execution;
   Frozen planning (PF9,10)                                    a Vol III DF3 at plan scale)
```

## Revision & Goal-coupling failures — PF6, PF7
- **Goal drift (PF6):** the goal shifts but the plan is not revised, so the plan now serves
  a superseded end (Vol I F6 / Vol II VF4 at plan scale). Localizes to the Goal→Commitment
  edge left un-updated.
- **Plan drift (PF7):** during revision, the plan mutates *away* from means-end coherence —
  revision that corrupts rather than corrects (a bad replanning loop, the mirror of a
  degrading inquiry that chases noise). Localizes to the Revision edge inverting its
  function.

## What the taxonomy establishes
1. **Every failure localizes; the taxonomy is bounded by the primitive set + graph.**
   SUPPORTED.
2. **The primitive set is validated by owned failures** — Dependency (PF1,2), Irreversibility
   (PF3,8), Commitment (PF5,9,10) each own failures the others cannot produce; **Temporal
   owns none** (PF4 reduces), confirming its demotion. This is the strongest structural
   argument in the volume: the failure taxonomy independently reconstructs the primitive
   analysis of file 01. SUPPORTED.
3. **The timing failures (PF9,10) are Inquiry's stopping rule** — Planning inherits Part
   I's forward-closure machinery with no new axiom, exactly as Decision did (Vol III DT5).
   This is the symmetry paying rent again. SUPPORTED.

## Falsifiers
The primitive-validation claim fails if resource-collapse or corner-painting (PF3, PF8) is
shown to reduce to a dependency/commitment failure after all (would collapse Irreversibility
back into the three-term formula). The demotion fails if a temporal inconsistency (PF4) is
exhibited that is *not* at root a dependency/resource conflict (an irreducibly temporal
failure). The stopping-rule inheritance fails if optimal plan-closure provably diverges
from optimal inquiry-stopping.
