"""The unit database (troops, spells, heroes, pets) bundled from Clash-Tools/clash-of-bots-data.

assets/units holds a pinned tag of that repository (scripts/update_units.py): index.json, one JSON file per
unit and the troop-bar card pictures the bot recognises units by. The bot only reads it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from cob.core.paths import app_root

log = logging.getLogger(__name__)

SPELL_KINDS = frozenset({"spell", "event_spell"})
SINGLE_KINDS = frozenset({"hero", "siege", "pet"})


@dataclass(frozen=True)
class Unit:
    id: str
    name: str
    kind: str
    village: str
    housing_space: int | None = None
    dark: bool = False
    flying: bool = False
    targets_ground: bool = True
    targets_air: bool = False
    super_of: str | None = None
    cards: tuple[str, ...] = field(default=())  # card picture paths relative to the database root

    @property
    def is_spell(self) -> bool:
        return self.kind in SPELL_KINDS


class UnitDB:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_root()
        self.version = _read(self.root / "VERSION").strip() or "unknown"
        self.units: dict[str, Unit] = {}
        index = json.loads(_read(self.root / "index.json") or '{"units": []}')
        for entry in index.get("units", []):
            try:
                self.units[entry["id"]] = _unit(json.loads((self.root / entry["path"]).read_text("utf-8")))
            except (OSError, ValueError, KeyError) as exc:
                log.warning("unit %s unreadable: %s", entry.get("id"), exc)

    def get(self, unit_id: str) -> Unit | None:
        return self.units.get(unit_id)

    def choices(self, village: str = "home") -> list[Unit]:
        """Units for a picker, by kind then name."""
        order = ["troop", "super_troop", "event_troop", "siege", "hero", "pet", "spell", "event_spell"]
        return sorted((u for u in self.units.values() if u.village == village),
                      key=lambda u: (order.index(u.kind) if u.kind in order else 99, u.name))

    def __len__(self) -> int:
        return len(self.units)


def _read(path: Path) -> str:
    try:
        return path.read_text("utf-8")
    except OSError:
        return ""


def _unit(d: dict) -> Unit:
    t = d.get("targets") or {}
    return Unit(d["id"], d["name"], d["kind"], d["village"], d.get("housing_space"), bool(d.get("dark")),
                bool(d.get("flying")), bool(t.get("ground", True)), bool(t.get("air", False)),
                d.get("super_of"), tuple(c["file"] for c in (d.get("detection") or {}).get("cards", [])))


def default_root() -> Path:
    return app_root() / "assets" / "units"


@lru_cache(maxsize=1)
def load() -> UnitDB:
    db = UnitDB()
    log.debug("unit database %s: %d units", db.version, len(db))
    return db
