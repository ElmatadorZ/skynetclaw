"""
cognitive_validation.py — Cognitive Validation Layer (CVL)
==========================================================
The cognitive quality gate: before SkynetClaw accepts ANY response — or takes an
autonomous action — its output is validated across every cognitive capability,
not just reasoning. CVL is the evolution of the Reasoning Validation Layer;
arithmetic is now the first of many cognitive validators.

Domains (a validator declares one):
    reasoning · memory · planning · tool_use · safety · production

Pipeline (operator's design):
    Observe → Diagnose → Repair → Explain → Validate → Accept
  · Observe   — a validator extracts the claims/artifacts it can check.
  · Diagnose  — it identifies the issue AND its root cause (not just "wrong").
  · Repair    — CVL renders a correction prompt the caller feeds back.
  · Explain   — CVL emits a human-readable audit record of every finding + the
                repair action taken (transparency / auditability).
  · Validate  — the caller re-runs CVL after the model corrects.
  · Accept    — errors block acceptance until fixed (bounded retries).

Extensibility (SOLID / Open-Closed): implement the Validator protocol and
register() — no pipeline change. Deterministic, model-free, stdlib only
(Article VIII). Governed by the Engineering Constitution v1.0 — ADR-0001, ADR-0002.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# The cognitive domains CVL is designed to cover (a validator picks one).
DOMAINS = ("reasoning", "memory", "planning", "tool_use", "safety", "production")


# ── Result types ──────────────────────────────────────────────────────────────
@dataclass
class Issue:
    validator: str
    domain: str              # one of DOMAINS
    severity: str            # "error" (blocks accept) | "warn" (surfaced only)
    message: str             # what is wrong
    diagnosis: str = ""      # WHY it is wrong (root cause) — the Diagnose stage
    evidence: str = ""       # the exact span that failed
    scb_category: str = ""   # SCB dimension this maps to


@dataclass
class ValidationResult:
    validator: str
    ok: bool
    issues: List[Issue] = field(default_factory=list)


@runtime_checkable
class Validator(Protocol):
    name: str
    domain: str
    scb_category: str
    def applicable(self, text: str, context: Dict[str, Any]) -> bool: ...
    def validate(self, text: str, context: Dict[str, Any]) -> ValidationResult: ...


# ── Registry ──────────────────────────────────────────────────────────────────
_VALIDATORS: List[Validator] = []


def register(v: Validator) -> None:
    """Add a validator plugin (idempotent by name)."""
    if not any(getattr(x, "name", None) == getattr(v, "name", None) for x in _VALIDATORS):
        _VALIDATORS.append(v)


def registered() -> List[str]:
    return [getattr(v, "name", "?") for v in _VALIDATORS]


def by_domain() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {d: [] for d in DOMAINS}
    for v in _VALIDATORS:
        out.setdefault(getattr(v, "domain", "reasoning"), []).append(getattr(v, "name", "?"))
    return out


# ── The pipeline: Observe → Diagnose → (Repair prompt) → Explain ──────────────
def validate(text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run every applicable validator over `text`. Returns
    {ok, issues[], errors[], repair_prompt, explanation, domains, validators_run}.
    Never raises — a broken validator must not break the mission."""
    ctx = context or {}
    issues: List[Issue] = []
    ran: List[str] = []
    for v in _VALIDATORS:
        try:
            if v.applicable(text or "", ctx):
                ran.append(v.name)
                r = v.validate(text or "", ctx)
                issues.extend(r.issues)
        except Exception:
            continue
    errors = [i for i in issues if i.severity == "error"]
    domains = sorted({i.domain for i in issues})
    return {
        "ok": not errors,
        "issues": [asdict(i) for i in issues],
        "errors": [asdict(i) for i in errors],
        "repair_prompt": _render_repair(errors) if errors else "",
        "explanation": _render_explanation(issues) if issues else "",  # Explain stage
        "domains": domains,
        "validators_run": ran,
    }


