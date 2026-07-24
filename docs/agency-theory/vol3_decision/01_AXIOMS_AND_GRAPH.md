# Agency — Volume III · 01 — Necessary Conditions, Axioms, Graph & the Information Ladder

> Pure philosophy. Deliverables 2 (dependency graph) + 3 (axioms) + Questions 2
> (what turns a choice into a decision) and 5 (certainty / risk / uncertainty /
> ignorance).

---

## Q2 · Necessary conditions — what makes a choice a *decision*?

Removal-tests, as in Vols I–II.

| Candidate | Necessary? | Test |
|---|---|---|
| **≥ 2 live options** | **YES (SUPPORTED)** | one admissible action → a *forced move*, nothing to decide. No option set, no decision. |
| **A criterion (value)** | **YES (SUPPORTED)** | VT1 (Vol II): flat value → arbitrary pick, not a decision. The criterion is what a decision is *for*. |
| **Some belief about outcomes** | **YES (LIKELY)** | with zero representation of what the options lead to, "choosing" is blind flailing, not deciding. (Degenerate under certainty, where belief is trivial.) |
| **Closure** (deliberation terminates on one option) | **YES (SUPPORTED)** | without closure the field stays open — that *is* ongoing deliberation, not a decision. |
| **Commitment** (the closure *binds* future conduct) | **YES (SUPPORTED / the differentia)** | a closure that binds nothing is revocable-at-whim indifference, indistinguishable from not having decided. |
| **Uncertainty** | **NO** | one can decide under certainty (Q5). Uncertainty shapes *how* one decides, not *whether* it is a decision. |
| **Optimality / rationality** | **NO** | a *bad* decision is still a decision (bounded, biased, akratic). Optimality is a norm *on* decisions, not a condition *of* them — same result as Vol I (rationality is not constitutive of agency). |

**Recovered necessary core (SUPPORTED):** `{ ≥2 options, a criterion, a belief, closure,
commitment }`. The first three are the *inputs*; **closure + commitment are the
differentia** that separate deciding from merely preferring or picking. Note what is
*excluded*: uncertainty and optimality. This is the whole point of asking "what is a
decision" before "how to decide" — the EU/Bayesian/RL frameworks are theories of the
*excluded* conditions (how to handle uncertainty optimally), not of decision itself.

## Q2-axioms / D3 · Minimal axioms of decision

- **D1 · Option axiom.** *No decision without ≥2 admissible options.* A forced move is
  not decided. SUPPORTED.
- **D2 · Criterion axiom.** *No decision without a value.* (VT1 inherited from Vol II.)
  Flat value → pick, not decision. SUPPORTED.
- **D3 · Closure axiom.** *A decision terminates deliberation on one option.* The
  defining event is the collapse of the live field to a point. SUPPORTED.
- **D4 · Commitment axiom.** *The closure binds:* it produces an intention that (i)
  guides future conduct and (ii) is a premise reasoned *from*, defeasibly stable against
  costless reconsideration (Bratman). *This is the differentia* and the seed of the final
  theorem (No Commitment → No Decision). SUPPORTED.

**Independence.** D3 (closure) and D4 (commitment) are distinct: one could imagine a
closure that evaporates the instant it forms (closure without commitment) — but that is
exactly a *pseudo-decision* (musing that briefly "lands" then reopens). D4 is what makes
the closure *a decision* rather than a fleeting settling. D1–D2 are the input conditions,
D3–D4 the constitutive act. The irreducible core is **D3 + D4 on a D1+D2 base**.
SUPPORTED.

**What the axioms do NOT require:** a probability distribution (that is *risk*, one rung
of Q5), a utility function (that is *representable* value, VNM), or optimization. A
satisficing, imprecise, boundedly-rational agent that closes-and-commits has *decided*.
The axioms are framework-neutral by design.

## D2 · The decision graph

