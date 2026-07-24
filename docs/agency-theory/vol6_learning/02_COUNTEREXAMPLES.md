# Agency — Volume VI · 02 — Counterexamples & Boundary Cases

> Pure philosophy. Ten cases, each ruled **Learning** or **Not-Learning** with the
> discriminating reason, tested against `learning = cross-episode, outcome-driven,
> credit-assigned disposition-change`. Two of them (LLM-in-context, evolution) are decisive
> for how SkynetClaw can learn at all.

---

## The ten verdicts

| Case | Verdict | Discriminating reason |
|---|---|---|
| **Calculator / fixed program** | **Not-Learning** | no mutable disposition (LA1) |
| **Lookup table / logging** | **Not-Learning** | memory without disposition-change (Q1 diff.) |
| **Thermostat** | **Not-Learning** | in-moment control, no cross-episode retention (LA4) |
| **Superstition (Skinner's pigeon)** | **Learning** (broken) | credit *mis*-assigned — real learning, pathological |
| **Overfit model** | **Learning** (fails to generalize) | learned the sample not the population (Vapnik) |
| **One-shot Bayesian update** | **Learning** (minimal) | outcome → changed belief, retained |
| **Human skill acquisition** | **Learning** (paradigm) | practice-outcome → improved policy, compiled |
| **Evolution** | **Learning** (population-scale) | selection = credit assignment across generations |
| **LLM in-context "learning"** | **Not-Learning** (adaptation) | no cross-episode retention — the seat (weights) is frozen |
| **LLM fine-tuning** | **Learning** | persistent weight-change from outcomes |

## Dissected — the cases that carry weight

### LLM in-context "learning" vs fine-tuning — *the decisive pair for SkynetClaw*
A model given examples in its prompt adjusts its behaviour *within that context* — but the
change **evaporates when the context ends**; the weights never move. By LA4 (retention) this
is **adaptation, not learning** — the exact twin of the thermostat (in-moment, non-retained),
one level up. **Fine-tuning** *is* learning (persistent weight-change). This pair yields the
volume's operative result for the host system: **a frozen-weight model can *adapt* but cannot
*learn*; therefore the system's learning must live in a seat that *does* persist across
episodes — an external memory that changes future context.** The choice is not "learn in
weights or don't learn" — it is "learn in weights or learn in the scaffolding," and with
weights frozen, the scaffolding is the only seat. SUPPORTED, and it is why the runtime bridge
(self-context / proprioception) *is* the system's learning organ, not a substitute for one.

### Superstition (Skinner) — *credit assignment is real, proven by its failure*
A pigeon rewarded on a timer that happens to fire after a head-bob learns to head-bob — it
**mis-assigned credit** (the bob did not cause the reward). This is genuine learning
(cross-episode, outcome-driven, retained) with a **broken credit-assignment node**. It proves
LA3 is a real, separable component: a system with intact feedback + retention but faulty
credit *learns the wrong thing*. It is the acting-side inheritance of the non-ergodic crux
(Q5) at its starkest — with counterfactuals hidden, correlation is mistaken for cause.
SUPPORTED.

### Evolution — *population-scale learning; the teleonomy result recurs*
Natural selection is learning **without a learner**: the population's gene-frequencies are
the disposition; differential survival is the credit assignment; generations are the episodes.
It is *teleonomic* learning (Vol I) — installed by selection, held by no individual. This
shows learning is **substrate-neutral and scale-neutral** (a genome learns, a brain learns, a
market learns) and that the disposition-seat need not be inside one agent. It also mirrors
Vol I's plant/teleonomy boundary: learning-without-a-holder is the floor, exactly as
agency-without-a-holder was. SUPPORTED.

### Lookup table / logging vs one-shot Bayesian update — *memory ≠ learning*
A growing log of outcomes that never changes what the system *does* is memory, not learning
(Q1). The minimal thing that crosses the line is a **single Bayesian update**: one outcome →
a changed posterior → different future behaviour. The discriminator is precisely whether the
stored outcome *re-enters the disposition*. This is the exact test the runtime bridge must
pass: SkynetClaw already **has** the log (agent_runs, warrant_log) — it is *memory*; it
becomes *learning* only when that log **changes a future decision**. The system today is at
the "lookup table" verdict; the bridge moves it to "Bayesian update." SUPPORTED, and
directly diagnostic.

### Overfit model — *learning that fails the generalization node*
A model that fits its training outcomes perfectly yet fails on unseen cases has **learned the
noise** (Vapnik): the Generalization node broke while Feedback/Credit/Update worked. It shows
"learning" and "learning-that-generalizes" are different — a system can learn *and* be wrong
about the future, which pre-stages the problem of induction (Vol VI·04). SUPPORTED.

## What the counterexamples establish
1. **Memory ≠ learning; adaptation ≠ learning** — logging and in-context both fail LA4/Q1;
   the discriminator is a *retained disposition-change*. SUPPORTED.
2. **The frozen model can only adapt** — so SkynetClaw's learning seat *must* be the
   persistent scaffolding. The single most consequential recovered fact for the build.
   SUPPORTED.
3. **Learning is substrate/scale-neutral and can be teleonomic** — evolution learns without a
   learner; the seat can be a population or an external store, not only weights. SUPPORTED.
4. **Credit assignment and generalization are separable, breakable nodes** — superstition and
   overfitting break each independently, validating the graph. SUPPORTED.

## Falsifiers
Any verdict is refuted by showing the case has/lacks the discriminator claimed — e.g. exhibit
in-context adjustment that *persists* across fresh contexts with frozen weights (would make
it learning and refute the frozen-seat result), or a log that is called learning though it
never changes behaviour (would collapse the memory≠learning line).
