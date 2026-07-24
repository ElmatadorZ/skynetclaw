"""
health_check.py — comprehensive /api/system/health endpoint
==============================================================
Reports status of EVERY subsystem with red/yellow/green + reason.
Operator can see at a glance what's healthy, what's degraded, what's down.

Output shape:
  { ok: bool, status: 'GREEN'|'YELLOW'|'RED',
    summary: '...',
    checks: [ {name, status, msg, latency_ms}, ... ] }
"""
from __future__ import annotations
import time, sqlite3, json, os
from pathlib import Path
from typing import Any, Dict, List

_BASE = Path(__file__).parent
_ROOT = _BASE.parent


def _check_file(name: str, path: Path, min_bytes: int = 0,
                generated: bool = False) -> Dict[str, Any]:
    """generated=True marks a file the House writes for itself at boot; its
    absence on a fresh checkout is a state to report, not a fault to fail on."""
    t0 = time.time()
    if not path.exists():
        return {"name": name, "status": "YELLOW" if generated else "RED",
                "msg": (f"not yet generated: {path.name}" if generated
                        else f"not found: {path.name}"),
                "latency_ms": int((time.time()-t0)*1000)}
    sz = path.stat().st_size
    if sz < min_bytes:
        return {"name": name, "status": "YELLOW", "msg": f"only {sz}b (expected ≥{min_bytes})",
                "latency_ms": int((time.time()-t0)*1000)}
    return {"name": name, "status": "GREEN", "msg": f"{sz:,}b",
            "latency_ms": int((time.time()-t0)*1000)}


def _check_module(name: str, modname: str) -> Dict[str, Any]:
    t0 = time.time()
    try:
        import importlib
        m = importlib.import_module(modname)
        return {"name": name, "status": "GREEN", "msg": f"imported ({getattr(m,'__file__','?').split('/')[-1]})",
                "latency_ms": int((time.time()-t0)*1000)}
    except Exception as e:
        return {"name": name, "status": "RED", "msg": f"import failed: {type(e).__name__}: {e}",
                "latency_ms": int((time.time()-t0)*1000)}


def _check_db(name: str, db: Path, expected_tables: List[str]) -> Dict[str, Any]:
    t0 = time.time()
    if not db.exists():
        return {"name": name, "status": "YELLOW", "msg": f"db not yet created: {db.name}",
                "latency_ms": int((time.time()-t0)*1000)}
    try:
        with sqlite3.connect(db) as c:
            existing = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        missing = [t for t in expected_tables if t not in existing]
        if missing:
            return {"name": name, "status": "YELLOW",
                    "msg": f"db OK · missing tables: {','.join(missing)}",
                    "latency_ms": int((time.time()-t0)*1000)}
        return {"name": name, "status": "GREEN",
                "msg": f"{len(existing)} tables present",
                "latency_ms": int((time.time()-t0)*1000)}
    except Exception as e:
        return {"name": name, "status": "RED", "msg": f"db error: {e}",
                "latency_ms": int((time.time()-t0)*1000)}


async def _check_ollama(base_url: str = "") -> Dict[str, Any]:
    # Inside a container the runtime is a sibling service, not localhost, so the
    # deployment says where it is (docker-compose sets OLLAMA_BASE_URL).
    base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    t0 = time.time()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as cx:
            r = await cx.get(f"{base_url}/api/tags")
            if r.status_code == 200:
                models = len(r.json().get("models", []))
                return {"name": "ollama", "status": "GREEN",
                        "msg": f"{models} models available at {base_url}",
                        "latency_ms": int((time.time()-t0)*1000)}
            return {"name": "ollama", "status": "YELLOW",
                    "msg": f"HTTP {r.status_code} from {base_url}",
                    "latency_ms": int((time.time()-t0)*1000)}
    except Exception as e:
        # DEGRADED, not broken. RED is reserved for "the House itself is faulty";
        # an absent local model runtime is an environment the House supports —
        # the operator may be running against an API provider instead, or may not
        # have started Ollama yet. Reporting it as RED made ok=false on every
        # clean machine, which is what a fresh CI runner and a first-time user
        # both look like.
        return {"name": "ollama", "status": "YELLOW",
                "msg": f"no local model runtime at {base_url} ({type(e).__name__}) — "
                       f"start Ollama or configure an API connection",
                "latency_ms": int((time.time()-t0)*1000)}


