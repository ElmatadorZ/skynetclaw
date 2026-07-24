"""
execution_watchdog.py — keep the execution runtime (llama.cpp :8080) alive
==========================================================================
The GPU model server (llama-server.exe on :8080, alias ElmatadorZ) has died
repeatedly during use. When it is down, missions fail; and immediately after a
restart the FIRST inference can glitch (the server is launched --no-warmup).

This watchdog closes both:
  * self-healing  — polls the runtime; if it is down, it (re)launches it with the
    exact flags from launch_execution_runtime.ps1 (the exe is invoked directly,
    no PowerShell policy bypass);
  * warm-up       — after the server answers /v1/models it sends one tiny
    inference so the first real request is not cold.

Run it alongside the app (start.bat launches it automatically):
    python execution_watchdog.py

Config via env (defaults match the launch script):
    LLAMACPP_ROOT, EXEC_MODEL, EXEC_PORT, EXEC_CTX, EXEC_ALIAS, WATCH_INTERVAL

Stdlib only. Safe to run multiple times — it never launches a second server
while one is already answering.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# The supervisor must never die because of its own log line: under a cp1252
# console (or DEVNULL when spawned by the backend) non-ASCII crashed log() at
# the exact moment it tried to launch the runtime — silently killing recovery.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT     = os.environ.get("LLAMACPP_ROOT",
                          str(Path.home() / "llamacpp_test"))
EXE      = os.path.join(ROOT, "llama-server.exe")
MODEL    = os.environ.get("EXEC_MODEL", os.path.join(ROOT, "qwen25-14b.gguf"))
if not os.path.exists(MODEL):
    MODEL = os.path.join(ROOT, "qwen25-7b.gguf")
PORT     = os.environ.get("EXEC_PORT", "8080")
CTX      = os.environ.get("EXEC_CTX", "16384")
ALIAS    = os.environ.get("EXEC_ALIAS", "ElmatadorZ")
INTERVAL = float(os.environ.get("WATCH_INTERVAL", "10"))
BASE     = f"http://127.0.0.1:{PORT}"


def log(msg: str) -> None:
    sys.stdout.write(f"[watchdog {time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stdout.flush()


def is_up(timeout: float = 4.0) -> bool:
    """Responsive means it answers the cheap /v1/models (not just a bound port)."""
    try:
        with urllib.request.urlopen(BASE + "/v1/models", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def warmup() -> bool:
    body = json.dumps({"model": ALIAS,
                       "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 1, "temperature": 0}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
        return True
    except Exception as e:
        log(f"warm-up call failed (non-fatal): {type(e).__name__}")
        return False


def launch() -> None:
    if not os.path.exists(EXE):
        log(f"MISSING exe: {EXE} — cannot launch"); return
    if not os.path.exists(MODEL):
        log(f"MISSING model: {MODEL} — cannot launch"); return
    # --parallel 1: SkynetClaw serves ONE request at a time, but llama-server
    # defaults to 4 slots, each reserving a full n_ctx KV cache → ~4× KV VRAM,
    # pushing the 14B+16k to 95% of the 12GB card (measured 11.6GB) and causing
    # intermittent OOM crashes (the ':8080 dies repeatedly' root cause). One slot
    # keeps the full 16k context per request and frees ~2.4GB → durable headroom.
    cmd = [EXE, "-m", MODEL, "-ngl", "99", "--jinja", "--flash-attn", "on",
           "--host", "127.0.0.1", "--port", str(PORT), "-c", str(CTX),
           "--parallel", "1", "--alias", ALIAS, "--no-warmup"]
    log(f"runtime DOWN → launching {os.path.basename(EXE)} :{PORT} (ctx {CTX})")
    try:
        # detach: new process group so the watchdog can exit without killing it
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags)
    except Exception as e:
        log(f"launch failed: {e}"); return
    # wait for readiness, then warm
    for _ in range(60):
        if is_up():
            log("runtime is UP — warming first inference")
            warmup()
            log("warm-up done — ready")
            return
        time.sleep(1)
    log("runtime did not become ready within 60s (will retry next cycle)")


_LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".watchdog.lock")


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _acquire_singleton() -> bool:
    """True if we hold the lock; False if a live watchdog already runs. Prevents two
    watchdogs from both relaunching :8080 (which would fight over the port)."""
    try:
        if os.path.exists(_LOCK):
            try:
                pid = int((open(_LOCK).read().strip() or "0"))
            except Exception:
                pid = 0
            if _pid_alive(pid):
                return False
        with open(_LOCK, "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return True  # fail-open: a lock error must not disable supervision


def _release_singleton() -> None:
    try:
        if os.path.exists(_LOCK) and open(_LOCK).read().strip() == str(os.getpid()):
            os.remove(_LOCK)
    except Exception:
        pass


def main() -> int:
    if not _acquire_singleton():
        log("another watchdog is already running — exiting (singleton)")
        return 0
    log(f"watching {BASE} · model={os.path.basename(MODEL)} · every {INTERVAL:.0f}s")
    was_up = None
    misses = 0
    while True:
        up = is_up()
        if up != was_up:
            log("runtime UP" if up else "runtime DOWN")
            was_up = up
        if not up:
            misses += 1
            if misses >= 2:          # two misses in a row → really down, relaunch
                launch()
                misses = 0
                was_up = is_up()
        else:
            misses = 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("stopped"); sys.exit(0)
    finally:
        _release_singleton()
