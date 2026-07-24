"""
skynet_genesis_masterpiece.py
=============================
SKYNETCLAW MASTERPIECE — Unified Cognitive Runtime
By ElmatadorZ (Bunyawat Dechanon) — Apache-2.0

This is the master runtime referenced in the elmatadorz-secret-os SKILL.
It does NOT replace /api/chat or /api/agent/run — it adds a single
new endpoint that runs the full Genesis Mind L0→L8 pipeline:

    POST /api/masterpiece/run     — SSE streaming, layer-by-layer
    GET  /api/masterpiece/status  — full system health snapshot
    GET  /api/masterpiece/identity — WillCore identity seed
    POST /api/masterpiece/critique — run Shadow Gate on arbitrary text

Pipeline (per ElmatadorZ Secret OS v1.0):
    INPUT
      ↓
    [L0 REALITY ANCHOR]   Known / Inferred / Unknown          (skynetclaw_meta)
      ↓
    [L1 WILL]             Identity + tone + risk policy        (skynetclaw_will)
      ↓
    [L7 GENOME RETRIEVAL] Past patterns + failures             (skynetclaw_meta)
      ↓
    [ROUTER]              Pick model by intent                 (skynetclaw_router)
      ↓
    [L4 SHADOW GATE]      Pre-exec critique on every tool call (skynetclaw_meta + will)
      ↓
    [EXEC]                Existing agent_run loop OR direct
      ↓
    [L8 SYNTHESIS]        Hook + Frame + Moves + Confidence    (this file)
      ↓
    [GENOME UPDATE]       Extract rules / failures             (skynetclaw_meta)
      ↓
    [AUDIT TRAIL]         Hash-chained log                     (skynetclaw_meta)

Wire-up (one block in main.py):

    from skynet_genesis_masterpiece import register_masterpiece
    register_masterpiece(app)

That's it. Three /api/masterpiece/* endpoints become available, plus a
GET /api/masterpiece/dashboard.json that the live dashboard polls.
"""
from __future__ import annotations

import json
import time
import asyncio
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Sibling modules — all live in the same backend/ directory
from skynetclaw_meta import (
    MetaSession, GateVerdict,
    meta_init, reality_anchor, retrieve_genome_hints,
    shadow_gate, deposit_memory, extract_rules,
    audit_log, format_meta_preamble,
    GENOME_PATH, AUDIT_PATH, MEMORY_PATH, _load_genome,
)
from skynetclaw_router import (
    resolve_model, classify_intent, preview_routing, _load_roster,
    ROUTER_AUDIT_PATH,
)
from skynetclaw_will import (
    identity_seed, tone_filter, risk_classify, RiskAssessment,
)

_BASE = Path(__file__).parent
MASTERPIECE_VERSION = "1.0.0"


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline stages — pure functions; the route handler streams them
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class StageResult:
    layer: str
    label: str
    elapsed_ms: int
    payload: Dict[str, Any] = field(default_factory=dict)
    verdict: str = "ok"   # ok | warn | block
    note: str = ""


@dataclass
class MasterpieceContext:
    """In-memory state for one /api/masterpiece/run invocation."""
    task: str
    session_id: str
    started_at: float
    meta: MetaSession
    risk_summary: Dict[str, int] = field(default_factory=lambda: {"SAFE":0,"MEDIUM":0,"IRREVERSIBLE":0})
    blocked_calls: List[Dict[str, Any]] = field(default_factory=list)
    confirmed_calls: List[Dict[str, Any]] = field(default_factory=list)
    chosen_role: str = ""
    chosen_model: str = ""
    stages: List[StageResult] = field(default_factory=list)


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── L0: Reality Anchor ───────────────────────────────────────────────────────
def stage_l0(ctx: MasterpieceContext) -> StageResult:
    t0 = _now_ms()
    a = reality_anchor(ctx.task)
    return StageResult(
        layer="L0",
        label="Reality Anchor",
        elapsed_ms=_now_ms() - t0,
        payload={
            "Known": a.get("Known", []),
            "Inferred": a.get("Inferred", []),
            "Unknown": a.get("Unknown", []),
        },
        note=f"{len(a.get('Known',[]))} known / {len(a.get('Inferred',[]))} inferred / {len(a.get('Unknown',[]))} unknown",
    )


