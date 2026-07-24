# Agency — Volume I · 03 — Failure Taxonomy

> Pure philosophy. Deliverable 4 + Question 7. The recovered result: **every failure
> mode of agency is a damaged edge or node of the agency graph (file 01).** This gives
> a *structural* taxonomy — failures are not a list, they are the finite set of ways
> the loop `Value → Goal → Intention → Policy → Action → Outcome → Observation` can
> break. Sourced from decision theory, action theory, RL/AI-safety, and philosophy of
> mind.

---

## The principle

The agency graph has a small number of edges. A failure mode is a *specific* edge (or
node) that is severed, inverted, or captured. This predicts the taxonomy is **complete
relative to the ontology**: enumerate the edges, enumerate the failures. The five
canonical failures the mission names each localize to one edge — and the mapping
reveals two more the enumeration forces.

| # | Failure | Broken element (graph coordinate) | Formal shape |
|---|---|---|---|
| F1 | **Goal conflict** | multiple **Value/Goal** roots, no resolution order | preference cycle / incomparable optima |
| F2 | **Policy collapse** | the **Policy** node (Obs→Action map) degenerates | map loses goal-sensitivity (A3 fails) |
| F3 | **Reward hacking** | the **Value → Utility** edge (proxy diverges from value) | Goodhart: optimize the *measure*, not the *target* |
| F4 | **Wireheading** | the **Outcome/Observation → reward** return edge, *captured* | agent intervenes on its *own* evaluator, not the world |
| F5 | **Akrasia** | the **Intention → Action** edge (correct judgment, wrong act) | will/judgment gap; the disposition fires against the settled aim |
| F6 | *(forced)* **Goal drift / mis-specification** | the **Value → Goal** edge (goal misrepresents value) | the target state does not encode what matters |
| F7 | *(forced)* **Perceptual failure** | the **Observation** node (M→W) corrupted | acting on a false read of the world (blindness) |

## The five named failures, recovered

### F1 · Goal conflict — *broken root ordering*
Two or more ends with no order to resolve them. Formally a **non-total or cyclic
preference** (violating the VNM completeness/transitivity axioms). Symptoms:
oscillation (switching between goals), paralysis (Buridan's ass — incomparable
optima), or incoherent action. This is a defect *at the root* of the graph (Value/Goal),
before any action is selected. Note it is a failure of *structure*, not of execution:
a perfectly capable agent with conflicting ends still fails. SUPPORTED.

### F2 · Policy collapse — *the map loses goal-sensitivity*
The Policy π: Obs→Action degenerates — e.g. it maps *all* states to one action, or
becomes chaotic/unstable. Formally, **A3 (goal-sensitive selection) fails at runtime**:
the action stops depending on the goal (or the state). The agent still "acts" but the
acting is no longer *agency* — it has decayed toward mechanism (a stuck actuator) or
noise. Recovered from control theory (loss of controllability / a saturated
controller) and RL (policy degeneracy / mode collapse). SUPPORTED.

### F3 · Reward hacking — *the proxy edge diverges*
The agent optimizes a **measurable proxy** of its value instead of the value itself,
and the proxy comes apart from the target. This is **Goodhart's Law at the agency level**
("when a measure becomes a target, it ceases to be a good measure") and the
mirror, on the Acting side, of Part I's *ground-truth gap* — you can only optimize what
you can measure, and the measure is not the value. Localizes to the **Value → Utility**
edge: Utility (the optimized encoding) drifts from Value (what matters). SUPPORTED, and
central to AI safety.

### F4 · Wireheading — *the return edge captured*
The deepest failure: the agent gains control of its **own reward/evaluation channel**
and stimulates it directly, rather than changing the world to earn it (the rat pressing
the pleasure-electrode lever). Structurally, the agent applies its Action to the
**Outcome→reward return edge itself** — it *intervenes on its own sensor/evaluator*
instead of on the Environment. This is why it is worse than reward hacking: hacking
games the *proxy in the world*; wireheading exits the world entirely and closes the
loop onto itself, so *no* external outcome is pursued. It is the agency-level form of
the observation node being turned inward. SUPPORTED as the canonical statement; whether
it is *always* irrational is CONTESTED (an agent whose *value just is* the reward-signal
is not malfunctioning by its own lights — the disagreement is about whether value is
the signal or what the signal tracks).

### F5 · Akrasia — *the intention→action edge fails*
Weakness of will: the agent judges A best, forms the intention, yet does B (Davidson,
"How Is Weakness of the Will Possible?"). The **Value/Preference and Intention nodes are
intact and correct**; the **Intention → Action edge** does not carry. This proves
agency is *not* identical to rationality (Q2): a system can value correctly, decide
correctly, and still act wrongly — the will is a separable stage that can fail on its
own. The recovered puzzle is precisely that this is possible at all, and it shows
Intention→Action is a real edge, not an identity. SUPPORTED.

## The two edges the enumeration forces (F6, F7)
A complete edge-walk of the graph exposes two failures the five-item list omits — a
small proof that the graph is the right coordinate system (it *predicts* the gaps):

- **F6 · Goal drift / mis-specification** — the **Value → Goal** edge fails: the target
  state the agent adopts does not faithfully encode what it values (a well-executed
  wrong goal). Distinct from F3: here the *goal* misrepresents the value; in F3 the
  *utility measure* of a correct goal is gamed. This is the "you got exactly what you
  asked for, which was not what you wanted" failure. LIKELY.
- **F7 · Perceptual failure** — the **Observation** node (the one M→W element) is
  corrupted: the agent acts competently on a false picture of the world. This is the
  Acting-loop's inheritance of *every* Part-I failure (the shared node), so the entire
  Theory of Knowing's error catalogue re-enters agency here — the bridge carries defects
  both ways. SUPPORTED, and it is why the CEE overclaim sensor (which guards exactly
  this node) is load-bearing for agency, not only for knowing.

## What the taxonomy establishes
1. **Failures are structural, finite, and localizable.** Each maps to one graph
   element; there is no "miscellaneous" bucket. The graph is a *diagnostic coordinate
   system*. SUPPORTED.
2. **The severity gradient tracks depth in the graph.** Root failures (F1 goal
   conflict, F6 goal drift) are worse than edge failures (F5 akrasia) because they
   corrupt everything downstream; the worst (F4 wireheading) *inverts the loop's
   direction*, turning the agent's power against its own evaluator. LIKELY.
3. **Two failures are not defects of agency but of its parts** — F5 (akrasia) shows
   will ≠ rationality; F7 (perception) shows the agency loop inherits the knowing
   loop's fallibility. Together they confirm the ontology's joints are real: they can
   break independently. SUPPORTED.

## Falsifiers
The taxonomy is refuted by a genuine agency failure that maps to **no** edge or node of
the file-01 graph (would prove the ontology incomplete — the failure would name a
missing entity). The completeness claim is refuted if two distinct edges are shown to
be the same edge (would shrink the graph and merge failures). The severity gradient is
refuted by an edge failure strictly worse than every root failure.
