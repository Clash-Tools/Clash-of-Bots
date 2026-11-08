"""Update check (#104): version order, channels, changelog and the Settings page."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cob.core import updates  # noqa: E402
from cob.core.updates import Release  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _rel(tag, pre=False, notes=""):
    return Release(tag, f"Clash of Bots {tag}", notes or f"notes {tag}", f"https://x/{tag}", pre)


RELEASES = [_rel("v0.5.0-beta.1", True), _rel("v0.4.1"), _rel("v0.4.0"), _rel("v0.3.0"), _rel("nightly")]


def test_versions_sort_by_number_then_channel():
    keys = ["0.4.0-alpha.2", "0.4.0-beta.1", "0.4.0-rc.1", "0.4.0", "0.4.1", "0.10.0"]
    assert sorted(keys, key=updates.parse) == keys
    assert updates.parse("v0.4.0") == updates.parse("0.4.0") and updates.parse("latest") is None


def test_stable_builds_see_stable_releases_only():
    info = updates.check(RELEASES, "0.4.0")
    assert info.available and [r.tag for r in info.newer] == ["v0.4.1"] and info.latest.tag == "v0.4.1"
    assert "## Clash of Bots v0.4.1" in info.changelog() and "notes v0.4.1" in info.changelog()


def test_prerelease_builds_also_see_prereleases():
    info = updates.check(RELEASES, "0.4.1-rc.1")
    assert [r.tag for r in info.newer] == ["v0.5.0-beta.1", "v0.4.1"]


def test_up_to_date():
    info = updates.check(RELEASES, "0.4.1")
    assert not info.available and info.changelog() == ""


def test_fetch_reads_the_api_shape(monkeypatch):
    import io
    import json

    body = json.dumps([{"tag_name": "v0.4.1", "name": "N", "body": "B", "html_url": "U", "prerelease": False},
                       {"tag_name": "v9.9.9", "draft": True}]).encode()

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    seen = {}

    def fake_urlopen(req, timeout):
        seen["ua"] = req.get_header("User-agent")
        return Resp(body)

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    assert updates.fetch() == [Release("v0.4.1", "N", "B", "U", False)]
    assert seen["ua"].startswith("ClashOfBots/")


def test_settings_page_shows_the_changelog(qapp):
    from cob.ui.main_window import _update_error
    from cob.ui.pages.settings import SettingsPage

    page = SettingsPage()
    asked = []
    page.check_updates.connect(lambda: asked.append(1))
    page.update_button.click()
    assert asked == [1] and not page.update_button.isEnabled()
    page.show_update(updates.check(RELEASES, "0.4.0"))
    assert page.update_button.isEnabled() and "0.4.1 is available" in page.update_status.text()
    assert not page.changelog.isHidden() and "notes v0.4.1" in page.changelog.toPlainText()
    assert page._release_url == "https://x/v0.4.1"
    page.show_update(updates.check(RELEASES, "0.4.1"))
    assert "latest version" in page.update_status.text() and page.changelog.isHidden()
    page.show_update_error(_update_error("HTTP Error 404: Not Found"))
    assert "private" in page.update_status.text()