```
   [ PART I ]                         [ VOL II ]
   Observation → Belief (M→W)         Value (W→M)  ◀── terminal floor
        │  uncertainty                    │  utility (iff VNM)
        └───────────┬────────────────────┘
                    ▼
              ╔═══════════╗
              ║  DECISION ║   the act · combines belief × value over the option set
              ╚═══════════╝   · bounded by CONSTRAINT (admissible actions)
                    │  closure (D3)
                    ▼
              ╔════════════╗
              ║ COMMITMENT ║   W→M · settled, defeasible, binding intention   ── the NEW status
              ╚════════════╝
                    │
                    ▼
                 ACTION  ─────▶ [ VOL I loop: intervene → OUTCOME → Observation ]
                    ▲                                                    │
                    └──────── (akrasia: this edge can fail — F5) ◀───────┘  feedback re-opens Belief
```

**Three structural facts:**
1. **Decision is the only node with two-directional input.** Every other node in the
   whole stack carries one direction of fit; Decision uniquely takes M→W (belief) *and*
   W→M (value) and emits W→M (commitment). It is the computational bridge the hinge doc
   predicted — the *output* twin of Observation's *input* bridge. SUPPORTED.
2. **Commitment sits exactly where Knowledge sits in the Knowing loop** — the licensed
   output of the licensing act, standing ready to cross to the outer (Action ≅
   Assertion). This is the structural claim Q10 and the red team test. LIKELY.
3. **The Action edge is severable** (akrasia, F5): Commitment → Action can fail, which is
   only coherent because Commitment is a distinct prior stage. The graph *predicts*
   akrasia as a severed edge, exactly as Vol I's graph did. SUPPORTED.

## Q5 · The information ladder — certainty / risk / uncertainty / ignorance

Recovered from Knight and Luce–Raiffa. The *belief* input to Decision degrades along a
ladder, and the available machinery degrades with it:

| Rung | Belief state | Machinery that applies | Direction-of-fit note |
|---|---|---|---|
| **Certainty** | outcome known given act | maximize value directly (trivial) | belief degenerate; pure value read-off |
| **Risk** | probabilities known (obj. or subj.) | Expected Utility (VNM/Savage) | belief = a distribution; EU is well-posed |
| **Uncertainty** | probabilities unknown / imprecise | maximin, minimax-regret (Wald/Savage), imprecise prob. | belief = a *set* of distributions; no unique EU |
| **Ignorance** | the *outcome space itself* unknown | — (no framework) | belief lacks a frame — **the silent frontier** |

**The recovered result (SUPPORTED, and it echoes the whole stack):** decision machinery
is **strong at certainty/risk, weakens under uncertainty, and goes silent under
ignorance** (unconceived outcomes — the exact dual of Inquiry's *unconceived
alternatives* and Estimation's *ground-truth gap*). Under ignorance there is no option
set to be complete over, so D1 itself cannot be certified — you may be deciding within a
frame that omits the real options.

**Two frontiers, one decision (SUPPORTED, important).** A decision needs *both* a belief
input and a value input, so it inherits *two* silent frontiers:
- the **belief** frontier — *ignorance* (Q5): unconceived outcomes;
- the **value** frontier — *incommensurability* (Vol II Q8): no common scale.
**A decision is well-posed only where both inputs are tame; it goes silent when *either*
frontier is hit.** This is the sharpest inheritance in Part II: Decision is doubly
bounded, once from each half of the stack it bridges. EU/Bayesian decision theory
occupies the *risk × commensurable* interior — real, powerful, and provably not the whole
space. Recovering this *before* adopting EU is exactly why the mission forbade starting
from EU: it keeps the framework as the interior, not the definition.

## Falsifiers
D1–D4 fail if a clear decision lacks any one of options / criterion / closure /
commitment (D4 is tested by Q10). The "Decision is the only two-directional node" claim
fails if another stack node is shown to take both directions of fit as input. The
double-frontier claim fails if a decision procedure handles *both* genuine ignorance and
genuine incommensurability without covertly re-taming one — not known to exist.
