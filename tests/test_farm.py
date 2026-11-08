"""Farm loop stop rules and stats, with scripted search/attack results (no device)."""

import random
from types import SimpleNamespace

from cob.attack.loot import Loot
from cob.tasks.farm import STEPS, FarmLimits, FarmTask
from cob.tasks.search import ACCEPTED, FAILED, LOW_GOLD, SearchOutcome
from tests.fakes import FakeClock

BASE = Loot(500_000, 400_000, 3_000)
GAIN = Loot(300_000, 200_000, 1_000)


class Script:
    """search() / attack() return the next scripted result; own() follows a resource ledger."""

    def __init__(self, searches, attacks=(), gain=GAIN):
        self.searches = list(searches)
        self.attacks = list(attacks)
        self.gain = gain
        self.own_now = Loot(2_000_000, 6_000_000, 50_000)
        self.calls = []

    def search(self):
        self.calls.append("search")
        return self.searches.pop(0)

    def attack(self):
        self.calls.append("attack")
        status = self.attacks.pop(0) if self.attacks else "done"
        if status == "done":
            g = self.gain
            self.own_now = Loot(self.own_now.gold + g.gold, self.own_now.elixir + g.elixir,
                                self.own_now.dark + g.dark)
        return SimpleNamespace(status=status, reason="" if status == "done" else "battle did not end")

    def own(self):
        return self.own_now


def _farm(script, **limits):
    clock = FakeClock()
    task = FarmTask(script.search, script.attack, script.own, FarmLimits(**limits), clock=clock,
                    sleep=clock.sleep, rng=random.Random(0))
    return task.run(), clock


def accepted():
    return SearchOutcome(ACCEPTED, BASE, nexts=2)


def test_runs_requested_cycles_and_sums_gains():
    s = Script([accepted() for _ in range(3)])
    stats, _ = _farm(s, max_cycles=3)
    assert stats.stop_reason == "3 cycles done" and stats.attacks == 3
    assert stats.gained == Loot(900_000, 600_000, 3_000)
    assert s.calls == ["search", "attack"] * 3


def test_time_limit():
    s = Script([accepted() for _ in range(50)])
    stats, clock = _farm(s, max_minutes=0.2)  # 12 s; each cycle pauses 3-8 s
    assert stats.stop_reason == "0.2 min elapsed" and 2 <= len(stats.cycles) <= 4


def test_low_gold_stops_without_attacking():
    s = Script([SearchOutcome(LOW_GOLD, reason="own gold below reserve")])
    stats, _ = _farm(s)
    assert stats.stop_reason == "own gold below reserve" and s.calls == ["search"]


def test_other_device_stops_immediately():
    s = Script([SearchOutcome(FAILED, reason="stopped on POPUP_OTHER_DEVICE")])
    stats, _ = _farm(s, max_cycles=10)
    assert stats.stop_reason == "stopped on POPUP_OTHER_DEVICE" and len(stats.cycles) == 1


def test_three_failures_in_a_row_stop():
    s = Script([accepted() for _ in range(10)], attacks=["failed", "failed", "failed"])
    stats, _ = _farm(s)
    assert stats.stop_reason == "3 failures in a row" and stats.attacks == 0


def test_success_resets_failure_count():
    s = Script([accepted() for _ in range(5)], attacks=["failed", "failed", "done", "failed", "failed"])
    stats, _ = _farm(s, max_cycles=5)
    assert stats.stop_reason == "5 cycles done" and stats.attacks == 1


def test_army_not_ready_waits_then_retries():
    army = SearchOutcome(FAILED, reason="army review without Attack! button (army not ready?)")
    s = Script([army, accepted()])
    stats, clock = _farm(s, max_cycles=2)
    assert [c.search for c in stats.cycles] == [FAILED, ACCEPTED] and stats.attacks == 1
    assert clock.t >= 60  # waited for the army


def test_waiting_for_the_army_is_not_a_failure():
    # #178 live: two attack failures and an army wait stopped the run with "3 failures in a row".
    from cob.tasks.search import ARMY_NOT_READY

    army = SearchOutcome(FAILED, reason=ARMY_NOT_READY)
    s = Script([accepted(), accepted(), army, army, accepted()], attacks=["failed", "failed", "done"])
    stats, _ = _farm(s, max_cycles=5)
    assert stats.stop_reason == "5 cycles done"


