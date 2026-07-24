# The Genesis Paradigm — what SkynetClaw *is*

> **Status: RATIFIED (2026-07-09).** No longer a proposal — the governing principle of the
> system. Its central law ("no capability without its governing invariant") is now enforced
> as a measured runtime invariant: the eval scoreboard's `paradigm_capability_coverage` case
> FAILS if any registered tool lacks a governance classification, so a capability cannot ship
> without its invariant without the scoreboard catching it. Ratification also closed the 7
> orphan tools that existed at the time (they were silently deny-by-default) → 100% coverage.
>
> Written from first principles + systems thinking over what was directly observed building
> this system. Its purpose is to resolve the one tension that produces every systemic symptom:
> **is SkynetClaw a reliable local agent, or a research lab for theories of agency?** The
> answer is that this is a false choice, and naming why is the highest-leverage move available
> (Meadows: a system's *goal* is its highest actionable leverage point).

---

## The observed tension (evidence, not theory)

SkynetClaw accreted two identities that pull apart:
- **A reliable local agent** — acts on files/web/tools/Telegram, driven by a weak local model.
- **A research lab** — 14 recovered theory volumes (Knowing ×9, Agency ×5), evaluation
  frameworks, a Theory of Warrant made runtime (CEE).

Symptoms of the unresolved pull (all seen this session): capability outran reliability
(a reproduced security P0; evidence lost under context compression; a sprawling TCB); the
*feature freeze* — a rule meant to hold the line — did not hold (a whole browser subsystem
landed mid-freeze). Systems thinking: **a rule always loses to the structure it fights.**
The freeze was the right instinct aimed at the wrong leverage level.

## The resolution: the lab *is* the reliability supply chain

The two identities are not rivals — they are one enterprise seen from two ends. The binding
constraint is fixed: **a weak local brain** (small model, 16k context, limited GPU). The
whole game is *extracting reliable capability from a weak brain*. And the only durable way
observed to raise reliability was **to turn a recovered theory into an enforced runtime
invariant** — the CEE bridge is the proof of concept: the Theory of Warrant's C1 ("assert
nothing beyond warrant") became `warrant_check.py`, a runtime detector that fires on every
completion. Theory → bridge → invariant. That pipeline *is* the reliability supply chain,
and the "research lab" is its factory.

So the paradigm, in one sentence:

> **SkynetClaw is a local, sovereign agent that earns each capability by first building the
> reliability to wield it — and reliability is manufactured by turning recovered theory into
> enforced runtime invariants.**

## Three commitments (the WHY, the HOW, the WHAT-IS-MISSING)

1. **Sovereignty (the WHY it is local at all).** Own the brain and the data; no cloud
   dependency. The weak-model constraint is the *price* of sovereignty — and the entire
   scaffolding enterprise is the act of paying that price well. This is a first-class value,
   not an accident of hardware.
2. **Reliability-before-capability (the HOW).** The operating law that makes the freeze
   *structural* instead of a rule: **no capability ships without its governing invariant.**
   A new actuator (tool) is incomplete until it carries its sensor (an evaluation), its
   governor (a gate), and its learning hook (a way its outcomes update future behavior). The
   stealth browser is the cautionary tale: it shipped its actuator and gate, but not its
   evaluation or learning hook, and its gate was bypassable — capability without its full
   governing invariant.
3. **Closed-loop (the WHAT-IS-MISSING).** An agent is a loop: `perceive → decide → act →
   outcome → learn → govern → (back)`. SkynetClaw built the **forward arc** (perceive→decide
   →act = Part I + Agency Vol I–V, with reality-grounding + governance) and left the
   **return arc** (outcome→learn→govern = Agency Vol VI–VII) unbuilt. **The system is an open
   loop.** Every systemic gap — no learning, no continuous evaluation, theory unused at
   runtime — is the *same* missing return arc seen from a different side.

## What this paradigm decides (the roadmap falls out of it)

- **The next work is closing the return arc**, not extending the forward arc. Reliability
  (the return arc) must catch up to capability (the forward arc) before more capability is
  added — because adding actuators to an open loop widens the very gap that produced the P0.
- **Every theory volume owes a runtime bridge.** A volume that never becomes an invariant is
  lab output that never entered the supply chain — a stock with no flow. CEE (Warrant→
  runtime) is the pattern; Vol VI (Learning) owes a *proprioception* bridge; Vol VII
  (Governance) owes the gate (partly built, just hardened).
- **"Feature freeze" is retired** and replaced by the construction law (commitment 2): not
  "don't add features," but "a feature is not done until its governing invariant is."
- **The sprawl test:** any proposed work must answer *which arc does this close?* Work that
  only widens the forward arc is deferred until the return arc catches up.

## Falsifier (so this is a claim, not a slogan)
This paradigm is wrong if reliability can be raised *durably* by means **other than**
theory→invariant (e.g. if ad-hoc scaffolding, prompt-tuning, or a bigger model alone
closes the gap without an enforced invariant). The session's evidence is against that
(reality-grounding worked *because* it made truth a runtime input; scaffolding-noise F2
actively hurt; the P0 existed *because* an invariant was missing) — but it is stated so the
paradigm can be tested, not merely believed. If falsified, the "lab is the supply chain"
claim collapses and SkynetClaw should choose one identity and shed the other.

## One line
The lab and the agent are the same thing: *the agent is reliable exactly to the degree the
lab's theories have become runtime invariants* — and right now the system is an open loop
because the theories of the return arc (learn, govern) are not yet invariants. Close the
loop; do not add limbs.
