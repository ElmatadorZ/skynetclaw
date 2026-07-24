"""
safe_math.py — deterministic, safe arithmetic (NO eval)
=======================================================
A tiny AST-based expression evaluator so the model can compute EXACTLY instead of
guessing numbers in its head — the missing counterpart to the CVL ArithmeticValidator
(CVL catches a wrong number; this prevents one). Deterministic, model-free, stdlib
only (Constitution Article VIII — never eval()/exec()).

Whitelist only: + - * / // % **, unary ±, parentheses, a fixed set of math
functions and constants. Anything else raises MathError. Guards against runaway
exponent/factorial so it can never hang or blow up memory.

Reusable: a future CVL equation validator can recompute with evaluate() too.
License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import ast
import math
import operator
from typing import Any


class MathError(Exception):
    """Raised for anything outside the safe arithmetic whitelist."""


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "round": round, "floor": math.floor,
    "ceil": math.ceil, "exp": math.exp, "log": math.log, "log10": math.log10,
    "log2": math.log2, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "min": min, "max": max, "pow": pow, "factorial": math.factorial,
    "gcd": math.gcd, "hypot": math.hypot, "degrees": math.degrees,
    "radians": math.radians,
}
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}

# Runaway guards — a calculator must never hang or exhaust memory.
_MAX_EXP = 1_000
_MAX_FACT = 1_000


def _preprocess(expr: str) -> str:
    expr = (expr or "").strip()
    if not expr:
        raise MathError("empty expression")
    # Strip thousands separators (1,200 → 1200) but ONLY at parenthesis depth 0,
    # where a comma cannot be a function-argument separator (and tuples are
    # disallowed). Inside a call — min(1,200), hypot(3,4) — the comma is kept.
    out = []
    depth = 0
    for i, ch in enumerate(expr):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            prev = expr[i - 1] if i > 0 else ""
            grp = expr[i + 1:i + 4]                       # the 3 chars after the comma
            after = expr[i + 4] if i + 4 < len(expr) else ""
            if prev.isdigit() and len(grp) == 3 and grp.isdigit() and not after.isdigit():
                continue                                   # a thousands separator → drop
        out.append(ch)
    return "".join(out)


def _eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):          # numbers only
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise MathError(f"disallowed constant: {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp):
        op = _BIN.get(type(node.op))
        if op is None:
            raise MathError(f"operator not allowed: {type(node.op).__name__}")
        a, b = _eval(node.left), _eval(node.right)
        if type(node.op) is ast.Pow and (abs(b) > _MAX_EXP or abs(a) > 1e12):
            raise MathError("exponent too large")
        if type(node.op) in (ast.Div, ast.FloorDiv, ast.Mod) and b == 0:
            raise MathError("division by zero")
        return op(a, b)
    if isinstance(node, ast.UnaryOp):
        op = _UNARY.get(type(node.op))
        if op is None:
            raise MathError(f"unary operator not allowed: {type(node.op).__name__}")
        return op(_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise MathError(f"function not allowed: {getattr(node.func, 'id', '?')}")
        if node.keywords:
            raise MathError("keyword arguments are not allowed")
        fn = _FUNCS[node.func.id]
        args = [_eval(a) for a in node.args]
        if node.func.id == "factorial" and (not args or args[0] > _MAX_FACT or args[0] < 0):
            raise MathError("factorial out of range")
        return fn(*args)
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise MathError(f"unknown name: {node.id}")
    raise MathError(f"disallowed syntax: {type(node).__name__}")


def evaluate(expr: str) -> float:
    """Evaluate a whitelisted arithmetic expression. Raises MathError otherwise."""
    src = _preprocess(expr)
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise MathError(f"cannot parse: {e.msg}")
    return _eval(tree)


def fmt(x: Any) -> str:
    """Human-readable result: integers without a trailing .0, else 10 sig figs."""
    try:
        if isinstance(x, bool):
            return str(x)
        if isinstance(x, int):
            return str(x)
        if isinstance(x, float) and x == int(x) and abs(x) < 1e15:
            return str(int(x))
        return f"{x:.10g}"
    except Exception:
        return str(x)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ok = [("1200*5", 6000), ("1,200 * 5", 6000), ("(3+4)/2", 3.5),
          ("10/100*500", 50), ("sqrt(144)", 12), ("2**10", 1024),
          ("min(1,200)", 1), ("max(3, 9, 4)", 9), ("factorial(5)", 120),
          ("1,200 * 5 + sqrt(144)", 6012), ("1,200,000 / 1000", 1200)]
    for expr, want in ok:
        got = evaluate(expr)
        assert abs(got - want) < 1e-9, f"{expr} → {got} != {want}"
        print(f"  {expr:16} = {fmt(got)}")
    for bad in ["__import__('os')", "1+", "open('x')", "2**999999", "1/0",
                "factorial(99999)", "x+1", "[1,2]"]:
        try:
            evaluate(bad); raise AssertionError(f"{bad} should have failed")
        except MathError:
            pass
    print("self-test OK — exact arithmetic, thousands separators, safe rejects")
