"""Loot values and the attack filter (pure functions; reading lives in LootReader)."""

from __future__ import annotations

from dataclasses import dataclass

from cob.core.config import FarmConfig
from cob.vision.frame import Frame, Region
from cob.vision.ocr import DigitReader

KINDS = ("gold", "elixir", "dark")


@dataclass(frozen=True)
class Loot:
    gold: int
    elixir: int
    dark: int

    @property
    def gold_elixir(self) -> int:
        return self.gold + self.elixir

    def __str__(self) -> str:
        return f"gold {self.gold:,} elixir {self.elixir:,} dark {self.dark:,}"


def minimums(cfg: FarmConfig, nexts: int = 0) -> tuple[int, int]:
    """(gold + elixir, dark) minimums after `nexts` Nexts. #113 (MyBot's search reduction): every
    `reduce_every` Nexts both drop by `reduce_percent` % of the set values, down to `reduce_floor` %."""
    if cfg.reduce_every <= 0:
        return cfg.min_gold_elixir, cfg.min_dark
    percent = max(100 - nexts // cfg.reduce_every * cfg.reduce_percent, cfg.reduce_floor)
    return cfg.min_gold_elixir * percent // 100, cfg.min_dark * percent // 100


def worth_attacking(loot: Loot, cfg: FarmConfig, nexts: int = 0) -> bool:
    min_gold_elixir, min_dark = minimums(cfg, nexts)
    if loot.gold_elixir >= min_gold_elixir:
        return True
    return min_dark > 0 and loot.dark >= min_dark


def better(a: Loot | None, b: Loot) -> Loot:
    """Keep the richer of two bases (gold+elixir, dark breaks ties); for logging the best skipped."""
    if a is None:
        return b
    return max(a, b, key=lambda x: (x.gold_elixir, x.dark))


class LootReader:
    """Reads one group of three rows (gold, elixir, dark) with the shared digit glyphs."""

    def __init__(self, digits: DigitReader, rows: dict[str, Region]):
        missing = [k for k in KINDS if k not in rows]
        if missing:
            raise ValueError(f"regions missing rows: {', '.join(missing)}")
        self.digits = digits
        self.rows = rows

    def read(self, frame: Frame) -> Loot | None:
        """None if any row is unreadable (e.g. still fading in)."""
        values = [self.digits.read(frame, self.rows[k]) for k in KINDS]
        if any(v is None for v in values):
            return None
        return Loot(*values)