def _check_chain() -> Dict[str, Any]:
    t0 = time.time()
    try:
        from bridge_protocol import verify_chain
        r = verify_chain()
        if r.get("ok"):
            return {"name": "audit_chain", "status": "GREEN",
                    "msg": f"{r['total']} envelopes verified",
                    "latency_ms": int((time.time()-t0)*1000)}
        return {"name": "audit_chain", "status": "RED",
                "msg": f"chain BROKEN at {r.get('first_bad')}",
                "latency_ms": int((time.time()-t0)*1000)}
    except Exception as e:
        return {"name": "audit_chain", "status": "YELLOW",
                "msg": f"check unavailable: {e}",
                "latency_ms": int((time.time()-t0)*1000)}


async def run_all() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    # L0 — filesystem (try every known naming variant)
    _cont = None
    for fname in ("THE CONTINENTAL DIVISION.html", "THE_CONTINENTAL_DIVISION.html",
                  "agent_room.html", "the_continental_division.html"):
        if (_ROOT / fname).exists():
            _cont = _ROOT / fname; break
    if _cont:
        checks.append(_check_file(f"continental UI ({_cont.name})", _cont, 50000))
    else:
        checks.append({"name":"continental UI","status":"RED",
                       "msg":"neither THE_CONTINENTAL_DIVISION.html nor agent_room.html found",
                       "latency_ms":0})
    checks.append(_check_file("bridge_console.html", _ROOT / "bridge_console.html", 10000))
    # SELF.md is written by ecosystem_manifest at boot and is git-ignored, so a
    # clean clone legitimately has none until the backend has run once.
    checks.append(_check_file("SELF.md", _BASE / "SELF.md", 500, generated=True))

    # L1 — backend modules
    for mod in ["ecosystem_manifest", "continental_relay", "bridge_protocol",
                "feedback_engine", "obsidian_tools", "skills_auto_router",
                "skills_loader"]:
        checks.append(_check_module(mod, mod))

    # L5 — databases
    checks.append(_check_db("skynerclaw.db", _BASE / "skynerclaw.db",
                            ["skills", "agent_runs", "custom_tools"]))
    checks.append(_check_db("chat_history.db", _BASE / "chat_history.db",
                            ["chat_messages", "continental_conversations"]))

    # External — Ollama
    checks.append(await _check_ollama())

    # Audit chain integrity
    checks.append(_check_chain())

    # Aggregate
    statuses = [c["status"] for c in checks]
    red = statuses.count("RED")
    yellow = statuses.count("YELLOW")
    green = statuses.count("GREEN")

    if red == 0 and yellow == 0:
        overall = "GREEN"
        summary = f"all {green} checks pass"
    elif red == 0:
        overall = "YELLOW"
        summary = f"{green} green · {yellow} degraded"
    else:
        overall = "RED"
        summary = f"{red} CRITICAL · {yellow} degraded · {green} ok"

    return {
        "ok":      red == 0,
        "status":  overall,
        "summary": summary,
        "checks":  checks,
        "totals":  {"green": green, "yellow": yellow, "red": red},
        "ts":      time.time(),
    }


def mount(app):
    @app.get("/api/system/health")
    async def _health():
        return await run_all()

    @app.get("/api/system/health/quick")
    def _quick():
        # cheap version — no module imports, no ollama call
        return {"ok": True, "ts": time.time(),
                "msg": "backend alive — call /api/system/health for full report"}

    print("[Health] mounted at /api/system/health (+ /quick)")


if __name__ == "__main__":
    import asyncio, sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    r = asyncio.run(run_all())
    print(f"\n=== SYSTEM HEALTH — {r['status']} ===")
    print(f"{r['summary']}\n")
    for c in r["checks"]:
        sym = {"GREEN":"✓","YELLOW":"⚠","RED":"✗"}[c["status"]]
        print(f"  {sym} {c['name']:<32} {c['msg']:<50} ({c['latency_ms']}ms)")
