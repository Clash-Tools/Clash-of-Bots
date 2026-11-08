"""Build the farm bot for one device: shared by the CLI and the GUI so both run the same thing."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cob.attack.geometry import load_attack_config
from cob.attack.loot import Loot, LootReader
from cob.core.config import FarmConfig, load_farm_config
from cob.device.base import COC_PACKAGE, DeviceError
from cob.device.phone import PhoneDevice, open_device, reconnect
from cob.screens import ScreenClassifier
from cob.screens.navigator import HOME, Navigator
from cob.tasks.attack import AttackConfig, AttackTask
from cob.tasks.builder import BbAttackTask
from cob.tasks.farm import CycleResult, FarmLimits, FarmTask
from cob.tasks.schedule import install_seed
from cob.tasks.search import ACCEPTED, SearchOutcome, SearchTask
from cob.vision.agree import read_stable
from cob.vision.ocr import DigitReader
from cob.vision.regions import load_regions
from cob.vision.templates import TemplateStore

log = logging.getLogger(__name__)


@dataclass
class FarmParts:
    nav: Navigator
    search: SearchTask
    attack: AttackTask
    own_resources: Callable[[], Loot | None]
    recover: Callable[[], bool] | None  # emulator relaunch, None when not an LDPlayer serial
    bb: BbAttackTask | None = None
    bb_resources: Callable[[], Loot | None] | None = None  # Builder Base gold + elixir (dark = 0)
    collect_minutes: int = 0  # 0 = no collecting
    clock: Callable[[], float] = time.monotonic
    _last_collect: float | None = None

    zoom_out: bool = True
    walls: object | None = None  # WallTask when farm.json wall_upgrades > 0
    wall_upgrades: int = 0
    walls_stopped: str = ""  # set after an unsafe result: no more wall spending this run
    request_minutes: int = 0
    _last_request: float | None = None
    _last_bb_collect: float | None = None
    restart_device: Callable[[], bool] | None = None  # #132: LDPlayer quit + relaunch, None on phones
    army_recipe: int = 0  # #185: Saved Recipe loaded when a run starts; 0 = keep the army

    def prepare_army(self) -> bool:
        from cob.tasks.army import ArmyRecipe

        return ArmyRecipe(self.nav).select(self.army_recipe)

    def io_stats(self) -> dict[str, tuple[int, float]]:
        io = getattr(self.nav.device, "io", None)
        return io.snapshot() if io is not None else {}

    def storages(self) -> dict[str, float] | None:
        """#119: gold / elixir storage fill from the home screen's resource bar; None when not at home."""
        from cob.attack.storage import storage_fill

        if not self.nav.go_home().ok:
            return None
        got = self.nav.wait_for({HOME}, 10)
        return storage_fill(got[1]) if got else None

    def close_game(self) -> None:
        """#120: close the game for a long rest; the next cycle's go_home opens it again."""
        self.nav.device.app_stop(COC_PACKAGE)

    def maintenance(self) -> None:
        """Before each cycle at home: zoom the camera out (collector bubbles and the boat stay on
        screen), then collect resource bubbles when due."""
        if self.zoom_out and self.nav.go_home().ok:
            self.nav.zoom_out()
        if self.collect_minutes <= 0:
            return
        now = self.clock()
        if self._last_collect is not None and now - self._last_collect < self.collect_minutes * 60:
            return
        from cob.tasks.collect import CollectTask

        CollectTask(self.nav).run()
        self._last_collect = now

    def upgrade_walls(self) -> None:
        if self.walls is None or self.wall_upgrades <= 0 or self.walls_stopped:
            return
        out = self.walls.run(self.wall_upgrades)
        if out.unsafe:
            self.walls_stopped = out.reason
            log.error("walls stopped for this run: %s", out.reason)

    def request_troops(self) -> None:
        if self.request_minutes <= 0:
            return
        now = self.clock()
        if self._last_request is not None and now - self._last_request < self.request_minutes * 60:
            return
        from cob.tasks.request import RequestTask

        RequestTask(self.nav).run()
        self._last_request = now

    def bb_maintain(self) -> None:
        """Builder Base before each cycle: collect its collectors when due (same interval as home)."""
        if self.collect_minutes <= 0:
            return
        now = self.clock()
        if self._last_bb_collect is not None and now - self._last_bb_collect < self.collect_minutes * 60:
            return
        from cob.tasks.builder import go_to_builder_base
        from cob.tasks.collect import collect_builder_base

        if go_to_builder_base(self.nav):  # zooms out on arrival
            collect_builder_base(self.nav)
            self._last_bb_collect = now

    def close(self) -> None:
        """End of a run: a phone gets its own display values back (emulators: nothing to do)."""
        end = getattr(self.nav.device, "end", None)
        if end is not None:
            end()

    def maintain(self) -> None:
        """All home maintenance before a cycle: zoom out + collect (when due), walls, CC request."""
        self.maintenance()
        self.upgrade_walls()
        self.request_troops()

    def farm_task(self, limits: FarmLimits, on_cycle: Callable[[CycleResult], None] | None = None,
                  on_break: Callable[[float], None] | None = None,
                  on_step: Callable[[str], None] | None = None) -> FarmTask:
        from cob.core import history

        def cycle_done(cycle: CycleResult) -> None:
            history.append(cycle, mode="home")  # every run, CLI or GUI, ends up in history.csv
            if on_cycle:
                on_cycle(cycle)

        return FarmTask(lambda: self.search.run(dry_run=False), self.attack.run, self.own_resources,
                        limits, stop=self.nav.stop, on_cycle=cycle_done, recover=self.recover,
                        restart_device=self.restart_device, storages=self.storages,
                        io=self.io_stats,
                        on_break=on_break, maintenance=self.maintain, on_step=on_step, usage=history_usage,
                        reload_village=self.nav.reload_other_device, close_game=self.close_game,
                        prepare=self.prepare_army if self.army_recipe else None,
                        unavailable=self.nav.game_unavailable)