def _render_repair(errors: List[Issue]) -> str:
    lines = ["⚠ COGNITIVE VALIDATION — fix these before finalizing your answer:"]
    for e in errors[:8]:
        lines.append(f"  · [{e.domain}/{e.validator}] {e.message}")
    lines.append("Recompute/correct the above, then restate the answer. Do not repeat the wrong value.")
    return "\n".join(lines)


def _render_explanation(issues: List[Issue]) -> str:
    """The Explain stage: a human-readable audit record of what was found, why,
    and what repair was applied — for transparency and auditability."""
    lines = [f"🧠 Cognitive Validation — {len(issues)} finding(s):"]
    for i in issues[:10]:
        action = ("blocked/flagged" if i.severity == "error" else "noted")
        why = f" — {i.diagnosis}" if i.diagnosis else ""
        lines.append(f"  · [{i.domain}] {i.validator}: {i.message}{why}  → {action}")
    return "\n".join(lines)


# ── Safe numeric helpers (NO eval — Article VIII) ─────────────────────────────
def _num(s: str) -> float:
    return float(str(s).replace(",", "").strip())


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-6, abs(a) * 0.001)


def _fmt(x: float) -> str:
    return f"{x:.10g}"


# ── Validator #1: ArithmeticValidator (domain=reasoning, SCB-002) ─────────────
# Binary "a op b = c" ONLY. The lookbehind rejects a leading operator so a fragment
# in the MIDDLE of a longer chain ("2000+3000=7000" inside "1000+2000+3000=7000")
# is left to the ExpressionValidator — no double-report with a conflicting result.
# The lookbehind rejects a leading COMMA (as well as \w/. and operators) so a
# thousands-separated number like "2,000" can never start a spurious match at its
# "000" fragment — the false-positive the certification council falsified at runtime.
_ARITH_RE = re.compile(
    r"(?<![\w.,+\-*/×÷])(\d[\d,]*\.?\d*)\s*([+\-*/×÷x])\s*(\d[\d,]*\.?\d*)\s*=\s*(\d[\d,]*\.?\d*)")
_PCT_RE = re.compile(
    r"(?<![\w.,])(\d[\d,]*\.?\d*)\s*%\s*(?:of|ของ)\s*(\d[\d,]*\.?\d*)\s*=\s*(\d[\d,]*\.?\d*)", re.I)
_OP_NAME = {"+": "addition", "-": "subtraction", "*": "multiplication", "/": "division"}


class ArithmeticValidator:
    name = "arithmetic"
    domain = "reasoning"
    scb_category = "Quantitative"

    def applicable(self, text: str, context: Dict[str, Any]) -> bool:
        return bool(_ARITH_RE.search(text) or _PCT_RE.search(text))

    def validate(self, text: str, context: Dict[str, Any]) -> ValidationResult:
        issues: List[Issue] = []
        for m in _ARITH_RE.finditer(text):
            try:
                a, op, b, stated = _num(m.group(1)), m.group(2), _num(m.group(3)), _num(m.group(4))
            except Exception:
                continue
            op = {"×": "*", "÷": "/", "x": "*"}.get(op, op)
            try:
                actual = {"+": a + b, "-": a - b, "*": a * b,
                          "/": (a / b if b != 0 else None)}.get(op)
            except Exception:
                actual = None
            if actual is not None and not _close(actual, stated):
                issues.append(Issue(
                    "arithmetic", "reasoning", "error",
                    f"{m.group(1)} {m.group(2)} {m.group(3)} = {m.group(4)} is incorrect; "
                    f"the correct result is {_fmt(actual)}.",
                    diagnosis=f"{_OP_NAME.get(op, 'operation')} miscalculated",
                    evidence=m.group(0), scb_category="Quantitative"))
        for m in _PCT_RE.finditer(text):
            try:
                p, base, stated = _num(m.group(1)), _num(m.group(2)), _num(m.group(3))
            except Exception:
                continue
            actual = p / 100.0 * base
            if not _close(actual, stated):
                issues.append(Issue(
                    "arithmetic", "reasoning", "error",
                    f"{m.group(1)}% of {m.group(2)} = {m.group(3)} is incorrect; "
                    f"the correct result is {_fmt(actual)}.",
                    diagnosis="percentage computed incorrectly",
                    evidence=m.group(0), scb_category="Quantitative"))
        return ValidationResult("arithmetic", not issues, issues)


