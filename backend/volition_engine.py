"""
volition_engine.py — programmatic L1 Volition extraction
=========================================================
The missing programmatic piece in SkynetClaw's Genesis Mind pipeline.

L0 Reality Anchor (skynetclaw_meta.reality_anchor)         — what's verifiable
L1 Volition Engine (THIS MODULE)                           — drive + tone + gap
L2 Shadow Genesis (in SOUL.md prompt)                      — frame critique
L4 Shadow Gate (skynetclaw_meta.shadow_gate)               — pre-exec block
L7 Echo Memory + Genome (skynetclaw_meta + atlas_genome)   — compound learning
L8 Synthesis (skynet_genesis_masterpiece.stage_l8)         — Money Atlas brief

What this gives the agent (per task):

    {
      "surface":        "the literal request",
      "drive":          "build" | "fix" | "decide" | "learn" | "validate"
                        | "vent"  | "explore" | "automate" | "escape" | "control",
      "drive_score":    {"build": 0.7, "decide": 0.3, ...},
      "emotional_tone": "analytical" | "anxious" | "excited" | "skeptical"
                        | "urgent"   | "neutral" | "frustrated",
      "tone_score":     {...},
      "urgency":        "low" | "medium" | "high",
      "gap_detected":   bool,
      "gap_note":       "surface asks for X but core drive is Y — surface that",
      "recommendation": short text to inject as system note
    }

Pure regex + keyword scoring. Zero LLM cost. Bilingual (Thai + English).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Lexicons — drive / tone / urgency markers (Thai + English)
# ──────────────────────────────────────────────────────────────────────────────
# Each entry: (regex_pattern, weight). Higher weight = stronger signal.
DRIVE_LEXICON: Dict[str, List[Tuple[str, float]]] = {
    "build": [
        (r"\b(build|create|make|generate|implement|develop|set\s*up|deploy)\b", 1.0),
        (r"\b(สร้าง|ทำ|พัฒนา|ติดตั้ง|deploy|เขียน(โค้ด|โปรแกรม))\b", 1.0),
        (r"\b(write|design)\s+(a|the|my)\s+(code|script|app|bot|module|file)", 1.0),
        (r"\b(ต้องการ|อยากได้)(ให้)?(สร้าง|ทำ|เขียน)\b", 0.8),
    ],
    "fix": [
        (r"\b(fix|repair|debug|resolve|patch|broken|not\s+work\w*|error|bug|issue|crash)\b", 1.0),
        (r"\b(แก้|ซ่อม|ดีบั๊ก|พัง|ใช้ไม่ได้|ไม่ทำงาน|error|บัค|มีปัญหา|พลาด|ผิด)\b", 1.0),
        (r"\b(why\s+is\s+this\s+(failing|broken|wrong))\b", 1.2),
    ],
    "decide": [
        (r"\b(should\s+i|which\s+(one|is\s+better)|choose|pick|decide|recommend|vs\.?|or)\s+", 1.0),
        (r"\b(ควร|ตัดสินใจ|เลือก|แนะนำ|ดีกว่า|หรือ)\b", 1.0),
        (r"\?\s*$", 0.3),  # ends with question mark — mild decide signal
    ],
    "learn": [
        (r"\b(explain|teach|how\s+does|what\s+is|tell\s+me|understand|learn|study)\b", 1.0),
        (r"\b(อธิบาย|สอน|คืออะไร|ยังไง|เพราะอะไร|ทำไม|รู้จัก|เรียน|ศึกษา)\b", 1.0),
    ],
    "validate": [
        (r"\b(is\s+this\s+(right|correct|ok|good)|am\s+i\s+correct|review|check\s+if)\b", 1.0),
        (r"\b(ถูกไหม|ใช่ไหม|ดีไหม|ตรวจสอบ|review|เช็ค)\b", 1.0),
    ],
    "vent": [
        (r"\b(frustrating|annoying|hate|sick\s+of|tired\s+of|why\s+won't|fed\s+up)\b", 1.0),
        (r"\b(เซ็ง|เหนื่อย|รำคาญ|เบื่อ|ทนไม่ไหว|ไม่ไหว|พอแล้ว)\b", 1.0),
    ],
    "explore": [
        (r"\b(what\s+if|maybe|could\s+we|brainstorm|ideas|possibilities|explore)\b", 1.0),
        (r"\b(ลอง|ถ้าหาก|จะเป็นไง|brainstorm|สำรวจ|ความเป็นไปได้)\b", 1.0),
    ],
    "automate": [
        (r"\b(automate|automatic|cron|schedule|every\s+\d|daily|hourly|recurring)\b", 1.0),
        (r"\b(อัตโนมัติ|ทุกวัน|ทุกชั่วโมง|ตั้งเวลา|cron|schedule|วน|ซ้ำ)\b", 1.0),
    ],
    "escape": [
        (r"\b(stop|cancel|abort|nevermind|forget\s+it|undo|revert)\b", 1.0),
        (r"\b(หยุด|ยกเลิก|ไม่เอาแล้ว|ลืมไปก่อน|ย้อน|undo)\b", 1.0),
    ],
    "control": [
        (r"\b(must|need\s+to|require|enforce|force|mandate|always|never|only)\b", 0.7),
        (r"\b(ต้อง|บังคับ|ต้องการให้|ห้าม|เท่านั้น|เสมอ|ห้ามใช้)\b", 0.7),
    ],
}

TONE_LEXICON: Dict[str, List[Tuple[str, float]]] = {
    "analytical": [
        (r"\b(analyze|because|therefore|since|hypothesis|verify|evidence|data)\b", 1.0),
        (r"\b(วิเคราะห์|เพราะ|ดังนั้น|สมมุติฐาน|verify|หลักฐาน|ข้อมูล)\b", 1.0),
    ],
    "anxious": [
        (r"\b(worry|worried|afraid|nervous|scared|concerned|risk|dangerous)\b", 1.0),
        (r"\b(กังวล|กลัว|เป็นห่วง|เสี่ยง|อันตราย|ไม่แน่ใจ|รู้สึกไม่ดี)\b", 1.0),
    ],
    "excited": [
        (r"\b(awesome|great|amazing|love\s+it|finally|let'?s\s+go)\b", 1.0),
        (r"\b(เจ๋ง|สุดยอด|เยี่ยม|รอ|ลุย|มาเลย)\b", 1.0),
        (r"!{2,}", 0.6),
    ],
    "skeptical": [
        (r"\b(really\?|are\s+you\s+sure|doubt|i\s+don'?t\s+think|seems\s+wrong)\b", 1.0),
        (r"\b(จริงเหรอ|แน่ใจ|สงสัย|ไม่น่า|ดูแปลก|ไม่เชื่อ|ว่าจริง)\b", 1.0),
    ],
    "urgent": [
        (r"\b(asap|urgent|now|immediately|right\s+now|hurry|quick)\b", 1.0),
        (r"\b(ด่วน|รีบ|เร็ว|เดี๋ยวนี้|ตอนนี้|เร่ง)\b", 1.0),
    ],
    "frustrated": [
        (r"\b(again\?|still|why\s+still|keeps\s+failing|broken\s+again)\b", 1.0),
        (r"\b(อีกแล้ว|ยังไม่ได้|พังอีก|ทำไมยัง|พลาดอีก)\b", 1.0),
    ],
    "neutral": [],  # default if nothing else scores
}

URGENCY_LEXICON: List[Tuple[str, str, float]] = [
    # (level, regex, weight)
    ("high",   r"\b(asap|urgent|right\s*now|immediately|ทันที|ด่วน|เดี๋ยวนี้|รีบ)\b", 1.0),
    ("high",   r"!{3,}|⏰|🚨", 0.8),
    ("medium", r"\b(today|tonight|วันนี้|คืนนี้|ในวันนี้)\b", 0.6),
    ("medium", r"\b(soon|เร็วๆ\s*นี้|ภายในวันนี้)\b", 0.5),
    ("low",    r"\b(eventually|whenever|no\s+rush|ไม่รีบ|ค่อย\s*ๆ|ไม่เร่ง)\b", 1.0),
]


# ──────────────────────────────────────────────────────────────────────────────
# Core types
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class VolitionResult:
    surface: str
    drive: str
    drive_score: Dict[str, float]
    emotional_tone: str
    tone_score: Dict[str, float]
    urgency: str
    gap_detected: bool
    gap_note: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────────
# Scoring + classification
# ──────────────────────────────────────────────────────────────────────────────
def _score_against_lexicon(text: str,
                           lex: Dict[str, List[Tuple[str, float]]]) -> Dict[str, float]:
    """Sum weights of matching patterns per category. Returns dict {cat: score}."""
    out: Dict[str, float] = {k: 0.0 for k in lex}
    for cat, patterns in lex.items():
        for pat, w in patterns:
            try:
                hits = re.findall(pat, text, re.IGNORECASE)
            except re.error:
                continue
            if hits:
                # log-ish saturation so 10 hits ≠ 10× weight
                n = min(len(hits), 5)
                out[cat] += w * (1.0 + 0.4 * (n - 1))
    return out


def _classify(scores: Dict[str, float], default: str) -> Tuple[str, float]:
    if not scores:
        return default, 0.0
    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] <= 0:
        return default, 0.0
    return best[0], best[1]


def _classify_urgency(text: str) -> str:
    bucket = {"high": 0.0, "medium": 0.0, "low": 0.0}
    for level, pat, w in URGENCY_LEXICON:
        if re.search(pat, text, re.IGNORECASE):
            bucket[level] += w
    # Prioritize by level then score
    if bucket["high"] >= 1.0:
        return "high"
    if bucket["low"] >= 1.0 and bucket["high"] <= 0:
        return "low"
    if bucket["medium"] >= 0.5 or bucket["high"] > 0:
        return "medium"
    return "low" if bucket["low"] > 0 else "medium" if bucket["medium"] > 0 else "low"


# ──────────────────────────────────────────────────────────────────────────────
# Gap detection (surface ≠ core drive)
# ──────────────────────────────────────────────────────────────────────────────
_GAP_HINTS = {
    # surface_drive  →  alt_drive  : how to interpret the gap
    ("validate", "decide"):
        "user is asking 'is this right?' but really wants permission to decide — surface the trade-offs",
    ("learn", "decide"):
        "user is asking 'how does X work' but really facing a decision — explain in choice-relevant terms",
    ("vent", "fix"):
        "user is venting but the task is actually a fixable problem — acknowledge feeling, then offer fix",
    ("vent", "validate"):
        "user is frustrated and wants validation more than a solution right now",
    ("explore", "decide"):
        "user is in brainstorm mode but a decision is implied — list options + recommend",
    ("control", "fix"):
        "user is asserting requirements; underlying need is to fix something previously unbounded",
    ("automate", "build"):
        "user wants automation; building the script is the prerequisite — propose both in order",
}


def _detect_gap(drive: str, drive_score: Dict[str, float],
                tone: str) -> Tuple[bool, str, str]:
    """Return (gap_detected, gap_note, recommendation)."""
    # No gap if there's a clear winner (top score >> second)
    sorted_scores = sorted(drive_score.items(), key=lambda x: -x[1])
    if len(sorted_scores) < 2:
        return False, "", ""
    top, second = sorted_scores[0], sorted_scores[1]
    # Gap = strong second contender (≥60% of winner) suggesting hidden core drive
    if second[1] <= 0 or top[1] <= 0:
        return False, "", ""
    if second[1] / top[1] < 0.6:
        return False, "", ""

    # Look up in gap hints; check both orderings
    hint = _GAP_HINTS.get((top[0], second[0])) or _GAP_HINTS.get((second[0], top[0]))
    if hint:
        rec = (
            f"Surface drive is **{top[0]}** but **{second[0]}** is close behind "
            f"(score {second[1]:.1f} vs {top[1]:.1f}). {hint}."
        )
        return True, hint, rec

    # Generic gap recommendation when no specific pattern matches
    rec = (
        f"Both **{top[0]}** ({top[1]:.1f}) and **{second[0]}** ({second[1]:.1f}) are strong. "
        f"Address both layers — don't pick one and ignore the other."
    )
    return True, f"dual drive: {top[0]} / {second[0]}", rec


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────
def extract(text: str) -> VolitionResult:
    """
    Extract L1 Volition signals from a user message.
    Pure-rule, no LLM. Always returns a result (never raises).
    """
    t = (text or "").strip()
    drive_scores = _score_against_lexicon(t, DRIVE_LEXICON)
    tone_scores  = _score_against_lexicon(t, TONE_LEXICON)
    drive, _ = _classify(drive_scores, default="explore")
    tone,  _ = _classify(tone_scores,  default="neutral")
    urgency = _classify_urgency(t)
    gap, note, rec = _detect_gap(drive, drive_scores, tone)
    return VolitionResult(
        surface=t[:200],
        drive=drive,
        drive_score={k: round(v, 2) for k, v in drive_scores.items() if v > 0},
        emotional_tone=tone,
        tone_score={k: round(v, 2) for k, v in tone_scores.items() if v > 0},
        urgency=urgency,
        gap_detected=gap,
        gap_note=note,
        recommendation=rec,
    )


def format_volition_directive(v: VolitionResult) -> str:
    """Render as a system-message that can be injected into agent_run prompt."""
    lines = [
        "## L1 VOLITION (programmatic — auto-extracted from this task):",
        f"  Drive          : {v.drive}",
        f"  Emotional tone : {v.emotional_tone}",
        f"  Urgency        : {v.urgency}",
    ]
    if v.gap_detected:
        lines.append(f"  ⚠ GAP DETECTED : {v.gap_note}")
        lines.append(f"  → Recommendation: {v.recommendation}")
        lines.append("")
        lines.append("Surface the gap explicitly in your response. The user's literal "
                     "request and underlying drive are not the same — address both.")
    else:
        lines.append(f"  Gap            : (none — surface and core drive aligned)")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Self-test  —  python volition_engine.py
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cases = [
        "สร้าง Telegram Bot ที่ D:\\Bot ทำให้เสร็จด่วนๆ",
        "BTC ตอนนี้ราคาเท่าไหร่?",
        "ผมอยากให้ระบบทำงานดีกว่านี้แต่สงสัยตัวเองด้วยว่าจะทำได้ไหม",
        "Why is this still broken? I've fixed it 3 times already",
        "Should I use nemotron3:33b or qwen3.5:9b for code review?",
        "Explain how OAuth works",
        "ลองคิดดูสิว่าจะ automate การส่งราคาทองทุกเช้ายังไง",
        "Stop the bot — มันส่ง message ผิด channel",
        "I want to be better, but I doubt my own intentions.",
    ]

    print("=== volition_engine self-test ===\n")
    for i, c in enumerate(cases, 1):
        v = extract(c)
        print(f"[{i}] {c[:70]}{'...' if len(c)>70 else ''}")
        print(f"    drive={v.drive:<10} tone={v.emotional_tone:<12} urgency={v.urgency:<6}"
              f"{' ⚠ GAP' if v.gap_detected else ''}")
        if v.gap_detected:
            print(f"    gap : {v.gap_note}")
        # Show top 3 drive scores
        top3 = sorted(v.drive_score.items(), key=lambda x: -x[1])[:3]
        print(f"    drive_scores: {top3}")
        print()

    # Demonstrate the Genesis Codex example case
    print("--- Genesis Codex example case ---")
    v = extract("I want to be better, but I doubt my own intentions.")
    print(format_volition_directive(v))
    print()
    print("=== self-test OK ===")
