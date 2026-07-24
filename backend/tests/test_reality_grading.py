"""
test_reality_grading.py — RFC-0001 Reality Grading Loop
=======================================================
Deterministic, offline. Locks the two wires + the judge that feed the outcome clock:

  W1 a COMPLETE mission stakes exactly one observable claim (dedup; non-COMPLETE none)
  W2 the judge grades against FILESYSTEM + LEDGER reality (correct/partial/incorrect),
     abstains (None) when reality is unverifiable, and auto_judge delegates to it
     without disturbing the eval-scoreboard branch
  W3 graded-correct claims surface as Validated Episodes
  E2E a backdated claim comes due at the 7-day horizon and flows through the existing
      evaluate() pipeline (status graded, reputation applied) with no human input

    python backend/tests/test_reality_grading.py
"""
from __future__ import annotations
import json, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

import institutional_db as _db
import outcome_tracker as OT
import reality_grading as RG

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)


def _tmp_db() -> str:
    p = tempfile.mktemp(suffix=".db")
    _db.ensure_schema(p)
    return p


def _mk_workspace(files) -> str:
    ws = tempfile.mkdtemp(prefix="rg_ws_")
    for f in files:
        fp = Path(ws) / f
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("artifact", encoding="utf-8")
    return ws


def _entry(id_="m1", status="COMPLETE", files=("out.html", "report.md"), task="build dashboard"):
    return {"id": id_, "status": status, "files": list(files), "task": task}


def t1_record_claims():
    print("== W1: staking claims at sign-off ==")
    db = _tmp_db()
    ws = _mk_workspace(["out.html", "report.md"])
    pid = RG.record_mission_hypothesis(ws, _entry(), path=db)
    check("COMPLETE + artifacts → claim staked", bool(pid), str(pid))
    p = OT.get_prediction(pid, path=db)
    check("claim is observable (payload has files+workspace+ledger_id)",
          all(k in json.loads(p["predicted_outcome"]) for k in ("files", "workspace", "ledger_id")))
    check("metric routes to mission judge", p["metric"] == "mission_artifacts")
    # Learning Integrity #2 — every hypothesis references immutable evidence
    ev = json.loads(p["predicted_outcome"]).get("evidence", {})
    check("evidence snapshot: sha256 per artifact",
          set(ev.get("sha256", {}).keys()) == {"out.html", "report.md"}
          and all(len(h) == 64 for h in ev["sha256"].values()))
    check("evidence snapshot: staked_at + judge version recorded",
          ev.get("staked_at", 0) > 0 and ev.get("judge_version_at_stake") == RG.JUDGE_VERSION)
    check("duplicate claim refused (one stake per mission)",
          RG.record_mission_hypothesis(ws, _entry(), path=db) is None)
    check("INCOMPLETE stakes nothing",
          RG.record_mission_hypothesis(ws, _entry(id_="m2", status="INCOMPLETE"), path=db) is None)
    check("no artifacts stakes nothing",
          RG.record_mission_hypothesis(ws, _entry(id_="m3", files=()), path=db) is None)


def t2_judge_reality():
    print("== W2: the judge reads reality, not the model ==")
    db = _tmp_db()
    ws = _mk_workspace(["a.txt", "b.txt"])
    pid = RG.record_mission_hypothesis(ws, _entry(files=("a.txt", "b.txt")), path=db)
    pred = OT.get_prediction(pid, path=db)
    check("all artifacts exist → correct", RG.judge_mission_hypothesis(pred) == "correct")
    (Path(ws) / "b.txt").unlink()
    check("one missing → partial", RG.judge_mission_hypothesis(pred) == "partial")
    (Path(ws) / "a.txt").unlink()
    check("all missing → incorrect", RG.judge_mission_hypothesis(pred) == "incorrect")
    # ledger overturn: entry now says PROBLEM → incorrect even if files exist
    ws2 = _mk_workspace(["x.txt"])
    (Path(ws2) / "_MISSION_LEDGER.json").write_text(
        json.dumps({"missions": [{"id": "m9", "status": "PROBLEM"}]}), encoding="utf-8")
    pid2 = RG.record_mission_hypothesis(
        ws2, _entry(id_="m9", files=("x.txt",), task="overturn case"), path=db)
    pred2 = OT.get_prediction(pid2, path=db)
    check("distinct task → distinct claim staked", pred2 is not None)
    check("ledger overturned → incorrect", RG.judge_mission_hypothesis(pred2) == "incorrect")
    # unverifiable: workspace gone → abstain, never guess
    import shutil; shutil.rmtree(ws2, ignore_errors=True)
    check("workspace gone → None (abstain for human)",
          RG.judge_mission_hypothesis(pred2) is None)


def t3_auto_judge_delegation():
    print("== W2: auto_judge delegation (eval branch untouched) ==")
    db = _tmp_db()
    ws = _mk_workspace(["ok.txt"])
    pid = RG.record_mission_hypothesis(ws, _entry(id_="m5", files=("ok.txt",)), path=db)
    pred = OT.get_prediction(pid, path=db)
    check("auto_judge routes mission claims to the reality judge",
          OT.auto_judge(pred) == "correct")
    check("unrelated metric still unjudged", OT.auto_judge({"metric": "revenue"}) is None)
    check("eval branch behavior unchanged",
          OT.auto_judge({"metric": "eval score", "direction": "up"},
                        eval_trend={"latest": 0.95}) == "correct")


