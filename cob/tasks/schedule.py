"""Daily play limits and quiet hours (D-027): checked by the farm loop before every cycle.

A reached rule stops the run (shown as a safety stop), unless "Farm on after a rest" is on (D-031): then
the farm loop rests and checks again every few minutes.
#121: the day's attack limit can be drawn from a range, and a random off-period of N hours can be added;
both are drawn once per day (same values for every run that day)."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import date, datetime, timedelta


def in_quiet_hours(now: datetime, start: int, end: int) -> bool:
    """Hours 0-23; start == end means no quiet hours. Wraps past midnight (23 -> 7)."""
    if start == end:
        return False
    h = now.hour
    return start <= h < end if start < end else h >= start or h < end


def today_usage(rows: list[dict[str, str]], today: date, profile: str | None = None) -> tuple[float, int]:
    """(farming seconds, attacks done) recorded today in history.csv rows; only `profile`'s rows when
    given (#2: each account has its own daily limits; rows without a profile are the Default one's)."""
    prefix = today.isoformat()
    seconds, attacks = 0.0, 0
    for r in rows:
        if not (r.get("time") or "").startswith(prefix):
            continue
        if profile is not None and (r.get("profile") or "default") != profile:
            continue
        s = (r.get("seconds") or "").strip()
        seconds += float(s) if s.replace(".", "", 1).isdigit() else 0.0
        attacks += r.get("attack") == "done"
    return seconds, attacks


def install_seed(profile: str = "default") -> int:
    """Stable per install (and per profile, #2), so two computers or two accounts do not draw the same daily
    limits and off-periods. The Default profile keeps the seed older versions used."""
    import zlib

    from cob.core.paths import user_data_dir

    key = str(user_data_dir()) if profile == "default" else f"{user_data_dir()}#{profile}"
    return zlib.crc32(key.encode("utf-8"))


def _day_rng(day: date, seed: int, salt: int) -> random.Random:
    return random.Random(day.toordinal() * 1_000_003 + salt * 7919 + seed)


def daily_attack_limit(low: int, high: int, day: date, seed: int = 0) -> int:
    """`low`, or a number in low..high drawn once for `day` when high > low. 0 (no limit) stays 0."""
    if low <= 0 or high <= low:
        return low
    return _day_rng(day, seed, 1).randint(low, high)


def off_start(hours: int, day: date, seed: int = 0) -> int | None:
    """Start hour of `day`'s random off-period of `hours` hours (may run past midnight); None = off."""
    if hours <= 0:
        return None
    return _day_rng(day, seed, 2).randrange(24)


def in_off_period(now: datetime, hours: int, seed: int = 0) -> int | None:
    """End hour of the random off-period `now` falls in (today's, or yesterday's past midnight), else None."""
    h = now.hour
    today = off_start(hours, now.date(), seed)
    if today is not None and today <= h < today + hours:
        return (today + hours) % 24
    yesterday = off_start(hours, now.date() - timedelta(days=1), seed)
    if yesterday is not None and h < yesterday + hours - 24:
        return (yesterday + hours) % 24
    return None


def schedule_stop(daily_minutes: int, daily_attacks: int, quiet_from: int, quiet_to: int,
                  usage: Callable[[], tuple[float, int]], now: datetime, daily_attacks_max: int = 0,
                  off_hours: int = 0, seed: int = 0) -> str | None:
    """Stop reason, or None to keep farming. `usage` is only read when a daily limit is set."""
    if in_quiet_hours(now, quiet_from, quiet_to):
        return f"quiet hours {quiet_from:02d}:00-{quiet_to:02d}:00"
    if (end := in_off_period(now, off_hours, seed)) is not None:
        return f"random off-period until {end:02d}:00"
    attack_limit = daily_attack_limit(daily_attacks, daily_attacks_max, now.date(), seed)
    if daily_minutes or attack_limit:
        seconds, attacks = usage()
        if daily_minutes and seconds >= daily_minutes * 60:
            return f"daily limit: {daily_minutes} min played today"
        if attack_limit and attacks >= attack_limit:
            return f"daily limit: {attack_limit} attacks today"
    return None
