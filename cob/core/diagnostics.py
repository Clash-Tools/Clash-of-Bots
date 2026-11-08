"""Sanitized diagnostics zip (#66): logs + settings + version, with private details scrubbed.

Scrubbed: IPv4 addresses, phone hardware serials / adb mDNS names, the user's home folder and user name.
Snapshots are left out on purpose: game screenshots show the player name and clan."""

from __future__ import annotations

import getpass
import json
import platform
import re
import sys
import zipfile
from pathlib import Path

from cob import __version__
from cob.core.paths import user_data_dir

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MDNS = re.compile(r"\badb-([A-Za-z0-9]{6,})-[A-Za-z0-9]{6}\b")
_SERIAL_KEYS = re.compile(r"(?i)\b(serial(?:no)?|phone)\s*[:=]?\s*([A-Z0-9]{8,16})\b")


def known_serials() -> set[str]:
    """Hardware serials the bot has seen (phone records are named after them)."""
    folder = user_data_dir() / "phones"
    return {p.stem for p in folder.glob("*.json") if p.stem != "wireless"} if folder.is_dir() else set()


def sanitize(text: str, serials: set[str] | None = None, home: str | None = None,
             user: str | None = None) -> str:
    serials = known_serials() if serials is None else serials
    home = str(Path.home()) if home is None else home
    if user is None:
        try:
            user = getpass.getuser()
        except Exception:  # no login name (some service accounts)
            user = ""
    out = _MDNS.sub("adb-<serial>-<id>", text)
    for s in sorted(serials, key=len, reverse=True):
        if len(s) >= 6:
            out = out.replace(s, "<serial>")
    out = _SERIAL_KEYS.sub(lambda m: f"{m.group(1)} <serial>", out)
    out = _IPV4.sub(lambda m: m.group(0) if m.group(0).startswith("127.") else "<ip>", out)
    if home:
        out = out.replace(home, "<home>")
    if user and len(user) >= 3:
        out = re.sub(rf"\b{re.escape(user)}\b", "<user>", out)
    return out


def build_zip(dest: Path, logs: list[Path], extra: dict[str, str] | None = None) -> Path:
    """Write the zip: sanitized log files, farm.json, a small system summary."""
    serials = known_serials()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        summary = {"version": __version__, "python": sys.version.split()[0],
                   "platform": platform.platform(terse=True)} | (extra or {})
        z.writestr("summary.json", sanitize(json.dumps(summary, indent=2), serials))
        for path in logs:
            if path.is_file():
                z.writestr(f"logs/{path.name}", sanitize(path.read_text("utf-8", errors="replace"), serials))
        cfg = user_data_dir() / "farm.json"
        if cfg.is_file():
            z.writestr("farm.json", cfg.read_text("utf-8"))
    return dest
