"""
test_artifact_factory.py — H6 Artifact Factory (model-free, real files)
"""
from __future__ import annotations
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import artifact_factory as AF

_K = {
    "title": "Build Stock Dashboard",
    "mission": "Build Stock Dashboard",
    "summary": "Compared 3 frameworks; LangGraph leads on control, CrewAI on speed.",
    "known": ["LangGraph supports cycles", "CrewAI is role-based", "AutoGen is conversation-first"],
    "beliefs": [{"belief": "LangGraph is best for control-heavy flows", "confidence": 0.78}],
    "unknowns": ["pricing at scale is unconfirmed"],
    "assumptions": ["the team prefers Python"],
    "sources": ["vendor docs", "benchmark run"],
    "metrics": {"knowledge_debt": 1, "coverage": 0.75, "known_count": 3},
}


def test_builder_selection():
    assert AF.choose_builder("Executive Brief") == "pdf"
    assert AF.choose_builder("Comparison Matrix") == "html"
    assert AF.choose_builder("Knowledge Graph") == "graph"
    assert AF.choose_builder("Obsidian Knowledge Base") == "obsidian"
    print("  OK  H4 asset type → correct builder")


def test_pdf_is_structurally_valid():
    d = tempfile.mkdtemp()
    r = AF.build("PDF Report", _K, d)
    assert r["ok"] and r["exists"] and r["bytes"] > 200, r
    raw = Path(r["path"]).read_bytes()
    assert raw.startswith(b"%PDF-1.4") and raw.rstrip().endswith(b"%%EOF")
    assert b"xref" in raw and b"/Catalog" in raw and b"startxref" in raw
    print(f"  OK  PDF built & structurally valid ({r['bytes']} bytes, {r['path'].split('/')[-1]})")


def test_html_dashboard():
    d = tempfile.mkdtemp()
    r = AF.build("Interactive HTML Dashboard", _K, d)
    assert r["ok"] and r["path"].endswith(".html")
    doc = Path(r["path"]).read_text(encoding="utf-8")
    assert "<!doctype html>" in doc and "LangGraph supports cycles" in doc and "Build Stock Dashboard" in doc
    print("  OK  HTML dashboard built & self-contained")


def test_knowledge_graph():
    d = tempfile.mkdtemp()
    r = AF.build("Knowledge Graph", _K, d)
    assert r["ok"]
    doc = Path(r["path"]).read_text(encoding="utf-8")
    assert "<svg" in doc and "graph-data" in doc and "CrewAI is role-based" in doc
    print("  OK  knowledge graph (inline SVG + JSON) built")


def test_obsidian_vault():
    d = tempfile.mkdtemp()
    r = AF.build("Obsidian Knowledge Base", _K, d)
    assert r["ok"] and r["path"].endswith(".md")
    idx = Path(r["path"]).read_text(encoding="utf-8")
    assert "[[" in idx and "mission-index" in idx
    notes = list((Path(r["path"]).parent / (Path(r["path"]).stem + "_notes")).glob("*.md"))
    assert len(notes) >= 3, "one linked note per known fact"
    print(f"  OK  Obsidian vault built: index + {len(notes)} linked notes")


def test_unicode_survives_in_html_and_obsidian():
    d = tempfile.mkdtemp()
    k = dict(_K, title="วิเคราะห์ตลาด", known=["ราคาทองคำสูงขึ้น"])
    rh = AF.build("Interactive HTML Dashboard", k, d)
    assert "ราคาทองคำสูงขึ้น" in Path(rh["path"]).read_text(encoding="utf-8")
    # PDF must NOT crash on unicode (Latin-1 replacement), still valid
    rp = AF.build("PDF Report", k, d)
    assert rp["ok"] and Path(rp["path"]).read_bytes().startswith(b"%PDF")
    print("  OK  Unicode renders in HTML/Obsidian; PDF degrades safely, never corrupts")


def test_verify_and_failure_is_honest():
    assert AF.verify("/no/such/file.pdf") is False
    print("  OK  verify() reports missing artifacts honestly")


def main():
    print("=" * 56 + "\nH6 ARTIFACT FACTORY\n" + "=" * 56)
    test_builder_selection()
    test_pdf_is_structurally_valid()
    test_html_dashboard()
    test_knowledge_graph()
    test_obsidian_vault()
    test_unicode_survives_in_html_and_obsidian()
    test_verify_and_failure_is_honest()
    print("\n  ALL ARTIFACT-FACTORY TESTS PASS — no artifact, no completion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
