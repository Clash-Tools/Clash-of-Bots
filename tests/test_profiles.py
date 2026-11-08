"""Profiles (#2): store, validation on load, per-profile settings / history / limits, page, run in turn."""

import json
import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cob.core import history  # noqa: E402
from cob.core.config import FarmConfig, save_farm_config  # noqa: E402
from cob.core.profiles import DEFAULT_ID, Profile, Profiles, normalize_tag, slug  # noqa: E402
from cob.tasks.farm import CycleResult  # noqa: E402
from cob.tasks.schedule import install_seed, today_usage  # noqa: E402

# --- store --------------------------------------------------------------------------------------


def test_existing_install_becomes_the_default_profile(tmp_path):
    save_farm_config(FarmConfig(max_nexts=17), tmp_path / "farm.json")
    store = Profiles(tmp_path)
    assert [p.id for p in store.profiles] == [DEFAULT_ID] and store.active.name == "Default"
    assert store.load_config(DEFAULT_ID).max_nexts == 17  # the old farm.json, not moved
    assert not (tmp_path / "profiles.json").exists()  # nothing written until something changes


def test_add_copy_update_remove(tmp_path):
    store = Profiles(tmp_path)
    store.save_config(DEFAULT_ID, FarmConfig(max_nexts=9))
    alt = store.add("Alt  account", copy_from=DEFAULT_ID)
    assert alt.id == "alt-account" and alt.name == "Alt account"
    assert store.load_config(alt.id).max_nexts == 9
    assert (tmp_path / "profiles" / "alt-account" / "farm.json").is_file()
    assert store.add("Alt account").id == "alt-account-2"  # same name: unique id
    assert store.add("Default").id == "default-2"
    assert store.load_config("alt-account-2") == FarmConfig()  # no copy: defaults

    saved = store.update(Profile(alt.id, "  Main ", " emulator-5556 ", "2pq8 y0l", True))
    assert (saved.name, saved.serial, saved.player_tag, saved.rotation) == ("Main", "emulator-5556",
                                                                            "#2PQ8Y0L", True)
    assert store.update(Profile(alt.id, "", "", "not a tag!", False)).name == "Main"  # empty name kept
    assert store.get(alt.id).player_tag == ""  # a bad tag is dropped

    store.set_active(alt.id)
    again = Profiles(tmp_path)  # saved at once
    assert again.active_id == alt.id and again.get(alt.id).serial == ""
    again.remove(alt.id)
    assert again.active_id == DEFAULT_ID and not (tmp_path / "profiles" / alt.id).exists()
    with pytest.raises(ValueError):
        again.remove(DEFAULT_ID)
    with pytest.raises(KeyError):
        again.set_active("nope")


def test_profile_file_is_validated_on_load(tmp_path):
    (tmp_path / "profiles.json").write_text(json.dumps({
        "active": "ghost",
        "profiles": [
            {"id": "ok", "name": "Ok", "serial": "emulator-5554", "player_tag": "#2pq", "rotation": True},
            {"id": "ok", "name": "Duplicate"},
            {"id": "Bad Id", "name": "x"},
            {"id": "../evil", "name": "x"},
            {"id": "noname", "name": "   "},
            {"id": "types", "name": "Types", "serial": 5, "player_tag": ["x"], "rotation": "yes"},
            "not an object",
        ]}), "utf-8")
    store = Profiles(tmp_path)
    assert [p.id for p in store.profiles] == [DEFAULT_ID, "ok", "types"]
    assert store.active_id == DEFAULT_ID  # unknown active falls back
    assert store.get("ok") == Profile("ok", "Ok", "emulator-5554", "#2PQ", True)
    assert store.get("types") == Profile("types", "Types")
    (tmp_path / "profiles.json").write_text("{broken", "utf-8")
    assert [p.id for p in Profiles(tmp_path).profiles] == [DEFAULT_ID]
    (tmp_path / "profiles.json").write_text("[1, 2]", "utf-8")
    assert [p.id for p in Profiles(tmp_path).profiles] == [DEFAULT_ID]


def test_tags_and_slugs():
    assert normalize_tag("#2pq8y0l") == "#2PQ8Y0L"
    assert normalize_tag(" 2PQ 8YOL ") == "#2PQ8Y0L"  # O typed for zero
    assert normalize_tag("#ABC") == ""  # A, B are never in a tag
    assert normalize_tag("") == "" and normalize_tag("#2") == ""
    assert slug("Main / War!") == "main-war" and slug("***") == "profile"


# --- history, daily limits, seeds ---------------------------------------------------------------


def test_daily_limits_count_only_the_profiles_own_rows(tmp_path):
    p = tmp_path / "h.csv"
    for profile in ("default", "alt", "alt"):
        history.append(CycleResult(1, "accepted", attack="done", seconds=60), path=p, profile=profile)
    rows = history.read(path=p) + [{"time": f"{date.today()} 01:00:00", "attack": "done", "seconds": "30"}]
    today = date.today()
    assert today_usage(rows, today, "alt") == (120.0, 2)
    assert today_usage(rows, today, "default") == (90.0, 2)  # an old row without a profile is Default's
    assert today_usage(rows, today) == (210.0, 4)


def test_each_profile_draws_its_own_schedule():
    assert install_seed() == install_seed("default")
    assert install_seed("alt") != install_seed("default")


def test_limits_and_history_rows_carry_the_profile():
    from cob.tasks.wiring import farm_limits

    assert farm_limits(FarmConfig(), profile="alt").schedule_seed == install_seed("alt")
    assert history.to_row(CycleResult(1, "x"), profile="alt")["profile"] == "alt"
    assert history.to_row(CycleResult(1, "x"))["profile"] == DEFAULT_ID


