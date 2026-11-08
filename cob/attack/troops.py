"""Troop bar: find cards by their brightness and tell troops, spells and single units apart.

troop  = has an "xN" count on a blue card (red for super troops) -> deploy until the card greys out
spell  = has an "xN" count on a purple card -> cast inside the attacked edge after the troops
single = no count (heroes, siege, clan castle) -> one tap; a second tap later fires the ability
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

TROOP, SPELL, SINGLE = "troop", "spell", "single"


@dataclass(frozen=True)
class Card:
    x0: int
    x1: int
    kind: str
    used: bool  # greyed out: nothing left to deploy

    @property
    def center(self) -> tuple[int, int]:
        return (self.x0 + self.x1) // 2, 815


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, width) of True runs in a 1-D mask."""
    out, start = [], None
    for x, on in enumerate(list(mask) + [False]):
        if on and start is None:
            start = x
        elif not on and start is not None:
            out.append((start, x - start))
            start = None
    return out


def read_bar(bgr: np.ndarray, cfg: dict) -> list[Card]:
    """Cards left to right (positions from find_cards), each classified troop / spell / single."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    by, bh = cfg["band"][1], cfg["band"][3]
    width = cfg["card_nominal_width"]
    # Reference "white" for count text: the bar's own brightest pixels (screen fades dim everything).
    by0, bh0 = cfg["count_box"][1], cfg["count_box"][3]
    bright = float(np.percentile(bgr[by0:by0 + bh0].min(axis=2), 99.5))
    white = min(cfg["count_white_v"], bright - cfg["count_white_margin"])
    cards: list[Card] = []
    for found in find_cards(bgr):
        a, b = found.x0, found.x0 + width
        body_sat = float(hsv[by + 10:by + bh - 10, a + 6:b - 6, 1].mean())
        cards.append(_classify(bgr, hsv, a, b, body_sat, cfg, white))
    return by_order(cards)


def by_order(cards: list[Card]) -> list[Card]:
    """The game lays the bar out as troops, siege machines, heroes / clan castle, then spells, so a counted
    card left of the last single unit is a troop whatever its colour (event and super troops come in
    colours the spell-hue band was never measured on)."""
    singles = [i for i, c in enumerate(cards) if c.kind == SINGLE]
    if not singles:
        return cards
    last = singles[-1]
    return [Card(c.x0, c.x1, TROOP, c.used) if c.kind == SPELL and i < last else c
            for i, c in enumerate(cards)]


def _classify(bgr: np.ndarray, hsv: np.ndarray, a: int, b: int, body_sat: float, cfg: dict,
              white: float) -> Card:
    cx, cy, cw, ch = cfg["count_box"]
    count = bgr[cy:cy + ch, max(0, b + cx):max(0, b + cx + cw)]
    has_count = count.size > 0 and float((count.min(axis=2) > white).mean()) >= cfg["count_white_min"]
    gx, gy, gw, gh = cfg["bg_box"]
    hue = float(np.median(hsv[gy:gy + gh, a + gx:a + gx + gw, 0]))
    if has_count:
        # Purple = spell. Super troops sit on a red card whose hue wraps round to ~179, above the purple
        # band (live: a Super Valkyrie x17 read as a spell and never deployed).
        kind = SPELL if cfg["spell_hue_min"] <= hue < cfg.get("spell_hue_max", 165) else TROOP
    else:
        kind = SINGLE
    return Card(a, b, kind, body_sat < cfg["used_body_saturation"])


def is_used(bgr: np.ndarray, card: Card, cfg: dict) -> bool:
    """Greyed out now? Cards keep their place during a battle, so the first read's x is reused."""
    by, bh = cfg["band"][1], cfg["band"][3]
    hsv = cv2.cvtColor(bgr[by + 10:by + bh - 10, card.x0 + 6:card.x1 - 6], cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 1].mean()) < cfg["used_body_saturation"]


def signature(cards: list[Card]) -> tuple:
    """Comparable summary for agreeing reads across frames (positions to 10 px, kinds)."""
    return tuple((round(c.x0, -1), c.kind) for c in cards)


def find_cards(bgr: np.ndarray, rows: tuple[int, int] = (745, 885), min_v: float = 95,
               min_width: int = 55, card_width: int = 110, used_saturation: float = 30,
               min_std: float = 30) -> list[Card]:
    """Ready cards in the troop bar (both villages), kind not decided (SINGLE). Cards are much brighter
    than the dark bar and the dashed empty slots, so the brightness profile finds them whatever the
    badges, counts or upgrade icons look like (live: "x1" counts and green upgrade arrows broke the
    old level-badge reader, so heroes and troops were never deployed). Card art is high contrast;
    a bright but smooth stretch is scenery through the translucent bar (min_std). Greyed-out cards
    are too dark to be found: read the bar before deploying."""
    y0, y1 = rows
    hsv = cv2.cvtColor(bgr[y0:y1], cv2.COLOR_BGR2HSV)
    profile = hsv[:, :, 2].astype(np.float32).mean(axis=0)
    cards: list[Card] = []
    for start, width in _runs(profile > min_v):
        if width < min_width:
            continue
        x1 = start + width
        x0 = max(0, x1 - card_width)
        if float(cv2.cvtColor(bgr[y0 + 15:y0 + 125, x0 + 8:x1 - 8], cv2.COLOR_BGR2GRAY).std()) < min_std:
            continue
        body = hsv[45:115, x0 + 6:x1 - 6, 1]
        used = float(body.mean()) < used_saturation if body.size else False
        cards.append(Card(x0, x1, SINGLE, used))
    return cards
