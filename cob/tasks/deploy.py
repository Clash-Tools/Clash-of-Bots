"""Place one unit and check it landed (both villages).

A tap outside the deploy zone (on the red line, inside it, on a UI box) does nothing: the card stays
selected and unchanged. A placed unit changes its card (greyed out, or the hero ability face), so
"card picture changed after the ground tap" is the check. Retries go to other points along the edge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import cv2
import numpy as np

from cob.attack.troops import Card
from cob.screens.navigator import Navigator

log = logging.getLogger(__name__)

CARD_ROWS = (760, 880)
COUNT_ROWS = (742, 780)  # a troop card's "x15" count


BAR_ROWS = (730, 900)  # everything the card checks read: count, face, greyed-out band


def capture_bar(device):
    """The troop bar rows only when the device can send just those (#166), else a full frame."""
    rows = getattr(device, "capture_rows", None)
    return rows(*BAR_ROWS) if rows is not None else device.capture()


def tap_card(nav: Navigator, card: Card) -> None:
    """Somewhere on the card's face, well above its bottom edge: the green upgrade arrow sits in the
    bottom-right corner (y ~840-870) and tapping it opens the troop picker (live: troops got swapped)."""
    nav.device.tap(*nav.human.in_box(card.x0 + 15, 775, card.x1 - card.x0 - 30, 40))


def _crop(bgr: np.ndarray, card: Card, rows: tuple[int, int]) -> np.ndarray:
    y0, y1 = rows
    return cv2.cvtColor(bgr[y0:y1, card.x0 + 6:card.x1 - 6], cv2.COLOR_BGR2GRAY).astype(np.int16)


def card_change(before: np.ndarray, after: np.ndarray, card: Card,
                rows: tuple[int, int] = CARD_ROWS) -> float:
    return float(np.abs(_crop(after, card, rows) - _crop(before, card, rows)).mean())


def count_change(before: np.ndarray, after: np.ndarray, card: Card) -> float:
    """A troop card only greys out at 0: until then a placement changes just its "x15" count at the top
    (#92: the whole-card crop scored 3.0 for 15 -> 3 dragons, the count rows 21.8)."""
    return card_change(before, after, card, COUNT_ROWS)


def spread(points: list, start: int, tries: int) -> list:
    """`tries` points from `start`, spread along the edge (a blocked spot is usually local)."""
    n = len(points)
    step = max(1, n // max(1, tries))
    return [points[(start + k * step) % n] for k in range(min(tries, n))]


@dataclass
class PointMemory:
    """Ground points the game took or refused in this battle (#166): the next unit goes straight to a
    point that worked instead of trying the refused ones again (live: a hero tried 7 refused points,
    ~4 s each, then the next hero tried the same 7)."""

    good: list = field(default_factory=list)
    bad: set = field(default_factory=set)

    def order(self, candidates: list) -> list:
        fresh = [p for p in candidates if p not in self.bad and p not in self.good]
        return self.good + fresh


def place_unit(nav: Navigator, card: Card, points: list, *, start: int | None = None, tries: int = 4,
               select: bool = True, select_s: float = 0.3, settle_s: float = 0.5,
               min_change: float = 10.0, memory: PointMemory | None = None) -> bool:
    """Tap the card once (select=False: still selected from a refused try), then ground points until
    the card shows the unit was placed."""
    if not points:
        return False
    if select:
        tap_card(nav, card)
        nav.sleep(select_s)  # selection pop-up animation done before the reference frame
    candidates = spread(points, len(points) // 2 if start is None else start, tries)
    if memory is not None:
        candidates = memory.order(candidates)[:max(tries, len(memory.good) + 1)]
    before = None
    for point in candidates:
        # A refused tap leaves the card as it was, so the frame after it is the next try's reference:
        # one capture per try instead of two (captures are 2-5 s over Wi-Fi).
        before = before if before is not None else capture_bar(nav.device)
        nav.device.tap(*nav.human.near(*point))
        nav.sleep(settle_s)
        after = capture_bar(nav.device)
        change = card_change(before, after, card)
        log.debug("deploy card@%d at %s: card change %.1f", card.x0, point, change)
        if change >= min_change:
            if memory is not None and point not in memory.good:
                memory.good.insert(0, point)
            return True
        if memory is not None:
            memory.bad.add(point)
        log.info("card@%d not placed at %s (card unchanged); trying another point", card.x0, point)
        before = after
        if nav.stop.is_set():
            break
    return False
