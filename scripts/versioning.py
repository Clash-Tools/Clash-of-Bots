"""Version + changelog logic for releases. Stdlib only; imported by release.py, CI and tests.

Scheme (D-011): SemVer 2.0 with channels  MAJOR.MINOR.PATCH[-alpha.N|-beta.N|-rc.N]
  0.2.0-alpha.1 -> 0.2.0-alpha.2 -> 0.2.0-beta.1 -> 0.2.0-rc.1 -> 0.2.0 (stable)
`X.Y.Z-alpha.0` = in development, never released.
Windows exe needs a numeric 4-part file version: MAJOR.MINOR.PATCH.B where
  B = 1000+N alpha, 2000+N beta, 3000+N rc, 9000 stable  (so later builds always sort higher).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, replace
from datetime import date

CHANNELS = ("alpha", "beta", "rc", "stable")
_CHANNEL_BASE = {"alpha": 1000, "beta": 2000, "rc": 3000}
_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    channel: str = "stable"
    n: int = 0

    @classmethod
    def parse(cls, text: str) -> Version:
        m = _RE.match(text.strip().removeprefix("v"))
        if not m:
            raise ValueError(f"not a release version: {text!r}")
        ma, mi, pa, ch, n = m.groups()
        return cls(int(ma), int(mi), int(pa), ch or "stable", int(n or 0))

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return base if self.channel == "stable" else f"{base}-{self.channel}.{self.n}"

    @property
    def tag(self) -> str:
        return f"v{self}"

    @property
    def prerelease(self) -> bool:
        return self.channel != "stable"

    @property
    def file_version(self) -> str:
        b = 9000 if self.channel == "stable" else _CHANNEL_BASE[self.channel] + self.n
        return f"{self.major}.{self.minor}.{self.patch}.{b}"

    @property
    def label(self) -> str:
        return {"alpha": "Alpha", "beta": "Beta", "rc": "Release Candidate", "stable": "Stable"}[self.channel]

    def bump_base(self, part: str) -> Version:
        if part == "major":
            return Version(self.major + 1, 0, 0)
        if part == "minor":
            return Version(self.major, self.minor + 1, 0)
        if part == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"unknown part {part!r}")


def next_version(cur: Version, channel: str, bump: str | None = None) -> Version:
    """Next release on `channel`.

    Same base while the current version is a pre-release of that base and channel order holds
    (alpha < beta < rc < stable). Starting a new cycle after a stable release needs `bump`.
    """
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    if bump:
        base = cur.bump_base(bump)
    elif cur.channel == "stable":
        raise ValueError(f"{cur} is stable: pass --bump major|minor|patch to start a new cycle")
    else:
        base = replace(cur, channel="stable", n=0)
        if CHANNELS.index(channel) < CHANNELS.index(cur.channel):
            raise ValueError(f"cannot go back from {cur.channel} to {channel}")
    if channel == "stable":
        return replace(base, channel="stable", n=0)
    if not bump and cur.channel == channel:
        return replace(cur, n=cur.n + 1)
    return replace(base, channel=channel, n=1)


# --- conventional commits -> changelog -------------------------------------------------------

_CC = re.compile(r"^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?:\s*(?P<subject>.+)$")
SECTIONS = [
    ("feat", "Features"),
    ("fix", "Bug Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("build", "Build"),
    ("ci", "CI"),
    ("chore", "Chores"),
]


@dataclass(frozen=True)
class Commit:
    sha: str
    type: str
    scope: str | None
    subject: str
    body: str
    breaking: bool


def parse_commit(sha: str, message: str) -> Commit | None:
    subject_line, _, body = message.partition("\n")
    m = _CC.match(subject_line.strip())
    if not m:
        return None
    breaking = bool(m["bang"]) or "BREAKING CHANGE" in body
    return Commit(sha[:7], m["type"].lower(), m["scope"], m["subject"].strip(), body.strip(), breaking)


def render_section(version: Version, commits: list[Commit], notes: str = "", today: date | None = None,
                   repo_url: str | None = None) -> str:
    day = (today or date.today()).isoformat()
    lines = [f"## [{version}] - {day}", "", f"Channel: **{version.label}**", ""]
    if notes.strip():
        lines += ["### Highlights", "", notes.strip(), ""]
    breaking = [c for c in commits if c.breaking]
    if breaking:
        lines += ["### BREAKING CHANGES", ""] + [f"- {_line(c, repo_url)}" for c in breaking] + [""]
    known = {t for t, _ in SECTIONS}
    for ctype, title in SECTIONS:
        # Unknown types (style, revert, ...) fall into Chores rather than vanishing.
        if ctype == "chore":
            group = [c for c in commits if c.type == "chore" or c.type not in known]
        else:
            group = [c for c in commits if c.type == ctype]
        if not group:
            continue
        lines += [f"### {title}", ""]
        for c in group:
            lines.append(f"- {_line(c, repo_url)}")
            # Bullet points in the commit body become sub-items: that is where the detail lives.
            for b in body_bullets(c.body):
                lines.append(f"  - {b}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def body_bullets(body: str) -> list[str]:
    """"- " / "* " items of a commit body; wrapped continuation lines join their bullet."""
    out: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith(("- ", "* ")):
            out.append(line[2:].strip())
        elif line and out and raw[:1].isspace():
            out[-1] += " " + line
        elif not line and out:
            out.append("")  # blank line ends the current bullet
    return [b for b in out if b]


def _line(c: Commit, repo_url: str | None) -> str:
    scope = f"**{c.scope}:** " if c.scope else ""
    sha = f"[`{c.sha}`]({repo_url}/commit/{c.sha})" if repo_url else f"`{c.sha}`"
    return f"{scope}{c.subject} ({sha})"


# --- CHANGELOG.md editing --------------------------------------------------------------------

UNRELEASED = "## [Unreleased]"


def split_unreleased(changelog: str) -> tuple[str, str, str]:
    """-> (head incl. Unreleased heading, unreleased notes, rest starting at next release)."""
    i = changelog.index(UNRELEASED) + len(UNRELEASED)
    j = changelog.find("\n## [", i)
    j = len(changelog) if j == -1 else j + 1
    return changelog[:i] + "\n\n", changelog[i:j].strip(), changelog[j:]


def insert_release(changelog: str, section: str) -> str:
    head, _notes, rest = split_unreleased(changelog)
    return head + section + ("\n" + rest if rest else "")


def extract_section(changelog: str, version: str) -> str:
    """Body of `## [version]` for GitHub release notes."""
    start = changelog.find(f"## [{version}]")
    if start == -1:
        raise KeyError(f"version {version} not in CHANGELOG.md")
    body_start = changelog.index("\n", start) + 1
    end = changelog.find("\n## [", body_start)
    return changelog[body_start : len(changelog) if end == -1 else end].strip() + "\n"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def commits_since(tag: str | None) -> list[Commit]:
    rng = f"{tag}..HEAD" if tag else "HEAD"
    raw = git("log", "--reverse", "--format=%H%x1f%B%x1e", rng)
    out = []
    for entry in raw.split("\x1e"):
        if not entry.strip():
            continue
        sha, _, msg = entry.strip().partition("\x1f")
        if (c := parse_commit(sha, msg)) and not (c.type == "chore" and c.scope == "release"):
            out.append(c)
    return out


def last_tag() -> str | None:
    try:
        return git("describe", "--tags", "--abbrev=0", "--match", "v*")
    except subprocess.CalledProcessError:
        return None
