"""Wall upgrades (M3). Spends gold or elixir only; off unless farm.json `wall_upgrades` > 0.

Flow: home -> Build menu -> scroll to a "Wall" row (cheapest visible) -> its wall panel -> the gold or
elixir Upgrade hammer (never the Wall Ring) -> "Upgrade Wall to Level N?" -> checks -> Confirm -> home.

Spend safety (CONSTRAINTS: cost readable + affordable + post-condition):
- the cost on the Confirm button must be read exactly (unknown digit -> no spend)
- the cost text must be white (red = not affordable) and the coin/drop icon must match the resource
- own resource minus cost must stay >= reserve
- afterwards the own resource must have dropped by the cost (+-1 %); otherwise walls stop for the run
Anything unexpected closes the dialog with its X (go_home) and spends nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from cob.attack.loot import Loot, LootReader
from cob.core.snapshots import save_snapshot
from cob.screens.navigator import HOME, Navigator
from cob.vision.match import Match, match, match_all
from cob.vision.ocr import DigitReader

log = logging.getLogger(__name__)

GOLD, ELIXIR = "gold", "elixir"
BUILDER_MENU = "BUILDER_MENU"
BUILD_BUTTON = (1495, 800)  # hammer on the home screen (HUD, fixed)
LIST_SWIPE = (1385, 720, 1385, 150)  # finger up = list scrolls towards cheaper rows
LIST_BOX = (1170, 60, 430, 740)
PANEL_BAND = (0, 680, 1600, 220)  # wall panel buttons appear somewhere in this band
CONFIRM_COST = (1010, 780, 180, 42)
CONFIRM_ICON = (1195, 780, 40, 40)


@dataclass
class WallOutcome:
    upgraded: int = 0
    spent: dict[str, int] | None = None
    reason: str = ""
    unsafe: bool = False  # post-condition failed: caller must stop walls for this run


def icon_resource(bgr: np.ndarray, box: tuple[int, int, int, int]) -> str | None:
    """Gold coin (hue ~25) or elixir drop (hue ~146) by the median colour of saturated pixels."""
    x, y, w, h = box
    hsv = cv2.cvtColor(bgr[y:y + h, x:x + w], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    vivid = hsv[(hsv[:, 1] > 120) & (hsv[:, 2] > 150)]
    if len(vivid) < 20:
        return None
    hue = float(np.median(vivid[:, 0]))
    if 15 <= hue <= 35:
        return GOLD
    if 130 <= hue <= 165:
        return ELIXIR
    return None


def hammer_icon_box(h: Match) -> tuple[int, int, int, int]:
    """Coin / drop icon at the right end of the cost line above an Upgrade hammer."""
    return h.x + 84, h.y - 50, 24, 24


def cost_is_red(bgr: np.ndarray, box: tuple[int, int, int, int]) -> bool:
    """Red cost text means the game says we cannot afford it."""
    x, y, w, h = box
    b, g, r = (c.astype(int) for c in cv2.split(bgr[y:y + h, x:x + w]))
    return int(((r > 180) & (g < 90) & (b < 90)).sum()) > 40


def pick_resource(own: Loot, cost: int, reserve: int, prefer: str = GOLD) -> str | None:
    """Resource that stays >= reserve after paying; preferred one first, None when neither does."""
    have = {GOLD: own.gold, ELIXIR: own.elixir}
    for res in (prefer, ELIXIR if prefer == GOLD else GOLD):
        if have[res] - cost >= reserve:
            return res
    return None


def drop_matches(before: Loot, after: Loot, res: str, cost: int) -> bool:
    spent = getattr(before, res) - getattr(after, res)
    return abs(spent - cost) <= max(1, cost // 100)


class WallTask:
    def __init__(self, nav: Navigator, bar: LootReader, cost_digits: DigitReader, reserve: int,
                 max_scrolls: int = 15):
        self.nav = nav
        self.device = nav.device
        self.bar = bar
        self.digits = cost_digits
        self.reserve = reserve
        self.max_scrolls = max_scrolls

    def _own(self) -> Loot | None:
        if not self.nav.go_home().ok:
            return None
        got = self.nav.wait_for({HOME}, 10)
        return self.bar.read(got[1]) if got else None

    def run(self, count: int = 1) -> WallOutcome:
        out = WallOutcome(spent={GOLD: 0, ELIXIR: 0})
        for _ in range(count):
            reason = self._one(out)
            if reason:
                out.reason = reason
                break
        self.nav.go_home()  # closes whatever is left open (dialog X, panel)
        log.info("walls: %d upgraded, spent %s%s", out.upgraded, out.spent,
                 f" ({out.reason})" if out.reason else "")
        return out

    def _one(self, out: WallOutcome) -> str:
        before = self._own()
        if before is None:
            return "own resources unreadable"
        if not self._open_wall_panel():
            return "no wall row / panel found"
        frame = self.nav.classify()[1]
        hammers = {}
        for h in match_all(frame, self.nav.store.get("upgrade_hammer"), PANEL_BAND, 0.8):
            res = icon_resource(frame.bgr, hammer_icon_box(h))
            if res:
                hammers[res] = h
        # Ask the confirm dialog for the exact cost of the preferred resource first.
        for res in (GOLD, ELIXIR):
            if res not in hammers:
                continue
            verdict = self._confirm(hammers[res], res, before, out)
            if verdict != "try_other":
                return verdict
            self._reopen_panel_after_cancel()
            frame = self.nav.classify()[1]
        return "no affordable wall upgrade above the reserve"

    def _list_frame(self) -> np.ndarray:
        x, y, w, h = LIST_BOX
        return cv2.cvtColor(self.nav.classify()[1].bgr[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)

    def _open_wall_panel(self) -> bool:
        """The builder list is sorted by cost, highest first: scroll to its end, then back up until a
        Wall row shows, and take the lowest one (the cheapest wall upgrade)."""
        self.nav.go_home()
        self.device.tap(*self.nav.human.near(*BUILD_BUTTON))
        if self.nav.wait_for({BUILDER_MENU}, 8) is None:
            return False
        last = self._list_frame()
        for _ in range(self.max_scrolls):  # down to the end of the list
            self.device.swipe(*LIST_SWIPE, 700)
            self.nav.sleep(1.2)
            now = self._list_frame()
            if float(np.abs(now.astype(int) - last.astype(int)).mean()) < 2.0:
                break
            last = now
        up = (LIST_SWIPE[0], LIST_SWIPE[3], LIST_SWIPE[2], LIST_SWIPE[1])
        for _ in range(self.max_scrolls + 1):  # back up until a Wall row is visible
            frame = self.nav.classify()[1]
            rows = match_all(frame, self.nav.store.get("bm_wall_label"), LIST_BOX, 0.85)
            if rows:
                row = max(rows, key=lambda m: m.y)
                self.device.tap(*self.nav.human.in_box(row.x, row.y, 300, row.h + 20))
                self.nav.sleep(2.0)
                panel = self.nav.classify()[1]
                return match(panel, self.nav.store.get("wall_panel_label"), None, 0.85) is not None
            self.device.swipe(*up, 700)
            self.nav.sleep(1.2)
        return False

    def _reopen_panel_after_cancel(self) -> None:
        self.nav.go_home()
        self._open_wall_panel()

    def _confirm(self, hammer: Match, res: str, before: Loot, out: WallOutcome) -> str:
        self.nav.tap_match(hammer)
        self.nav.sleep(1.5)
        frame = self.nav.classify()[1]
        if match(frame, self.nav.store.get("wall_confirm_title")) is None:
            return "confirm dialog did not open"
        cost = self.digits.read(frame, CONFIRM_COST)
        button = match(frame, self.nav.store.get("confirm_button_top"))
        checks = {
            "cost readable": cost is not None and cost > 0,
            "cost not red": not cost_is_red(frame.bgr, CONFIRM_COST),
            "icon matches": icon_resource(frame.bgr, CONFIRM_ICON) == res,
            "confirm button": button is not None,
        }
        if not all(checks.values()):
            failed = [k for k, ok in checks.items() if not ok]
            save_snapshot(frame.bgr, f"walls_refused_{failed[0]}", device=self.device)
            return f"refused: {', '.join(failed)}"
        if getattr(before, res) - cost < self.reserve:
            log.info("walls: %s %d would go below the reserve %d", res, cost, self.reserve)
            return "try_other"
        self.nav.tap_match(button)
        self.nav.sleep(2.0)
        after = self._own()
        if after is None or not drop_matches(before, after, res, cost):
            save_snapshot(self.device.capture(), "walls_postcondition_failed", device=self.device)
            out.unsafe = True
            return f"post-condition failed ({res} before {getattr(before, res)}, after " \
                   f"{getattr(after, res) if after else '?'}, cost {cost})"
        out.upgraded += 1
        out.spent[res] += cost
        log.info("walls: upgraded one wall for %d %s", cost, res)
        return ""
