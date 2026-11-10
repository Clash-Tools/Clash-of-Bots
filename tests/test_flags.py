"""Feature flags (D-038): registry, file, environment override, hidden Developer options, gated UI."""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cob.core import flags  # noqa: E402


def test_registry_is_complete_and_tracked():
    assert len({f.key for f in flags.FLAGS}) == len(flags.FLAGS)
    for f in flags.FLAGS:
        assert f.stage in flags.STAGES and f.title and f.description
        assert f.issue, f"{f.key} has no issue to finish it"
        assert f.default == (f.stage == flags.BETA)


def test_defaults_file_and_environment(tmp_path):
    p = tmp_path / "flags.json"
    f = flags.load(p, env="")
    assert f.enabled("builder_base") and not f.enabled("clan_games") and not f.developer
    f.set("clan_games", True)
    f.set("builder_base", True)  # already the default: not stored
    f.developer = True
    flags.save(f, p)
    assert json.loads(p.read_text()) == {"developer": True, "flags": {"clan_games": True}}
    again = flags.load(p, env="-clan_games,coc_api_sync,nonsense")
    assert not again.enabled("clan_games") and again.enabled("coc_api_sync") and again.developer
    assert again.changed() == ["coc_api_sync=on"]
    with pytest.raises(KeyError):
        again.enabled("nonsense")


@pytest.mark.parametrize("content", ["{broken", "[1]", '{"flags": "x", "developer": "yes"}',
                                     '{"flags": {"clan_games": "on", "ghost": true}}'])
def test_a_bad_file_falls_back_to_defaults(tmp_path, content):
    p = tmp_path / "flags.json"
    p.write_text(content)
    f = flags.load(p, env="")
    assert not f.developer and f.values == {}


def test_current_reads_the_user_file_once(monkeypatch):
    flags.save(flags.Flags({"clan_games": True}))
    assert flags.enabled("clan_games")
    flags.save(flags.Flags())  # changed on disk: the running app keeps what it started with
    assert flags.enabled("clan_games")
    flags.reset()
    assert not flags.enabled("clan_games")


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_incomplete_features_are_hidden_by_default(qapp):
    from cob.ui.main_window import MainWindow

    win = MainWindow(devices=lambda: [])
    a = win.automation
    assert a.tabs.buttons["games"].isHidden() and a.upgrades_note.isHidden() and a.stream_row.isHidden()
    assert not a.tabs.buttons["builder"].isHidden() and not win.dashboard.mode.isHidden()  # beta: on
    p = win.profiles_page
    assert p.turn_card.isHidden() and p.rotation.isHidden() and p.sync_button.isHidden() and p.tag.isHidden()
    s = win.settings_page
    assert s.coc_token.isHidden() and s.tabs.buttons["developer"].isHidden()
    assert not win.shell.nav["cards"].isHidden()
    win.profiles.update(win.profiles.active.__class__("default", "Default", "emulator-5554", "", True))
    win.start_rotation()  # experimental and off: nothing starts
    assert win._worker is None


def test_flags_show_the_features(qapp, monkeypatch):
    from cob.ui.main_window import MainWindow

    monkeypatch.setenv("COB_FLAGS", "clan_games,building_upgrades,profile_rotation,coc_api_sync,"
                                    "live_stream,-builder_base,-card_labelling")
    win = MainWindow(devices=lambda: [])
    a = win.automation
    assert not a.tabs.buttons["games"].isHidden() and not a.upgrades_note.isHidden()
    assert not a.stream_row.isHidden()
    assert a.tabs.buttons["builder"].isHidden() and win.dashboard.mode.isHidden()
    p = win.profiles_page
    assert not p.turn_card.isHidden() and not p.sync_button.isHidden() and not p.tag.isHidden()
    assert not win.settings_page.coc_token.isHidden() and win.shell.nav["cards"].isHidden()


def test_developer_options_unlock_after_seven_clicks(qapp):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from cob.ui.pages.settings import SettingsPage

    page = SettingsPage()
    assert page.tabs.buttons["developer"].isHidden()
    click = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(2, 2), QPointF(2, 2),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    for _ in range(6):
        page.version_label.mousePressEvent(click)
    assert page.tabs.buttons["developer"].isHidden()
    page.version_label.mousePressEvent(click)
    assert not page.tabs.buttons["developer"].isHidden() and page.tabs.current() == "developer"
    assert flags.load().developer  # remembered

    page.flag_rows["clan_games"].switch.setChecked(True)
    assert flags.load().values == {"clan_games": True}
    assert not page.flags_restart.isHidden() and "Restart" in page.flags_note.text()
    page.flag_rows["clan_games"].switch.setChecked(False)
    assert page.flags_restart.isHidden()

    page.set_developer(False)
    assert page.tabs.buttons["developer"].isHidden() and not flags.load().developer
    assert page.tabs.current() != "developer"


def test_developer_switch_in_about_asks_first(qapp, monkeypatch):
    from cob.ui.pages.settings import SettingsPage

    asked = []
    page = SettingsPage()
    monkeypatch.setattr(page, "confirm", lambda parent: asked.append(parent) or False)
    assert not page.developer_switch.isChecked() and page.tabs.buttons["developer"].isHidden()

    page.developer_switch.setChecked(True)  # declined: stays off
    assert len(asked) == 1 and not page.developer_switch.isChecked()
    assert page.tabs.buttons["developer"].isHidden() and not flags.load().developer

    monkeypatch.setattr(page, "confirm", lambda parent: asked.append(parent) or True)
    page.developer_switch.setChecked(True)  # accepted: tab shown and opened, remembered
    assert len(asked) == 2 and page.developer_switch.isChecked()
    assert not page.tabs.buttons["developer"].isHidden() and page.tabs.current() == "developer"
    assert flags.load().developer

    page.set_developer(False)  # "Hide developer options" turns the switch off, no question
    assert len(asked) == 2 and not page.developer_switch.isChecked()
    page.developer_switch.setChecked(True)
    page.developer_switch.setChecked(False)  # turning off never asks
    assert len(asked) == 3 and page.tabs.buttons["developer"].isHidden() and not flags.load().developer


def test_seven_clicks_turn_the_switch_on(qapp):
    from cob.ui.pages.settings import SettingsPage

    page = SettingsPage()
    page.confirm = lambda parent: pytest.fail("the hidden unlock does not ask")
    page.unlock_developer()
    assert page.developer_switch.isChecked() and SettingsPage().developer_switch.isChecked()
