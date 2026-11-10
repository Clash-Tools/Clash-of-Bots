"""Feature flags (D-038): features that are not finished, or not yet proven live, stay out of sight.

Each flag has a stage:

    beta          finished and in use, still being polished: ON unless turned off
    experimental  built, but not checked live yet: OFF unless turned on
    incomplete    only partly built (or only a placeholder): OFF unless turned on

The switches are on the hidden Developer options page (Settings > About: click the version seven times)
and are kept in flags.json in the user data folder. They are read once at start-up, so a change applies
after a restart, like the theme. COB_FLAGS=name,-other (environment) overrides the file, for tests and
development. Every flag points at the issue that finishes it (the project board tracks them).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from cob.core.paths import user_data_dir

log = logging.getLogger(__name__)

BETA, EXPERIMENTAL, INCOMPLETE = "beta", "experimental", "incomplete"
STAGES = (BETA, EXPERIMENTAL, INCOMPLETE)


@dataclass(frozen=True)
class Flag:
    key: str
    title: str
    description: str
    stage: str
    issue: int | None = None  # Clash-Tools/Clash-of-Bots issue that finishes it

    @property
    def default(self) -> bool:
        return self.stage == BETA


# English only on purpose: the Developer options page is for testers and contributors.
FLAGS: tuple[Flag, ...] = (
    Flag("builder_base", "Builder Base attacks",
         "Dashboard mode and Automation tab. Attacks and collecting work; loot priority, Clock Tower boosts "
         "and Builder Base upgrades are not built.", BETA, 29),
    Flag("card_labelling", "Cards page",
         "Label troop-bar cards the bot does not recognise and export them for the unit database. Every "
         "home unit is recognised from game portraits; siege machines still need labels.", BETA, 19),
    Flag("profile_rotation", "Run profiles in turn",
         "Profiles page: farm the ticked profiles one after another. Not run live with two devices yet.",
         EXPERIMENTAL, 2),
    Flag("coc_api_sync", "Clash of Clans API sync",
         "API key in Settings, player tag and Sync on the Profiles page, own units first on the Cards page. "
         "Not checked against the live API yet.", EXPERIMENTAL, 45),
    Flag("live_stream", "Live screen stream (phones)",
         "Automation > Farming Heuristics switch: waits watch an H.264 stream of the phone screen, actions "
         "still use screenshots. Speed-up not measured live yet.", EXPERIMENTAL, 37),
    Flag("clan_games", "Clan Games",
         "Automation tab for Clan Games. Placeholder only: nothing is automated yet.", INCOMPLETE, 1),
    Flag("building_upgrades", "Building and lab upgrades",
         "Note on the Upgrades tab. Only walls are upgraded today.", INCOMPLETE, 3),
)
BY_KEY = {f.key: f for f in FLAGS}


def path() -> Path:
    return user_data_dir() / "flags.json"


class Flags:
    def __init__(self, values: dict[str, bool] | None = None, developer: bool = False):
        self.values = {k: v for k, v in (values or {}).items() if k in BY_KEY and isinstance(v, bool)}
        self.developer = developer  # the Developer options page is unlocked

    def enabled(self, key: str) -> bool:
        if key not in BY_KEY:
            raise KeyError(f"unknown feature flag {key!r}")
        return self.values.get(key, BY_KEY[key].default)

    def set(self, key: str, on: bool) -> None:
        if key not in BY_KEY:
            raise KeyError(f"unknown feature flag {key!r}")
        if on == BY_KEY[key].default:
            self.values.pop(key, None)  # only changes from the default are kept
        else:
            self.values[key] = on

    def changed(self) -> list[str]:
        """Flags not at their default (for logs and diagnostics)."""
        return sorted(f"{k}={'on' if v else 'off'}" for k, v in self.values.items())


def load(file: Path | None = None, env: str | None = None) -> Flags:
    """flags.json (missing or broken = all defaults), then COB_FLAGS from the environment on top."""
    file = file or path()
    raw: object = {}
    try:
        raw = json.loads(file.read_text("utf-8"))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        log.warning("feature flags %s unreadable (%s); using the defaults", file, exc)
    if not isinstance(raw, dict):
        raw = {}
    values = raw.get("flags") if isinstance(raw.get("flags"), dict) else {}
    flags = Flags(values, raw.get("developer") is True)
    for item in (os.environ.get("COB_FLAGS", "") if env is None else env).split(","):
        item = item.strip()
        key, on = (item[1:], False) if item.startswith("-") else (item, True)
        if key in BY_KEY:
            flags.set(key, on)
        elif key:
            log.warning("COB_FLAGS: unknown feature flag %r ignored", key)
    return flags


def save(flags: Flags, file: Path | None = None) -> Path:
    file = file or path()
    file.write_text(json.dumps({"developer": flags.developer, "flags": flags.values}, indent=2) + "\n",
                    "utf-8")
    return file


_current: Flags | None = None


def current() -> Flags:
    """The flags this run started with (loaded on first use)."""
    global _current
    if _current is None:
        _current = load()
        if _current.changed():
            log.info("feature flags: %s", ", ".join(_current.changed()))
    return _current


def enabled(key: str) -> bool:
    return current().enabled(key)


def reset() -> None:
    """Forget the loaded flags (tests; the next current() reads the file again)."""
    global _current
    _current = None
