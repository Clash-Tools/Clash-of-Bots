"""Cut a release: bump version, write CHANGELOG section, signed commit + signed tag.

  uv run python scripts/release.py alpha                 # 0.1.0-alpha.1 -> 0.1.0-alpha.2
  uv run python scripts/release.py beta                  # -> 0.1.0-beta.1
  uv run python scripts/release.py stable                # -> 0.1.0
  uv run python scripts/release.py alpha --bump minor    # 0.1.0 -> 0.2.0-alpha.1
  ... --dry-run   show version + changelog section, change nothing
  ... --push      push main + tag (tag push triggers .github/workflows/release.yml)

Helpers used by CI:
  scripts/release.py current | file-version | notes VERSION
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from versioning import (  # noqa: E402
    CHANNELS,
    Version,
    commits_since,
    extract_section,
    git,
    insert_release,
    last_tag,
    next_version,
    render_section,
    split_unreleased,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "cob" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
REPO_URL = "https://github.com/Clash-Tools/Clash-of-Bots"
_VERSION_RE = re.compile(r'^__version__ = "([^"]+)"$', re.M)


def current() -> Version:
    return Version.parse(_VERSION_RE.search(VERSION_FILE.read_text("utf-8")).group(1))


def write_version(v: Version) -> None:
    text = VERSION_FILE.read_text("utf-8")
    VERSION_FILE.write_text(_VERSION_RE.sub(f'__version__ = "{v}"', text), "utf-8")


def preflight() -> None:
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        sys.exit("release from main only (merge the feature branch first)")
    if git("status", "--porcelain"):
        sys.exit("working tree not clean")
    git("fetch", "origin", "main", "--tags")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        sys.exit("main differs from origin/main: pull/push first")


def cmd_cut(args) -> int:
    cur = current()
    new = next_version(cur, args.channel, args.bump)
    commits = commits_since(last_tag())
    changelog = CHANGELOG.read_text("utf-8")
    _, notes, _ = split_unreleased(changelog)
    section = render_section(new, commits, notes, repo_url=REPO_URL)
    print(f"{cur} -> {new}  (tag {new.tag}, file version {new.file_version})\n")
    print(section)
    if args.dry_run:
        return 0
    if not commits:
        sys.exit("no conventional commits since last tag: nothing to release")
    preflight()
    write_version(new)
    CHANGELOG.write_text(insert_release(changelog, section), "utf-8")
    git("add", str(VERSION_FILE), str(CHANGELOG))
    git("commit", "-S", "-m", f"chore(release): {new.tag}")
    git("tag", "-s", new.tag, "-m", f"Clash of Bots {new.tag} ({new.label})")
    print(f"committed + tagged {new.tag}")
    if args.push:
        git("push", "origin", "main")
        git("push", "origin", new.tag)
        print("pushed; release workflow will build and publish")
    else:
        print(f"push with: git push origin main && git push origin {new.tag}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for ch in CHANNELS:
        c = sub.add_parser(ch, help=f"release on {ch} channel")
        c.add_argument("--bump", choices=["major", "minor", "patch"])
        c.add_argument("--dry-run", action="store_true")
        c.add_argument("--push", action="store_true")
        c.set_defaults(fn=cmd_cut, channel=ch)
    sub.add_parser("current").set_defaults(fn=lambda a: print(current()) or 0)
    sub.add_parser("file-version").set_defaults(fn=lambda a: print(current().file_version) or 0)
    n = sub.add_parser("notes", help="print CHANGELOG section for VERSION")
    n.add_argument("version")
    n.set_defaults(fn=lambda a: print(extract_section(CHANGELOG.read_text("utf-8"), a.version)) or 0)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
