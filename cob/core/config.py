"""User-editable farm settings: JSON in the user data folder, validated and clamped on load."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from cob.core.paths import user_data_dir

log = logging.getLogger(__name__)

# (min, max) per field; values outside are clamped, wrong types fall back to the default.
_LIMITS = {
    "min_gold_elixir": (0, 10_000_000),
    "min_dark": (0, 500_000),
    "max_nexts": (0, 500),
    "reduce_every": (0, 500),
    "reduce_percent": (1, 50),
    "reduce_floor": (0, 100),
    "min_own_gold": (0, 100_000_000),
    "halt_full_percent": (0, 100),
    "loot_stall_s": (0, 120),
    "end_at_damage": (0, 100),
    "break_every": (0, 200),
    "break_minutes": (1, 120),
    "collect_minutes": (0, 1440),
    "wall_upgrades": (0, 10),
    "wall_reserve": (0, 100_000_000),
    "request_minutes": (0, 1440),
    "max_failures": (1, 20),
    "other_device_wait": (0, 240),
    "unavailable_wait": (0, 60),
    "two_sides": (0, 1),
    "cast_spells": (0, 1),
    "resume_after_rest": (0, 1),
    "close_game_resting": (0, 1),
    "daily_minutes": (0, 1440),
    "daily_attacks": (0, 1000),
    "quiet_from": (0, 23),
    "quiet_to": (0, 23),
    "daily_attacks_max": (0, 1000),
    "off_hours": (0, 12),
    "army_recipe": (0, 4),  # #185: 0 = keep the army; 1-4 = Saved Recipes row
}


@dataclass(frozen=True)
class FarmConfig:
    min_gold_elixir: int = 800_000  # attack if gold + elixir >= this ...
    min_dark: int = 8_000  # ... or dark elixir >= this (0 disables the dark rule)
    max_nexts: int = 40  # after this many Nexts, take the current base
    reduce_every: int = 0  # #113: lower both minimums every this many Nexts; 0 = never
    reduce_percent: int = 5  # ... by this % of the set value per step
    reduce_floor: int = 50  # ... but never below this % of the set value
    min_own_gold: int = 50_000  # stop searching below this (each Next costs gold)
    halt_full_percent: int = 0  # #119: no attacks while gold and elixir storages are this full; 0 = off
    loot_stall_s: int = 0  # #114: end the battle when Available Loot stops changing this long; 0 = off
    end_at_damage: int = 0  # #114: end the battle once damage reaches this %; 0 = off
    break_every: int = 8  # rest after about this many cycles (randomised +-2); 0 = no breaks
    break_minutes: int = 5  # rest length (randomised 0.6x..1.4x)
    collect_minutes: int = 10  # collect resource bubbles at most this often; 0 = never
    wall_upgrades: int = 0  # walls to upgrade per cycle (gold/elixir only); 0 = never spend on walls
    wall_reserve: int = 1_000_000  # never let gold / elixir drop below this by upgrading walls
    request_minutes: int = 0  # ask the clan for castle troops at most this often; 0 = never (posts to chat)
    max_failures: int = 3  # stop after this many failed cycles in a row
    other_device_wait: int = 0  # #117: village opened elsewhere -> wait this many minutes, reload; 0 = stop
    unavailable_wait: int = 10  # #118: game stuck loading (maintenance) -> close, wait, retry; 0 = failure
    resume_after_rest: int = 0  # #120 (D-031): 1 = wait out quiet hours / limits and farm on; 0 = stop
    close_game_resting: int = 0  # #120: 1 = close the game while resting
    daily_minutes: int = 0  # stop once this much farming time is recorded today (history.csv); 0 = no limit
    daily_attacks: int = 0  # stop once this many attacks are recorded today; 0 = no limit
    quiet_from: int = 0  # quiet hours start (hour 0-23); quiet_from == quiet_to = no quiet hours
    quiet_to: int = 0  # quiet hours end (hour, exclusive); wraps past midnight
    daily_attacks_max: int = 0  # #121: above daily_attacks, each day's limit is drawn from that range
    off_hours: int = 0  # #121: one random off-period of this many hours a day; 0 = none
    cast_spells: int = 1  # 1 = cast spell cards a little inside the attacked edge after the troops
    two_sides: int = 0  # #44: 1 = deploy troops along 2 adjacent edges around a corner; 0 = one edge
    army_recipe: int = 0  # #185: Saved Recipe (1-4) loaded as the army when a run starts; 0 = keep the army


def default_path() -> Path:
    return user_data_dir() / "farm.json"


def load_farm_config(path: Path | None = None) -> FarmConfig:
    path = path or default_path()
    if not path.is_file():
        return FarmConfig()
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("farm config %s unreadable (%s); using defaults", path, exc)
        return FarmConfig()
    if not isinstance(raw, dict):
        log.warning("farm config %s is not an object; using defaults", path)
        return FarmConfig()
    values = {}
    for f in fields(FarmConfig):
        if f.name not in raw:
            continue
        v = raw[f.name]
        if isinstance(v, bool) or not isinstance(v, int):
            log.warning("farm config %s=%r is not an integer; using default", f.name, v)
            continue
        lo, hi = _LIMITS[f.name]
        if not lo <= v <= hi:
            log.warning("farm config %s=%d clamped to [%d, %d]", f.name, v, lo, hi)
            v = min(max(v, lo), hi)
        values[f.name] = v
    return FarmConfig(**values)


def save_farm_config(cfg: FarmConfig, path: Path | None = None) -> Path:
    path = path or default_path()
    path.write_text(json.dumps(asdict(cfg), indent=2) + "\n", "utf-8")
    return path
