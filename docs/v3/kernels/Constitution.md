# Constitution Kernel

> The root of trust. Immutable invariants that **no one** can change — not the
> operator, not the Governor, not Reflection's self-evolution. Sits *below* Governance.
> Parent: [V3-Architecture](../V3-Architecture.md) · Justification: [DecisionLog](../DecisionLog.md)

## 1. Why it is a kernel (not policy)
Governance is **mutable by definition** — deny-by-default rules that are tuned over
time. An invariant that must *never* change cannot be enforced by something that can
itself be edited. The Constitution is therefore a separate kernel at the root: laws
that bound every other kernel, engine, and human action.

> Constitution > Governance, always. Governance operates only *within* the Constitution.

## 2. The articles (immutable invariants)
Examples (the seed set; the *set* is signed and versioned, but articles are
append-only — an article can be *added* by a constitutional process, never silently
edited or removed):
1. **Never modify or delete the audit log.** Append-only, forever.
2. **Never overwrite history.** The Journal is immutable; corrections are new events.
3. **Never execute an irreversible/destructive action without an explicit human gate.**
4. **Never bypass the governance path** (risk → security → approval → audit).
5. **Never act without an identity** (no anonymous privileged action).
6. **Never exceed a granted capability** (no privilege escalation).
7. **Reflection may propose, never silently self-apply** evolution to skills/agents/
   policy outside its opt-in, reversible allowlist.

## 3. Enforcement model
- The Constitution is a **signed artifact** (`config/constitution.yaml` + detached
  signature). It is loaded at boot; a failed signature **halts boot** (fail-closed).
- Every privileged operation passes a `constitution.check(action, actor, ctx)` *before*
  governance. A constitutional violation is **not overridable** — it raises and is
  itself audited (a violation attempt is an event).
- The check is a pure function of (article set, action) — no I/O, no model call — so it
  cannot be subverted by prompt, plan, or runtime.

## 4. Interface
```python
class Constitution:                      # loaded once; immutable in memory
    version: str; signature_ok: bool
    def articles(self) -> list[Article]
    def check(self, action: Action, actor: Principal, ctx: Context) -> Ruling
        # → ALLOW (within constitution) | DENY_IMMUTABLE (never overridable)
    def amend(self, proposal: Amendment, *, ceremony: ConstitutionalCeremony) -> None
        # append-only; requires the out-of-band ceremony (multi-party, signed)
```
`amend` is deliberately heavy: amendments require an out-of-band **ceremony**
(multi-party human approval + re-signing), never an in-band agent action.

## 5. Events
`constitution.loaded`, `constitution.violation_attempt` (actor, action, article),
`constitution.amended`. All are appended to the Journal; the violation event itself can
never be deleted (Article 1).

## 6. Relationship to Governance
| | Constitution | Governance |
|---|---|---|
| Mutability | immutable (ceremony-only, append) | mutable (operator-tunable) |
| Scope | universal invariants | contextual policy/risk |
| Override | **never** | human gate can approve within constitution |
| Failure mode | fail-closed (halt/deny) | deny-by-default |

## 7. Single → distributed
Workstation: signed file loaded in-proc. Organization: the same signed artifact is
**replicated** to every node; nodes verify the signature independently; an amendment
ceremony updates all replicas. The check stays a local pure function everywhere — no
network dependency in the hot path.

## 8. Compatibility
Built over the existing `governance.py` / `skynetclaw_meta.shadow_gate`: those become
*governance* (mutable), and the Constitution wraps them as the outer, immutable bound.
Seed articles encode rules SkynetClaw already honors informally ("no destructive action
without operator approval", "GPS-2 must never be bypassed") — now made unbreakable.

## 9. Proposed articles — PENDING CEREMONY (not yet immutable)
> Staged by [ADR-0013 — Cognitive Constitutional Architecture](../../adr/ADR-0013-cognitive-constitutional-architecture.md).
> Per §2/§4 an article becomes immutable **only** through the multi-party amend ceremony
> (re-signing). Until then these are *proposed*, not ratified — recorded here for review,
> not enforced as invariants. Do not treat as signed. Note: nothing here is *immutable* —
> even these are the **highest-order constraints** (highest change-cost / widest blast radius),
> not sacred untouchables.

**A. Identity & Governance (the crown — two axes).**
- *Identity (existential):* SkynetClaw is "architecture that governs through explicit
  semantics and replaceable capability providers." Change it and the system becomes a
  different system.
- *Highest-order Constraint (governance):* changes to core semantics/identity occur only by
  the amend ceremony (§4) — the change with the widest blast radius, therefore the last resort.

**B. Semantic Constitution.** What is maximally-stable is the **meaning**, not the
implementation. Core semantics (Decision, Validation, Memory, Event, Persistence, Truth)
change only by ceremony; *operational* semantics and *implementations* (`logic/`, CVL,
`decision_intelligence`/DIC, the storage engine) evolve freely **as long as they still
satisfy the core semantic**, proven by conformance evidence. Persistence is a capability
(SQLite→Postgres→S3 are interchangeable providers); the *truth semantic* (single, append-only,
ordered) is architecture (§2 "no resource may become a source of truth"), not the DB.

**C. Resource Subordination.** A resource (model, tool, datastore, simulator, human, future
AI) is an external, swappable **Capability Provider** invoked via a Contract. The architecture
declares *capabilities required* — never a provider name/API. Final decisions for **decidable**
problems belong to the architecture (the provider is a Candidate Generator); **generative**
tasks are governed, not decided.

**D. Living Constitution (feedback) + anti-circularity anchor.** Evidence feeds back up
(Implementation → Conformance Evidence → Governance → Amendment → Core Semantics), keeping the
system alive rather than static. **But the upward path MUST pass through an external, held-out
anchor the loop cannot edit** (frozen ground-truth + neutral judge, ADR-0010). Self-generated
evidence alone may never justify changing identity or core semantics.

**E. Burden of proof.** Challenge implementation before principles. Amending identity/core
semantics requires **externally-anchored evidence, from real operational conditions,** that
the current constitution can no longer preserve the system's identity. Changing the top is the
last resort, never the first move.

**F. State Ownership Principle** (staged by [ADR-0014](../../adr/ADR-0014-state-consolidation.md),
operator ruling 2026-07-19). **Every mutable state SHALL have exactly one authoritative
writer. Derived projections MAY exist. Additional authoritative writers SHALL NOT.**
State ownership is a system-level law, not a per-ADR decision: the drift that produced six
databases and three-writer state files is what this article makes structurally illegal.
Enforcement (CI-checkable): the state tripwire (`tests/test_state_tripwire.py`) blocks
unchartered stores; single-writer guards land with ADR-0014 P1.

**Enforcement (proposed, CI-checkable before ceremony):**
- cognitive core imports no provider client:
  `grep -rE "openai|ollama|anthropic|httpx" logic/ decision_intelligence/ capabilities/ cognitive_validation.py` → empty;
- no module outside the truth-store owner writes `skynerclaw.db` / the journal directly.
