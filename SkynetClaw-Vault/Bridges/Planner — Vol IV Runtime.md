---
tags: [bridge, planning]
type: bridge
theory: Agency Vol IV (Planning)
runtime: backend/task_planner.py
commit: 11833ce
---

# Planner — Vol IV Runtime (decompose → build across rounds → save)

> The bridge [[Part II — Theory of Agency|Vol IV]] owes. Fixes a reproduced failure: asked
> to *build a DCA dashboard*, the weak model streamed ~200 lines of HTML into the chat,
> **never saved it**, regenerated inconsistently across turns, and halted ("PLAN เปล่า").
> The task was bigger than one reliable generation and nothing decomposed it, budgeted
> rounds, built it piece by piece, or assembled + saved the result.

## What it does (`plan_and_execute`)
1. **DECOMPOSE** — one planning call → 3–6 ordered file sections
   (Plan = Commitment ⊕ Dependency ⊕ Irreversibility, temporal order induced).
2. **BUILD per round** — budgeted to the connection window ([[Protocol over Model|resolve_window]]).
   A weak model won't re-emit the whole growing file, so from round 2 it produces a
   **fragment** and the planner **merges** it into the HTML deterministically
   (`merge_fragment`: CSS into `<style>`, JS/markup before `</body>`). Whole-file returns
   are still accepted, guarded against truncation (**anti-drop**).
3. **WRITE** — the **planner** writes the file itself; the model is *never trusted* to call
   `write_file` (the exact thing that failed).
4. **VERIFY + SUMMARIZE** — plus a **model-unavailable guard** (fails clearly when the
   runtime is down, instead of looping empty).

## Auto-route
A clear build-a-single-file task **with a workspace** routes to the planner in
`/api/agent/run` (disable: `settings.planner_autoroute=false`). Endpoint:
`/api/agent/plan_execute`.

## Proof (live, once [[Execution Runtime & Constraints|:8080]] was stabilized)
The DCA build that previously produced a 655-char skeleton now produces a **complete
7719-char dashboard** (5 rounds all accepted + growing: 3257 → 4274 → 5910 → 7031 → 7719),
with valid HTML + CSS + JS + charts, **saved**. The reproduced failure is closed
end-to-end — and it needed *both* the planner **and** a runtime that no longer dies
mid-build (see [[Execution Runtime & Constraints]]).

## See also
[[Runtime Bridges]] · [[Execution Runtime & Constraints]] · [[Part II — Theory of Agency]] · [[🏠 HOME]]
