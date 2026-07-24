"""
path_security.py — file-tool path confinement + sensitive-path deny-list
========================================================================
Extracted from main.py — God Object decomposition, strangler-fig slice 1. Pure
security logic with a narrow interface: the active-workspace ContextVar, the
sensitive-path deny-list, and _resolve_path (workspace confinement with the
Obsidian-vault exemption). main re-exports every name here, so all call sites are
unchanged.

Runtime deps that remain in main (_vault_root, load_settings, _default_workspace)
are resolved via a LAZY import, so there is no import cycle: main imports this at
module load; this imports main only when _resolve_path actually runs (by which time
main is fully loaded).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import contextvars
import os
import re
from pathlib import Path

from vault_awareness import _vault_root  # no main dependency → no import cycle

# ── Active workspace folder (per-request, set by agent_run / chat) ────────────
ACTIVE_WORKSPACE: contextvars.ContextVar = contextvars.ContextVar(
    "ACTIVE_WORKSPACE", default=None
)

# ── SECURITY (audit P1): sensitive-path deny-list for file tools ─────────────
# Closes the reproduced token-exfil (the agent used read_file to read the stealth
# bearer token) without confining the whole workspace — a targeted block on
# secrets/creds/policy files, so legitimate project reads are unaffected.
_SENSITIVE_PATH_PATTERNS = [
    r"\.bridge_token$", r"\.approval_secret$", r"stealth_approval",
    r"(^|[/\\])\.env(\.|$)", r"id_rsa", r"[/\\]\.ssh[/\\]", r"[/\\]\.aws[/\\]cred",
    r"\.pem$", r"\.ppk$", r"\.key$", r"\.pfx$",
    r"governance_config\.json$", r"governance_pending", r"exec_approvals",
    r"\.watchdog\.lock$", r"[/\\]credentials?[/\\]",
    r"(^|[/\\])secrets?\.(json|ya?ml|toml|txt|env)$",
]


def _path_is_sensitive(p) -> bool:
    try:
        pl = str(p).replace("\\", "/").lower()
        return any(re.search(pat, pl) for pat in _SENSITIVE_PATH_PATTERNS)
    except Exception:
        return False


def _resolve_path(raw: str) -> Path:
    """
    Resolve a tool 'path' argument, CONFINED to the active workspace (SEC C3).
      - If a workspace is active: the final resolved path MUST stay inside it.
        Relative paths are prefixed; absolute paths are allowed only if already
        inside the workspace; any traversal/escape (`..`, absolute-outside) is
        clamped to <workspace>/<basename> rather than escaping the sandbox.
      - If no workspace is active: legacy behavior (cannot confine).
    Always returns a Path.
    """
    if not raw:
        return Path(raw or ".")
    p = Path(raw)
    # THE OBSIDIAN VAULT IS ALWAYS REACHABLE: it is the agent's own configured
    # memory (settings.obsidian_vault), so a file tool targeting it must NOT be
    # clamped away just because a different workspace is active — that returned
    # [] and made the agent think its own vault was empty/unknown. Structural
    # fix (a prompt banner alone didn't stop a small model from using find_files).
    try:
        if p.is_absolute():
            _vr = _vault_root()
            if _vr is not None:
                _pr = p.resolve()
                if _pr == _vr or _vr in _pr.parents:
                    return _pr
    except Exception:
        pass
    ws = ACTIVE_WORKSPACE.get()
    # SAFE-MODE (opt-in): when settings.confine_workspace is true, never run
    # unconfined — fall back to a per-user sandbox instead of the raw filesystem
    # (the AtlasZClaw public-build posture). Default OFF here: this is the
    # operator's own trusted dev tool and reads/writes across the disk on
    # purpose. Turn on with settings.json {"confine_workspace": true}.
    if not ws:
        try:
            import main as _m  # lazy — only for the opt-in confine_workspace safe-mode
            if _m.load_settings().get("confine_workspace"):
                ws = _m._default_workspace()
        except Exception:
            ws = None
    if ws:
        wsr = Path(ws).resolve()
        cand = p if p.is_absolute() else (wsr / p)
        try:
            resolved = cand.resolve()
        except Exception:
            resolved = cand
        try:
            resolved.relative_to(wsr)        # inside workspace → OK
            return resolved
        except ValueError:
            # escape attempt → clamp into the workspace using basename only
            safe = os.path.basename(str(raw).replace("\\", "/").rstrip("/")) or "file"
            return wsr / safe
    # no workspace + safe-mode off → legacy (unconfined; trusted operator)
    return p
