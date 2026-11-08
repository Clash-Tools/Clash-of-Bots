"""Desktop app preferences (Settings page, #67): ui.json in the user data folder, validated on load."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from cob.core import notify
from cob.core.paths import user_data_dir

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UiSettings:
    start_minimized: bool = False  # start in the system tray (only when a tray exists)
    notify_safety_stop: bool = True  # tray notification when a safety rule or an error stops farming
    notify_finished: bool = True  # ... when farming ends normally (limit reached, user stop)
    notify_breaks: bool = False  # ... when a break starts
    check_updates: bool = False  # look for a new release at start-up (#104; opt-in, CONSTRAINTS)
    wizard_done: bool = False  # first-run setup wizard finished (#51)
    risk_accepted: bool = False  # the terms-of-service / ban risk notice was acknowledged
    theme: str = "dark"  # dark / light / amoled (#102), applied at start-up
    accent: str = "teal"  # accent colour name (cob.ui.style.tokens.ACCENTS)
    language: str = "en"  # UI language code (assets/i18n/<code>.json, #103), applied at start-up
    discord_webhook: str = ""  # #43: alerts also go to this Discord webhook; empty = off
    telegram_token: str = ""  # #43: ... and to this Telegram bot (token from @BotFather) ...
    telegram_chat: str = ""  # ... in this chat (id or @channel); both needed


CHOICES = {"theme": ("dark", "light", "amoled"),
           "accent": ("teal", "blue", "purple", "orange", "pink", "green")}


# Free-text fields and their checks: a bad value loads as empty.
TEXT = {"discord_webhook": notify.valid_discord, "telegram_token": notify.valid_telegram_token,
        "telegram_chat": notify.valid_telegram_chat}


def default_path() -> Path:
    return user_data_dir() / "ui.json"


def load(path: Path | None = None) -> UiSettings:
    path = path or default_path()
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return UiSettings()
    if not isinstance(raw, dict):
        return UiSettings()
    # Unknown keys are ignored, wrong types or values fall back to the default: a hand-edited file never
    # crashes the app.
    values = {}
    for f in fields(UiSettings):
        v = raw.get(f.name)
        if f.name in CHOICES:
            if v in CHOICES[f.name]:
                values[f.name] = v
        elif f.name == "language":
            from cob.core.i18n import CODE

            if isinstance(v, str) and CODE.match(v):
                values[f.name] = v
        elif f.name in TEXT:
            if isinstance(v, str) and (v == "" or TEXT[f.name](v)):
                values[f.name] = v.strip()
        elif isinstance(v, bool):
            values[f.name] = v
    return UiSettings(**values)


def save(settings: UiSettings, path: Path | None = None) -> Path:
    path = path or default_path()
    path.write_text(json.dumps(asdict(settings), indent=2), "utf-8")
    return path


def folder_sizes(root: Path | None = None) -> dict[str, int]:
    """Bytes used per data category (Settings storage bar)."""
    root = root or user_data_dir()

    def size(p: Path) -> int:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0

    return {"Logs": size(root / "logs"), "Snapshots": size(root / "snapshots"),
            "History": size(root / "history.csv"), "Phones & settings": sum(
                size(root / n) for n in ("phones", "farm.json", "ui.json"))}