def t4_end_to_end_clock():
    print("== E2E: backdated claim → due at 7d → graded → Validated Episode ==")
    db = _tmp_db()
    ws = _mk_workspace(["done.txt"])
    made = time.time() - 8 * OT.DAY          # staked 8 days ago → 7d review is due
    pid = OT.record_prediction(
        statement="Mission hypothesis: outcome COMPLETE will hold — e2e", agent="mission_operative",
        session_id="", predicted_outcome=json.dumps(
            {"files": ["done.txt"], "workspace": ws, "ledger_id": "m7"}),
        confidence=0.75, made_at=made, metric="mission_artifacts", direction="hold",
        extracted_from="mission_ledger", evidence_source=ws, path=db)
    due = OT.due_reviews("7", path=db)
    check("claim is due at the 7-day horizon", any(d["id"] == pid for d in due))
    verdict = OT.auto_judge(next(d for d in due if d["id"] == pid))
    check("clock can grade it with zero human input", verdict == "correct")
    res = OT.evaluate(pid, "7", verdict, path=db)
    check("evaluate() pipeline runs (reputation attributed)",
          "mission_operative" in res["attributed_to"])
    check("prediction leaves pending", OT.get_prediction(pid, path=db)["status"] == "correct")
    vs = RG.validated_sessions(path=db)
    check("Validated Episode surfaced (W3)", any(v["id"] == pid for v in vs))
    check("Validated Episode carries its evidence payload (Integrity #2 shape)",
          all("evidence" in v for v in vs))
    summ = RG.loop_summary(path=db)
    check("loop_summary shows the graded claim",
          summ["mission_hypotheses"].get("correct", 0) >= 1
          and summ["validated_episodes"] >= 1, str(summ))


def t5_vital_signs():
    print("== Observatory: canonical health API ==")
    db = _tmp_db()
    vs0 = RG.vital_signs(path=db)
    check("empty loop → WAITING_FIRST_HYPOTHESIS", vs0["verdict"] == "WAITING_FIRST_HYPOTHESIS")
    ws = _mk_workspace(["vs.txt"])
    RG.record_mission_hypothesis(ws, _entry(id_="v1", files=("vs.txt",), task="vitals"), path=db)
    vs1 = RG.vital_signs(path=db)
    check("staked → AWAITING_REALITY", vs1["verdict"] == "AWAITING_REALITY"
          and vs1["hypotheses_staked"] == 1)
    # grade one via the full pipeline → VALIDATING (belief revision needs a council session)
    made = time.time() - 8 * OT.DAY
    pid = OT.record_prediction(
        statement="Mission hypothesis: outcome COMPLETE will hold — vitals2",
        agent="mission_operative", session_id="", predicted_outcome=json.dumps(
            {"files": ["vs.txt"], "workspace": ws, "ledger_id": "v2"}),
        confidence=0.75, made_at=made, metric="mission_artifacts", direction="hold",
        extracted_from="mission_ledger", evidence_source=ws, path=db)
    OT.evaluate(pid, "7", OT.auto_judge(OT.get_prediction(pid, path=db)), path=db)
    vs2 = RG.vital_signs(path=db)
    check("validated episode moves the verdict", vs2["verdict"] in ("VALIDATING", "ALIVE")
          and vs2["validated_episodes"] >= 1, vs2["verdict"])
    check("all 8 vital signs present",
          all(k in vs2 for k in ("hypotheses_staked", "due_for_review", "validated_episodes",
                                 "belief_revisions_from_reality", "promotion_candidates",
                                 "promotion_rate", "abstain_rate", "reality_coverage")))
    check("no-data metrics are honest None, not fake zeros",
          vs0["abstain_rate"] is None and vs0["reality_coverage"] is None)


def t6_observatory_endpoints():
    print("== Observatory: /api/learning endpoints ==")
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import learning_loop_endpoints as LLE
    except Exception as e:
        check("fastapi available for endpoint test", False, str(e)); return
    app = FastAPI(); LLE.mount(app)
    client = TestClient(app)
    r = client.get("/api/learning/loop")
    check("/api/learning/loop responds", r.status_code == 200 and r.json().get("ok") is True)
    check("loop payload carries verdict + judge version",
          "verdict" in r.json() and r.json().get("judge_version") == RG.JUDGE_VERSION)
    d = client.get("/api/learning/dashboard")
    check("/api/learning/dashboard serves the page",
          d.status_code == 200 and "MISSION LEARNING OBSERVATORY" in d.text)
    check("dashboard reads ONLY the canonical surface",
          "/api/learning/loop" in d.text and "loop_summary" not in d.text)


def main():
    for fn in (t1_record_claims, t2_judge_reality, t3_auto_judge_delegation,
               t4_end_to_end_clock, t5_vital_signs, t6_observatory_endpoints):
        try: fn()
        except Exception as e:
            check(fn.__name__, False, f"harness error: {type(e).__name__}: {e}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1


def test_reality_grading():
    assert main() == 0

if __name__ == "__main__":
    raise SystemExit(main())
