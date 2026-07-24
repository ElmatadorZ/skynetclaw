"""
test_knowledge_engine.py — H3/H4/H5 + dynamics validation (model-free)
Runs against a temp house_state DB; no model, no network.
"""
from __future__ import annotations
import sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import house_state as HS
import knowledge_frontier as KF
import knowledge_asset as KA
import skill_evolution as SE
import cognitive_dynamics as CD


def _db():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(p); return p


# ── H3 KNOWLEDGE FRONTIER ────────────────────────────────────────────────────
def test_frontier_maps_uncertainty():
    p = _db()
    sid = HS.open_state("Will gold rise next week?", bootstrap=False, path=p)
    HS.add_known_fact(sid, "Gold spot is 2050 USD/oz", path=p)
    HS.add_unknown_fact(sid, "next week's CPI print is unknown", path=p)
    HS.add_blind_spot(sid, "central-bank net purchases not tracked", path=p)
    HS.add_hypothesis(sid, "a rate cut would push gold up", confidence=0.4, path=p)
    fr = KF.frontier(sid, path=p)
    assert fr["known"] and "CPI" in fr["known_unknowns"][0]
    assert fr["unknown_unknowns"], "blind spots surface as unknown-unknowns"
    assert fr["assumptions"], "low-confidence hypothesis is an assumption"
    assert fr["metrics"]["knowledge_debt"] >= 2
    print("  OK  H3 frontier maps known / known-unknowns / blind-spots / assumptions")


def test_discovery_source_routing():
    assert KF.route_source("read the config file gold.json")["source"] == "filesystem"
    assert KF.route_source("what is the latest gold price today")["source"] == "web"
    assert KF.route_source("is this note already in the vault")["source"] == "obsidian"
    assert KF.route_source("should we hedge the position")["source"] == "council"
    print("  OK  H3 routes each unknown to the fastest-reducing source")


# ── H4 KNOWLEDGE ASSET ───────────────────────────────────────────────────────
def test_asset_inference_and_delivery():
    r = KA.recommend("compare the top 3 agent frameworks", files_touched=["/out/matrix.html"])
    assert r["asset_type"] == "Comparison Matrix" and r["confidence"] >= 0.9
    assert KA.is_delivered(r, ["/out/matrix.html"]) is True
    assert KA.is_delivered(r, ["/out/notes.txt"]) is False
    r2 = KA.recommend("research the history of X")
    assert r2["asset_type"] in ("PDF Report", "Markdown Note")
    # collecting without producing the asset → NOT delivered
    assert KA.is_delivered(r2, []) is False
    print("  OK  H4 infers asset type + confidence; delivery requires the artifact")


# ── H5 SKILL EVOLUTION ───────────────────────────────────────────────────────
def test_skill_mining_from_sequences():
    runs = [
        {"id": "a", "status": "TASK_COMPLETE", "ended_at": 5,
         "sequence": ["web_search", "read_file", "extract", "summarize", "write_file"]},
        {"id": "b", "status": "TASK_COMPLETE", "ended_at": 9,
         "sequence": ["web_search", "read_file", "extract", "summarize", "write_file"]},
        {"id": "c", "status": "limit", "ended_at": 3,
         "sequence": ["list_files", "read_file"]},
    ]
    cands = SE.mine(runs)
    assert cands, "a chain recurring in 2 successful runs is a candidate"
    top = cands[0]
    assert top["usage_count"] == 2 and top["success_rate"] == 1.0
    assert top["length"] >= 3 and "→" in top["derived_workflow"]
    print(f"  OK  H5 mines candidate skill: {top['suggested_name']} ({top['derived_workflow']})")


def test_skill_requires_recurrence():
    runs = [{"id": "x", "status": "TASK_COMPLETE", "ended_at": 1,
             "sequence": ["a_tool", "b_tool", "c_tool"]}]   # appears once → not a pattern
    assert SE.mine(runs) == []
    print("  OK  H5 ignores one-off sequences (support >= 2 required)")


# ── SYSTEM DYNAMICS ──────────────────────────────────────────────────────────
def test_dynamics_stocks_flows_bottleneck():
    fm = {"known_count": 5, "knowledge_debt": 9, "assumption_load": 1, "learning_velocity": 3}
    m = CD.model(frontier_metrics=fm, run_stats={"by_status": {"TASK_COMPLETE": 4}},
                 capability=15, capability_debt=2)
    assert m["stocks"]["knowledge"] == 5 and m["stocks"]["knowledge_debt"] == 9
    assert m["bottleneck"]["constraint"] == "knowledge_debt"   # 9 dominates
    assert any(l["id"] == "R1" for l in m["loops"]) and any(l["id"] == "B1" for l in m["loops"])
    assert m["health"] in ("growing", "constrained", "warming up")
    print(f"  OK  dynamics: bottleneck={m['bottleneck']['constraint']}, health={m['health']}")


def test_no_shadow_state():
    import inspect
    for mod in (KF, KA, SE, CD):
        src = inspect.getsource(mod)
        assert "CREATE TABLE" not in src and "INSERT INTO" not in src, f"{mod.__name__} owns state"
    print("  OK  all four engines own NO new state (projections over existing sources)")


def main():
    print("=" * 56 + "\nH3/H4/H5 KNOWLEDGE & CAPABILITY ENGINES\n" + "=" * 56)
    test_frontier_maps_uncertainty()
    test_discovery_source_routing()
    test_asset_inference_and_delivery()
    test_skill_mining_from_sequences()
    test_skill_requires_recurrence()
    test_dynamics_stocks_flows_bottleneck()
    test_no_shadow_state()
    print("\n  ALL KNOWLEDGE-ENGINE TESTS PASS — collect → create → evolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
