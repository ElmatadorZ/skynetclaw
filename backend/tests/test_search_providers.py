"""
test_search_providers.py — deterministic, OFFLINE tests for the Search Provider Layer.

Verifies the Operational-Infrastructure invariants of the web_search refactor
(Commander ruling 2026-07-21) WITHOUT any network call:

  1. Output format is byte-identical to the legacy web_search line shape.
  2. Router returns the FIRST non-empty provider and preserves order.
  3. Keyed providers are skipped (not errored) when their env key is absent —
     so the no-key path is identical to pre-refactor behaviour.
  4. Keyed providers become available (and go first) when a key is present.
  5. Total failure yields [] + an error per attempted provider (fuel for the
     handler's anti-fabrication FAILED message) — never fabricated results.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")  # cp1252 guard (production discipline)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import search_providers as sp


# ── fakes (no network) ─────────────────────────────────────────────────────────
class _Ok(sp.SearchProvider):
    def __init__(self, name, items):
        self.name = name; self.short = name; self._items = items
    def search(self, query, n, q_enc):
        return self._items[:n], self.name


class _Boom(sp.SearchProvider):
    def __init__(self, name):
        self.name = name; self.short = name
    def search(self, query, n, q_enc):
        raise RuntimeError("dead")


def _swap(providers):
    saved = sp.PROVIDERS[:]
    sp.PROVIDERS[:] = providers
    return saved


# ── tests ───────────────────────────────────────────────────────────────────────
def test_format_is_byte_identical_to_legacy():
    line = sp.format_results([{"title": "Foo", "url": "http://x", "snippet": "bar"}])[0]
    assert line == "1. **Foo**\n   🔗 http://x\n   bar"


def test_format_tag_and_truncation():
    it = {"title": "T", "url": "u" * 200, "snippet": "s" * 300, "tag": "Wikipedia EN"}
    line = sp.format_results([it])[0]
    assert line.startswith("1. **T** [Wikipedia EN]\n")
    assert ("u" * 140) in line and ("u" * 141) not in line     # url[:140]
    assert ("s" * 240) in line and ("s" * 241) not in line     # snippet[:240]


def test_router_returns_first_nonempty_in_order():
    saved = _swap([
        _Boom("A"),
        _Ok("B", [{"title": "hit", "url": "http://b", "snippet": "s"}]),
        _Ok("C", [{"title": "later", "url": "http://c", "snippet": "s"}]),
    ])
    try:
        results, source, errors = sp.search("q", 6)
        assert source == "B"
        assert results == ["1. **hit**\n   🔗 http://b\n   s"]
        assert errors == ["A: RuntimeError: dead"]        # earlier failure recorded, not fatal
    finally:
        _swap(saved)


def test_total_failure_yields_no_results_and_errors():
    saved = _swap([_Boom("A"), _Boom("B")])
    try:
        results, source, errors = sp.search("q", 6)
        assert results == [] and source == ""
        assert len(errors) == 2                           # one per attempted provider — anti-fabrication fuel
    finally:
        _swap(saved)


def test_keyed_providers_skipped_without_env_key():
    for var in ("BRAVE_SEARCH_API_KEY", "TAVILY_API_KEY", "SERPER_API_KEY"):
        os.environ.pop(var, None)
    assert BraveApiAvailable() is False
    assert sp.configured() == []                          # no-key path == legacy free-only path


def BraveApiAvailable():
    return sp.BraveApiProvider().available()


def test_keyed_provider_available_and_first_when_key_present():
    os.environ["BRAVE_SEARCH_API_KEY"] = "test-key-not-real"
    try:
        assert sp.BraveApiProvider().available() is True
        assert "Brave API" in sp.configured()
        # in the real registry Brave API is index 0 → tried before any free provider
        assert sp.PROVIDERS[0].short == "BraveAPI"
    finally:
        os.environ.pop("BRAVE_SEARCH_API_KEY", None)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn(); passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} passed")
