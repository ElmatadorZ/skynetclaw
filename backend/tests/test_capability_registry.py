"""
test_capability_registry.py — Capability-Skill Architecture (CSA v1)
====================================================================
Deterministic, offline. Locks the overhaul that replaced keyword
auto-injection with capability resolution + runtime discovery:

  * Thai design brief resolves design.frontend and binds frontend-design
    (the DCA-dashboard failure mode: Thai briefs never activated design skills).
  * Benign Thai inputs (g4 golden set) activate NOTHING.
  * Budget law: total injected chars <= ACTIVATION_BUDGET (16k ceiling).
  * Primary/card shape: exactly one full body, cards teach use_skill().
  * find_skills is bilingual and ranked; skill_body returns real playbooks.

    python backend/tests/test_capability_registry.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import capability_skill_registry as C

FAILED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def t1_thai_design_brief_activates_design():
    print("== T1: Thai design brief -> design capability ==")
    q = "ปรับปรุง UI dashboard ให้สวยงามและใช้งานได้จริง"
    caps = [c["capability"] for c in C.resolve(q)]
    check("resolves design.frontend", "design.frontend" in caps, str(caps))
    msgs = C.activate_for_task(q)
    names = [m["skill_meta"]["name"] for m in msgs]
    check("binds frontend-design", "frontend-design" in names, str(names))
    check("binds web-dashboard-builder", "web-dashboard-builder" in names, str(names))


def t2_no_false_positives():
    print("== T2: benign inputs activate nothing (g4 golden) ==")
    for q in ("สวัสดีครับ สบายดีไหม", "ช่วยคำนวณ 15 คูณ 3 หน่อย",
              "วันนี้อยากกินอะไรดี"):
        caps = C.resolve(q)
        check(f"no capability for {q[:16]!r}", not caps,
              str([c["capability"] for c in caps]))


def t3_budget_law():
    print("== T3: budget law ==")
    for q in ("ปรับปรุง UI dashboard ให้สวยงาม", "debug this traceback",
              "find a tool for vector database", "ออกแบบหน้าเว็บ landing page"):
        msgs = C.activate_for_task(q)
        total = sum(len(m["content"]) for m in msgs)
        check(f"{q[:24]!r} within budget", total <= C.ACTIVATION_BUDGET,
              f"{total}/{C.ACTIVATION_BUDGET}")


def t4_primary_and_cards():
    print("== T4: one primary + teaching cards ==")
    msgs = C.activate_for_task("ปรับปรุง UI dashboard ให้สวยงาม")
    modes = [m["skill_meta"].get("mode") for m in msgs]
    check("exactly one primary", modes.count("primary") == 1, str(modes))
    cards = [m for m in msgs if m["skill_meta"].get("mode") == "card"]
    check("cards teach use_skill", all("use_skill" in m["content"] for m in cards),
          f"{len(cards)} card(s)")


def t5_find_and_use():
    print("== T5: runtime discovery ==")
    hits = C.find_skills("ออกแบบหน้าเว็บให้สวย")
    names = [h["name"] for h in hits]
    check("thai find ranks design skills",
          bool(names) and names[0] in ("frontend-design", "web-dashboard-builder"),
          str(names))
    hits_en = C.find_skills("debug stack trace root cause")
    check("english find ranks debugging",
          bool(hits_en) and hits_en[0]["name"] == "systematic-debugging",
          str([h["name"] for h in hits_en]))
    body = C.skill_body("frontend-design")
    check("skill_body returns playbook", len(body) > 500, f"{len(body)} chars")
    check("skill_body caps at PRIMARY_BODY_CAP",
          len(body) <= C.PRIMARY_BODY_CAP + 100, f"{len(body)}")


def t6_architecture_tree():
    print("== T6: architecture tree ==")
    arch = C.architecture()
    check("has capabilities", arch["n_capabilities"] >= 10, str(arch["n_capabilities"]))
    caps = {c["capability"]: c for c in arch["capabilities"]}
    fe = caps.get("design.frontend", {})
    check("design.frontend lists skills",
          any(s["name"] == "frontend-design" for s in fe.get("skills", [])),
          str([s["name"] for s in fe.get("skills", [])]))


def main() -> int:
    C.build_index()
    for fn in (t1_thai_design_brief_activates_design, t2_no_false_positives,
               t3_budget_law, t4_primary_and_cards, t5_find_and_use,
               t6_architecture_tree):
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"harness error: {type(e).__name__}: {e}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())
