"""
genesis_os.py — OX-HOUSE-OS-1
=============================
Genesis House as an AI Operating System. This facade wires the OS subsystems
together and exposes a single boot/status surface. The Runtime Kernel becomes
ONE subsystem among many (runtime service); everything above it — apps,
services, permissions, IPC, packages, workspaces — is modular and independently
manageable.

  OS = IPC bus + Permission/Audit + Service Manager + Workspace Manager
       + Application Manager + Package Manager + (Runtime Kernel as a service)

No redesign of existing layers — pure orchestration.
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import time
from typing import Any, Dict

from os_ipc import EventBus
from os_permissions import AuditLog, PermissionManager
from os_services import ServiceManager
from os_workspace import WorkspaceManager
from os_apps import ApplicationManager
from os_packages import PackageManager


class GenesisOS:
    def __init__(self):
        self.ipc = EventBus()
        self.audit = AuditLog()
        self.permissions = PermissionManager(self.audit)
        self.services = ServiceManager(); self.services.register_defaults()
        self.workspace = WorkspaceManager()
        self.apps = ApplicationManager(self)
        self.packages = PackageManager(self)
        self.state = "halted"
        self.booted_at: float = 0.0

    def kernel(self):
        """The Runtime Kernel — accessed as a subsystem, never bypassed by apps."""
        import runtime_kernel as rk
        return rk.get_kernel(rediscover=False)

    def boot(self, start_services: bool = True) -> Dict[str, Any]:
        t0 = time.time()
        self.ipc.publish("os.boot_start", source="os")
        if start_services:
            self.services.start_all()
        self.apps.discover()
        self.state = "running"; self.booted_at = time.time()
        self.ipc.publish("os.ready", {"services": self.services.names(),
                                      "apps": list(self.apps.apps.keys())}, source="os")
        return {"state": self.state, "boot_s": round(time.time() - t0, 3),
                "services": self.services.names(), "apps": list(self.apps.apps.keys())}

    def shutdown(self) -> None:
        for aid in list(self.apps.apps.keys()):
            try: self.apps.stop(aid)
            except Exception: pass
        self.services.stop_all()
        self.state = "halted"
        self.ipc.publish("os.halted", source="os")

    def status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "uptime_s": round(time.time() - self.booted_at, 1) if self.booted_at else 0,
            "services": self.services.health(),
            "apps": self.apps.list(),
            "workspace": self.workspace.describe(),
            "ipc": {"topics": self.ipc.topics()[-20:],
                    "subscriptions": len(self.ipc.subscriptions())},
            "permissions": {"audited": len(self.audit.entries(limit=10_000)),
                            "denials": len(self.audit.denials(limit=10_000))},
        }


_OS: GenesisOS = None


def get_os() -> GenesisOS:
    global _OS
    if _OS is None:
        _OS = GenesisOS()
    return _OS