def test_a_failed_search_mentioning_the_army_is_no_army_wait():
    # "no army review or search after Find a Match" is a failure, not "army not ready".
    lost = SearchOutcome(FAILED, reason="no army review or search after Find a Match")
    s = Script([lost, accepted()])
    stats, clock = _farm(s, max_cycles=2)
    assert clock.t < 60 and stats.attacks == 1


def test_failed_attack_has_no_gain_recorded():
    s = Script([accepted()], attacks=["failed"])
    stats, _ = _farm(s, max_cycles=1)
    assert stats.cycles[0].gained is None and stats.gained == Loot(0, 0, 0)


def test_keyboard_interrupt_returns_stats():
    s = Script([accepted()])

    def boom():
        raise KeyboardInterrupt

    clock = FakeClock()
    calls = iter([s.search, boom])
    task = FarmTask(lambda: next(calls)(), s.attack, s.own, FarmLimits(), clock=clock, sleep=clock.sleep)
    stats = task.run()
    assert stats.stop_reason == "interrupted" and len(stats.cycles) == 1


def test_device_error_stops_with_reason_when_device_lost():
    from cob.device.base import DeviceError

    s = Script([accepted()])

    def lost():
        raise DeviceError("device emulator-5554 not reachable: device 'emulator-5554' not found")

    clock = FakeClock()
    stats = FarmTask(lost, s.attack, s.own, FarmLimits(), clock=clock, sleep=clock.sleep).run()
    assert stats.stop_reason.startswith("device lost") and stats.cycles[0].search == "error"


def test_transient_errors_are_retried_until_the_limit():
    s = Script([accepted()])
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        raise RuntimeError("adb hiccup")

    clock = FakeClock()
    stats = FarmTask(flaky, s.attack, s.own, FarmLimits(), clock=clock, sleep=clock.sleep).run()
    assert stats.stop_reason == "3 failures in a row" and calls["n"] == 3


def _lost_then(script, n_lost):
    from cob.device.base import DeviceError

    state = {"lost": n_lost}

    def search():
        if state["lost"] > 0:
            state["lost"] -= 1
            raise DeviceError("device emulator-5554 not reachable: device 'emulator-5554' not found")
        return script.search()

    return search


def test_device_lost_relaunches_and_continues():
    s = Script([accepted(), accepted()])
    relaunches = []
    clock = FakeClock()
    task = FarmTask(_lost_then(s, 1), s.attack, s.own, FarmLimits(max_cycles=3), clock=clock,
                    sleep=clock.sleep, recover=lambda: relaunches.append(1) or True)
    stats = task.run()
    assert relaunches == [1] and stats.attacks == 2 and stats.stop_reason == "3 cycles done"


def test_recovery_limit_then_stop():
    s = Script([accepted()])
    clock = FakeClock()
    task = FarmTask(_lost_then(s, 5), s.attack, s.own, FarmLimits(max_recoveries=2), clock=clock,
                    sleep=clock.sleep, recover=lambda: True)
    stats = task.run()
    assert task.recoveries == 2 and stats.stop_reason.startswith("device lost")


def test_failed_recovery_stops():
    s = Script([accepted()])
    clock = FakeClock()
    task = FarmTask(_lost_then(s, 1), s.attack, s.own, FarmLimits(), clock=clock, sleep=clock.sleep,
                    recover=lambda: False)
    assert task.run().stop_reason.startswith("device lost") and task.recoveries == 1


def test_blocked_search_waits_then_retries():
    blocked = SearchOutcome(FAILED, reason="search blocked: try again later")
    s = Script([blocked, accepted()])
    stats, clock = _farm(s, max_cycles=2)
    assert stats.attacks == 1 and clock.t >= 120


