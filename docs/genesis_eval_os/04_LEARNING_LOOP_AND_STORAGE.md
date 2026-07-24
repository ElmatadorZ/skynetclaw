# 04 — Learning Loop & Storage Model

> Design only. Deliverables 7 (Learning Loop) and 8 (Storage Model). How evidence
> becomes durable improvement, and the smallest storage that can hold a falsifiable,
> fully-explained epistemic history. Evidence-first; recover existing pieces.

---

## Deliverable 7 — The Learning Loop (how the system evolves ON evidence)

The loop turns a confirmed epistemic event into a permanent artifact. It is the
S8→S9 edge of the state machine, expanded, and it is **the only place CEE changes
the system's future behavior** — so it is tightly gated.

```
 anomaly/failure Event
     │
     ▼  (S4–S7) hypothesize → acquire evidence → revise → CONFIRM cause
 confirmed Failure  (Evidence-backed, not suspected)
     │
     ├─► emit REGRESSION probe        ── auto, deterministic ── (Failure Graph: guarded_by)
     ├─► emit GOLDEN test case        ── auto ── (feeds the harness / pyramid band)
     ├─► emit FAILURE-PATTERN node    ── auto ── (Failure Graph, for recurrence detection)
     ├─► emit BENCHMARK case          ── auto ── (adds a probe to the minimal suite)
     └─► propose RULE (e.g. new Constitution clause)  ── HUMAN-GATED ──
```

Governing principles (each recovered from existing project discipline):
- **Only confirmed causes learn.** A *suspected* failure does not write a rule —
  S9 fires only after S7 reached confidence ≥ threshold with cited Evidence. Kills
  learning-from-hallucination. SUPPORTED (mirrors skill-evolution's "human-gated
  promotion" + "surface with evidence").
- **Automatic for guards, gated for policy.** Regressions/probes/patterns are
  generated automatically (they only ADD safety). Rules/Constitution changes are
  proposed, never auto-applied (they change behavior globally — the R8 lesson: a
  rule is only as good as the model that obeys it, so a human confirms intent).
- **Every fix ships its guard.** S9's invariant: a Failure cannot be marked fixed
  without a `guarded_by` Regression. The Failure Graph's `unguarded_failures()`
  is the live debt list. SUPPORTED (this is the reliability rule automated).
- **Falsifiable learning.** A learned artifact stores what would prove it wrong /
  obsolete (e.g. "regression retired when the code path is deleted"). No permanent
  cruft. LIKELY.

What is RECOVERED vs NEW: `skill_evolution.py` already mines successful tool-chains
→ proposes skills (human-gated). The Learning Loop generalizes that one miner into
"any confirmed epistemic event → the right durable artifact." SUPPORTED that the
pattern exists; NEW is the generality + the auto-regression emission.

## Deliverable 8 — Storage Model (the smallest durable substrate)

Three tiers, one source of truth:

**Tier 1 · Observation Log — append-only, immutable (source of truth).**
- Every Event, timestamped, typed, source-tagged. Never mutated, never deleted
  (compacted/rolled, not edited). This is what makes the whole system auditable and
  rebuildable.
- Recovered: `house_sync._EVENT_LOG` (ring, in-memory) + `agent_runs` (DB) +
  `trajectory.jsonl`. NEW requirement: unify + persist (the ring is currently
  volatile — CEE needs durable history for baselines and evolution). SUPPORTED as
  a modest extension.

**Tier 2 · Epistemic Store — mutable, but every mutation is itself logged.**
- Beliefs, Confidences (with full value history), Hypotheses, Unknowns, Claims.
- **Critical rule:** the Store holds *current* state, but every change appends a
  record to Tier 1 (the why-record). So the Store is a cache of "latest"; Tier 1 is
  the truth. You can replay Tier 1 to reconstruct the Store at any past instant —
  time-travel over the system's own mind. This is what "store evolution" (the user's
  Stage 8) means concretely. SUPPORTED.

**Tier 3 · Graph Projections — derived, disposable.**
- The four graphs (file 03). Caches for traversal; rebuildable from Tiers 1–2.
  Never authoritative. If a graph and the log disagree, the log wins and the graph
  is rebuilt.

### The one storage invariant
> Nothing that asserts (Belief, Confidence, Claim, Failure) exists outside a Tier-1
> record that gives its evidence + why + refutation condition.

This single rule makes the storage model *self-auditing*: any assertion can be
traced to its cause, any confidence to its reason, any decision to its state. A
row with no provenance is not "low quality data" — it is inadmissible and rejected
at write. SUPPORTED (this is K1+K2+K3 enforced at the storage boundary — the cheapest
possible place to enforce them).

### Retention & cost (bounded, per the estimation/budget discipline)
- Tier 1 grows unbounded → compaction: keep raw Events for a window, then keep
  *derived summaries* (baselines, confirmed Failures, Regressions) forever and roll
  the raw. A confirmed Failure is permanent; a routine latency Event is not.
- Baselines are the compressed memory of "normal" — anomaly detection reads them,
  not the raw stream. LIKELY (retention policy tuned empirically).
