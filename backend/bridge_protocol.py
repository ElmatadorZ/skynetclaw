"""
bridge_protocol.py — Continental Bridge Protocol (CBP) v1.0
==================================================================
Formal message envelope for traffic between THE CONTINENTAL DIVISION (UI)
and SkynetClaw (execution backend). Every cross-app message must conform.

ENVELOPE shape:
  { v, id, ts, src, dst, type, payload, prev_hash, hash }

ELEVEN message TYPES:
  DIRECTIVE      operator → house         text/intent submission
  ACK            house → operator         received + conv_id assigned
  STREAM_START   house → operator         relay opens SSE pipe
  PHASE          house → operator         L0..L8 transition
  OPERATIVE_ON   house → operator         operative engaged + verb
  OPERATIVE_OFF  house → operator         operative stood down
  SKILL_FIRE     house → operator         auto-router activated a skill
  TOOL_CALL      house → operator         exec_tool invoked (name + args hash)
  TOOL_RESULT    house → operator         exec_tool returned (size + ok)
  TEXT_DELTA     house → operator         streaming text chunk
  VERDICT        house → operator         skeptic shadow gate verdict
  COMPLETE       house → operator         mission closed + response hash
  ERROR          house → operator         any error during mission

HASH CHAIN:
  Each message stores prev_hash = sha256 of previous message's hash.
  hash = sha256(prev_hash || canonical_json(envelope_minus_hash))[:16]
  → tamper-evident — modify one message → all subsequent hashes invalidate.

PERSISTENCE:
  Every envelope is written to bridge_log.jsonl (append-only)
  + last_hash kept in memory for O(1) chain continuation.
"""
from __future__ import annotations
import hashlib, json, time, secrets
from pathlib import Path
from typing import Any, Dict, Optional

_BASE = Path(__file__).parent
LOG   = _BASE / "bridge_log.jsonl"

# ── public message type vocabulary ─────────────────────────────────
class T:
    DIRECTIVE      = "DIRECTIVE"
    ACK            = "ACK"
    STREAM_START   = "STREAM_START"
    PHASE          = "PHASE"
    OPERATIVE_ON   = "OPERATIVE_ON"
    OPERATIVE_OFF  = "OPERATIVE_OFF"
    SKILL_FIRE     = "SKILL_FIRE"
    TOOL_CALL      = "TOOL_CALL"
    TOOL_RESULT    = "TOOL_RESULT"
    TEXT_DELTA     = "TEXT_DELTA"
    VERDICT        = "VERDICT"
    COMPLETE       = "COMPLETE"
    ERROR          = "ERROR"
    ALL = {DIRECTIVE, ACK, STREAM_START, PHASE, OPERATIVE_ON, OPERATIVE_OFF,
           SKILL_FIRE, TOOL_CALL, TOOL_RESULT, TEXT_DELTA, VERDICT, COMPLETE, ERROR}


_last_hash: Optional[str] = None  # in-process chain head


def _read_last_hash() -> str:
    """Recover chain head from disk on cold start."""
    global _last_hash
    if _last_hash is not None:
        return _last_hash
    if not LOG.exists():
        _last_hash = "GENESIS"
        return _last_hash
    try:
        with LOG.open("rb") as f:
            f.seek(0, 2); size = f.tell()
            f.seek(max(0, size - 4096))
            tail = f.read().decode("utf-8", errors="ignore").splitlines()
            for line in reversed(tail):
                try:
                    h = json.loads(line).get("hash")
                    if h:
                        _last_hash = h
                        return h
                except Exception:
                    continue
    except Exception:
        pass
    _last_hash = "GENESIS"
    return _last_hash


def emit(type: str, payload: Dict[str, Any],
         src: str = "house", dst: str = "operator",
         conv_id: str = "") -> Dict[str, Any]:
    """Build + persist + return a CBP envelope."""
    global _last_hash
    if type not in T.ALL:
        raise ValueError(f"unknown CBP type: {type}")
    prev = _read_last_hash()
    env = {
        "v":         1,
        "id":        secrets.token_hex(6),
        "ts":        time.time(),
        "src":       src,
        "dst":       dst,
        "conv_id":   conv_id,
        "type":      type,
        "payload":   payload,
        "prev_hash": prev,
    }
    # canonical json for hashing (sort keys)
    canon = json.dumps(env, ensure_ascii=False, sort_keys=True)
    env["hash"] = hashlib.sha256((prev + canon).encode("utf-8")).hexdigest()[:16]
    _last_hash = env["hash"]
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(env, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return env


def read_tail(limit: int = 100) -> list:
    """Return last N envelopes."""
    if not LOG.exists():
        return []
    out = []
    try:
        with LOG.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out[-limit:]


def verify_chain() -> Dict[str, Any]:
    """Walk the entire chain and verify every hash. Returns {ok, total, first_bad}."""
    if not LOG.exists():
        return {"ok": True, "total": 0}
    prev = "GENESIS"
    total = 0
    bad_id = None
    with LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                env = json.loads(line)
            except Exception:
                continue
            total += 1
            stored = env.pop("hash", "")
            env["prev_hash"] = prev  # ensure
            canon = json.dumps(env, ensure_ascii=False, sort_keys=True)
            recomputed = hashlib.sha256((prev + canon).encode("utf-8")).hexdigest()[:16]
            if recomputed != stored:
                bad_id = env.get("id", "?")
                return {"ok": False, "total": total, "first_bad": bad_id,
                        "expected": recomputed, "found": stored}
            prev = stored
    return {"ok": True, "total": total}


# ── public mount for FastAPI ────────────────────────────────────────
def mount(app):
    from fastapi.responses import JSONResponse
    @app.get("/api/bridge/log")
    def _log(limit: int = 100):
        return {"ok": True, "envelopes": read_tail(limit)}
    @app.get("/api/bridge/verify")
    def _verify():
        return verify_chain()
    @app.get("/api/bridge/spec")
    def _spec():
        return {
            "version": "CBP 1.0",
            "types": sorted(list(T.ALL)),
            "envelope_keys": ["v","id","ts","src","dst","conv_id","type","payload","prev_hash","hash"],
            "hash": "sha256(prev_hash || canonical_json(envelope_minus_hash))[:16]",
            "transport": "JSON over POST/SSE",
            "persistence": str(LOG),
        }
    print("[BridgeProtocol] CBP 1.0 mounted at /api/bridge/*")


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    # self-test
    print("=== CBP 1.0 self-test ===")
    e1 = emit(T.DIRECTIVE, {"text": "test directive"}, src="operator", dst="house", conv_id="CV-TEST")
    e2 = emit(T.ACK, {"received": True}, conv_id="CV-TEST")
    e3 = emit(T.PHASE, {"phase": "L0"}, conv_id="CV-TEST")
    print(f"emitted 3 envelopes, last hash: {_last_hash}")
    v = verify_chain()
    print(f"chain verify: {v}")
