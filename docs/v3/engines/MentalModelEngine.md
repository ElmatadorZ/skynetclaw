# Mental Model Engine (Theory of Mind)

> Agents must reason about *other agents* — what each peer believes, knows, doesn't
> know, and how confident it is. This is the Theory of Mind of the organization.
> **It is an engine, not a kernel** — derivable as a projection over existing kernels.
> Parent: [V3-Architecture](../V3-Architecture.md) · Justification: [DecisionLog](../DecisionLog.md)

## 1. The gap it fills
In V2, an agent knows the Mission but not its peers. The Architect cannot ask "does the
Analyst already know X?"; the Governor cannot weigh "how confident is the Scout?". A
digital organization needs each member to hold a **model of other members' minds** —
otherwise councils talk past each other, duplicate work, and over- or under-trust peers.

## 2. Why an engine, not a kernel
A mental model is **derivable**, so by the Freeze rule it cannot be a kernel. It is a
per-observer **projection** over three existing kernels:
- **[Epistemic Kernel](../kernels/EpistemicKernel.md)** — *what* is believed, with
  confidence/evidence (the content of minds).
- **[Identity](../kernels/IdentityCapability.md)** — *who* the principals are.
- **[Journal](../kernels/Journal.md)** — *which events each agent was exposed to* (so we
  can infer what a peer has or hasn't seen → what it can/can't know).

`MentalModel(observer, subject) = fold over (events subject was exposed to) ∩ (epistemic
claims subject asserted/voted on)`. No new kernel — a read model.

## 3. What a mental model contains
```jsonc
{ "observer":"agent:architect", "subject":"agent:analyst",
  "believes":[{"claim":"kg:..","est_confidence":0.7}],   // observer's estimate of subject's belief
  "knows":["kg:topic:gold"],        // subject demonstrably exposed (Journal)
  "unaware_of":["kg:topic:forex"],  // not in subject's exposure set
  "reliability":0.8,                // calibrated track record (calibration.py)
  "last_updated":"evt:.." }
```
Note `est_confidence` is the *observer's estimate of the subject's* confidence — a
second-order belief. This is what makes it Theory of Mind, not just shared memory.

## 4. How it is used
- **Council efficiency** — don't re-explain what a peer already knows; route a question
  to the member most likely to know.
- **Trust weighting** — weight a peer's vote by your model of its reliability *on this
  topic* (not a global score).
- **Gap detection** — the Governor sees `unaware_of` across members and assigns Scout to
  close the gap before a vote.
- **Disagreement diagnosis** — when two members conflict, compare their mental models to
  see whether it is different *evidence* or different *interpretation*.

## 5. Interface
```python
class MentalModelEngine:                       # cognition tier, peer to Council/Reflection
    def model_of(self, observer: Principal, subject: Principal) -> MentalModel
    def estimate_belief(self, observer, subject, claim) -> float
    def knowledge_gap(self, council_id) -> dict[Principal, list[ClaimRef]]
    def reliability(self, subject, topic) -> float
```
Stateless: every method is a fold over Journal + Epistemic + Identity. Rebuildable by
replay, like any projection.

## 6. Events
Consumes `claim.*`, `council.*`, `identity.*` from the Journal; emits
`mentalmodel.updated`, `mentalmodel.gap_detected`. Emissions are advisory projections,
not new sources of truth.

## 7. Single → distributed
Identical interface; cross-node it simply folds events from the distributed Journal.
Because it is a pure projection, it needs no coordination — each node can compute the
models it needs locally from the shared log.

## 8. Compatibility
New engine, flag `mental_model_engine`, default off. When off, the Council behaves as in
V2 (no peer modeling). It adds no kernel and no new source of truth — it only *reads* —
so it is the safest possible addition and a model citizen of the Freeze: a capability
delivered without inflating the kernel set.
