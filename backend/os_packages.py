"""
os_packages.py — OX-HOUSE-OS-1 Phase 5
======================================
The Package Manager for Genesis Packages (.gpkg). A .gpkg is a ZIP containing a
manifest.json plus the app's files. Supports install / update / rollback /
uninstall with a kept version history, so any install can be reverted.

Delegates the actual app lifecycle to the Application Manager — this layer only
handles packaging, versioning, and history.

Dependency-free (stdlib only: zipfile/json/shutil).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import shutil
import time
import zipfile
from typing import Any, Dict, List, Optional

try:
    from config import paths as _paths
except Exception:
    import importlib
    _paths = importlib.import_module("config.paths")


def _versions_root() -> str:
    d = os.path.join(str(_paths.user_data_dir()), "plugins", "versions")
    os.makedirs(d, exist_ok=True)
    return d


def build_gpkg(manifest: Dict[str, Any], files: Dict[str, str], out_path: str) -> str:
    """Create a .gpkg (zip) from a manifest dict + {filename: text}. Returns path."""
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        for name, content in files.items():
            z.writestr(name, content)
    return out_path


def read_gpkg(gpkg_path: str) -> Dict[str, Any]:
    with zipfile.ZipFile(gpkg_path) as z:
        names = z.namelist()
        if "manifest.json" not in names:
            raise ValueError("invalid .gpkg: missing manifest.json")
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        files = {n: z.read(n).decode("utf-8", "replace")
                 for n in names if n != "manifest.json"}
    return {"manifest": manifest, "files": files}


class PackageManager:
    def __init__(self, os_api: "Any"):
        self._os = os_api

    def _snapshot(self, app_id: str) -> Optional[str]:
        """Save the current app dir into version history before overwrite."""
        app = self._os.apps.apps.get(app_id)
        if not app or not os.path.isdir(app.path):
            return None
        ver = app.manifest.version
        dest = os.path.join(_versions_root(), app_id, f"{ver}-{int(time.time())}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copytree(app.path, dest, dirs_exist_ok=True)
        return dest

    def install(self, gpkg_path: str) -> Dict[str, Any]:
        pkg = read_gpkg(gpkg_path)
        aid = pkg["manifest"]["id"]
        if aid in self._os.apps.apps:
            self._snapshot(aid)        # keep prior version for rollback
        info = self._os.apps.install(pkg["manifest"], pkg["files"])
        self._os.ipc.publish("package.installed", {"id": aid, "version": info.get("version")},
                             source="package_manager")
        return info

    def update(self, gpkg_path: str) -> Dict[str, Any]:
        return self.install(gpkg_path)   # install snapshots the old version first

    def list_versions(self, app_id: str) -> List[str]:
        root = os.path.join(_versions_root(), app_id)
        if not os.path.isdir(root):
            return []
        return sorted(os.listdir(root))

    def rollback(self, app_id: str) -> Dict[str, Any]:
        versions = self.list_versions(app_id)
        if not versions:
            return {"error": f"no version history for {app_id}"}
        latest = versions[-1]
        src = os.path.join(_versions_root(), app_id, latest)
        app = self._os.apps.apps.get(app_id)
        was_running = app and app.state == "running"
        if was_running:
            self._os.apps.stop(app_id)
        # snapshot current (so rollback is itself reversible), then restore
        self._snapshot(app_id)
        dest = os.path.join(str(_paths.user_data_dir()), "plugins", "apps", app_id)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(src, dest, dirs_exist_ok=True)
        self._os.apps.discover()
        if was_running:
            self._os.apps.start(app_id)
        self._os.ipc.publish("package.rolledback", {"id": app_id, "to": latest},
                             source="package_manager")
        return {"rolledback": app_id, "restored": latest}

    def uninstall(self, app_id: str) -> Dict[str, Any]:
        res = self._os.apps.uninstall(app_id)
        self._os.ipc.publish("package.uninstalled", app_id, source="package_manager")
        return res
