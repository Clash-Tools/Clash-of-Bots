"""Farm loop: search -> attack -> home, repeated, with stats and stop rules.

Steps are injected as plain callables so the loop is tested without a device; the CLI wires the
real SearchTask / AttackTask / resource-bar reader.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from cob.attack.loot import Loot
from cob.core.timing import IoStats
from cob.device.base import GameCrashed, RunBlocked
from cob.tasks.schedule import schedule_stop
from cob.tasks.search import ARMY_NOT_READY, FAILED, HOME_FAILED, LOW_GOLD, SearchOutcome

log = logging.getLogger(__name__)

OTHER_DEVICE = "POPUP_OTHER_DEVICE"  # "Another device is connecting to this Village."

STEPS = ("collect", "search", "attack", "return", "break")  # on_step names, in cycle order


@dataclass(frozen=True)
class FarmLimits:
    max_cycles: int = 0  # 0 = no limit
    max_minutes: float = 0.0  # 0 = no limit
    max_failures_in_row: int = 3
    army_wait_s: float = 60.0  # army review without Attack! -> wait this long before retrying
    pause_s: tuple[float, float] = (3.0, 8.0)  # random pause between cycles
    max_recoveries: int = 2  # emulator relaunches per run when the device is lost
    blocked_wait_s: float = 120.0  # matchmaking said "try again later"
    break_every: int = 0  # rest after about this many cycles (+-2 random); 0 = no breaks
    break_minutes: float = 5.0  # rest length (0.6x..1.4x random)
    daily_minutes: int = 0  # D-027: stop when today's recorded farming time reaches this; 0 = off
    daily_attacks: int = 0  # stop when today's recorded attacks reach this; 0 = off
    quiet_from: int = 0  # quiet hours (local hour); equal to quiet_to = off
    quiet_to: int = 0
    daily_attacks_max: int = 0  # #121: daily_attacks..daily_attacks_max, drawn once a day
    off_hours: int = 0  # #121: a random off-period of this many hours a day
    schedule_seed: int = 0  # makes the daily draws differ between installs
    other_device_wait_minutes: float = 0.0  # #117: wait, then reload, instead of stopping; 0 = stop
    max_other_device_waits: int = 3  # waits in a row before the run stops anyway
    resume_after_rest: bool = False  # #120 (D-031): rest through quiet hours / limits instead of stopping
    close_game_resting: bool = False  # close the game while resting
    rest_check_s: float = 300.0  # how often a rest checks whether farming is allowed again
    halt_full_percent: int = 0  # #119: no attacks while gold and elixir are both this full; 0 = off
    unavailable_wait_minutes: float = 10.0  # #118: game down -> close it, wait, retry; 0 = count as failure
    max_unavailable_minutes: float = 180.0  # total wait for a game that stays down before the run stops


@dataclass
class CycleResult:
    n: int
    search: str
    nexts: int = 0
    loot: Loot | None = None  # base attacked
    attack: str = ""  # "done" / "failed" / "" (no attack)
    gained: Loot | None = None  # own resources after - before (net of search costs)
    seconds: float = 0.0
    reason: str = ""


@dataclass
class FarmStats:
    cycles: list[CycleResult] = field(default_factory=list)
    stop_reason: str = ""
    seconds: float = 0.0

    @property
    def attacks(self) -> int:
        return sum(1 for c in self.cycles if c.attack == "done")

    @property
    def gained(self) -> Loot:
        known = [c.gained for c in self.cycles if c.gained is not None]
        return Loot(sum(g.gold for g in known), sum(g.elixir for g in known), sum(g.dark for g in known))


def _diff(after: Loot | None, before: Loot | None) -> Loot | None:
    """Net change of own resources, or None when a read looks wrong.

    An attack cannot cost more than half of a resource; a drop like that means a dialog covered the
    resource bar and digits were lost (live: 9,721,228 read as 21,228), so the cycle gets no gain.
    """
    if after is None or before is None:
        return None
    for b, a in ((before.gold, after.gold), (before.elixir, after.elixir), (before.dark, after.dark)):
        if b > 0 and a < b * 0.5:
            log.warning("own resources read %s after %s: looks like a misread, gain not counted",
                        after, before)
            return None
    return Loot(after.gold - before.gold, after.elixir - before.elixir, after.dark - before.dark)


class FarmTask:
    def __init__(self, search: Callable[[], SearchOutcome], attack: Callable[[], object],
                 own_resources: Callable[[], Loot | None], limits: FarmLimits | None = None, *,
                 stop: threading.Event | None = None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] | None = None, rng: random.Random | None = None,
                 on_cycle: Callable[[CycleResult], None] | None = None,
                 recover: Callable[[], bool] | None = None,
                 on_break: Callable[[float], None] | None = None,
                 maintenance: Callable[[], object] | None = None,
                 on_step: Callable[[str], None] | None = None,
                 usage: Callable[[], tuple[float, int]] | None = None,
                 now: Callable[[], datetime] = datetime.now,
                 reload_village: Callable[[], bool] | None = None,
                 close_game: Callable[[], None] | None = None,
                 restart_device: Callable[[], bool] | None = None,
                 storages: Callable[[], dict[str, float] | None] | None = None,
                 io: Callable[[], dict[str, tuple[int, float]]] | None = None,
                 prepare: Callable[[], object] | None = None,
                 unavailable: Callable[[], bool] | None = None):
        self.search = search
        self._prepare = prepare  # #185: once before the first cycle (load the chosen army recipe)
        self._unavailable = unavailable  # #118: True when the last home trip got stuck loading
        self._down_waits = 0  # unavailable waits since the game last worked
        self._down_s = 0.0  # seconds waited for it
        self.attack = attack
        self.own_resources = own_resources
        self.limits = limits or FarmLimits()
        self.stop = stop or threading.Event()
        self._clock = clock
        self._sleep = sleep or (lambda s: self.stop.wait(s))
        self._rng = rng or random.Random()
        self._on_cycle = on_cycle
        self._recover = recover  # e.g. relaunch the emulator; True when the device is back
        self.recoveries = 0
        self._on_break = on_break  # GUI status: called with the break length in seconds
        self._maintenance = maintenance  # e.g. collect resources; runs at home before each cycle
        self.breaks = 0
        self._next_break = self._draw_break_at(0)
        # GUI step pipeline: "collect", "search", "attack", "return", "break" (STEPS).
        self._on_step = on_step
        self._usage = usage or (lambda: (0.0, 0))  # today's (seconds, attacks); wiring reads history.csv
        self._now = now
        self._reload_village = reload_village  # taps RELOAD on "another device is connecting" (#117)
        self._device_waits = 0  # other-device waits in a row
        self._close_game = close_game  # #120: closes the game for a long rest
        self._restart_device = restart_device  # #132: quit + relaunch the emulator (LDPlayer only)
        self._storages = storages  # #119: gold / elixir storage fill 0..1, read at home
        self._io = io  # #166: device call counters, for the per-cycle timing line
        self._step_name: str | None = None
        self._step_at = 0.0
        self._step_times: dict[str, float] = {}
        self._io_at: dict[str, tuple[int, float]] = {}
        self._full = False  # storages were full at the last check
        self.device_restarts = 0
        self.pause = threading.Event()  # #133: set = hold between cycles (GUI Pause); stats are kept
        self._resting: str | None = None  # reason of the rest under way
        self.rests = 0

    def _step(self, name: str) -> None:
        self._time_step(name)
        if self._on_step:
            try:
                self._on_step(name)
            except Exception:  # a display hook must never break the farm loop
                log.exception("step callback failed")

    def run(self) -> FarmStats:
        stats = FarmStats()
        start = self._clock()
        try:
            if self._prepare is not None and not self.stop.is_set():
                try:
                    self._prepare()
                except Exception as exc:  # setting up the army must never stop the run by itself
                    log.warning("run preparation failed: %s", exc)
            stats.stop_reason = self._loop(stats, start)
        except KeyboardInterrupt:
            stats.stop_reason = "interrupted"
        stats.seconds = self._clock() - start
        g = stats.gained
        log.info("farm stopped (%s): %d cycles, %d attacks, net gold %+d elixir %+d dark %+d in %.0f min",
                 stats.stop_reason, len(stats.cycles), stats.attacks, g.gold, g.elixir, g.dark,
                 stats.seconds / 60)
        return stats

    def _loop(self, stats: FarmStats, start: float) -> str:
        lim = self.limits
        failures = 0
        while True:
            self._hold()
            if self.stop.is_set():
                return "stopped"
            if lim.max_cycles and len(stats.cycles) >= lim.max_cycles:
                return f"{lim.max_cycles} cycles done"
            if lim.max_minutes and self._clock() - start >= lim.max_minutes * 60:
                return f"{lim.max_minutes:g} min elapsed"
            if failures >= lim.max_failures_in_row:
                return f"{failures} failures in a row"
            if reason := schedule_stop(lim.daily_minutes, lim.daily_attacks, lim.quiet_from, lim.quiet_to,
                                       self._usage, self._now(), lim.daily_attacks_max, lim.off_hours,
                                       lim.schedule_seed):
                if not lim.resume_after_rest:
                    return reason
                self._rest(reason)
                continue
            if self._resting:
                log.info("rest over (%s); farming again", self._resting)
                self._resting = None

            t0 = self._clock()
            try:
                cycle_stop = self._cycle(stats, t0)
            except KeyboardInterrupt:
                raise
            except RunBlocked as exc:  # a locked phone (#86) or a crashing game: stop at once
                stats.cycles.append(CycleResult(len(stats.cycles) + 1, "error", reason=str(exc),
                                                seconds=self._clock() - t0))
                if isinstance(exc, GameCrashed) and self._restart_device_once():
                    continue  # #132: a fresh emulator often fixes a game that keeps failing
                return str(exc)
            except Exception as exc:  # device lost / adb error: record, retry, give up after the limit
                log.error("cycle %d failed: %s", len(stats.cycles) + 1, exc)
                failures += 1
                stats.cycles.append(CycleResult(len(stats.cycles) + 1, "error", reason=str(exc),
                                                seconds=self._clock() - t0))
                if self._device_lost(exc):
                    if not self._try_recover():
                        return f"device lost: {exc}"
                    failures = 0  # fresh emulator: start counting again
                    continue
                self._sleep(self._rng.uniform(*lim.pause_s))
                continue
            if isinstance(cycle_stop, str):
                return cycle_stop
            if cycle_stop is not None:
                failures = 0 if cycle_stop else failures + 1
            if self._next_break and len(stats.cycles) >= self._next_break:
                self._take_break(len(stats.cycles))
            else:
                self._sleep(self._rng.uniform(*lim.pause_s))

    def _time_step(self, name: str | None) -> None:
        """#166: time spent per step (collect / search / attack / return / break) in this cycle."""
        now = self._clock()
        if self._step_name is not None:
            spent = now - self._step_at
            self._step_times[self._step_name] = self._step_times.get(self._step_name, 0.0) + spent
        self._step_name, self._step_at = name, now

    def _cycle(self, stats: FarmStats, t0: float) -> str | bool | None:
        """One search (+ attack). Returns a stop reason, True on success, False on a failure, None when
        neither (waited for the army)."""
        self._step_times, self._step_name = {}, None
        self._io_at = self._io() if self._io else {}
        if self._maintenance is not None:
            self._step("collect")
            try:
                self._maintenance()  # before the resource read, so collected loot is not counted as farmed
            except Exception as exc:
                log.warning("maintenance failed: %s", exc)
        if (full := self._storages_full()) is not None:
            return full
        before = self.own_resources()
        log.info("own resources before: %s", before or "unreadable")  # #91: gains to check against the screen
        self._step("search")
        found = self.search()
        cycle = CycleResult(len(stats.cycles) + 1, found.status, found.nexts, found.loot, reason=found.reason)
        if found.status == FAILED and found.reason.startswith("stopped on"):
            self._finish(stats, cycle, t0, before)
            if found.reason.endswith(OTHER_DEVICE) and self._wait_out_other_device():
                return True
            return found.reason  # e.g. village open on another device: never fight it
        self._device_waits = 0
        if found.status == FAILED and found.reason == HOME_FAILED and self._game_down():
            self._finish(stats, cycle, t0, before)
            return self._wait_out_game_down()
        if found.status != FAILED:
            self._down_waits, self._down_s = 0, 0.0
        if found.status == LOW_GOLD:
            self._finish(stats, cycle, t0, before)
            return "own gold below reserve"
        ok = False
        if found.attack:
            self._step("attack")
            result = self.attack()
            cycle.attack = getattr(result, "status", "failed")
            cycle.reason = getattr(result, "reason", "") or cycle.reason
            ok = cycle.attack == "done"
            self._step("return")
        elif found.reason == ARMY_NOT_READY:
            # The army is still training: wait, and do not count it as a failure (#178: the old substring
            # test also caught "no army review or search after Find a Match", a real failure).
            log.info("army not ready; waiting %.0f s", self.limits.army_wait_s)
            self._sleep(self.limits.army_wait_s)
            self._finish(stats, cycle, t0, before)
            return None
        elif "try again later" in found.reason:
            log.info("matchmaking blocked; waiting %.0f s", self.limits.blocked_wait_s)
            self._sleep(self.limits.blocked_wait_s)
        self._finish(stats, cycle, t0, before)
        return ok

    def _game_down(self) -> bool:
        if self.limits.unavailable_wait_minutes <= 0 or self._unavailable is None:
            return False
        try:
            return bool(self._unavailable())
        except Exception as exc:
            log.debug("unavailable check failed: %s", exc)
            return False

    def _wait_out_game_down(self) -> str | None:
        """#118: the game never got past loading (maintenance break, server outage, forced update).
        Close it, wait (10, 20, 30, 30... min with the default), and try again without counting a failure;
        past max_unavailable_minutes in total the run stops. None = neutral cycle, str = stop reason."""
        lim = self.limits
        if self._down_s >= lim.max_unavailable_minutes * 60:
            return f"game unavailable for {self._down_s / 60:.0f} min"
        self._down_waits += 1
        seconds = min(lim.unavailable_wait_minutes * 60 * min(self._down_waits, 3),
                      lim.max_unavailable_minutes * 60 - self._down_s)
        log.warning("game unavailable (stuck loading: maintenance or servers?); closing it and waiting "
                    "%.0f min (%d)", seconds / 60, self._down_waits)
        if self._close_game is not None:
            try:
                self._close_game()
            except Exception as exc:
                log.warning("closing the game failed: %s", exc)
        self._step("break")
        if self._on_break:
            self._on_break(seconds)
        self._sleep(seconds)
        self._down_s += seconds
        return None

    def _restart_device_once(self) -> bool:
        """#132: the game crashed or stopped responding again after its restart. On an emulator, restart
        the whole instance once per run; phones (no hook) stop as before."""
        if self._restart_device is None or self.device_restarts >= 1:
            return False
        self.device_restarts += 1
        log.warning("the game keeps failing; restarting the emulator")
        try:
            return bool(self._restart_device())
        except Exception as exc:
            log.error("emulator restart failed: %s", exc)
            return False

    def _storages_full(self) -> str | bool | None:
        """#119: with gold and elixir both at least halt_full_percent full, attacking only wastes search
        gold. Stop the run, or (Farm on after a rest, D-031) skip the attack and look again in a few
        minutes; maintenance (collect, walls) keeps running meanwhile. None = carry on with the cycle."""
        pct = self.limits.halt_full_percent
        if pct <= 0 or self._storages is None:
            return None
        fill = self._storages()
        if not fill:
            return None
        log.info("storages: gold %.0f%%, elixir %.0f%% full", 100 * fill["gold"], 100 * fill["elixir"])
        if min(fill["gold"], fill["elixir"]) * 100 < pct:
            if self._full:
                log.info("storages below %d%% again; attacking", pct)
            self._full = False
            return None
        reason = f"storages full (gold {100 * fill['gold']:.0f}%, elixir {100 * fill['elixir']:.0f}%)"
        if not self.limits.resume_after_rest:
            return reason
        if not self._full:
            log.info("%s; not attacking, looking again every %.0f min", reason, self.limits.rest_check_s / 60)
        self._full = True
        self._step("break")
        if self._on_break:
            self._on_break(self.limits.rest_check_s)
        self._sleep(self.limits.rest_check_s)
        return True

    def _hold(self) -> None:
        """#133: Pause takes effect here, between cycles (a battle or search is never left half done);
        the run waits until Resume or Stop."""
        if not self.pause.is_set():
            return
        log.info("paused between cycles; waiting for Resume")
        self._step("break")  # the pipeline shows a held run like a break
        while self.pause.is_set() and not self.stop.is_set():
            self._sleep(1.0)
        if not self.stop.is_set():
            log.info("resumed")

    def _rest(self, reason: str) -> None:
        """#120 (D-031): sleep through quiet hours, a random rest or a reached daily limit, checking every
        few minutes; the next cycle reopens the game if it was closed."""
        if self._resting is None:
            self.rests += 1
            log.info("resting: %s; farming starts again when allowed (checked every %.0f min)", reason,
                     self.limits.rest_check_s / 60)
            if self.limits.close_game_resting and self._close_game is not None:
                try:
                    self._close_game()
                except Exception as exc:  # the rest goes on either way
                    log.warning("could not close the game: %s", exc)
        self._resting = reason
        self._step("break")
        if self._on_break:
            self._on_break(self.limits.rest_check_s)
        self._sleep(self.limits.rest_check_s)

    def _wait_out_other_device(self) -> bool:
        """#117 (opt-in): someone opened the village elsewhere. Wait, then reload and carry on; False =
        stop the run (the default, the wait is off, or it happened too many times in a row)."""
        minutes = self.limits.other_device_wait_minutes
        if minutes <= 0 or self._reload_village is None:
            return False
        if self._device_waits >= self.limits.max_other_device_waits:
            log.warning("village opened on another device %d times in a row; stopping", self._device_waits)
            return False
        self._device_waits += 1
        log.info("village opened on another device; waiting %.0f min, then reloading (%d/%d)", minutes,
                 self._device_waits, self.limits.max_other_device_waits)
        self._step("break")
        if self._on_break:
            self._on_break(minutes * 60)
        self._sleep(minutes * 60)
        if self.stop.is_set():
            return False
        if not self._reload_village():
            log.warning("no RELOAD button on the other-device popup; trying the next cycle anyway")
        return True

    def _draw_break_at(self, done: int) -> int:
        """Cycle count for the next break (0 = never)."""
        n = self.limits.break_every
        return done + max(1, n + self._rng.randint(-2, 2)) if n > 0 else 0

    def _take_break(self, done: int) -> None:
        seconds = self.limits.break_minutes * 60 * self._rng.uniform(0.6, 1.4)
        self.breaks += 1
        log.info("break %d after %d cycles: resting %.1f min", self.breaks, done, seconds / 60)
        self._step("break")
        if self._on_break:
            self._on_break(seconds)
        self._sleep(seconds)
        self._next_break = self._draw_break_at(done)

    def _try_recover(self) -> bool:
        if self._recover is None or self.recoveries >= self.limits.max_recoveries:
            return False
        self.recoveries += 1
        log.warning("device lost; recovery %d/%d", self.recoveries, self.limits.max_recoveries)
        try:
            return bool(self._recover())
        except Exception as exc:
            log.error("recovery failed: %s", exc)
            return False

    @staticmethod
    def _device_lost(exc: Exception) -> bool:
        text = str(exc)
        return "not reachable" in text or "not found" in text or "returned 0 bytes" in text

    def _finish(self, stats: FarmStats, cycle: CycleResult, t0: float, before: Loot | None) -> None:
        after = self.own_resources() if cycle.attack == "done" else None
        if after is not None:
            log.info("own resources after: %s", after)
        cycle.gained = _diff(after, before)
        cycle.seconds = self._clock() - t0
        stats.cycles.append(cycle)
        log.info("cycle %d: search %s (%d nexts) %s attack %s gained %s in %.0fs%s", cycle.n,
                 cycle.search, cycle.nexts, cycle.loot or "-", cycle.attack or "-", cycle.gained or "-",
                 cycle.seconds, f" ({cycle.reason})" if cycle.reason else "")
        self._time_step(None)
        steps = ", ".join(f"{k} {v:.0f}s" for k, v in self._step_times.items()) or "-"
        io = IoStats.since(self._io_at, self._io()) if self._io else "-"
        log.info("cycle %d timing: %s; device: %s", cycle.n, steps, io)
        if self._on_cycle:
            self._on_cycle(cycle)
