"""
split_grid.py — split a 3x4 grid reference image into 12 OPV-XXX.png files

USAGE:
  1. Save your reference image (the 3x4 grid of 12 cards) as `source.png`
     in this folder.
  2. Run: python split_grid.py
  3. Output: OPV-001.png through OPV-012.png in this folder.

ASSUMES grid is roughly 4 cols x 3 rows of equal cells.
Override --gap if there's visible spacing between cards.
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("PIL/Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

HERE = Path(__file__).parent
SRC  = HERE / "source.png"

# Order matches the reference image layout: row-major, left-to-right, top-to-bottom
LAYOUT = [
    "OPV-001", "OPV-002", "OPV-003", "OPV-004",   # row 1
    "OPV-005", "OPV-006", "OPV-007", "OPV-008",   # row 2
    "OPV-009", "OPV-010", "OPV-011", "OPV-012",   # row 3
]
COLS, ROWS = 4, 3

def main():
    if not SRC.exists():
        print(f"[ERR] source.png not found at: {SRC}")
        print("      Save the reference image (3x4 grid of 12 cards) as 'source.png' here.")
        sys.exit(1)

    img = Image.open(SRC).convert("RGB")
    W, H = img.size
    cw = W / COLS
    ch = H / ROWS
    print(f"[INFO] source: {W}x{H}  -> cell {cw:.0f}x{ch:.0f}")

    # Optional trim — if your grid has even gutters, set gap > 0
    gap_x = int(cw * 0.02)   # 2% margin trim per cell
    gap_y = int(ch * 0.02)

    for idx, code in enumerate(LAYOUT):
        col = idx % COLS
        row = idx // COLS
        x0 = int(col * cw) + gap_x
        y0 = int(row * ch) + gap_y
        x1 = int((col + 1) * cw) - gap_x
        y1 = int((row + 1) * ch) - gap_y

        crop = img.crop((x0, y0, x1, y1))
        # ensure 4:5 aspect ratio expected by the UI — center-crop if needed
        cw2, ch2 = crop.size
        target_ratio = 4 / 5
        cur_ratio = cw2 / ch2
        if cur_ratio > target_ratio:
            # too wide — trim sides
            new_w = int(ch2 * target_ratio)
            left = (cw2 - new_w) // 2
            crop = crop.crop((left, 0, left + new_w, ch2))
        elif cur_ratio < target_ratio:
            # too tall — trim top/bottom
            new_h = int(cw2 / target_ratio)
            top = (ch2 - new_h) // 2
            crop = crop.crop((0, top, cw2, top + new_h))

        out = HERE / f"{code}.png"
        crop.save(out, "PNG", optimize=True)
        print(f"  [OK] {out.name}  {crop.size[0]}x{crop.size[1]}")

    print(f"\n[DONE] 12 portrait files written to: {HERE}")
    print("       Refresh agent_room.html — UI auto-detects them.")

if __name__ == "__main__":
    main()
