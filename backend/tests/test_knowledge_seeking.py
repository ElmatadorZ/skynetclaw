"""
test_knowledge_seeking.py — OX-KNOWLEDGE-1 Knowledge Seeking Engine (model-free)
Covers the three spec validations:
  A — known capability → NO knowledge search.
  B — missing capability → knowledge sources are searched.
  C — unavailable information → clarification ONLY after discovery fails.
Plus the source registry, KNOWN/KNOWABLE/UNKNOWN split, and search-first gate.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import knowledge_seeking as KS

_TOOLS = ["list_files", "find_files", "read_file", "grep_search", "write_file",
          "web_search", "http_request", "search_obsidian", "read_obsidian_note",
          "shell_command", "recall_archive", "query_learning", "ask_user_options"]
# Portable: the repository root, whatever machine this runs on.
_WS = str(Path(__file__).resolve().parents[2])
_VAULT = "D:/Genesis Obsidian"


def _plan(task, **kw):
    return KS.plan(task, available_tools=_TOOLS, workspace=_WS, vault=_VAULT, **kw)


def test_source_registry_complete():
    ids = {s["id"] for s in KS.describe_sources()}
    # the seven spec source types are all registered
    assert {"skills", "artifacts", "workspace", "obsidian", "github",
            "documentation", "code"} <= ids
    for s in KS.describe_sources():
        assert s["tools"] and s["how"]


def test_A_known_capability_no_search():
    """Test A — a task whose capability exists and whose target is concrete is
    KNOWN: no gap, no knowledge search, no clarification, empty brief."""
    p = _plan(f"List the files in {_WS}/backend")
    assert p["known"] is True
    assert p["knowable"] == [] and p["unknown"] == []
    assert p["needs_search"] is False
    assert KS.should_clarify(p) is False          # before
    assert KS.render_brief(p) == ""               # no noise


def test_B_missing_capability_searches_sources():
    """Test B — a task needing absent knowledge yields KNOWABLE gaps routed to
    real sources; the House must SEARCH (not ask)."""
    p = _plan("Integrate the Stripe payment API into our checkout flow")
    assert p["known"] is False
    assert p["knowable"], "should detect a knowable gap"
    assert p["needs_search"] is True
    order = KS.acquisition_order(p)
    assert order, "an ordered search plan must exist"
    srcs = {s["source"] for s in order}
    assert srcs & {"documentation", "github", "code"}
    # search-first: it does NOT clarify before discovery
    assert KS.should_clarify(p) is False
    brief = KS.render_brief(p)
    assert "KNOWABLE" in brief and "SEARCH before you ask" in brief


def test_C_clarify_only_after_discovery_fails():
    """Test C — info that is missing is searched FIRST; clarification happens
    only once discovery returns nothing."""
    p = _plan("Summarize the figures from the previous quarterly report")
    assert p["knowable"], "prior-artifact reference is a knowable gap"
    # BEFORE discovery: must not ask — search first
    assert KS.should_clarify(p, discovered=None) is False
    # discovery runs and finds nothing for the gap(s)
    found_nothing = {g["need"]: False for g in p["knowable"] + p["unknown"]}
    assert KS.should_clarify(p, discovered=found_nothing) is True
    # discovery succeeds → no clarification
    found_all = {g["need"]: True for g in p["knowable"] + p["unknown"]}
    assert KS.should_clarify(p, discovered=found_all) is False


def test_operator_only_secret_is_unknown_but_searched_first():
    """A secret has no authoritative source, but the engine still routes a
    best-effort discovery pass before justifying a question."""
    p = _plan("Deploy using the production database password")
    assert any(g["operator_only"] for g in p["unknown"])
    # if a discovery source is reachable, do not ask pre-search
    if p["needs_search"]:
        assert KS.should_clarify(p, discovered=None) is False


def test_no_source_reachable_asks_immediately():
    """When nothing is reachable, asking is the only remaining move."""
    p = KS.plan("which format do you prefer?", available_tools=[], workspace=None, vault=None)
    # a pure preference with no reachable source → clarify is justified up front
    if p["unknown"] and not p["needs_search"]:
        assert KS.should_clarify(p) is True


def test_known_fact_suppresses_gap():
    """A gap already covered by a known fact is not re-sought."""
    p = _plan("research the Stripe API",
              known_facts=["external system / API knowledge: Stripe uses bearer-token auth"])
    # the known fact text contains the need fragment → suppressed
    assert all(g["need"] != "external system / API knowledge" for g in p["knowable"])
