# 02 — Composition & Conflict

> Pure epistemology. Deliverables 4 (Composition) & 7 (Conflict) + Questions 7
> (how warrants combine) & 8 (how two warrants that clash are adjudicated).
> Recovered, falsifiable, tagged.

---

## Q7 / D4 · Composition — how do warrants combine?

**Recovered thesis: there is no single universal composition operator. The correct
operator is a function of (i) warrant TYPE, (ii) the DEPENDENCE structure between
the grounds, and (iii) whether the grounds AGREE or CONFLICT.** Choosing one
operator globally is a category error. SUPPORTED (each operator below is the
established model for its regime).

The candidate operators, and their proper domain:

| Operator | Combines warrant when… | Regime |
|---|---|---|
| **Min (weakest-link)** | grounds form a *serial chain* (a proof, a testimony chain): the whole is only as warranted as its weakest link | deductive chains, transmission (file 03) |
| **Probabilistic (Bayesian)** | grounds are *independent evidence* for the same proposition: they accumulate by conditionalization; warrant ≈ posterior | independent empirical/statistical evidence |
| **Noisy-OR / accumulation** | multiple *independent fallible indicators* each raise support; convergent independent lines add more than their max | corroboration, consilience |
| **Dempster–Shafer** | grounds carry explicit *ignorance* (mass on "don't know"), not just probabilities; combines belief + plausibility, keeps UNKNOWN first-class | evidence under partial ignorance |
| **Ordinal / ranking (Spohn)** | warrant is a *rank order*, not a number; combine by rank arithmetic | qualitative degrees, the warrant lattice |
| **Argumentation graph (Dung)** | grounds *attack and defend* each other; warrant = the status of a node after defeat propagation | conflict, defeasible reasoning (Q8) |

Two structural results (recovered):

- **Dependence is the hinge.** Independent lines → accumulate (Bayesian/noisy-OR);
  dependent/serial → min. Treating dependent evidence as independent is the classic
  *double-counting* fallacy — it manufactures unwarranted confidence (the same error
  a naive sum makes). SUPPORTED.
- **Consilience > accumulation of like-kind.** Independent lines of *different type*
  (empirical + experimental + statistical) converging on one claim confer more
  warrant than the same total mass of one type (Whewell's consilience). Warrant is
  not fungible by quantity; its *diversity* matters. LIKELY.

**Falsifier:** exhibit one operator that correctly composes warrant across chains,
independent evidence, ignorance, and conflict without regime-switching. None is
known; a success would refute the no-universal-operator thesis.

## Q8 / D7 · Conflict — adjudicating two warrants that clash

When ground g₁ warrants p and g₂ warrants ¬p (or undercuts g₁), adjudication is
**defeat resolution**, recovered in three layers:

**Layer 1 — kind of defeater (Pollock).**
- *Rebutting*: g₂ is direct evidence for ¬p. Resolve by comparative weight on the
  total evidence (A6).
- *Undercutting*: g₂ attacks the link g₁→p without bearing on p itself (e.g. "the
  lighting is red" undercuts "it looks red ⇒ it is red"). An undercutter does not
  need to outweigh; it *dissolves* the warrant. **Undercutting is the more powerful
  and the more overlooked** — it defeats without counter-evidence. SUPPORTED.

**Layer 2 — the warrant ordering (lattice).**
Where the two grounds are of different *kind*, higher-warrant kinds defeat lower on
the a priori/observation lattice:
```
proof ≻ direct observation ≻ controlled experiment ≻ statistics ≻ inference ≻ testimony ≻ assumption
```
A mathematical proof defeats a contrary intuition; a direct observation defeats a
contrary report. (This is the operational core the mission's whole lineage kept
reaching for.) LIKELY — the ordering is defeasible, not lexical: a mountain of
observation can overturn a *suspected* proof (which flags a hidden error).

**Layer 3 — global status (argumentation semantics, Dung).**
Local weighing under-determines multi-argument conflict. Model the arguments as a
graph (nodes = arguments, edges = attacks); warrant = membership in an *extension*
(grounded = the sceptical core that survives all attacks; preferred = maximal
consistent defensible sets). A belief is warranted iff its argument is in the
grounded extension after propagation. SUPPORTED (Dung's semantics are the standard
formal model of defeasible conflict).

**The tie case — equipollence.** When neither ground defeats the other and no
higher-order consideration breaks the tie, the *warranted* attitude is **suspension**,
not a coin-flip (Pyrrhonian equipollence; Sextus). A forced choice between
equipollent grounds is itself unwarranted. SUPPORTED. → This is the bridge to Q9:
conflict can *manufacture* a warranted UNKNOWN even amid abundant evidence.

### Recovered adjudication procedure (the minimal algorithm)
1. Classify each defeater (rebutting / undercutting). Undercutters dissolve; they do
   not need to outweigh.
2. On rebutting conflict, weigh on **total** evidence (A6), using the kind-ordering
   where kinds differ.
3. Propagate through the argument graph; keep the grounded extension.
4. If the survivors are equipollent → **suspend** (warranted UNKNOWN), do not force.

Every step is falsifiable by a case where it yields the intuitively wrong verdict;
the procedure is offered as the best recovered synthesis, not a proven optimum
(LIKELY).