def test_breaks_every_few_cycles_with_random_length():
    s = Script([accepted() for _ in range(30)])
    rests = []
    clock = FakeClock()
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=24, break_every=8, break_minutes=5),
                    clock=clock, sleep=clock.sleep, rng=random.Random(3), on_break=rests.append)
    stats = task.run()
    assert stats.attacks == 24 and 2 <= task.breaks <= 4 and len(rests) == task.breaks
    assert all(0.6 * 300 <= r <= 1.4 * 300 for r in rests)


def test_breaks_off_by_default():
    s = Script([accepted() for _ in range(12)])
    clock = FakeClock()
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=12), clock=clock, sleep=clock.sleep)
    task.run()
    assert task.breaks == 0


def test_stop_during_break_ends_the_run():
    import threading

    s = Script([accepted() for _ in range(10)])
    stop = threading.Event()
    clock = FakeClock()

    def sleep(sec):  # the stop button pressed while resting
        if sec > 60:
            stop.set()
        clock.sleep(sec)

    task = FarmTask(s.search, s.attack, s.own, FarmLimits(break_every=1, break_minutes=5), stop=stop,
                    clock=clock, sleep=sleep, rng=random.Random(0))
    stats = task.run()
    assert stats.stop_reason == "stopped" and task.breaks == 1


def test_maintenance_runs_before_each_cycle_and_its_errors_are_ignored():
    s = Script([accepted() for _ in range(3)])
    calls = []

    def maint():
        calls.append(len(s.calls))
        if len(calls) == 2:
            raise RuntimeError("collect hiccup")

    clock = FakeClock()
    stats = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=3), clock=clock, sleep=clock.sleep,
                     maintenance=maint).run()
    assert stats.attacks == 3 and calls == [0, 2, 4]  # before each search, never mid-cycle


def test_collect_is_throttled_by_minutes(monkeypatch):
    from types import SimpleNamespace

    import cob.tasks.collect as collect
    from cob.tasks.wiring import FarmParts

    runs = []
    monkeypatch.setattr(collect.CollectTask, "run", lambda self: runs.append(1))
    t = [0.0]
    parts = FarmParts(SimpleNamespace(), None, None, lambda: None, None, collect_minutes=10,
                      clock=lambda: t[0], zoom_out=False)
    for minute in (0, 4, 9, 10, 15, 21):
        t[0] = minute * 60
        parts.maintenance()
    assert len(runs) == 3  # at 0, 10 and 21 minutes
    off = FarmParts(SimpleNamespace(), None, None, lambda: None, None, zoom_out=False)  # collect off
    off.maintenance()
    assert len(runs) == 3



def test_maintenance_zooms_out_at_home_first():
    from types import SimpleNamespace

    from cob.tasks.wiring import FarmParts

    events = []
    nav = SimpleNamespace(go_home=lambda: events.append("home") or SimpleNamespace(ok=True),
                          zoom_out=lambda: events.append("zoom") or 1)
    FarmParts(nav, None, None, lambda: None, None).maintenance()
    assert events == ["home", "zoom"]


def test_resource_misread_is_not_counted_as_a_loss():
    from cob.tasks.farm import _diff

    before = Loot(9_721_228, 6_283_000, 70_000)
    assert _diff(Loot(21_228, 6_283_000, 70_000), before) is None  # dialog hid the first digits
    assert _diff(Loot(9_800_000, 6_100_000, 69_000), before) == Loot(78_772, -183_000, -1_000)


def test_steps_are_reported_in_cycle_order():
    s = Script([accepted() for _ in range(4)])
    clock = FakeClock()
    steps = []
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=4, break_every=1, break_minutes=1),
                    clock=clock, sleep=clock.sleep, rng=random.Random(0), maintenance=lambda: None,
                    on_step=steps.append)
    task.run()
    assert steps[:4] == ["collect", "search", "attack", "return"]
    assert set(steps) <= set(STEPS)
    assert task.breaks > 0 and steps.count("break") == task.breaks  # break_every 1 -> at least one


def test_failing_step_callback_never_breaks_the_loop():
    s = Script([accepted()])
    clock = FakeClock()

    def boom(_name):
        raise RuntimeError("display gone")

    stats = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=1), clock=clock, sleep=clock.sleep,
                     on_step=boom).run()
    assert stats.attacks == 1