# --- CLI ----------------------------------------------------------------------------------------


def test_cli_lists_profiles_and_farm_needs_a_device(capsys):
    from cob.cli import main

    store = Profiles()
    alt = store.add("Alt")
    store.update(Profile(alt.id, "Alt", "", "#2PQ", True))
    assert main(["profiles"]) == 0
    out = capsys.readouterr().out
    assert "* default" in out and "alt" in out and "#2PQ" in out and "in turn" in out
    assert main(["farm", "--profile", "alt"]) == 2
    assert "has no device" in capsys.readouterr().err
    assert main(["farm", "--profile", "ghost"]) == 2


# --- page and window ----------------------------------------------------------------------------


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_profiles_page_edits_the_store(qapp, tmp_path):
    from cob.ui.pages.profiles import ProfilesPage

    store = Profiles(tmp_path)
    names = iter(["Alt", "Third"])
    page = ProfilesPage(store, ask_name=lambda *_: next(names), confirm_delete=lambda *_: True)
    changed = []
    page.changed.connect(lambda: changed.append(1))
    page.set_devices([("LDPlayer #1", "emulator-5556"), ("No device", None)])
    assert page.list.count() == 1 and not page.delete_button.isEnabled() and not page.run_button.isEnabled()

    page.new_profile()
    assert page._current().id == "alt" and page.delete_button.isEnabled()
    page.device.setCurrentIndex(page.device.findData("emulator-5556"))
    page.tag.setText("bad tag")
    page.save()
    assert "not a player tag" in page.form_status.text() and store.get("alt").serial == ""
    page.tag.setText("2pq8y0l")
    page.rotation.setChecked(True)
    page.save()
    assert store.get("alt") == Profile("alt", "Alt", "emulator-5556", "#2PQ8Y0L", True)
    assert page.run_button.isEnabled() and "Alt" in page.turn_label.text()

    page.duplicate()
    assert store.get("third").rotation and page._current().id == "third"
    page.delete()
    assert store.get("third") is None and len(changed) == 4

    used = []
    page.use_requested.connect(used.append)
    page.list.setCurrentRow(1)
    page.use()
    assert used == ["alt"]
    store.update(Profile("alt", "Alt", "emulator-9999"))  # device not connected now
    page.refresh("alt")
    assert "not found now" in page.device.currentText()


def test_window_switches_profiles_and_runs_them_in_turn(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from cob.ui.main_window import MainWindow
    from tests.test_gui import FakeParts, _run_worker

    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append("warning"))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append("critical"))
    store = Profiles()
    store.save_config(DEFAULT_ID, FarmConfig(max_nexts=11))
    alt = store.add("Alt")
    store.save_config(alt.id, FarmConfig(max_nexts=22))
    built = []
    devices = [("LDPlayer #0", "emulator-5554"), ("LDPlayer #1", "emulator-5556")]
    win = MainWindow(devices=lambda: devices, profiles=store,
                     build=lambda s, c, p: built.append((s, c.max_nexts, p)) or FakeParts())
    assert win.profile_combo.count() == 2 and win.filter_spins["max_nexts"].value() == 11

    win.switch_profile(alt.id)
    assert win.filter_spins["max_nexts"].value() == 22 and win.profile_combo.currentData() == alt.id
    win.device_combo.setCurrentIndex(1)
    win._device_picked(1)  # the user picked LDPlayer #1: it is Alt's device now
    assert store.get(alt.id).serial == "emulator-5556"
    win.filter_spins["max_nexts"].setValue(33)  # unsaved edit ...
    win.switch_profile(DEFAULT_ID)  # ... saved to Alt on the way out
    assert store.load_config(alt.id).max_nexts == 33 and win.filter_spins["max_nexts"].value() == 11
    assert win.device_combo.currentData() == "emulator-5556"  # Default has no device of its own: kept

    win.start_rotation()  # nothing ticked
    assert shown == ["warning"] and win._worker is None
    store.update(Profile(DEFAULT_ID, "Default", "emulator-5554", "", True))
    store.update(Profile(alt.id, "Alt", "emulator-5556", "", True))
    win.cycles_spin.setValue(2)
    win.start_rotation()
    assert not win.profile_combo.isEnabled()
    _run_worker(qapp, win)
    assert win._queue == [alt.id] and len(built) == 1
    win._run_next_profile()  # what the 3 s timer does
    _run_worker(qapp, win)
    assert built == [("emulator-5554", 11, DEFAULT_ID), ("emulator-5556", 33, alt.id)]
    assert store.active_id == alt.id and win._queue == [] and win.profile_combo.isEnabled()
    assert [r["profile"] for r in win.history._rows] == [DEFAULT_ID] * 2 + [alt.id] * 2


def test_stop_ends_a_run_in_turn(qapp, monkeypatch):
    import threading

    from cob.ui.main_window import MainWindow
    from tests.test_gui import FakeParts, _run_worker

    store = Profiles()
    store.update(Profile(DEFAULT_ID, "Default", "emulator-5554", "", True))
    alt = store.add("Alt")
    store.update(Profile(alt.id, "Alt", "emulator-5556", "", True))
    parts = FakeParts(block=threading.Event())
    win = MainWindow(devices=lambda: [("LDPlayer #0", "emulator-5554")], profiles=store,
                     build=lambda *_: parts)
    win.start_rotation()
    assert win._queue == [alt.id]
    win.stop()
    _run_worker(qapp, win)
    assert win._queue == [] and store.active_id == DEFAULT_ID
