---
tags: [meta, open-problem, roadmap]
type: roadmap
---

# Roadmap & Open Problems

> Honest, evidence-grounded. The [[Genesis Paradigm]] sprawl test governs the roadmap:
> *which arc does this close?* Work that only widens the forward arc is deferred until the
> return arc catches up.

## Recently closed (2026-07-10)
- [x] **Council outcome loop** — 19 sessions had produced **0 predictions** (English-only
  regex vs Thai verdicts; memory kept only a summary string). Closed structurally: members
  emit `prediction`+`invalidation` as JSON fields, the full verdict persists
  (`verdict_json`), the Commander honors a Constitution REJECT (HOLD unless the operator
  overrides on the record), and the council auto-routes from `/api/agent/run` (exactly
  once per mission). First predictions are on the Outcome Clock; reputation starts moving
  when their 30/90/180-day reviews come due. Evidence: 3 new [[Eval Scoreboard]] cases
  (15/15), live run governance=PASS 1.0, predictions 0→2, dissent 0→1.
- [x] **Watchdog cp1252 silent death** — the :8080 supervisor crashed on its own `→` log
  character at the exact moment of recovery; stderr=DEVNULL made it invisible (af22091).
- [x] **WFE sprawl test** — zero registered workflows, no caller, yet it could execute
  tools → OFF by default (`SKYNET_WFE=1` to enable).

## Recently closed (2026-07-10, second pass — commit e2c3ebd)
- [x] **Vol V bridge (G1)** — `guidance_check.py`: no act on a target nothing guided
  (mission / the loop's own words / a prior observation) — the deviant-chain detector,
  C1's dual on the act side. The Theory of Agency now has ALL its runtime bridges.
- [x] **Continuous evaluation** — the institutional scheduler finally *ticks* (daemon,
  10 min; it only ran at boot before) and runs the behavioral tier nightly at 04:00 →
  the scoreboard becomes a rate with a time series.
- [x] **Outcome Clock in days** — 7-day horizon + `auto_judge`: self-measurable
  predictions (eval-metric) are graded by the scoreboard itself when due.
- [x] **One brain at every door** — task-like Telegram messages route through the full
  agent pipeline (planner/council/skills), owner-gated; plain chat unchanged.

## Engineering roadmap (build)
- [ ] **Eval hard case** — a big workspace that forces 16k compression (stress the
  evidence-loss fix).
- [ ] **VRAM headroom** — the durable [[Execution Runtime & Constraints|:8080]] fix (lower
  `-ngl` or the 7B) — a quality/stability trade-off to decide.
- [ ] **Self-write to the vault** — let the agent promote `Learned/` notes into the curated
  sections on review ([[How This Vault Grows]]).

## Open problems inherited from the theory ([[Recurring Structures|the one hole, 8 ways]])
These are **not bugs to patch** — they are where the system must receive its foundation
from *outside* itself, chosen deliberately:
- the **origin of ends** / authority of terminal value (what SkynetClaw is *for*).
- the **problem of induction** (learning's ground — no finite outcomes justify a policy).
- the **legitimacy of the governor** (why the gate's bound is binding — the operator is it).
- the **deviant-chain problem** (Vol V — what makes an act *guided* vs merely triggered).
- **scalable oversight / requisite variety** (GF5) — a weak governor over a governed that
  keeps acquiring capability; the answer is *construct, don't out-smart*
  ([[Governance — GPS-2]]).

## The standing tension (paradigm-level)
Sovereignty (local, weak brain) vs capability (a stronger cloud brain breaks sovereignty
and makes governance harder). Resolved by the paradigm: **grow the governor's variety, or
refuse the governed's, so the two never diverge** — including on model upgrades
([[Protocol over Model]]).

## See also
[[Genesis Paradigm]] · [[Recurring Structures]] · [[Foundations Session Log]] · [[🏠 HOME]]
