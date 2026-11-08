"""Search task: home -> Battle -> Find a Match -> read loot -> Next until the filter passes.

Every tap waits for its screen to be confirmed first (screens open late; see FEATURE-003).
The scouting timer is 30 s per base, so one base must be read and decided well inside that.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cob.attack.loot import Loot, LootReader, better, minimums, worth_attacking
from cob.core.config import FarmConfig
from cob.core.snapshots import save_snapshot
from cob.screens.navigator import HOME, Navigator
from cob.vision.agree import read_stable
from cob.vision.frame import Frame
from cob.vision.match import match
from cob.vision.templates import TemplateMissing

log = logging.getLogger(__name__)

ATTACK_MENU = "ATTACK_MENU"
ARMY = "ARMY"
SEARCHING = "SEARCHING"
SEARCH_BLOCKED = "SEARCH_BLOCKED"
BLOCKED_REASON = "search blocked: try again later"
ARMY_NOT_READY = "army review without Attack! button (army not ready?)"
HOME_FAILED = "could not reach home"
ARMY_TRAINING = "ARMY_TRAINING"  # attack menu with "Attack available in:" instead of Find a Match
ATTACK_SEARCH = "ATTACK_SEARCH"
BATTLE = "BATTLE"  # the scout timer ran out and the battle started on the base being looked at
NEXT_BASE_WAIT_S = 12.0  # #88: time for the next base to show after Next

ACCEPTED = "accepted"  # base passes the filter
MAX_NEXTS = "max_nexts"  # filter never passed; current base taken
LOW_GOLD = "low_gold"  # own gold below reserve; search stopped
FAILED = "failed"  # could not reach or read a screen


@dataclass
class SearchOutcome:
    status: str
    loot: Loot | None = None  # base we stopped on
    nexts: int = 0
    own_gold: int | None = None
    best_skipped: Loot | None = None
    reason: str = ""
    seen: list[Loot] = field(default_factory=list)

    @property
    def attack(self) -> bool:
        return self.status in (ACCEPTED, MAX_NEXTS)


class SearchTask:
    def __init__(self, nav: Navigator, loot: LootReader, bar: LootReader, cfg: FarmConfig, *,
                 screen_timeout_s: float = 30.0, battle_tap_attempts: int = 3,
                 battle_tap_wait_s: float = 8.0):
        self.nav = nav
        self.device = nav.device
        self.loot = loot
        self.bar = bar
        self.cfg = cfg
        self.screen_timeout_s = screen_timeout_s
        self.battle_tap_attempts = battle_tap_attempts
        self.battle_tap_wait_s = battle_tap_wait_s

    def run(self, dry_run: bool = True) -> SearchOutcome:
        out = self._search()
        log.info("search %s after %d nexts: %s%s", out.status, out.nexts, out.loot or "-",
                 f" ({out.reason})" if out.reason else "")
        if out.status == FAILED and out.reason != ARMY_NOT_READY:  # waiting for the army is no failure
            # #178: the screen that showed instead of the one waited for
            seen = getattr(self.nav, "last_unwanted", None)
            save_snapshot(self.device.capture(), f"search_failed_{out.reason[:30]}", device=self.device,
                          details={"reason": out.reason, "instead": seen[0] if seen else None},
                          images={"seen": seen[1].bgr} if seen else None)
        if dry_run or not out.attack:
            self._leave()
        return out

    def _search(self) -> SearchOutcome:
        home_nav = self.nav.go_home()
        if not home_nav.ok:
            why = f"stopped on {home_nav.stopped_on}" if home_nav.stopped_on else HOME_FAILED
            return SearchOutcome(FAILED, reason=why)
        home = self.nav.wait_for({HOME}, self.screen_timeout_s)
        if home is None:
            return SearchOutcome(FAILED, reason="home not stable")
        own = self.bar.read(home[1])
        if own is not None and own.gold < self.cfg.min_own_gold:
            return SearchOutcome(LOW_GOLD, own_gold=own.gold, reason="own gold below reserve")
        menu = self._open_attack_menu(home)
        if isinstance(menu, str):
            return SearchOutcome(FAILED, reason=menu)
        if not self._tap(menu, "find_match"):
            return SearchOutcome(FAILED, reason="Find a Match not found in the attack menu")
        # Find a Match may first show the army review with a green Attack! button.
        nxt = self.nav.wait_for({ARMY, SEARCHING, ATTACK_SEARCH, SEARCH_BLOCKED}, self.screen_timeout_s)
        if nxt is None:
            return SearchOutcome(FAILED, reason="no army review or search after Find a Match")
        if nxt[0].screen == SEARCH_BLOCKED:
            return SearchOutcome(FAILED, reason=BLOCKED_REASON)
        if nxt[0].screen == ARMY and not self._tap(nxt, "army_attack"):
            return SearchOutcome(FAILED, reason=ARMY_NOT_READY)

        nexts = 0
        best: Loot | None = None
        seen: list[Loot] = []
        while True:
            got = self.nav.wait_for({ATTACK_SEARCH, SEARCH_BLOCKED, BATTLE}, self.screen_timeout_s)
            if got is not None and got[0].screen == BATTLE:
                # #88: the 30 s scout timer ran out (slow captures): the battle is on, so attack it
                # rather than wait idle until it ends.
                log.info("base %d: scout timer ran out, the battle started; attacking it", nexts + 1)
                return SearchOutcome(ACCEPTED, None, nexts, None, best, seen=seen,
                                     reason="scout timer ran out")
            if got is not None and got[0].screen == SEARCH_BLOCKED:
                return SearchOutcome(FAILED, nexts=nexts, best_skipped=best, seen=seen, reason=BLOCKED_REASON)
            if got is None:
                return SearchOutcome(FAILED, nexts=nexts, best_skipped=best, seen=seen,
                                     reason="no search screen")
            loot = read_stable(lambda: Frame(self.device.capture()), self.loot.read, need=2,
                               max_frames=6, stop=self.nav.stop, first=got[1])
            own = self.bar.read(got[1])
            own_gold = own.gold if own else None
            if loot is not None:
                seen.append(loot)
                log.info("base %d: %s", nexts + 1, loot)
                if worth_attacking(loot, self.cfg, nexts):
                    return SearchOutcome(ACCEPTED, loot, nexts, own_gold, best, seen=seen)
            else:
                log.warning("base %d: loot unreadable, skipping", nexts + 1)
            if nexts >= self.cfg.max_nexts:
                return SearchOutcome(MAX_NEXTS, loot, nexts, own_gold, best, seen=seen,
                                     reason=f"filter not met in {nexts} nexts")
            if own_gold is not None and own_gold < self.cfg.min_own_gold:
                return SearchOutcome(LOW_GOLD, loot, nexts, own_gold, best, seen=seen,
                                     reason="own gold below reserve")
            if loot is not None:
                best = better(best, loot)
            current = self.nav.wait_for({ATTACK_SEARCH}, self.screen_timeout_s)
            if current is None or not self._tap(current, "next_button"):
                return SearchOutcome(FAILED, loot, nexts, own_gold, best, seen=seen,
                                     reason="Next button not found")
            nexts += 1
            if self.cfg.reduce_every and nexts % self.cfg.reduce_every == 0:
                low = minimums(self.cfg, nexts)
                log.info("after %d nexts: looking for gold + elixir %s or dark %s", nexts, f"{low[0]:,}",
                         f"{low[1]:,}")
            self._wait_next_base(loot)

    def _wait_next_base(self, previous: Loot | None) -> None:
        """After Next: the new base is there once the screen changes (clouds, battle) or the loot shown
        changes. Waiting only for the screen to change missed the short cloud transition when captures
        take ~1 s (phone over Wi-Fi), so the next base's scout timer ran out unseen (#88)."""
        start = self.nav.now()
        while not self.nav.stop.is_set() and self.nav.now() - start <= NEXT_BASE_WAIT_S:
            cls, frame = self.nav.classify()
            if cls.screen != ATTACK_SEARCH:
                return
            shown = self.loot.read(frame)
            if shown is not None and shown != previous:
                return
            self.nav.sleep(self.nav.cfg.poll_s)

    def _open_attack_menu(self, home):
        """Tap Battle until the attack menu shows. Right after a game (re)start the village can ignore
        the first tap, so tap again while HOME is still on screen. Returns the menu or a reason."""
        got = home
        for _ in range(self.battle_tap_attempts):
            if not self._tap(got, "attack_button"):
                return "Battle button not found"
            menu = self.nav.wait_for({ATTACK_MENU, ARMY_TRAINING}, self.battle_tap_wait_s)
            if menu is not None and menu[0].screen == ARMY_TRAINING:
                # #180: the army is still training ("Attack available in: 39s"): wait, not a failure
                return ARMY_NOT_READY
            if menu is not None:
                return menu
            got = self.nav.wait_for({HOME}, 2)
            if got is None:  # something else opened: let the caller recover
                return "attack menu did not open (another screen appeared)"
            log.info("attack menu did not open; tapping Battle again")
        return f"attack menu did not open after {self.battle_tap_attempts} Battle taps"

    def _leave(self) -> None:
        """End the search without attacking and return home (dry run, low gold, failures)."""
        if not self.nav.go_home().ok:
            log.warning("could not return home after search")

    def _tap(self, got, name: str) -> bool:
        cls, frame = got
        hit = cls.matches.get(name)
        if hit is None:
            try:
                hit = match(frame, self.nav.store.get(name))
            except TemplateMissing:
                hit = None
        if hit is None:
            return False
        self.nav.tap_match(hit)
        return True
