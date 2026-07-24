# Agency — Volume III · 00 — The Ontology of Decision

> Pure philosophy. The question is **"What is a decision?"** — *not* "how should an
> agent decide?" Starting from Expected Utility, Bayesian decision theory, or RL would
> import a framework as an axiom; the method here is recover-first, compare-after.
> Part II, Volume III. Questions 1, 3, 4. Deliverable 1 (Ontology). Tags: SUPPORTED /
> LIKELY / CONTESTED / OPEN. Sourcing caveat: attributions recalled from decision
> theory, philosophy of action, statistics, economics; names index positions.

Vol II handed Decision a defined primitive (Value) and a marked boundary
(commensurability). This volume asks what the *act* that consumes value actually is,
before asking how to do it well.

---

## Q1 · What is a decision?

The traditions answer "how to decide well," and only philosophy of action answers
"what a decision *is*":

- **Statistical / Bayesian (Savage, Wald).** A decision is the selection of an *act* (a
  function state→outcome) or a *decision rule* (observation→action) that optimizes an
  expected criterion. — This defines a *good* decision; it presupposes what a decision
  is. Normative, not ontological.
- **Economics (VNM).** A decision reveals a preference; the chosen option maximizes
  utility. Deflationary and circular for our question (decision defined by choice,
  choice by preference).
- **Bounded rationality (Simon).** Real decisions *satisfice* — stop at the first
  option above an aspiration level. — Descriptively true, but again about *how*.
- **Philosophy of action (Anscombe, Searle, Bratman).** A decision is the *mental act
  by which deliberation terminates and an intention is formed* — the event that
  converts an open field of options into a settled aim. **This is the ontological
  answer**, and the others are theories of how to perform it well.

**Recovered core (SUPPORTED):** *a decision is the act that closes deliberation by
forming a commitment* — the transition from *many options live* to *one settled*, which
(i) terminates the deliberative field, (ii) produces an intention that guides future
conduct, and (iii) becomes a premise the agent reasons and acts *from* rather than
*about*. A "decision" that leaves every option equally open and binds nothing is not a
decision; it is continued deliberation.

**Decision is the confluence of both directions of fit (SUPPORTED, and the volume's
spine).** A decision *consumes* a **mind→world** input (Belief — how the world is, from
Part I) and a **world→mind** input (Value — how it should be, from Vol II) and *produces*
a **world→mind** output (Commitment — a settled aim). It is the unique operator where
the two halves of the stack **combine to write out**:

```
   BELIEF (M→W, Part I) ┐
                        ├─▶  [ DECISION : the act ]  ─▶  COMMITMENT (W→M, settled)
   VALUE  (W→M, Vol II) ┘
```

The hinge doc found **Observation** as the shared node where the world writes *in*
(input confluence). Vol III reveals **Decision** as the shared node where belief + value
write *out* (output confluence). **The two loops share two bridges, not one** — sense
in at Observation, commit out at Decision. This refines the hinge doc: the figure-eight
crosses itself twice.

## Q3 / D1 · The ontology of decision (nine entities)

Most are *inherited*; the volume's own contribution is **Decision** (the act) and
**Commitment** (its product). Direction of fit noted; "inh." marks import.

| Entity | Minimal definition in the decision context | Fit | Source |
|---|---|---|---|
| **State** | a way the world could be (an element of the outcome-relevant space) | — | inh. Vol I |
| **Belief** | the agent's (uncertain) representation of which state holds | **M→W** | inh. Part I |
| **Uncertainty** | the structure of the agent's ignorance over states (Q5 ladder) | **M→W** | inh. estimation |
| **Utility / Value** | the ranking of outcomes; the criterion | **W→M** | inh. Vol II |
| **Action** | an available intervention; a row in the act×state matrix | **W→M** | inh. Vol I |
| **Outcome** | the state resulting from an action (act × state) | — | inh. Vol I |
| **Constraint** | limits on the admissible action set | — | inh. Vol I |
| **Decision** | *the act that closes deliberation by forming a commitment* | operator | **NEW** |
| **Commitment** | *the settled, defeasible, binding intention the decision produces* | **W→M** | **NEW** |

**Recovered claim (SUPPORTED):** Vol III adds *no new material entities* to the world —
State/Action/Outcome/Belief/Value/Constraint all pre-exist it. It adds exactly one
*act* (Decision) and one *status* (Commitment). Decision theory is not about new things;
it is about the **operation** that combines the inherited things into a commitment. This
is why "what is a decision?" is answered by an *operator + a status*, not by an object.

## Q4 · Decision ≠ Choice ≠ Preference ≠ Action ≠ Planning

The differentiae, recovered as a strict progression (each adds one thing):

| Concept | What it is | What it adds |
|---|---|---|
| **Preference** | a standing ranking ⪰ over options (Vol II) | — (a disposition; no occasion) |
| **Choice** | a selection *on an occasion* | an occasion; but may be a mere *pick* (no deliberation, no binding) |
| **Decision** | a choice that *closes deliberation and commits* | **closure + commitment** (the differentia) |
| **Action** | the *execution* of a commitment (Vol I) | outward effect; can fail to follow the decision (akrasia) |
| **Planning** | a *structured, temporally-extended* lattice of decisions (Vol IV) | sequence/structure over many commitments |

**The load-bearing distinction (SUPPORTED):** *choice ⊋ decision.* Every decision is a
choice, but not every choice is a decision — a Buridan coin-flip is a choice that
*decides nothing* (it manufactures a selection without closing a deliberation on the
merits). **The differentia of decision is the commitment it produces**, which is exactly
Q10's hypothesis, previewed here: strip the commitment and you are left with mere choice.

Two further separations that matter downstream:
- **Decision precedes and is distinct from Action.** You can decide and not act (akrasia,
  Vol I F5) — which is only possible if the decision produced a *commitment* that the
  action then failed to honour. Akrasia is thus indirect proof that Decision ≠ Action and
  that Commitment is a real, separate stage. SUPPORTED.
- **Planning is temporally-extended deciding.** A plan is a lattice of sub-decisions /
  sub-commitments coordinated over time (Vol IV). This makes Vol IV *continuous* with
  Vol III — Planning extends the Commitment of a single decision into a structured field,
  needing no new axioms, exactly as the user predicted. LIKELY (to be shown in Vol IV).

## Falsifiers
Q1's core fails if a genuine decision is exhibited that closes no deliberation and forms
no commitment (a decision indistinguishable from continued musing). The
"decision-as-confluence" thesis fails if a genuine decision uses *no* belief input
(decides with zero representation of the world) or *no* value input (VT1 already forbids
the latter). Q4 fails if choice and decision are shown coextensive (every choice a
decision) — the Buridan pick is the standing counterexample.
