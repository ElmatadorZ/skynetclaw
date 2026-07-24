---
tags: [bridge, security, governance, invariant]
type: bridge
theory: Agency Vol VII (Governance)
runtime: backend/governance.py, governance_config.json
---

# Governance — GPS-2 (the reference monitor)

> The bridge [[Part II — Theory of Agency|Vol VII]] owes — and it *pre-existed* the theory
> (the theory names what it is). **Governance is the second-order regulation of action:** a
> policy of permissible action, *completely mediated*, *enforced*, by a governor separated
> from and superior to the agent. Soft alignment (RLHF / a prompt "please don't") is
> **not** governance — it's influence, and bypasses route around it.

## The policy (deny-by-default)
`governance_config.json` classifies every capability: **allow** (auto) · **escalate**
(human gate) · **deny**. An **unknown tool is DENIED** (GOS-0: capability is a
constitutional act). Split by direction of fit: *observe* → allow, *act* (world-changing)
→ escalate. `GPS2Gate.evaluate(tool, args)` runs **before acting**, in the agent loop and
in `/api/tools/execute`.

## Fail-CLOSED (invariant I5)
A missing monitor (`_GOV is None`) or an `evaluate()` exception now **DENIES** (was
ALLOW — the audit flagged fail-open as a P0). *A gate that fails open is not a gate.*

## The paradigm made measurable (ratified 2026-07-09)
The [[Eval Scoreboard]] case `paradigm_capability_coverage` FAILS if any registered tool
lacks a governance classification → 100% coverage is a checked invariant. This is the
[[Genesis Paradigm]] law — *no capability without its governing invariant* — enforced by
measurement. (Ratification closed 7 orphan tools.)

## The theory it enforces (the capstone)
- **GT1:** No complete mediation → no governance (the 8th [[Recurring Structures|No-X→No-Y]]).
- **GT3 (Ashby):** requisite variety is governance's ceiling — you cannot completely govern
  a governed richer than the governor → the answer is **construct** (shrink the governed's
  variety: least privilege, minimal TCB), not a smarter rule. **This system's live failure
  is now GF5 (variety), not a bypass** — a weak governor over a governed that keeps
  acquiring capability → exactly why the paradigm law must hold for model upgrades too.
- The **Security Theory is Vol VII specialized to authority** → [[Capability Escalation & Threat Model]].

## See also
[[Capability Escalation & Threat Model]] · [[Genesis Paradigm]] · [[Eval Scoreboard]] · [[🏠 HOME]]