def _bb_cycle_search() -> SearchOutcome:
    # Builder Base has no loot search: every cycle is an attack.
    return SearchOutcome(ACCEPTED, reason="builder base")


def bb_farm_task(parts: FarmParts, limits: FarmLimits,
                 on_cycle: Callable[[CycleResult], None] | None = None,
                 on_break: Callable[[float], None] | None = None,
                 on_step: Callable[[str], None] | None = None) -> FarmTask:
    """Builder Base attacks driven by the same loop (limits, breaks, stop, relaunch, history)."""
    from cob.core import history

    def cycle_done(cycle: CycleResult) -> None:
        history.append(cycle, mode="bb")
        if on_cycle:
            on_cycle(cycle)

    return FarmTask(_bb_cycle_search, parts.bb.run, parts.bb_resources or (lambda: None), limits,
                    stop=parts.nav.stop, on_cycle=cycle_done, recover=parts.recover, on_break=on_break,
                    restart_device=getattr(parts, "restart_device", None),
                    maintenance=parts.bb_maintain, on_step=on_step, usage=history_usage,
                    reload_village=getattr(parts.nav, "reload_other_device", None),
                    close_game=getattr(parts, "close_game", None))


def _card_library():
    """Card recognition (#troop detection); a broken database or folder must not stop a run."""
    from cob.attack.cards import library

    try:
        return library()
    except Exception as exc:
        log.warning("card library unavailable: %s", exc)
        return None


def farm_limits(cfg: FarmConfig, max_cycles: int = 0, max_minutes: float = 0.0) -> FarmLimits:
    """Run limits from the command line / window plus breaks and safety rules from farm.json."""
    return FarmLimits(max_cycles=max_cycles, max_minutes=max_minutes, break_every=cfg.break_every,
                      break_minutes=float(cfg.break_minutes), max_failures_in_row=cfg.max_failures,
                      daily_minutes=cfg.daily_minutes, daily_attacks=cfg.daily_attacks,
                      quiet_from=cfg.quiet_from, quiet_to=cfg.quiet_to,
                      daily_attacks_max=cfg.daily_attacks_max, off_hours=cfg.off_hours,
                      schedule_seed=install_seed(), other_device_wait_minutes=float(cfg.other_device_wait),
                      resume_after_rest=bool(cfg.resume_after_rest),
                      close_game_resting=bool(cfg.close_game_resting),
                      halt_full_percent=cfg.halt_full_percent,
                      unavailable_wait_minutes=float(cfg.unavailable_wait))


