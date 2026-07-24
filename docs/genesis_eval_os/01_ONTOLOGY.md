# 01 — Minimal Ontology

> Design only. Deliverable 10 (placed early — the graphs and state machine are
> defined over these entities). The SMALLEST set of entities and relations that
> can express continuous epistemic evaluation. Evidence-first: every entity that
> asserts anything carries provenance + a refutation condition.

Design rule applied to the ontology itself: an entity is admitted only if a real
CEE function needs it. No entity exists "for completeness."

---

## The nine entities

| Entity | Is | Provenance? | Falsifiable? |
|---|---|---|---|
| **Event** | one observed runtime fact (a tool ran, a file changed, a latency, a failure) | it IS the observation (source-tagged) | n/a — raw observation |
| **Claim** | an assertion the system output ("the file is X", "38 failures") | must cite Evidence (K1) | yes — refuted by contradicting Evidence |
| **Evidence** | an Event promoted to support/contradict a Claim | the Event id + tool/source | n/a |
| **Belief** | a stable disposition the system holds, with Confidence | Evidence edges (≥1) | yes — its stored refutation condition (K3) |
| **Confidence** | a value in [0,1] on a Belief, WITH history + why-record | each value cites the Evidence that set it (K2) | yes — the why is checkable |
| **Hypothesis** | a candidate explanation under test (competing set) | the anomaly/Event that spawned it | yes — the evidence whose absence rejects it |
| **Unknown** | a named gap: a question with no sufficient Evidence yet | the query + why-unresolved | yes — resolved when Evidence arrives |
| **Failure** | a confirmed violation of an invariant/expectation | the Event(s) + detector | yes — reproduction command |
| **Regression** | a Failure frozen as a permanent probe | the Failure id + probe | yes — it re-runs |

Nothing else is primitive. Risk, Coverage, "state" are *derived* (§derived).

## The warrant lattice (the spine — reused from the pyramid + belief-science)

Every Claim/Evidence carries a tag ordered by warrant:

```
observed ≻ retrieved ≻ computed ≻ inferred ≻ assumed ≻ unknown
   (direct)  (tool)     (derived)  (reasoned) (guessed)  (none)
```

- The lattice is a *partial order of trust*, not of truth. It answers "how do you
  know", the failure-report field that was all-UNKNOWN.
- **The gate lives here (recovered from pyramid):** a Claim whose *claimed* tag is
  higher than its *evidenced* tag is an **overclaim** — the live fabrication
  detector. K1 forces the floor: no evidence ⇒ tag pinned to `unknown`.
- This lattice is exactly the belief-science result applied operationally: a Belief
  is `observed`-grade only where the invariance is directly exploitable; otherwise
  it degrades down the lattice. SUPPORTED.

## Core relations (the edges the graphs are built from)

- `Claim  —cites→  Evidence` (provenance; K1)
- `Evidence —supports|contradicts→ Belief` (grounding / disconfirmation)
- `Belief —confidence@t, why→ Evidence` (K2: every confidence value points at its cause)
- `Belief —depends_on|contradicts→ Belief` (belief dependency; propagation on revision)
- `Hypothesis —predicts→ Evidence` (what we'd see if true) and `—rejected_by→ Evidence`
- `Unknown —closes_via→ (tool | observation | experiment)` (the evidence plan)
- `Failure —caused_by→ Hypothesis —fixed_by→ Change —guarded_by→ Regression`

## Derived state (NOT primitive — computed from the above)

The user's "epistemic / confidence / unknown / risk / coverage states" are
projections, not stored entities:

- **Belief state** = the set of Beliefs + Confidences (from the store).
- **Unknown state** = open Unknowns weighted by how much they block current work.
- **Risk state** = f(open high-impact Unknowns, low-Confidence Beliefs being acted
  on, near-gate metrics). A live number, always explainable to its inputs.
- **Coverage state** = fraction of the active mission's claims that trace to
  `observed`/`retrieved` Evidence vs `inferred`/`assumed`. "How grounded am I right
  now." SUPPORTED as computable.

Keeping these derived (not stored) is the minimality discipline: one source of
truth, everything else a view — so they can never silently disagree.

## Falsifiability schema (applies to every asserting entity — K3)
Every Belief, Hypothesis, Anomaly, Failure stores a record:
```
{ assertion, evidence[], refutation_condition, tag, confidence, why[] }
```
`refutation_condition` is mandatory and machine-checkable where possible ("recurs
within baseline", "file byte-differs", "tool exit ≠ 0"). An entity without it is
inadmissible — the ontology cannot represent dogma. SUPPORTED (this is what makes
the whole OS falsifiable rather than a belief engine that merely feels rigorous).
