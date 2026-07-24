"""
reliability_dashboard.py — OX-HOUSE-STABILIZATION-1 Phase 1
===========================================================
A LIVE production-reliability dashboard. No cognition, no learning — pure
operational telemetry so the operator can see whether the House can actually
execute. Every number is measured at request time (no cached estimates):

  • GPU / VRAM / utilization      → nvidia-smi (live)
  • CPU / RAM                     → wmic (live, Windows) w/ psutil fallback
  • Active model + offload (CPU?) → Ollama /api/ps (live: size vs size_vram)
  • Success rate / timeout rate   → agent_runs table (measured outcomes)
  • Avg run duration / tool usage → agent_runs table
  • Prompt tokens                 → measured from the live prompt strings

Dependency-free (stdlib only). Exposes mount(app) → /api/house/reliability
(JSON) and /reliability (auto-refreshing HTML).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from typing import Any, Dict, List, Optional

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skynerclaw.db")
_OLLAMA = "http://127.0.0.1:11434"


# ── low-level helpers ─────────────────────────────────────────────────────────
def _run(cmd: List[str], timeout: float = 5.0) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception:
        return ""


def _http_json(url: str, timeout: float = 4.0) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


# ── GPU (live, nvidia-smi) ────────────────────────────────────────────────────
def gpu_metrics() -> Dict[str, Any]:
    out = _run(["nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,driver_version",
                "--format=csv,noheader,nounits"])
    if not out:
        return {"present": False}
    p = [x.strip() for x in out.split(",")]
    try:
        return {"present": True, "name": p[0], "util_pct": float(p[1]),
                "vram_used_mb": float(p[2]), "vram_total_mb": float(p[3]), "driver": p[4]}
    except Exception:
        return {"present": True, "raw": out}


# ── system CPU/RAM (live) ─────────────────────────────────────────────────────
def system_metrics() -> Dict[str, Any]:
    try:
        import psutil  # optional
        return {"cpu_pct": psutil.cpu_percent(interval=0.3),
                "ram_used_mb": round(psutil.virtual_memory().used / 1e6),
                "ram_total_mb": round(psutil.virtual_memory().total / 1e6),
                "source": "psutil"}
    except Exception:
        pass
    cpu = _run(["wmic", "cpu", "get", "loadpercentage", "/value"])
    mem = _run(["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"])
    d: Dict[str, Any] = {"source": "wmic"}
    for line in (cpu + "\n" + mem).splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    try:
        total_kb = float(d.get("TotalVisibleMemorySize", 0)); free_kb = float(d.get("FreePhysicalMemory", 0))
        return {"cpu_pct": float(d.get("LoadPercentage", "nan")),
                "ram_used_mb": round((total_kb - free_kb) / 1024),
                "ram_total_mb": round(total_kb / 1024), "source": "wmic"}
    except Exception:
        return {"source": "unavailable"}


# ── Ollama residency / offload (live) ─────────────────────────────────────────
def ollama_metrics() -> Dict[str, Any]:
    ps = _http_json(_OLLAMA + "/api/ps")
    if ps is None:
        return {"reachable": False}
    models = []
    for m in ps.get("models", []):
        size = m.get("size", 0) or 0
        vram = m.get("size_vram", 0) or 0
        loc = "GPU" if vram >= size * 0.95 and size else ("CPU" if vram == 0 else "HYBRID")
        models.append({"name": m.get("name"), "size_gb": round(size / 1e9, 1),
                       "vram_gb": round(vram / 1e9, 1), "offload": loc,
                       "gpu_pct": round(100 * vram / size) if size else 0})
    return {"reachable": True, "loaded": models}


# ── agent outcomes (measured from agent_runs) ─────────────────────────────────
def agent_stats(db_path: str = _DB, window: int = 20) -> Dict[str, Any]:
    try:
        c = sqlite3.connect(db_path); c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT started_at,ended_at,model,status,n_tools,summary "
            "FROM agent_runs ORDER BY rowid DESC LIMIT ?", (window,))]
        c.close()
    except Exception as e:
        return {"available": False, "error": str(e)[:80]}
    if not rows:
        return {"available": True, "n": 0}
    import statistics
    _SUCCESS = ("task_complete", "complete", "completed", "success", "done")
    n = len(rows)
    ok = sum(1 for r in rows if (r.get("status") or "").lower() in _SUCCESS)
    timeouts = sum(1 for r in rows if "timeout" in (r.get("summary") or "").lower())
    durs = []
    for r in rows:
        try:
            d = float(r["ended_at"]) - float(r["started_at"])
            if 0 <= d < 86400:  # drop stale/malformed rows (>24h) so the median is real
                durs.append(d)
        except Exception:
            pass
    tools = [int(r.get("n_tools") or 0) for r in rows]
    return {"available": True, "n": n, "window": window,
            "success_rate": round(ok / n, 3), "timeout_rate": round(timeouts / n, 3),
            "median_duration_s": round(statistics.median(durs), 1) if durs else None,
            "runs_with_tools": sum(1 for t in tools if t > 0),
            "last_model": rows[0].get("model"), "last_status": rows[0].get("status")}


# ── prompt token size (measured from live prompt strings) ─────────────────────
def prompt_tokens() -> Dict[str, Any]:
    try:
        import main as _m  # the live prompt strings
        full = len(getattr(_m, "GENESIS_AGENT_PROMPT", "")) // 4
        compact = len(getattr(_m, "_MODULAR_PROMPT_COMPACT", "")) // 4
        return {"full_prompt_tok": full, "compact_prompt_tok": compact,
                "note": "chars/4; tool schemas added per-task selection"}
    except Exception:
        return {"available": False}


# ── assemble ──────────────────────────────────────────────────────────────────
def collect(db_path: str = _DB) -> Dict[str, Any]:
    gpu = gpu_metrics()
    oll = ollama_metrics()
    # offload truth: is any loaded model actually on the GPU?
    on_gpu = any(m.get("offload") == "GPU" for m in oll.get("loaded", [])) if oll.get("reachable") else False
    gpu_engaged = bool(gpu.get("present") and gpu.get("util_pct", 0) > 5 and on_gpu)
    return {
        "ts": time.time(),
        "gpu": gpu,
        "system": system_metrics(),
        "ollama": oll,
        "inference_on_gpu": gpu_engaged,
        "agent": agent_stats(db_path),
        "prompt": prompt_tokens(),
    }


# ── HTML ──────────────────────────────────────────────────────────────────────
def render_html(snap: Dict[str, Any]) -> str:
    g = snap.get("gpu", {}); s = snap.get("system", {}); a = snap.get("agent", {})
    oll = snap.get("ollama", {}); pr = snap.get("prompt", {})
    def card(label, value, ok=None):
        color = "#888" if ok is None else ("#3fb950" if ok else "#f85149")
        return (f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
                f'padding:14px 16px;min-width:150px"><div style="color:#8b949e;font-size:12px;'
                f'text-transform:uppercase;letter-spacing:.05em">{label}</div>'
                f'<div style="color:{color};font-size:22px;font-weight:600;margin-top:4px">{value}</div></div>')
    gpu_v = f"{g.get('util_pct','?')}% · {g.get('vram_used_mb','?')}/{g.get('vram_total_mb','?')}MB" if g.get("present") else "no GPU"
    loaded = ", ".join(f"{m['name']} [{m['offload']}]" for m in oll.get("loaded", [])) or "none"
    cards = "".join([
        card("Inference on GPU", "YES" if snap.get("inference_on_gpu") else "NO (CPU)", snap.get("inference_on_gpu")),
        card("GPU util / VRAM", gpu_v, snap.get("inference_on_gpu")),
        card("CPU", f"{s.get('cpu_pct','?')}%"),
        card("RAM", f"{s.get('ram_used_mb','?')}/{s.get('ram_total_mb','?')}MB"),
        card("Success rate", f"{a.get('success_rate',0)*100:.0f}%" if a.get("n") else "n/a",
             (a.get("success_rate") or 0) >= 0.9 if a.get("n") else None),
        card("Timeout rate", f"{a.get('timeout_rate',0)*100:.0f}%" if a.get("n") else "n/a",
             (a.get("timeout_rate") or 0) == 0 if a.get("n") else None),
        card("Median run", f"{a.get('median_duration_s','?')}s" if a.get("n") else "n/a"),
        card("Loaded model", loaded),
        card("Prompt tokens", f"full {pr.get('full_prompt_tok','?')} / compact {pr.get('compact_prompt_tok','?')}"),
    ])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>House Reliability</title>
<meta http-equiv="refresh" content="5"></head>
<body style="background:#0d1117;color:#c9d1d9;font-family:system-ui,Segoe UI,sans-serif;margin:0;padding:24px">
<h1 style="font-size:20px;margin:0 0 4px">THE HOUSE · Reliability Dashboard</h1>
<div style="color:#8b949e;font-size:12px;margin-bottom:18px">live · auto-refresh 5s · {time.strftime('%Y-%m-%d %H:%M:%S')}</div>
<div style="display:flex;flex-wrap:wrap;gap:12px">{cards}</div>
<pre style="margin-top:22px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;
font-size:12px;color:#8b949e;overflow:auto">{json.dumps(snap, indent=2)}</pre>
</body></html>"""


# ── FastAPI integration ───────────────────────────────────────────────────────
def mount(app) -> None:
    from fastapi.responses import HTMLResponse

    @app.get("/api/house/reliability")
    async def _house_reliability():  # noqa
        try:
            return {"ok": True, "snapshot": collect()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/reliability")
    async def _reliability_page():  # noqa
        try:
            return HTMLResponse(render_html(collect()))
        except Exception as e:
            return HTMLResponse(f"<pre>reliability error: {e}</pre>", status_code=500)


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
