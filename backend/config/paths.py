"""
config/paths.py — OX-RUNTIME-DISCOVERY-1 Phases 9 & 10
======================================================
Single source of truth for filesystem locations so the backend can run as:
  • source       (python main.py from the repo)
  • portable      (a folder you can move/zip — data lives beside the app)
  • installed     (data in the OS user-data dir)
  • exe           (PyInstaller/Nuitka frozen single binary)

No absolute paths anywhere else in the runtime layer should be hardcoded —
import these helpers instead. All directories are created on first access.

Dependency-free (stdlib only).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TheHouse"


def is_frozen() -> bool:
    """True when running as a PyInstaller/Nuitka frozen executable."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def mode() -> str:
    if is_frozen():
        return "exe"
    if os.environ.get("HOUSE_PORTABLE") == "1":
        return "portable"
    if os.environ.get("HOUSE_INSTALLED") == "1":
        return "installed"
    return "source"


def app_dir() -> Path:
    """Directory of the running app/binary (where the exe or main.py lives)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # backend/


def _base_data_dir() -> Path:
    m = mode()
    if m in ("portable", "exe"):
        # data travels with the app
        return app_dir() / "data"
    if m == "installed":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") \
            or str(Path.home() / ".local" / "share")
        return Path(root) / APP_NAME
    # source: keep data inside backend/ (current behaviour)
    return app_dir()


def _ensure(p: Path) -> Path:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def user_data_dir() -> Path: return _ensure(_base_data_dir())
def cache_dir() -> Path:     return _ensure(_base_data_dir() / "cache")
def log_dir() -> Path:       return _ensure(_base_data_dir() / "logs")
def runtime_dir() -> Path:   return _ensure(_base_data_dir() / "runtime")
def config_dir() -> Path:    return _ensure(app_dir() / "config")


def data_file(name: str) -> str:
    """Resolve a data file (db/json) under the active data dir. In source mode
    this is backend/<name> so existing files (skynerclaw.db, *.json) keep working."""
    return str(_base_data_dir() / name)


def describe() -> dict:
    return {
        "mode": mode(), "frozen": is_frozen(),
        "app_dir": str(app_dir()), "user_data": str(_base_data_dir()),
        "cache": str(cache_dir()), "logs": str(log_dir()),
        "runtime": str(runtime_dir()), "config": str(config_dir()),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(describe(), indent=2))
