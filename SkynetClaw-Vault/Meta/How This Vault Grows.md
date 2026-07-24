---
tags: [meta, invariant]
type: protocol
---

# How This Vault Grows

> This is what makes the vault a **second brain**, not a doc dump: a protocol for how it is
> maintained, by humans **and by SkynetClaw itself**, so it compounds instead of rotting.

## Principle
The vault is the **durable memory** of the [[Genesis Paradigm|paradigm]]: recovered theory
+ its runtime bridge + the operational truth. It follows the same law: *every capability
gets a note; every note links to its evidence.*

## When to add / update a note
- **A new [[Runtime Bridges|bridge]] is built** → add a note under `Bridges/`, link it from
  [[Runtime Bridges]] and the theory it enforces. (Bridge note template below.)
- **A theory volume is recovered** → summarize + link into [[Theory Stack Map]] (do **not**
  re-copy `docs/` — link to it).
- **A failure is diagnosed / an invariant added** → record the root cause and the fix in the
  relevant Operations/Security note (evidence-first: cite the commit).
- **The system self-learns something durable** → see below.

## How SkynetClaw writes to its own second brain (self-learning)
The system's Obsidian tools (`obsidian_write_note` / `read` / `search` / `list`) point at
this vault (`settings.json → obsidian_vault`). So the agent can:
- **Read** foundations before acting (grounding — "consult the vault first").
- **Write** a note when it discovers something durable (a resolved failure pattern, a new
  operational fact) — the human-facing twin of [[Proprioception — Learning|proprioception]]
  (which feeds the *prompt*; the vault is the *narrative* memory).
- The `Learned/` folder is the agent's write area — human-authored foundations stay in the
  curated sections; the agent's discoveries accrue in `Learned/` and get promoted into the
  curated notes on review.

## Bridge note template
```
---
tags: [bridge, ...]
theory: <volume>   runtime: backend/<file>.py   commit: <hash>
---
# <Bridge> — <one-line>
> The theory it enforces + why.
## What it does · ## The loop it closes · ## Proof (evidence/commit) · ## See also
```

## The single rule
**A note with no `[[link]]` and no evidence (commit / file / measurement) is not done.**
The vault's value is the graph, not the pages.

## See also
[[Reproduce & Rebuild]] · [[Proprioception — Learning]] · [[Genesis Paradigm]] · [[🏠 HOME]]
