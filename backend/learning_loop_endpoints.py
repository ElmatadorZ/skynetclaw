"""
learning_loop_endpoints.py — the Mission Learning Observatory (RFC-0001)
========================================================================
Mounted at /api/learning/*. One question, one surface:

    GET /api/learning/loop        the Canonical Health API (reality_grading.vital_signs)
    GET /api/learning/dashboard   a plain vital-signs page: "is the learning loop alive?"

Discipline: the dashboard reads ONLY /api/learning/loop; no subsystem invents its own
metrics. Follows the mount(app) pattern (skill_router_endpoints) so main.py gains two
lines, not a route body.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def mount(app: FastAPI) -> None:
    @app.get("/api/learning/loop")
    def _loop() -> Dict[str, Any]:
        try:
            import reality_grading as _rg
            return {"ok": True, **_rg.vital_signs()}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.get("/api/learning/dashboard")
    def _dashboard() -> HTMLResponse:
        return HTMLResponse(_PAGE)


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Learning Observatory</title>
<style>
 body{background:#0b0e14;color:#cdd6e4;font:14px/1.5 'Segoe UI',system-ui,sans-serif;
      margin:0;padding:32px;display:flex;justify-content:center}
 .wrap{max-width:680px;width:100%}
 h1{font-size:18px;letter-spacing:.12em;color:#8ea0b8;margin:0 0 4px}
 .q{color:#5c6b80;font-size:13px;margin-bottom:20px}
 .verdict{font-size:26px;font-weight:700;padding:14px 18px;border-radius:10px;
          margin-bottom:22px;border:1px solid #223}
 .ALIVE{color:#4ade80;border-color:#14532d;background:#052e16}
 .VALIDATING{color:#a78bfa;border-color:#3b2d63;background:#1e1533}
 .AWAITING_REALITY{color:#facc15;border-color:#544512;background:#241d05}
 .WAITING_FIRST_HYPOTHESIS{color:#94a3b8;border-color:#28303c;background:#111722}
 table{width:100%;border-collapse:collapse}
 td{padding:9px 6px;border-bottom:1px solid #1a2130}
 td:last-child{text-align:right;font-variant-numeric:tabular-nums;color:#e2e8f0;font-weight:600}
 .meta{margin-top:18px;color:#48576b;font-size:12px}
 .null{color:#48576b;font-weight:400}
</style></head><body><div class="wrap">
<h1>MISSION LEARNING OBSERVATORY</h1>
<div class="q">One question: is the learning loop alive?</div>
<div id="verdict" class="verdict">loading…</div>
<table id="vitals"></table>
<div class="meta" id="meta"></div>
<script>
const ROWS=[["hypotheses_staked","Hypotheses Staked — does the system dare to predict?"],
 ["due_for_review","Due for Review — awaiting reality's judgment"],
 ["validated_episodes","Validated Episodes — knowledge that survived reality"],
 ["belief_revisions_from_reality","Belief Revisions — times reality changed our mind"],
 ["promotion_candidates","Promotion Candidates — knowledge ready to be elevated"],
 ["promotion_rate","Promotion Rate — episode → capability"],
 ["abstain_rate","Abstain Rate — how often the judge says 'unknown'"],
 ["reality_coverage","Reality Coverage — COMPLETE missions that staked a hypothesis"]];
function fmt(k,v){if(v===null||v===undefined)return '<span class="null">— no data yet</span>';
 if(k.endsWith('_rate')||k==='reality_coverage')return (100*v).toFixed(0)+'%';return v;}
async function tick(){try{
 const d=await (await fetch('/api/learning/loop')).json();
 const v=document.getElementById('verdict');
 v.textContent=(d.verdict||'UNKNOWN').replaceAll('_',' ');
 v.className='verdict '+(d.verdict||'');
 document.getElementById('vitals').innerHTML=
   ROWS.map(([k,label])=>`<tr><td>${label}</td><td>${fmt(k,d[k])}</td></tr>`).join('');
 document.getElementById('meta').textContent=
   `judge ${d.judge_version} · single observation surface: /api/learning/loop · refreshed ${new Date().toLocaleTimeString()}`;
}catch(e){document.getElementById('verdict').textContent='backend unreachable';}}
tick();setInterval(tick,60000);
</script></div></body></html>"""