# ── L1: Will (identity + tone) ───────────────────────────────────────────────
def stage_l1(ctx: MasterpieceContext) -> StageResult:
    t0 = _now_ms()
    seed = identity_seed()
    softened, changes = tone_filter(ctx.task)
    return StageResult(
        layer="L1",
        label="WillCore",
        elapsed_ms=_now_ms() - t0,
        payload={
            "identity_preview": seed.splitlines()[0],
            "task_softened": softened if changes else None,
            "tone_changes": changes,
        },
        note="identity anchored" + (f"; {len(changes)} overclaim softened" if changes else ""),
    )


# ── L7: Genome retrieval ─────────────────────────────────────────────────────
def stage_l7_pre(ctx: MasterpieceContext) -> StageResult:
    t0 = _now_ms()
    hints = retrieve_genome_hints(ctx.task)
    return StageResult(
        layer="L7",
        label="Genome Retrieval",
        elapsed_ms=_now_ms() - t0,
        payload={"hints": hints},
        note=f"{len(hints)} hint(s) recalled",
    )


# ── Router: pick model ───────────────────────────────────────────────────────
def stage_router(ctx: MasterpieceContext, requested: Optional[str]) -> StageResult:
    t0 = _now_ms()
    role = classify_intent(ctx.task)
    model = resolve_model(requested or "@auto", ctx.task)
    ctx.chosen_role = role
    ctx.chosen_model = model
    return StageResult(
        layer="ROUTER",
        label="Multi-Model Router",
        elapsed_ms=_now_ms() - t0,
        payload={"requested": requested or "@auto", "role": role, "model": model},
        note=f"role={role} → model={model or '(unset)'}",
        verdict="warn" if not model else "ok",
    )


# ── L4: Shadow Gate dry-run on a hypothetical tool call ──────────────────────
def stage_l4_dryrun(ctx: MasterpieceContext, tool_calls: List[Dict[str, Any]]) -> StageResult:
    """
    Pre-flight Shadow Gate over a list of (hypothetical or real) tool calls.
    Returns aggregated verdicts. Does NOT execute anything.
    """
    t0 = _now_ms()
    results = []
    for tc in tool_calls:
        name = tc.get("name") or tc.get("function", {}).get("name", "")
        args = tc.get("args") or tc.get("function", {}).get("arguments", {})
        v = shadow_gate(name, args, [], session_id=ctx.session_id)
        risk = risk_classify(name, args)
        ctx.risk_summary[risk.level] = ctx.risk_summary.get(risk.level, 0) + 1
        if v.action == "BLOCK":
            ctx.blocked_calls.append({"tool": name, "args": args, "reason": v.reason})
        elif risk.require_confirm:
            ctx.confirmed_calls.append({"tool": name, "args": args, "reason": risk.reason})
        results.append({
            "tool": name,
            "verdict": v.verdict,
            "action": v.action,
            "risk": risk.level,
            "require_confirm": risk.require_confirm,
            "reason": v.reason or risk.reason,
        })
    blocked_ct = sum(1 for r in results if r["action"] == "BLOCK")
    overall = "block" if blocked_ct else ("warn" if ctx.confirmed_calls else "ok")
    return StageResult(
        layer="L4",
        label="Shadow Gate (dry-run)",
        elapsed_ms=_now_ms() - t0,
        payload={"per_tool": results, "blocked_count": blocked_ct,
                 "confirm_required_count": len(ctx.confirmed_calls)},
        verdict=overall,
        note=f"{len(results)} call(s) inspected · {blocked_ct} blocked · {len(ctx.confirmed_calls)} need confirm",
    )


# ── L8: Synthesis (Money Atlas brief) ────────────────────────────────────────
def stage_l8(ctx: MasterpieceContext) -> StageResult:
    t0 = _now_ms()
    a = ctx.meta.anchor
    hook = _generate_hook(ctx)
    frame = _generate_frame(ctx)
    moves = _generate_moves(ctx)
    confidence = _calc_confidence(ctx)
    brief = {
        "hook": hook,
        "frame": frame,
        "moves": moves,
        "close": "Compounding > one-shot. Each run deposits to Genome. — SkynetClaw Masterpiece",
        "confidence_field": {
            "confidence": confidence,
            "shadow_verdict": _aggregate_verdict(ctx),
            "unknowns": a.get("Unknown", []),
            "failure_conditions": _failure_conditions(ctx),
            "audit_hash_tail": _last_audit_hash(),
        },
    }
    return StageResult(
        layer="L8",
        label="Synthesis (Money Atlas tone)",
        elapsed_ms=_now_ms() - t0,
        payload=brief,
        note=f"confidence {int(confidence*100)}% · verdict {brief['confidence_field']['shadow_verdict']}",
    )


