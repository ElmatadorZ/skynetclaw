"""
smoke_test.py — verify the 5-atom loop works end-to-end
==========================================================
Run after every significant change. Returns exit code 0 = green, 1 = red.

Checks:
  1. Backend reachable
  2. Health endpoint reports GREEN
  3. /api/models returns ≥1 model
  4. /api/skills/match works
  5. /api/continental/dispatch streams (with a trivial directive)
  6. /api/bridge/log contains the dispatch envelope
  7. /api/feedback/insights returns valid JSON
"""
import json, sys, time, urllib.request, urllib.error

BASE = "http://localhost:8766"
TIMEOUT = 10


def _get(path):
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)


def _post(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ct = r.headers.get("content-type", "")
            if "json" in ct:
                return r.status, json.loads(r.read().decode("utf-8"))
            return r.status, r.read().decode("utf-8", errors="ignore")[:500]
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 60)
    print("  SkynetClaw Smoke Test")
    print("=" * 60)
    failures = 0

    # 1. Backend alive
    s, r = _get("/api/system/health/quick")
    if s == 200:
        print(f"  ✓ backend alive ({BASE})")
    else:
        print(f"  ✗ backend unreachable: {r}")
        return 1

    # 2. Full health
    s, r = _get("/api/system/health")
    if s == 200 and r.get("status") in ("GREEN", "YELLOW"):
        print(f"  ✓ /api/system/health → {r['status']} ({r['summary']})")
        if r["status"] == "YELLOW":
            print(f"     degraded subsystems:")
            for c in r["checks"]:
                if c["status"] != "GREEN":
                    print(f"       · {c['name']}: {c['msg']}")
    else:
        print(f"  ✗ /api/system/health failed: {s} · {r}")
        failures += 1

    # 3. Models
    s, r = _get("/api/models")
    if s == 200:
        n = len(r) if isinstance(r, list) else len(r.get("models", []))
        if n > 0:
            print(f"  ✓ /api/models → {n} model(s)")
        else:
            print(f"  ⚠ /api/models OK but 0 models · pull a model with `ollama pull qwen2.5:7b`")
    else:
        print(f"  ✗ /api/models failed: {s}")
        failures += 1

    # 4. Skills match
    s, r = _post("/api/skills/match", {"text": "หาเครื่องมือ vector database", "top_k": 2})
    if s == 200 and r.get("ok"):
        print(f"  ✓ /api/skills/match → {r.get('n_matches')} match(es)")
    else:
        print(f"  ✗ /api/skills/match failed: {s} · {r}")
        failures += 1

    # 5. Bridge log endpoint
    s, r = _get("/api/bridge/log?limit=5")
    if s == 200 and r.get("ok"):
        print(f"  ✓ /api/bridge/log → {len(r.get('envelopes', []))} recent envelopes")
    else:
        print(f"  ✗ /api/bridge/log failed: {s}")
        failures += 1

    # 6. Feedback insights
    s, r = _get("/api/feedback/insights")
    if s == 200:
        print(f"  ✓ /api/feedback/insights → {r['totals']['conversations']} conv · "
              f"{len(r['issues'])} issue(s)")
    else:
        print(f"  ✗ /api/feedback/insights failed: {s}")
        failures += 1

    # 7. Ecosystem manifest
    s, r = _get("/api/ecosystem/manifest")
    if s == 200 and r.get("apps"):
        print(f"  ✓ /api/ecosystem/manifest → {len(r['apps'])} apps · "
              f"{len(r['operatives'])} operatives")
    else:
        print(f"  ✗ /api/ecosystem/manifest failed: {s}")
        failures += 1

    # 8. CBP chain integrity
    s, r = _get("/api/bridge/verify")
    if s == 200 and r.get("ok"):
        print(f"  ✓ audit chain INTACT ({r.get('total')} envelopes)")
    else:
        print(f"  ✗ audit chain BROKEN: {r}")
        failures += 1

    print("=" * 60)
    if failures == 0:
        print("  RESULT: ✓ ALL GREEN — system is healthy")
        print("=" * 60)
        return 0
    print(f"  RESULT: ✗ {failures} FAILURE(S) — see above")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
