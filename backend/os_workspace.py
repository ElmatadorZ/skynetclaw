"""
os_workspace.py — OX-HOUSE-OS-1 Phase 7
=======================================
Workspace Manager. A workspace is a portable, self-contained directory holding
everything an instance of the House needs: memory, registry, runtime, logs,
settings, plugins. All paths resolve under config.paths (no absolute paths), so
a workspace can be zipped, moved, or shipped inside GenesisHouse.exe.

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

try:
    from config import paths as _paths
except Exception:
    import importlib
    _paths = importlib.import_module("config.paths")

_SUBDIRS = ["memory", "registry", "runtime", "logs", "settings", "plugins"]


def _workspaces_root() -> str:
    root = os.path.join(str(_paths.user_data_dir()), "workspaces")
    os.makedirs(root, exist_ok=True)
    return root


class Workspace:
    def __init__(self, name: str):
        self.name = name
        self.root = os.path.join(_workspaces_root(), name)

    def ensure(self) -> "Workspace":
        for sub in _SUBDIRS:
            os.makedirs(os.path.join(self.root, sub), exist_ok=True)
        meta = os.path.join(self.root, "workspace.json")
        if not os.path.exists(meta):
            open(meta, "w", encoding="utf-8").write(json.dumps(
                {"name": self.name, "created": time.time(), "subdirs": _SUBDIRS}, indent=2))
        return self

    def dir(self, sub: str) -> str:
        return os.path.join(self.root, sub)

    def describe(self) -> Dict[str, Any]:
        return {"name": self.name, "root": self.root,
                "dirs": {s: os.path.join(self.root, s) for s in _SUBDIRS},
                "exists": os.path.isdir(self.root)}


class WorkspaceManager:
    def __init__(self):
        self._current = "default"
        Workspace("default").ensure()

    def create(self, name: str) -> Dict[str, Any]:
        return Workspace(name).ensure().describe()

    def list(self) -> List[str]:
        root = _workspaces_root()
        return sorted(d for d in os.listdir(root)
                      if os.path.isdir(os.path.join(root, d)))

    def switch(self, name: str) -> Dict[str, Any]:
        Workspace(name).ensure()
        self._current = name
        return {"current": name}

    def current(self) -> Workspace:
        return Workspace(self._current).ensure()

    def describe(self) -> Dict[str, Any]:
        return {"current": self._current, "workspaces": self.list(),
                "root": _workspaces_root()}
