# 03 — The Four Graphs (Knowledge · Evidence · Belief · Failure)

> Design only. Deliverables 3–6. All four are **projections over one substrate**
> (the Observation Log + Epistemic Store, file 00) — NOT four databases. Each: what
> it answers · nodes · edges · derivation · the one operation that matters. Minimal
> discipline: if a graph can't be rebuilt from the log, it is state drift and
> forbidden.

The four are different questions asked of the same evidence:
`Knowledge` = what CAN I do · `Evidence` = what do I KNOW and why · `Belief` = what
do I HOLD and how strongly · `Failure` = what BREAKS and how it's guarded.

---

## Deliverable 3 — Knowledge Graph  (the self-model)
- **Answers:** "What is this system, right now, actually capable of?" (Not the docs'
  claim — the *verified* capability. Directly attacks the facades finding.)
- **Nodes:** Capabilities, Tools, Skills, Runtimes, Rules(Constitution), Invariants.
- **Edges:** `Capability —requires→ Tool/Runtime`; `Skill —grants→ Tool`;
  `Tool —verified_by→ Evidence` (a Tool node is `verified` only if an Event proves
  it executed with a real effect — else `claimed`, not `capable`).
- **Derived from:** the tool registry + the Execution-class Events. A skill that
  declares tools but never grants them (F6) shows as an edge with no `verified_by`
  → visibly a facade.
- **Key op:** `capability_truth(x)` → {capable | claimed-only | broken}, evidence-
  backed. This is the Knowledge Graph's whole point: separate declared from real.
  SUPPORTED (the data — tool events, skill.tools — already exists; the graph makes
  the gap visible).

## Deliverable 4 — Evidence Graph  (provenance)
- **Answers:** "For any Claim, what observations back it — and are they enough?"
- **Nodes:** Events (raw), Evidence (promoted Events), Claims.
- **Edges:** `Claim —cites→ Evidence —is→ Event`; `Evidence —supports|contradicts→
  Claim`; each Evidence carries its warrant tag (observed…unknown).
- **Derived from:** the log (Events) + outputs parsed into Claims at S2.
- **Key op:** `warrant(claim)` = the max warrant tag among its supporting Evidence;
  **overclaim(claim)** = claimed_tag ≻ warrant(claim) → the LIVE fabrication
  detector (K1). A Claim node with zero inbound Evidence edges is auto-`unknown`.
- **Invariant:** the Evidence Graph is acyclic Claim→Evidence→Event (no claim
  supports itself). SUPPORTED — this graph *is* the runtime enforcement of the
  pyramid's L2 gate.

## Deliverable 5 — Belief Graph  (what is held, and why it moves)
- **Answers:** "What does the system believe, at what confidence, and what would
  change it?"
- **Nodes:** Beliefs (with Confidence + full history), Unknowns.
- **Edges:**
  - `Belief —grounded_by→ Evidence` (K1 floor)
  - `Belief —confidence@t {Δ, why, evidence_id}→` (K2: **every confidence value is
    an edge to its cause** — the "explain why it changed" constraint IS the edge set)
  - `Belief —depends_on|contradicts→ Belief` (revision propagates along these)
  - `Belief —refuted_if→ Condition` (K3)
- **Derived from:** the Epistemic Store's revision log (S7 writes).
- **Key op:** `revise(belief, new_evidence)` → new Confidence + a mandatory why-edge;
  **rigidity check** = flag any Confidence that rose under a `contradicts` edge
  (belief-rigidity failure, pyramid L3). Belief individuation follows the belief-
  science result: a Belief is the counterfactually-invariant disposition, held at
  the coarsest grain the Evidence supports — not a stored token. SUPPORTED as a
  design; the confidence-calibration magnitude is LIKELY (direction crisp, size fuzzy).

## Deliverable 6 — Failure Graph  (what breaks → how it's guarded)
- **Answers:** "What has failed, why, is it fixed, and can it recur silently?"
- **Nodes:** Failures (from the taxonomy), Hypotheses, Causes, Changes(fixes),
  Regressions.
- **Edges:** `Failure —caused_by→ Hypothesis(confirmed)`; `Failure —detected_by→
  Detector`; `Failure —fixed_by→ Change`; `Change —guarded_by→ Regression`;
  `Failure —recurs→ Failure` (repeat detection).
- **Derived from:** Violation/Regression-class Events + S9 (Learn) writes.
- **Key op:** `unguarded_failures()` = Failure nodes with a `fixed_by` but no
  `guarded_by` → the exact "fixed without a test" debt the reliability rule forbids;
  `recurrence(failure)` surfaces flaky/unfixed modes. This graph is the memory that
  makes Evolution possible: it is where every session failure this project hit would
  live, linked to its fix and its guard. SUPPORTED (the taxonomy + agent_runs
  failures already exist; the graph links them).

---

## Why four graphs and not one (the minimality answer)
They are four *indices* over the same nodes, each optimized for one question the OS
must answer continuously: capability-truth (Knowledge), provenance (Evidence),
held-belief-and-revision (Belief), break-and-guard (Failure). Collapsing them into
one graph would still need these four traversals — so the split is the traversal
pattern, not extra storage. All four rebuild deterministically from the log+store;
none holds authoritative state of its own. That rebuildability is the guarantee
that the "living evaluation" can never quietly diverge from reality — the same
property that makes the reality-grounding trustworthy. SUPPORTED.
