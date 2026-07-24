# V3 Red-Team — Kernel Stress Test

> The architecture was frozen, then attacked. Goal: prove a kernel redundant,
> insufficient, or misplaced. Outcome: 7/8 original kernels survived; the set was
> **insufficient** at the egress boundary, forcing the 9th kernel
> ([Reality Boundary](kernels/RealityBoundary.md)). The Journal was found
> theoretically incorrect on agreement and amended *within* the kernel. After adding
> the 9th and self-attacking it, **no 10th is forced** — the set is declared complete
> at nine.
> Parent: [V3-Architecture](V3-Architecture.md) · [DecisionLog](DecisionLog.md)

## 1. Rules of engagement
Same DecisionLog test, run in reverse: a finding forces a new kernel only if the
responsibility is (a) a single responsibility, (b) ownerless — no existing kernel can
absorb it without violating its own single responsibility, (c) not a projection. The
rule also runs *forward* (can a kernel be demoted?) and *as correctness* (is a kernel's
stated contract true?).

## 2. Per-kernel survival
| Kernel | Attack | Result |
|---|---|---|
| Constitution | redundant vs Governance? confused-deputy via Reflection | **survives** — only an immutable kernel stops "edit policy to allow editing audit"; bounds blast radius of a Byzantine high-authority agent |
| Identity & Capability | privilege escalation, forged delegation | **survives** — attenuating caps + delegation chain to a human |
| Scheduler | deadlock (hold-and-wait), starvation | **survives (conditional)** — lease expiry + preemption break deadlock; livelock under contention is tuning, not a missing kernel |
| Supervisor | does let-it-crash create bugs? | **survives — but is the star witness**: restart + non-idempotent egress = double-effect by design → see Finding 2 |
| Contract Registry | redundant? fold into Journal? | **survives, weakest** — broader than Journal events (RPC/cap/projection) + upcast lifecycle; on watch: demote if it never grows past event schemas |
| Model Gateway | is it a specialization of Reality Boundary? | **survives demotion** — Liskov: its core invariant (coalescing) *inverts* RBK's (individuation); sibling, not subtype (see §5) |
| Epistemic | Byzantine agent asserts false claims w/ "evidence" | **survives (bounded)** — detects contradiction/freshness, down-weights via calibration; truth corruptible short-term but Constitution caps damage |
| Journal | multi-node agreement | **insufficient → amended in-kernel** (Finding 1) |

## 3. Finding 1 — Journal conflated *ordering* with *agreement* (amended, not a new kernel)
Vector clocks give partial causal order and *detect* concurrency; they are **not
consensus** and do not *resolve* it. Split-brain counterexample: two nodes append to
`mission:OX-1` concurrently → on heal, two truths, no winner. **Fix:** consensus
(quorum/total-order broadcast) is *how you implement a distributed append log* — it
lives **inside** the Journal kernel (like causal ordering, like the rejected Semantic
Clock). The doc was corrected (Journal §9); **no kernel added.** Symmetric application
of the anti-inflation rule.

## 4. Finding 2 — ownerless egress integrity (forced the 9th kernel)
**Counterexample (crash mid-egress):** agent passes the Constitution gate, posts an
order to a broker API (external effect happens), crashes before journaling the result;
Supervisor restarts and replays the node; the order is **re-sent** — the foreign API
never honored our dedupe key. Money moves twice. Partition makes it worse: both halves
send the same effect.

No kernel owns "at-most-once external effect + compensation/gate": Journal=internal,
Scheduler=resources, Constitution=forbids-not-implements, Identity=who-not-how-many,
Supervisor=the *cause*, Model Gateway=inference only. The DecisionLog 3-question test
passes cleanly (cleaner than Semantic Clock, which failed Q3 as a projection). →
**[Reality Boundary Kernel](kernels/RealityBoundary.md) added.**

**Tell:** the Model Gateway is a whole kernel built to make *one* external-effect class
(inference) safe — proof the general responsibility is real and was unowned.

## 5. The Model Gateway demotion test (survived)
Asked: is MGW just RBK specialized to inference → remove it? **No.**
- A true specialization *refines* (Liskov-strengthens) the parent's invariant. MGW
  *inverts* RBK's: RBK = never-coalesce + re-execute-forbidden; MGW = coalesce(batch) +
  re-execute-safe. A subtype cannot invert its parent's invariant.
- Two-way proof: RBK can't batch (breaks its 1 intent : 1 call : 1 key : 1 compensation
  model); MGW can't promise at-most-once (it retries/batches freely — safe for inference,
  fatal for payments).
- Also not Scheduler's: Scheduler owns *allocation* (resource-agnostic leasing); MGW
  owns *packing* (inference-specific batching). Different responsibilities.
→ **sibling, not subtype.** Shared plumbing factored into a non-kernel lib `egress-io`.
This is the first **demotion** precedent: the anti-inflation rule cuts both ways.

## 6. Self-attack on the 9th kernel (does it force a 10th?)
- **Exactly-once is impossible (Two Generals).** → RBK's contract is *weakened to the
  truth*: at-most-once + reconcile + gate-on-unreconcilable. A refinement of RBK, not a
  new kernel.
- **Compensation needs external support.** → non-compensable + non-reconcilable = a
  Constitutional irreversible action → existing human gate. No new kernel.
- **"Intent committed" agreement across nodes.** → rides on the now-amended Journal
  consensus. No new kernel.
**No 10th kernel is forced.**

## 7. Watch-list (weaknesses that are not missing kernels)
- **Contract Registry** is the weakest kernel; demote to a Journal service if it never
  exceeds event-schema validation.
- **Constitution assumes a clean TCB**: `constitution.check` is in-process code; an
  RCE-bearing skill could skip it. Mitigation = node attestation, which folds into
  **Identity** (node identity + attestation), not a new kernel. Assumption now stated.
- **Epistemic lacks a fast online trust-collapse** for a repeatedly-lying agent (today
  it leans on slow post-mission Reflection). This is engine/policy work, not a kernel.

## 8. Verdict
The architecture survived as a structure: every original kernel is non-redundant and
roughly correctly placed, and the attacks *validated* Constitution/Identity/Epistemic.
One real insufficiency (egress) forced **one** new kernel; one real incorrectness
(agreement) was fixed in place. With Reality Boundary added and self-attacked, and with
Model Gateway surviving demotion, the **Kernel Set is declared complete at nine.** Future
proposals must pass the DecisionLog test; this document is the precedent that the test
admits, rejects, demotes, and corrects with equal rigor.
