<div align="center">

# SkynetClaw · THE HOUSE
### An institutional-intelligence operating system — a council of agents that *remembers, deliberates, learns, evaluates itself, and improves.*

`FastAPI` · `SQLite` · `Ollama / OpenAI-compatible` · Python 3.10+ · Apache-2.0

</div>

---

## Why this exists

Most multi-agent systems are a collection of agents that talk. The moment a session
ends, everything is forgotten — no one remembers what was decided, whether it was
right, or who disagreed. **THE HOUSE is built the other way around: memory and
self-awareness are the core, and the agents are the council that operates on top of it.**

A council that forgets every meeting is not a council. A council that cannot evaluate
its past decisions is not intelligent. THE HOUSE keeps an institutional memory, grades
its own predictions over time, tracks each member's reputation, governs every verdict
against a constitution, preserves dissent, and maintains a single **living model of its
own current understanding** that all fourteen members share.

## What it does

- **Council of 14** — Elite Commander, Atlas, Analyst, Strategist, Skeptic, Auditor,
  Governor, Architect, Scout, Storyteller, Concierge, Forecaster, Sentinel, Executor —
  deliberating in parallel, then converging.
- **Institutional Memory** — every deliberation is persisted, archived (SQLite +
  Obsidian), and recallable.
- **Recall Quality** — recalled memories carry *similarity · accuracy · calibration ·
  outcome · validity*; the House recalls **justified** information, never raw history,
  and never cites its own disproven conclusions as authority.
- **Deliberation Briefing** — before the council reasons, it reads a synthesized brief
  of its own graded history: validated lessons, repeated errors, blind spots.
- **Governance Engine** — the constitution is enforced, not advisory: forecasts without
  an invalidation condition, claims without evidence, and omitted minority opinions are
  **rejected**. Dissent is tracked; the House learns when a minority was right.
- **Reputation** — a calibrated, recency-weighted Bayesian skill estimate per member
  (bounded, overconfidence-penalised).
- **The House Mind** — a shared cognitive state that can answer, at any moment:
  *what do we know · what don't we know · what do we believe · why · what changed our mind.*

See [`docs/`](docs/) for the full architecture of each layer.

## Architecture (high level)

```
Directive
   ↓
Recall Quality   ── justified prior memories (validity-graded)
   ↓
Briefing Engine  ── synthesized history (lessons, errors, blind spots)
   ↓
House Mind       ── shared current understanding (read before deliberating)
   ↓
Council (14)     ── parallel deliberation → verdict
   ↓
Governance       ── enforce the constitution; preserve dissent
   ↓
House Mind Update + Memory + Predictions (graded at 30/90/180 days)
   ↓
Verdict
```

The institutional subsystem is a set of focused modules over one SQLite database, with
a versioned, reversible migration history (currently schema **v5**):

| Module | Role |
|---|---|
| `institutional_db.py` | schema owner · migrations · one connection layer |
| `council_memory.py` | persists sessions · outcome-weighted recall |
| `recall_quality.py` | the 5 recall scores + 5 validity states |
| `deliberation_briefing.py` | synthesizes history into a council brief |
| `house_state.py` | **the House Mind** — shared cognitive state + belief evolution |
| `governance_engine.py` | enforces the constitution · minority tracking |
| `agent_reputation.py` | Bayesian, calibrated, recency-weighted reputation |
| `outcome_tracker.py` | 30/90/180-day prediction reviews |
| `scheduler.py` | durable Outcome Clock |
| `council_intelligence_api.py` | `/api/council/*` + the Council Intelligence UI |

## Quick start

Requirements: **Python 3.10+** and (for local models) **[Ollama](https://ollama.com)**.

```bash
# 1. clone, then create config from the templates
cp .env.example .env
cp backend/settings.example.json backend/settings.json   # edit vault_path + model

# 2. install
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# 3. (optional) a local model
ollama pull llama3.1:8b

# 4. initialise the institutional database
cd backend && python migrate.py up

# 5. run
uvicorn main:app --host 127.0.0.1 --port 8766
```

Open the app:
- **THE CONTINENTAL DIVISION** (the chamber) — `THE CONTINENTAL DIVISION.html`
- **Council Intelligence** (House Mind + reputation + governance + outcomes) —
  `http://127.0.0.1:8766/api/council/dashboard`

## Configuration

All machine-specific config lives in two git-ignored files (templates provided):
- `.env` — optional cloud-provider keys and integration tokens (local Ollama needs none).
- `backend/settings.json` — your Obsidian vault path and default model.

No secrets, databases, or personal paths are committed — see `.gitignore`.

## Tests

```bash
cd backend
python -m pytest tests/ -q
```

## License

[Apache-2.0](LICENSE) — free for individuals, research, and systems
under USD 10M/yr attributable revenue; 2% revenue share above that. Attribution required.
Built on FPCOS by Bunyawat Dechanon (ElmatadorZ).
