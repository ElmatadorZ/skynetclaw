# Responsibility Evolution Graph (organism-level)

> The repository read as a living organism, not a class diagram. Nodes are
> **responsibilities** (what the organism must do), not code. Edges are ownership
> movements across generations. Tags: SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.
>
> **Observation basis (honesty):** only two generations are directly observed —
> **G1** (the V1 artifact, source in hand) and **G3/now** (the current repo). **G2**
> (cognition living in prompt/skill text) rests on a single self-report and is
> detail-**UNKNOWN**. **G4** (kernel vision) is design-only.

## Generations (named by nature, not by file)
| Gen | Nature | Evidence | Tag |
|---|---|---|---|
| **G1** | The Deterministic Compound — closed, offline, one owner per job | V1 source | SUPPORTED |
| **G2** | The Prompt Migration — cognition leaves code, lives in prompt/skill text | one self-report ("protocol lived only in skill prompt text + a workflow endpoint") | LIKELY (details UNKNOWN) |
| **G3 / now** | The Live Autonomous Organism — open, persistent, multi-agent, governed | current repo | SUPPORTED |
| **G-freeze** | The Evidence-Governed Organism — RC-1 frozen, Trust discipline | Trust/RC docs | SUPPORTED |
| **G4** | The Kernel Consolidation — one owner per job again, at OS scale | V3 design docs | SUPPORTED (design) / N/A (impl) |

## The responsibilities (name-free) and their ownership trajectory
`owners` = how many distinct places answer this responsibility.
| # | Responsibility (what the organism must do) | G1 owners | G3 owners | Movement | Tag |
|---|---|:--:|:--:|---|---|
| R1 | **Dispatch** — decide who/what handles a task | 1 | many (≥5) | **SPLIT → DUPLICATED** | SUPPORTED |
| R2 | **Decompose / Plan** | 1 (shallow, one path only) | several | **SPLIT + deepened** | SUPPORTED |
| R3 | **Produce** — make the artifact | few (pure fns) | loop + tools + prompt-skills | **EVOLVED** | SUPPORTED |
| R4 | **Judge** — evaluate quality | 1 | many (≥6) | **SPLIT → DUPLICATED** | SUPPORTED (existence) |
| R5 | **Verify truth** — handle claims/evidence | 1 (advisory, human-adjudicated) | enforced gate + epistemic suite | **EXPANDED + moved in-machine** | SUPPORTED (existence); lineage LIKELY |
| R6 | **Revise / Learn** — refine, reflect, remember lessons | 1 | several | **SPLIT** | LIKELY |
| R7 | **Voice** — style / persona / brand identity | 1 (structured, numeric) | scattered prose + skills | **SUPERSEDED + SCATTERED** | SUPPORTED |
| R8 | **Remember** — hold state | 1 (ephemeral, in-proc) | many (≥8, persistent) | **SPLIT + made durable** | SUPPORTED |
| R9 | **Bound the model** — contain/adapt stochasticity | 1 (sole stochastic point) | provider/runtime layer | **EVOLVED; the *belief* weakened** | SUPPORTED |
| R10 | **Persist** — durable cross-run state | 0 | many | **EMERGED** | SUPPORTED |
| R11 | **Govern** — permissions, safety, rules | ~0 (a lone risk-disclosure nudge) | permission + anti-hallucination + immutable-rules layer | **EMERGED** | SUPPORTED |
| R12 | **Perceive self** — know own runtime state (files/model/net/mission) | 0 (no runtime world existed) | weak / partial | **EMERGED but UNDERDEVELOPED** ← the live gap | SUPPORTED |
| R13 | **Perceive world** — live external data (net/time/prices) | 0 (offline, mock only) | live | **EMERGED** | SUPPORTED |

## The graph (ownership flow, not classes)
```
                 G1 (one owner each)                 G3 / now (ownership fragmented + new organs)
 R1 Dispatch     ●──────────────────────────────────▶ ◍◍◍◍◍  (split → duplicated)
 R2 Plan         ●──────────────────────────────────▶ ◍◍◍    (split, deeper)
 R3 Produce      ●──────────────────────────────────▶ ◍◍     (loop+tools)
 R4 Judge        ●──────────────────────────────────▶ ◍◍◍◍◍◍ (split → duplicated)
 R5 Verify-truth ●·····(advisory, to humans)·········▶ ◍◍◍◍  (enforced + epistemic suite)   ▲ moved in-machine
 R6 Revise/Learn ●──────────────────────────────────▶ ◍◍◍    (split)
 R7 Voice        ●─(structured StyleProfile)─ ✗ gone ─▶ ◌◌   (scattered prose; structured owner DIED)
 R8 Remember     ●─(ephemeral)──────────────────────▶ ◍◍◍◍◍◍◍◍ (split + durable)
 R9 Bound-model  ●─(deterministic core)── belief ✗ ─▶ ◍     (still one layer; the *belief* lost)
 R10 Persist     ∅ ─────────────── EMERGED ─────────▶ ◍◍◍
 R11 Govern      ∅ ─────────────── EMERGED ─────────▶ ◍◍◍
 R12 Perceive-self ∅ ───── EMERGED (weak) ──────────▶ ◌     ← the reality-awareness gap (proprioception)
 R13 Perceive-world ∅ ──────────── EMERGED ─────────▶ ◍◍
   ●=single owner  ◍=multiple owners  ◌=weak/scattered  ∅=did not exist  ✗=belief/mechanism died
```

## Answering the six questions the organism poses
- **Which responsibilities SPLIT?** R1 Dispatch, R4 Judge, R6 Revise, R8 Remember (each 1→many). SUPPORTED.
- **Which MERGED?** Essentially none durably; the one merge attested is a *protocol* re-merged into the loop after G2 duplicated it (LIKELY). No responsibility collapsed two into one.
- **Which became DUPLICATED?** R1 and R4 most severely (the two the organism once kept singular). SUPPORTED.
- **Which DISAPPEARED?** **At the responsibility level — none.** What disappeared were *mechanisms/beliefs*: the structured Voice engine (R7 owner) and the deterministic-core guarantee (R9 belief). The *responsibilities* R7/R9 persist. SUPPORTED.
- **Which EMERGED?** R10 Persist, R11 Govern, R12 Perceive-self, R13 Perceive-world. SUPPORTED.
- **Which remained INVARIANT (as responsibilities)?** R1–R9 all still exist and are still required; only their **ownership count and mechanism** changed. SUPPORTED.

## The organism-level finding (LIKELY)
The organism **lost no function and grew new senses** (persist, govern, perceive) — but it
**fragmented ownership** of the jobs it once did with a single organ each (judge, remember,
dispatch), and it **inverted two constitutive beliefs**: determinism and truth-locus (see
[WORLD_MODEL](WORLD_MODEL.md)). Its newest sense — **proprioception (R12, knowing its own
state)** — is the least developed, which is exactly where its live failures appear.
