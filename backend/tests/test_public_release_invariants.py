"""
test_public_release_invariants.py — fixes that exist ONLY in the public release
==============================================================================
This repository is assembled from a private working instance, and drift runs both
ways: it carries portability fixes the private instance does not have. Porting a
file wholesale from private to public silently reverts them.

That is not hypothetical. It happened twice in one sitting:

  · reality_grading.py — the `promotion_rate` None-guard was overwritten. Caught
    only because an unrelated test divided None by an int.
  · obsidian_tools.py — platform-aware vault discovery (Linux Nextcloud/Dropbox,
    macOS iCloud) was overwritten. **Nothing failed.** No test covers platform
    discovery, so the fix vanished without a signal.

The second one is the reason this file exists. An invariant that only a human
remembers is an invariant that gets reverted. These tests are cheap, they name
what they protect, and they fail loudly on a careless port.

    python -m pytest tests/test_public_release_invariants.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))


def _src(name: str) -> str:
    return (_BASE / name).read_text(encoding="utf-8")


# ── platform portability: this ships to machines that are not the author's ────
def test_vault_discovery_covers_all_three_platforms():
    s = _src("obsidian_tools.py")
    assert "os.name" in s, "Windows branch missing"
    assert "darwin" in s or "iCloud" in s, "macOS branch missing"
    assert "Nextcloud" in s or "Dropbox" in s, "Linux branch missing"


def test_tesseract_is_found_by_path_not_by_a_hardcoded_location():
    s = _src("doc_reader.py")
    assert "which" in s, (
        "OCR must locate tesseract on PATH first; a hardcoded Windows path is not "
        "portable")


def test_the_model_runtime_address_is_configurable():
    s = _src("main.py")
    assert "OLLAMA_BASE_URL" in s, (
        "inside a container 'localhost' is the container itself — the runtime "
        "address must come from the environment")


# ── honest nulls: a fabricated zero is the failure this project is about ──────
def test_promotion_rate_stays_null_when_unmeasured():
    """`promoted` is None while the promotion path is dormant. None/int raises, and
    a 0.0 would claim a measurement nobody took."""
    s = _src("reality_grading.py")
    assert "promoted is not None" in s, "the promotion_rate None-guard was reverted"


def test_health_reports_a_missing_runtime_as_degraded_not_broken():
    """A machine that has not started Ollama is a supported state. RED means the
    House itself is faulty and would fail CI and alarm every new user."""
    s = _src("health_check.py")
    assert "YELLOW" in s
    assert "no local model runtime" in s


def test_kernel_policies_are_reported_per_hook():
    """Printing every policy under one hook's name claimed the fabrication guard
    fires before the action; it fires before the commit."""
    s = _src("main.py")
    assert "registered_by_hook" in s, (
        "the boot log must report each hook with its own policies")


# ── the epistemic instrument must not go quiet ────────────────────────────────
def test_self_audit_findings_are_proportional():
    """Binary conditions let one success of nine silence a systemic warning."""
    s = _src("epistemic_dossier.py")
    assert "_gap(" in s, "proportional findings were reverted to binary conditions"


def test_the_dossier_opens_its_database_read_only():
    assert "mode=ro" in _src("epistemic_dossier.py")


# ── privacy: this tree is assembled from a private instance ───────────────────
def test_no_operator_home_directory_in_any_shipped_module():
    """tools/privacy_scan.py is the full gate; this is the fast in-suite check so a
    regression fails with the tests rather than only in CI."""
    import re
    pat = re.compile(r"[Cc]:[\\/]+Users[\\/]+(?!default|public|all users)[A-Za-z0-9._-]+",
                     re.I)
    hits = []
    for p in _BASE.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        for m in pat.finditer(p.read_text(encoding="utf-8", errors="ignore")):
            if "privacy_scan" in p.name or "release_invariants" in p.name:
                continue
            hits.append(f"{p.relative_to(_BASE).as_posix()}: {m.group(0)[:40]}")
    assert not hits, f"operator paths in shipped code: {hits[:4]}"
