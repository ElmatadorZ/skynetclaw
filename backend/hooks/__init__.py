"""
backend/hooks/  —  boot hook discovery (port of OpenClaw hooks.internal pattern)
================================================================================
At FastAPI lifespan startup, main.py calls `run_boot_hooks(app)` which scans
this directory for any `*.py` file (other than this one) defining a function:

    def run(app, ctx: dict) -> None:
        ...

Each hook is invoked with the FastAPI app + a small context dict
(workspace path, db path, etc.). Hooks let users add custom startup logic
(register routes, seed data, validate config, send a heartbeat, etc.) without
editing main.py.

Conventions:
  - File name = hook name (e.g. boot.py → "boot")
  - Hooks run in alphabetical order of filename — name with NN_ prefix to order
  - A hook that raises is logged but does NOT crash startup
  - Hooks are best-effort. Lifespan continues regardless.

Author: ElmatadorZ — Apache-2.0
"""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HOOKS_DIR = Path(__file__).parent


def discover() -> List[str]:
    """Return list of hook module names (no .py suffix), alpha-sorted."""
    out: List[str] = []
    for p in sorted(_HOOKS_DIR.glob("*.py")):
        if p.name.startswith("_"):       # skip __init__.py and _private.py
            continue
        out.append(p.stem)
    return out


def run_boot_hooks(app: Any, ctx: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
    """
    Run every hook in this folder. Returns [(hook_name, status_msg), ...].

    Args:
        app: FastAPI app instance (hooks may register routes / middleware)
        ctx: shared context dict (workspace path, db path, etc.)

    Each hook is loaded fresh (importlib.reload) so users can edit hooks
    without restarting the whole backend (next agent_run picks up changes).
    """
    ctx = ctx or {}
    results: List[Tuple[str, str]] = []
    for name in discover():
        mod_name = f"hooks.{name}"
        t0 = time.time()
        try:
            if mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                mod = importlib.import_module(mod_name)
            run = getattr(mod, "run", None)
            if not callable(run):
                results.append((name, "skipped (no run() function)"))
                continue
            run(app, ctx)
            elapsed = (time.time() - t0) * 1000
            results.append((name, f"ok ({elapsed:.0f}ms)"))
        except Exception as e:
            results.append((name, f"error: {type(e).__name__}: {str(e)[:120]}"))
    return results


if __name__ == "__main__":
    print("hooks discovered:", discover())
