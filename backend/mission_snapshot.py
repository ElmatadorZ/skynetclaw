"""
mission_snapshot.py — MISSION SNAPSHOT / CONTEXT RECOVERY (Phase P0)
===================================================================
When the context budget goes critical, the agent loop must NOT halt. Instead it
compresses the conversation: the bulk of older raw tool output is replaced by a
compact, factual snapshot, while the system preamble and the most recent
messages are preserved so execution continues seamlessly.

EVERYTHING in the snapshot is extracted from REAL message content:
  Current Objective  <- the original user task message
  Completed Work     <- the tool names that actually ran (counted)
  Known Facts        <- the first meaningful line of each executed tool result
  Pending Questions  <- the DONE_WHEN criteria block if present

Nothing is summarised by an LLM, invented, or paraphrased beyond truncation.

compress(cur, keep_recent) -> (new_cur, snapshot_dict, dropped_count)

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from collections import Counter, OrderedDict
from typing import Any, Dict, List, Tuple

LEDGER_MARK = "[[SKYNET_LEDGER_v1]]"
SNAPSHOT_MARK = "[[MISSION_SNAPSHOT]]"
_DONE_WHEN = re.compile(r"DONE_WHEN[:\s]+(.+)", re.I)


def _content(m: Dict[str, Any]) -> str:
    c = m.get("content")
    return c if isinstance(c, str) else ("" if c is None else str(c))


def _first_fact(text: str) -> str:
    """First meaningful line of a tool result (skip markers / banners / brackets)."""
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s or s.startswith(("[", "─", "##", "STDOUT", "STDERR")):
            continue
        return s[:160]
    return ""


# ── EVIDENCE-DENSE fact extraction ───────────────────────────────────────────
# _first_fact keeps only the first 160 chars of a tool result. For directory
# listings and searches that is a warrant-losing bug: a `list_files` of a tests/
# folder returns a JSON array, and the test_*.py names live PAST char 160, so
# compression dropped them — the run then reported "no tests found / UNKNOWN"
# about files it had actually observed. Worse, find_files/grep results begin with
# "[", which _first_fact skips entirely, contributing NO fact at all. This
# extractor preserves the evidence that matters for exploration — the child NAMES
# — compactly (names only, not size/modified noise), so observed files survive
# the compression that the 16k-ceiling forces.
_NAME_RE = re.compile(r'"name"\s*:\s*"([^"]+)"')
_PATH_TOKEN_RE = re.compile(r'"([^"]*[\\/][^"]*)"')


def _tool_fact(name: str, text: str) -> str:
    """Evidence-dense one-liner for a tool result. Listing/search tools keep ALL
    observed child names; everything else falls back to _first_fact."""
    t = text or ""
    if name in ("list_files", "find_files", "grep_search", "read_file"):
        # list_files: JSON objects with "name" keys → names only, deduped
        names = _NAME_RE.findall(t)
        if not names:
            # find_files/grep: JSON array of path strings → basenames
            for p in _PATH_TOKEN_RE.findall(t):
                base = re.split(r"[\\/]", p.strip())[-1]
                if base:
                    names.append(base)
        if names:
            joined = ", ".join(dict.fromkeys(names))  # dedup, preserve order
            return joined[:600]
    return _first_fact(t)


_FACT_LINE_RE = re.compile(r"^- (.+)$")


def _carried_facts(snap_content: str) -> List[str]:
    """Recover the KNOWN FACTS already captured in a prior mission snapshot, so a
    SECOND compression accumulates evidence instead of dropping the first
    snapshot's facts (compress must be idempotent for long, multi-round runs)."""
    out: List[str] = []
    in_facts = False
    for ln in (snap_content or "").splitlines():
        s = ln.rstrip()
        if s.startswith("## KNOWN FACTS"):
            in_facts = True
            continue
        if in_facts:
            if s.startswith("## "):
                break
            m = _FACT_LINE_RE.match(s.strip())
            if m and "no textual facts captured" not in m.group(1):
                out.append(m.group(1))
    return out


def _extract_pending(cur: List[Dict[str, Any]]) -> str:
    for m in cur:
        c = _content(m)
        mt = _DONE_WHEN.search(c)
        if mt:
            return mt.group(1).strip()[:300]
    return ""


def compress(cur: List[Dict[str, Any]], keep_recent: int = 6
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], int]:
    """Compress the middle of `cur` into a factual snapshot. Returns the new
    message list, the snapshot dict, and how many messages were dropped."""
    cur = cur or []
    # 1) preserve leading system preamble verbatim
    i = 0
    leading_system: List[Dict[str, Any]] = []
    while i < len(cur) and cur[i].get("role") == "system" and SNAPSHOT_MARK not in _content(cur[i]):
        leading_system.append(cur[i])
        i += 1
    body = cur[i:]

    # the original objective = first non-ledger user message
    objective = ""
    for m in body:
        if m.get("role") == "user" and LEDGER_MARK not in _content(m) and SNAPSHOT_MARK not in _content(m):
            objective = _content(m).strip()
            break

    pending = _extract_pending(cur)

    if keep_recent > 0:
        recent = body[-keep_recent:]
        middle = body[:-keep_recent]
    else:
        recent, middle = [], body

    # 2) extract real facts + completed work from the dropped middle.
    #    A prior MISSION_SNAPSHOT in the middle carries facts from earlier
    #    compressions — recover them FIRST so evidence accumulates across rounds
    #    (idempotent compression), then add the new tool facts.
    tools_done: List[str] = []
    facts: "OrderedDict[str,str]" = OrderedDict()
    for m in middle:
        if m.get("role") == "system" and SNAPSHOT_MARK in _content(m):
            for f in _carried_facts(_content(m)):
                facts.setdefault(f, None)
        elif m.get("role") == "tool":
            nm = m.get("name", "tool") or "tool"
            tools_done.append(nm)
            fact = _tool_fact(nm, _content(m))
            if fact:
                facts[f"{nm}: {fact}"] = None
    tool_counts = Counter(tools_done)
    fact_list = list(facts.keys())[-60:]   # keep most recent distinct facts
                                           # (raised from 24: evidence-bearing
                                           # listings must survive multi-round runs)

    snapshot = {
        "objective": objective[:300],
        "completed": dict(tool_counts),
        "n_tool_calls": sum(tool_counts.values()),
        "facts": fact_list,
        "pending": pending,
        "dropped": len(middle),
    }

    completed_line = ", ".join(f"{k}×{v}" for k, v in tool_counts.items()) or "(none)"
    snap_text = (
        f"{SNAPSHOT_MARK} (context recovered — older raw tool output compressed; "
        "all facts below come from tools that actually ran)\n"
        f"## CURRENT OBJECTIVE\n{objective or '(see task above)'}\n\n"
        f"## COMPLETED WORK ({snapshot['n_tool_calls']} tool calls)\n{completed_line}\n\n"
        f"## KNOWN FACTS (from executed tools)\n"
        + ("\n".join(f"- {f}" for f in fact_list) if fact_list else "- (no textual facts captured)")
        + (f"\n\n## PENDING\n{pending}" if pending else "")
        + "\n\nContinue the mission from here. Do NOT repeat completed work; "
          "call the next needed tool or reply TASK_COMPLETE if DONE_WHEN holds."
    )
    snap_msg = {"role": "system", "content": snap_text}

    new_cur = leading_system + [snap_msg] + recent
    return new_cur, snapshot, len(middle)
