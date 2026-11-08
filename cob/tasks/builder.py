"""Builder Base: get there by boat, and attack in two stages (FEATURE-007).

A BB battle is two bases in a row (100 % each, 200 % total). Stage 1 starts with a countdown
(BB_STAGE_WAIT); when stage 1 reaches 100 % the camera pans to stage 2, a new countdown appears and the
bar gains a reinforcement card. Every BB card is one unit (no "xN" counts), so deploying = tap the card,
tap a point. Stage 2 deploys whatever is still unused. Then results -> Return Home.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from cob.attack.geometry import BorderConfig, DeployConfig, deploy_points, find_base, red_mask
from cob.attack.troops import Card, find_cards, signature
from cob.core.snapshots import save_snapshot
from cob.screens.navigator import HOME, Navigator
from cob.tasks.deploy import place_unit, tap_card
from cob.vision.agree import read_stable
from cob.vision.frame import Frame
from cob.vision.match import match

log = logging.getLogger(__name__)

BB_HOME, BB_ATTACK_MENU, BB_SEARCHING = "BB_HOME", "BB_ATTACK_MENU", "BB_SEARCHING"
BB_STAGE_WAIT, BB_RESULTS, BATTLE = "BB_STAGE_WAIT", "BB_RESULTS", "BATTLE"
INTERRUPTS = frozenset({"POPUP_RELOAD", "POPUP_OTHER_DEVICE"})

DONE, FAILED = "done", "failed"
HERO_SLOT_MAX_X = 200  # the Battle Machine / Copter card is always first in the bar


@dataclass(frozen=True)
class BbConfig:
    screen_timeout_s: float = 30.0
    cooldown_wait_s: float = 180.0  # "Attack available in: 33s" on the Start Attack dialog
    search_timeout_s: float = 60.0
    settle_s: float = 2.5  # camera pans into stage 2: let it stop before reading the base
    ability_delay_s: float = 6.0
    battle_timeout_s: float = 330.0  # two stages of up to 3 min each, minus what is left of stage 1
    tap_pause_s: float = 0.15
    boat_attempts: int = 4


@dataclass
class BbOutcome:
    status: str
    stages: int = 0  # stages we deployed in
    deployed: list[int] = field(default_factory=list)  # cards deployed per stage
    reason: str = ""


def go_to_builder_base(nav: Navigator, cfg: BbConfig | None = None) -> bool:
    """From the home village (or already there) to BB_HOME. Only taps the boat once it is seen."""
    cfg = cfg or BbConfig()
    if not nav.go_home(arrive={HOME, BB_HOME}).ok:  # clear popups, but do not leave Builder Base
        return False
    zoomed = False
    for _ in range(cfg.boat_attempts):
        got = nav.wait_for({HOME, BB_HOME}, cfg.screen_timeout_s)
        if got is None:
            return False
        if got[0].screen == BB_HOME:
            nav.zoom_out()  # BB home has its own camera: zoomed out, the boat back is on screen too
            return True
        # Same boat bubble in both villages; home_boat_icon is the version half covered by the event bar.
        hit = match(got[1], nav.store.get("bb_boat_icon")) or match(got[1], nav.store.get("home_boat_icon"))
        if hit is not None:
            nav.tap_match(hit)
            if nav.wait_for({BB_HOME}, cfg.screen_timeout_s) is not None:
                nav.zoom_out()
                return True
        elif not zoomed:  # zoomed in, the dock is usually off screen: zoom out first, then look again
            zoomed = True
            if nav.zoom_out():
                continue
        else:  # boat off screen: drag the map so the bottom-left shore (the dock) comes into view
            nav.device.swipe(500, 600, 950, 300, 600)
            nav.sleep(1.0)
    return nav.wait_for({BB_HOME}, 3) is not None


class BbAttackTask:
    def __init__(self, nav: Navigator, border: BorderConfig, deploy: DeployConfig, bar: dict,
                 cfg: BbConfig | None = None):
        self.nav = nav
        self.device = nav.device
        self.border = border
        self.deploy = deploy
        self.bar = bar
        self.cfg = cfg or BbConfig()

    def run(self) -> BbOutcome:
        out = self._run()
        log.info("bb attack %s: %d stage(s), deployed %s%s", out.status, out.stages, out.deployed,
                 f" ({out.reason})" if out.reason else "")
        if out.status == FAILED:
            save_snapshot(self.device.capture(), f"bb_failed_{out.reason[:30]}", device=self.device)
        return out

    def _run(self) -> BbOutcome:
        if not go_to_builder_base(self.nav, self.cfg):
            return BbOutcome(FAILED, reason="could not reach Builder Base")
        home = self.nav.wait_for({BB_HOME}, self.cfg.screen_timeout_s)
        if home is None or not self._tap(home[1], "bb_attack_button"):
            return BbOutcome(FAILED, reason="BB Battle button not found")
        menu = self.nav.wait_for({BB_ATTACK_MENU}, self.cfg.screen_timeout_s)
        if menu is None:
            return BbOutcome(FAILED, reason="BB attack menu did not open")
        if not self._tap_find_now():
            return BbOutcome(FAILED, reason="Find Now not available (attack cooldown longer than the wait)")
        out = BbOutcome(DONE)
        start = self.nav.now()
        while not self.nav.stop.is_set() and self.nav.now() - start <= self.cfg.battle_timeout_s:
            got = self.nav.wait_for({BB_STAGE_WAIT, BB_RESULTS, BATTLE} | INTERRUPTS,
                                    self.cfg.search_timeout_s)
            if got is None:
                out.status, out.reason = FAILED, "no BB battle screen"
                return out
            screen = got[0].screen
            if screen in INTERRUPTS:
                out.status, out.reason = FAILED, f"battle interrupted ({screen})"
                return out
            if screen == BB_RESULTS:
                self._tap(got[1], "bb_return_home")
                if self.nav.wait_for({BB_HOME}, self.cfg.screen_timeout_s) is None:
                    out.reason = "results closed but BB home not seen"
                if sum(out.deployed) == 0:  # the timer ran out on an empty battle: not a real attack
                    out.status, out.reason = FAILED, "no troops deployed"
                return out
            if screen == BB_STAGE_WAIT:
                if out.stages >= 2:  # a third countdown would mean we misread something
                    out.status, out.reason = FAILED, "unexpected third stage"
                    return out
                self.nav.sleep(self.cfg.settle_s)
                self.nav.zoom_out()  # the battle camera has its own zoom; zoomed in, the outline is cut
                n = self._deploy_stage()
                out.stages += 1
                out.deployed.append(n)
                if n == 0:
                    log.info("stage %d: nothing left to deploy; waiting for the timer", out.stages)
                # wait until the countdown is gone before looking for the next stage
                self.nav.wait_leave(BB_STAGE_WAIT, self.cfg.search_timeout_s + 10)
            else:  # BATTLE: troops fighting; just look again soon
                self.nav.sleep(3.0)
        out.status, out.reason = FAILED, "battle did not end"
        return out

    def _deploy_stage(self) -> int:
        cards = read_stable(lambda: Frame(self.device.capture()), self._read_cards, need=2, max_frames=8,
                            stop=self.nav.stop)
        frame = Frame(self.device.capture())
        base = find_base(frame.bgr, self.border)
        if base is None or cards is None:
            log.warning("stage: %s", "no base outline" if base is None else "bar unreadable")
            return 0
        red = red_mask(frame.bgr, self.border, base)  # every point checked against the real red line
        edge, points = deploy_points(base, self.deploy, self.border.ui, red=red)
        if len(points) < 3:
            log.warning("stage: no room to deploy (%d points)", len(points))
            return 0
        ready = [c for c in cards.cards if not c.used]  # Builder Base has no spells: deploy every card
        log.info("stage: edge %s, %d points, deploying %d card(s)", edge, len(points), len(ready))
        wide = None  # same edge further out, when the near points are refused
        placed = []
        for i, card in enumerate(ready):
            # Each card is tapped ONCE (a second tap on a placed card can open "Change Troops");
            # a refused spot only gets more ground taps.
            start = (len(points) // 2 + i) % len(points)
            ok = place_unit(self.nav, card, points, start=start)
            if not ok:
                if wide is None:
                    far = replace(self.deploy, edge=edge, margin=self.deploy.margin * 3)
                    wide = deploy_points(base, far, self.border.ui, red=red)[1]
                ok = bool(wide) and place_unit(self.nav, card, wide, select=False)
            if ok:
                placed.append(card)
            else:
                log.warning("stage: card@%d could not be placed", card.x0)
        machine = [c for c in placed if c.x0 < HERO_SLOT_MAX_X]
        if machine:
            # Only the hero / machine (leftmost slot) has an ability. Re-tapping any other card can open
            # the stage-2 "Change Troops" picker over the battle (live: it hid the results screen).
            self.nav.sleep(self.cfg.ability_delay_s)
            self._tap_card(machine[0])
            self.nav.sleep(self.cfg.tap_pause_s)
        return len(placed)

    def _tap_find_now(self) -> bool:
        """Find Now, waiting out the BB attack cooldown (the dialog shows a timer instead of the button)."""
        start = self.nav.now()
        while not self.nav.stop.is_set() and self.nav.now() - start <= self.cfg.cooldown_wait_s:
            frame = self.nav.classify()[1]
            if self._tap(frame, "bb_find_now"):
                return True
            self.nav.sleep(5.0)
        return False

    def _read_cards(self, frame: Frame):
        cards = find_cards(frame.bgr)
        return _Cards(cards) if cards else None

    def _tap_card(self, card: Card) -> None:
        tap_card(self.nav, card)

    def _tap(self, frame: Frame, name: str) -> bool:
        hit = match(frame, self.nav.store.get(name))
        if hit is None:
            return False
        self.nav.tap_match(hit)
        return True


class _Cards:
    """Bar reads agree when kinds, positions and used flags match."""

    def __init__(self, cards: list[Card]):
        self.cards = cards
        self.sig = (signature(cards), tuple(c.used for c in cards))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Cards) and self.sig == other.sig

    __hash__ = None


def run_bb(task: BbAttackTask, attacks: int, max_failures: int = 3) -> list[BbOutcome]:
    """Several BB attacks in a row (stops on the stop event or repeated failures), then back to the
    home village so a home-village farm can follow."""
    results: list[BbOutcome] = []
    failures = 0
    while len(results) < attacks and not task.nav.stop.is_set() and failures < max_failures:
        out = task.run()
        results.append(out)
        failures = failures + 1 if out.status == FAILED else 0
        log.info("bb %d/%d: %s", len(results), attacks, out.status)
    task.nav.go_home()
    return results
