"""Update check (#104): the newest GitHub release for this app's channel, with the changelogs since ours.

The only network call the app makes, and only when asked: the Check for updates button, or the
"check at start-up" switch (off by default, CONSTRAINTS / D-030). It reads the public releases API of
this repository; nothing about the user or the device is sent. Nothing is downloaded or installed: the
user opens the release page.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

from cob import __version__

REPO = "Clash-Tools/Clash-of-Bots"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
_RANK = {"alpha": 0, "beta": 1, "rc": 2, "stable": 3}
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")


def parse(text: str) -> tuple[int, int, int, int, int] | None:
    """Sortable key for "0.5.0-beta.2" / "v0.4.0"; None for anything else."""
    m = _VERSION.match(text.strip())
    if not m:
        return None
    major, minor, patch, channel, n = m.groups()
    return int(major), int(minor), int(patch), _RANK[channel or "stable"], int(n or 0)


def channel_of(version: str) -> str:
    m = _VERSION.match(version.strip())
    return (m.group(4) if m else None) or "stable"


@dataclass(frozen=True)
class Release:
    tag: str
    name: str
    notes: str  # markdown changelog section
    url: str  # release page
    prerelease: bool

    @property
    def key(self):
        return parse(self.tag)


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: Release | None  # newest release allowed for our channel
    newer: list[Release]  # every allowed release newer than ours, newest first

    @property
    def available(self) -> bool:
        return bool(self.newer)

    def changelog(self) -> str:
        """Markdown: each newer release's notes under its name."""
        return "\n\n".join(f"## {r.name or r.tag}\n\n{r.notes.strip()}" for r in self.newer)


def fetch(timeout: float = 10.0, url: str = API) -> list[Release]:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"ClashOfBots/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        data = json.loads(resp.read().decode("utf-8"))
    return [Release(r.get("tag_name", ""), r.get("name") or "", r.get("body") or "", r.get("html_url", ""),
                    bool(r.get("prerelease"))) for r in data if not r.get("draft")]


def check(releases: list[Release], current: str = __version__) -> UpdateInfo:
    """Stable builds only see stable releases; alpha / beta / rc builds also see pre-releases."""
    mine = parse(current)
    pre_ok = channel_of(current) != "stable"
    allowed = sorted((r for r in releases if r.key is not None and (pre_ok or not r.prerelease)),
                     key=lambda r: r.key, reverse=True)
    newer = [r for r in allowed if mine is None or r.key > mine]
    return UpdateInfo(current, allowed[0] if allowed else None, newer)
