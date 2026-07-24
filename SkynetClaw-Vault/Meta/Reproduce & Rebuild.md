---
tags: [meta]
type: runbook
---

# Reproduce & Rebuild

> How to bring SkynetClaw up from scratch, and how to rebuild understanding of it from this
> vault. Reproducibility is a [[Genesis Paradigm]] requirement (a system you can't rebuild
> you don't understand).

## Bring the system up
1. **Execution model** — `launch_execution_runtime.ps1` starts `llama-server.exe` (Qwen2.5-14B,
   `-c 16384`, `--parallel 1`, `-ngl 99`) on `:8080`. See [[Execution Runtime & Constraints]].
2. **Backend** — `python backend/main.py` (`:8766`). It **auto-starts the watchdog** (keeps
   `:8080` alive) — no separate step needed.
3. **UI** — open `index.html`. `start.bat` does 1–3 + opens the UI.
4. **Stealth browser (optional)** — `../stealth-browser-mcp-master/start_bridge.bat` (`:8781`,
   its own Python 3.13 venv). Auto-started by `start.bat` if installed.

## Verify it's healthy
- `python backend/eval_suite.py` → substrate should be **12/12 = 1.0** ([[Eval Scoreboard]]).
- `POST /api/eval/run?behavioral=true` → the honest agent success measurement (needs `:8080`).

## Rebuild the *understanding* (read order)
1. [[What SkynetClaw Is]] → [[Genesis Paradigm]] (identity + governing law).
2. [[System Map]] → [[Protocol over Model]] (the shape; the model is swappable).
3. [[Runtime Bridges]] → the 4 bridge notes (the paradigm in action).
4. [[Theory Stack Map]] → [[Recurring Structures]] (the foundation the bridges rest on).
5. [[Capability Escalation & Threat Model]] (why it's safe) → [[Execution Runtime & Constraints]] (the real bottleneck).
6. [[Roadmap & Open Problems]] (where it goes) → [[Foundations Session Log]] (how it got here).

## Rebuild the *theory* (in the repo)
Full text: `docs/agency-theory/` (Vols I–VII + the hinge), `docs/warrant-theory/`,
`docs/inquiry-theory/`, `docs/belief-science/`, `docs/estimation_theory/`,
`docs/GENESIS_PARADIGM.md`. Method: **recover first, synthesize later; every theorem
falsifiable; red-team; tag SUPPORTED/LIKELY/OPEN/FALSIFIED.**

## Key per-machine config (NOT in git)
`settings.json` (connections, `obsidian_vault`, `exec_connection`/`exec_model`),
`governance_config.json` (the policy — migrates from `DEFAULT_CONFIG` on version bump).

## See also
[[How This Vault Grows]] · [[System Map]] · [[🏠 HOME]]