def _generate_hook(ctx: MasterpieceContext) -> str:
    if ctx.blocked_calls:
        return f"{len(ctx.blocked_calls)} tool call(s) blocked by Shadow Gate — pipeline halted before damage."
    if ctx.confirmed_calls:
        return f"{len(ctx.confirmed_calls)} irreversible action(s) staged — awaiting your call."
    if not ctx.chosen_model:
        return "Router has no model assigned — Multi-Model Setup is the first move."
    return f"Routed to {ctx.chosen_role} ({ctx.chosen_model}) — pipeline ready to execute."


def _generate_frame(ctx: MasterpieceContext) -> str:
    a = ctx.meta.anchor
    bits = [
        f"Task anchored: {len(a.get('Known',[]))} concrete entities, "
        f"{len(a.get('Inferred',[]))} inferred intents, "
        f"{len(a.get('Unknown',[]))} vague references."
    ]
    if ctx.meta.hints:
        bits.append(f"Genome recalled {len(ctx.meta.hints)} pattern(s) from past sessions.")
    if ctx.risk_summary.get("IRREVERSIBLE", 0):
        bits.append(f"{ctx.risk_summary['IRREVERSIBLE']} irreversible call(s) flagged.")
    return " ".join(bits)


def _generate_moves(ctx: MasterpieceContext) -> List[Dict[str, str]]:
    moves = []
    if not ctx.chosen_model:
        moves.append({
            "n": "1",
            "action": "Open Multi-Model Setup → assign at least one model to the workhorse role",
            "why": "router currently returns empty model name",
            "exit": "model name appears in the next preview",
        })
    if ctx.blocked_calls:
        moves.append({
            "n": str(len(moves) + 1),
            "action": f"Review blocked calls: {ctx.blocked_calls[0]['tool']}",
            "why": "Shadow Gate flagged irreversible/denylist match",
            "exit": "rewrite the call OR override via /api/masterpiece/run?override=true",
        })
    if ctx.confirmed_calls:
        moves.append({
            "n": str(len(moves) + 1),
            "action": f"Confirm or reject {len(ctx.confirmed_calls)} staged action(s)",
            "why": "WillCore risk policy requires human approval for IRREVERSIBLE",
            "exit": "POST /api/masterpiece/confirm with the call IDs",
        })
    a = ctx.meta.anchor
    if any("vague" in u or "the file" in u for u in a.get("Unknown", [])):
        moves.append({
            "n": str(len(moves) + 1),
            "action": "Resolve vague references in task before execution",
            "why": "L0 Reality Anchor flagged unknowns",
            "exit": "task references concrete paths/entities",
        })
    if not moves:
        moves.append({
            "n": "1",
            "action": "Forward the resolved plan to /api/agent/run with the chosen model",
            "why": "all gates passed — ready to execute",
            "exit": "TASK_COMPLETE event from agent loop",
        })
    return moves


def _calc_confidence(ctx: MasterpieceContext) -> float:
    base = 0.85
    if ctx.blocked_calls:
        base -= 0.30
    if ctx.confirmed_calls:
        base -= 0.05 * len(ctx.confirmed_calls)
    if not ctx.chosen_model:
        base -= 0.20
    a = ctx.meta.anchor
    if len(a.get("Unknown", [])) > 1 and "(no vague" not in (a.get("Unknown", [""])[0] or ""):
        base -= 0.10
    return max(0.10, min(0.95, base))


def _aggregate_verdict(ctx: MasterpieceContext) -> str:
    if ctx.blocked_calls:
        return "REBUILD"
    if ctx.confirmed_calls or not ctx.chosen_model:
        return "FRAGILE"
    return "CONSISTENT"


def _failure_conditions(ctx: MasterpieceContext) -> List[str]:
    out = []
    if not ctx.chosen_model:
        out.append("router roster empty — execution will fail")
    if ctx.blocked_calls:
        out.append(f"any of {len(ctx.blocked_calls)} blocked calls overridden without manual review")
    if not ctx.meta.hints:
        out.append("no Genome hints — first time seeing this task pattern")
    return out or ["none flagged"]


