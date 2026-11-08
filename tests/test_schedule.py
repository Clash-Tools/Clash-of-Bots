import random
from datetime import date, datetime, timedelta

import pytest

from cob.core.config import FarmConfig, load_farm_config, save_farm_config
from cob.tasks.farm import FarmLimits, FarmTask
from cob.tasks.schedule import in_quiet_hours, schedule_stop, today_usage
from cob.tasks.wiring import farm_limits
from tests.fakes import FakeClock
from tests.test_farm import Script, accepted


@pytest.mark.parametrize("hour, start, end, quiet", [
    (23, 23, 7, True), (3, 23, 7, True), (7, 23, 7, False), (12, 23, 7, False),
    (13, 12, 14, True), (14, 12, 14, False), (5, 0, 0, False),
])
def test_quiet_hours(hour, start, end, quiet):
    assert in_quiet_hours(datetime(2026, 10, 26, hour, 30), start, end) is quiet


def test_today_usage_counts_only_today():
    rows = [{"time": "2026-10-26 01:00:00", "seconds": "120", "attack": "done"},
            {"time": "2026-10-26 02:00:00", "seconds": "60", "attack": "failed"},
            {"time": "2026-10-25 23:59:00", "seconds": "999", "attack": "done"},
            {"time": "2026-10-26 03:00:00", "seconds": "", "attack": "done"}]
    assert today_usage(rows, date(2026, 10, 26)) == (180.0, 2)


def test_schedule_stop_reasons_and_lazy_usage():
    calls = []

    def usage():
        calls.append(1)
        return 3600.0, 10

    noon = datetime(2026, 10, 26, 12)
    assert schedule_stop(0, 0, 0, 0, usage, noon) is None and calls == []  # no limits: history never read
    assert schedule_stop(60, 0, 0, 0, usage, noon) == "daily limit: 60 min played today"
    assert schedule_stop(0, 10, 0, 0, usage, noon) == "daily limit: 10 attacks today"
    assert schedule_stop(120, 11, 0, 0, usage, noon) is None
    assert schedule_stop(0, 0, 11, 13, usage, noon) == "quiet hours 11:00-13:00"


def test_farm_loop_stops_on_daily_limit():
    s = Script([accepted() for _ in range(5)])
    clock = FakeClock()
    done = []

    def usage():  # every finished cycle adds 60 s (history.csv grows the same way)
        return 60.0 * len(done), len(done)

    task = FarmTask(s.search, s.attack, s.own, FarmLimits(daily_attacks=2), clock=clock, sleep=clock.sleep,
                    rng=random.Random(0), on_cycle=done.append, usage=usage,
                    now=lambda: datetime(2026, 10, 26, 12))
    stats = task.run()
    assert stats.stop_reason == "daily limit: 2 attacks today" and stats.attacks == 2


def test_new_config_fields_round_trip_and_clamp(tmp_path):
    p = tmp_path / "farm.json"
    cfg = FarmConfig(max_failures=5, daily_minutes=240, daily_attacks=35, quiet_from=23, quiet_to=7)
    save_farm_config(cfg, p)
    assert load_farm_config(p) == cfg
    p.write_text('{"quiet_from": 30, "max_failures": 0}', "utf-8")
    loaded = load_farm_config(p)
    assert loaded.quiet_from == 23 and loaded.max_failures == 1
    lim = farm_limits(cfg)
    assert (lim.max_failures_in_row, lim.daily_minutes, lim.quiet_to) == (5, 240, 7)


def test_daily_attack_limit_is_drawn_once_a_day_from_the_range():
    # #121: a fixed limit looks regular; each day gets its own number in the range, the same all day.
    from cob.tasks.schedule import daily_attack_limit

    days = [date(2026, 11, d) for d in range(1, 29)]
    limits = [daily_attack_limit(40, 60, d, seed=7) for d in days]
    assert all(40 <= n <= 60 for n in limits) and len(set(limits)) > 5
    assert daily_attack_limit(40, 60, days[0], seed=7) == limits[0]  # same day, same limit
    assert daily_attack_limit(40, 0, days[0]) == 40 and daily_attack_limit(0, 60, days[0]) == 0


