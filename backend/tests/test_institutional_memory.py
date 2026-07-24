"""Test suite for THE HOUSE Institutional Memory — unit, db, integration,
routing, retrieval, and forecast-evaluation tests."""
import time, json, importlib
import pytest

import institutional_db as idb
import agent_reputation as rep
import council_memory as mem
import outcome_tracker as out
import deliberation_archive as arc
import house_constitution as con
import atlas_system_map as asm
import obsidian_knowledge_protocol as okp


# ───────────────────────── DATABASE / MIGRATIONS ─────────────────────────
def test_schema_creates_all_tables(db):
    with idb.connect(db) as c:
        names = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("council_sessions","council_contributions","deliberation_archive",
              "agent_reputation","predictions","schema_migrations"):
        assert t in names

def test_indexes_exist(db):
    with idb.connect(db) as c:
        idx = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_pred_status" in idx and "idx_sessions_ts" in idx

def test_migration_up_down(db, monkeypatch):
    import migrate
    monkeypatch.setenv("INSTITUTIONAL_DB", db)
    idb.rollback(db)                      # clean slate
    ran = migrate.up(db)
    assert any("001" in r for r in ran)
    assert 1 in migrate.applied(db)
    migrate.down("001", db)
    assert 1 not in migrate.applied(db)

def test_version_tracking(db):
    assert idb.current_version(db) == 5


# ───────────────────────── QUALITY SCORERS (unit) ─────────────────────────
def test_score_evidence_rewards_sources():
    assert rep.score_evidence("per source [1]: 64000") > rep.score_evidence("it is high")
def test_score_forecast_needs_invalidation():
    strong = rep.score_forecast("bull case if cuts; invalidation below 58k")
    weak = rep.score_forecast("it goes up")
    assert strong > weak
def test_score_critique_rewards_objection():
    assert rep.score_critique("however there is a flaw and a risk") > rep.score_critique("looks fine")
def test_scorers_clamped():
    for f in (rep.score_evidence, rep.score_critique, rep.score_forecast):
        assert 0.0 <= f("x"*5000+" source [1] invalidation risk however") <= 1.0
        assert f("") == 0.0


# ───────────────────────── REPUTATION (unit + integration) ────────────────
def test_seed_house_creates_14(db):
    rep.seed_house(db)
    assert len(rep.leaderboard(db, limit=100)) == 14

def test_apply_outcome_updates_record(db):
    rep.ensure_agent("Atlas", db)
    r = rep.apply_outcome("Atlas", "correct", path=db)
    assert r["wins"] == 1 and r["accuracy_rate"] == 1.0
    r2 = rep.apply_outcome("Atlas", "incorrect", path=db)
    assert r2["losses"] == 1 and r2["accuracy_rate"] == 0.5

def test_score_moves_with_outcome(db):
    rep.ensure_agent("Scout", db)
    base = rep.get("Scout", db)["score"]
    rep.apply_outcome("Scout", "correct", path=db)
    assert rep.get("Scout", db)["score"] > base

def test_best_and_worst(db):
    rep.seed_house(db)
    rep.apply_outcome("Atlas", "correct", path=db); rep.apply_outcome("Atlas", "correct", path=db)
    rep.apply_outcome("Skeptic", "incorrect", path=db)
    bw = rep.best_and_worst(db)
    assert bw["best"][0]["agent"] == "Atlas"


# ───────────────────────── COUNCIL MEMORY (integration) ───────────────────
def _verdict():
    return {
        "analyst": {"known": ["BTC 64000 per source [1]"], "data_gaps": ["dot plot"]},
        "strategist": {"leverage_point": "phase in"},
        "skeptic": {"verdict": "REBUILD", "reason": "liquidity thin, big risk however"},
        "forecaster": {"scenario": "bull if cuts; invalidation below 58k; uncertain"},
        "executor": {"start": "hedge"},
        "storyteller": {"hook": "the tide"},
        "aggregate_recommendation": "Phase in, hedge tail risk.",
    }

