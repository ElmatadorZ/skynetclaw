# 02 — Ordering & the Question Dependency Graph

> Pure epistemology. Deliverables 4 (Dependency Graph) + Question 6 (what to ask
> first / next). Recovered, falsifiable, tagged.

---

## Q9 / D4 · The Question Dependency Graph

Questions are not independent; inquiry has structure. Recovered edge-types (nodes =
questions):

- **Presupposition edge (Q_b ⟶presupposes⟶ Q_a).** Q_b's presupposition is settled
  only by an answer to Q_a; you cannot sensibly ask "which fault caused the crash?"
  before "did it crash?". These edges impose a *partial order* — a hard ordering
  constraint (you may not ask into a presupposition you have not secured). SUPPORTED
  (Belnap; the presupposition structure of questions).
- **Decomposition edge (Q ⟶ {q₁…qₙ}).** A "principal question" decomposes into
  operational sub-questions whose answers compose into its answer (Hintikka's
  interrogative model: the big question is answered by a strategy over small ones).
  SUPPORTED.
- **Evocation edge (Q_a + background ⟶evokes⟶ Q_b).** An answer to Q_a, against a
  declarative background, *raises* a new question Q_b that did not exist before —
  Wiśniewski's **erotetic implication**: questions imply questions. SUPPORTED, and
  the source of inquiry's growth (below).
- **Contrast edge.** For why-questions, changing the contrast class yields a *sibling*
  question (van Fraassen). SUPPORTED.

**The central structural result — inquiry EXPANDS, it does not merely shrink.**
Naively, answering questions reduces the Unknown, so the question-set should shrink to
empty. But the **evocation edge** means answering a question *creates* new questions:
each answer redraws the frontier of what can now be asked. Therefore:

> **Theorem E (Expanding Frontier).** The question graph is not a shrinking tree but a
> graph that closes locally and expands globally. Knowledge growth *increases* the
> number of well-posed questions available (you can only ask what you know enough to
> frame — file 00, I4). The known-unknown boundary grows with knowledge.
> — LIKELY (recovered from erotetic implication + the history of science: every major
> answer opened more questions than it closed). Falsifier: a domain where answering
> questions provably evokes none — a *closed* inquiry — which pure/finite formal
> systems may approximate but empirical domains do not.

Corollary: an inquiry can be *progressing* (reducing the Unknown on its current
questions) while its total open-question count *rises* — and this is health, not
failure (Kuhn: a fertile paradigm generates more puzzles; Laudan: problem-generation
is a mark of progress). The "amount of Unknown" is therefore not a single decreasing
number; it is a *moving frontier*. LIKELY. (This is the erotetic counterpart of
Warrant's non-monotonicity: there, more evidence can lower warrant; here, more answers
can raise the question-count.)

## Q6 · Ordering — what to ask first, next

Given the dependency graph and the quality metric (file 01), the ordering problem is
a **sequential design / optimal-search** problem. Recovered:

- **Hard constraints first: the presupposition partial order.** You may not ask a
  question before securing its presupposition. This *topologically sorts* part of the
  graph — non-negotiable, prior to any value calculation. SUPPORTED.
- **Greedy (myopic) rule: max relevant EIG-per-cost next.** Among askable questions,
  pick the highest quality (file 01). Simple, and the default of "twenty questions."
  SUPPORTED as a *baseline*.
- **Greedy is provably suboptimal in general.** A question with low *immediate* gain
  can *unlock* a high-gain follow-up (it settles a presupposition, or its answer
  sharpens the prior so the next question's EIG jumps). Optimal ordering requires
  *lookahead* over the dependency graph — the value of a question includes the value
  of the questions it enables. SUPPORTED (this is the non-myopic experimental-design /
  Hintikka strategic-questioning result; myopic active learning is a known
  approximation, not the optimum).
- **The strategic frame (Hintikka).** Inquiry is a game against nature: the questioner
  chooses questions, nature answers truthfully within the presupposition, and the
  *strategy* (the policy over the graph), not any single question, is what is
  evaluated. The right first question is the first move of the best strategy, which
  may look locally weak. SUPPORTED.

**Recovered ordering principle:** *respect the presupposition order (hard); then follow
the policy that maximizes expected cumulative relevant information per cost with
lookahead over evoked questions — not the locally greediest question.* The gap between
greedy and optimal is exactly the value a question adds by *opening better questions*
— which is why a great question is often not the most immediately informative one, but
the one that reshapes the whole subsequent inquiry. LIKELY.

## Two ordering pathologies (recovered)
- **Depth-trap:** chasing one decomposition branch to exhaustion while a cheap sibling
  question would have collapsed the whole subtree (no lookahead across branches).
- **Frontier-thrash:** letting every evoked question reopen the agenda, so inquiry
  never converges (the expanding frontier without a stopping discipline — file 03).
The dependency graph makes both visible; the stopping rule (file 03) bounds the
second. LIKELY.
