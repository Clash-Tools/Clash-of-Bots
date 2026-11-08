"""Profiles (#2): several accounts / devices, each with its own farm settings and history.

A profile is a name, the device it farms on, an optional player tag (for the Clash of Clans API sync)
and whether it takes part in "Run profiles in turn". profiles.json in the user data folder lists them;
each profile's farm settings live in profiles/<id>/farm.json. The "default" profile keeps the farm.json
older versions wrote, so an existing install becomes the Default profile without moving any file.
Everything is validated on load: a hand-edited or broken file never crashes the app.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from cob.core.config import FarmConfig, load_farm_config, save_farm_config
from cob.core.paths import user_data_dir

log = logging.getLogger(__name__)

DEFAULT_ID = "default"
MAX_PROFILES = 20
MAX_NAME = 40
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
TAG = re.compile(r"^#[0289PYLQGRJCUV]{3,14}$")  # the characters Supercell uses in player tags


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    serial: str = ""  # adb serial of the device it farms on; "" = the device picked in the top bar
    player_tag: str = ""  # "#ABC123" for the Clash of Clans API sync; "" = none
    rotation: bool = False  # part of "Run profiles in turn"


def normalize_tag(tag: str) -> str:
    """'abc 123' -> '#ABC123' ('O' typed for zero becomes '0'); '' when it cannot be a player tag."""
    t = re.sub(r"\s+", "", tag or "").upper().replace("O", "0")
    if not t:
        return ""
    t = "#" + t.lstrip("#")
    return t if TAG.match(t) else ""


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32].strip("-")
    return s or "profile"


class Profiles:
    """profiles.json plus each profile's farm.json. Changes are saved at once."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else user_data_dir()
        self.path = self.root / "profiles.json"
        self.profiles: list[Profile] = []
        self.active_id = DEFAULT_ID
        self.load()

    # --- file -----------------------------------------------------------------------------------

    def load(self) -> None:
        raw: object = {}
        if self.path.is_file():
            try:
                raw = json.loads(self.path.read_text("utf-8"))
            except (OSError, ValueError) as exc:
                log.warning("profiles %s unreadable (%s); keeping only the Default profile", self.path, exc)
        if not isinstance(raw, dict):
            raw = {}
        seen: set[str] = set()
        out: list[Profile] = []
        entries = raw.get("profiles") if isinstance(raw.get("profiles"), list) else []
        for entry in entries:
            p = _profile(entry)
            if p is None or p.id in seen:
                log.warning("profile entry %r skipped (invalid or duplicate)", entry)
                continue
            seen.add(p.id)
            out.append(p)
        if DEFAULT_ID not in seen:
            out.insert(0, Profile(DEFAULT_ID, "Default"))
        self.profiles = out[:MAX_PROFILES]
        active = raw.get("active")
        self.active_id = active if isinstance(active, str) and self.get(active) else DEFAULT_ID

    def save(self) -> Path:
        data = {"active": self.active_id, "profiles": [asdict(p) for p in self.profiles]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
        tmp.replace(self.path)
        return self.path

    # --- lookups --------------------------------------------------------------------------------

    def get(self, profile_id: str) -> Profile | None:
        return next((p for p in self.profiles if p.id == profile_id), None)

    @property
    def active(self) -> Profile:
        return self.get(self.active_id) or self.profiles[0]

    def rotation(self) -> list[Profile]:
        """Profiles that run in turn, in list order."""
        return [p for p in self.profiles if p.rotation]

    def farm_path(self, profile_id: str) -> Path:
        if profile_id == DEFAULT_ID:
            return self.root / "farm.json"
        return self.root / "profiles" / profile_id / "farm.json"

    def player_path(self, profile_id: str) -> Path:
        """Where the profile's last Clash of Clans API sync is cached (D-035)."""
        return self.root / "profiles" / profile_id / "player.json"

    def load_config(self, profile_id: str) -> FarmConfig:
        return load_farm_config(self.farm_path(profile_id))

    def save_config(self, profile_id: str, cfg: FarmConfig) -> Path:
        path = self.farm_path(profile_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        return save_farm_config(cfg, path)

    # --- changes --------------------------------------------------------------------------------

    def set_active(self, profile_id: str) -> Profile:
        if self.get(profile_id) is None:
            raise KeyError(profile_id)
        self.active_id = profile_id
        self.save()
        return self.active

    def add(self, name: str, copy_from: str | None = None) -> Profile:
        """New profile; its farm settings are a copy of `copy_from`'s (else the defaults)."""
        if len(self.profiles) >= MAX_PROFILES:
            raise ValueError(f"at most {MAX_PROFILES} profiles")
        name = _clean_name(name) or "Profile"
        base = slug(name)
        pid, n = base, 2
        while self.get(pid) is not None or pid == DEFAULT_ID:
            pid = f"{base[:28]}-{n}"
            n += 1
        cfg = self.load_config(copy_from) if copy_from and self.get(copy_from) else FarmConfig()
        profile = Profile(pid, name)
        if copy_from and (src := self.get(copy_from)):
            profile = replace(profile, rotation=src.rotation)
        self.profiles.append(profile)
        self.save_config(pid, cfg)
        self.save()
        return profile

    def update(self, profile: Profile) -> Profile:
        """Save a changed profile (same id); name and tag are cleaned, a bad tag is dropped."""
        i = next((i for i, p in enumerate(self.profiles) if p.id == profile.id), None)
        if i is None:
            raise KeyError(profile.id)
        profile = replace(profile, name=_clean_name(profile.name) or self.profiles[i].name,
                          serial=profile.serial.strip(), player_tag=normalize_tag(profile.player_tag))
        self.profiles[i] = profile
        self.save()
        return profile

    def remove(self, profile_id: str) -> None:
        """Delete a profile and its settings folder; the Default profile stays."""
        if profile_id == DEFAULT_ID:
            raise ValueError("the Default profile cannot be removed")
        if self.get(profile_id) is None:
            raise KeyError(profile_id)
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        folder = self.root / "profiles" / profile_id
        if folder.is_dir():
            shutil.rmtree(folder)
        if self.active_id == profile_id:
            self.active_id = DEFAULT_ID
        self.save()


def _clean_name(name: object) -> str:
    return " ".join(str(name).split())[:MAX_NAME] if isinstance(name, str) else ""


def _profile(entry: object) -> Profile | None:
    if not isinstance(entry, dict):
        return None
    pid, name = entry.get("id"), _clean_name(entry.get("name"))
    if not isinstance(pid, str) or not ID.match(pid) or not name:
        return None
    serial = entry.get("serial")
    tag = entry.get("player_tag")
    rotation = entry.get("rotation")
    return Profile(pid, name, serial.strip() if isinstance(serial, str) else "",
                   normalize_tag(tag) if isinstance(tag, str) else "",
                   rotation if isinstance(rotation, bool) else False)
