"""
kernel_events.py — Cognitive Kernel · Event subsystem (migration step 1)
=======================================================================
The first migration under COGNITIVE_KERNEL_SPEC v0.2 / ADR-0003. Formalizes the
event envelope on top of the existing house_sync bus WITHOUT breaking it
(strangler-fig): house_sync stays the live SSE relay; this adds the canonical
envelope, correlation, the A2 two-tier durability split, and A4 authority.

Envelope (SPEC §4):
    {id, type, payload, source, correlation_id, mission_id, ts, severity, tier}

Two tiers (amendment A2 — resolves the "best-effort audit spine" tension):
    · audit-critical  → policy.* · mission.commit · cognitive.invalid · *.escalated
                        durably appended to an on-disk log BEFORE the live relay
                        (the black-box recorder). If the durable write fails, emit
                        reports ok=False so a caller may treat it as fail-safe.
    · observational   → everything else: best-effort via house_sync only.

Authority (amendment A4): only the owning source may emit an authority namespace —
only "policy" emits policy.*, only "cvl" emits cognitive.*. A spoofed authority
event from any other source is REJECTED at the producer (never reaches the bus).

Correlation (decision D2): a per-cognitive-request id, grouped by a mission id,
carried on a contextvar so emit() attaches it automatically.

Never raises — a telemetry failure must not break the runtime. Stdlib only;
house_sync is a lazy import. License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

# ── Taxonomy (SPEC §4) ────────────────────────────────────────────────────────
NAMESPACES = ("lifecycle", "cognitive", "policy", "memory", "mission", "outcome", "auth")

# A4 — authority: namespace → the ONLY source allowed to emit it.
_AUTHORITY = {"policy": "policy", "cognitive": "cvl", "auth": "operator"}

# A2 — which event types are audit-critical (durable + synchronous).
_AUDIT_CRITICAL_TYPES = {"cognitive.invalid"}
_AUDIT_CRITICAL_NS = {"policy", "auth"}   # every elevation attempt is on the record
_AUDIT_CRITICAL_PREFIXES = ("mission.commit",)
_AUDIT_CRITICAL_SUFFIXES = (".escalated",)

_SEVERITIES = ("info", "warn", "error")

_AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kernel_audit.jsonl")
_audit_lock = threading.Lock()
_seq = 0

# D2 — correlation context (per cognitive request, grouped by mission).
_correlation: contextvars.ContextVar[str] = contextvars.ContextVar("ck_correlation", default="")
_mission: contextvars.ContextVar[str] = contextvars.ContextVar("ck_mission", default="")


# ── Envelope ──────────────────────────────────────────────────────────────────
@dataclass
class Event:
    id: str
    type: str
    payload: Dict[str, Any]
    source: str
    correlation_id: str
    mission_id: str
    ts: float
    severity: str
    tier: str            # "audit" | "observational"


def namespace_of(etype: str) -> str:
    return str(etype).split(".", 1)[0]


def is_audit_critical(etype: str) -> bool:
    etype = str(etype)
    return (etype in _AUDIT_CRITICAL_TYPES
            or namespace_of(etype) in _AUDIT_CRITICAL_NS
            or etype.startswith(_AUDIT_CRITICAL_PREFIXES)
            or etype.endswith(_AUDIT_CRITICAL_SUFFIXES))


def authorized(etype: str, source: str) -> bool:
    """A4 — is `source` allowed to emit this namespace?"""
    owner = _AUTHORITY.get(namespace_of(etype))
    return owner is None or owner == source


# ── Correlation context (D2) ──────────────────────────────────────────────────
def new_correlation_id() -> str:
    global _seq
    _seq += 1
    return f"cog_{int(time.time() * 1000)}_{_seq}"


def set_context(correlation_id: Optional[str] = None, mission_id: Optional[str] = None) -> str:
    """Bind the current cognitive-request id (+ mission group). Returns the cid."""
    cid = correlation_id or new_correlation_id()
    _correlation.set(cid)
    if mission_id is not None:
        _mission.set(mission_id)
    return cid


def current_correlation() -> str:
    return _correlation.get()


def current_mission() -> str:
    return _mission.get()


# ── Durable audit log (A2) ────────────────────────────────────────────────────
def _durable_append(evt: Dict[str, Any], path: str) -> bool:
    try:
        with _audit_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        return True
    except Exception:
        return False


def audit_tail(n: int = 50, path: Optional[str] = None) -> List[Dict[str, Any]]:
    p = path or _AUDIT_LOG_PATH
    try:
        with open(p, encoding="utf-8") as f:
            lines = f.readlines()[-max(0, n):]
        return [json.loads(x) for x in lines if x.strip()]
    except Exception:
        return []


# ── The producer front door ───────────────────────────────────────────────────
def emit(etype: str, payload: Optional[Dict[str, Any]] = None, source: str = "runtime",
         severity: str = "info", correlation_id: Optional[str] = None,
         mission_id: Optional[str] = None, _audit_path: Optional[str] = None) -> Dict[str, Any]:
    """Emit ONE kernel event. Returns {ok, rejected?, durable?, event}. Never raises.

    - Enforces A4 authority (rejects a spoofed authority event).
    - Classifies the A2 tier; audit-critical events are durably logged first.
    - Relays to house_sync for the live SSE bus (best-effort, back-compat).
    """
    etype = str(etype)
    if not authorized(etype, source):
        return {"ok": False, "rejected": "authority",
                "reason": f"{source} may not emit {namespace_of(etype)}.* "
                          f"(owner={_AUTHORITY.get(namespace_of(etype))})", "event": None}
    if severity not in _SEVERITIES:
        severity = "info"
    global _seq
    _seq += 1
    tier = "audit" if is_audit_critical(etype) else "observational"
    evt = Event(
        id=f"evt_{int(time.time() * 1000)}_{_seq}",
        type=etype, payload=payload or {}, source=str(source),
        correlation_id=correlation_id or _correlation.get(),
        mission_id=mission_id if mission_id is not None else _mission.get(),
        ts=time.time(), severity=severity, tier=tier,
    )
    d = asdict(evt)
    durable = True
    if tier == "audit":
        durable = _durable_append(d, _audit_path or _AUDIT_LOG_PATH)
    # live relay — best-effort, and back-compat with existing bus consumers.
    try:
        import house_sync
        house_sync.publish(etype, {**evt.payload, "_cid": evt.correlation_id,
                                   "_sev": severity, "_tier": tier}, source=source)
    except Exception:
        pass
    return {"ok": (durable or tier == "observational"), "durable": durable, "event": d}


# ── A6 — conformance self-test (a subsystem is 'migrated' only when this is green) ─
def conforms_to() -> Dict[str, Any]:
    import tempfile
    checks: Dict[str, bool] = {}
    # envelope shape
    r = emit("lifecycle.execute", {"step": 1}, source="scheduler", severity="info")
    e = r["event"]
    checks["envelope"] = bool(e) and all(k in e for k in
        ("id", "type", "payload", "source", "correlation_id", "mission_id", "ts", "severity", "tier"))
    checks["observational_tier"] = e and e["tier"] == "observational"
    # correlation context is attached automatically
    cid = set_context()
    checks["correlation"] = emit("lifecycle.plan", source="planner")["event"]["correlation_id"] == cid
    # A4 authority: a spoofed policy event from a non-owner is rejected
    checks["authority_reject"] = emit("policy.denied", source="cvl")["rejected"] == "authority"
    checks["authority_allow"] = emit("policy.denied", {"x": 1}, source="policy")["ok"] is True
    # A2 tiers
    checks["policy_is_audit"] = is_audit_critical("policy.denied") and not is_audit_critical("lifecycle.execute")
    checks["cognitive_invalid_audit"] = is_audit_critical("cognitive.invalid")
    # durability: an audit-critical event is written to disk and read back
    tmp = os.path.join(tempfile.gettempdir(), f"ck_audit_{int(time.time()*1000)}.jsonl")
    r2 = emit("cognitive.invalid", {"msg": "test"}, source="cvl", severity="error", _audit_path=tmp)
    tail = audit_tail(5, path=tmp)
    checks["durable_audit"] = r2["durable"] and any(t["type"] == "cognitive.invalid" for t in tail)
    try:
        os.remove(tmp)
    except Exception:
        pass
    ok = all(checks.values())
    return {"ok": ok, "checks": checks}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = conforms_to()
    for k, v in r["checks"].items():
        print(f"  {'OK ' if v else 'XX '} {k}")
    print("conforms_to:", r["ok"])
