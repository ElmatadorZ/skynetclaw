# World Model Archaeology — the reality each generation assumed

> Not the code — the **implicit model of the world** the organism was built to live in.
> Recovered from what the code *assumes exists*. Tags: SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.

## G1 — the world Genesis V1 assumed (SUPPORTED, from the artifact)
| Axis | V1's assumed world | Evidence |
|---|---|---|
| **Openness** | **Closed.** The world is an in-process sandbox. | "No external HTTP calls; safe to run offline with mock data." SUPPORTED |
| **Liveness** | **Static / dead.** No real time, no live prices; data is fabricated. | `mock_prices()` generates fake series; no datetime/net. SUPPORTED |
| **Extent** | **Domain-bounded.** Reality = 4 business verticals; nothing else exists. | `Domain` enum {Content,Finance,Marketing,Sales} at the type level. SUPPORTED |
| **Truth** | **External to the machine.** The machine *flags*; humans *adjudicate*. | fact-flags "mark for human review." SUPPORTED |
| **Reasoner** | **Deterministic code is the mind; the model is a bounded oracle.** | "Deterministic core. LLMBridge is the only stochastic component." SUPPORTED |
| **Continuity** | **Ephemeral.** The world resets each run; no history. | memory is in-process, non-persistent. SUPPORTED |
| **Population** | **Solitary + synchronous.** One task, one agent, one call. | `mind.run(spec)->Result`; static single-agent route. SUPPORTED |
| **Self-knowledge** | **None needed.** There is no runtime state to perceive. | no files/model/net/mission concept exists. SUPPORTED |
> **V1 lived in a SIMULATED, CLOSED, TIMELESS world where truth was a human's job and the
> machine's own reasoning was trustworthy because it was deterministic.**

## G3 / now — the world SkynetClaw assumes (SUPPORTED unless noted)
| Axis | Current assumed world | Evidence |
|---|---|---|
| **Openness** | **Open.** Real internet, filesystem, runtimes, providers. | live web/prices/news fetch; workspace mount; connections DB. SUPPORTED |
| **Liveness** | **Live.** Real datetime injected; real-time data; "no stale training answers." | datetime banner + live-data directive + realtime endpoints. SUPPORTED |
| **Extent** | **Unbounded.** No domain enum; open tasks + open-ended skills/tools. | 50 tools, open skill folders, no `Domain` type. SUPPORTED |
| **Truth** | **Internal + enforced.** An anti-hallucination gate blocks unfactual writes; an epistemic suite reasons about claims. | shadow gate + first-principles/belief/theory/experiment organs. SUPPORTED (existence) |
| **Reasoner** | **The stochastic model IS the mind; code POLICES it.** Determinism belief inverted. | LLM calls pervade plan/produce/judge; scaffolding governs them. SUPPORTED |
| **Continuity** | **Persistent.** Missions, lessons, beliefs, history survive runs. | SQLite/WAL + durable stores. SUPPORTED |
| **Population** | **Plural.** A council of specialized minds deliberates; concurrent jobs (bots, runs). | 14-role roster; background jobs. SUPPORTED |
| **Self-knowledge** | **Assumed-but-blind.** The world model *presumes* the organism should know its own state, yet perception of it is weak. | reality-awareness audit: workspace/model/net/mission not reliably grounded. SUPPORTED |
> **SkynetClaw lives in a REAL, OPEN, LIVE, PERSISTENT, MULTI-MIND, GOVERNED world where
> truth moved inside the machine — but it perceives that world (especially *itself*)
> unreliably.**

## The four inversions (SUPPORTED / LIKELY)
| # | Belief | G1 | now | Type |
|---|---|---|---|---|
| I-1 | **Locus of trust** | trust the deterministic core, distrust the model | trust the model as reasoner, *police* it | **INVERTED** (SUPPORTED) |
| I-2 | **Locus of truth** | truth is the human's (external) | truth is the machine's (enforced, internal) | **INVERTED** (SUPPORTED) |
| I-3 | **Nature of the world** | closed / simulated / timeless | open / real / live / persistent | **INVERTED** (SUPPORTED) |
| I-4 | **Nature of the self** | no self to perceive | a self that *must* be perceived — but isn't, well | **EMERGED, unmet** (SUPPORTED) |

## The one deep tension (LIKELY)
V1's coherence came from a **matched** world model: closed world + deterministic mind +
external truth → internally consistent, if narrow. SkynetClaw opened the world, made the
mind stochastic, and pulled truth inside — three simultaneous inversions — **without**
completing the fourth (self-perception). The organism's live failures (searching a brand
as if it were news; asking for a file it already holds) are all **I-4 failures**: a mind
acting in a real world it cannot fully *sense* — especially its own state. The world model
grew faster than the organism's senses. *(LIKELY — consistent with every reproduced failure
this session, not proven exhaustively.)*

## Unknowns
- **UNKNOWN:** whether the inversions (I-1..I-3) were deliberate design decisions or
  emergent drift — no decision record recovered (see DECISIONS_REQUIRING_EVIDENCE).
- **UNKNOWN:** G2's world model (the prompt-migration era) — not observed.
