"""
test_workflow_engine.py — OX-WORKFLOW-ENGINE-1 validation
IR/compiler (cycle detection, levels), context resolution, and every required
execution pattern: sequential, parallel, conditional, loop, nested/recursive,
pause/resume, checkpoint/rollback, plus kernel-routed LLM + events/metrics.
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
import workflow as wf
from workflow.engine import WorkflowEngine


def run(eng, defn, **kw):
    return asyncio.run(eng.run(defn, **kw))


# ── IR + compiler ─────────────────────────────────────────────────────────────
def test_parse_and_validate():
    ir = wf.parse({"id": "w", "nodes": [{"id": "a", "type": "set"}]})
    assert ir.id == "w" and len(ir.nodes) == 1
    assert wf.validate_ir(wf.parse({"id": "w", "nodes": []}))  # empty → error


def test_compiler_levels_and_topo():
    g = wf.compile(wf.parse({"id": "w", "nodes": [
        {"id": "s", "type": "set"},
        {"id": "a", "type": "set", "deps": ["s"]},
        {"id": "b", "type": "set", "deps": ["s"]},
        {"id": "m", "type": "merge", "deps": ["a", "b"]}]}))
    assert g.levels[0] == ["s"]
    assert set(g.levels[1]) == {"a", "b"}        # parallel level
    assert g.levels[2] == ["m"]
    assert g.order.index("s") < g.order.index("m")


def test_compiler_detects_cycle():
    with pytest.raises(wf.CompileError):
        wf.compile(wf.parse({"id": "w", "nodes": [
            {"id": "a", "type": "set", "deps": ["b"]},
            {"id": "b", "type": "set", "deps": ["a"]}]}))


def test_context_resolution():
    c = wf.WorkflowContext("r", inputs={"x": 5})
    c.set_output("n", {"v": 7})
    assert c.resolve("${x}") == 5                # native type preserved
    assert c.resolve("${n.v}") == 7
    assert c.resolve("val=${x}") == "val=5"      # embedded → string


# ── execution patterns ────────────────────────────────────────────────────────
def test_sequential():
    eng = WorkflowEngine()
    r = run(eng, {"id": "s", "outputs": ["d"], "nodes": [
        {"id": "a", "type": "set", "params": {"x": 5}},
        {"id": "b", "type": "python", "deps": ["a"], "params": {"expr": "x*2"}},
        {"id": "c", "type": "set", "deps": ["b"], "params": {"d": "${b.value}"}}]})
    assert r["status"] == "completed" and r["outputs"]["d"] == 10


def test_parallel_merge():
    eng = WorkflowEngine()
    r = run(eng, {"id": "p", "nodes": [
        {"id": "s", "type": "set", "params": {"n": 1}},
        {"id": "p1", "type": "python", "deps": ["s"], "params": {"expr": "n+10"}},
        {"id": "p2", "type": "python", "deps": ["s"], "params": {"expr": "n+20"}},
        {"id": "m", "type": "merge", "deps": ["p1", "p2"]}]})
    assert r["outputs"]["m"]["merged"]["p1"]["value"] == 11
    assert r["outputs"]["m"]["merged"]["p2"]["value"] == 21


def test_conditional_branch_skips_other():
    eng = WorkflowEngine()
    r = run(eng, {"id": "c", "nodes": [
        {"id": "x", "type": "set", "params": {"x": 10}},
        {"id": "c", "type": "condition", "deps": ["x"], "params": {"expr": "x>5"}},
        {"id": "hi", "type": "set", "deps": ["c"], "when": "${c.value}==True", "params": {"b": "HI"}},
        {"id": "lo", "type": "set", "deps": ["c"], "when": "${c.value}==False", "params": {"b": "LO"}}]})
    assert "hi" in r["outputs"] and "lo" not in r["outputs"]


def test_loop_map():
    eng = WorkflowEngine()
    r = run(eng, {"id": "l", "outputs": ["o"], "nodes": [
        {"id": "L", "type": "loop", "params": {"items": [1, 2, 3], "node": "python",
                                               "params": {"expr": "item*item"}}},
        {"id": "o", "type": "set", "deps": ["L"], "params": {"o": "${L.results}"}}]})
    assert [v["value"] for v in r["outputs"]["o"]] == [1, 4, 9]


def test_nested_recursive():
    eng = WorkflowEngine()
    sub = {"id": "sub", "outputs": ["v"], "nodes": [{"id": "v", "type": "python", "params": {"expr": "21*2"}}]}
    r = run(eng, {"id": "n", "nodes": [{"id": "w", "type": "workflow", "params": {"definition": sub}}]})
    assert r["outputs"]["w"]["status"] == "completed"
    assert r["outputs"]["w"]["outputs"]["v"]["value"] == 42


def test_pause_resume():
    eng = WorkflowEngine()
    defn = {"id": "ap", "nodes": [
        {"id": "a", "type": "set", "params": {"k": 1}},
        {"id": "g", "type": "approval", "deps": ["a"], "params": {"message": "ok?"}},
        {"id": "after", "type": "set", "deps": ["g"], "params": {"done": True}}]}
    r1 = run(eng, defn, run_id="rid")
    assert r1["status"] == "paused" and r1["paused_at"] == "g"
    r2 = asyncio.run(eng.resume("rid", approvals={"g": True}, definition=defn))
    assert r2["status"] == "completed" and "after" in r2["outputs"]


def test_checkpoint_and_rollback():
    eng = WorkflowEngine()
    run(eng, {"id": "cp", "nodes": [
        {"id": "a", "type": "set", "params": {"x": 1}},
        {"id": "b", "type": "set", "deps": ["a"], "params": {"y": 2}}]}, run_id="cp1")
    assert len(eng.checkpoints.history("cp1")) >= 2
    assert eng.rollback("cp1", 0)["to"] == 0


def test_retry_on_failure():
    eng = WorkflowEngine()
    r = run(eng, {"id": "rt", "nodes": [
        {"id": "bad", "type": "http", "retries": 1,
         "params": {"url": "http://127.0.0.1:9/nope", "timeout": 1}}]})
    assert r["status"] == "failed"
    assert r["metrics"]["per_node"][0]["retries"] == 1     # retried before failing


def test_llm_routes_through_kernel_no_model_name():
    class FakeKernel:
        def infer(self, **k):
            assert "required" in k and "role" in k["required"]   # capability, not model
            yield json.dumps({"type": "text", "text": "hi"})
            yield json.dumps({"type": "__tool_calls__", "calls": [{"function": {"name": "t", "arguments": {}}}]})
            yield json.dumps({"type": "done"})
        def embeddings(self, texts): return [[0.0]] * len(texts)
    eng = WorkflowEngine(runtime=FakeKernel())
    r = run(eng, {"id": "llm", "outputs": ["r"], "nodes": [
        {"id": "r", "type": "llm", "params": {"role": "Execution", "prompt": "x"}}]})
    assert r["outputs"]["r"]["text"] == "hi"
    assert r["outputs"]["r"]["tool_calls"][0]["function"]["name"] == "t"


def test_events_and_metrics_emitted():
    eng = WorkflowEngine()
    r = run(eng, {"id": "e", "nodes": [{"id": "a", "type": "set", "params": {"x": 1}}]})
    events = [h["event"] for h in r["history"]]
    assert "WorkflowStarted" in events and "NodeStarted" in events
    assert "NodeFinished" in events and "WorkflowFinished" in events
    assert r["metrics"]["nodes"] == 1


def test_registry_register_and_list():
    eng = WorkflowEngine()
    rec = eng.registry.register(wf.parse({"id": "rw", "version": "2.0.0",
                                          "nodes": [{"id": "a", "type": "set"}]}),
                                owner="me", tags=["demo"])
    assert rec["id"] == "rw" and rec["version"] == "2.0.0"
    assert any(w["id"] == "rw" for w in eng.registry.list())


def test_no_hardcoded_model_names_in_engine():
    import inspect, workflow.engine, workflow.nodes
    for mod in (workflow.engine, workflow.nodes):
        src = inspect.getsource(mod).lower()
        for banned in ("qwen", "gemma", "nemotron", "ollama", "llamacpp"):
            assert banned not in src
