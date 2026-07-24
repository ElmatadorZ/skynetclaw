"""
os_apps.py — OX-HOUSE-OS-1 Phase 1
==================================
The Application Manager. Applications live in `plugins/apps/<id>/` with a
manifest (id/version/dependencies/permissions/entrypoint) and an entrypoint
module exporting `setup(ctx)` / optional `teardown(ctx)`. The manager handles the
full lifecycle: discover → install → start → stop → uninstall, enforcing
dependencies and permissions.

Apps NEVER touch runtime/memory/fs/network directly. They receive an AppContext
whose every privileged method is brokered by the Permission Manager and routed
through the IPC bus / Service Manager / Runtime Kernel. (Phase 3 + 4.)

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from config import paths as _paths
except Exception:
    import importlib
    _paths = importlib.import_module("config.paths")


def apps_dir() -> str:
    d = os.path.join(str(_paths.user_data_dir()), "plugins", "apps")
    os.makedirs(d, exist_ok=True)
    return d


@dataclass
class AppManifest:
    id: str
    name: str = ""
    version: str = "0.0.0"
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    entrypoint: str = "app.py"
    description: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AppManifest":
        return AppManifest(
            id=d["id"], name=d.get("name", d["id"]), version=d.get("version", "0.0.0"),
            dependencies=list(d.get("dependencies", [])),
            permissions=list(d.get("permissions", [])),
            entrypoint=d.get("entrypoint", "app.py"),
            description=d.get("description", ""))

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "version": self.version,
                "dependencies": self.dependencies, "permissions": self.permissions,
                "entrypoint": self.entrypoint, "description": self.description}


class AppContext:
    """The permission-gated OS surface handed to an application. Every privileged
    call checks a capability before delegating — apps cannot bypass the broker."""
    def __init__(self, app_id: str, os_api: "Any"):
        self.app_id = app_id
        self._os = os_api

    def infer(self, **kwargs):
        self._os.permissions.require(self.app_id, "runtime.infer")
        return self._os.kernel().infer(**kwargs)

    def publish(self, topic: str, payload: Any = None) -> int:
        self._os.permissions.require(self.app_id, "ipc.publish", topic)
        return self._os.ipc.publish(topic, payload, source=f"app:{self.app_id}")

    def subscribe(self, pattern: str, handler: Callable) -> Callable:
        self._os.permissions.require(self.app_id, "ipc.subscribe", pattern)
        return self._os.ipc.subscribe(pattern, handler, owner=f"app:{self.app_id}")

    def service(self, name: str):
        self._os.permissions.require(self.app_id, "service.use", name)
        return self._os.services.get(name)

    def workspace(self):
        return self._os.workspace.current()

    def log(self, msg: str) -> None:
        self._os.ipc.publish(f"app.{self.app_id}.log", str(msg)[:500], source=f"app:{self.app_id}")


@dataclass
class Application:
    manifest: AppManifest
    path: str
    state: str = "installed"        # installed | running | stopped | error
    error: Optional[str] = None
    module: Any = None
    started_at: Optional[float] = None

    def info(self) -> Dict[str, Any]:
        return {"id": self.manifest.id, "name": self.manifest.name,
                "version": self.manifest.version, "state": self.state,
                "permissions": self.manifest.permissions,
                "dependencies": self.manifest.dependencies, "error": self.error,
                "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else 0}


class ApplicationManager:
    def __init__(self, os_api: "Any"):
        self._os = os_api
        self.apps: Dict[str, Application] = {}

    # — discovery / install —
    def discover(self) -> List[str]:
        found = []
        root = apps_dir()
        for aid in sorted(os.listdir(root)):
            mpath = os.path.join(root, aid, "manifest.json")
            if os.path.isfile(mpath):
                try:
                    man = AppManifest.from_dict(json.loads(open(mpath, encoding="utf-8").read()))
                    self.apps[man.id] = Application(manifest=man, path=os.path.join(root, aid))
                    found.append(man.id)
                except Exception:
                    continue
        return found

    def install(self, manifest: Dict[str, Any], files: Dict[str, str] = None) -> Dict[str, Any]:
        man = AppManifest.from_dict(manifest)
        dest = os.path.join(apps_dir(), man.id)
        os.makedirs(dest, exist_ok=True)
        open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8").write(
            json.dumps(man.to_dict(), indent=2))
        for fname, content in (files or {}).items():
            open(os.path.join(dest, fname), "w", encoding="utf-8").write(content)
        self.apps[man.id] = Application(manifest=man, path=dest)
        self._os.ipc.publish("app.installed", man.id, source="app_manager")
        return self.apps[man.id].info()

    # — lifecycle —
    def start(self, app_id: str) -> Dict[str, Any]:
        app = self.apps.get(app_id)
        if not app:
            return {"error": f"no app {app_id}"}
        # dependency check
        missing = [d for d in app.manifest.dependencies
                   if self.apps.get(d) is None or self.apps[d].state != "running"]
        if missing:
            app.state = "error"; app.error = f"unmet dependencies: {missing}"
            return app.info()
        # grant declared permissions
        self._os.permissions.grant(app_id, app.manifest.permissions)
        # load entrypoint + setup
        try:
            mod = self._load_module(app)
            app.module = mod
            if hasattr(mod, "setup"):
                mod.setup(AppContext(app_id, self._os))
            app.state = "running"; app.started_at = time.time(); app.error = None
            self._os.ipc.publish("app.started", app_id, source="app_manager")
        except Exception as e:
            app.state = "error"; app.error = str(e)[:200]
        return app.info()

    def stop(self, app_id: str) -> Dict[str, Any]:
        app = self.apps.get(app_id)
        if not app:
            return {"error": f"no app {app_id}"}
        try:
            if app.module and hasattr(app.module, "teardown"):
                app.module.teardown(AppContext(app_id, self._os))
        except Exception:
            pass
        self._os.ipc.unsubscribe_owner(f"app:{app_id}")
        app.state = "stopped"; app.started_at = None
        self._os.ipc.publish("app.stopped", app_id, source="app_manager")
        return app.info()

    def uninstall(self, app_id: str) -> Dict[str, Any]:
        app = self.apps.get(app_id)
        if app and app.state == "running":
            self.stop(app_id)
        self._os.permissions.revoke(app_id)
        if app and os.path.isdir(app.path):
            shutil.rmtree(app.path, ignore_errors=True)
        self.apps.pop(app_id, None)
        self._os.ipc.publish("app.uninstalled", app_id, source="app_manager")
        return {"uninstalled": app_id}

    def list(self) -> List[Dict[str, Any]]:
        return [a.info() for a in self.apps.values()]

    def _load_module(self, app: Application):
        ep = os.path.join(app.path, app.manifest.entrypoint)
        spec = importlib.util.spec_from_file_location(f"genesis_app_{app.manifest.id}", ep)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
