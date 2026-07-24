"""
task_planner.py — the Planning runtime bridge (Vol IV, made runnable)
====================================================================
The failure this fixes (reproduced): asked to "build a DCA dashboard", the weak
local model streamed ~200 lines of HTML into the chat, never saved it, then across
turns regenerated inconsistently and finally halted ("PLAN เปล่า"). The task was
bigger than one reliable generation, and nothing decomposed it, allocated rounds,
built it piece by piece, or assembled + saved the result.

This is the Vol IV bridge: Plan = Commitment (the goal) ⊕ Dependency (ordered
sections) ⊕ Irreversibility (a written artifact), with temporal order induced by
the section order. It:
  1. DECOMPOSE — one planning call turns the task into 3–6 ordered file sections.
  2. EXECUTE per round — each round the model refines the WHOLE file to add one
     section; budgeted to the connection's window (Vol: resolve_window). An
     anti-drop guard rejects a round that truncates prior content.
  3. ASSEMBLE + WRITE — the planner (not the flaky model) writes the final file
     deterministically, so "the model wouldn't call write_file" can't happen.
  4. VERIFY + SUMMARIZE — the artifact is checked and reported.

Decoupled for testability: the LLM is injected as `call_llm(messages) -> str`
(one completion, no tools); the caller (main.py) wires it to the House's router.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

CallLLM = Callable[[List[Dict[str, str]]], Awaitable[str]]

_CODE_BLOCK = re.compile(r"```[a-zA-Z0-9_+\-]*\s*\n(.*?)```", re.S)
_FILE_IN_TASK = re.compile(r"([\w\-]+\.(?:html?|jsx?|tsx?|py|css|md|json|txt|vue|svelte))", re.I)


def extract_code(text: str) -> str:
    """Largest fenced code block, else the raw text."""
    blocks = _CODE_BLOCK.findall(text or "")
    if blocks:
        return max(blocks, key=len).strip()
    return (text or "").strip()


def _insert_before(html: str, marker: str, ins: str) -> str:
    idx = html.lower().rfind(marker.lower())
    if idx == -1:
        return html + "\n" + ins
    return html[:idx] + ins + "\n" + html[idx:]


def merge_fragment(artifact: str, frag: str) -> Optional[str]:
    """Merge a model-produced FRAGMENT into the current HTML artifact at a sensible
    place — a weak model reliably emits one focused piece but not the whole growing
    file, so the planner does the assembly. Returns the grown artifact, or None if
    the fragment is trivial/unmergeable."""
    frag = (frag or "").strip()
    if len(frag) < 8:
        return None
    low = frag.lower()
    is_css = ("{" in frag and "}" in frag and "<" not in frag)
    if "<script" in low:
        return _insert_before(artifact, "</body>", frag)
    if is_css:
        if "</style>" in artifact:
            return artifact.replace("</style>", frag + "\n</style>", 1)
        return _insert_before(artifact, "</head>", f"<style>\n{frag}\n</style>")
    if low.startswith("<") or any(t in low for t in ("<div", "<canvas", "<table", "<form", "<section", "<h1", "<input", "<button")):
        return _insert_before(artifact, "</body>", frag)
    if any(k in frag for k in ("function", "const ", "let ", "var ", "=>", "document.")):
        return _insert_before(artifact, "</body>", f"<script>\n{frag}\n</script>")
    return _insert_before(artifact, "</body>", frag)


def artifact_filename(task: str) -> str:
    """Deterministic output filename for a build task."""
    t = (task or "")
    m = _FILE_IN_TASK.search(t)
    if m:
        return m.group(1)
    tl = t.lower()
    if any(k in tl for k in ("html", "dashboard", "หน้าเว็บ", "เว็บ", "page", "landing", "แดชบอร์ด")):
        return "dashboard.html"
    if "python" in tl or ".py" in tl or "สคริปต์" in tl:
        return "script.py"
    return "artifact.txt"


def looks_like_build_task(task: str) -> bool:
    """Conservative detector for 'build a single-file artifact' tasks — used for
    auto-routing. Requires a build verb AND an artifact noun (avoids false positives
    on questions / research / chat)."""
    t = (task or "").lower()
    verb = any(v in t for v in ("build", "create", "make", "generate", "สร้าง", "ทำ", "เขียน", "ออกแบบ"))
    noun = any(n in t for n in ("dashboard", "html", "หน้าเว็บ", "เว็บ", "webpage", "page", "app",
                                "แดชบอร์ด", "landing", "ui", "หน้า", "calculator", "เครื่องคิดเลข",
                                "report", "รายงาน", "form", "ฟอร์ม", "chart", "กราф", "กราฟ")) or bool(_FILE_IN_TASK.search(task or ""))
    return verb and noun and len(t) > 12


async def decompose(task: str, call_llm: CallLLM, max_sections: int = 6) -> List[Dict[str, str]]:
    """Turn a build task into 3–6 ordered file sections (the Plan). Robust JSON
    parse with a generic fallback so a bad planner reply never blocks the build."""
    sys = ("You are a build planner. Break the user's BUILD task into 3 to 6 ordered sections "
           "of ONE single file, each a coherent buildable piece (e.g. structure, styles, core "
           "logic, data/rendering, finalize). Return ONLY a compact JSON array of objects with "
           "keys \"title\" and \"instruction\". No prose, no code fences — JSON only.")
    try:
        out = await call_llm([{"role": "system", "content": sys}, {"role": "user", "content": task}])
        s = out[out.index("["): out.rindex("]") + 1]
        arr = json.loads(s)
        steps = [{"title": str(x.get("title", "") or "")[:80],
                  "instruction": str(x.get("instruction", "") or "")[:300]}
                 for x in arr if isinstance(x, dict)]
        steps = [s for s in steps if s["title"]][:max_sections]
        if len(steps) >= 2:
            return steps
    except Exception:
        pass
    return [
        {"title": "Complete minimal working version",
         "instruction": "produce a complete, valid, runnable first version of the whole file"},
        {"title": "Full logic and content",
         "instruction": "implement all required functionality, calculations, and content"},
        {"title": "Rendering / visuals",
         "instruction": "add any charts, tables, or visual output the task asks for"},
        {"title": "Polish and finalize",
         "instruction": "handle edge cases and finalize; ensure the file is complete and valid"},
    ]


async def plan_and_execute(task: str, workspace: Optional[str], call_llm: CallLLM,
                           filename: Optional[str] = None, max_sections: int = 6,
                           lang: Optional[str] = None):
    """Async generator of SSE-shaped dict events. Decompose -> per-round build ->
    assemble+write -> verify. The final 'plan_complete' event carries the result."""
    plan = await decompose(task, call_llm, max_sections)
    yield {"type": "plan_decomposed", "steps": [s["title"] for s in plan], "n": len(plan)}

    fn = filename or artifact_filename(task)
    lang_hint = lang or ("HTML" if fn.lower().endswith((".html", ".htm"))
                         else ("Python" if fn.lower().endswith(".py") else "code"))
    build_sys = (f"You are an expert builder producing ONE complete {lang_hint} file. "
                 "Always output the ENTIRE file in a single fenced code block — never a fragment, "
                 "never prose, never omit content that already exists.")
    artifact = ""
    is_html = lang_hint == "HTML"
    for i, step in enumerate(plan, 1):
        yield {"type": "plan_step_start", "step": i, "of": len(plan), "title": step["title"]}
        accepted = False
        if not artifact:
            usr = (f"BUILD TASK:\n{task}\n\nProduce the COMPLETE, VALID, runnable first version of the "
                   f"single {lang_hint} file, focused on: {step['title']} — {step['instruction']}.\n"
                   "Return ONLY the full file in one code block.")
            out = await call_llm([{"role": "system", "content": build_sys}, {"role": "user", "content": usr}])
            code = extract_code(out)
            if len(code) >= 40:
                artifact = code; accepted = True
            elif not (out or "").strip():
                # the model returned nothing at all → almost always the execution
                # runtime is down/overloaded. Fail clearly instead of looping empty.
                yield {"type": "plan_error",
                       "error": "the model returned no output — the execution runtime may be down "
                                "or overloaded (check :8080 / the active connection)."}
                yield {"type": "plan_complete", "ok": False, "file": None, "chars": 0,
                       "steps": len(plan), "summary": "aborted: model unavailable (no output)."}
                return
        else:
            # weak models won't reliably re-emit the whole growing file, so ask for the
            # FRAGMENT and merge it here. (A model that returns a whole file is still
            # accepted, guarded against truncation.)
            usr = (f"BUILD TASK:\n{task}\n\nA file is being built. Provide ONLY the code to ADD for this "
                   f"section: {step['title']} — {step['instruction']}.\n"
                   + ("Return just the fragment (the <style> rules, the <script> block, or the extra "
                      "HTML) in one code block — NOT the whole file, no prose."
                      if is_html else
                      "Return just the additional code in one code block — no prose."))
            out = await call_llm([{"role": "system", "content": build_sys}, {"role": "user", "content": usr}])
            code = extract_code(out)
            low = code.lower()
            if "<html" in low or "<!doctype" in low:            # a whole-file return
                if len(code) >= max(40, int(len(artifact) * 0.9)):
                    artifact = code; accepted = True
            elif is_html:                                        # a fragment → merge
                merged = merge_fragment(artifact, code)
                if merged and len(merged) > len(artifact) + 15:
                    artifact = merged; accepted = True
            else:                                                # non-html: append growth
                if len(code) >= 15:
                    artifact = (artifact + "\n" + code).strip(); accepted = True
        yield {"type": "plan_step_done", "step": i, "title": step["title"],
               "chars": len(artifact), "accepted": accepted}

    out_path = str(Path(workspace) / fn) if workspace else fn
    written = False
    try:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(artifact, encoding="utf-8")
        written = True
    except Exception as e:
        yield {"type": "plan_error", "error": f"write failed: {str(e)[:120]}"}

    ok = written and len(artifact) > 200
    yield {"type": "plan_complete", "ok": ok, "file": out_path if written else None,
           "chars": len(artifact), "steps": len(plan),
           "summary": (f"Built {fn} ({len(artifact)} chars) across {len(plan)} planned sections."
                       if ok else f"Build incomplete ({len(artifact)} chars).")}
