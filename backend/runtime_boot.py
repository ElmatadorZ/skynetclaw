"""
runtime_boot.py — OX-HOUSE-BOOT-1
=================================
The Boot Layer: a deterministic Bootstrap Loader that starts Genesis House from
an empty machine — discovering runtimes, loading drivers, scanning capabilities,
benchmarking, building the registry/pools, warming sessions, starting the health
monitor, and reaching HOUSE_READY with NO manual configuration and NO hardcoded
model/runtime/provider names.

It ORCHESTRATES existing layers (does not redesign them):
  runtime_plugins.load_drivers · runtime_scanner.scan · runtime_kernel ·
  runtime_registry · runtime_metrics · config.paths

Every stage is independently timed and published to a Boot Event Bus.
Artifacts (inventories/rankings/timeline) are written under config.paths data
dirs — no absolute paths. First launch benchmarks; later launches reuse the
registry and only re-benchmark changed models.

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

import runtime_registry as _registry
import runtime_metrics as _metrics
import runtime_scanner as _scanner
from runtime_plugins import load_drivers

try:
    from config import paths as _paths
except Exception:                       # pragma: no cover - fallback for odd import roots
    import importlib
    _paths = importlib.import_module("config.paths")

# Phase-9 canonical boot event names, emitted in this fixed order.
BOOT_EVENTS = ["BOOT_START", "CONFIG_LOADED", "PLUGIN_DISCOVERED",
               "RUNTIME_DISCOVERED", "DRIVER_READY", "CAPABILITY_READY",
               "BENCHMARK_COMPLETE", "REGISTRY_READY", "POOL_READY",
               "SESSION_READY", "WORKFLOW_READY", "HOUSE_READY"]


# ── Boot Event Bus (Phase 9) ──────────────────────────────────────────────────
class BootEventBus:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._t0 = time.time()

    def publish(self, event: str, status: str = "ok", **detail) -> None:
        self.events.append({"event": event, "status": status,
                            "t": round(time.time() - self._t0, 3),
                            "ts": time.time(), "detail": detail})

    def timeline(self) -> List[Dict[str, Any]]:
        return list(self.events)


# ── registry persistence (Phase 4) ────────────────────────────────────────────
# ADR-0014 P0: the models table now lives in the institutional DB (satellite
# runtime_registry.db absorbed; original preserved in backups/adr0014_p0_*)
def _registry_db_path() -> str:
    return _paths.data_file("skynerclaw.db")


def _save_registry_db(models: List[Dict[str, Any]]) -> None:
    c = sqlite3.connect(_registry_db_path())
    c.execute("""CREATE TABLE IF NOT EXISTS models(
        model_id TEXT, runtime TEXT, api_type TEXT, roles TEXT, caps TEXT, ts REAL)""")
    c.execute("DELETE FROM models")
    for m in models:
        c.execute("INSERT INTO models VALUES (?,?,?,?,?,?)",
                  (m.get("id"), m.get("runtime"), m.get("api_type"),
                   json.dumps(m.get("roles", [])), json.dumps(
                       {k: m.get(k) for k in ("tool_calling", "vision", "thinking",
                                              "embedding", "context", "param_b",
                                              "quantization")}), time.time()))
    c.commit(); c.close()


def _registry_exists() -> bool:
    p = _registry_db_path()
    if not os.path.exists(p):
        return False
    try:
        c = sqlite3.connect(p)
        n = c.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        c.close()
        return n > 0
    except Exception:
        return False


# ── runtime manifests (Phase 12) ──────────────────────────────────────────────
def _read_manifests() -> List[Dict[str, str]]:
    """Read optional runtime.json manifests from the runtime dir → extra probes,
    sorted by declared priority (higher first). Kernel reads these before probing."""
    probes: List[Dict[str, Any]] = []
    try:
        rdir = _paths.runtime_dir()
        for fn in sorted(os.listdir(rdir)):
            if not fn.endswith(".json"):
                continue
            try:
                man = json.loads(open(os.path.join(rdir, fn), encoding="utf-8").read())
                if man.get("url"):
                    probes.append({"runtime": man.get("runtime") or man.get("driver") or fn,
                                   "url": man["url"], "api_type": man.get("driver", "openai"),
                                   "priority": man.get("priority", 0)})
            except Exception:
                continue
    except Exception:
        pass
    return sorted(probes, key=lambda p: p.get("priority", 0), reverse=True)


# ── Bootstrap Loader (Phase 1) ────────────────────────────────────────────────
class BootLoader:
    def __init__(self, extra_probes: Optional[List[dict]] = None,
                 bus: Optional[BootEventBus] = None):
        self.bus = bus or BootEventBus()
        self.extra_probes = extra_probes or []
        self.timeline: List[Dict[str, Any]] = []
        self.state = "COLD"
        self.drivers = []
        self.scan: List[Dict[str, Any]] = []
        self.registry: Dict[str, Any] = {}
        self.kernel = None
        self._monitor_stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def boot(self, quick: bool = False, warmup: bool = True,
             start_monitor: bool = False) -> Dict[str, Any]:
        """Run the full deterministic boot sequence. quick=True reuses an existing
        registry/metrics and skips benchmarking unchanged models (warm boot)."""
        self.bus.publish("BOOT_START", mode="quick" if quick else "full")
        t_boot = time.time()

        # CONFIG
        cfg = self._timed("CONFIG", "CONFIG_LOADED", lambda: _paths.describe())
        # PLUGINS (Phase 3)
        self.drivers = self._timed("PLUGINS", "PLUGIN_DISCOVERED",
                                   lambda: load_drivers())
        # RUNTIMES (Phase 2) — manifests first, then probes. Discover ONCE via the
        # kernel (driver-based, trimmed timeouts); POOLS later just reads it.
        man = _read_manifests()
        self.scan = self._timed("RUNTIMES", "RUNTIME_DISCOVERED",
                                lambda: self._discover(man + self.extra_probes))
        # DRIVERS ready
        self._timed("DRIVERS", "DRIVER_READY",
                    lambda: [d.describe() for d in self.drivers])
        # CAPABILITIES (Phase 4) — classification from declared caps
        models = self._timed("CAPABILITIES", "CAPABILITY_READY",
                             lambda: _registry.flatten(self.scan))
        # HEALTH
        import runtime_router as _router
        self._timed("HEALTH", "HEALTH_OK",
                    lambda: _router.health_report(self.scan))
        # BENCHMARK (Phase 5) — wizard: only when needed / changed (Phase 11)
        self._timed("BENCHMARK", "BENCHMARK_COMPLETE",
                    lambda: self._benchmark(models, quick))
        # REGISTRY (Phase 4/6)
        self.registry = self._timed("REGISTRY", "REGISTRY_READY",
                                    lambda: self._build_registry(self.scan))
        _save_registry_db(models)
        # POOLS (Phase 6) — kernel already discovered in RUNTIMES; just read pools
        self._timed("POOLS", "POOL_READY", lambda: self.kernel.pools() if self.kernel else {})
        # SESSIONS (Phase 8) — warm execution pool
        self._timed("SESSIONS", "SESSION_READY", lambda: self._warmup() if warmup else {})
        # WORKFLOW
        self._timed("WORKFLOW", "WORKFLOW_READY", lambda: {"engine": "ready"})

        self.state = "READY"
        ready_s = round(time.time() - t_boot, 3)
        self.bus.publish("HOUSE_READY", ready_s=ready_s,
                         runtimes=len(self.scan), drivers=len(self.drivers))
        self._write_artifacts()
        if start_monitor:
            self.start_health_monitor()
        return {"state": self.state, "ready_s": ready_s, "timeline": self.timeline,
                "runtimes": len(self.scan), "drivers": len(self.drivers),
                "pools": self.kernel.pools() if self.kernel else {}}

    def _timed(self, name: str, event: str, fn):
        t0 = time.time()
        try:
            res = fn()
            dt = round(time.time() - t0, 3)
            n = len(res) if hasattr(res, "__len__") else None
            self.timeline.append({"stage": name, "ms": int(dt * 1000), "ok": True, "count": n})
            self.bus.publish(event, "ok", duration_s=dt, count=n)
            return res
        except Exception as e:
            dt = round(time.time() - t0, 3)
            self.timeline.append({"stage": name, "ms": int(dt * 1000), "ok": False, "error": str(e)[:120]})
            self.bus.publish(event, "error", duration_s=dt, error=str(e)[:160])
            return None

    # — stage helpers —
    def _benchmark(self, models, quick: bool) -> Dict[str, Any]:
        existing = _metrics.load_metrics()
        # wizard: first launch (no registry) → benchmark all execution-capable;
        # warm boot → only models without metrics (changed/new).
        exec_models = [m for m in (models or []) if "Execution" in m.get("roles", [])]
        if quick and _registry_exists():
            todo = [m for m in exec_models if m["id"] not in existing]
        else:
            todo = exec_models
        if not todo:
            return {"benchmarked": 0, "reused": len(existing)}
        return _metrics.benchmark_all(todo)

    def _build_registry(self, scan) -> Dict[str, Any]:
        return _registry.build_registry(scan, _metrics.load_metrics())

    def _discover(self, probes):
        """Single discovery via the kernel (driver-based, trimmed timeouts).
        Returns scanner-shaped runtime list derived from kernel instances."""
        import runtime_kernel as _rk
        self.kernel = _rk.get_kernel(extra_probes=probes, rediscover=True)
        return [{"runtime": i.name, "url": i.url, "api_type": i.api_type,
                 "online": i.online, "models": i.models} for i in self.kernel.instances]

    def _warmup(self) -> Dict[str, Any]:
        if not self.kernel:
            return {}
        sel = self.kernel.select(required={"role": "Execution", "tool_calling": True},
                                 metrics=_metrics.load_metrics())
        if not sel:
            return {"warmed": None}
        try:
            for _ in self.kernel.infer(required={"role": "Execution", "tool_calling": True},
                                       messages=[{"role": "user", "content": "ok"}],
                                       stream=True, options={"temperature": 0.0},
                                       metrics=_metrics.load_metrics()):
                break  # first event = model resident
        except Exception:
            pass
        return {"warmed": sel.get("model"), "runtime": sel.get("runtime")}

    # — health monitor (Phase 7) —
    def start_health_monitor(self, interval: float = 30.0) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_stop.clear()

        def _loop():
            while not self._monitor_stop.wait(interval):
                try:
                    if self.kernel:
                        h = self.kernel.health()       # flips instance.healthy + failover-ready
                        self.bus.publish("HEALTH_TICK", "ok",
                                         healthy=h.get("healthy"), unhealthy=h.get("unhealthy"))
                except Exception:
                    pass
        self._monitor_thread = threading.Thread(target=_loop, daemon=True)
        self._monitor_thread.start()

    def stop_health_monitor(self) -> None:
        self._monitor_stop.set()

    def health_tick(self) -> Dict[str, Any]:
        """One synchronous monitor tick (for tests / on-demand)."""
        return self.kernel.health() if self.kernel else {}

    # — artifacts (deliverables) —
    def _write_artifacts(self) -> None:
        d = _paths.user_data_dir()
        try:
            _dump(os.path.join(str(d), "runtime_inventory.json"), self.scan)
            _dump(os.path.join(str(d), "driver_inventory.json"),
                  [drv.describe() for drv in self.drivers])
            _dump(os.path.join(str(d), "runtime_rankings.json"),
                  (self.registry or {}).get("rankings", {}))
            self._write_timeline_md(os.path.join(str(d), "BOOT_TIMELINE.md"))
        except Exception:
            pass

    def _write_timeline_md(self, path: str) -> None:
        lines = ["# BOOT_TIMELINE.md (generated)\n",
                 f"state: {self.state}\n", "| # | stage | ms | ok | count |",
                 "|--:|---|--:|:--:|--:|"]
        for i, s in enumerate(self.timeline, 1):
            lines.append(f"| {i} | {s['stage']} | {s['ms']} | "
                         f"{'✅' if s.get('ok') else '❌'} | {s.get('count','')} |")
        total = sum(s["ms"] for s in self.timeline)
        lines.append(f"\n**Total: {total} ms** · events: " +
                     " → ".join(e["event"] for e in self.bus.timeline()))
        open(path, "w", encoding="utf-8").write("\n".join(lines))

    def snapshot(self) -> Dict[str, Any]:
        return {"state": self.state, "timeline": self.timeline,
                "events": self.bus.timeline(),
                "runtimes": len(self.scan), "drivers": len(self.drivers),
                "pools": self.kernel.pools() if self.kernel else {}}


def _dump(path: str, obj) -> None:
    open(path, "w", encoding="utf-8").write(json.dumps(obj, indent=2, default=str))


# ── singleton (the House boots once) ──────────────────────────────────────────
_BOOT: Optional[BootLoader] = None


def house_boot(extra_probes: Optional[List[dict]] = None, quick: bool = True,
               start_monitor: bool = True) -> BootLoader:
    global _BOOT
    if _BOOT is None or _BOOT.state != "READY":
        _BOOT = BootLoader(extra_probes=extra_probes)
        _BOOT.boot(quick=quick, start_monitor=start_monitor)
    return _BOOT


def get_boot() -> Optional[BootLoader]:
    return _BOOT


if __name__ == "__main__":
    b = BootLoader().boot(quick=False)
    print(json.dumps({"state": b["state"], "ready_s": b["ready_s"],
                      "timeline": b["timeline"]}, indent=2))
