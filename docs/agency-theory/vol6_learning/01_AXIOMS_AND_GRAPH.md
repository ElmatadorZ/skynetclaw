# Agency — Volume VI · 01 — Necessary Conditions, Axioms, Graph & the Credit-Assignment Crux

> Pure philosophy. Deliverables 2 (graph) + 3 (axioms) + Questions 2 (necessary conditions)
> and 5 (the non-ergodic credit-assignment crux — where the Part I↔II symmetry is re-tested).

---

## Q2 · Necessary conditions for learning

Removal-tests, distinguishing learning from memory / control / a fixed program.

| Candidate | Necessary? | Test |
|---|---|---|
| **A mutable disposition** | **YES (SUPPORTED)** | nothing to change → a fixed program; a calculator does not learn |
| **Outcome-driven feedback** | **YES (SUPPORTED)** | no signal from results → no basis to change; disposition-change from nothing is drift, not learning |
| **Credit assignment** | **YES (SUPPORTED — the differentia)** | feedback without *knowing what to change* → you cannot update the right component; superstition is credit *mis*-assignment, and it is the failure that proves the node is real |
| **Cross-episode retention (memory)** | **YES (SUPPORTED)** | change that does not persist past the episode is in-moment adaptation (control), not learning |
| **Stationarity (uniformity of nature)** | **YES for *justified* learning; contested as constitutive** | if the past does not constrain the future *at all*, no outcome licenses any future disposition — Hume. Learning can still *occur* under non-stationarity; it just isn't *justified* (Vol VI·04) |
| **Improvement / optimality** | **NO** | a *bad* learner still learns (overfit, superstition). Optimality is a norm, not a condition — the recurring result across Vols I–V |

**Recovered necessary core (SUPPORTED):** `{ mutable disposition, outcome-feedback, credit
assignment, retention }`. Add **stationarity** for learning to be *justified* rather than
merely *occurring* (Q5, Q10). The volume's own contribution is **credit assignment** — the
node that turns "something happened" into "change *this*."

## Axioms of learning ("no learning without…")

- **LA1 · Plasticity.** *No learning without a mutable disposition.* The seat of change must
  exist (weights, a policy table, or — when weights are frozen — an external store that
  changes future inputs). SUPPORTED.
- **LA2 · Feedback.** *No learning without outcome-driven signal.* SUPPORTED.
- **LA3 · Credit.** *No learning without assigning the outcome to a disposition-component.*
  The differentia and the seed of the final theorem. SUPPORTED.
- **LA4 · Retention.** *No learning without persistence across episodes.* SUPPORTED.
- **LA5 · Stationarity (for justified learning).** *No **warranted** generalization without
  some uniformity between past and future.* Hume: this cannot itself be learned without
  circularity — the open foundation. SUPPORTED (as the condition) / OPEN (as groundable).

**Independence.** LA1–LA4 are irreducible together: a plastic disposition with no feedback
(LA1¬LA2) drifts; feedback with no credit (LA2¬LA3) cannot target the change; credit with no
retention (LA3¬LA4) forgets it. LA5 is separable — it is what divides *learning-that-occurs*
from *learning-that-is-warranted*. SUPPORTED.

## Q5 · The credit-assignment crux — where the symmetry breaks (again)

**The Part I return-arc analog of Learning is belief revision / estimation-update** (updating
belief from new evidence — the Bayesian seat). Testing `Learning ≅ Belief-revision`:

- **Knowing-side learning (belief revision) is over a *fixed* world.** You can **re-observe**
  — the evidence is repeatable, so counterfactuals are testable and **credit assignment is
  tractable** (which hypothesis the evidence supports is checkable by looking again). The
  world holds still while you learn about it — *ergodic* (Vol IV).
- **Acting-side learning (policy/value update) is over a *spent* world.** You **cannot
  re-act the same state** (Vol V irreversibility). You see the outcome of what you **did**,
  **never** the outcome of what you **didn't** — the counterfactual is unobservable because
  the prior state is gone. So **credit assignment is under-determined in principle**: this is
  the *fundamental problem of causal inference* (you never see both potential outcomes) and
  RL's off-policy / counterfactual problem.

**Verdict (SUPPORTED): `Learning ≅ Belief-revision` is a HOMOMORPHISM that breaks at credit
assignment — and the kernel of the break is, once again, the irreversibility of action.**
Same seam as Vol IV (`Planning ≅ Inquiry`) and Vol V (the two world-boundaries): to learn
about a world you only *observe*, you can re-check; to learn about a world you *changed*, the
evidence for the road-not-taken is destroyed by the taking. **Acting-side learning is
strictly harder than knowing-side learning, by exactly the non-ergodicity Vol IV named.** The
symmetry holds in form (both revise a disposition from outcome) and diverges in tractability
(credit is checkable vs inferable-only). SUPPORTED, and it predicts why real agents need
*exploration* (deliberately vary actions to recover the counterfactuals a spent world hides).

## D2 · The learning graph

```
        ACTION ──▶ [world, irreversible] ──▶ OUTCOME
                                               │
                                               ▼
                                          FEEDBACK  (outcome made informative: error/reward/observation)
                                               │
                          ┌──── MODEL ────────┤  (a predictor lets you credit without re-acting —
                          │  (Part I)          │   the partial escape from the non-ergodic crux)
                          ▼                     ▼
                     CREDIT ASSIGNMENT  ◀── the crux: which disposition-component caused this?
                          │   (under-determined on the acting side — Q5)
                          ▼
                     UPDATE RULE ──▶ DISPOSITION (Value II / Policy III / Belief I)  ──▶ next ACTION
                          ▲                                   │
                     MEMORY / TRACE ────────────────────────┘  (retention across episodes, LA4)
                          ▲
                     EXPLORATION ── generates outcomes worth crediting (recovers hidden counterfactuals)
```

**Three structural facts:**
1. **Credit assignment is the unique hard node** — everything else is transport (feedback in,
   update out, memory holds). The theory's weight sits here (Q5). SUPPORTED.
2. **A Model is the only partial escape from the non-ergodic crux** — if you can *predict*
   outcomes, you can credit counterfactuals *without re-acting* (model-based learning; Part
   I's Belief feeding Part II again). But the model is itself learned over the spent world →
   the escape is partial, never total. LIKELY.
3. **Learning feeds back into *every* forward node** — it revises Value (II), Policy/Commitment
   (III), Plan-priors (IV), and Belief (I). It is the meta-operation that closes the loop
   onto the whole forward arc. SUPPORTED.

## The frozen-weight corollary (LA1 applied to SkynetClaw)
LA1 requires a mutable seat. If the disposition-seat (model weights) is **frozen**, learning
must relocate to a *different* mutable seat: a **persistent external memory that changes
future inputs** (the prompt/context that steers the frozen model). This is not lesser
learning — by the ontology it *is* learning (cross-episode, outcome-driven, retained
disposition-change), with the disposition living in the store rather than the weights. **The
runtime bridge this volume owes is therefore a proprioceptive memory** — the system learning
its own competence from operational outcomes and feeding it forward. SUPPORTED (follows from
LA1 + the frozen seat).

## Falsifiers
LA3's necessity fails if genuine learning occurs with provably no credit assignment (blind
disposition-change that still counts as learning). The homomorphism-break (Q5) fails if
acting-side credit assignment is shown as tractable as knowing-side (counterfactuals of a
spent world made checkable without re-acting or a model). The frozen-weight corollary fails
if the frozen model learns with no external mutable store.
