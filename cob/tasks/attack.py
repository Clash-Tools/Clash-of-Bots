"""Attack: deploy the army just outside one edge of the base, fire hero abilities, cast spells, end
the battle.

Starts on a confirmed ATTACK_SEARCH screen (SearchTask.run(dry_run=False)). Order: troops (until
each card greys out), then single units (siege, heroes, clan castle). A second tap on each single
card fires hero abilities, then spells are cast a little inside the attacked edge. The battle is
left to end by itself (all troops down or the timer), then Return Home, or surrender once the
damage % stops growing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from cob.attack.damage import damage_reader, read_damage
from cob.attack.geometry import (
    BorderConfig,
    DeployConfig,
    deploy_sides,
    draw_base,
    find_base,
    red_mask,
    spell_points,
)
from cob.attack.loot import LootReader
from cob.attack.troops import SINGLE, SPELL, TROOP, Card, is_used, read_bar, signature
from cob.core.snapshots import save_snapshot
from cob.screens.navigator import HOME, Navigator
from cob.tasks.deploy import PointMemory, capture_bar, count_change, place_unit, spread, tap_card
from cob.vision.agree import read_stable
from cob.vision.frame import Frame
from cob.vision.match import match

log = logging.getLogger(__name__)

ATTACK_SEARCH, BATTLE, BATTLE_END = "ATTACK_SEARCH", "BATTLE", "BATTLE_END"
SURRENDER_CONFIRM = "SURRENDER_CONFIRM"
# Battle can be cut off by these; waiting for BATTLE_END would only run into the timeout.
INTERRUPTS = frozenset({"POPUP_RELOAD", "POPUP_OTHER_DEVICE"})

DONE = "done"  # battle ended, back home
FAILED = "failed"


@dataclass(frozen=True)
class AttackConfig:
    max_taps_per_troop: int = 400  # ceiling per troop card; rounds stop earlier once the count stops changing
    check_every: int = 6  # re-check a troop card after this many taps
    ability_delay_s: float = 8.0  # after the last single unit, wait then tap singles again
    battle_timeout_s: float = 240.0  # 3 min battle + end screen
    tap_pause_s: float = 0.05
    stall_s: float = 15.0  # damage % unchanged this long after full deploy -> surrender
    first_damage_s: float = 45.0  # #78: troops dropped far out can walk this long before the first hit
    watch_poll_s: float = 3.0
    loot_stall_s: float = 0.0  # #114: Available Loot unchanged this long after full deploy -> end; 0 = off
    end_at_damage: int = 0  # #114: end the battle once damage reaches this %; 0 = off
    sides: int = 1  # #44: deploy along this many adjacent edges (1 or 2)
    cast_spells: bool = True  # cast every spell card inside the attacked edge after the troops
    spell_depth: float = 0.3  # how far towards the base centre spells land (share of the distance)
    max_spell_taps: int = 15  # per spell card (counts are small: x5 is a full spell army)
    spell_pause_s: float = 0.3  # after each cast, before the card check


class _BarRead:
    """Bar reads agree when kinds and rough positions match (exact x may jitter a few px)."""

    def __init__(self, cards: list[Card]):
        self.cards = cards
        self.sig = signature(cards)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _BarRead) and self.sig == other.sig

    __hash__ = None


@dataclass
class AttackOutcome:
    status: str
    edge: str = ""
    points: int = 0
    deployed: dict[str, int] = field(default_factory=dict)  # kind -> cards deployed
    taps: int = 0
    reason: str = ""
    ended_by: str = ""  # "battle_end" (base destroyed / troops down / timer) or "surrender"
    damage: float = 0.0  # last Overall Damage % read before the battle ended


class AttackTask:
    def __init__(self, nav: Navigator, border: BorderConfig, deploy: DeployConfig, bar: dict,
                 damage: dict, cfg: AttackConfig | None = None, loot: LootReader | None = None):
        self.nav = nav
        self.device = nav.device
        self.border = border
        self.deploy = deploy
        self.bar = bar
        self.damage = damage
        self.percent = damage_reader(nav.store, damage)
        self.cfg = cfg or AttackConfig()
        self.loot = loot  # Available Loot rows, for the loot stall (#114)

    def run(self) -> AttackOutcome:
        out = self._attack()
        log.info("attack %s: edge %s, %d points, %d taps, deployed %s, ended by %s at ~%.0f%%%s",
                 out.status, out.edge, out.points, out.taps, out.deployed, out.ended_by or "-", out.damage,
                 f" ({out.reason})" if out.reason else "")
        if out.status == FAILED:
            self._report(out)
            self.nav.go_home()
        return out

    def _report(self, out: AttackOutcome) -> None:
        """#170: failure report with the screen now and the base frame the attack worked from."""
        images = {}
        base_frame = getattr(self, "_base_frame", None)
        if base_frame is not None:
            try:
                images["base"] = draw_base(base_frame, self.border, self.deploy,
                                           getattr(self, "_points", None))
            except Exception as exc:  # the report must never break the attack
                log.debug("base drawing failed: %s", exc)
        details = {"reason": out.reason, "edge": out.edge, "points": out.points, "taps": out.taps,
                   "deployed": out.deployed, "ended_by": out.ended_by, "damage": out.damage}
        save_snapshot(self.device.capture(), f"attack_failed_{out.reason[:30]}", details=details,
                      images=images, device=self.device)

    def _attack(self) -> AttackOutcome:
        self._base_frame, self._points = None, None
        got = self.nav.wait_for({ATTACK_SEARCH, BATTLE}, 10)
        if got is None:
            return AttackOutcome(FAILED, reason="not on the search/battle screen")
        self._base_frame = got[1].bgr
        # The battle camera starts zoomed in whatever the village zoom; zoomed in, part of the red
        # deploy line is off screen or under the bar and deploy points land inside the base.
        self.nav.zoom_out()
        bar = read_stable(lambda: Frame(self.device.capture()), self._read_bar, need=2, max_frames=8,
                          stop=self.nav.stop)
        if bar is None:
            return AttackOutcome(FAILED, reason="troop bar not readable")
        cards = bar.cards
        frame = Frame(self.device.capture())
        self._base_frame = frame.bgr
        base = find_base(frame.bgr, self.border)
        if base is None:
            return AttackOutcome(FAILED, reason="base border not found or unclear")
        self._red = red_mask(frame.bgr, self.border, base)  # every point checked against the real red line
        edge, points = deploy_sides(base, self.deploy, self.border.ui, self.cfg.sides, red=self._red)
        self._points = points
        if len(points) < 3:
            return AttackOutcome(FAILED, edge=edge, points=len(points), reason="no room to deploy")

        out = AttackOutcome(DONE, edge=edge, points=len(points))
        log.info("bar: %s", ", ".join(f"{c.kind}@{c.center[0]}" for c in cards))
        wide = None  # same edge further out, for units the near points refused
        for card in [c for c in cards if c.kind == TROOP and not c.used]:
            taps, ok = self._deploy_troop(card, points)
            if not ok:
                wide = wide or self._wide_points(base, edge)
                if wide:
                    log.info("troop card@%d: not confirmed empty; trying points further out", card.x0)
                    more, ok = self._deploy_troop(card, wide)
                    taps += more
            out.taps += taps
            if ok:
                out.deployed[TROOP] = out.deployed.get(TROOP, 0) + 1
            else:
                log.warning("troop card@%d: deployment could not be confirmed", card.x0)
        singles = [c for c in cards if c.kind == SINGLE and not c.used]
        placed = []
        memory = PointMemory()  # points the game took / refused, shared by the single units
        for card in singles:
            ok = place_unit(self.nav, card, points, memory=memory)
            if not ok:
                wide = wide or self._wide_points(base, edge)
                ok = place_unit(self.nav, card, wide, select=False, memory=memory) if wide else False
            if ok:
                placed.append(card)
            else:
                log.warning("single card@%d could not be placed", card.x0)
        out.taps += 2 * len(singles)
        singles = placed
        out.deployed[SINGLE] = len(singles)
        out.deployed[SPELL] = 0
        if singles:
            self.nav.sleep(self.cfg.ability_delay_s)
            for card in singles:  # hero abilities (harmless for siege / clan castle)
                self._tap_card(card)
                out.taps += 1
                self._pause()
        spells = [c for c in cards if c.kind == SPELL and not c.used] if self.cfg.cast_spells else []
        if spells:
            if not singles:  # troops need a moment to reach the buildings the spells land on
                self.nav.sleep(self.cfg.ability_delay_s)
            targets = spell_points(base, points, self.border.ui, self.cfg.spell_depth)
            for card in spells:
                taps, ok = self._cast_spell(card, targets)
                out.taps += taps
                if ok:
                    out.deployed[SPELL] += 1
                else:
                    log.warning("spell card@%d: casting could not be confirmed", card.x0)
        end = self._watch_battle(out)
        if end is None:
            out.status, out.reason = FAILED, "stopped" if self.nav.stop.is_set() else "battle did not end"
            return out
        if end in INTERRUPTS:
            out.status, out.reason = FAILED, f"battle interrupted ({end})"
            return out
        if not self.nav.go_home().ok:
            out.status, out.reason = FAILED, "could not return home"
        return out

    def _watch_battle(self, out: AttackOutcome) -> str | None:
        """Until BATTLE_END or an interrupting popup: surrender once the damage % stops growing.

        #135: after a 3-star win the results screen went unrecognised and the village showed up later, so
        HOME also ends the watch, and the first other screen after 100 % is saved for a template."""
        start = self.nav.now()
        best, changed_at = -1, start
        loot, loot_at = None, start
        surrendered = stalled = shot = False
        last = None
        while not self.nav.stop.is_set() and self.nav.now() - start <= self.cfg.battle_timeout_s:
            cls, frame = self.nav.classify()
            if cls.screen != last:
                log.debug("battle watch: %s", cls.screen)
                last = cls.screen
            if cls.screen == BATTLE_END or cls.screen in INTERRUPTS:
                out.ended_by = out.ended_by or "battle_end"
                return cls.screen
            if cls.screen == HOME:
                out.ended_by = out.ended_by or "home"
                return cls.screen
            now = self.nav.now()
            if best >= 100 and cls.screen != BATTLE and not shot:
                save_snapshot(frame.bgr, f"after_100pct_{cls.screen.lower()}", device=self.device)
                shot = True
            if cls.screen == SURRENDER_CONFIRM:
                self._tap_template(frame, "okay_button")
            elif cls.screen == BATTLE and not surrendered:
                pct = read_damage(self.percent, frame, self.damage)
                grew = pct is not None and pct > best
                if grew:
                    best, changed_at = pct, now
                    out.damage = float(pct)
                    log.debug("damage %d%%", pct)
                now_loot = self.loot.read(frame) if self.cfg.loot_stall_s > 0 and self.loot else None
                if now_loot is not None and now_loot != loot:
                    loot, loot_at = now_loot, now
                why = label = None
                if not grew and ((best > 0 and now - changed_at >= self.cfg.stall_s) or (
                        best <= 0 and now - start >= self.cfg.first_damage_s)):
                    why = f"damage stalled at {out.damage:.0f}% for {now - changed_at:.0f} s"
                    label = f"stall_surrender_{out.damage:.0f}pct"
                elif self.cfg.end_at_damage > 0 and best >= self.cfg.end_at_damage:
                    why = f"damage reached {best}% (end at {self.cfg.end_at_damage}%)"
                    label = f"end_at_damage_{best}pct"
                elif loot is not None and now - loot_at >= self.cfg.loot_stall_s:
                    why = f"no new loot for {now - loot_at:.0f} s at {out.damage:.0f}%"
                    label = f"loot_stall_{out.damage:.0f}pct"
                if why:
                    if not stalled:  # once: a missed button is retried every poll
                        log.info("%s; surrendering", why)
                        save_snapshot(frame.bgr, label, device=self.device)
                        stalled = True
                    if self._surrender(frame):
                        surrendered, out.ended_by = True, "surrender"
                        continue
            self.nav.sleep(self.cfg.watch_poll_s)
        return None

    def _surrender(self, frame: Frame) -> bool:
        """The red button says Surrender until the first star, End Battle after it (#78). Then the
        confirm dialog's Okay; a dialog the classifier does not know still has its Okay there."""
        if not (self._tap_template(frame, "surrender_button") or self._tap_template(frame, "end_battle")):
            return False
        got = self.nav.wait_for({SURRENDER_CONFIRM, BATTLE_END}, 6)
        if got is None:
            self._tap_template(self.nav.classify()[1], "okay_button")
        elif got[0].screen == SURRENDER_CONFIRM:
            self._tap_template(got[1], "okay_button")
        return True

    def _tap_template(self, frame: Frame, name: str) -> bool:
        hit = match(frame, self.nav.store.get(name))
        if hit is None:
            return False
        self.nav.tap_match(hit)
        return True

    def _tap_card(self, card: Card) -> None:
        """Somewhere on the card's picture (above the level badge, below the count)."""
        tap_card(self.nav, card)

    def _read_bar(self, frame: Frame) -> _BarRead | None:
        cards = read_bar(frame.bgr, self.bar)
        if not any(c.kind in (TROOP, SINGLE) for c in cards):
            return None
        return _BarRead(cards)

    def _wide_points(self, base, edge: str) -> list:
        wide = replace(self.deploy, edge=edge.split("+")[0], margin=self.deploy.margin * 3)
        return deploy_sides(base, wide, self.border.ui, self.cfg.sides, red=getattr(self, "_red", None))[1]

    def _deploy_troop(self, card: Card, points: list) -> tuple[int, bool]:
        """Tap until the card greys out; return False if emptying it cannot be confirmed.

        Rounds of `check_every` taps go on while each round changes the card's count, so a big stack
        (150 barbarians) is placed in full; a round that changes nothing means these points are
        refused (inside the red line / blocked) and the caller tries points further out (#98)."""
        taps = 0
        self._tap_card(card)
        self._pause()
        last = capture_bar(self.device)
        while taps < self.cfg.max_taps_per_troop and not self.nav.stop.is_set():
            if self.nav.stop.is_set():
                return taps, False
            n = min(self.cfg.check_every, self.cfg.max_taps_per_troop - taps)
            round_points = [self.nav.human.near(*points[(taps + i) % len(points)]) for i in range(n)]
            batch = getattr(self.device, "tap_many", None)
            if batch is not None:  # #166: one adb call per round (Wi-Fi: ~0.45 s per call)
                batch(round_points)
            else:
                for p in round_points:
                    self.device.tap(*p)
                    self._pause()
            taps += n
            now = capture_bar(self.device)
            if is_used(now, card, self.bar):
                return taps, True
            if count_change(last, now, card) < 3.0:
                return taps, False
            last = now
        return taps, False

    def _cast_spell(self, card: Card, targets: list) -> tuple[int, bool]:
        """One cast per tap, checked each time, until the card greys out. One at a time because a card
        that runs out hands the selection to the next card, and a blind extra tap would cast that."""
        if not targets:
            return 0, False
        self._tap_card(card)
        self._pause()
        last = capture_bar(self.device)
        order = spread(targets, len(targets) // 2, len(targets))  # different spots, middle first
        taps = 0
        while taps < self.cfg.max_spell_taps and not self.nav.stop.is_set():
            self.device.tap(*self.nav.human.near(*order[taps % len(order)]))
            taps += 1
            self.nav.sleep(self.cfg.spell_pause_s)
            now = capture_bar(self.device)
            if is_used(now, card, self.bar):
                return taps, True
            if count_change(last, now, card) < 3.0:
                return taps, False  # the tap cast nothing (on a UI box, or the card is not selected)
            last = now
        return taps, False

    def _pause(self) -> None:
        self.nav.sleep(self.cfg.tap_pause_s)
