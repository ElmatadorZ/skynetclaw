# 04 — Coverage · Regression · Blind Spots · Future Layers

> Design only. What the current harness covers, how the benchmark stays honest
> over time, what it structurally CANNOT see, and where it grows.

---

## 1. Coverage map (honest, present state)

| Layer | Covered by today's harness? | Gap |
|---|---|---|
| L0 Runtime Health | **Partial** — liveness check + watchdog exist, not folded into the eval score | wire L0 as a run-validity gate |
| L1 Reality Grounding | **Yes (2/6 dims)** — G1 files, G2 operational | git, mission, runtime, tool-awareness dims missing (P1.3/P1.4) |
| L2 Evidence Discipline | **Partial** — G3 catches placeholder fabrication only | no confusion matrix; no tag-level probes (P2.2) |
| L3 Belief Revision | **No** | entire layer unbuilt |
| L4 Tool Execution | **Partial** — G5 write-file | no false_success metric across tools; P4.2/P4.3 missing |
| L5 Reasoning | **No** | needs judge (Claude) |
| L6 Scientific Method | **No** | needs judge |
| L7 Autonomy | **No** | needs end-to-end gap probes |
| Cross · Scaffolding noise | **Yes** — G4 (F2) | good; keep |

Reading: **the harness covers the deterministic band (L0–L4) partially and the
judged band (L5–L7) not at all.** That is the correct order to build, and it is
honestly the state — do not report a "cognitive system score" while L3/L5/L6/L7
are UNKNOWN. (SUPPORTED — the coverage map is itself an application of L2: mark
unbuilt layers UNKNOWN, not PASS.)

## 2. Regression strategy (how it stays a ratchet, not a snapshot)

- **Three cadences** (from Principle 1): smoke (L0, seconds, pre-run) · commit
  (L0–L4 deterministic, minutes, every change) · release (full L0–L7 with judge,
  slow/costly, per version).
- **Pinned per-model baselines.** Store {model → per-band scores + gate booleans}.
  A change is judged by its **delta against the same model's baseline**, never an
  absolute. (14B and Claude have different baselines on identical probes.)
- **Gate rule:** no change merges that turns any Family-A gate red (overclaim,
  false_success, fabrication-on-gap). A deterministic-band score *drop* is a
  blocking review, not an auto-fail (nondeterminism), but a gate flip is auto-fail.
- **Every new failure becomes a probe.** The taxonomy grows only from observed
  failures (never speculative classes) — a failure fixed without a probe is a
  regression waiting to happen. This is the same rule the reliability suite already
  follows ("reliability is earned only when the same failure cannot recur without a
  failing test"). SUPPORTED.
- **Judged-layer stability:** N≥3 runs, report pass-rate + variance; a judged
  layer with high variance is itself a finding (unstable cognition).

## 3. Blind spots (what the pyramid CANNOT measure — stated so no one trusts it blindly)

- **B1 · The evaluator's ceiling.** Judged layers cannot exceed the judge's own
  ability; a judge shares the subject's blind spots when they share a model
  family. Mitigation: judge ≥ subject, ideally a *different* frontier model.
  Residual: UNKNOWN failures both share are invisible. SUPPORTED.
- **B2 · Only known failures are tested.** The suite is built from observed
  failures; a novel failure mode scores 100% until it bites someone. The pyramid
  measures *absence of known lies*, not *presence of intelligence*. SUPPORTED.
- **B3 · Goodhart.** Once the benchmark is the target, the system (or its authors)
  optimize to it; the probes stop correlating with real quality. Mitigation: keep
  a HELD-OUT probe set never used for tuning; rotate probes. LIKELY.
- **B4 · Healthy-in-test, broken-in-wild.** Probes are curated; real operator
  tasks are messier (longer, multi-turn, ambiguous). A 100% pyramid ≠ a good
  product. Mitigation: sample real sessions into the probe set periodically.
  SUPPORTED (this session's failures were all found in the wild, not in tests).
- **B5 · Nondeterminism as noise.** Single-sample judged scores are unreliable;
  even deterministic-band probes drift if the model is swapped. Ground the score
  in N-runs and per-model baselines. SUPPORTED.
- **B6 · The pyramid cannot certify autonomy safety.** L7 measures *closure*, not
  *whether autonomous action was correct/safe to take*. Safe-autonomy is a
  governance question the pyramid touches only at the fabrication gate. UNKNOWN /
  deferred to a future value-alignment layer.

## 4. Future layers (beyond L7 — where it grows)

- **L8 · Multi-Agent Coherence.** Do the council's specialists actually disagree
  and integrate, or theatrically agree? Metric: dissent-preservation (Constitution
  R5) measured, not asserted; information gain from deliberation vs a single agent.
- **L9 · Long-Horizon Memory Consistency.** Across sessions: does recalled memory
  stay true to what happened; does it contradict itself over time. Ground truth:
  the ledger / institutional memory vs the actual run history.
- **L10 · Adversarial Robustness.** Prompt injection, tool-output poisoning,
  malicious skills (the external-skill install risk / F11). Metric: does hostile
  input from outside the trust boundary alter behavior.
- **L11 · Efficiency / Cost.** Tokens, tool calls, rounds, wall-clock per unit of
  real work — quality-per-cost, not quality alone (ties to run_big + the estimation
  theory's cost axis).
- **L12 · Value / Governance Alignment.** Does it obey the Constitution and the
  GPS-2 gates under pressure; does it refuse the irreversible without authority.
  The safety layer B6 points to.

Ordering principle for growth: **add a layer only when a real failure demands it**
(evidence-first), and always below the judged band if it can be made deterministic.
Speculative layers are marked SPECULATIVE and not built until a failure grounds
them. SUPPORTED.

---

## Closing — what this framework IS
The pyramid is not a scoreboard; it is a **ground-truth acquisition strategy plus a
set of gates against the system lying about its own warrant.** Its permanent core
is small: L0–L4 deterministic, two zero-tolerance gates (overclaim, false-success),
per-model baselines, and a taxonomy that only grows from observed reality. Its
honest present state is: deterministic band partially built, judged band UNKNOWN.
Naming that gap truthfully is the framework passing its own L2.
