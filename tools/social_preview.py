#!/usr/bin/env python3
"""
social_preview.py — generate the repository's social preview card.

GitHub renders this image whenever the repository is linked anywhere: X,
LinkedIn, Slack, Discord, a chat message. Without one, a link that took months
of work to earn shows a grey placeholder and the owner's avatar.

The card is generated rather than drawn by hand so it can be regenerated when
the claims on it change -- and so the claims on it stay checkable, which is the
whole disposition of this project.

    python tools/social_preview.py

Writes docs/assets/social-preview.png at 1280x640 (GitHub's recommended size;
it renders the card at 2:1 and crops nothing at that ratio). Upload it under
Settings -> General -> Social preview.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

W, H = 1280, 640
OUT = Path(__file__).resolve().parent.parent / "docs" / "assets" / "social-preview.png"

# GitHub's own dark canvas, so the card sits in the page rather than on top of it.
BG = (13, 17, 23)
PANEL = (22, 27, 34)
GOLD = (212, 160, 23)
TEXT = (240, 240, 240)
MUTED = (139, 148, 158)
GREEN = (46, 160, 67)
LINE = (48, 54, 61)

FONTS = Path("C:/Windows/Fonts")
_FALLBACK = ["/usr/share/fonts/truetype/dejavu", "/System/Library/Fonts"]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by Windows filename, falling back to whatever the platform has."""
    p = FONTS / name
    if p.exists():
        return ImageFont.truetype(str(p), size)
    for d in _FALLBACK:
        for cand in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "DejaVuSansMono.ttf"):
            q = Path(d) / cand
            if q.exists():
                return ImageFont.truetype(str(q), size)
    return ImageFont.load_default()


def _loop(d: ImageDraw.ImageDraw, x0: int, x1: int, top: int) -> None:
    """The one thing that distinguishes this from a chat transcript: the loop
    closes. A verdict becomes a prediction, the prediction is graded against
    what actually happened, and the grade revises what the House believes.
    Drawn with primitives rather than arrow glyphs, which not every font has."""
    f = font("segoeui.ttf", 17)
    steps = ("deliberate", "predict", "grade", "revise")
    h, gap = 30, 20
    w = x1 - x0

    for i, label in enumerate(steps):
        y = top + i * (h + gap)
        d.rounded_rectangle([x0, y, x1, y + h], radius=6, fill=PANEL, outline=LINE)
        tw = d.textlength(label, font=f)
        d.text((x0 + (w - tw) / 2, y + 7), label, font=f, fill=TEXT)

        if i < len(steps) - 1:
            cx, ay = x0 + w / 2, y + h
            d.line([(cx, ay), (cx, ay + gap - 7)], fill=GOLD, width=2)
            d.polygon([(cx - 4, ay + gap - 8), (cx + 4, ay + gap - 8), (cx, ay + gap - 1)],
                      fill=GOLD)

    # The return edge: what a system without memory does not have.
    bottom = top + (len(steps) - 1) * (h + gap) + h
    rx = x1 + 14
    d.line([(x1, bottom - h / 2), (rx, bottom - h / 2)], fill=GOLD, width=2)
    d.line([(rx, bottom - h / 2), (rx, top + h / 2)], fill=GOLD, width=2)
    d.line([(rx, top + h / 2), (x1 + 8, top + h / 2)], fill=GOLD, width=2)
    d.polygon([(x1 + 9, top + h / 2 - 4), (x1 + 9, top + h / 2 + 4), (x1 + 1, top + h / 2)],
              fill=GOLD)

    cap = "the loop closes"
    fc = font("segoeui.ttf", 16)
    cw = d.textlength(cap, font=fc)
    d.text((x0 + (w - cw) / 2, bottom + 16), cap, font=fc, fill=GOLD)


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    f_title = font("seguibl.ttf", 76)
    f_sub = font("segoeuib.ttf", 30)
    f_body = font("segoeui.ttf", 25)
    f_mono = font("consola.ttf", 21)
    f_mono_b = font("consolab.ttf", 21)
    f_small = font("segoeui.ttf", 20)

    # A single gold rule down the left edge: the accent used across the ecosystem.
    d.rectangle([0, 0, 10, H], fill=GOLD)

    x = 74
    y = 70

    d.text((x, y), "SkynetClaw", font=f_title, fill=TEXT)
    tw = d.textlength("SkynetClaw", font=f_title)
    d.text((x + tw + 24, y + 26), "· THE HOUSE", font=f_sub, fill=GOLD)

    y += 102
    d.text((x, y), "An institutional-intelligence operating system", font=f_sub, fill=MUTED)

    y += 58
    for line in (
        "A council of 14 agents that remembers every deliberation, grades its own",
        "predictions against reality, and revises what it believes.",
    ):
        d.text((x, y), line, font=f_body, fill=TEXT)
        y += 36

    _loop(d, x0=986, x1=1166, top=88)

    # The proof panel. These are the numbers CI re-establishes on every push --
    # if one of them stops being true, this card is wrong and should be regenerated.
    py0 = 316
    d.rounded_rectangle([x, py0, W - 74, py0 + 128], radius=10, fill=PANEL, outline=LINE)

    cells = [
        ("709", "tests"),
        ("272", "routes"),
        ("91", "tools"),
        ("14", "council"),
        ("6", "CI matrix"),
    ]
    cw = (W - 74 - x) / len(cells)
    for i, (n, label) in enumerate(cells):
        cx = x + cw * i + cw / 2
        nw = d.textlength(n, font=font("seguibl.ttf", 40))
        d.text((cx - nw / 2, py0 + 26), n, font=font("seguibl.ttf", 40), fill=GOLD)
        lw = d.textlength(label, font=f_small)
        d.text((cx - lw / 2, py0 + 80), label, font=f_small, fill=MUTED)
        if i:
            d.line([(x + cw * i, py0 + 24), (x + cw * i, py0 + 104)], fill=LINE, width=1)

    # Runtime line, in monospace because it is a fact about the machine.
    y = 478
    d.text((x, y), "local-first", font=f_mono_b, fill=GREEN)
    off = d.textlength("local-first", font=f_mono_b)
    d.text((x + off, y), "  ·  Ollama · llama.cpp · any OpenAI-compatible API",
           font=f_mono, fill=MUTED)

    y += 34
    d.text((x, y), "FastAPI + SQLite  ·  Python 3.10+  ·  no build step  ·  Apache-2.0",
           font=f_mono, fill=MUTED)

    # Footer rule and the line the whole project turns on.
    d.line([(x, 556), (W - 74, 556)], fill=LINE, width=1)
    d.text((x, 578), "Models are temporary. Protocols endure.", font=f_body, fill=MUTED)
    url = "github.com/ElmatadorZ/skynetclaw"
    uw = d.textlength(url, font=f_mono)
    d.text((W - 74 - uw, 582), url, font=f_mono, fill=GOLD)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    kb = OUT.stat().st_size / 1024
    print(f"  wrote {OUT.relative_to(OUT.parent.parent.parent)}  {W}x{H}  {kb:.0f} KB")
    if kb > 1024:
        print("  WARNING: GitHub rejects social previews larger than 1 MB")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