def test_from_verdict_persists_session_and_dissent(db):
    sid = mem.from_verdict("Risk-on into Q3?", _verdict(), model="t", path=db)
    s = mem.get_session(sid, db)
    assert s["verdict"].startswith("Phase in")
    assert "Skeptic" in s["participants"]
    assert "unanimous" not in s["dissent_summary"]          # R5 dissent preserved
    assert len(s["contributions"]) == 6

def test_contributions_feed_reputation(db):
    mem.from_verdict("Q", _verdict(), path=db)
    atlas = rep.get("Analyst", db)
    assert atlas["evidence_quality"] > 0

def test_recall_finds_similar(db):
    mem.from_verdict("Should we go risk-on into Q3 markets?", _verdict(), path=db)
    hits = mem.recall("risk-on Q3 market decision", path=db)
    assert hits and hits[0]["similarity"] > 0

def test_recall_empty_on_no_overlap(db):
    mem.from_verdict("apples oranges bananas", _verdict(), path=db)
    assert mem.recall("quantum chromodynamics tensor", path=db) == []

def test_stats(db):
    mem.from_verdict("Q one", _verdict(), path=db)
    st = mem.stats(db)
    assert st["sessions"] == 1 and st["sessions_with_dissent"] == 1


# ───────────────────────── FORECAST / OUTCOME EVALUATION ──────────────────
def test_record_and_due_30(db):
    pid = out.record_prediction("BTC 70k", agent="Atlas",
                                made_at=time.time()-31*out.DAY, path=db)
    due = out.due_reviews("30", path=db)
    assert any(p["id"] == pid for p in due)

def test_not_due_before_horizon(db):
    out.record_prediction("soon", agent="Atlas", made_at=time.time(), path=db)
    assert out.due_reviews("30", path=db) == []

def test_evaluate_updates_status_and_reputation(db):
    rep.ensure_agent("Atlas", db)
    pid = out.record_prediction("X", agent="Atlas",
                                made_at=time.time()-200*out.DAY, path=db)
    r = out.evaluate(pid, "180", "correct", path=db)
    assert r["result"] == "correct"
    assert out.get_prediction(pid, db)["status"] == "correct"
    assert rep.get("Atlas", db)["wins"] == 1

def test_evaluate_validates_inputs(db):
    pid = out.record_prediction("X", agent="A", path=db)
    with pytest.raises(ValueError): out.evaluate(pid, "45", "correct", path=db)
    with pytest.raises(ValueError): out.evaluate(pid, "30", "maybe", path=db)
    with pytest.raises(KeyError): out.evaluate("nope", "30", "correct", path=db)

def test_review_summary(db):
    pid = out.record_prediction("X", agent="A", made_at=time.time()-31*out.DAY, path=db)
    out.evaluate(pid, "30", "partial", path=db)
    s = out.review_summary(db)
    assert s["total"] == 1 and s["by_status"].get("partial") == 1


# ───────────────────────── ARCHIVE (integration) ─────────────────────────
def test_archive_persists_and_paths(db):
    rec = arc.archive("Q?", ["Atlas","Skeptic"], "reasoning", "verdict",
                      0.7, "BTC up", path=db)
    assert rec["date"] and rec["obsidian_path"].startswith("Council Archive/")
    got = arc.get_archive(rec["id"], db)
    assert got["agents"] == ["Atlas","Skeptic"]

def test_archive_obsidian_writer_injected(db):
    captured = {}
    def w(path, content, **k): captured["p"]=path; return {"ok": True}
    rec = arc.archive("Q?", ["Atlas"], "r", "v", 0.5, "", path=db, obsidian_writer=w)
    assert rec["obsidian_written"] is True
    assert captured["p"].startswith("Council Archive/")

def test_archive_recent_and_by_month(db):
    arc.archive("Q?", ["Atlas"], "r", "v", 0.5, "", ts=time.time(), path=db)
    assert len(arc.recent(path=db)) == 1


