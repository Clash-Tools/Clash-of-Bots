import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from versioning import (  # noqa: E402
    Version,
    extract_section,
    insert_release,
    next_version,
    parse_commit,
    render_section,
)

V = Version.parse


@pytest.mark.parametrize(
    "cur, channel, bump, expected",
    [
        ("0.1.0-alpha.0", "alpha", None, "0.1.0-alpha.1"),
        ("0.1.0-alpha.3", "alpha", None, "0.1.0-alpha.4"),
        ("0.1.0-alpha.3", "beta", None, "0.1.0-beta.1"),
        ("0.1.0-beta.2", "rc", None, "0.1.0-rc.1"),
        ("0.1.0-rc.1", "stable", None, "0.1.0"),
        ("0.1.0-alpha.2", "stable", None, "0.1.0"),
        ("0.1.0", "alpha", "minor", "0.2.0-alpha.1"),
        ("0.1.0", "stable", "patch", "0.1.1"),
        ("1.4.2", "beta", "major", "2.0.0-beta.1"),
    ],
)
def test_next_version(cur, channel, bump, expected):
    assert str(next_version(V(cur), channel, bump)) == expected


def test_cannot_go_backwards_or_skip_bump():
    with pytest.raises(ValueError, match="back"):
        next_version(V("0.1.0-beta.1"), "alpha")
    with pytest.raises(ValueError, match="stable"):
        next_version(V("0.1.0"), "alpha")


def test_file_version_sorts_with_channels():
    order = ["0.1.0-alpha.1", "0.1.0-alpha.12", "0.1.0-beta.1", "0.1.0-rc.2", "0.1.0", "0.1.1-alpha.1"]
    fv = [tuple(map(int, V(v).file_version.split("."))) for v in order]
    assert fv == sorted(fv)
    assert V("0.1.0").file_version == "0.1.0.9000"
    assert V("v0.2.0-rc.3").tag == "v0.2.0-rc.3" and V("0.2.0-rc.3").prerelease


def test_parse_rejects_garbage():
    for bad in ("1.0", "1.0.0-dev", "1.0.0-alpha", "x.y.z"):
        with pytest.raises(ValueError):
            V(bad)


def test_parse_commit():
    c = parse_commit("abcdef123", "feat(vision)!: new matcher\n\n- detail one\n")
    assert (c.type, c.scope, c.subject) == ("feat", "vision", "new matcher")
    assert c.breaking and c.sha == "abcdef1"
    assert parse_commit("1", "random message") is None
    assert parse_commit("1", "fix: x\n\nBREAKING CHANGE: api").breaking


def test_render_and_roundtrip_changelog():
    commits = [
        parse_commit("1111111", "feat(device): faster capture\n\n- raw screencap\n"),
        parse_commit("2222222", "fix: crash on start"),
        parse_commit("3333333", "style: whitespace"),
    ]
    section = render_section(V("0.2.0-beta.1"), commits, "Big one.", today=date(2026, 1, 2))
    assert section.startswith("## [0.2.0-beta.1] - 2026-01-02")
    assert "Channel: **Beta**" in section and "### Highlights" in section
    assert "- **device:** faster capture (`1111111`)\n  - raw screencap" in section
    assert "### Bug Fixes" in section and "### Chores" in section  # unknown type 'style' kept

    log = "# Changelog\n\n## [Unreleased]\n\nBig one.\n\n## [0.1.0] - 2026-01-01\n\nold\n"
    new = insert_release(log, section)
    assert new.index("## [Unreleased]") < new.index("## [0.2.0-beta.1]") < new.index("## [0.1.0]")
    assert "Big one.\n\n## [0.2.0" not in new  # notes moved out of Unreleased
    assert extract_section(new, "0.1.0").strip() == "old"
    assert extract_section(new, "0.2.0-beta.1").startswith("Channel: **Beta**")


def test_wrapped_body_bullets_are_joined():
    from versioning import body_bullets

    body = ("- first point that wraps\n  onto a second line\n- second\n\n"
            "Plain paragraph text\nnot a bullet\n* star bullet")
    assert body_bullets(body) == ["first point that wraps onto a second line", "second", "star bullet"]
