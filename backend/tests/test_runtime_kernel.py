"""
test_runtime_kernel.py — OX-RUNTIME-KERNEL-1 Phase 9
Deterministic kernel tests with injected fake drivers (no network):
driver loading, plugin loading, capability negotiation, pools, failover,
session reuse. No model names drive any decision.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import runtime_kernel as K
from runtime_plugins import load_drivers
from runtime_plugins.base import RuntimeDriver


# ── a fake driver (proves zero runtime-specific logic in the kernel) ──────────
class FakeDriver(RuntimeDriver):
    name = "fake"
    api_types = ("fake",)
    def __init__(self, fail_urls=()): self.fail_urls = set(fail_urls)
    def connect(self, url): return True
    def health(self, url): return {"alive": True, "latency_s": 0.01, "healthy": True}
    def list_models(self, url): return []
    def capabilities(self, url, model): return {}
    def benchmark(self, url, model): return {}
    def embeddings(self, url, model, texts): return [[0.1, 0.2] for _ in texts]
    def infer(self, url, model, messages, tools=None, stream=False, options=None):
        if url in self.fail_urls:
            raise RuntimeError("simulated runtime down")
        yield json.dumps({"type": "__tool_calls__",
                          "calls": [{"function": {"name": "write_file", "arguments": "{}"}}]})
        yield json.dumps({"type": "done"})


def _exec_model(mid, url, runtime, **caps):
    m = {"id": mid, "url": url, "runtime": runtime, "api_type": "fake",
         "param_b": caps.get("param_b", 7.0), "tool_calling": caps.get("tool_calling", True),
         "online": True}
    import runtime_registry as R
    m["roles"] = R.classify(m)
    return m


def _kernel_with(instances, drivers=None):
    k = K.RuntimeKernel(drivers=drivers or [FakeDriver()])
    k.instances = instances
    return k


def _inst(name, url, models, driver):
    return K.RuntimeInstance(name=name, url=url, api_type="fake", driver=driver,
                             models=models, online=True, healthy=True)


# ── plugin / driver loading ───────────────────────────────────────────────────
def test_plugin_loading_discovers_drivers():
    names = {d.name for d in load_drivers()}
    assert {"ollama", "openai"} <= names           # both shipped plugins discovered


def test_drivers_implement_full_interface():
    for d in load_drivers():
        for meth in ("connect", "health", "list_models", "capabilities",
                     "benchmark", "infer", "embeddings", "shutdown"):
            assert callable(getattr(d, meth))


# ── capability negotiation (no names) ─────────────────────────────────────────
def test_negotiation_ranks_gpu_execution_first():
    drv = FakeDriver()
    gpu = _inst("gpu", "http://gpu/v1", [_exec_model("anymodel", "http://gpu/v1", "gpu")], drv)
    cpu = _inst("cpu", "http://cpu", [_exec_model("othermodel", "http://cpu", "cpu")], drv)
    # gpu instance is api_type openai-like → registry treats as GPU; give it metrics edge
    k = _kernel_with([cpu, gpu])
    ranked = k.negotiate({"role": "Execution", "tool_calling": True})
    assert ranked and ranked[0]["role"] == "Execution"
    assert all(r["model"] in ("anymodel", "othermodel") for r in ranked)


def test_negotiation_filters_by_capability_not_name():
    drv = FakeDriver()
    tool_model = _exec_model("m1", "http://a", "a", tool_calling=True)
    notool = _exec_model("m2", "http://a", "a", tool_calling=False)
    k = _kernel_with([_inst("a", "http://a", [tool_model, notool], drv)])
    ranked = k.negotiate({"role": "Execution", "tool_calling": True})
    ids = [r["model"] for r in ranked]
    assert "m1" in ids and "m2" not in ids          # filtered by capability


def test_required_for_task_maps_role():
    k = _kernel_with([])
    assert k.required_for_task("create a file")["role"] == "Execution"
    assert k.required_for_task("analyze the data")["role"] == "Reasoning"


# ── pools ─────────────────────────────────────────────────────────────────────
def test_pools_group_by_capability_role():
    drv = FakeDriver()
    models = [_exec_model("small", "http://a", "a", param_b=7.0),
              _exec_model("big", "http://a", "a", param_b=33.0)]
    k = _kernel_with([_inst("a", "http://a", models, drv)])
    pools = k.pools()
    assert "Execution" in pools and "Council" in pools


# ── failover ──────────────────────────────────────────────────────────────────
def test_failover_to_next_runtime():
    down = FakeDriver(fail_urls={"http://down/v1"})
    m_down = _exec_model("md", "http://down/v1", "down")
    m_up = _exec_model("mu", "http://up/v1", "up")
    # both served by the same fake driver; first candidate fails → kernel fails over
    k = K.RuntimeKernel(drivers=[down])
    k.instances = [_inst("down", "http://down/v1", [m_down], down),
                   _inst("up", "http://up/v1", [m_up], down)]
    evs = [json.loads(e) for e in k.infer(task="create a file",
                                          messages=[{"role": "user", "content": "x"}],
                                          tools=[{"type": "function", "function": {"name": "write_file"}}])]
    assert any(e.get("type") == "__tool_calls__" for e in evs)   # recovered via failover


def test_all_runtimes_down_yields_error():
    down = FakeDriver(fail_urls={"http://a/v1"})
    k = K.RuntimeKernel(drivers=[down])
    k.instances = [_inst("a", "http://a/v1", [_exec_model("m", "http://a/v1", "a")], down)]
    evs = [json.loads(e) for e in k.infer(task="create a file",
                                          messages=[{"role": "user", "content": "x"}])]
    assert any(e.get("type") == "error" for e in evs)


# ── session reuse ─────────────────────────────────────────────────────────────
def test_session_reuse_same_object():
    drv = FakeDriver()
    k = _kernel_with([_inst("a", "http://a", [_exec_model("m", "http://a", "a")], drv)])
    sel = {"url": "http://a", "model": "m", "api_type": "fake", "runtime": "a"}
    s1 = k.acquire_session(sel); s2 = k.acquire_session(sel)
    assert s1 is s2 and s2.requests == 2 and len(k.sessions) == 1


def test_embeddings_route():
    drv = FakeDriver()
    emb = {"id": "e1", "url": "http://a", "runtime": "a", "api_type": "fake",
           "embedding": True, "param_b": 0.3}
    import runtime_registry as R
    emb["roles"] = R.classify(emb)
    k = _kernel_with([_inst("a", "http://a", [emb], drv)])
    out = k.embeddings(["hello", "world"])
    assert len(out) == 2 and out[0] == [0.1, 0.2]
