# Agency — Volume VI · 00 — The Ontology of Learning

> Pure philosophy. The question is **"what is learning?"** — not "which learning algorithm."
> No RL/gradient-descent/backprop as axioms; they enter only as recovered comparisons. Part
> II, Volume VI — the **first node of the return arc** (`outcome → learn → govern`), the half
> the system left unbuilt (see GENESIS_PARADIGM.md). Questions 1, 3, 4. Tags: SUPPORTED /
> LIKELY / SPECULATIVE / UNKNOWN / FALSIFIED. Sourcing caveat: attributions recalled from
> RL, statistical learning, control theory, epistemology; names index positions.

Vol V (Execution) ended at the **Outcome** — a spent, irreversible change to the world.
Learning is what the return arc does *with* that outcome: it turns outcome into a changed
disposition. This volume asks what that operation is, before asking how to perform it.

---

## The question the volume must not dodge (stated up front)

SkynetClaw's brain is a **frozen-weight local model**. It *cannot* learn in the weight-
update sense — its parameters do not change from outcomes. So a live, honest theory of
learning must answer: **where can learning live when the model cannot?** The recovered
answer (developed across the volume): learning is *any* persistent disposition-change driven
by outcome, and the model's weights are only *one* possible seat of disposition. When that
seat is frozen, learning must move to the **scaffolding** — a persistent store that changes
future *inputs* (prompts/context). This is not a workaround; it is the ontology telling you
where the disposition is. **The system's learning organ is its memory-of-itself, not its
weights.** SUPPORTED as the volume's load-bearing consequence.

## Q1 · What is learning?

Traditions, from their sides:
- **Reinforcement learning (Sutton–Barto).** Update a policy/value from reward so future
  return improves. Names the *update*; presupposes a mutable disposition.
- **Statistical learning (Vapnik).** Fit a hypothesis from samples that *generalizes* —
  minimize expected risk over *unseen* data, not training error. Names the *goal* (generalize),
  and the danger (overfit).
- **Bayesian revision.** Update a posterior from evidence. The Knowing-side seat of learning.
- **Popper.** Learning = conjecture + *refutation* — the elimination of error, not the
  accumulation of confirmation. Names learning's *logic* (error-driven).
- **Control / adaptive systems.** Adjust a controller from tracking error over time.

**Recovered core (SUPPORTED):** *learning is the transformation of **outcome** into a
**changed standing disposition**, persisting across episodes, such that future behaviour
differs.* It is the return arc's constitutive operation — it takes the Outcome (Vol V) and
revises the Value / Policy / Belief that produced it. Direction: it closes the loop from
world back to mind.

**Three things learning is NOT (the differentiae, SUPPORTED):**
- **≠ Memory.** Storing outcomes is memory; learning is when the stored outcome *changes the
  disposition*. A perfect log that never alters behaviour is memory, not learning.
- **≠ In-the-moment adaptation.** A thermostat or a guidance loop (Vol V) adjusts *within* an
  act; learning persists *across* acts. Adaptation without cross-episode retention is control,
  not learning.
- **≠ Improvement.** Learning can make behaviour *worse* (superstition, overfitting). Learning
  is disposition-*change* driven by outcome; "better" is a norm on it, not its definition —
  the same result Vols I–V reached for rationality/optimality.

So the minimal form: **cross-episode disposition-change driven by outcome.** SUPPORTED.

## Q3 / D1 · The ontology of learning (ten entities)

| Entity | Minimal definition | Source |
|---|---|---|
| **Outcome** | the realized world-state after action (Vol V) | inh. |
| **Feedback / signal** | the outcome *made informative* — an error, reward, or observation of the result | new |
| **Disposition** | the mutable thing learning changes — Value (II) / Policy–Commitment (III) / Belief (I) | inh. |
| **Credit assignment** | the map from an outcome back to the disposition-component responsible for it | **new (the crux)** |
| **Error / regret** | the gap between the outcome and the intended/predicted | new |
| **Memory / trace** | the retained record of outcomes across episodes | new |
| **Update rule** | the operation that turns credited error into a disposition change | new |
| **Generalization** | the extension of a learned disposition to *unseen* situations | new |
| **Exploration** | the generation of the outcomes there is anything to learn *from* | new |
| **Model** | an internal predictor of outcomes (enables learning without acting) | inh. (Part I) |

**Recovered claim (SUPPORTED):** learning adds no new *actuator* — it revises the
dispositions the forward arc already defined (Value, Policy, Plan). Its own contribution is
**Credit assignment** (Q1's differentia, the hardest node, Vol VI·01) and **Update rule**.
Learning is a *meta*-operation: it operates on the other volumes' outputs.

## Q4 · Direction of fit — learning revises *both* arcs

Learning is unusual: it *uses* a **mind→world** input (observing the outcome — how the world
actually turned out) to revise **both** kinds of disposition:
- it can revise **belief** (mind→world: "the world is like this after all"), and
- it can revise **policy/value** (world→mind: "act/aim like this instead").

So learning is the operation that **couples outcome-observation to disposition-revision** —
the return-arc twin of Decision (Vol III), which coupled belief+value to a commitment.
Decision was the *forward* confluence (write out); Learning is the *return* confluence (write
*back*). **SUPPORTED.** The stack's figure-eight now has both confluences theorized:
Observation (input), Decision (forward output), Guidance (in-act), **Learning (return)**.

## Falsifiers
Q1's core fails if a genuine learning is exhibited with **no** disposition change (pure
memory that we would still call learning), or with **no** outcome driving it (a disposition
change from nothing). The "learning ≠ improvement" claim fails if every genuine learning is
shown to be improvement (superstition/overfitting are the standing counterexamples). The
frozen-weight consequence fails if the local model is shown to learn *without* any persistent
external store changing its inputs.
