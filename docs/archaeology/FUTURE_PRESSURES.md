# Future Pressures — the next mutation the organism is most likely to face

> **Not a roadmap. Not a redesign. Not a proposal.** Only a prediction of which
> *evolutionary pressure* is most likely to rise next, given the recovered trajectory
> (SELECTIVE_PRESSURES / EVOLUTION_TIMELINE). Every prediction is **falsifiable**: it
> states the observation that would prove it wrong. Tags: SUPPORTED / LIKELY / SPECULATIVE.
> Predictions describe *pressure*, never prescribe *solutions* (stop condition).

## Ranking (most likely first)

### FP-1 — Proprioception (self-perception) pressure — **MOST LIKELY** · LIKELY
- **Evidence:** M-8 (proprioception never shipped) is the only unmet sense; and this
  session reproduced **live production failures that all trace to it** — the organism
  searched a brand name as if it were news, and asked for a file it already held. The
  audits exist; the capability does not.
- **Why it may happen:** the organism now acts in a real, open world (M-6) but cannot
  reliably sense *its own* current state (workspace/model/net/mission). Each such failure
  adds pressure to close the gap; the failures are recurring, not one-off.
- **What would prove it wrong:** over the next observation window, self-state failures
  (mis-grounded answers about the organism's own files/model/context) **do not recur** AND
  no self-state/reality-context work is undertaken. If the gap causes no further failures,
  the pressure was not real.
- **Confidence:** LIKELY.

### FP-2 — Ownership / consolidation pressure — **RISING NOW** · LIKELY
- **Evidence:** G-ζ already shows it emerging — the V3 design frames "one owner per
  responsibility again, at OS scale," and Epic Trust *froze additive growth*. The
  fragmentation created in G-γ (dispatch 1→5+, judge 1→6+, memory 1→8+) is the standing cost.
- **Why it may happen:** P-ADD won for two weeks and produced many owners per job; the
  cost of that (drift, "which one is authoritative?") is what examination (G-ζ) surfaces.
  Consolidation pressure classically follows an additive explosion.
- **What would prove it wrong:** the next substantive changes are **again "additive,
  read-only" new modules with zero owner-consolidation** and no observed cost from the
  fragmentation (no drift, no conflicting owners) — i.e., P-ADD keeps winning with no penalty.
- **Confidence:** LIKELY.

### FP-3 — The collision: proprioception-need vs freeze/additive-resistance — **SPECIFIC** · LIKELY
- **Evidence:** FP-1 requires an **invasive** change to the hot loop (self-perception must
  be authoritative in-loop, per M-8). FP-2 / Epic Trust actively **resist** new organs and
  invasive change. These two pressures point in opposite directions.
- **Why it may happen:** the organism cannot satisfy FP-1 with the additive method that
  built everything else (M-8's core finding) — so the next real tension is *"must build an
  invasive sense" vs "freeze forbids new organs."*
- **What would prove it wrong:** proprioception gets built **additively** (as a read-only
  side-organ) and *works* — i.e., self-perception turns out **not** to require invasive
  core change. (That would falsify M-8's premise and this collision.)
- **Confidence:** LIKELY (depends on M-8's invasiveness premise, which is SUPPORTED for
  "authoritative in-loop" but SPECULATIVE for "no additive form can work").

### FP-4 — Coordination / drift pressure among duplicate owners — SPECULATIVE→LIKELY
- **Evidence:** 5+ routers, 6+ evaluators, 8+ memories coexist (RESPONSIBILITY_EVOLUTION_GRAPH).
  More owners of one job ⇒ higher chance two disagree or diverge.
- **Why it may happen:** the second-order cost of fragmentation is coordination — duplicate
  evaluators may return conflicting verdicts; duplicate memories may diverge.
- **What would prove it wrong:** the DEC-1/DEC-2 traces (still unrun) show the duplicate
  owners are **layer-disjoint** (never decide the same thing), so no coordination is needed.
- **Confidence:** SPECULATIVE until DEC-1/DEC-2 run; LIKELY given the raw owner counts.

### FP-5 — Latency / context-budget pressure — LIKELY
- **Evidence:** it has *already occurred twice* — `a0faf73 perf(P1)` (cached 2.3s→11ms
  probes) and `7590c53 "cap multi-skill injection to a context budget (fix 400 exceed
  context)"`. Every new perception/organ adds prompt or probes.
- **Why it may happen:** if the organism grows any new sense (esp. FP-1, which injects
  runtime state into every message), context size and per-call latency rise again.
- **What would prove it wrong:** new perception is added and measured latency/context stay
  within the existing budget (health-probe SLA, context cap) — no regression.
- **Confidence:** LIKELY (precedent is SUPPORTED; recurrence is the prediction).

### FP-6 — Governance-enforcement pressure (process → structure) — LIKELY
- **Evidence:** Epic Trust is currently *process-level* (docs, review gates, regression
  suites) — `bf1d8a4`. It is not enforced in the architecture.
- **Why it may happen:** process discipline without structural backing tends to erode as
  activity resumes after a freeze; pressure builds to make the gate enforce itself.
- **What would prove it wrong:** the freeze/evidence-gate is honored across the next wave of
  changes **without** any code-level enforcement — pure process holds.
- **Confidence:** LIKELY.

---

## The single most-likely next mutation (synthesis) · LIKELY
> **FP-1 + FP-3.** The organism's strongest live signal is *self-perception failure*
> (reproduced, recurring), and its strongest structural constraint is the *freeze +
> additive habit*. The next evolutionary event is most likely a **collision between the
> need to sense itself and the inability to do so additively.** How that collision
> resolves is **UNKNOWN** and outside this archaeology's scope — this document only
> predicts the *pressure*, and states (above) exactly what observations would falsify it.

## Falsification log (to be filled by future observation)
| Prediction | Falsifier observed? | Evidence | Date |
|---|---|---|---|
| FP-1 self-perception | — | | |
| FP-2 consolidation | — | | |
| FP-3 collision | — | | |
| FP-4 coordination | — | | |
| FP-5 latency | — | | |
| FP-6 governance-enforcement | — | | |