def _last_audit_hash() -> str:
    if not AUDIT_PATH.exists():
        return "GENESIS"
    try:
        with AUDIT_PATH.open("rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 2048))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
        for line in reversed(tail):
            if line.strip():
                return json.loads(line).get("hash", "GENESIS")
    except Exception:
        pass
    return "GENESIS"


# ──────────────────────────────────────────────────────────────────────────────
# System status — for the dashboard
# ──────────────────────────────────────────────────────────────────────────────
def system_status() -> Dict[str, Any]:
    """Snapshot of every Masterpiece subsystem. Cheap to call (file stats only)."""
    g = _load_genome()
    roster = _load_roster()
    return {
        "version": MASTERPIECE_VERSION,
        "generated_at": int(time.time()),
        "subsystems": {
            "meta": {
                "audit_trail_exists": AUDIT_PATH.exists(),
                "audit_size_bytes": AUDIT_PATH.stat().st_size if AUDIT_PATH.exists() else 0,
                "echo_memory_size_bytes": MEMORY_PATH.stat().st_size if MEMORY_PATH.exists() else 0,
                "last_audit_hash": _last_audit_hash(),
            },
            "genome": {
                "version": g.get("version", 1),
                "updated_at": g.get("updated_at", 0),
                "strategy_rules_count": len(g.get("strategy_rules", [])),
                "execution_paths_count": len(g.get("execution_paths", [])),
                "failure_map_count": len(g.get("failure_map", [])),
            },
            "router": {
                "enabled": roster.get("enabled", True),
                "roles": {
                    name: {"model": cfg.get("model", ""), "fallback": cfg.get("fallback", "")}
                    for name, cfg in roster.get("roles", {}).items()
                },
                "rules_count": len(roster.get("rules", [])),
                "audit_size_bytes": ROUTER_AUDIT_PATH.stat().st_size if ROUTER_AUDIT_PATH.exists() else 0,
            },
            "will": {
                "identity_loaded": True,
                "tone_filter_active": True,
            },
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI integration
# ──────────────────────────────────────────────────────────────────────────────
class MasterpieceRunReq(BaseModel):
    task: str
    requested_model: Optional[str] = "@auto"
    # Optional dry-run tool call list for the L4 stage to inspect
    proposed_tool_calls: Optional[List[Dict[str, Any]]] = None
    override_blocks: bool = False


class CritiqueReq(BaseModel):
    text: str
    context: Optional[str] = ""


def register_masterpiece(app):
    """Call once from main.py: register_masterpiece(app)."""

    @app.get("/api/masterpiece/identity")
    async def mp_identity():
        return {"identity": identity_seed(), "version": MASTERPIECE_VERSION}

    @app.get("/api/masterpiece/status")
    async def mp_status():
        return system_status()

    @app.get("/api/masterpiece/dashboard.json")
    async def mp_dashboard():
        """Combined snapshot for the live dashboard artifact (one call)."""
        s = system_status()
        # tail of router audit
        router_tail = []
        if ROUTER_AUDIT_PATH.exists():
            try:
                lines = ROUTER_AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()
                router_tail = [json.loads(l) for l in lines[-12:]]
            except Exception:
                pass
        # tail of audit trail
        audit_tail = []
        if AUDIT_PATH.exists():
            try:
                lines = AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()
                audit_tail = [json.loads(l) for l in lines[-12:]]
            except Exception:
                pass
        # genome highlights
        g = _load_genome()
        return {
            **s,
            "router_audit_tail": router_tail,
            "audit_tail": audit_tail,
            "genome_recent_failures": (g.get("failure_map") or [])[-5:],
            "genome_recent_paths": (g.get("execution_paths") or [])[-5:],
        }

    @app.post("/api/masterpiece/critique")
    async def mp_critique(req: CritiqueReq):
        """Run Shadow Gate-style critique on arbitrary text (no exec)."""
        anchor = reality_anchor(req.text)
        softened, changes = tone_filter(req.text)
        hints = retrieve_genome_hints(req.text)
        return {
            "anchor": anchor,
            "tone_changes": changes,
            "softened": softened if changes else None,
            "genome_hints": hints,
        }

    @app.post("/api/masterpiece/run")
    async def mp_run(req: MasterpieceRunReq):
        """
        Run the full L0 → L8 pipeline as an SSE stream.
        Each stage emits an event. Does NOT execute tool calls — it stages
        them and returns the synthesis brief. Use /api/agent/run for actual exec.
        """
        async def gen():
            # Init
            meta = meta_init(req.task)
            ctx = MasterpieceContext(
                task=req.task,
                session_id=meta.session_id,
                started_at=time.time(),
                meta=meta,
            )
            yield _sse("masterpiece_start", {
                "session": meta.session_id,
                "task_preview": req.task[:200],
                "version": MASTERPIECE_VERSION,
            })

            # L0
            r = stage_l0(ctx); ctx.stages.append(r)
            yield _sse("stage", asdict(r))

            # L1
            r = stage_l1(ctx); ctx.stages.append(r)
            yield _sse("stage", asdict(r))

            # L7 retrieval
            r = stage_l7_pre(ctx); ctx.stages.append(r)
            yield _sse("stage", asdict(r))

            # Router
            r = stage_router(ctx, req.requested_model); ctx.stages.append(r)
            yield _sse("stage", asdict(r))

            # L4 dry-run on proposed tool calls (if any)
            if req.proposed_tool_calls:
                r = stage_l4_dryrun(ctx, req.proposed_tool_calls)
                ctx.stages.append(r)
                yield _sse("stage", asdict(r))

            # L8 synthesis
            r = stage_l8(ctx); ctx.stages.append(r)
            yield _sse("stage", asdict(r))

            # Final
            audit_log("masterpiece.run", {
                "session": ctx.session_id,
                "blocked": len(ctx.blocked_calls),
                "confirm_pending": len(ctx.confirmed_calls),
                "chosen_role": ctx.chosen_role,
                "chosen_model": ctx.chosen_model,
                "stages": [s.layer for s in ctx.stages],
            })
            yield _sse("masterpiece_complete", {
                "session": ctx.session_id,
                "total_ms": sum(s.elapsed_ms for s in ctx.stages),
                "verdict": _aggregate_verdict(ctx),
                "confidence": _calc_confidence(ctx),
            })
            yield _sse("done", {})

        return StreamingResponse(gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        })


def _sse(event_type: str, payload: Dict[str, Any]) -> str:
    body = {"type": event_type, **payload}
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"


# ──────────────────────────────────────────────────────────────────────────────
# Self-test (no FastAPI) — runs full pipeline against a sample task
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=== SkynetClaw Masterpiece self-test ===\n")

    sample_task = 'รัน python script สร้าง Telegram Bot ที่ "D:\\Skynet_Bridge" ส่งราคาทอง ทุก 5 นาที'

    meta = meta_init(sample_task)
    ctx = MasterpieceContext(
        task=sample_task,
        session_id=meta.session_id,
        started_at=time.time(),
        meta=meta,
    )

    for stage_fn, label in [
        (stage_l0,     "L0 Reality Anchor"),
        (stage_l1,     "L1 WillCore"),
        (stage_l7_pre, "L7 Genome Retrieval"),
    ]:
        r = stage_fn(ctx); ctx.stages.append(r)
        print(f"[{r.layer}] {r.label}  ({r.elapsed_ms}ms)")
        print(f"    note: {r.note}")
        if r.payload:
            for k, v in list(r.payload.items())[:3]:
                preview = str(v)[:120]
                print(f"    {k}: {preview}")
        print()

    r = stage_router(ctx, "@auto"); ctx.stages.append(r)
    print(f"[ROUTER] {r.note}\n")

    proposed = [
        {"name": "create_folder", "args": {"path": "D:\\Skynet_Bridge"}},
        {"name": "write_file",    "args": {"path": "D:\\Skynet_Bridge\\bot.py", "content": "..."}},
        {"name": "shell_command", "args": {"command": "rm -rf D:\\"}},
        {"name": "telegram_send", "args": {"message": "test"}},
    ]
    r = stage_l4_dryrun(ctx, proposed); ctx.stages.append(r)
    print(f"[L4] {r.note} → verdict={r.verdict}")
    for item in r.payload["per_tool"]:
        print(f"    {item['tool']:18s} {item['risk']:13s} {item['action']:8s} — {item['reason'][:60]}")
    print()

    r = stage_l8(ctx); ctx.stages.append(r)
    p = r.payload
    print("=== L8 SYNTHESIS ===")
    print(f"HOOK : {p['hook']}")
    print(f"FRAME: {p['frame']}")
    print("MOVES:")
    for m in p["moves"]:
        print(f"  [{m['n']}] {m['action']}")
        print(f"      why: {m['why']}")
    print(f"CLOSE: {p['close']}")
    cf = p["confidence_field"]
    print(f"\nCONFIDENCE   : {int(cf['confidence']*100)}%")
    print(f"SHADOW VERDICT: {cf['shadow_verdict']}")
    print(f"UNKNOWNS     : {cf['unknowns']}")
    print(f"FAILURE COND : {cf['failure_conditions']}")
    print(f"AUDIT HASH   : {cf['audit_hash_tail']}")

    print("\n=== SYSTEM STATUS ===")
    s = system_status()
    print(json.dumps(s, ensure_ascii=False, indent=2)[:1200])

    print("\n=== self-test OK ===")
