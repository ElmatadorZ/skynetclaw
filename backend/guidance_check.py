"""
guidance_check.py — Vol V (Execution) runtime bridge: G1 GUIDANCE INVARIANT
===========================================================================
THEORY (docs/agency-theory vol5): what makes a behavior an ACTION — rather
than a mere event — is that it is caused by the intention IN THE RIGHT WAY
(guidance). Davidson's deviant chains are outcomes that satisfy the desire
without being guided by it. CEE's C1 (warrant_check) governs the REPORT side:
no claim without observation. G1 is its dual on the ACT side:

    G1 — no act on a target that has no provenance in the guiding context.

Operationally: a tool act whose TARGET (file path, URL, note) appears nowhere
in the mission, the agent's own prior words, or any prior tool result is an
UNGUIDED act — the loop invented a target to act on (also Constitution R8).
That is the deviant chain a runtime can actually catch: the act happened, it
may even "succeed", but nothing in the guiding intention named it.

Deterministic, model-free, post-hoc over the same event stream C1 reads.
Deliberately narrow: acts on provenanced targets never flag, tools without a
target argument never flag — false accusations would teach the loop to stop
declaring, which is the OPPOSITE of guidance.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

# tool arg keys that name the act's TARGET (what the act is done TO)
_TARGET_KEYS = ("path", "file_path", "filepath", "filename", "file", "rel_path",
                "url", "note", "folder", "target", "dest", "destination")

# acts that CREATE are exempt from provenance on their own output name when the
# mission asked for a creation generically ("save it as you see fit") — but a
# named target is still checked. Read-only acts are the risky ones to invent.
_WRITE_TOOLS = ("write_file", "edit_file", "create_folder", "obsidian_write_note",
                "write_obsidian_note", "copy_file", "move_file")

_TOKEN_RE = re.compile(r"[\w฀-๿.\-]+")


def _basename(target: str) -> str:
    t = str(target or "").replace("\\", "/").rstrip("/")
    return t.rsplit("/", 1)[-1].lower()


def _stem(name: str) -> str:
    return name.rsplit(".", 1)[0] if "." in name else name


def _targets_of(name: str, args: Any) -> List[str]:
    if not isinstance(args, dict):
        return []
    out = []
    for k in _TARGET_KEYS:
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def check_guidance(task: str, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scan an agent event stream for G1 violations.

    events: ordered dicts shaped like the trajectory —
      {"type": "text"|"think", "text": ...}
      {"type": "tool_call", "name": ..., "args": {...}}
      {"type": "tool_result", "name": ..., "result": "..."}

    Returns [{"rule": "G1", "tool", "target", "reason"}] — acts whose target
    has no provenance in the mission or anything the loop saw or said first.
    """
    context = (task or "").lower()
    violations: List[Dict[str, Any]] = []
    for ev in events or []:
        et = ev.get("type", "")
        if et in ("text", "think", "agent_think"):
            context += "\n" + str(ev.get("text") or "").lower()
        elif et == "tool_result":
            context += "\n" + str(ev.get("result") or "")[:4000].lower()
        elif et in ("tool_call", "tool"):
            name = str(ev.get("name") or "")
            for target in _targets_of(name, ev.get("args")):
                base = _basename(target)
                if not base or len(base) < 3:
                    continue
                # provenance: the full target, its basename, or its stem was
                # named by the mission, the loop's own words, or a prior result
                if (target.lower() in context or base in context
                        or (_stem(base) and len(_stem(base)) >= 3 and _stem(base) in context)):
                    pass
                else:
                    violations.append({
                        "rule": "G1", "tool": name, "target": target,
                        "reason": ("act on unprovenanced target — nothing in the mission, "
                                   "the loop's own declarations, or prior observations "
                                   "named it (deviant chain / invented target)"),
                    })
            # the act itself becomes context for later acts (args + name)
            try:
                context += "\n" + name.lower() + " " + json.dumps(ev.get("args") or {},
                                                                  ensure_ascii=False).lower()
            except Exception:
                pass
    return violations


def format_violations(violations: List[Dict[str, Any]]) -> str:
    if not violations:
        return ""
    lines = ["⚠ G1 GUIDANCE — act(s) on targets nothing guided:"]
    for v in violations[:5]:
        lines.append(f"  · {v['tool']} → {v['target']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    evs = [
        {"type": "text", "text": "จะเขียนสรุปลง report.md ตามที่สั่ง"},
        {"type": "tool_call", "name": "write_file", "args": {"path": "ws/report.md", "content": "x"}},
        {"type": "tool_call", "name": "read_file", "args": {"path": "C:/secrets/creds.txt"}},
    ]
    v = check_guidance("สรุปข่าวลงไฟล์ report.md", evs)
    print(json.dumps(v, ensure_ascii=False, indent=1))
    assert len(v) == 1 and v[0]["target"].endswith("creds.txt")
    print("self-test OK — guided act passed, invented target flagged")