# ───────────────────────── CONSTITUTION (unit) ───────────────────────────
def test_constitution_has_eight_rules():
    # R8 (no invented targets / no fake tool use) joined the constitution —
    # these assertions were stale at seven and failing ever since.
    assert len(con.RULES) == 8
    assert con.load_constitution().count("R") >= 8

def test_compliance_pass_and_fail():
    good = con.check_compliance("Evidence per source [1]; uncertain assume; "
        "invalidation below 58k; however minority dissent; compared to prior session; "
        "target missing — reply BLOCKED, not executed.")
    assert good["valid"] and good["score"] == 1.0
    bad = con.check_compliance("trust me")
    assert not bad["valid"] and "R2" in bad["violations"]


# ───────────────────────── ATLAS V2 (unit) ───────────────────────────────
def test_atlas_seven_layers():
    assert len(asm.LAYERS) == 7

def test_atlas_map_structure():
    m = asm.map_system("AI energy demand and liquidity over the decade")
    for k in ("drivers","dependencies","feedback_loops","second_order","third_order"):
        assert k in m
    assert "Artificial Intelligence" in m["layers_in_scope"]
    assert asm.format_system_map(m).startswith("## ATLAS SYSTEM MAP")

def test_atlas_defaults_to_all_layers():
    m = asm.map_system("zzz nothing matches")
    assert len(m["layers_in_scope"]) == 7


# ───────────────────────── SCOUT V2 (unit) ───────────────────────────────
def test_johnny_decimal_detection():
    assert okp.is_johnny_decimal("03 · System Designs")
    assert okp.is_johnny_decimal("12.04 - Notes")
    assert not okp.is_johnny_decimal("Random Folder")

def test_scout_detects_duplicate():
    s = lambda q: {"ok": True, "hits": [{"path": "03 · System Designs/AI Energy Demand.md"}]}
    p = okp.plan_write("AI Energy Demand", "body", category="03 · System Designs", search_fn=s)
    assert p["decision"] == "append" and p["duplicates"][0]["similarity"] >= 0.6

def test_scout_new_note_requires_link():
    s = lambda q: {"ok": True, "hits": []}
    p = okp.plan_write("Totally New Topic", "body", category="03 · System Designs", search_fn=s)
    assert p["decision"] == "create"
    assert any("LINK-BEFORE-FOLDER" in w for w in p["warnings"])

def test_scout_routes_uncategorized_to_inbox():
    s = lambda q: {"ok": True, "hits": []}
    p = okp.plan_write("X", "b", search_fn=s)
    assert p["category"] == "00 · Inbox"

def test_scout_execute_plan_appends_links():
    s = lambda q: {"ok": True, "hits": []}
    p = okp.plan_write("Note A", "the body", category="03 · System Designs",
                       links=["[[MOC]]"], search_fn=s)
    captured = {}
    def w(path, content, **k): captured["c"]=content; return {"ok": True}
    r = okp.execute_plan(p, "the body", writer=w)
    assert r["ok"] and "## Links" in captured["c"]

def test_scout_record_structural_change():
    calls = {}
    def w(path, content, **k): calls["path"]=path; return {"ok": True}
    r = okp.record_structural_change("merge","03a","03 · System Designs","dedupe", writer=w)
    assert r["logged"] and "Vault Organization Log" in calls["path"]