def test_phone_locked_stops_the_run_at_once():
    from cob.device.base import PhoneLocked

    s = Script([accepted() for _ in range(3)])
    clock = FakeClock()

    def locked_search():
        raise PhoneLocked("phone locked during the run: unlock it and start again")

    stats = FarmTask(locked_search, s.attack, s.own, FarmLimits(max_cycles=3), clock=clock,
                     sleep=clock.sleep).run()
    assert stats.stop_reason.startswith("phone locked") and len(stats.cycles) == 1


def test_a_crashing_game_stops_the_run_at_once():
    from cob.device.base import GameCrashed

    s = Script([accepted() for _ in range(3)])
    clock = FakeClock()

    def crashing_search():
        raise GameCrashed("Clash of Clans keeps crashing while it starts.")

    stats = FarmTask(crashing_search, s.attack, s.own, FarmLimits(max_cycles=3), clock=clock,
                     sleep=clock.sleep).run()
    assert stats.stop_reason.startswith("Clash of Clans keeps crashing") and len(stats.cycles) == 1


OTHER = SearchOutcome(FAILED, reason="stopped on POPUP_OTHER_DEVICE")


def _other_device_farm(searches, **limits):
    s = Script(searches)
    clock = FakeClock()
    reloads = []
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(**limits), clock=clock, sleep=clock.sleep,
                    rng=random.Random(0), reload_village=lambda: reloads.append(clock.t) or True)
    return task.run(), clock, reloads, s


def test_other_device_wait_reloads_then_farms_on():
    # #117 (opt-in): someone opened the village elsewhere; wait 30 min, tap RELOAD, carry on.
    stats, clock, reloads, s = _other_device_farm([OTHER, accepted(), accepted()], max_cycles=3,
                                                  other_device_wait_minutes=30)
    assert stats.stop_reason == "3 cycles done" and stats.attacks == 2
    assert len(reloads) == 1 and reloads[0] >= 30 * 60


def test_other_device_wait_gives_up_after_three_in_a_row():
    stats, _, reloads, _ = _other_device_farm([OTHER] * 5, other_device_wait_minutes=10)
    assert stats.stop_reason == "stopped on POPUP_OTHER_DEVICE" and len(reloads) == 3


def test_other_device_waits_count_again_after_a_good_cycle():
    stats, _, reloads, _ = _other_device_farm([OTHER, OTHER, OTHER, accepted(), OTHER, OTHER],
                                              other_device_wait_minutes=10, max_cycles=6)
    assert stats.stop_reason == "6 cycles done" and len(reloads) == 5


def test_a_game_that_keeps_failing_on_an_emulator_gets_one_emulator_restart():
    # #132: crash / "isn't responding" again after the app restart -> restart LDPlayer once, farm on.
    from cob.device.base import GameCrashed

    s = Script([accepted() for _ in range(3)])
    clock = FakeClock()
    restarts, crashes = [], [GameCrashed("Clash of Clans keeps crashing or not responding.")]

    def search():
        if crashes:
            raise crashes.pop()
        return s.search()

    stats = FarmTask(search, s.attack, s.own, FarmLimits(max_cycles=3), clock=clock, sleep=clock.sleep,
                     restart_device=lambda: restarts.append(1) or True).run()
    assert restarts == [1] and stats.attacks == 2 and stats.stop_reason == "3 cycles done"


def test_a_second_game_failure_after_the_emulator_restart_stops_the_run():
    from cob.device.base import GameCrashed

    s = Script([])
    clock = FakeClock()
    restarts = []

    def search():
        raise GameCrashed("Clash of Clans keeps crashing or not responding.")

    stats = FarmTask(search, s.attack, s.own, FarmLimits(max_cycles=5), clock=clock, sleep=clock.sleep,
                     restart_device=lambda: restarts.append(1) or True).run()
    assert restarts == [1] and stats.stop_reason.startswith("Clash of Clans keeps crashing")

