# Release Readiness — SkynetClaw · THE HOUSE

This repository is prepared for public release. This document records what ships,
what doesn't, and the first-run path for a new user.

## State

- **Tests:** 129 passing (institutional subsystem); run `cd backend && python -m pytest tests/ -q`.
- **Schema:** v5, with reversible migrations `001`–`005` (`python migrate.py up`).
- **Secrets/personal data:** scrubbed — final scan reports **no** secrets or personal
  paths (`D:\…`, vault paths, API keys) in any shippable file.
- **License:** Apache-2.0 (`LICENSE`).

## What ships (tracked)

```
README.md · LICENSE · CONTRIBUTING.md · .gitignore · .env.example
THE CONTINENTAL DIVISION.html        ← the app (chamber) + Council Intelligence link
bridge_console.html                  ← observability surface (served)
docs/                                ← architecture & reports (this folder)
backend/
  main.py + 42 modules               ← the institution + agent runtime
  council_intelligence.html          ← merged UI: House Mind · Reputation · Governance · Outcomes · Memory
  settings.example.json · requirements.txt
  migrations/ (001–005)  tests/ (8 suites)  skills/ (15)
  prompts/ · hooks/                  ← prompt + hook assets
QUICKSTART.txt · start.bat · setup_ollama.bat · install.bat · Modelfile_Skynet-Claw · logo.svg · portraits/
```

## What does NOT ship (git-ignored)

- `.env`, `backend/settings.json` — secrets & machine config (templates ship instead).
- `*.db`, `*.jsonl`, `backend/logs/`, `backend/backups/`, `backend/sessions/` — runtime data & logs.
- Runtime state: `agent_memory.json`, `atlas_genome.json`, `exec_approvals.json`,
  `pending_gates.json`, `skills_index.json`, `_MISSION_LEDGER.json`, `backend/SELF.md` (regenerated on boot).
- `backend/memory/`, `backend/Skynet_Agent/`, `workspace/`, `ToolsList/` — per-install / legacy.
- `_archive/` — superseded files moved aside during cleanup (review, then delete).
- `__pycache__/`, `.venv/`, backups (`*.bak`), and editor/OS junk.

## Cleanup performed

- Archived to `_archive/`: 4 `main.py` backups, 5 `settings.json` backups, root dev/debug
  scripts (`debug_*`, `fixed_agent_room`, `test_import`, `process_logo`, `add_telegram_bot`),
  superseded UIs (`index.html`, `multimodel_panel.js`, `masterpiece_dashboard.html`,
  `openclaw_reverse_engineering.html`, `skynetclaw_mindmap.html`), and the
  `install_masterpiece` installer + `github_skills_report` artifact.
- Merged two dashboards (`council_dashboard.html` + `house_mind_panel.html`) into one
  `backend/council_intelligence.html`, linked from the app header.
- Organized all architecture/report docs into `docs/`.

## Manual step (OS-locked junk)

Three entries could not be deleted from the build environment (held by the OS) and are
git-ignored so they won't ship. Delete them on your machine before publishing:
`$null`, the empty `-p/` folder, and the broken 9-byte `gh_windows_amd64.zip`.

## First run (new user)

```bash
cp .env.example .env
cp backend/settings.example.json backend/settings.json     # set vault_path + model
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
ollama pull llama3.1:8b                                     # optional, for local models
cd backend && python migrate.py up
uvicorn main:app --host 127.0.0.1 --port 8766
```

Then open `THE CONTINENTAL DIVISION.html`, or the merged UI at
`http://127.0.0.1:8766/api/council/dashboard`.

## Pre-publish checklist

- [ ] `git init` (history starts clean — none of your data was ever committed)
- [ ] delete the 3 OS-locked junk entries above
- [ ] review and delete `_archive/`
- [ ] confirm `git status` shows no `.env`, `*.db`, `settings.json`, or `*.jsonl`
- [ ] `cd backend && python -m pytest tests/ -q` → all green
