# Running SkynetClaw on Linux

SkynetClaw is developed on Windows but the backend is platform-neutral, and CI
proves that on Ubuntu on every push. This page covers what a Linux install
actually needs.

---

## Quick path

```bash
git clone https://github.com/ElmatadorZ/skynetclaw.git
cd skynetclaw
./start.sh
```

`start.sh` creates the virtualenv, installs the five dependencies, seeds both
config templates, runs the database migration, warns if Ollama is unreachable,
and starts the server. It is idempotent — run it again any time.

Or with `make`:

```bash
make setup && make run
```

Or skip Python entirely:

```bash
docker compose up -d
docker compose exec ollama ollama pull llama3.1:8b
```

---

## System packages

Only Python is strictly required. Everything else is optional and degrades
gracefully — a missing component disables one capability, it does not stop the
system.

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl

# optional — OCR for scanned PDFs and images
sudo apt install -y tesseract-ocr tesseract-ocr-tha
```

### Fedora / RHEL

```bash
sudo dnf install -y python3 python3-pip curl
sudo dnf install -y tesseract tesseract-langpack-tha      # optional
```

### Arch

```bash
sudo pacman -S python python-pip curl
sudo pacman -S tesseract tesseract-data-tha               # optional
```

OCR is discovered from `PATH` first, so a package-manager install needs no
configuration. Without it, `doc_reader` simply reports that OCR is unavailable.

---

## A local model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                    # or: systemctl --user start ollama
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b      # the execution path
```

**No GPU required.** A 7–8B model runs on CPU; it is slower, not broken. With an
NVIDIA GPU and the container toolkit installed, Ollama uses it automatically.

Full provider matrix, including cloud APIs: **[MODELS.md](MODELS.md)**.

---

## What Linux discovers automatically

These were Windows-shaped and are now probed per platform:

| Capability | Linux locations searched |
|---|---|
| **Obsidian vault** | `~/Documents/Obsidian Vault`, `~/Obsidian`, `~/Notes`, `~/vault`, `~/Nextcloud/Obsidian`, `~/Dropbox/Obsidian`, `~/Sync/Obsidian`, `/vault`, `/data/obsidian` |
| **Obsidian vault registry** | `$XDG_CONFIG_HOME/obsidian/obsidian.json`, `~/.config/obsidian/obsidian.json`, and the Flatpak path under `~/.var/app/md.obsidian.Obsidian/` |
| **Tesseract binary** | `PATH`, then `/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, `/snap/bin` |
| **tessdata** | `$TESSDATA_PREFIX`, `/usr/share/tesseract-ocr/5/tessdata`, `/usr/share/tessdata`, `/usr/local/share/tessdata` |
| **Agent workspace** | `~/Desktop/workspace` when a Desktop exists, otherwise `~/skynetclaw-workspace` — headless servers and non-English XDG names are handled |

Set an explicit vault path in `backend/settings.json` to skip discovery entirely.

---

## Shell execution on Linux

The agent's `shell_command` tool runs through the platform's own shell. The
system already branches on `os.name`, so PowerShell-specific handling applies
only on Windows; on Linux commands go to `/bin/sh` unchanged.

This is the highest-risk capability in the system. The GPS-2 gate is
deny-by-default and irreversible actions require a human gate — leave those on.
See [NOTICE](../NOTICE).

---

## Running as a service

`systemd --user` unit, adjusting `WorkingDirectory`:

```ini
# ~/.config/systemd/user/skynetclaw.service
[Unit]
Description=SkynetClaw
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/skynetclaw
ExecStart=%h/skynetclaw/start.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now skynetclaw
systemctl --user status skynetclaw
journalctl --user -u skynetclaw -f
```

For a system-wide unit, run it as a dedicated unprivileged user whose home is the
only workspace the agent can reach.

---

## Ports

| Port | Service | Bound to |
|---|---|---|
| 8766 | SkynetClaw backend | `127.0.0.1` by default |
| 11434 | Ollama | localhost |
| 8080 | execution runtime (optional) | localhost |

The backend binds to loopback deliberately. **Do not expose 8766 to a network**
without putting authentication in front of it — the API can run tools and write
files, and it has no built-in authentication.

---

## Known Linux gaps

Stated rather than discovered later:

- **`.bat` / `.ps1` launchers do not apply.** Use `start.sh`, `make`, or Docker.
- **macOS is not in CI.** It should work — the Linux code path is POSIX — but it
  is untested, so it is marked as such in the README rather than claimed.
- **Tesseract language data** for non-English OCR must be installed separately
  (`tesseract-ocr-tha` and friends).
- **File-path handling in agent prompts** is written with Windows examples in
  places. It functions on Linux, but a model may occasionally produce
  Windows-style guidance in its explanations.

If you hit something else, please open an issue with the distribution, the
Python version, and the failing output.