def test_pause_holds_between_cycles_and_resume_carries_on():
    # #133: Pause waits before the next cycle (never mid-battle); stats of the session are kept.
    s = Script([accepted() for _ in range(3)])
    clock = FakeClock()
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=2), clock=clock, rng=random.Random(0))
    held = []

    def sleep(seconds):
        clock.sleep(seconds)
        if task.pause.is_set():
            held.append(seconds)
            if len(held) == 30:  # Resume after 30 s
                task.pause.clear()

    task._sleep = sleep
    task.pause.set()
    stats = task.run()
    assert stats.attacks == 2 and len(held) == 30 and s.calls[0] == "search"


def test_stop_while_paused_ends_the_run():
    s = Script([accepted()])
    clock = FakeClock()
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=2), clock=clock, rng=random.Random(0))

    def sleep(seconds):
        clock.sleep(seconds)
        task.stop.set()

    task._sleep = sleep
    task.pause.set()
    stats = task.run()
    assert stats.stop_reason == "stopped" and stats.attacks == 0 and s.calls == []


def test_full_storages_stop_the_run_before_searching():
    # #119: gold and elixir both 95 % full -> searching only wastes gold.
    s = Script([accepted() for _ in range(3)])
    clock = FakeClock()
    stats = FarmTask(s.search, s.attack, s.own, FarmLimits(halt_full_percent=95), clock=clock,
                     sleep=clock.sleep, storages=lambda: {"gold": 0.97, "elixir": 0.99}).run()
    assert stats.stop_reason == "storages full (gold 97%, elixir 99%)" and s.calls == []


def test_one_full_storage_keeps_attacking():
    s = Script([accepted() for _ in range(2)])
    clock = FakeClock()
    stats = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=2, halt_full_percent=95), clock=clock,
                     sleep=clock.sleep, storages=lambda: {"gold": 1.0, "elixir": 0.4}).run()
    assert stats.attacks == 2


def test_full_storages_rest_and_attack_again_once_spent():
    # With 'Farm on after a rest': skip the attack, keep maintenance (walls spend), look again later.
    s = Script([accepted() for _ in range(2)])
    clock = FakeClock()
    fills = iter([{"gold": 1.0, "elixir": 1.0}] * 3 + [{"gold": 0.6, "elixir": 0.7}] * 5)
    upkeep = []
    stats = FarmTask(s.search, s.attack, s.own, FarmLimits(max_cycles=2, halt_full_percent=95,
                                                           resume_after_rest=True),
                     clock=clock, sleep=clock.sleep, storages=lambda: next(fills),
                     maintenance=lambda: upkeep.append(1)).run()
    assert stats.attacks == 2 and len(upkeep) == 5 and clock.t >= 3 * 300


HOME_FAIL = SearchOutcome(FAILED, reason="could not reach home")


def _down_farm(searches, down=True, **limits):
    s = Script(searches)
    clock = FakeClock()
    closed, rests = [], []
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(**limits), clock=clock, sleep=clock.sleep,
                    rng=random.Random(0), unavailable=lambda: down, close_game=lambda: closed.append(clock.t),
                    on_break=rests.append)
    return task.run(), closed, rests


def test_game_down_waits_longer_each_time_then_farms_on():
    # #118: stuck loading (maintenance) is waited out with the game closed, not counted as failures.
    stats, closed, rests = _down_farm([HOME_FAIL] * 4 + [accepted()], max_cycles=5)
    assert stats.stop_reason == "5 cycles done" and stats.attacks == 1
    assert len(closed) == 4 and rests == [600, 1200, 1800, 1800]


def test_game_down_too_long_stops_the_run():
    stats, closed, rests = _down_farm([HOME_FAIL] * 20, max_unavailable_minutes=60)
    assert stats.stop_reason == "game unavailable for 60 min"
    assert rests == [600, 1200, 1800]


def test_game_down_wait_off_or_not_down_counts_failures():
    stats, closed, _ = _down_farm([HOME_FAIL] * 3, unavailable_wait_minutes=0)
    assert stats.stop_reason == "3 failures in a row" and closed == []
    stats, closed, _ = _down_farm([HOME_FAIL] * 3, down=False)
    assert stats.stop_reason == "3 failures in a row" and closed == []