# ── Validator #2: SecretLeakValidator (domain=safety) ─────────────────────────
# Proves CVL spans capabilities beyond reasoning: a response must never expose a
# credential. Conservative patterns → an error blocks the answer.
_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"), "a private key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key id"),
    (re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "a GitHub token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "an API secret key"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "a Slack token"),
    (re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
     "a hardcoded credential"),
]


class SecretLeakValidator:
    name = "secret_leak"
    domain = "safety"
    scb_category = "Security"

    def applicable(self, text: str, context: Dict[str, Any]) -> bool:
        return len(text or "") > 0

    def validate(self, text: str, context: Dict[str, Any]) -> ValidationResult:
        issues: List[Issue] = []
        for rx, label in _SECRET_PATTERNS:
            m = rx.search(text)
            if m:
                span = m.group(0)
                issues.append(Issue(
                    "secret_leak", "safety", "error",
                    f"the response exposes {label} — remove it before responding.",
                    diagnosis="a credential-shaped string must never appear in an answer",
                    evidence=span[:12] + "…", scb_category="Security"))
        return ValidationResult("secret_leak", not issues, issues)


# ── Validator #3: ExpressionValidator (domain=reasoning, SCB-002) ─────────────
# The arithmetic validator only checks BINARY "a op b = c". This catches
# MULTI-TERM / parenthesised expressions it misses ("10+20+30 = 70",
# "(100-20)*3 = 260", "1000*12*0.05 = 600") by re-computing the LHS deterministically
# with safe_math (the kernel's arithmetic primitive — no eval, Article VIII).
# Only fires with ≥2 operators so it never double-reports the binary case; the
# safe_math parse is the real guard, so prose/years/versions can't false-positive.
_EXPR_RE = re.compile(
    r"(?<![\w.,])([0-9(][0-9.,()\s]*(?:[+\-*/×÷][0-9.,()\s]+){2,})=\s*([0-9][0-9,]*\.?[0-9]*)")


class ExpressionValidator:
    name = "expression"
    domain = "reasoning"
    scb_category = "Quantitative"

    def applicable(self, text: str, context: Dict[str, Any]) -> bool:
        return bool(_EXPR_RE.search(text or ""))

    def validate(self, text: str, context: Dict[str, Any]) -> ValidationResult:
        issues: List[Issue] = []
        try:
            import safe_math
        except Exception:
            return ValidationResult("expression", True, [])
        for m in _EXPR_RE.finditer(text):
            lhs = m.group(1).replace("×", "*").replace("÷", "/").strip()
            try:
                stated = _num(m.group(2))
            except Exception:
                continue
            try:
                actual = safe_math.evaluate(lhs)   # raises MathError on non-math → skipped
            except Exception:
                continue
            if not _close(float(actual), stated):
                issues.append(Issue(
                    "expression", "reasoning", "error",
                    f"{lhs} = {m.group(2)} is incorrect; the correct result is {_fmt(float(actual))}.",
                    diagnosis="multi-term expression miscalculated",
                    evidence=m.group(0)[:60], scb_category="Quantitative"))
        return ValidationResult("expression", not issues, issues)


register(ArithmeticValidator())
register(SecretLeakValidator())
register(ExpressionValidator())


if __name__ == "__main__":
    import sys, json
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("domains:", by_domain())
    bad = "รายได้ = 1,200 × 5 = 6200 และ token=AKIAIOSFODNN7EXAMPLE12"
    r = validate(bad)
    print("BAD ok:", r["ok"], "| domains:", r["domains"])
    print(r["explanation"])
    assert not r["ok"] and set(r["domains"]) == {"reasoning", "safety"}
    assert validate("1,200 × 5 = 6,000; ในปี 2026 ราคา $5 ต่อชิ้น")["ok"]
    print("self-test OK — multi-domain (reasoning+safety), explanation emitted, no prose false-positive")
