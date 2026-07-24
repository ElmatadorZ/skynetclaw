# Agency — Volume II · 01 — Axioms, the Value Graph & Terminal vs Derived Goals

> Pure philosophy. Deliverables 2 (dependency graph) + 3 (axioms) + Question 6
> (terminal vs derived goals). The value ontology as a directed structure, its minimal
> axioms, and how it plugs into the Vol I agency graph.

---

## The axioms of value ("no value structure without…")

Recovered as removal-tests, mirroring Vol I's method.

- **V1 · Ordering axiom.** *No value without a ranking.* Value is at minimum a partial
  order ⪰ over states/outcomes: for value to *do anything*, some states must rank above
  others. A "value" flat over all states is inert — indistinguishable from no value.
  SUPPORTED. (This is the seed of the final theorem, `No Value → No Decision`.)
- **V2 · Grounding axiom (terminality).** *No value structure without at least one
  terminal value.* By Aristotle's regress (Vol II·00 Q5), instrumental value borrows
  from what it leads to; a purely instrumental structure never repays the loan.
  Therefore the order must have a *non-instrumental floor*. SUPPORTED.
- **V3 · Derivation axiom.** *Instrumental value is not free — it is computed.*
  Instrumental value = terminal value propagated *backward through a causal model*
  (what-leads-to-what). No causal model → no instrumental value, only terminal value
  and noise. LIKELY. (This is the edge where Part I's causation feeds Part II.)
- **V4 · Fidelity axiom (representation).** *Utility represents value only under the
  VNM axioms; reward tracks value only as a fallible sensor.* Both are
  *representations*, exact only conditionally. Maximizing a representation is safe only
  to its fidelity. SUPPORTED (it is just VNM + measurement error, imported).

**Independence.** V1 (there is an order) and V2 (the order has a terminal floor) are
distinct — an order could in principle be an infinite instrumental regress (V1 without
V2), which V2 forbids as ungrounded. V3 (instrumental value is derived) and V4
(representations are conditional) are separable add-ons about *structure* and
*encoding*. The irreducible core is **V1 + V2**: *a grounded ranking*. SUPPORTED.

**What the axioms deliberately do NOT settle:** *which* states are terminally valued
(that is ethics, out of scope), *where* terminal value comes from (Q9, open), and
whether value is complete/commensurable (Q8, often no). The ontology fixes the *form*
of value, not its *content* — exactly as Part I's Belief volume fixed the form of a
belief, not which beliefs are true.

## D2 · The value graph (internal structure + plug-in to Vol I)

```
   [ external source ]  ← evolution / construction / reflective endorsement / (authority: OPEN, Q9)
          │  (the arrow with no tail — Vol I T5, made precise: it is TERMINAL value)
          ▼
   ╔══════════════════╗
   ║  TERMINAL VALUE  ║   V2 floor · intrinsic/final · W→M · the rootless root
   ╚══════════════════╝
          │  + causal/world-model  ◀───────────────  [ from PART I: causation / intervention ]
          ▼            (V3: backward propagation)
   INSTRUMENTAL VALUE   derived · computed · W→M
          │
          ▼
        GOAL            a reachable state selected by value (argmax-ish)   ──▶ [ into VOL I graph ]
          │
          ▼
     PREFERENCE  ⪰   ──represents (iff VNM, V4)──▶   UTILITY
          ▲
          │  estimates / measures (M→W, fallible — V4)
      REWARD           the value-sensor · gameable → hacking (F3) / wireheading (F4)
          ▲
          └──────────  [ from the world: OUTCOME observed ]  ◀── (feedback, Vol I loop)
```

Read top-to-bottom as the **W→M derivation** (source → terminal → instrumental → goal →
preference → utility); read bottom-up on the Reward branch as the **M→W measurement**
(outcome → reward → estimate of value-achievement). The value node is itself a
*miniature figure-eight*: it derives downward (what to pursue) and senses upward (how
well pursuit is going), meeting the world at Goal (out) and Reward (in).

**Three structural facts (used later):**
1. **Terminal value is the graph's only rootless node** — Vol I T5 localized here
   exactly. Everything else in value is *derived* (instrumental, goal, preference,
   utility) or *sensed* (reward). SUPPORTED.
2. **Reward is the only M→W node in the value graph** — the value-axis twin of
   Observation; the single point where the world writes back a value-signal, and hence
   the single attack surface for hacking/wireheading. LIKELY.
3. **Part I plugs in twice** — at the *causal model* (deriving instrumental value, V3)
   and at the *outcome* feeding reward. Value is not sealed off from knowing; it *uses*
   knowing to compute means, while its terminal floor stays knowing-independent (Hume).
   SUPPORTED.

## Q6 · Terminal vs Derived goals

The goal-level mirror of Q5 (terminal vs instrumental *value*).

- **Terminal goal** = a state pursued for its own sake — the instantiation of a
  terminal value.
- **Derived goal (subgoal)** = a state pursued *as a means* — generated by *means-end
  reasoning* (Planning, Vol IV) from a terminal goal + causal model. Derived goals are
  *computed*, not held: change the causal model and they change; achieve the terminal
  goal and they dissolve.

**Instrumental convergence (Omohundro / Bostrom, SUPPORTED as a structural claim).**
Certain derived goals — self-preservation, resource acquisition, goal-integrity,
capability-gain — are generated by *almost any* terminal goal, because they are
instrumentally useful for nearly anything ("you can't fetch the coffee if you're dead").
This is a fact about the *derivation*, not about content: **derived goals can be
dangerous even when the terminal goal is benign**, because convergence is
goal-agnostic. This is where AI-safety enters the ontology *honestly* — not as ethics,
but as a structural property of the terminal→derived edge. It also refutes the naive
hope that a benign terminal value guarantees benign behaviour: the *derivation* has its
own attractors. LIKELY→SUPPORTED.

**The recovered asymmetry (SUPPORTED):** terminal goals/values are *given* (the open
root); derived goals/values are *entailed* (terminal + causal model). So the entire
value structure below the terminal floor is, in principle, **deducible** — value theory
is *determinate given the terminal floor and a world model*, and *indeterminate exactly
at the floor*. This is the same shape as every prior volume: computable in the middle,
open at the foundation.

## Falsifiers
V1 fails if a genuine agent decides using a value flat over all outcomes (an inert
value that still discriminates — a contradiction, so its failure would be deep). V2
fails if a grounded, non-regressive value structure exists with no terminal floor. V3
fails if instrumental value can be assigned with no causal model at all. The
instrumental-convergence claim fails if some broad class of terminal goals provably
generates *none* of the convergent subgoals (would bound the danger structurally).
