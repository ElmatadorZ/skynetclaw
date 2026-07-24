# V3 Decision Log — Justifying Every Kernel

> The record that makes the Freeze enforceable. Every proposed kernel was tested
> against one rule: **"No new kernel without proving that an existing kernel cannot
> solve the problem."** This log is the precedent for all future proposals.
> Parent: [V3-Architecture](V3-Architecture.md)

## 1. The rule
A capability becomes a **kernel** only if no existing kernel can own it without
violating its own single responsibility. Otherwise it is an **engine** (cognition,
built on kernels), a **projection** (a read model over the Journal), or a **property**
of an existing kernel. This prevents Kernel Inflation — the failure mode where kernels
accrete overlapping duties until the "OS" is mud.

## 2. Verdicts on the V3.5 proposals
| Proposal | Verdict | Justification (why existing kernels can / cannot absorb it) |
|---|---|---|
| **Constitution** | **NEW KERNEL** | Governance is *mutable by definition* (deny-by-default rules, tunable). Immutable invariants ("never modify the audit log", "never overwrite history") cannot be enforced by a thing that can itself be edited. It must sit *below* Governance, at the root of trust. No existing kernel can hold an unchangeable invariant. → kernel. |
| **Epistemic** | **NEW KERNEL** | The Knowledge Graph is a *data/storage plane*. Truth-maintenance — belief revision, contradiction detection, consensus, freshness decay — is *behavior over* that data. Putting behavior in the store violates its single responsibility and couples retrieval to reasoning. No existing kernel owns "justified belief". → kernel (a trust plane over the KG data plane). |
| **Identity & Capability** | **EXISTING (refined)** | Already required by the V3 audit. Refined into two planes per the proposed layering: **Identity** (authentication — who the principal is) high in the stack; **Capability** (authorization — scoped, time-bound grants) issued under Identity, checked at every action. One kernel, two faces. → no new kernel. |
| **Semantic Clock** | **ABSORBED — NOT A KERNEL** | Causal ordering of events is a property the **Journal must already provide** to be a correct distributed log (logical/vector clocks stamped on every appended event). The "semantic timeline" (order by dependency → decision → meaning) is a **projection** over that causal order — a read model, like Mission or Knowledge. Making it a standalone kernel would duplicate the Journal's ordering responsibility = textbook Kernel Inflation. → folded into [Journal](kernels/Journal.md) + a Semantic Timeline projection. |
| **Theory of Mind / Mental Model** | **NEW ENGINE — NOT A KERNEL** | It is *derivable*: a per-observer projection over the **Epistemic Kernel** (what is believed, with confidence) + **Identity** (who is who) + **Journal** (which events each agent was exposed to). A capability that is a projection over existing kernels is, by the rule, not a kernel. It is a cognition **engine**, peer to Council and Reflection. → [MentalModelEngine](engines/MentalModelEngine.md). |

## 3. Tally
- Proposed as kernels: 3 (Constitution, Epistemic, Semantic Clock).
- Admitted as kernels: **2** (Constitution, Epistemic).
- Rejected as kernel, absorbed: **1** (Semantic Clock → Journal property + projection).
- Admitted as engine: **1** (Theory of Mind / Mental Model).
- Reaffirmed existing: **1** (Identity & Capability, refined into two planes).

The rule rejected one of the proposer's own kernels. That is the rule working.

## 3b. Post-freeze precedents (from the red-team)
The Freeze was tested by attack ([RedTeam](RedTeam-KernelStressTest.md)). Three rulings,
showing the rule admits, demotes, and corrects with equal rigor:

| Item | Verdict | Justification |
|---|---|---|
| **Reality Boundary** (9th kernel) | **ADMITTED** | Crash mid-egress + Supervisor restart re-executes irreversible external effects; no existing kernel owns at-most-once external effect + compensation/gate (Journal=internal, Scheduler=resources, Constitution=forbids-not-implements, Gateway=inference-only). Passes all 3 questions; cleaner than Semantic Clock (which failed Q3). |
| **Model Gateway** (demotion test) | **KEPT — not a subtype of Reality Boundary** | A specialization must *refine* (Liskov) the parent's invariant; MGW *inverts* it: RBK = individuation + re-execute-forbidden, MGW = coalescing(batch) + re-execute-safe. Two-way proof (RBK can't batch; MGW can't promise at-most-once). Sibling, sharing a non-kernel `egress-io` lib. First **demotion** precedent — the rule cuts both ways. |
| **Journal agreement** (correctness) | **AMENDED in-kernel — no new kernel** | Vector clocks order but do not *agree*; a distributed log needs consensus (quorum/total-order broadcast). Consensus is *how you implement* the log, like causal ordering → folded into the Journal, like the rejected Semantic Clock. |
| **10th kernel?** (self-attack on RBK) | **NOT FORCED** | Exactly-once is impossible (Two Generals) → RBK contract weakened to at-most-once + reconcile + gate (a refinement). Compensation gaps → Constitutional gate. Cross-node intent → rides Journal consensus. Set complete at nine. |

## 4. Precedent for future proposals
Any future kernel proposal must answer, in writing, the same three questions:
1. **Which single responsibility is it?** (one sentence; if it needs "and", it is two
   things — split or reject.)
2. **Why can no existing kernel own it?** (name the kernel that is closest and the
   exact reason absorbing it would break that kernel's single responsibility.)
3. **Is it a projection?** (if it can be computed as a read model over the Journal +
   existing kernels, it is an engine or a view — not a kernel.)

If all three are not cleanly answered, the answer is **no new kernel**.
