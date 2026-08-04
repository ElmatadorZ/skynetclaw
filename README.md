<div align="center">

# SkynetClaw · THE HOUSE

### An institutional-intelligence operating system — a council of agents that *remembers, deliberates, learns, evaluates itself, and improves.*

[![CI](https://github.com/ElmatadorZ/skynetclaw/actions/workflows/ci.yml/badge.svg)](https://github.com/ElmatadorZ/skynetclaw/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Local first](https://img.shields.io/badge/local--first-Ollama%20%7C%20llama.cpp-brightgreen.svg)](#choosing-a-model)

`FastAPI` · `SQLite` · runs on **your** machine · no account, no telemetry, no cloud required

</div>

---

## Why this exists

Most multi-agent systems are a collection of agents that talk. The moment a session ends,
everything is forgotten — no one remembers what was decided, whether it was right, or who
disagreed. **THE HOUSE is built the other way around: memory and self-awareness are the core,
and the agents are the council that operates on top of it.**

A council that forgets every meeting is not a council. A council that cannot evaluate its past
decisions is not intelligent. THE HOUSE keeps an institutional memory, grades its own predictions
over time, tracks each member's reputation, governs every verdict against a constitution,
preserves dissent, and maintains a single **living model of its own current understanding** that
all fourteen members share.

---

## Install in 5 minutes

**Requirements:** Python 3.10+ · ~500 MB disk · a model (local via [Ollama](https://ollama.com), or
any cloud API key). **No GPU required** — a small local model runs on CPU.

```bash
git clone https://github.com/ElmatadorZ/skynetclaw.git
cd skynetclaw

# 1 — configuration (both files are git-ignored; templates are provided)
cp .env.example .env
cp backend/settings.example.json backend/settings.json

# 2 — dependencies (16 packages + 2 for tests, no build step)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# 3 — a local model (skip if you are using a cloud API)
ollama pull llama3.1:8b

# 4 — create the institutional database
cd backend && python migrate.py up

# 5 — run
python -m uvicorn main:app --host 127.0.0.1 --port 8766
```

> **Shortcuts:** `./start.sh` (Linux/macOS) or `make setup && make run` does steps 1–5 for you.
> `docker compose up -d` skips Python entirely. Full guide: **[docs/INSTALL.md](docs/INSTALL.md)**.

Then open **`THE CONTINENTAL DIVISION.html`** in a browser — that is the chamber where you talk to
the council.

### What you should see

```
[Governance] GPS-2 gate armed — deny-by-default · human gate on irreversible tools
[Kernel] PRE_ACT armed — governance.gps2, shadow.fabrication, approvals.prior_deny, run.tool_allow
[Kernel] PRE_VALIDATE armed — cvl.quality_gate
[Kernel] PRE_COMMIT armed — guidance.g1, warrant.cee_c1
[Council] L5 six specialists loaded
[Prompts] full: 22,054 chars · compact: 12,672 chars
INFO:     Uvicorn running on http://127.0.0.1:8766
```

Confirm it is healthy:

```bash
curl http://127.0.0.1:8766/api/system/health
# {"ok":true,"status":"YELLOW","summary":"13 green · 1 degraded", ...}
```

`YELLOW` is expected before a model runtime is running — the `ollama` check reports *degraded* and
names the remedy. Start Ollama and the same call returns `GREEN — all 14 checks pass`. Only `RED`
means the House itself is faulty, and only `RED` makes `ok` false.

| Surface | Where |
|---|---|
| **The chamber** (talk to the council) | `THE CONTINENTAL DIVISION.html` |
| **Council Intelligence** (House Mind · reputation · governance · outcomes) | `http://127.0.0.1:8766/api/council/dashboard` |
| **Health report** | `http://127.0.0.1:8766/api/system/health` |
| **Bridge console** | `http://127.0.0.1:8766/bridge` |

---

## Choosing a model

SkynetClaw is **model-independent**. The reasoning layer does not care which engine answers.

| Setup | How | Notes |
|---|---|---|
| **Ollama** (default) | `ollama pull llama3.1:8b`, set `model` in `settings.json` | fully local, no key, no data leaves the machine |
| **llama.cpp / any OpenAI-compatible server** | point `.env` at its base URL | works with `llama-server`, LM Studio, vLLM |
| **Cloud** — OpenAI · Anthropic · Gemini · Groq · OpenRouter · DeepSeek · xAI · Mistral · Together | put the key in `.env` | a universal adapter is built in |

Two models are configured separately in `backend/settings.json`, and this matters:

```jsonc
"model":       "llama3.1:8b",       // reasoning — the council deliberates with this
"exec_model":  "qwen2.5-coder:7b",  // execution — tool calls and file edits
```

The model that *reasons* does not have to be the model that *executes*. A small fast model on the
execution path keeps tool loops cheap without dulling the deliberation.

Full provider matrix — Ollama, llama.cpp, and ten cloud APIs: **[docs/MODELS.md](docs/MODELS.md)**.

---

## What it does

- **Council of 14** — Elite Commander, Atlas, Analyst, Strategist, Skeptic, Auditor, Governor,
  Architect, Scout, Storyteller, Concierge, Forecaster, Sentinel, Executor — deliberating in
  parallel, then converging.
- **Institutional Memory** — every deliberation is persisted, archived (SQLite + Obsidian), and
  recallable.
- **Recall Quality** — recalled memories carry *similarity · accuracy · calibration · outcome ·
  validity*; the House recalls **justified** information, never raw history, and never cites its
  own disproven conclusions as authority.
- **Deliberation Briefing** — before the council reasons, it reads a synthesized brief of its own
  graded history: validated lessons, repeated errors, blind spots.
- **Governance Engine** — the constitution is enforced, not advisory: forecasts without an
  invalidation condition, claims without evidence, and omitted minority opinions are **rejected**.
  Dissent is tracked; the House learns when a minority was right.
- **Reputation** — a calibrated, recency-weighted Bayesian skill estimate per member (bounded,
  overconfidence-penalised).
- **The House Mind** — a shared cognitive state that can answer, at any moment: *what do we know ·
  what don't we know · what do we believe · why · what changed our mind.*
- **"Prove it"** — a receipt for any belief: who asserted it, on what evidence, who dissented and
  whether that was ever resolved, what would falsify it, and the calibrated track record of the
  asserters. The field that matters is `trust_basis`: **UNEARNED** when a belief carries a
  confidence figure but nobody who asserted it has ever been graded against reality. Most beliefs
  start there, and saying so is the point.
- **Tool Provider Layer** — external tool sources reach the House as *providers*, the way runtimes
  reach it through drivers. **MCP servers** are provider #1: tools arrive namespaced
  `mcp__<server>__<tool>` so an external server can never shadow a native tool and inherit its
  trust, output is quarantined as untrusted, and the gate escalates anything the server has not
  itself declared read-only.

```bash
curl "http://127.0.0.1:8766/api/house/prove?claim=your+claim+here"
curl  http://127.0.0.1:8766/api/house/self-audit     # the loop's vital signs, stated against itself
curl  http://127.0.0.1:8766/api/house/judgments      # what is open, and who it is waiting on
```

See [`docs/`](docs/) for the architecture of each layer.

---

## Architecture

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
House Mind Update + Memory + Predictions (graded at 7/30/90/180 days)
   ↓
Verdict
```

The institutional subsystem is a set of focused modules over one SQLite database, with a
versioned, reversible migration history (currently schema **v5**):

| Module | Role |
|---|---|
| `institutional_db.py` | schema owner · migrations · one connection layer |
| `council_memory.py` | persists sessions · outcome-weighted recall |
| `recall_quality.py` | the 5 recall scores + 5 validity states |
| `deliberation_briefing.py` | synthesizes history into a council brief |
| `house_state.py` | **the House Mind** — shared cognitive state + belief evolution |
| `governance_engine.py` | enforces the constitution · minority tracking |
| `agent_reputation.py` | Bayesian, calibrated, recency-weighted reputation |
| `outcome_tracker.py` | 7/30/90/180-day prediction reviews |
| `scheduler.py` | durable Outcome Clock |
| `council_intelligence_api.py` | `/api/council/*` + the Council Intelligence UI |

---

## Configuration

Everything machine-specific lives in two **git-ignored** files, with templates provided:

| File | Holds |
|---|---|
| `.env` | optional cloud provider keys and integration tokens — local Ollama needs none |
| `backend/settings.json` | model choices and your Obsidian vault path (vault is optional) |

Optionally, tell the council who you are: copy `backend/prompts/USER.example.md` to
`backend/prompts/USER.md` and fill it in. It is git-ignored, and the system runs fine without it.

No secrets, databases, or personal paths are ever committed — CI re-checks this on every push.

---

## ⚠️ Before you enable execution

SkynetClaw runs autonomous agents that can **read and write files, run tools, and reach the
network**. That is the point of it, and it is also the risk.

- It is **not sandboxed by default.** Point it at a workspace you are willing to lose.
- The **GPS-2 permission gate is deny-by-default**, and irreversible actions require a human gate.
  Do not disable those unless you understand the consequence — they are what makes autonomy
  survivable.
- Model output is **not verified truth.** The Reality Grading loop grades claims against evidence
  precisely because a model's account of its own success cannot be trusted.

See [NOTICE](NOTICE) for the full statement.

---

## Platform support

| Platform | Backend | Launcher scripts |
|---|---|---|
| **Linux** | ✅ verified in CI | use the commands above |
| **Windows** | ✅ verified in CI | `install.bat` · `start.bat` |
| **macOS** | ⚠️ should work (POSIX path); **not yet in CI** | use the commands above |

Linux specifics — system packages, discovery paths, systemd unit, known gaps:
**[docs/LINUX.md](docs/LINUX.md)**.

CI installs from `requirements.txt` alone on Ubuntu and Windows across Python 3.10 / 3.11 / 3.12,
runs the migration, boots the server, and requires `/api/system/health` to report `ok`. If that
badge is red, the claim that this works is not currently true.

---

## Tests

```bash
cd backend
python -m pytest -q          # 734 tests
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | virtualenv not active | activate `.venv`, re-run `pip install -r backend/requirements.txt` |
| `no such table` | database not initialised | `cd backend && python migrate.py up` |
| Port 8766 already in use | a previous instance is running | change `--port`, or stop the old process |
| Model calls hang or fail | Ollama is not running | `ollama serve`, then `ollama list` to confirm the tag |
| `settings.json not found` | step 1 skipped | `cp backend/settings.example.json backend/settings.json` |
| Health reports non-GREEN | a subsystem failed to load | read `/api/system/health` — each check names what is missing |

---

## Companion projects

SkynetClaw composes several standalone standards by the same author, all Apache-2.0:

| Repository | Answers |
|---|---|
| [First Principle Codex OS](https://github.com/ElmatadorZ/FirstPrincipleCodex-OS-Skill) | *don't make it up* |
| [Genesis Protocol](https://github.com/ElmatadorZ/GENESIS_PROTOCOL-) | *know when not to answer* |
| [Genesis Governance OS](https://github.com/ElmatadorZ/genesis-governance-os) | *who may do what* |
| [Genesis Reality Grading](https://github.com/ElmatadorZ/genesis-reality-grading) | *was it actually right?* |
| [Genesis OS Blueprint](https://github.com/ElmatadorZ/genesis-os-blueprint) | the reference architecture |

---

## License

**[Apache License 2.0](LICENSE)** — OSI-approved, with an express patent grant. Free to use,
modify, and redistribute, **including commercially, at any revenue**. Keep the licence and
[NOTICE](NOTICE), and state any changed files.

Attribution is requested but not required beyond NOTICE:
*Built on SkynetClaw by Bunyawat Dechanon (ElmatadorZ).*

<div align="center">

*Models are temporary. Protocols endure.*

</div>
