# Installing SkynetClaw

Four ways in. Pick one.

| Route | Best for | Time |
|---|---|---|
| [Docker](#docker--fastest) | trying it out with the least setup | ~5 min |
| [Linux / macOS](#linux--macos) | day-to-day use | ~5 min |
| [Windows](#windows) | day-to-day use | ~5 min |
| [Make](#make) | anyone with `make` available | ~3 min |

**Requirements everywhere:** Python 3.10+ (or Docker), ~500 MB disk, and a model — either local via
[Ollama](https://ollama.com) or a cloud API key. **No GPU required.**

---

## Docker — fastest

```bash
git clone https://github.com/ElmatadorZ/skynetclaw.git
cd skynetclaw
cp backend/settings.example.json backend/settings.json

docker compose up -d
docker compose exec ollama ollama pull llama3.1:8b     # first run only
```

Confirm:

```bash
curl http://127.0.0.1:8766/api/system/health
```

This starts two containers: the backend on `127.0.0.1:8766` and a local Ollama on `:11434`. Models
and the institutional database live in named volumes, so they survive `docker compose down`.

Stop with `docker compose down`. Add `-v` to also delete the volumes — that erases the House's
memory, so do it deliberately.

To use a **cloud model instead of local**, create `.env` from `.env.example`, add your key, and skip
the `ollama pull` step.

---

## Linux / macOS

```bash
git clone https://github.com/ElmatadorZ/skynetclaw.git
cd skynetclaw

./start.sh
```

`start.sh` is idempotent and does the whole first-run sequence for you: creates `.venv`, installs
the five dependencies, copies both config templates if they are missing, runs the database
migration, warns if Ollama is not reachable, and starts the server.

Run it again any time — it skips whatever is already done.

<details>
<summary>Manual steps, if you prefer to see each one</summary>

```bash
cp .env.example .env
cp backend/settings.example.json backend/settings.json

python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

ollama pull llama3.1:8b        # skip if using a cloud API

cd backend
python migrate.py up
python -m uvicorn main:app --host 127.0.0.1 --port 8766
```
</details>

A different port: `./start.sh 9000`

---

## Windows

```powershell
git clone https://github.com/ElmatadorZ/skynetclaw.git
cd skynetclaw

copy .env.example .env
copy backend\settings.example.json backend\settings.json

python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt

ollama pull llama3.1:8b

cd backend
python migrate.py up
python -m uvicorn main:app --host 127.0.0.1 --port 8766
```

`install.bat` and `start.bat` wrap the same steps.

---

## Make

```bash
git clone https://github.com/ElmatadorZ/skynetclaw.git
cd skynetclaw

make setup     # venv + dependencies + config + database
make run       # start
make health    # probe a running instance
make test      # 734 tests
```

---

## After it starts

```
[Governance] GPS-2 gate armed — deny-by-default · human gate on irreversible tools
[Council] L5 six specialists loaded
INFO:     Uvicorn running on http://127.0.0.1:8766
```

| Surface | Where |
|---|---|
| **The chamber** — talk to the council | open `THE CONTINENTAL DIVISION.html` |
| **Council Intelligence** — House Mind, reputation, governance, outcomes | `http://127.0.0.1:8766/api/council/dashboard` |
| **Health** | `http://127.0.0.1:8766/api/system/health` |
| **Bridge console** | `http://127.0.0.1:8766/bridge` |

Health on a machine that has not started a model runtime yet reports:

```json
{"ok": true, "status": "YELLOW", "summary": "13 green · 1 degraded"}
```

That is the correct answer, not a problem: the `ollama` check is *degraded* and says so, along
with what to do about it. Once a runtime is up the same call returns
`{"ok": true, "status": "GREEN", "summary": "all 14 checks pass"}`.

| Verdict | Meaning | `ok` |
|---|---|---|
| `GREEN` | every subsystem reachable | `true` |
| `YELLOW` | running; something optional is absent or not yet generated | `true` |
| `RED` | the House itself is faulty — a file, module, or database is broken | `false` |

Every check names itself in `checks[]`, so read the response before changing anything.

---

## Configuration

| File | Holds | Committed? |
|---|---|---|
| `.env` | cloud provider keys, integration tokens | **no** — git-ignored |
| `backend/settings.json` | model choices, Obsidian vault path | **no** — git-ignored |
| `backend/prompts/USER.md` | optional: who you are, for the council | **no** — git-ignored |

Templates for all three ship in the repository (`*.example.*`). CI re-checks on every push that no
personal file has crept in.

Choosing and mixing models: **[MODELS.md](MODELS.md)**.

Linux specifics — packages, discovery paths, systemd: **[LINUX.md](LINUX.md)**.

---

## Before enabling execution

SkynetClaw runs agents that can read and write files, run tools, and reach the network.

- Not sandboxed by default — point it at a workspace you are willing to lose.
- The GPS-2 gate is deny-by-default and irreversible actions need a human gate. Leave those on.
- Model output is not verified truth.

See [NOTICE](../NOTICE).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | virtualenv not active | activate `.venv`, reinstall requirements |
| `no such table` | migration not run | `cd backend && python migrate.py up` |
| `settings.json not found` | config step skipped | copy the template |
| Port 8766 in use | previous instance running | change `--port`, or stop it |
| Model calls hang | Ollama not running | `ollama serve`, then `ollama list` |
| JSON / tool-call failures | model too small | see the note in [MODELS.md](MODELS.md) |
| Health `YELLOW` | normal — an optional subsystem is absent | read the check's message; it names the remedy |
| Health `RED` | a subsystem failed to load | read `/api/system/health` — it names the check |
| Docker: backend cannot reach Ollama | wrong base URL inside the container | set `OLLAMA_BASE_URL`; inside Docker it is `http://ollama:11434`, not `localhost` |