def history_usage() -> tuple[float, int]:
    """Today's farming seconds and attacks from history.csv (every run, CLI and GUI, appends there)."""
    from datetime import date

    from cob.core import history
    from cob.tasks.schedule import today_usage

    return today_usage(history.read(limit=5_000), date.today())


def emulator_restart(serial: str) -> Callable[[], bool] | None:
    """#132: quit + relaunch hook for an LDPlayer instance whose game keeps failing, else None."""
    from cob.device.ldplayer import LdConsole, index_for_serial

    index = index_for_serial(serial)
    if index is None:
        return None
    try:
        console = LdConsole()
    except DeviceError:
        return None
    return lambda: console.restart(index, serial)


def emulator_recovery(serial: str) -> Callable[[], bool] | None:
    """Relaunch hook for the farm loop when the serial is an LDPlayer instance, else None."""
    from cob.device.ldplayer import LdConsole, index_for_serial

    index = index_for_serial(serial)
    if index is None:
        return None
    try:
        console = LdConsole()
    except DeviceError as exc:
        log.info("no emulator recovery: %s", exc)
        return None
    return lambda: console.ensure_running(index, serial)


def build_farm(serial: str, templates: Path | None = None, cfg: FarmConfig | None = None) -> FarmParts:
    store = TemplateStore(templates)
    regions = load_regions(store.root)
    digits = DigitReader(store.load_dir("digits/loot"))
    bar = LootReader(digits, regions["bar"])
    nav = Navigator(open_device(serial), ScreenClassifier(store))  # phones: display mode on
    cfg = cfg or load_farm_config()
    search = SearchTask(nav, LootReader(digits, regions["loot"]), bar, cfg)
    attack = AttackTask(nav, *load_attack_config(store.root),
                        AttackConfig(loot_stall_s=cfg.loot_stall_s, end_at_damage=cfg.end_at_damage,
                                     sides=2 if cfg.two_sides else 1,
                                     cast_spells=bool(cfg.cast_spells)),
                        loot=LootReader(digits, regions["loot"]), cards=_card_library())

    def own_resources() -> Loot | None:
        """Own storages, once two reads 1.5 s apart agree: collected loot and battle rewards fly into the
        storages for a few seconds, and a read mid-animation counted collected loot as farmed (#78).
        No agreement -> None, so the cycle records no gain rather than a wrong one."""
        if not nav.go_home().ok or nav.wait_for({HOME}, 10) is None:
            return None
        return read_stable(lambda: nav.classify()[1], bar.read, need=2, max_frames=6, interval_s=1.5,
                           stop=nav.stop)

    border, deploy, bar_cfg, _ = load_attack_config(store.root)
    bb = BbAttackTask(nav, border, deploy, bar_cfg)

    def bb_resources() -> Loot | None:
        """Builder Base has gold and elixir in the same rows as the home village, and no dark elixir."""
        from cob.tasks.builder import BB_HOME, go_to_builder_base

        if not go_to_builder_base(nav):
            return None
        for _ in range(4):  # counters animate for a moment after a battle: retry until both read
            got = nav.wait_for({BB_HOME}, 10)
            if got is None:
                return None
            gold = digits.read(got[1], regions["bar"]["gold"])
            elixir = digits.read(got[1], regions["bar"]["elixir"])
            if gold is not None and elixir is not None:
                return Loot(gold, elixir, 0)
            nav.sleep(1.5)
        log.warning("Builder Base resources unreadable")
        return None

    walls = None
    if cfg.wall_upgrades > 0:
        from cob.tasks.walls import WallTask

        walls = WallTask(nav, bar, DigitReader(store.load_dir("digits/cost")), cfg.wall_reserve)
    recover = emulator_recovery(serial)
    if recover is None and isinstance(nav.device, PhoneDevice):
        recover = lambda: reconnect(nav.device)  # noqa: E731  (USB drop: wait, display mode back on)
    return FarmParts(nav, search, attack, own_resources, recover, bb, bb_resources,
                     collect_minutes=cfg.collect_minutes, walls=walls, wall_upgrades=cfg.wall_upgrades,
                     request_minutes=cfg.request_minutes, restart_device=emulator_restart(serial),
                     army_recipe=cfg.army_recipe)
