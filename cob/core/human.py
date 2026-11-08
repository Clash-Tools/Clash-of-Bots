"""Human-like variation: taps land somewhere inside a button, not on its exact centre pixel.

Fixed pixel-perfect taps on every button are an easy bot signature. Variation stays inside the middle
part of the target, so a tap never misses the button.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Humanizer:
    enabled: bool = True
    frac: float = 0.3  # max offset as a fraction of the target size (0.3 = middle 60 %)
    point_px: int = 6  # max offset for free taps (deploy points), in px
    rng: random.Random | None = None

    def __post_init__(self) -> None:
        self.rng = self.rng or random.Random()

    def in_box(self, x: int, y: int, w: int, h: int) -> tuple[int, int]:
        """A point inside the box (x, y = top-left), near its centre."""
        cx, cy = x + w // 2, y + h // 2
        if not self.enabled:
            return cx, cy
        dx = self.rng.uniform(-self.frac, self.frac) * w
        dy = self.rng.uniform(-self.frac, self.frac) * h
        return int(round(cx + dx)), int(round(cy + dy))

    def near(self, x: int, y: int) -> tuple[int, int]:
        """A point a few px around (x, y) (deploy spots, where any nearby tile works)."""
        if not self.enabled:
            return x, y
        return (x + self.rng.randint(-self.point_px, self.point_px),
                y + self.rng.randint(-self.point_px, self.point_px))
