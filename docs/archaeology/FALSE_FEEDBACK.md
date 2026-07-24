# False Feedback — mechanisms that look adaptive but change no behaviour

> A mechanism is *false feedback* if it presents as learning/adaptation yet leaves future
> behaviour unchanged. Distinguished here from *true feedback* (persists + actuates).
> Tags: SUPPORTED / LIKELY / UNKNOWN.

## Test applied
For each mechanism: (a) does it persist? (b) does any code branch on its output? If **both
no**, it is false feedback (informational only). Evidence: persistence probe (state-writes)
+ the live-loop comments.

## FALSE feedback (looks adaptive; behaviour unchanged) · SUPPORTED
| Mechanism | The illusion | Why it's false |
|---|---|---|
| **belief_revision** | "the House revises beliefs when contradicted" | persists nothing; "no promotion/demotion/correction"; only renders a drift count |
| **first_principles** | "the House learns durable principles" | recomputed each run; "candidates, not rules"; never committed |
| **theory** | "the House forms theories/laws" | "not laws"; state-writes=0 |
| **experiment** | "the House runs experiments to test itself" | "**never runs anything**" — design without execution = no measurement = no adaptation |
| **calibration** | "the House corrects its confidence" | "MEASURE ONLY — does not alter any runtime decision" |
| **decision** | "the House decides its next move from evidence" | "does not decide for the runtime" — advisory text only |
| **paradigm** | "the House undergoes paradigm shifts" | renders a status; nothing consumes it |
| **unknowns** | "the House closes its knowledge gaps" | maps gaps; no code schedules work against the map |
| **belief_timeline** | "a history of belief evolution" | state-writes=0 — it renders, it does not record |

Collectively: an entire suite that reads like an adaptive scientific mind, whose net effect
on the next run is **one paragraph of advisory text and one event-count** — both regenerated
from scratch, neither remembered.

## TRUE feedback (persists AND actuates) · SUPPORTED — and it is narrow
| Mechanism | Why it's real |
|---|---|
| **reinforcement** (capability_weights.json) | persists; re-orders recalled capabilities by weight; rate-limited |
| **metalearning** (learning_strategies.json) | persists learned strategies |
| **engineering regression** (test suites + quality gate) | persists (committed tests); blocks merges — enforced |
Note: the first two are **capability/strategy** (excluded from "belief"); the third is the
**human dev loop**, not cognition.

## The asymmetry (SUPPORTED)
- **Belief-flavoured feedback: 100% false** (0 of 8 organs persist or actuate).
- **Capability-flavoured feedback: true** (2 stores) — but out of scope for "belief."
- **Engineering feedback: true** — but human-executed.

## Consequence for the hypothesis
The "operational epistemology" is, at the *belief* layer, **false feedback**: a beautifully
instrumented gauge that measures the organism's epistemic state and displays it, while the
organism's *behaviour* is driven by capability weights and a stochastic model — neither of
which the epistemic gauge controls. **SUPPORTED.**
