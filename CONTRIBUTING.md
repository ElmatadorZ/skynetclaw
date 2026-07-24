# Contributing to SkynetClaw · THE HOUSE

Thank you for helping the House get smarter. A few principles keep this codebase
coherent — they mirror the system's own values.

## Principles

1. **Memory and honesty are the product.** Features that make the House *more
   confidently wrong* are regressions, even if they pass tests. Preserve uncertainty,
   dissent, and governance signals — never strip them.
2. **One database, one schema owner.** All institutional tables live in
   `backend/institutional_db.py`. Schema changes are **additive migrations** with a
   version bump and a matching `backend/migrations/NNN_*.{up,down}.sql`.
3. **Reads are lock-free.** Hot paths call `institutional_db.init_once()`, never
   `ensure_schema()`. Don't reintroduce per-call schema writes.
4. **Best-effort wiring.** Institutional hooks in `agent_council.py` / `main.py` are
   wrapped in `try/except` — a memory failure must never break a deliberation.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && python migrate.py up
```

## Tests

Every change to the institutional subsystem needs a regression test. Run:

```bash
cd backend
python -m pytest tests/ -q
```

Tests use an isolated temp database (the `db` fixture sets `INSTITUTIONAL_DB`); they
never touch your real `skynerclaw.db`. Aim to keep coverage high on changed modules.

## Migrations

```bash
python migrate.py up          # apply
python migrate.py status      # show applied versions
python migrate.py down NNN    # roll back one migration
```

A migration must reproduce, via raw SQL, the exact schema `ensure_schema()` produces
(the two are kept in lockstep — see `institutional_db.ADD_COLUMNS`).

## Style

- Standard library first; the only runtime deps are FastAPI, uvicorn, httpx, pydantic.
- Deterministic, testable cores; let the LLM reason *over* structured output rather than
  generating the structure where a rule will do.
- Don't commit secrets, databases, logs, or personal paths — `.gitignore` enforces this;
  double-check before a PR.

## Pull requests

Keep PRs focused on one capability. Describe what changed, why, and which regression
test guards it. If you touch reputation, recall, or governance, explain how the change
keeps the House epistemically stable.
