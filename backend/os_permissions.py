"""
os_permissions.py — OX-HOUSE-OS-1 Phase 3
=========================================
The Permission + Capability Manager with an Audit Log. Applications NEVER touch
the runtime, memory, filesystem, or network directly — every privileged action
is brokered here: an app must hold the capability or the call is denied and
audited.

Capabilities are coarse, declarative strings an app requests in its manifest:
  runtime.infer · runtime.read · memory.read · memory.write · fs.read · fs.write
  · net.http · service.use · ipc.publish · ipc.subscribe · package.manage

Pure & deterministic → fully unit-tested.
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Set

CAPABILITIES: Set[str] = {
    "runtime.infer", "runtime.read", "memory.read", "memory.write",
    "fs.read", "fs.write", "net.http", "service.use",
    "ipc.publish", "ipc.subscribe", "package.manage", "workspace.manage",
}


class PermissionDenied(Exception):
    pass


class AuditLog:
    def __init__(self, limit: int = 1000):
        self._log: List[Dict[str, Any]] = []
        self._limit = limit

    def record(self, actor: str, capability: str, resource: str, allowed: bool) -> None:
        self._log.append({"actor": actor, "capability": capability,
                          "resource": resource, "allowed": allowed, "ts": time.time()})
        if len(self._log) > self._limit:
            self._log = self._log[-self._limit:]

    def entries(self, actor: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        items = [e for e in self._log if not actor or e["actor"] == actor]
        return items[-limit:]

    def denials(self, limit: int = 200) -> List[Dict[str, Any]]:
        return [e for e in self._log if not e["allowed"]][-limit:]


class PermissionManager:
    def __init__(self, audit: AuditLog = None):
        self.audit = audit or AuditLog()
        self._grants: Dict[str, Set[str]] = {}     # app_id → capabilities

    def grant(self, app_id: str, capabilities: List[str]) -> Dict[str, Any]:
        valid = {c for c in capabilities if c in CAPABILITIES}
        unknown = sorted(set(capabilities) - valid)
        self._grants.setdefault(app_id, set()).update(valid)
        return {"granted": sorted(valid), "unknown": unknown}

    def revoke(self, app_id: str, capabilities: List[str] = None) -> None:
        if capabilities is None:
            self._grants.pop(app_id, None)
        else:
            self._grants.get(app_id, set()).difference_update(capabilities)

    def granted(self, app_id: str) -> List[str]:
        return sorted(self._grants.get(app_id, set()))

    def check(self, app_id: str, capability: str, resource: str = "") -> bool:
        allowed = capability in self._grants.get(app_id, set())
        self.audit.record(app_id, capability, resource, allowed)
        return allowed

    def require(self, app_id: str, capability: str, resource: str = "") -> None:
        if not self.check(app_id, capability, resource):
            raise PermissionDenied(f"{app_id} lacks capability '{capability}'"
                                   + (f" for {resource}" if resource else ""))
