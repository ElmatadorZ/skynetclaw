"""
test_runtime_boot.py — OX-HOUSE-BOOT-1 Phase 15
Deterministic boot-layer tests with the heavy stages monkeypatched (no network):
event bus, deterministic stage ordering, canonical event sequence, first-launch
wizard, health monitor, no hardcoded names, relocatable paths.
"""
from __future__ import annotations
import sys, time, inspect
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runtime_boot as B


def test_event_bus_order_and_timing():
    bus = B.BootEventBus()
    bus.publish("BOOT_START"); bus.publish("HOUSE_READY")
    tl = bus.timeline()
    assert [x["event"] for x in tl] == ["BOOT_START", "HOUSE_READY"]
    assert all("t" in x and "ts" in x for x in tl)


def test_canonical_event_names():
    assert B.BOOT_EVENTS[0] == "BOOT_START" and B.BOOT_EVENTS[-1] == "HOUSE_READY"


class _FakeInst:
    def __init__(self):
        self.name = "r"; self.url = "http://x"; self.api_type = "openai"
        self.online = True
        self.models = [{"id": "m", "roles": ["Execution"], "tool_calling": True}]


class _FakeKernel:
    def __init__(self): self.instances = [_FakeInst()]
    def pools(self): return {"Execution": [{"runtime": "r", "model": "m"}]}
    def health(self): return {"runtimes": [], "healthy": ["r"], "unhealthy": []}
    def select(self, **k): return None
    def infer(self, **k): yield '{"type":"done"}'


def _patch(mp):
    fk = _FakeKernel()
    mp.setattr(B, "load_drivers", lambda: [type("D", (), {"describe": lambda s: {"driver": "fake"}})()])
    def _disc(self, probes): self.kernel = fk; return [{"runtime": "r", "url": "http://x",
                                                        "api_type": "openai", "online": True,
                                                        "models": fk.instances[0].models}]
    mp.setattr(B.BootLoader, "_discover", _disc)
    mp.setattr(B._metrics, "load_metrics", lambda *a, **k: {})
    mp.setattr(B._metrics, "benchmark_all", lambda *a, **k: {"benchmarked": 0})
    mp.setattr(B._registry, "build_registry", lambda *a, **k: {"rankings": {"Execution": [
        {"id": "m", "runtime": "r", "url": "http://x", "api_type": "openai", "score": 1}]}})
    mp.setattr(B._registry, "flatten", lambda scan: [m for rt in scan for m in rt["models"]])
    mp.setattr(B, "_save_registry_db", lambda *a, **k: None)
    mp.setattr(B.BootLoader, "_write_artifacts", lambda self: None)
    import runtime_router
    mp.setattr(runtime_router, "health_report", lambda scan: {"healthy": ["r"], "unhealthy": []})
    return fk


_EXPECTED_STAGES = ["CONFIG", "PLUGINS", "RUNTIMES", "DRIVERS", "CAPABILITIES",
                    "HEALTH", "BENCHMARK", "REGISTRY", "POOLS", "SESSIONS", "WORKFLOW"]


def test_boot_reaches_ready_and_is_deterministic(monkeypatch):
    _patch(monkeypatch)
    r1 = B.BootLoader().boot(quick=False, warmup=False)
    r2 = B.BootLoader().boot(quick=False, warmup=False)
    assert r1["state"] == r2["state"] == "READY"
    s1 = [s["stage"] for s in r1["timeline"]]
    s2 = [s["stage"] for s in r2["timeline"]]
    assert s1 == s2 == _EXPECTED_STAGES          # deterministic, fixed order


def test_boot_event_sequence(monkeypatch):
    _patch(monkeypatch)
    loader = B.BootLoader(); loader.boot(quick=False, warmup=False)
    evs = [e["event"] for e in loader.bus.timeline()]
    assert evs[0] == "BOOT_START" and evs[-1] == "HOUSE_READY"
    for name in ["CONFIG_LOADED", "PLUGIN_DISCOVERED", "RUNTIME_DISCOVERED",
                 "BENCHMARK_COMPLETE", "POOL_READY", "HOUSE_READY"]:
        assert name in evs


def test_wizard_skips_benchmark_when_registry_and_metrics_exist(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(B, "_registry_exists", lambda: True)
    monkeypatch.setattr(B._metrics, "load_metrics", lambda *a, **k: {"m": {"ttft_s": 1}})
    res = B.BootLoader()._benchmark([{"id": "m", "roles": ["Execution"]}], quick=True)
    assert res["benchmarked"] == 0               # reused, not re-benchmarked


def test_no_hardcoded_model_names_in_boot():
    src = inspect.getsource(B)
    for banned in ("qwen", "gemma", "nemotron", "skynetclaw"):
        assert banned not in src.lower()


def test_health_monitor_start_stop(monkeypatch):
    fk = _patch(monkeypatch)
    loader = B.BootLoader(); loader.kernel = fk
    loader.start_health_monitor(interval=0.05)
    time.sleep(0.18)
    loader.stop_health_monitor()
    assert any(e["event"] == "HEALTH_TICK" for e in loader.bus.timeline())


def test_paths_relocatable_no_absolute_assumption():
    from config import paths
    d = paths.describe()
    assert d["mode"] in ("source", "portable", "installed", "exe")
    assert "user_data" in d and "runtime" in d
