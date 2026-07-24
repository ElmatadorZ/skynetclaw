"""
security_regression_test.py — regression tests for the QA critical fixes
(C1 unauthenticated RCE / network exposure, C2 secret exfiltration,
C3 path traversal / workspace escape).

Run offline unit tests only:      python security_regression_test.py
Run incl. live HTTP tests:        (start backend first) python security_regression_test.py --http
"""
import os, sys, tempfile

BASE = "http://127.0.0.1:8766"
_fail = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        _fail.append(name)


# ── C3: _resolve_path confinement (offline unit test) ────────────────────────
def test_resolve_path():
    print("C3 — _resolve_path workspace confinement")
    import importlib
    main = importlib.import_module("main")
    ws = tempfile.mkdtemp(prefix="skynet_ws_")
    main.ACTIVE_WORKSPACE.set(str(main.Path(ws).resolve()))
    wsr = main.Path(ws).resolve()

    inside = main._resolve_path("notes.txt")
    check("relative stays inside", str(inside).startswith(str(wsr)), str(inside))

    esc = main._resolve_path("../../../../Windows/System32/evil.txt")
    check("dot-dot traversal clamped inside", str(esc).startswith(str(wsr)) and "System32" not in str(esc), str(esc))

    absout = main._resolve_path("C:/Windows/System32/evil.txt" if os.name == "nt" else "/etc/passwd")
    check("absolute-outside clamped inside", str(absout).startswith(str(wsr)), str(absout))

    absin = main._resolve_path(str(wsr / "sub" / "ok.txt"))
    check("absolute-inside preserved", str(absin).startswith(str(wsr)), str(absin))


# ── C1 / C2: live HTTP behavior ──────────────────────────────────────────────
def test_http():
    print("C1/C2 — live HTTP guards")
    try:
        import requests
    except ImportError:
        import urllib.request, urllib.error, json as _json
        class _R:  # minimal shim
            @staticmethod
            def request(method, url, headers=None, json=None):
                data = _json.dumps(json).encode() if json is not None else None
                req = urllib.request.Request(url, data=data, method=method,
                                             headers={**(headers or {}), **({"Content-Type": "application/json"} if data else {})})
                try:
                    r = urllib.request.urlopen(req, timeout=8)
                    return r.getcode(), r.read().decode("utf-8", "replace")
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode("utf-8", "replace")
                except Exception as e:                       # connection refused / DNS / timeout
                    return 0, f"UNREACHABLE: {e.__class__.__name__}"
        def _do(m, p, headers=None, json=None): return _R.request(m, BASE + p, headers, json)
    else:
        def _do(m, p, headers=None, json=None):
            try:
                r = requests.request(m, BASE + p, headers=headers, json=json, timeout=8)
                return r.status_code, r.text
            except Exception as e:                           # never stack-trace on a down server
                return 0, f"UNREACHABLE: {e.__class__.__name__}"

    # Fail clearly (not a stack trace) when the backend isn't running.
    probe, _ = _do("GET", "/api/connections")
    if probe == 0:
        check("backend reachable for HTTP tests", False, "server not running at " + BASE)
        return

    code, _ = _do("POST", "/api/shell", json={"command": "echo pwned", "cwd": "."})
    check("C1 /api/shell disabled by default (403)", code == 403, f"got {code}")

    code, _ = _do("POST", "/api/code/run", json={"code": "print(1)"})
    check("C1 /api/code/run disabled by default (403)", code == 403, f"got {code}")

    code, body = _do("GET", "/api/connections")
    check("C2 /api/connections returns 200", code == 200, f"got {code}")
    check("C2 api_key is masked (no long raw secret)", ("…" in body or '"api_key":""' in body or '"api_key":"***"' in body), body[:200])

    code, _ = _do("GET", "/api/connections", headers={"Origin": "https://evil.example"})
    check("C1 foreign-Origin request blocked (403)", code == 403, f"got {code}")

    code, _ = _do("GET", "/api/connections", headers={"Origin": "null"})
    check("C1 file:// SPA (Origin null) still allowed", code == 200, f"got {code}")


if __name__ == "__main__":
    test_resolve_path()
    if "--http" in sys.argv:
        test_http()
    else:
        print("(skipping live HTTP tests; pass --http with the backend running)")
    print()
    if _fail:
        print(f"RESULT: {len(_fail)} FAILED — {_fail}")
        sys.exit(1)
    print("RESULT: ALL PASS")
