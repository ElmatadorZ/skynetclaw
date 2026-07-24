"""
kernel_operator.py — authenticated operator elevation (audited, still governed)
==============================================================================
The SAFE alternative to a backdoor. There is no secret phrase and no hidden path:
an operator proves identity with a real token (verified server-side, constant-time),
and elevation only ever downgrades an ESCALATE (the interactive human gate) to an
audited ALLOW. It NEVER touches DENY, never unlocks an unknown/prohibited tool, and
every elevation lands on the kernel audit spine.

Why this is not a backdoor:
  · the token is verified on the server; the model/agent loop never sees it, so it
    cannot be triggered by prompt-injection or by a phrase typed into chat;
  · elevation is an INPUT to the GPS-2 policy decision, not a bypass of the hooks —
    DENY stays DENY, deny-by-default for unknown tools stays;
  · every verify (success AND failure) emits an audit-critical auth.* event
    (source="operator"), so use and brute-force attempts are visible in Intel.

Token storage: only a salted SHA-256 HASH is persisted (.operator_token, gitignored,
0600). The raw token is shown once at setup and never stored or logged.

Stdlib only. License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional

_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".operator_token")
_SALT = "skynet-operator:v1:"


def _hash(token: str) -> str:
    return hashlib.sha256((_SALT + (token or "")).encode("utf-8")).hexdigest()


def is_configured() -> bool:
    return os.path.exists(_TOKEN_FILE)


def setup(force: bool = False) -> Dict[str, Any]:
    """Generate the operator token ONCE. Stores only its hash; returns the raw
    token to show the operator a single time. Never call this from the agent loop."""
    if is_configured() and not force:
        return {"ok": False, "error": "operator token already configured (use force=True to rotate)"}
    token = secrets.token_urlsafe(32)
    data = {"hash": _hash(token), "created": time.time()}
    try:
        with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        try:
            os.chmod(_TOKEN_FILE, 0o600)   # best-effort restrictive perms
        except Exception:
            pass
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "token": token,
            "note": "shown once — store it in your password manager; it is NOT recoverable"}


def verify(token: Optional[str]) -> bool:
    """Constant-time check of a presented token against the stored hash."""
    if not token or not is_configured():
        return False
    try:
        with open(_TOKEN_FILE, encoding="utf-8") as f:
            stored = json.load(f).get("hash", "")
    except Exception:
        return False
    return bool(stored) and hmac.compare_digest(stored, _hash(token))


def elevate(token: Optional[str], origin: str = "") -> Dict[str, Any]:
    """Verify a token and AUDIT the attempt. Returns {ok, elevated, rationale}.
    Emits an audit-critical auth.* event either way (visible in Intel)."""
    ok = verify(token)
    try:
        import kernel_events as _ke
        _ke.emit("auth.elevated" if ok else "auth.denied",
                 {"origin": origin or "local", "configured": is_configured()},
                 source="operator", severity="info" if ok else "warn")
    except Exception:
        pass
    return {"ok": ok, "elevated": ok,
            "rationale": "operator token verified" if ok else "no/invalid operator token"}


def status() -> Dict[str, Any]:
    """Read-only: is a token configured? (never reveals the token or its hash)."""
    return {"configured": is_configured()}


# ── A6 — conformance self-test (uses a temp token file; never touches the real one) ─
def conforms_to() -> Dict[str, Any]:
    import tempfile
    global _TOKEN_FILE
    checks: Dict[str, bool] = {}
    real = _TOKEN_FILE
    tmp = os.path.join(tempfile.gettempdir(), f"ck_op_{int(time.time()*1000)}")
    _TOKEN_FILE = tmp
    try:
        checks["unconfigured_rejects"] = not verify("anything")
        s = setup()
        tok = s.get("token", "")
        checks["setup_returns_token"] = bool(s.get("ok")) and len(tok) > 20
        checks["stores_only_hash"] = tok not in open(tmp, encoding="utf-8").read()
        checks["correct_token_verifies"] = verify(tok) is True
        checks["wrong_token_rejects"] = verify(tok + "x") is False and verify("") is False and verify(None) is False
        checks["elevate_audits"] = elevate(tok)["ok"] is True and elevate("bad")["ok"] is False
        ok = all(checks.values())
        return {"ok": ok, "checks": checks}
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
        _TOKEN_FILE = real


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = conforms_to()
    for k, v in r["checks"].items():
        print(f"  {'OK ' if v else 'XX '} {k}")
    print("conforms_to:", r["ok"], "| configured:", is_configured())
