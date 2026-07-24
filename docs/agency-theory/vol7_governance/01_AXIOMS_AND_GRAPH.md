# Agency — Volume VII · 01 — Necessary Conditions, Axioms, Graph & Requisite Variety

> Pure philosophy. Deliverables 2 (graph) + 3 (axioms) + Question 5 (requisite variety — and
> the recovered result that the **Security Theory is Vol VII specialized to authority**).

---

## Q2 · Necessary conditions for governance

Removal-tests, distinguishing governance from advice / self-restraint / a mere rule.

| Candidate | Necessary? | Test |
|---|---|---|
| **A normative standard** (policy: which actions permissible) | **YES (SUPPORTED)** | nothing to enforce → no governance, only observation |
| **Separation** (governor ≠ governed, not overridable-at-will by the governed) | **YES (SUPPORTED)** | a bound the governed lifts at whim is self-restraint, not governance |
| **Complete mediation** (every action checked before effect) | **YES (SUPPORTED)** | a policy checked *sometimes* is advisory; the unchecked path *is* the governance hole (the audit's P0) |
| **Enforcement** (power to prevent/sanction) | **YES (SUPPORTED)** | a standard with no teeth is a suggestion; prohibition without prevention is not a bound |
| **Requisite variety** (governor's variety ≥ governed's) | **YES for *complete* governance** | a governor poorer than the governed cannot cover all its actions (Ashby) — partial governance only |
| **Legitimacy** (accepted ground of authority) | **YES for *stable* governance; contested as constitutive** | an illegitimate governor can still *bound* (tyranny/brute force), but not *stably* — compliance decays, or it is mere coercion |

**Recovered necessary core (SUPPORTED):** `{ policy, separation, complete mediation,
enforcement }`. Add **requisite variety** for governance to be *complete* (not merely partial),
and **legitimacy** for it to be *stable* (not merely coercive). The volume's own contribution
is **Mediation** (Anderson's completeness) as the differentia — the node whose failure *is*
the governance hole.

## Axioms of governance ("no governance without…")

- **GA1 · Standard.** *No governance without a policy of permissible action.* SUPPORTED.
- **GA2 · Separation.** *No governance without the bound being beyond the governed's
  at-will override.* Frankfurt's second-order volition is the *internal* limiting case;
  genuine governance needs the constraint to be structurally superior. SUPPORTED.
- **GA3 · Complete mediation.** *No governance without every action crossing the monitor.*
  The reference-monitor completeness condition; a single unmediated path voids the bound. This
  is the seed of the final theorem *and* the exact failure the security audit reproduced.
  SUPPORTED.
- **GA4 · Enforcement.** *No governance without the power to prevent/sanction.* SUPPORTED.
- **GA5 · Requisite variety (for completeness).** *No **complete** governance of a system
  richer than the governor.* Ashby. SUPPORTED (as the bound) / OPEN (scalable oversight).

**Independence.** GA1–GA4 are irreducible together: a policy with no separation (GA1¬GA2) is
self-advice; separation with no mediation (GA2¬GA3) is an unenforced constitution; mediation
with no enforcement (GA3¬GA4) is a checkpoint that only logs. GA5 is separable — it divides
*complete* from *partial* governance. SUPPORTED.

## Q5 · Requisite variety — and the Security Theory as a special case

**Ashby's law applied (SUPPORTED):** a governor can *completely* govern only a system whose
variety it can match. Consequence: **you cannot fully govern a governed richer than your
governor** — an overseer weaker than the agent it oversees has a coverage gap (the scalable-
oversight problem; the reason a weak model cannot self-govern a powerful tool-surface).

**This is the governance-layer image of HRU-undecidability** (from the Security Theory): you
cannot in general *prove or enforce* safety over an arbitrary system; you must **construct**
the situation so the governor's variety *suffices*. The security discipline — least privilege
(shrink the governed's authority to what the governor can mediate), deny-by-default (the
governor covers the whole space by refusing the unenumerated), minimal TCB (shrink what must
be trusted to what can be verified) — **is Ashby's requisite variety made operational.** So:

> **The Theory of Capability Escalation (recovered this session) is Vol VII specialized to the
> domain of *authority*.** Its master invariant (authority conservation) is governance's GA3
> (complete mediation conserving authority across boundaries); its impossibility triangle
> (ambient authority + confused deputy + incomplete mediation) is the failure of GA3; its
> reference monitor is the Governor; its minimal-TCB is requisite-variety-by-construction.
> Governance ⊇ Security-governance. SUPPORTED.

This retroactively grounds the P0 fixes: fail-closed (GA3 completeness on the error path),
the SSRF cut (closing an unmediated boundary), the shim allow-list (shrinking the governed's
variety to the governor's) — all were Vol VII enacted before Vol VII was written.

## D2 · The governance graph

```
   [ agent proposes ] ACTION
            │
            ▼
        MEDIATION  ◀── POLICY (standard of permissible action)     [GA3: EVERY action, no bypass]
            │            ▲
            │            │  (secondary loop: governance of governance —
     ┌──────┼──────┐     │   the policy itself is revised, Hart's "change" rule)
     ▼      ▼      ▼      │
  PERMIT  ESCALATE  PROHIBIT
     │      │(→ OVERRIDE/VETO: irreversible/high-footprint action halts pending AUTHORITY)
     ▼      ▼
  EXECUTION (Vol V) ──▶ OUTCOME + EXCESS FOOTPRINT ──▶ ACCOUNTABILITY (attribute the surplus)
                                                            │
                                                            ▼
                                                        SANCTION (on violation) / feeds LEARN (Vol VI)
```

**Three structural facts:**
1. **Mediation is the load-bearing node** — its *completeness* (GA3) is the whole game; one
   unmediated edge voids governance (the P0). Everything else is transport. SUPPORTED.
2. **The Override/Veto exists for the excess footprint** — irreversible/high-footprint actions
   (Vol V) route to a human/higher authority because their surplus exceeds what a proxy policy
   can pre-authorize. The human gate is not friction; it is the governor of the ungoverned
   surplus. SUPPORTED.
3. **Governance has a secondary loop** — the policy itself is revised (Hart's "change" rule),
   which is *governance of governance*, raising the regress (who governs the governor? — Vol
   VII·04). The graph is reflexive at the Policy node. SUPPORTED.

## The runtime bridge Vol VII owes — already built
Unlike Vols I–VI, Vol VII's bridge **pre-exists**: the GPS-2 governance gate (deny-by-default,
human gate on irreversible tools), just hardened by the security audit (fail-closed, SSRF cut,
shim reference monitor). Vol VII is the theory that *names what that gate is* — a reference
monitor enforcing GA1–GA4 — and what it still lacks: **requisite variety** (a weak governor
over a rich tool-surface, GA5) and complete accountability of the footprint. SUPPORTED.

## Falsifiers
GA3's necessity fails if governance survives a permanent unmediated path (a bound that holds
despite a bypass — the audit says it does not). The Security-as-special-case claim fails if an
authority escalation is exhibited that is *not* a mediation failure (would separate the two
theories). Requisite variety fails if a governor is shown to completely govern a strictly
richer governed (would refute Ashby).
