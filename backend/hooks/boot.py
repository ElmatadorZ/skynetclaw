"""
boot.py — sample / default boot hook
=====================================
Runs once on FastAPI startup. Default behavior: print a banner showing
which Masterpiece subsystems were loaded.

Edit freely. Add your own hooks as separate files (e.g. 10_seed.py,
20_register_routes.py, 30_warmup.py — alphabetical order of filename).

Hook contract:
    def run(app, ctx: dict) -> None:
        # app is the FastAPI instance
        # ctx may contain workspace/db_path/etc — see hooks/__init__.py
        ...
"""
from __future__ import annotations

import time
import datetime as _dt
from typing import Any, Dict


def run(app: Any, ctx: Dict[str, Any]) -> None:
    """Default boot hook — banner print."""
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Detect which subsystems are wired in
    subsystems = []
    try:
        from skynet_genesis_masterpiece import register_masterpiece  # noqa
        subsystems.append("Masterpiece")
    except Exception:
        pass
    try:
        from skynetclaw_router import register_router  # noqa
        subsystems.append("Router")
    except Exception:
        pass
    try:
        from openclaw_port import TrajectoryWriter  # noqa
        subsystems.append("TrajectoryWriter")
    except Exception:
        pass
    try:
        from openclaw_port_tier2 import AgentRunsDB  # noqa
        subsystems.append("AgentRunsDB")
    except Exception:
        pass
    try:
        from prompts import compose_genesis_prompt  # noqa
        subsystems.append("ModularPrompts")
    except Exception:
        pass

    banner = (
        "\n"
        "  ╭──────────────────────────────────────────────────────────────╮\n"
        "  │  SKYNETCLAW MASTERPIECE — boot hook fired                    │\n"
        f"  │  {now}                                       │\n"
        f"  │  loaded: {', '.join(subsystems) or '(none)':<52s}│\n"
        "  ╰──────────────────────────────────────────────────────────────╯\n"
    )
    print(banner)
