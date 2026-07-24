"""
model_manager.py — AtlasZClaw local-model discovery + ElmatadorZ installer
==========================================================================
The public build of AtlasZClaw is local-first: it runs on whatever model the
user already has, and can install its house model "ElmatadorZ" for them. This
module is the first-run brain-finder + installer, cross-platform (Windows +
Linux), stdlib + Ollama only.

  scan_local_models()   — find every usable local model, no config needed:
                          · Ollama (native /api/tags, if the daemon is up)
                          · llama.cpp / LM Studio OpenAI servers on common ports
                          · loose .gguf files in the usual model folders
  install_elmatadorz()  — pull a small capable base via Ollama and stamp it as
                          "elmatadorz" with the House system prompt + params
                          (a Modelfile — no multi-GB download bundled in the app)

Design choice (operator, 2026-07-12): ElmatadorZ is an Ollama Modelfile over a
base, not a bundled GGUF — so the installer is a few-hundred-MB pull, works the
same on Windows and Linux, and upgrades by swapping the base.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

OLLAMA = "http://127.0.0.1:11434"
# OpenAI-compatible local servers people commonly run (llama.cpp, LM Studio, …)
_OPENAI_PORTS = (8080, 1234, 8000, 5000)
ELMATADORZ_NAME = "elmatadorz"
# a small, capable, tool-calling base that pulls fast on modest hardware
DEFAULT_BASE = "qwen2.5:7b"


# ── low-level http (stdlib, never raises) ─────────────────────────────────────
def _get(url: str, timeout: float = 3.0) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


# ── model folders per OS (where loose GGUFs usually live) ─────────────────────
def _gguf_dirs() -> List[Path]:
    home = Path.home()
    dirs = [
        home / ".cache" / "lm-studio" / "models",
        home / ".cache" / "huggingface",
        home / "models", home / "gguf", home / "llama_models",
    ]
    if platform.system() == "Windows":
        dirs += [home / "llamacpp_test", home / ".ollama" / "models",
                 Path(os.environ.get("LOCALAPPDATA", str(home))) / "nomic.ai"]
    else:
        dirs += [home / ".ollama" / "models", Path("/usr/share/ollama/.ollama/models")]
    return [d for d in dirs if d.exists()]


def _scan_gguf() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for d in _gguf_dirs():
        try:
            for f in d.rglob("*.gguf"):
                if f.stat().st_size < 50_000_000:   # skip tiny/partial files
                    continue
                key = f.name.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "id": f.stem, "path": str(f), "runtime": "gguf-file",
                    "size_gb": round(f.stat().st_size / 1e9, 1),
                    "api_type": "openai",
                    "note": "load with llama.cpp: llama-server -m <path>",
                })
                if len(out) >= 40:
                    return out
        except Exception:
            continue
    return out


def _scan_ollama() -> List[Dict[str, Any]]:
    tags = _get(OLLAMA + "/api/tags")
    if not tags:
        return []
    out = []
    for t in tags.get("models", []):
        mid = t.get("name") or t.get("model") or ""
        det = t.get("details") or {}
        out.append({
            "id": mid, "runtime": "ollama", "api_type": "ollama",
            "size_gb": round((t.get("size", 0) or 0) / 1e9, 1),
            "parameters": det.get("parameter_size"),
            "quantization": det.get("quantization_level"),
            "is_elmatadorz": mid.split(":")[0].lower() == ELMATADORZ_NAME,
        })
    return out


def _scan_openai_servers() -> List[Dict[str, Any]]:
    out = []
    for port in _OPENAI_PORTS:
        base = f"http://127.0.0.1:{port}/v1"
        data = _get(base + "/models")
        if not data:
            continue
        for m in data.get("data", []):
            out.append({"id": m.get("id", ""), "runtime": f"openai-server:{port}",
                        "api_type": "openai", "url": base})
    return out


def ollama_present() -> bool:
    return shutil.which("ollama") is not None or _get(OLLAMA + "/api/tags") is not None


def scan_local_models() -> Dict[str, Any]:
    """Everything usable on this machine, grouped by source. No config needed."""
    ollama = _scan_ollama()
    servers = _scan_openai_servers()
    gguf = _scan_gguf()
    has_elmatadorz = any(m.get("is_elmatadorz") for m in ollama)
    total = len(ollama) + len(servers) + len(gguf)
    return {
        "ok": True,
        "platform": platform.system(),
        "ollama_installed": ollama_present(),
        "ollama_models": ollama,
        "openai_servers": servers,
        "gguf_files": gguf,
        "elmatadorz_installed": has_elmatadorz,
        "total": total,
        "recommendation": _recommend(ollama, servers, gguf, has_elmatadorz),
    }


def _recommend(ollama, servers, gguf, has_elm) -> str:
    if has_elm:
        return f"ElmatadorZ is installed — AtlasZClaw is ready. Select '{ELMATADORZ_NAME}'."
    if ollama_present():
        return (f"Ollama is ready but ElmatadorZ isn't installed yet. "
                f"Run install_elmatadorz() (pulls {DEFAULT_BASE}, ~a few hundred MB).")
    if servers or gguf:
        return ("A local model server / GGUF was found — you can use it now, or "
                "install Ollama to add the one-click ElmatadorZ house model.")
    return ("No local model found. Install Ollama (https://ollama.com) then run "
            "install_elmatadorz(), or point AtlasZClaw at any OpenAI-compatible server.")


# ── ElmatadorZ installer (Ollama Modelfile over a base) ───────────────────────
def _elmatadorz_modelfile(base: str, system_prompt: str) -> str:
    esc = system_prompt.replace('"""', "'''")
    return (
        f"FROM {base}\n"
        f'SYSTEM """{esc}"""\n'
        "PARAMETER temperature 0.4\n"
        "PARAMETER top_p 0.9\n"
        "PARAMETER num_ctx 16384\n"
    )


