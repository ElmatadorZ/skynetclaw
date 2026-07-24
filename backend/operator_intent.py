"""
operator_intent.py — THE OPERATOR INTENT ENGINE for THE HOUSE
============================================================
The House understands tasks. It does not yet understand the Operator.

Short directives — "ไหนอะ", "ดูดิ", "อันนี้", "ตัวนี้", "ลองคิดดู" — are not
missing requirements. They are anaphoric: the Operator is pointing at something
already in the shared working context. The naive system treats them as ambiguous
and stops. That is wrong.

MISSION: recover probable intent from working context BEFORE declaring ambiguity.

Inputs (OperatorContext):
  directive · recent_conversation · mission · workspace · active_agent ·
  house_state · recent_deliberation

Output (RecoveredIntent):
  recovered_intent · confidence (0–100) · assumptions · clarification_need
  (+ intent_type, anchor, anchor_source, clarification_question)

RULE (enforced): a short/deictic directive is first run through contextual
recovery. Only if no context anchor exists — or recovery confidence is too low —
is clarification requested. Even then a best-guess intent is always returned.

This module is PURE: `recover()` needs no DB. `from_house()` is a convenience
that pulls house_state + recent sessions so the engine is House-aware without
being wired into the deliberation flow.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── thresholds (tunable) ───────────────────────────────────────────────────────
ACT_CONF = 70          # ≥ this: proceed on recovered intent, no clarification
SOFT_CONF = 50         # ≥ this but < ACT_CONF: proceed but state assumptions
CONF_CAP = 98          # never claim certainty on an inferred intent
SHORT_TOKENS = 4       # directives this short are candidates for recovery

# ── intent types ───────────────────────────────────────────────────────────────
LOCATION = "LOCATION"      # "where is it" — asking for a location / result
DISPLAY = "DISPLAY"        # "show me" — reveal / open an artifact
REFERENCE = "REFERENCE"    # "this / that one" — deixis pointing at a referent
ELABORATE = "ELABORATE"    # "think about it / try" — reason further
CONTINUE = "CONTINUE"      # "go on / next" — resume the previous action
CONFIRM = "CONFIRM"        # "right? really?" — verify a prior statement
FULL = "FULL"              # a self-contained directive; taken at face value

# Deictic / anaphoric markers (Thai + English). Order = match priority.
_MARKERS: List[tuple] = [
    (LOCATION,  re.compile(r"(ไหน|อยู่ไหน|ที่ไหน|ตรงไหน|\bwhere\b|\bwhich\b|\blocation\b)", re.I)),
    (DISPLAY,   re.compile(r"(ดูดิ|ดูสิ|ดูหน่อย|^ดู|\bดู\b|แสดง|เปิด|โชว์|\bshow\b|\blook\b|\bopen\b|\breveal\b|\bdisplay\b)", re.I)),
    (ELABORATE, re.compile(r"(ลองคิด|คิดดู|ลองดู|^ลอง|วิเคราะห์|\btry\b|\bthink\b|\belaborate\b|\bexpand\b|\banalyse\b|\banalyze\b)", re.I)),
    (CONTINUE,  re.compile(r"(ต่อเลย|ทำต่อ|^ต่อ|\bต่อ\b|แล้วไง|\bcontinue\b|\bnext\b|\bgo on\b|\bproceed\b)", re.I)),
    (CONFIRM,   re.compile(r"(ใช่ไหม|ใช่มั้ย|จริงเหรอ|จริงดิ|แน่ใจ|\breally\b|\bsure\b|\bcorrect\?|\bright\?)", re.I)),
    (REFERENCE, re.compile(r"(อันนี้|อันนั้น|ตัวนี้|ตัวนั้น|นี่|นั่น|มัน|\bthis one\b|\bthat one\b|\bthis\b|\bthat\b|\bit\b)", re.I)),
]

# Mission verbs that COHERE with each intent type (raises confidence when the
# active mission's verb agrees with what the short directive is asking for).
_COHERENCE: Dict[str, re.Pattern] = {
    LOCATION:  re.compile(r"(find|locate|search|discover|where|scan|hunt|ค้นหา|หา|ค้น)", re.I),
    DISPLAY:   re.compile(r"(show|render|build|generate|create|draw|produce|map|report|สร้าง|ทำ|วาด)", re.I),
    ELABORATE: re.compile(r"(analy[sz]e|think|plan|assess|evaluate|deliberat|design|วิเคราะห์|คิด|วางแผน)", re.I),
    CONTINUE:  re.compile(r"(.*)", re.I),     # continuation coheres with any active mission
    REFERENCE: re.compile(r"(.*)", re.I),
    CONFIRM:   re.compile(r"(.*)", re.I),
}

# Leading verbs stripped to expose the object of a mission ("Find Blueprint
# Files" → "blueprint files").
_LEAD_VERB = re.compile(
    r"^\s*(find|locate|search( for)?|discover|show|build|generate|create|draw|map|"
    r"analy[sz]e|assess|evaluate|plan|review|ค้นหา|หา|ค้น|สร้าง|ทำ|ดู|วิเคราะห์)\s+", re.I)

_WORD = re.compile(r"[\w฀-๿]+")


def _tokens(s: str) -> List[str]:
    return [t for t in _WORD.findall(s or "") if t.strip()]


def _object_of(mission: str) -> str:
    """The thing a mission acts on: 'Find Blueprint Files' → 'blueprint files'."""
    m = (mission or "").strip()
    obj = _LEAD_VERB.sub("", m).strip()
    return (obj or m).lower()


def _phrase(s: str, n: int = 80) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())[:n]


# ── context container ──────────────────────────────────────────────────────────
@dataclass
class OperatorContext:
    directive: str = ""
    recent_conversation: List[str] = field(default_factory=list)
    mission: str = ""
    workspace: str = ""                       # cwd / focused file / artifact name
    active_agent: str = ""
    house_state: Optional[Dict[str, Any]] = None   # house_state.read_state(...) shape
    recent_deliberation: List[Dict[str, Any]] = field(default_factory=list)


# ── anchor resolution ──────────────────────────────────────────────────────────
def _anchors(ctx: OperatorContext) -> List[Dict[str, str]]:
    """Salient context objects the Operator could be pointing at, most-trusted
    first. Each anchor carries a weight used in confidence scoring."""
    out: List[Dict[str, str]] = []

    # 1) the subject of the most recent deliberation — strongest "current focus"
    for d in (ctx.recent_deliberation or [])[:1]:
        subj = d.get("directive") or d.get("question") or d.get("verdict")
        if subj:
            out.append({"text": _phrase(subj), "source": "recent_deliberation", "weight": "0.12"})

    # 2) the active mission
    if ctx.mission:
        out.append({"text": _phrase(ctx.mission), "source": "mission", "weight": "0.20"})

    # 3) the House Mind's current question / belief
    hs = ctx.house_state or {}
    q = hs.get("question")
    if q:
        out.append({"text": _phrase(q), "source": "house_state", "weight": "0.10"})

    # 4) the last salient line of conversation
    for line in reversed(ctx.recent_conversation or []):
        if line and len(_tokens(line)) >= 2:
            out.append({"text": _phrase(line), "source": "conversation", "weight": "0.05"})
            break

    # 5) the focused workspace artifact
    if ctx.workspace:
        out.append({"text": _phrase(ctx.workspace), "source": "workspace", "weight": "0.05"})

    return out


# ── directive classification ───────────────────────────────────────────────────
def classify(directive: str) -> tuple:
    """Return (intent_type, marker_clarity 0..1, is_short).

    Short = few tokens. A directive is treated as deictic when it is short AND/OR
    carries a deixis marker; a long, self-contained directive is FULL."""
    text = (directive or "").strip()
    toks = _tokens(text)
    is_short = len(toks) <= SHORT_TOKENS

    matched = None
    for itype, pat in _MARKERS:
        if pat.search(text):
            matched = itype
            break

    if matched is None:
        return (FULL, 1.0, is_short)

    # Marker clarity: a short directive dominated by the marker is an unambiguous
    # signal; a marker buried in a long directive is weaker (it may be a real task).
    if is_short:
        clarity = 1.0
    elif len(toks) <= SHORT_TOKENS * 2:
        clarity = 0.6
    else:
        # long directive that merely contains a deictic word → treat as FULL
        return (FULL, 1.0, False)
    return (matched, clarity, is_short)


# ── intent phrasing ────────────────────────────────────────────────────────────
def _compose(intent_type: str, anchor: Optional[Dict[str, str]], mission: str) -> str:
    if anchor is None:
        base = {
            LOCATION:  "User is asking where something is, but no current focus is on record.",
            DISPLAY:   "User wants to see something, but no artifact is on record to show.",
            ELABORATE: "User wants the House to reason further, but no current topic is on record.",
            CONTINUE:  "User wants to continue, but no previous action is on record.",
            CONFIRM:   "User is asking to confirm something, but no prior statement is on record.",
            REFERENCE: "User is pointing at something, but no referent is on record.",
            FULL:      "Directive is self-contained.",
        }
        return base.get(intent_type, "Intent unclear; no context anchor available.")

    a = anchor["text"]
    obj = _object_of(mission) if (mission and anchor["source"] == "mission") else a
    if intent_type == LOCATION:
        return f"User is likely asking for the location/result of the {obj} (from: {a})."
    if intent_type == DISPLAY:
        return f"User likely wants to see / open {a}."
    if intent_type == ELABORATE:
        return f"User likely wants the House to reason further about {a}."
    if intent_type == CONTINUE:
        return f"User likely wants to continue the previous action on {a}."
    if intent_type == CONFIRM:
        return f"User likely wants to verify the prior conclusion about {a}."
    if intent_type == REFERENCE:
        return f"User is likely referring to {a} (most recent salient item)."
    return _phrase(mission) or a


# ── the engine ─────────────────────────────────────────────────────────────────
@dataclass
class RecoveredIntent:
    directive: str
    intent_type: str
    recovered_intent: str
    confidence: int                       # 0..100
    assumptions: List[str]
    clarification_need: bool
    clarification_question: str = ""
    anchor: str = ""
    anchor_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directive": self.directive,
            "intent_type": self.intent_type,
            "recovered_intent": self.recovered_intent,
            "confidence": self.confidence,
            "assumptions": self.assumptions,
            "clarification_need": self.clarification_need,
            "clarification_question": self.clarification_question,
            "anchor": self.anchor,
            "anchor_source": self.anchor_source,
        }


def recover(ctx: OperatorContext) -> RecoveredIntent:
    """Recover probable operator intent from working context.

    A self-contained directive is taken at face value. A short/deictic directive
    is resolved against context anchors (per the RULE) and only escalated to a
    clarification request when recovery confidence is too low."""
    directive = (ctx.directive or "").strip()
    intent_type, clarity, is_short = classify(directive)

    # 1) self-contained directive → face value, high confidence, no clarification
    if intent_type == FULL:
        if not directive:
            return RecoveredIntent(
                directive, FULL, "No directive provided.", 0, ["empty directive"],
                clarification_need=True,
                clarification_question="What would you like the House to do?")
        return RecoveredIntent(
            directive, FULL, _phrase(directive, 200), 90,
            ["directive is self-contained; taken at face value"],
            clarification_need=False)

    # 2) contextual recovery (the RULE: try before declaring ambiguity)
    anchors = _anchors(ctx)
    top = anchors[0] if anchors else None

    score = 0.0
    assumptions: List[str] = []
    if top is not None:
        score = 0.30                                  # floor for a grounded recovery
        score += 0.30 * clarity                       # how clean the deixis signal is
        # anchor mass (corroboration), capped
        score += min(0.40, sum(float(a["weight"]) for a in anchors))
        # coherence: does the active mission's verb agree with the asked intent?
        cohere = _COHERENCE.get(intent_type)
        if ctx.mission and cohere and cohere.search(ctx.mission):
            score += 0.07
            assumptions.append(
                f"Assumed '{directive}' refers to the active mission "
                f"'{_phrase(ctx.mission)}' (intent and mission cohere).")
        else:
            assumptions.append(
                f"Assumed '{directive}' points at the most salient context: "
                f"{top['text']} (via {top['source']}).")
        if ctx.active_agent:
            assumptions.append(f"Resolved in the working context of agent '{ctx.active_agent}'.")
    else:
        # no anchor at all → genuine ambiguity
        score = 0.18 * clarity
        assumptions.append("No context anchor was available to resolve the reference.")

    confidence = min(CONF_CAP, int(round(score * 100)))
    recovered = _compose(intent_type, top, ctx.mission)

    need = confidence < ACT_CONF
    question = ""
    if need:
        if top is not None:
            question = (f"By '{directive}', do you mean {recovered.rstrip('.')}? "
                        f"(recovered with {confidence}% confidence)")
        else:
            question = f"By '{directive}', what are you referring to? No current focus is on record."
        if confidence >= SOFT_CONF:
            assumptions.append("Confidence is moderate — proceeding on the recovered intent, "
                               "but confirm if this is wrong.")

    return RecoveredIntent(
        directive, intent_type, recovered, confidence, assumptions,
        clarification_need=need, clarification_question=question,
        anchor=top["text"] if top else "", anchor_source=top["source"] if top else "")


# ── House-aware convenience (pulls live context without wiring) ─────────────────
def from_house(directive: str, mission: str = "", workspace: str = "",
               active_agent: str = "", recent_conversation: Optional[List[str]] = None,
               path: Optional[str] = None) -> RecoveredIntent:
    """Build an OperatorContext from the House's own memory (current House Mind +
    recent council sessions) and recover intent. Read-only; no deliberation wiring."""
    house_state = None
    recent: List[Dict[str, Any]] = []
    try:
        import house_state as _hs
        house_state = _hs.current(path)
    except Exception:
        house_state = None
    try:
        import council_memory as _cm
        recent = _cm.recent(limit=5, path=path)
    except Exception:
        recent = []
    # fall back to the House Mind's question as mission when none is supplied
    if not mission and house_state:
        mission = house_state.get("question", "") or ""
    ctx = OperatorContext(
        directive=directive, recent_conversation=recent_conversation or [],
        mission=mission, workspace=workspace, active_agent=active_agent,
        house_state=house_state, recent_deliberation=recent)
    return recover(ctx)


def format_for_council(ri: RecoveredIntent) -> str:
    """Render a recovered intent for injection ahead of deliberation (optional)."""
    L = ["## OPERATOR INTENT (recovered from working context)",
         f"Directive: \"{ri.directive}\"  →  {ri.intent_type}",
         f"Recovered intent: {ri.recovered_intent}",
         f"Confidence: {ri.confidence}%"]
    if ri.anchor:
        L.append(f"Anchor: {ri.anchor}  (via {ri.anchor_source})")
    if ri.assumptions:
        L.append("Assumptions:")
        L.extend(f"  • {a}" for a in ri.assumptions)
    if ri.clarification_need:
        L.append(f"⚠ Clarification advised: {ri.clarification_question}")
    else:
        L.append("Proceeding on the recovered intent (confidence sufficient).")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    demo = recover(OperatorContext(directive="ไหนอะ", mission="Find Blueprint Files"))
    print(format_for_council(demo))
    print("\nconfidence:", demo.confidence, "| need_clarify:", demo.clarification_need)
