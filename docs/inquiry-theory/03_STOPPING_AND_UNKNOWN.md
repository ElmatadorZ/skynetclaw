# 03 — The Stopping Rule & Unknown Reduction

> Pure epistemology. Deliverables 6 (Stopping Rule) & 7 (Unknown Reduction) +
> Question 8 (when to stop asking). This file also states the **duality** that
> closes the theory stack: Inquiry is the forward pass, Warrant the backward pass,
> and the Stopping Rule is where they meet. Recovered, falsifiable, tagged.

---

## D7 · Unknown Reduction — what "reducing the Unknown" actually means

From file 02, the Unknown is not a single decreasing scalar (answers evoke new
questions — Theorem E). So "reducing the Unknown" is precise only *relative to a fixed
question or target*:

- **Local reduction (SUPPORTED):** for a fixed target X, answering questions reduces
  H(X) monotonically in *realized* information (each true answer can only inform or
  leave X's entropy unchanged, never raise it — conditioning does not increase
  expected uncertainty). So *within a fixed question*, inquiry converges.
- **Global non-reduction (LIKELY):** across the *evoked* frontier, the total open
  question-count can rise (Theorem E). Progress on X coexists with growth of the
  question-space. The two are not in tension — one is depth, the other breadth.
- **Consequence for measurement:** "how much Unknown remains" must be indexed to a
  target and a question-set; an unindexed "Unknown %" is ill-defined (the same lesson
  as Warrant's "no measurement without a frame"). SUPPORTED.

## Q8 / D6 · The Stopping Rule — when to stop asking

Recovered: stopping is an **optimal-stopping / sequential-analysis** problem, and the
correct rule is the *earliest* trigger among four conditions:

1. **Sufficiency (warrant threshold).** Stop when the warrant on the target reaches
   the level the *decision/aim* requires. This is the direct hand-off to Warrant
   theory: inquiry serves a purpose π, π sets a required warrant grade, and once that
   grade is met, further questioning has no value *for that purpose*. SUPPORTED
   (decision-theoretic; the required grade is π-relative, not absolute).
2. **Marginal VoI < cost (Howard).** Stop when the best remaining askable question's
   expected value of information falls below its cost. The forward-looking economic
   stop: keep asking only while the next question pays for itself. SUPPORTED.
3. **Exhaustion / no discriminator.** Stop when *no obtainable* question has positive
   relevant EIG — every remaining question is answered, dead (file 04), or
   non-discriminating (underdetermination). SUPPORTED.
4. **Sequential-boundary (Wald SPRT).** In a stream of evidence, continue while the
   accumulated warrant sits between an accept and a reject threshold; stop when it
   crosses either. SUPPORTED (the optimal test for a fixed error budget).

> **Stopping Theorem.** The rational stop = min-time over {sufficiency, VoI<cost,
> exhaustion, sequential-boundary}. Whichever fires first ends the inquiry.
> — SUPPORTED as the recovered synthesis; each disjunct is an established result, and
> their minimum is the earliest defensible stop.

**The critical case — stopping AT Unknown (the load-bearing result).** If *exhaustion*
(3) or *no-discriminator* fires while *sufficiency* (1) has NOT been reached, the
correct terminal state is **UNKNOWN**: inquiry has done all it can and the warrant is
still below the decision threshold. This is not failure — it is the *only warranted
output*. It derives, from the Inquiry side, exactly the Warrant-theory result
(Theorem U): abundant questioning can terminate honestly at UNKNOWN when no obtainable
question discriminates. SUPPORTED, and it is the philosophical licence for a system to
answer "I cannot know this yet" as a *completed*, not a *failed*, inquiry.

**The two stopping vices (recovered, symmetric — the same pair as file 01):**
- **Premature stop (under-inquiry):** halting while a positive-VoI, in-budget,
  discriminating question remains — deciding on avoidable ignorance. The failure-twin
  of the lazy-UNKNOWN.
- **Endless stop (over-inquiry):** never triggering, chasing marginal questions past
  the point VoI < cost — the frontier-thrash of file 02. The failure-twin of idle
  curiosity.
The Stopping Theorem's *minimum* is exactly the line between them. LIKELY.

## The duality that closes the stack (recovered synthesis)

The lineage's two directional theories are duals:

```
   INQUIRY  (forward)                          WARRANT  (backward)
   given a TARGET, what question              given EVIDENCE, is there
   most reduces the Unknown per cost?  ──▶     enough reason to accept?
        │                                              ▲
        │ generates evidence                           │ evaluates evidence
        ▼                                              │
        └──────────── the STOPPING RULE ───────────────┘
             stop asking ⇔ warrant suffices for the aim
                        OR no obtainable question would raise it
```

- **Inquiry without Warrant is aimless** (no criterion for "enough" → never stops or
  stops arbitrarily). **Warrant without Inquiry is passive** (evaluates whatever
  arrives, never seeks the missing evidence). Neither is complete alone.
- **The Stopping Rule is the hinge:** it reads the Warrant state (condition 1) and the
  Inquiry state (conditions 2–3) and fires on the first. It is the single point where
  "what should I ask?" and "do I now know?" become one question.
- **The composite objective** — *maximize warrant on the aim, per unit cost, and stop
  at the min-trigger* — is the recovered, theory-derived definition of a rational
  inquiring agent. It owes nothing to heuristics: it falls out of Information Theory
  (file 01) + the Dependency Graph (file 02) + Warrant's threshold + the estimation
  cost axis. SUPPORTED as a synthesis of the recovered parts.

This is what the stack was building toward: not a system that answers questions, but
one whose *questioning policy* and *acceptance threshold* are two faces of one
epistemic law — ask until warrant suffices or no question would help, then stop, at
knowledge or at an honest Unknown.
