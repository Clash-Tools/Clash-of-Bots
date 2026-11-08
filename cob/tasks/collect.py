"""Collect resources: tap the gold / elixir / dark elixir bubbles over full collectors (M3).

Spends nothing. One tap on a bubble collects every collector of that resource, so each round taps ONE
bubble per resource type and re-captures (a second tap would land on a bare collector and open the
"Boost Production" gem offer). Stops when no bubbles are left. HUD areas are excluded so a look-alike
icon on a button is never tapped. Ends on HOME, closing anything a tap opened by accident.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

import cv2

from cob.screens.navigator import HOME, Navigator
from cob.vision.frame import Region
from cob.vision.match import match, match_all
from cob.vision.templates import Template

log = logging.getLogger(__name__)

BUBBLES = ("collect_gold", "collect_elixir", "collect_dark")
# Village HUD on the home screen: never tap bubbles inside these [x, y, w, h] boxes.
HUD: tuple[Region, ...] = (
    (0, 0, 360, 165),  # profile / clan
    (15, 185, 115, 110),  # trophies
    (1230, 0, 370, 330),  # resources, gems, shield
    (0, 330, 160, 330),  # chat, war
    (1440, 380, 160, 140),  # shop
    (0, 700, 1600, 200),  # Battle, bottom bar, Build
)


# The village camera zoom differs between sessions (bubbles were 1.2x after a restart).
SCALES = (1.0, 1.1, 1.2, 0.9, 1.3, 0.8)


def scaled(tpl: Template, s: float) -> Template:
    if s == 1.0:
        return tpl
    bgr = cv2.resize(tpl.bgr, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
    return replace(tpl, bgr=bgr, gray=cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))


def best_scale(frame, templates: list[Template]) -> float | None:
    """Zoom at which any bubble matches best; None when no bubble is visible at any zoom."""
    best, best_score = None, 0.0
    for s in SCALES:
        for tpl in templates:
            hit = match(frame, scaled(tpl, s), None)
            if hit is not None and hit.score > best_score:
                best, best_score = s, hit.score
    return best


@dataclass
class CollectOutcome:
    ok: bool
    tapped: dict[str, int] = field(default_factory=dict)
    rounds: int = 0
    loot_cart: bool = False
    reason: str = ""


def _in_hud(x: int, y: int) -> bool:
    return any(rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in HUD)


class CollectTask:
    def __init__(self, nav: Navigator, max_rounds: int = 4, tap_pause_s: float = 0.25):
        self.nav = nav
        self.max_rounds = max_rounds
        self.tap_pause_s = tap_pause_s

    def run(self) -> CollectOutcome:
        out = CollectOutcome(ok=False)
        if not self.nav.go_home().ok:
            out.reason = "could not reach home"
            return out
        for _ in range(self.max_rounds):
            got = self.nav.wait_for({HOME}, 10)
            if got is None:
                out.reason = "home not stable"
                return out
            frame = got[1]
            templates = [self.nav.store.get(n) for n in BUBBLES]
            scale = best_scale(frame, templates)
            if scale is None:
                break
            hits = []
            for name, tpl in zip(BUBBLES, templates, strict=True):
                found = [h for h in match_all(frame, scaled(tpl, scale), None, None)
                         if not _in_hud(*h.center)]
                if found:
                    hits.append((name, max(found, key=lambda h: h.score)))  # one per type
            if not hits:
                break
            out.rounds += 1
            for name, h in hits:
                self.nav.tap_match(h)
                out.tapped[name] = out.tapped.get(name, 0) + 1
                self.nav.sleep(self.tap_pause_s)
            self.nav.sleep(1.0)  # bubbles fly to the storages
        out.loot_cart = self._loot_cart()
        # Anything a tap opened by accident (boost offer, building info) is closed by its X.
        if not self.nav.go_home().ok:
            out.reason = "could not return home after collecting"
            return out
        out.ok = True
        got_any = {k.removeprefix("collect_"): v for k, v in out.tapped.items()}
        log.info("collect: %s in %d round(s)%s", got_any or "nothing", out.rounds,
                 ", loot cart" if out.loot_cart else "")
        return out

    def _loot_cart(self) -> bool:
        """Tap the cart's Collect label, then its Collect button; only acts on confirmed matches."""
        got = self.nav.wait_for({HOME}, 10)
        if got is None:
            return False
        label = match(got[1], self.nav.store.get("loot_cart_label"), None)
        if label is None or _in_hud(*label.center):
            return False
        x, y = label.center
        self.nav.device.tap(x, y + 18)  # the wagon, just under its label
        self.nav.sleep(1.5)
        frame = self.nav.classify()[1]
        if match(frame, self.nav.store.get("loot_cart_title")) is None:
            log.info("loot cart: tapped, but no Loot Cart panel")
            return False
        button = match(frame, self.nav.store.get("loot_cart_collect"))
        if button is None:
            return False
        self.nav.tap_match(button)
        self.nav.sleep(1.5)
        return True


BB_HOME = "BB_HOME"
BB_BUBBLES = ("bb_collect_gold", "bb_collect_elixir", "bb_collect_gems")


def collect_builder_base(nav: Navigator, max_rounds: int = 3, tap_pause_s: float = 0.4) -> dict[str, int]:
    """On BB_HOME (camera zoomed out): tap EVERY collector bubble. Unlike the home village, one tap
    there collects one collector only, so each bubble is tapped once per round, then re-checked.
    Ends on BB_HOME (anything a tap opened is closed). Returns taps per resource."""
    tapped: dict[str, int] = {}
    for _ in range(max_rounds):
        got = nav.wait_for({BB_HOME}, 10)
        if got is None:
            break
        hits = [(name, h) for name in BB_BUBBLES for h in match_all(got[1], nav.store.get(name))
                if not _in_hud(*h.center)]
        if not hits:
            break
        for name, h in hits:
            nav.tap_match(h)
            key = name.removeprefix("bb_collect_")
            tapped[key] = tapped.get(key, 0) + 1
            nav.sleep(tap_pause_s)
        nav.sleep(1.0)  # bubbles fly to the storages
    nav.go_home(arrive={BB_HOME})
    log.info("bb collect: %s", tapped or "nothing")
    return tapped

