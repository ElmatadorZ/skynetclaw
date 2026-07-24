"""
os_services.py — OX-HOUSE-OS-1 Phase 2
======================================
The Service Manager. Long-lived OS subsystems are wrapped as Services with a
uniform lifecycle — start() / stop() / restart() / health() — so the OS can
supervise them independently. Services WRAP existing subsystems (kernel, boot,
workflow, memory, scheduler); they do not reimplement them.

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional


class Service:
    name: str = "service"

    def __init__(self, name: str = None):
        if name:
            self.name = name
        self.state = "stopped"          # stopped | running | error
        self.started_at: Optional[float] = None
        self.error: Optional[str] = None

    def start(self) -> None:
        try:
            self.on_start()
            self.state = "running"; self.started_at = time.time(); self.error = None
        except Exception as e:
            self.state = "error"; self.error = str(e)[:160]

    def stop(self) -> None:
        try:
            self.on_stop()
        finally:
            self.state = "stopped"; self.started_at = None

    def restart(self) -> None:
        self.stop(); self.start()

    def health(self) -> Dict[str, Any]:
        h = {"service": self.name, "state": self.state,
             "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else 0,
             "error": self.error}
        try:
            h.update(self.on_health())
        except Exception as e:
            h["health_error"] = str(e)[:120]
        return h

    # hooks
    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...
    def on_health(self) -> Dict[str, Any]: return {}


# ── built-in services (thin wrappers over existing subsystems) ────────────────
class RuntimeService(Service):
    name = "runtime"
    def on_start(self):
        import runtime_kernel as rk
        self._k = rk.get_kernel(rediscover=False)
    def on_health(self):
        import runtime_kernel as rk
        k = rk.get_kernel(rediscover=False)
        pools = k.pools()
        return {"instances": len(k.instances), "pools": {r: len(v) for r, v in pools.items()},
                "sessions": len(k.sessions)}


class WorkflowService(Service):
    name = "workflow"
    def on_health(self):
        return {"engine": "comprehend→plan→execute→reflect"}


class MemoryService(Service):
    name = "memory"
    def on_health(self):
        import os
        try:
            from config import paths
            d = paths.user_data_dir()
            return {"data_dir": str(d), "exists": os.path.isdir(str(d))}
        except Exception:
            return {"data_dir": None}


class MonitoringService(Service):
    name = "monitoring"
    def on_health(self):
        try:
            import reliability_dashboard as rel
            g = rel.gpu_metrics()
            return {"gpu_present": g.get("present"), "gpu_util": g.get("util_pct")}
        except Exception:
            return {}


class SchedulerService(Service):
    """Background scheduler: runs registered periodic jobs off a daemon thread."""
    name = "scheduler"
    def __init__(self):
        super().__init__()
        self._jobs: List[Dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def add_job(self, name: str, fn: Callable[[], None], interval_s: float) -> None:
        self._jobs.append({"name": name, "fn": fn, "interval": interval_s, "last": 0.0})

    _TICK = 0.2     # scheduler resolution

    def on_start(self):
        self._stop.clear()
        def _loop():
            while not self._stop.wait(self._TICK):
                now = time.time()
                for j in self._jobs:
                    if now - j["last"] >= j["interval"]:
                        j["last"] = now
                        try: j["fn"]()
                        except Exception: pass
        self._thread = threading.Thread(target=_loop, daemon=True); self._thread.start()

    def on_stop(self):
        self._stop.set()

    def on_health(self):
        return {"jobs": [j["name"] for j in self._jobs]}


class ServiceManager:
    def __init__(self):
        self._services: Dict[str, Service] = {}

    def register(self, svc: Service) -> None:
        self._services[svc.name] = svc

    def register_defaults(self) -> None:
        for s in (RuntimeService(), WorkflowService(), MemoryService(),
                  MonitoringService(), SchedulerService()):
            self.register(s)

    def get(self, name: str) -> Optional[Service]:
        return self._services.get(name)

    def start(self, name: str) -> Dict[str, Any]:
        s = self._services.get(name)
        if not s: return {"error": f"no service {name}"}
        s.start(); return s.health()

    def stop(self, name: str) -> Dict[str, Any]:
        s = self._services.get(name)
        if not s: return {"error": f"no service {name}"}
        s.stop(); return s.health()

    def restart(self, name: str) -> Dict[str, Any]:
        s = self._services.get(name)
        if not s: return {"error": f"no service {name}"}
        s.restart(); return s.health()

    def start_all(self) -> List[Dict[str, Any]]:
        for s in self._services.values():
            s.start()
        return self.health()

    def stop_all(self) -> None:
        for s in self._services.values():
            s.stop()

    def health(self) -> List[Dict[str, Any]]:
        return [s.health() for s in self._services.values()]

    def names(self) -> List[str]:
        return list(self._services.keys())