def test_random_off_period_moves_each_day_and_runs_past_midnight():
    from cob.tasks.schedule import in_off_period, off_start

    first = date(2026, 1, 1)
    starts = [off_start(3, first + timedelta(days=d), seed=7) for d in range(60)]
    assert len(set(starts)) > 5 and off_start(0, first) is None
    # a rest from 10:00 (start hour of some day, the day before not running late) covers 10..12 only
    d = next(i for i in range(1, 60) if starts[i] == 10 and starts[i - 1] < 21)
    day = first + timedelta(days=d)
    assert in_off_period(datetime.combine(day, datetime.min.time()).replace(hour=10), 3, 7) == 13
    assert in_off_period(datetime.combine(day, datetime.min.time()).replace(hour=12, minute=59), 3, 7) == 13
    assert in_off_period(datetime.combine(day, datetime.min.time()).replace(hour=13), 3, 7) is None
    # a rest that starts at 23:00 still holds at 01:00 the next day, and ends at 02:00
    late = next(i for i in range(400) if off_start(3, first + timedelta(days=i), 7) == 23
                and off_start(3, first + timedelta(days=i + 1), 7) > 3)  # next day's rest starts later
    nxt = datetime.combine(first + timedelta(days=late + 1), datetime.min.time())
    assert in_off_period(nxt.replace(hour=1), 3, seed=7) == 2


def test_schedule_stop_uses_the_drawn_limit_and_the_off_period():
    from cob.tasks.schedule import daily_attack_limit, off_start

    noon = datetime(2026, 11, 4, 12)
    limit = daily_attack_limit(10, 30, noon.date(), seed=3)
    reason = schedule_stop(0, 10, 0, 0, lambda: (0.0, limit), noon, 30, 0, 3)
    assert reason == f"daily limit: {limit} attacks today"
    assert schedule_stop(0, 10, 0, 0, lambda: (0.0, limit - 1), noon, 30, 0, 3) is None
    s = off_start(2, noon.date(), seed=3)
    at = noon.replace(hour=s)
    reason = schedule_stop(0, 0, 0, 0, lambda: (0.0, 0), at, 0, 2, 3)
    assert reason == f"random off-period until {(s + 2) % 24:02d}:00"


def _resting_farm(**limits):
    from datetime import timedelta

    s = Script([accepted() for _ in range(5)])
    clock = FakeClock()
    closed = []
    start = datetime(2026, 11, 4, 12, 0)
    task = FarmTask(s.search, s.attack, s.own, FarmLimits(**limits), clock=clock, sleep=clock.sleep,
                    rng=random.Random(0), now=lambda: start + timedelta(seconds=clock.t),
                    close_game=lambda: closed.append(clock.t))
    return task, task.run(), clock, closed


def test_quiet_hours_pause_the_run_and_farming_starts_again():
    # #120 (D-031, opt-in): quiet 12:00-13:00 at noon; rest, close the game once, farm from 13:00.
    task, stats, clock, closed = _resting_farm(max_cycles=2, quiet_from=12, quiet_to=13,
                                               resume_after_rest=True, close_game_resting=True)
    assert stats.stop_reason == "2 cycles done" and stats.attacks == 2
    assert clock.t >= 3600 and closed == [0.0] and task.rests == 1


def test_quiet_hours_still_stop_the_run_by_default():
    _, stats, clock, closed = _resting_farm(max_cycles=2, quiet_from=12, quiet_to=13)
    assert stats.stop_reason == "quiet hours 12:00-13:00" and stats.attacks == 0 and closed == []


def test_a_rest_ends_early_when_stopped():
    import threading

    s = Script([accepted()])
    stop = threading.Event()
    clock = FakeClock()

    def sleep(seconds):
        clock.sleep(seconds)
        stop.set()  # the user presses Stop during the rest

    limits = FarmLimits(quiet_from=12, quiet_to=13, resume_after_rest=True)
    stats = FarmTask(s.search, s.attack, s.own, limits, clock=clock, sleep=sleep, stop=stop,
                     now=lambda: datetime(2026, 11, 4, 12, 30)).run()
    assert stats.stop_reason == "stopped" and stats.attacks == 0
