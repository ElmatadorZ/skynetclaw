"""
makruk/board.py — Thai Chess (Makruk) board & pieces
====================================================
Single responsibility: represent the 8x8 board, the pieces, the initial Makruk
setup, and (de)serialization. No move logic here.

Squares are 0..63, sq = rank*8 + file. rank 0 = White's first rank (rank "1").
White moves toward higher ranks; Black toward lower.

Pieces are 2-char strings: color ∈ {w,b}, kind ∈
    K Khun (king) · M Met (counselor, moves 1 diagonally) · B Khon (bishop:
    1 diagonal + 1 straight-forward) · N Ma (knight) · R Ruea (rook) ·
    P Bia (pawn) · F promoted pawn (Bia-ngai — moves like Met).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import List, Optional, Tuple

FILES = "abcdefgh"
WHITE, BLACK = "w", "b"


def sq(file: int, rank: int) -> int:
    return rank * 8 + file


def file_of(s: int) -> int:
    return s % 8


def rank_of(s: int) -> int:
    return s // 8


def in_bounds(file: int, rank: int) -> bool:
    return 0 <= file < 8 and 0 <= rank < 8


def alg(s: int) -> str:
    return f"{FILES[file_of(s)]}{rank_of(s) + 1}"


def parse_alg(a: str) -> int:
    a = a.strip().lower()
    return sq(FILES.index(a[0]), int(a[1]) - 1)


def opponent(color: str) -> str:
    return BLACK if color == WHITE else WHITE


def forward(color: str) -> int:
    """Rank delta for a forward move."""
    return 1 if color == WHITE else -1


def promotion_rank(color: str) -> int:
    """0-indexed rank on which a pawn promotes (the opponent's pawn rank)."""
    return 5 if color == WHITE else 2


class Board:
    """A Makruk position (just the pieces)."""

    def __init__(self, squares: Optional[List[Optional[str]]] = None):
        self.squares: List[Optional[str]] = squares if squares is not None else [None] * 64

    # ── construction ──
    @classmethod
    def initial(cls) -> "Board":
        b = cls()
        # White back rank (rank 0): R N B K M B N R  (Khun d1, Met e1)
        white_back = ["R", "N", "B", "K", "M", "B", "N", "R"]
        # Black back rank (rank 7): R N B M K B N R  (Khun e8, Met d8)
        # Rotational (180°) symmetry, not mirror: White Khun d1 ↔ Black Khun e8.
        black_back = ["R", "N", "B", "M", "K", "B", "N", "R"]
        for f in range(8):
            b.squares[sq(f, 0)] = "w" + white_back[f]
            b.squares[sq(f, 2)] = "wP"                 # White pawns on rank 3
            b.squares[sq(f, 5)] = "bP"                 # Black pawns on rank 6
            b.squares[sq(f, 7)] = "b" + black_back[f]
        return b

    def clone(self) -> "Board":
        return Board(list(self.squares))

    # ── queries ──
    def piece_at(self, s: int) -> Optional[str]:
        return self.squares[s]

    def color_at(self, s: int) -> Optional[str]:
        p = self.squares[s]
        return p[0] if p else None

    def kind_at(self, s: int) -> Optional[str]:
        p = self.squares[s]
        return p[1] if p else None

    def set(self, s: int, piece: Optional[str]) -> None:
        self.squares[s] = piece

    def pieces(self, color: str) -> List[Tuple[int, str]]:
        return [(s, self.squares[s][1]) for s in range(64)
                if self.squares[s] and self.squares[s][0] == color]

    def king_sq(self, color: str) -> Optional[int]:
        target = color + "K"
        for s in range(64):
            if self.squares[s] == target:
                return s
        return None

    # ── serialization for the UI ──
    def to_rows(self) -> List[List[Optional[str]]]:
        """Rows top-to-bottom (rank 8 first) for rendering."""
        return [[self.squares[sq(f, r)] for f in range(8)] for r in range(7, -1, -1)]

    def to_dict(self) -> dict:
        return {alg(s): self.squares[s] for s in range(64) if self.squares[s]}
