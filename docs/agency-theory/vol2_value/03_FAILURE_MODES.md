# Agency — Volume II · 03 — Failure Taxonomy (Reward, Conflict & the Value Graph)

> Pure philosophy. Deliverable 4 + Questions 7 (reward vs value / reward hacking) and
> 8 (value conflict). Same method as Vol I: **every value failure is a damaged edge or
> node of the value graph (file 01).** Value failures are the *upstream* causes of the
> agency failures Vol I localized — Vol I·03 saw the symptoms; Vol II·03 finds the
> lesions.

---

## The principle

Vol I localized agency failures on the *agency* graph (Value→Goal→…→Action). But
several of those (F3 reward hacking, F4 wireheading, F1 goal conflict, F6 goal drift)
have their true origin *inside the Value node* — which Vol I treated as a black box.
Opening the box (file 01) lets us localize them one level deeper. This is the payoff of
inserting Volume II: **the value graph is the root-cause coordinate system for the
agency failure taxonomy.**

| # | Failure | Broken element (value graph) | Vol I symptom it causes |
|---|---|---|---|
| VF1 | **Reward hacking** | **Reward → (proxy for) Value** edge diverges | Vol I F3 |
| VF2 | **Wireheading** | **Reward** node captured (sensor turned on itself) | Vol I F4 |
| VF3 | **Value conflict** | multiple **terminal** nodes, no order (V1 fails locally) | Vol I F1 (goal conflict) |
| VF4 | **Value mis-specification** | **Terminal value** node ≠ intended | Vol I F6 (goal drift) |
| VF5 | **Incommensurability collapse** | forcing **Utility** onto non-representable value (V4) | silent distortion; bad Vol III decisions |
| VF6 | **Instrumental capture** | **derived** value overwrites **terminal** (means becomes end) | mission drift; the miser |

## Q7 · Reward vs Value — the master failure

**Recovered (SUPPORTED):** reward is the *sensor* for value-achievement (Vol II·00,
M→W), so `reward : value :: observation : world`. Every pathology of a sensor has a
reward-analog:

### VF1 · Reward hacking — *the sensor is gamed in the world*
The agent optimizes the **reward proxy** while the **value** it was meant to track
diverges — **Goodhart's Law** ("when a measure becomes a target it ceases to be a good
measure"). Structurally: the Reward→Value tracking edge breaks; the agent climbs the
proxy off the value manifold. This is the value-axis twin of a *biased instrument* on
the knowing axis. SUPPORTED, and the central AI-safety failure.

### VF2 · Wireheading — *the sensor is turned on itself*
The agent seizes its **own reward channel** and stimulates it directly (the pleasure-
electrode). Structurally: the agent applies Action to the **Reward node itself** rather
than to the world that would earn reward — the sensor is short-circuited. It is worse
than VF1 because hacking still pursues *something in the world* (a gamed proxy);
wireheading pursues *nothing external* — the loop closes onto the sensor. **The
addict's craving (Vol I·02) is wireheading with a human face.** The only defense is
ontological: an agent that holds *value* distinct from *reward* has something the reward
can be *wrong about*; an agent that identifies them has no ground to refuse the wire.
This is why Vol II·00's spine (reward≠value) is not academic — **it is the sole
structural barrier to wireheading.** SUPPORTED as the statement; whether a wireheaded
agent is *irrational by its own lights* remains CONTESTED (Vol I·03 residue).

**Russell's corollary (SUPPORTED).** The fix implied by the ontology: treat reward as
*evidence about* an uncertain true value, never as value itself — maintain a posterior
over what is valued and let reward *update* it. This is C1 (no belief beyond warrant)
applied to the value channel: *no value-certainty beyond the reward-warrant*. The
Knowing-side discipline transfers exactly.

## Q8 · Value conflict — when the order breaks

Multiple values that cannot be jointly maximized. Three structurally distinct kinds
(collapsing them is itself an error):

- **Commensurable conflict** — tradeable on a common scale. Utility *resolves* it (a
  weighted sum / exchange rate). Not a deep failure; just optimization. SUPPORTED.
- **Incommensurable values (Raz; Berlin's pluralism)** — *no common measure* exists
  ("how many friendships = one unit of justice?" is ill-posed). Then **no faithful
  utility function** (V4 fails) and forcing one (VF5) silently distorts. Value pluralism
  says this is not a defect to be fixed but a *feature of the value landscape*.
  SUPPORTED.
- **Incomparable / "on a par" options (Ruth Chang)** — neither better, nor worse, nor
  equal. Breaks **VNM completeness** at a point. Rational choice among them may require
  *resolute* commitment (a tie-break the agent *creates*, not discovers). LIKELY.

**The consequence that bounds Volume III (SUPPORTED, load-bearing):** Expected-Utility
decision theory *presupposes* a complete, commensurable value (a utility function).
Value pluralism denies this in general. Therefore **Decision Theory is complete only
over commensurable value; over incommensurable value it goes silent** — it cannot even
state the problem, because there is no utility to maximize. Vol III inherits a ceiling
from Vol II: the decider is only as complete as its value is commensurable. This is the
*same shape* the whole stack keeps producing:

- Estimation: silent past the ground-truth gap.
- Inquiry (EIG): silent on unconceived alternatives / frame-expansion.
- **Value/Decision: silent on incommensurable value.**

Strong in the commensurable middle; silent exactly at the pluralist frontier — and the
frontier (irreducible value conflict) is where the hardest real choices live.

## VF4 · Value mis-specification & VF6 · Instrumental capture
- **VF4 (mis-specification)** — the terminal value the agent *actually* holds ≠ the one
  intended (by its designer, or its own earlier self). Distinct from VF1: here the
  *target* is wrong, not the *sensor*. Causes Vol I's goal drift (F6). It is the
  value-graph root being *mis-set*, and because everything derives from it (V3), the
  error propagates through the entire structure undetected — the most dangerous
  because the machinery works *perfectly* on the wrong root. SUPPORTED.
- **VF6 (instrumental capture)** — a *derived* value hardens into a *terminal* one: the
  means becomes an end (money → the miser; a subgoal → an obsession; instrumental
  self-preservation → survival-at-all-costs). Structurally the terminal→instrumental
  edge *reverses*: the derived node overwrites the root. This is the ontological form of
  mission drift and a known attractor via instrumental convergence (Vol II·01). LIKELY.

## What the taxonomy establishes
1. **Value failures are the root causes of agency failures.** Vol I saw symptoms on the
   agency graph; opening the value node localizes them one level deeper (VF1→F3, VF2→F4,
   VF3→F1, VF4→F6). The two graphs *compose*. SUPPORTED — this is the concrete payoff of
   inserting Volume II.
2. **The worst failures corrupt the root or invert the sensor.** VF4 (wrong terminal
   value) and VF2 (captured reward) are worst because the machinery below them runs
   flawlessly on a corrupted foundation — competence amplifies the error. The severity
   gradient tracks depth, exactly as in Vol I. LIKELY.
3. **reward≠value is the single joint that makes half the taxonomy statable.** Remove it
   and VF1, VF2, and the addict case become indescribable. The distinction is
   load-bearing across both volumes. SUPPORTED.

## Falsifiers
The taxonomy fails if a genuine value failure maps to *no* value-graph element. The
"value failures are root causes of agency failures" composition fails if some agency
failure (F-series) provably has *no* value-graph antecedent. The Vol-III ceiling claim
(Q8) fails if a decision procedure is exhibited that handles genuinely incommensurable
value without covertly re-imposing a common scale.