# ───────────────────────── API / ROUTING ─────────────────────────────────
def _client(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import council_intelligence_api as api
    app = FastAPI()
    api.register(app)
    return TestClient(app)

def test_api_reputation_and_constitution(db):
    rep.seed_house(db)
    c = _client(db)
    assert c.get("/api/council/reputation").status_code == 200
    assert len(c.get("/api/council/reputation").json()["leaderboard"]) == 14
    con_r = c.get("/api/council/constitution").json()
    assert len(con_r["rules"]) == 8      # R8 joined — stale seven-rule assertion

def test_api_memory_and_recall(db):
    mem.from_verdict("Risk-on into Q3 markets?", _verdict(), path=db)
    c = _client(db)
    assert c.get("/api/council/memory/recent").json()["sessions"]
    rec = c.get("/api/council/memory/recall", params={"q": "risk-on Q3"}).json()
    assert rec["matches"]

def test_api_memory_404(db):
    c = _client(db)
    assert c.get("/api/council/memory/nope").status_code == 404

def test_api_outcomes_and_evaluate(db):
    rep.ensure_agent("Atlas", db)
    pid = out.record_prediction("X", agent="Atlas",
                                made_at=time.time()-31*out.DAY, path=db)
    c = _client(db)
    assert c.get("/api/council/outcomes/summary").json()["total"] == 1
    due = c.get("/api/council/outcomes/due/30").json()["due"]
    assert any(p["id"] == pid for p in due)
    r = c.post(f"/api/council/outcomes/{pid}/evaluate",
               json={"horizon": "30", "result": "correct"})
    assert r.status_code == 200 and r.json()["result"] == "correct"
    assert c.get("/api/council/outcomes/due/bad").status_code == 400

def test_api_learning_and_dashboard(db):
    mem.from_verdict("Q markets risk", _verdict(), path=db)
    c = _client(db)
    lr = c.get("/api/council/learning").json()
    assert "confidence_trend" in lr and "best_agents" in lr
    assert c.get("/api/council/dashboard").status_code == 200

def test_api_archive(db):
    arc.archive("Q?", ["Atlas"], "r", "v", 0.5, "", path=db)
    c = _client(db)
    assert c.get("/api/council/archive/recent").json()["archive"]


# ───────────────────────── COVERAGE CLOSERS ──────────────────────────────
def test_idb_rollback_and_version(db):
    idb.rollback(db)
    with idb.connect(db) as c:
        names = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "predictions" not in names
    idb.ensure_schema(db)
    assert idb.current_version(db) == 5

def test_constitution_header_and_rule():
    assert "HOUSE CONSTITUTION" in con.constitution_header()
    assert con.rule("R4")["name"] == "Forecasts require invalidation conditions"
    assert con.rule("ZZ") == {}

def test_archive_by_month_and_writer_raises(db):
    arc.archive("Q?", ["Atlas"], "r", "v", 0.5, "", ts=time.time(), path=db)
    import datetime
    y = datetime.datetime.utcnow().strftime("%Y"); m = datetime.datetime.utcnow().strftime("%m")
    assert len(arc.by_month(y, m, db)) == 1
    def boom(p, c, **k): raise RuntimeError("vault down")
    rec = arc.archive("Q2?", ["Atlas"], "r", "v", 0.5, "", path=db, obsidian_writer=boom)
    assert rec["obsidian_written"] is False
    assert rec["obsidian_path"].startswith("Council Archive/")   # canonical path kept

def test_scout_structural_change_writer_no_mode():
    def w(path, content): return {"ok": True}      # writer without **mode kwarg
    r = okp.record_structural_change("rename", "a", "b", "tidy", writer=w)
    assert r["logged"]

def test_scout_execute_without_links():
    p = {"target_path": "00 · Inbox/X.md", "links": []}
    def w(path, content, **k): return {"ok": True}
    assert okp.execute_plan(p, "body", writer=w)["ok"]

def test_api_best_worst_stats_memberget(db):
    rep.seed_house(db); rep.apply_outcome("Atlas", "correct", path=db)
    sid = mem.from_verdict("Q markets", _verdict(), path=db)
    c = _client(db)
    assert "best" in c.get("/api/council/reputation/best-worst").json()
    assert c.get("/api/council/memory/stats").json()["sessions"] == 1
    assert c.get(f"/api/council/memory/{sid}").json()["id"] == sid
    assert "outcomes" in c.get("/api/council/outcomes/recent").json()
