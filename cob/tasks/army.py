"""Pick one of the game's Saved Recipes as the army before farming (#185).

Battle -> attack menu (or the "Attack available in" menu while the army trains) -> Edit Army -> the
Saved Recipes arrow -> row N of the list. Picking a row loads that recipe into My Army at once (no
confirm button, moto g84 2026-11-07); the army screen is then closed and the village shows again.
"""

from __future__ import annotations

import logging

from cob.screens.navigator import Navigator
from cob.vision.match import match
from cob.vision.templates import TemplateMissing

log = logging.getLogger(__name__)

ARMY = "ARMY"
ATTACK_MENU, ARMY_TRAINING = "ATTACK_MENU", "ARMY_TRAINING"
MAX_RECIPES = 4  # rows the Saved Recipes list shows
ROW_X, FIRST_ROW_Y, ROW_STEP = 965, 187, 90  # list rows in 1600x900 frame pixels


def recipe_row(slot: int) -> tuple[int, int]:
    """Centre of row `slot` (1-based) of the open Saved Recipes list."""
    return ROW_X, FIRST_ROW_Y + ROW_STEP * (slot - 1)


class ArmyRecipe:
    def __init__(self, nav: Navigator, wait_s: float = 8.0):
        self.nav = nav
        self.wait_s = wait_s

    def select(self, slot: int) -> bool:
        """Load Saved Recipe `slot` (1..MAX_RECIPES) into My Army and return home. False when a step
        did not show up; the farm then goes on with the army as it is."""
        if not 1 <= slot <= MAX_RECIPES:
            raise ValueError(f"army recipe slot must be 1..{MAX_RECIPES}, not {slot}")
        ok = self._select(slot)
        log.info("army recipe %d %s", slot, "selected" if ok else "not selected; keeping the current army")
        self.nav.go_home()
        return ok

    def _select(self, slot: int) -> bool:
        if not self.nav.go_home().ok:
            return False
        # A tap on a screen that has just opened is often ignored (live, moto g84: Edit Army took two
        # taps), so each step taps again until the next screen shows.
        if not self._step("attack_button", lambda: self._screen({ATTACK_MENU, ARMY_TRAINING})):
            return False
        if not self._step("edit_army_label", lambda: self._screen({ARMY})):
            return False
        if not self._step("recipes_arrow", lambda: self._has("recipes_list_open")):
            return False
        x, y = recipe_row(slot)
        for _ in range(self.tries):
            self.nav.device.tap(x, y)
            self.nav.sleep(self.nav.cfg.poll_s * 2)
            if not self._has("recipes_list_open"):  # the list closed: the recipe is loaded
                return True
        log.info("army recipe: the Saved Recipes list did not close after tapping row %d", slot)
        return False

    tries = 3

    def _screen(self, screens: set[str]) -> bool:
        return self.nav.wait_for(screens, self.wait_s) is not None

    def _has(self, name: str) -> bool:
        for i in range(3):
            if i:
                self.nav.sleep(self.nav.cfg.poll_s)
            if match(self.nav.classify()[1], self.nav.store.get(name)) is not None:
                return True
        return False

    def _step(self, name: str, arrived) -> bool:
        """Tap template `name` until `arrived()` is true (at most `tries` taps)."""
        for attempt in range(self.tries):
            frame = self.nav.classify()[1]
            if not self._tap(frame, name):
                if attempt and arrived():  # the last tap worked late and the button is gone
                    return True
                return False
            if arrived():
                return True
            log.info("army recipe: no reaction to %s; tapping again", name)
        return False

    def _tap(self, frame, name: str) -> bool:
        try:
            hit = match(frame, self.nav.store.get(name))
        except TemplateMissing:
            hit = None
        if hit is None:
            log.info("army recipe: %s not found", name)
            return False
        self.nav.tap_match(hit)
        return True