def _house_system_prompt() -> str:
    """The House identity, kept short enough to live in a Modelfile."""
    return (
        "You are ElmatadorZ, the house model of AtlasZClaw — a local-first "
        "autonomous agent. You act, you don't just describe: prefer calling a "
        "tool over talking about it. State evidence before conclusions; say "
        "UNKNOWN rather than guess; never invent a file, path, or result you "
        "did not observe. For computer problems, diagnose read-only first, then "
        "propose one repair for the operator to approve. Be concise and honest."
    )


def install_elmatadorz(base: str = DEFAULT_BASE,
                       progress=None) -> Dict[str, Any]:
    """Pull `base` via Ollama and create the `elmatadorz` model from it.
    Returns {ok, model, base, steps}. Requires the Ollama CLI."""
    def emit(msg):
        if progress:
            try: progress(msg)
            except Exception: pass
    if shutil.which("ollama") is None:
        return {"ok": False, "error": "Ollama CLI not found — install from https://ollama.com first"}
    steps: List[str] = []

    emit(f"pulling base model {base} (this can take a few minutes)…")
    p = subprocess.run(["ollama", "pull", base], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    steps.append(f"ollama pull {base} → exit {p.returncode}")
    if p.returncode != 0:
        return {"ok": False, "error": f"pull failed: {(p.stderr or p.stdout)[:300]}", "steps": steps}

    emit("stamping the ElmatadorZ system prompt onto the base…")
    mf = _elmatadorz_modelfile(base, _house_system_prompt())
    mf_path = Path.home() / ".atlaszclaw_elmatadorz.Modelfile"
    try:
        mf_path.write_text(mf, encoding="utf-8")
        c = subprocess.run(["ollama", "create", ELMATADORZ_NAME, "-f", str(mf_path)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        steps.append(f"ollama create {ELMATADORZ_NAME} → exit {c.returncode}")
        if c.returncode != 0:
            return {"ok": False, "error": f"create failed: {(c.stderr or c.stdout)[:300]}", "steps": steps}
    finally:
        try: mf_path.unlink()
        except Exception: pass

    emit(f"done — '{ELMATADORZ_NAME}' is ready.")
    return {"ok": True, "model": ELMATADORZ_NAME, "base": base, "steps": steps,
            "next": "select ElmatadorZ in AtlasZClaw, or set exec_model=elmatadorz in settings.json"}


# ── llama.cpp fallback (for users who don't want Ollama) ──────────────────────
# A curated GGUF the app can fetch and run directly with llama.cpp. Kept small
# and tool-capable; downloaded on demand, never bundled.
_FALLBACK_GGUF = {
    "name": "qwen2.5-7b-instruct-q4",
    "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf",
    "size_gb": 4.7,
    "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
}


def models_dir() -> Path:
    d = Path(__file__).parent.parent / "models"
    d.mkdir(exist_ok=True)
    return d


def llamacpp_present() -> Optional[str]:
    """Return the llama-server path if a llama.cpp binary is on PATH, else None."""
    for name in ("llama-server", "llama-server.exe", "server", "server.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


def download_fallback_gguf(progress=None) -> Dict[str, Any]:
    """Download the curated GGUF for llama.cpp users (no Ollama needed).
    Streams to disk so a multi-GB file doesn't sit in memory."""
    def emit(m):
        if progress:
            try: progress(m)
            except Exception: pass
    spec = _FALLBACK_GGUF
    dest = models_dir() / spec["filename"]
    if dest.exists() and dest.stat().st_size > 1_000_000_000:
        return {"ok": True, "path": str(dest), "note": "already downloaded", "model": spec["name"]}
    emit(f"downloading {spec['name']} (~{spec['size_gb']} GB) — one time…")
    try:
        tmp = dest.with_suffix(".part")
        with urllib.request.urlopen(spec["url"], timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length", 0))
            done = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and done % (256 << 20) < (1 << 20):
                    emit(f"  {done/1e9:.1f}/{total/1e9:.1f} GB")
        tmp.replace(dest)
    except Exception as e:
        return {"ok": False, "error": f"download failed: {str(e)[:200]}"}
    emit("download complete")
    return {"ok": True, "path": str(dest), "model": spec["name"],
            "next": ("run it:  llama-server -m \"%s\" -c 16384 --port 8080\n"
                     "then AtlasZClaw auto-detects it at http://127.0.0.1:8080/v1") % dest}


def ensure_a_model(progress=None) -> Dict[str, Any]:
    """First-run convenience: guarantee SOME usable local model exists.
    Prefers Ollama+ElmatadorZ; falls back to a llama.cpp GGUF download when
    Ollama is absent. Returns what it did."""
    scan = scan_local_models()
    if scan["total"] > 0:
        return {"ok": True, "action": "none", "reason": f"{scan['total']} model(s) already present"}
    if ollama_present():
        return install_elmatadorz(progress=progress)
    if llamacpp_present():
        return download_fallback_gguf(progress=progress)
    return {"ok": False, "action": "manual",
            "reason": "no Ollama and no llama.cpp found — install one, or add a cloud API in the UI",
            "hint": "Ollama: https://ollama.com  ·  llama.cpp: https://github.com/ggml-org/llama.cpp"}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "download-gguf":
        print(json.dumps(download_fallback_gguf(progress=lambda m: print("  ·", m)), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "ensure":
        print(json.dumps(ensure_a_model(progress=lambda m: print("  ·", m)), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "install":
        print(json.dumps(install_elmatadorz(progress=lambda m: print("  ·", m)),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(scan_local_models(), ensure_ascii=False, indent=1))
