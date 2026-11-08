"""Clash of Clans API sync (D-035): a profile's own troops, spells, heroes, pets and equipment with levels.

Opt-in and started by the user (Sync button): one GET of /players/{tag} on the official API
(developer.clashofclans.com) with the user's own API key. The key is kept only in ui.json, sent only in
the Authorization header to the configured API address, and never logged or shown in an error. Nothing
else is sent. The answer is cached per profile (player.json) so the app works offline afterwards.

API keys are tied to the IP addresses the user listed when creating them; a different address answers
403. The API address can point at a fixed-IP proxy that forwards to the official API instead.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from cob import __version__

log = logging.getLogger(__name__)

DEFAULT_BASE = "https://api.clashofclans.com/v1"
TOKEN = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")  # a JSON Web Token
BASE = re.compile(r"^https://[A-Za-z0-9.-]+(?::\d{1,5})?(?:/[A-Za-z0-9._~/-]*)?$")
MAX_TOKEN = 4096
VILLAGES = {"home": "home", "builderBase": "builder"}
_KIND_ORDER = {"troop": 0, "spell": 0, "hero": 0, "pet": 0, "siege": 0, "super_troop": 1,
               "event_troop": 2, "event_spell": 2}  # a name in both lists is the regular unit


class CocApiError(Exception):
    """A failed sync, with a message for the user (never the key)."""


def valid_token(token: str) -> bool:
    t = token.strip()
    return len(t) <= MAX_TOKEN and bool(TOKEN.match(t))


def valid_base(url: str) -> bool:
    return bool(BASE.match(url.strip()))


# --- the player ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Owned:
    name: str  # as the API names it
    level: int
    max_level: int  # the game's maximum, not this Town Hall's
    village: str  # home / builder
    group: str  # troops / spells / heroes / heroEquipment
    unit_id: str | None = None  # unit database id; None for equipment and names the database lacks

    @property
    def maxed(self) -> bool:
        return self.level >= self.max_level > 0


@dataclass(frozen=True)
class Player:
    tag: str
    name: str
    town_hall: int
    town_hall_weapon: int = 0
    builder_hall: int = 0
    exp_level: int = 0
    trophies: int = 0
    clan: str = ""
    units: tuple[Owned, ...] = field(default=())
    fetched_at: float = 0.0  # time.time() of the sync

    def owned(self, village: str = "home") -> dict[str, Owned]:
        """unit id -> what the player has (troops, spells, heroes, pets, sieges) in that village."""
        return {u.unit_id: u for u in self.units if u.unit_id and u.village == village}

    def equipment(self) -> list[Owned]:
        return [u for u in self.units if u.group == "heroEquipment"]

    def heroes(self, village: str = "home") -> list[Owned]:
        return [u for u in self.units if u.group == "heroes" and u.village == village]

    def unmatched(self) -> list[str]:
        return [u.name for u in self.units if u.unit_id is None and u.group != "heroEquipment"]


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def name_index(db) -> dict[tuple[str, str], str]:
    """(normalised name, village) -> unit id; regular units win over event ones of the same name."""
    best: dict[tuple[str, str], tuple[int, str]] = {}
    for u in db.units.values():
        k = (_key(u.name), u.village)
        rank = _KIND_ORDER.get(u.kind, 3)
        if k not in best or rank < best[k][0]:
            best[k] = (rank, u.id)
    return {k: v[1] for k, v in best.items()}


def parse_player(data: dict, db=None, fetched_at: float = 0.0) -> Player:
    """The API's player object -> Player, units matched to the unit database by name and village."""
    if not isinstance(data, dict) or not isinstance(data.get("tag"), str):
        raise CocApiError("the API answer is not a player")
    index = name_index(db) if db is not None else {}
    units: list[Owned] = []
    for group in ("troops", "spells", "heroes", "heroEquipment"):
        for item in data.get(group) or []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            village = VILLAGES.get(item.get("village", "home"), "home")
            name = item["name"]
            unit_id = None if group == "heroEquipment" else index.get((_key(name), village))
            units.append(Owned(name, _int(item.get("level")), _int(item.get("maxLevel")), village, group,
                               unit_id))
    clan = data.get("clan") if isinstance(data.get("clan"), dict) else {}
    return Player(data["tag"], str(data.get("name", "")), _int(data.get("townHallLevel")),
                  _int(data.get("townHallWeaponLevel")), _int(data.get("builderHallLevel")),
                  _int(data.get("expLevel")), _int(data.get("trophies")), str(clan.get("name", "")),
                  tuple(units), fetched_at)


def _int(v) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) else 0


# --- network ------------------------------------------------------------------------------------


_STATUS = {
    400: "the request was refused (check the player tag)",
    403: "the API key was refused: check it, and that it lists this computer's public IP address",
    404: "no player with this tag",
    429: "too many requests: try again in a minute",
    503: "the Clash of Clans API is down for maintenance",
}


def fetch_player(tag: str, token: str, base: str = "", timeout: float = 10.0,
                 opener=urllib.request.urlopen) -> dict:
    """GET {base}/players/{tag} with the user's key. Raises CocApiError with a message for the user."""
    from cob.core.profiles import normalize_tag

    tag = normalize_tag(tag)
    if not tag:
        raise CocApiError("set a valid player tag first (Profiles page)")
    if not valid_token(token):
        raise CocApiError("set your Clash of Clans API key first (Settings > Clash of Clans API)")
    base = (base.strip() or DEFAULT_BASE).rstrip("/")
    if not valid_base(base):
        raise CocApiError("the API address must be an https:// address")
    url = f"{base}/players/{urllib.parse.quote(tag, safe='')}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token.strip()}",
                                               "Accept": "application/json",
                                               "User-Agent": f"ClashOfBots/{__version__}"})
    try:
        with opener(req, timeout=timeout) as resp:  # noqa: S310 (https only, checked above)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise CocApiError(f"Clash of Clans API: {_STATUS.get(exc.code, f'HTTP {exc.code}')}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise CocApiError(f"Clash of Clans API not reachable ({type(reason).__name__})") from None
    except ValueError:
        raise CocApiError("the Clash of Clans API answer was not JSON") from None


def sync(tag: str, token: str, cache: Path, base: str = "", db=None, opener=urllib.request.urlopen,
         clock=time.time) -> Player:
    """Fetch the player, cache the answer at `cache`, return it parsed."""
    data = fetch_player(tag, token, base, opener=opener)
    now = clock()
    player = parse_player(data, db, now)
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    tmp.write_text(json.dumps({"fetched_at": now, "player": data}, indent=1) + "\n", "utf-8")
    tmp.replace(cache)
    if player.unmatched():
        log.info("API units not in the unit database: %s", ", ".join(player.unmatched()))
    log.info("synced %s: TH%d, %d units", player.tag, player.town_hall, len(player.units))
    return player


def load_cached(cache: Path, db=None) -> Player | None:
    """The last synced player, or None (never synced, or the file is broken)."""
    try:
        raw = json.loads(cache.read_text("utf-8"))
        return parse_player(raw["player"], db, float(raw.get("fetched_at", 0.0)))
    except (OSError, ValueError, KeyError, TypeError, CocApiError):
        return None
