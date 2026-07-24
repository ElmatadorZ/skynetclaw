# Agency — Volume I · 01 — Necessary Conditions, Axioms & the Agency Graph

> Pure philosophy. Deliverables 2 (dependency graph) + 3 (minimal axioms) +
> Questions 2 (necessary conditions), 5 (minimal axioms), 8 (agency graph).

---

## Q2 · Necessary conditions for agency

Test each candidate condition by removal: if a system can lack it and still be an
agent, it is not necessary. Recovered from cybernetics, action theory, decision
theory, RL.

| Candidate | Necessary? | Test |
|---|---|---|
| **An end** (goal / value / preference) | **YES (SUPPORTED)** | remove it → only motion remains; nothing is being *brought about*; "action" collapses to event. Aristotle's final cause, cybernetic goal, decision-theoretic preference all agree. |
| **Capability to act** (a non-trivial action set that affects the environment) | **YES (SUPPORTED)** | remove effectors → a system with goals but no reach is a *desirer/observer*, not an agent. Agency is intervention; no intervention, no agent. |
| **Goal-sensitive selection** (the action taken *depends counterfactually* on the end) | **YES (SUPPORTED)** | remove it → action is goal-independent = mechanism. If the system would act identically whatever its goal, the goal is idle and there is no agency. This is the counterfactual signature (belief-science's invariance, run world→mind). |
| **Observation / feedback** (coupling action to environment state) | **YES for closed-loop; NO for the degenerate open-loop limit** | remove it → a *ballistic* system (fire-and-forget). Still minimally goal-serving but blind; treated as the limiting/degenerate case, not paradigm agency. LIKELY. |
| **Representation of the goal** (the agent *encodes* its goal vs merely *embodies* it) | **CONTESTED** | the thermostat has a setpoint it *embodies* but arguably does not *represent*. Realists: representation is necessary for genuine (vs as-if) agency. Deflationists (Dennett): no — the stance suffices. **This is the deep cut of the whole volume.** |
| **Rationality / coherence** (preferences well-ordered; VNM axioms) | **NO** | remove it → an *incoherent* agent (akratic, intransitive) is still an agent, just a bad one. Rationality is a *norm on* agency, not a condition *of* it. SUPPORTED. |
| **Consciousness / phenomenal experience** | **NO (LIKELY)** | remove it → robots/RL agents act with no evidence of experience; agency does not require the lights on. Consciousness may be necessary for *personhood*, not agency. |

**Recovered necessary core (SUPPORTED):** `{ end, capability, goal-sensitive selection }`.
Add `observation` for non-degenerate (closed-loop) agency. The two hard, contested
add-ons — *representation* and *rationality* — are what separate the *kinds* of agent
(Volume-I counterexamples), not what make something an agent at all.

## Q5 / D3 · Minimal axioms — "No agency can exist without…"

Stated as the smallest independent set. Each is a removal-test result from Q2.

- **A1 · Teleological axiom (the End).** *No agency without an end.* There must be
  some state/ordering the system aims to bring about. Without it there is motion, not
  action. — SUPPORTED. (This is the seed of the final theorem, `No Goal → No Agency`.)
- **A2 · Efficacy axiom (Capability).** *No agency without the power to act.* The
  action set must be non-empty and able to change the environment. A goal with no
  reach is a wish, not agency. — SUPPORTED.
- **A3 · Sensitivity axiom (goal-sensitive selection).** *No agency without the
  action depending on the end.* Formally: there exist goals g₁ ≠ g₂ and a state s
  such that the selected action differs — π(s; g₁) ≠ π(s; g₂). If the map is constant
  in the goal, the goal is inert and there is no agent. — SUPPORTED. This is the
  **operational, testable** axiom: it makes agency a counterfactual property, not an
  introspective one, so it applies to thermostats and humans alike.
- **A4 · Coupling axiom (Observation), for closed-loop agency only.** *No
  self-correcting agency without feedback.* Non-degenerate agents observe outcomes and
  let observation re-enter selection (the loop). Drop A4 and you keep only open-loop
  ballistic agency. — LIKELY.

**Independence:** A1–A3 are mutually irreducible — an end with no capability (A1¬A2)
is a wish; capability with no end (A2¬A1) is a tool; end + capability with no
goal-sensitive selection (A1∧A2, ¬A3) is a mechanism that happens to have a goal
bolted on but ignores it. All three are required together and none implies another.
A4 is separable (it grades open- vs closed-loop). SUPPORTED.

**What the axioms deliberately do NOT require:** representation, rationality,
consciousness, learning, or planning. Those generate *higher* agency (Volume-I
counterexamples' spectrum) but a system satisfying only A1–A3 is *already* a minimal
agent. Setting the bar here is a choice, and it is the deflationary choice — defended
against the realist alternative in the red team.

## Q8 / D2 · The agency graph (dependency structure)

The ontology as a directed graph. Read `X → Y` as "Y depends on / is produced from
X." The **W→M** spine runs left-to-right; the **M→W** return closes the loop.

```
            ┌──────────────────────── VALUE ────────────────────────┐
            │ (what matters — the root; W→M)                          │
            ▼                                                         ▼
      PREFERENCE  ──represents──▶  UTILITY                          GOAL
      (ordinal ≽)   (iff VNM axioms)  (cardinal)        (value made a target state)
                                                                     │
                                                     GOAL + OBSERVATION
                                                                     │
                                                                     ▼
                                                                INTENTION ──▶ COMMITMENT
                                                            (settled, executable aim)   (stabilized)
                                                                     │
                                              CAPABILITY ∩ CONSTRAINT bounds ▼
                                                                  POLICY  π: Obs → Action
                                                                     │
                                                                     ▼
                                                                  ACTION ──(do)──▶ [ENVIRONMENT]
                                                                                        │
                                                                                        ▼
                                                                                    OUTCOME
                                                                                        │
                                                                     ◀── OBSERVATION ◀──┘   (M→W: feedback)
                                                                     │
                                          (re-enters INTENTION / updates the world-model)
```

**The loop, minimally:** `Value → Goal → Intention → Policy → Action → Outcome →
Observation → (back into Intention)`. Every entity in the ontology is either on this
cycle or a modifier of one of its edges (Capability/Constraint bound the Policy→Action
edge; Preference/Utility encode Value).

Three structural facts this graph fixes (used later):
1. **Value is the unique root** — nothing in the graph produces Value; it enters from
   outside (the origin-of-ends problem, Volume-I theorems & open problems). Every other
   node is downstream of it. LIKELY.
2. **Observation is the unique return edge** — the only **M→W** node, the sole point
   where the world writes back into the agent. It is the shared node with the Knowing
   loop (the hinge doc). SUPPORTED.
3. **Every failure mode is a damaged edge or node of this graph** — proved
   constructively in Volume-I failure modes. This is why the graph matters: it is the
   coordinate system for the failure taxonomy.

## Falsifiers
A1–A3 fail if a clear agent lacks any one of end / capability / goal-sensitivity
(none is known). A3's counterfactual formulation fails if two agents provably
identical in behaviour across all goals are yet correctly said to differ in agency
(would show agency is not behaviourally fixed). The graph's "Value is the unique
root" fails if some genuine agent's value is *derived* from within the graph (would
resolve the origin-of-ends problem — not currently known to occur).
