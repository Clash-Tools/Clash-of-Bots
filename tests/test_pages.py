"""UI v2 pages (#63, #64): dashboard formatting and automation settings behaviour (offscreen)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from cob.attack.loot import Loot  # noqa: E402
from cob.core.config import FarmConfig  # noqa: E402
from cob.tasks.farm import CycleResult, FarmStats  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from cob.ui.style import qss

    app = QApplication.instance() or QApplication([])
    qss.apply(app)
    return app


def test_compact_numbers():
    from cob.ui.pages.dashboard import _k

    assert [_k(n) for n in (0, 9_999, 12_345, -45_000, 1_530_000)] == ["0", "9,999", "12k", "-45k", "1.53M"]


def test_dashboard_stats_and_last_cycle(qapp):
    from cob.ui.pages.dashboard import DashboardPage

    d = DashboardPage()
    cycles = [CycleResult(1, "accepted", 3, attack="done", gained=Loot(400_000, 300_000, 2_000), seconds=180),
              CycleResult(2, "error", reason="adb hiccup", seconds=20)]
    d.set_stats(FarmStats(cycles=cycles), max_cycles=4)
    assert d.tiles["gold"].value.text() == "400k" and d.tiles["cycles"].sub.text() == "Session complete: 50%"
    assert d.tiles["attacks"].sub.text() == "1 done / 0 failed"
    d.set_stats(FarmStats(cycles=cycles))
    assert d.tiles["cycles"].sub.text() == "1 error"
    d.set_last_cycle(cycles[0])
    assert d.last_title.text() == "Cycle #1  •  Attack done" and d.last_gold.text() == "+400,000"
    d.set_guardrails(FarmConfig(wall_upgrades=2, break_every=0))
    assert d.guard_count.text() == "3 / 6 ON"


def test_dashboard_running_swaps_start_and_stop(qapp):
    from cob.ui.pages.dashboard import DashboardPage

    d = DashboardPage()
    d.set_running(True)
    assert d.stop_button.isVisibleTo(d) and not d.start_button.isVisibleTo(d) and not d.mode.isEnabled()
    d.set_step("attack")
    assert d.pipeline.steps["attack"].state == "active"
    d.show_safety_stop("3 failures in a row")
    assert not d.banner.isHidden()
    d.set_running(True)
    assert d.banner.isHidden()


def test_automation_dirty_discard_and_defaults(qapp):
    from cob.ui.pages.automation import AutomationPage

    page = AutomationPage()
    page.set_config(FarmConfig(max_nexts=30))
    assert not page.dirty() and page.unsaved.isHidden()
    page.spins["max_nexts"].setValue(45)
    assert page.dirty() and not page.unsaved.isHidden()
    page.unsaved.discard.emit()
    assert page.config().max_nexts == 30 and not page.dirty()
    page.defaults_button.click()
    assert page.config() == FarmConfig() and page.dirty()  # defaults are not saved until Save
    page.mark_saved()
    assert not page.dirty()


@pytest.mark.parametrize("typed_ok, walls", [(True, 1), (False, 0)])
def test_walls_need_typed_confirmation(qapp, typed_ok, walls):
    from cob.ui.pages.automation import AutomationPage

    asked = []
    page = AutomationPage(confirm_spend=lambda parent: asked.append(1) or typed_ok)
    page.set_config(FarmConfig())
    page.walls_switch.click()
    assert asked == [1] and page.config().wall_upgrades == walls
    assert page.walls_switch.isChecked() == bool(walls)
    page.walls_switch.setChecked(False)
    assert page.config().wall_upgrades == 0


def test_every_farm_field_has_a_control(qapp):
    from dataclasses import fields

    from cob.ui.pages.automation import AutomationPage
    from cob.ui.pages.safety import SafetyPage

    a, s = AutomationPage(), SafetyPage()
    auto, safety = {*a.spins, *a.toggles}, {*s.spins, *s.toggles}
    dashboard = {"army_recipe"}  # #185: picked next to Start on the dashboard
    assert not auto & safety and auto | safety | dashboard == {f.name for f in fields(FarmConfig)}


def _row(day, mode="home", attack="done", gold="100", seconds="60", reason=""):
    return {"time": f"{day} 12:00:00", "mode": mode, "attack": attack, "gained_gold": gold,
            "gained_elixir": "50", "gained_dark": "", "seconds": seconds, "reason": reason,
            "search": "accepted"}


def test_history_filters_totals_and_days():
    from datetime import date

    from cob.ui.pages.history import filter_rows, per_day, totals

    today = date(2026, 10, 26)
    rows = [_row("2026-10-10"), _row("2026-10-25", "bb", "failed", "0", reason="battle did not end"),
            _row("2026-10-26"), {**_row("2026-10-26"), "mode": ""}]  # old row without mode = home
    assert len(filter_rows(rows, days=7, today=today)) == 3
    assert len(filter_rows(rows, mode="home", today=today)) == 3
    assert len(filter_rows(rows, mode="bb", today=today)) == 1
    assert len(filter_rows(rows, search="did not END", today=today)) == 1
    tot = totals(filter_rows(rows, days=1, today=today))
    assert (tot.gold, tot.elixir, tot.attacks, tot.seconds) == (200, 100, 2, 120)
    assert tot.per_hour == 300 * 3600 / 120
    days = per_day(rows, 7, today=today)
    assert len(days) == 7 and list(days)[-1] == today and days[today].attacks == 2
    assert days[date(2026, 10, 25)].cycles == 1 and days[date(2026, 10, 25)].attacks == 0


def test_history_page_renders_rows(qapp):
    from datetime import date

    from cob.ui.pages.history import HistoryPage

    page = HistoryPage()
    today = date.today().isoformat()
    page.set_rows([_row(today), _row(today, "bb")], "h.csv")
    assert page.table.rowCount() == 2 and page.table.item(0, 1).text() == "Builder Base"  # newest first
    page.mode.set_value("bb")
    page.refresh()
    assert page.table.rowCount() == 1 and page.summary.text().startswith("Showing 1 of 2")
    page.search.setText("nothing matches this")
    assert page.table.isHidden() and not page.empty.isHidden()


def test_chart_axis_rounding():
    from cob.ui.widgets.chart import nice_max, short

    assert [nice_max(v) for v in (0, 7, 23, 140, 1_700_000)] == [1.0, 10, 25, 200, 2_000_000]
    assert [short(v) for v in (500, 2500, 1_500_000)] == ["500", "2.5k", "1.5M"]


def test_log_filter_levels_and_regex(qapp):
    from cob.ui.log_bridge import LogLine
    from cob.ui.pages.logs import LogsPage, matches

    err = LogLine("12:00:01", "ERROR", "tasks.farm", "cycle 3 failed: device not reachable")
    info = LogLine("12:00:02", "INFO", "tasks.search", "base 14 gold 412,300 -> attack")
    assert matches(err, "ERROR", "") and not matches(info, "ERROR", "")
    assert matches(info, "ALL", r"gold \d+") and matches(info, "ALL", "GOLD")
    assert matches(info, "ALL", "[unclosed") is False and matches(
        LogLine("t", "INFO", "m", "a [unclosed b"), "ALL", "[unclosed")  # bad regex = plain text
    page = LogsPage()
    for line in (err, info, info):
        page.add(line)
    assert page.chips["ALL"].text() == "ALL  3" and page.chips["ERROR"].text() == "ERROR  1"
    page.chips["ERROR"].click()
    assert [x.message for x in page.visible_lines()] == [err.message]
    page.chips["ALL"].click()
    page.search.setText("gold")
    assert len(page.visible_lines()) == 2 and page.footer.text().startswith("Showing 2 lines")
    page.clear()
    assert page.view.count() == 0 and page.chips["ALL"].text() == "ALL  0"


def test_snapshot_line_shows_preview(qapp, tmp_path):
    import cv2
    import numpy as np

    from cob.ui.log_bridge import LogLine
    from cob.ui.pages.logs import LogsPage

    shot = tmp_path / "20261026-120000_unknown.png"
    cv2.imwrite(str(shot), np.zeros((90, 160, 3), np.uint8))
    page = LogsPage()
    page.add(LogLine("12:00:00", "INFO", "core.snapshots", f"snapshot saved: {shot}"))
    page.view.setCurrentRow(0)
    assert not page.detail.isHidden() and page.detail_path.text() == str(shot)


def test_diagnostics_scrub_private_details(tmp_path):
    import json
    import zipfile

    from cob.core.diagnostics import build_zip, sanitize

    text = ("connected adb-AB12CD34EF-x1Yz9Q at 192.168.1.201:41949 serialno AB12CD34EF, "
            "log in /home/alice/.local/share, user alice, adb at 127.0.0.1:5037")
    out = sanitize(text, serials={"AB12CD34EF"}, home="/home/alice", user="alice")
    assert "AB12CD34EF" not in out and "192.168.1.201" not in out and "alice" not in out
    assert "127.0.0.1:5037" in out and "<home>/.local/share" in out
    log = tmp_path / "session.log"
    log.write_text("phone AB12CD34EF at 10.0.0.7:5555", "utf-8")
    z = build_zip(tmp_path / "d.zip", [log, tmp_path / "missing.log"], {"device": "x"})
    with zipfile.ZipFile(z) as f:
        assert set(f.namelist()) >= {"summary.json", "logs/session.log"}
        assert "10.0.0.7" not in f.read("logs/session.log").decode()
        assert json.loads(f.read("summary.json"))["device"] == "x"


def test_automation_categories_work_as_tabs(qapp):
    # #101: one section at a time instead of one long scrolling page.
    from cob.ui.pages.automation import CATEGORIES, AutomationPage

    page = AutomationPage(confirm_spend=lambda _w: True)
    assert page.current_section() == CATEGORIES[0][0]
    page.category_buttons["upgrades"].click()
    assert page.current_section() == "upgrades" and page.category_buttons["upgrades"].isChecked()
    assert not page.category_buttons["farming"].isChecked()
    assert len(page.sections) == len(CATEGORIES) and not page.sections["farming"].isVisibleTo(page)


def test_devices_page_lists_and_signals(qapp):
    from cob.device.discovery import CONNECT, Nearby, Service
    from cob.ui.pages.devices import DevicesPage, device_icon, short_serial

    assert short_serial("adb-AB12CD34EF-x1Yz9Q._adb-tls-connect._tcp") == "AB12CD34EF (Wi-Fi)"
    assert [device_icon(s) for s in ("emulator-5554", "192.168.1.5:5555", "AB12CD34EF")] == [
        "desktop_windows", "wifi_tethering", "usb"]
    page = DevicesPage()
    used, connected = [], []
    page.use_device.connect(used.append)
    page.connect_address.connect(connected.append)
    page.set_devices([("LDPlayer #0", "emulator-5554"), ("Phone", "AB12CD34EF")], "emulator-5554")
    page.set_devices([("LDPlayer #0", "emulator-5554"), ("Phone", "AB12CD34EF")], "emulator-5554")  # no dupes
    rows = [page.connected_box.itemAt(i).widget() for i in range(page.connected_box.count())]
    assert len(rows) == 2 and rows[0].button is None  # the device in use has no "Use" button
    rows[1].button.click()
    page.set_nearby([Nearby(Service("adb-R5CT30XYZ-Qq9Zz1", CONNECT, "192.168.1.40:39001"), False, False)])
    page.nearby_box.itemAt(0).widget().button.click()
    assert used == ["AB12CD34EF"] and connected == ["192.168.1.40:39001"]


def test_health_has_its_own_page_and_devices_can_recheck(qapp):
    # #100: health checks moved to a rail tab at the bottom; Devices gets a Recheck button.
    from cob.ui.main_window import MainWindow

    calls = []
    win = MainWindow(devices=lambda: calls.append(1) or [("Phone", "AB12CD34EF")])
    assert not hasattr(win.devices, "check_grid") and win.check_grid is win.health.check_grid
    rail = win.shell.nav["health"]
    assert rail.parentWidget().layout().indexOf(rail) == rail.parentWidget().layout().count() - 1
    before = len(calls)
    win.devices.recheck_button.click()
    assert len(calls) == before + 1
    assert win.health.checked_device.text() == "AB12CD34EF"


def test_devices_use_button_switches_top_bar_device(qapp):
    from cob.ui.main_window import MainWindow

    win = MainWindow(devices=lambda: [("LDPlayer #0", "emulator-5554"), ("Phone", "AB12CD34EF")])
    assert win.device_combo.currentData() == "emulator-5554"
    win.devices.use_device.emit("AB12CD34EF")
    assert win.device_combo.currentData() == "AB12CD34EF"
    assert win.health.checked_device.text() == "AB12CD34EF"


def test_ui_settings_round_trip_and_validation(tmp_path):
    from cob.core import ui_settings

    p = tmp_path / "ui.json"
    assert ui_settings.load(p) == ui_settings.UiSettings()  # missing file
    ui_settings.save(ui_settings.UiSettings(start_minimized=True, notify_breaks=True), p)
    assert ui_settings.load(p).start_minimized and ui_settings.load(p).notify_breaks
    p.write_text('{"start_minimized": "yes", "notify_finished": false, "extra": 1}', "utf-8")
    s = ui_settings.load(p)
    assert s.start_minimized is False and s.notify_finished is False  # bad type -> default, unknown ignored
    p.write_text("[1, 2]", "utf-8")
    assert ui_settings.load(p) == ui_settings.UiSettings()


def test_settings_page_emits_and_formats(qapp):
    from cob.core.ui_settings import UiSettings
    from cob.ui.pages.settings import SettingsPage, channel, human_size

    assert [channel(v) for v in ("0.3.0", "0.4.0-beta.2", "1.0.0-rc.1", "0.1.0-alpha.3")] == [
        "Stable", "Beta", "Release candidate", "Alpha"]
    assert [human_size(n) for n in (500, 2048, 5 * 1024 * 1024)] == ["500 B", "2.0 KB", "5.0 MB"]
    page = SettingsPage(UiSettings(notify_breaks=True))
    seen = []
    page.changed.connect(seen.append)
    page.start_minimized.switch.click()
    assert seen[-1] == UiSettings(start_minimized=True, notify_breaks=True)
    page.show_usage({"Logs": 3000, "Snapshots": 1000})
    assert page.used.text() == "3.9 KB USED" and page.usage.count() == 2


def test_notifications_follow_settings(qapp, monkeypatch):
    from cob.core.ui_settings import UiSettings
    from cob.ui.main_window import MainWindow

    win = MainWindow(devices=lambda: [("LDPlayer #0", "emulator-5554")])
    shown = []
    win.tray = type("Tray", (), {"showMessage": lambda self, *a: shown.append(a[0])})()
    win.ui_settings = UiSettings(notify_finished=False, notify_breaks=True)
    win.on_finished(FarmStats(stop_reason="5 cycles done"))
    win.on_finished(FarmStats(stop_reason="3 failures in a row"))
    win.on_break(60)
    assert shown == ["Farming stopped", "Break"]


def test_safety_page_usage_quiet_and_defaults(qapp):
    from cob.ui.pages.safety import SafetyPage

    page = SafetyPage()
    page.set_config(FarmConfig(daily_minutes=240, daily_attacks=35, quiet_from=23, quiet_to=7, min_dark=1234))
    page.set_usage(134 * 60, 14)
    assert page.time_text.text() == "Today: 2h 14m played of 4h 00m" and page.time_bar.value() == 558
    assert page.attack_text.text() == "Today: 14 attacks of 35" and page.attack_bar.value() == 400
    assert page.quiet_text.text() == "The bot will not run 23:00 – 07:00 (8 h)"
    page.defaults_button.click()
    cfg = page.config()
    assert cfg.daily_minutes == 0 and cfg.min_dark == 1234  # only safety fields reset
    assert page.dirty() and not page.unsaved.isHidden()


def test_window_saves_both_pages_into_one_farm_json(qapp):
    from cob.core.config import load_farm_config
    from cob.ui.main_window import MainWindow

    win = MainWindow(devices=lambda: [("LDPlayer #0", "emulator-5554")])
    win.filter_spins["max_nexts"].setValue(33)
    win.safety.spins["daily_attacks"].setValue(40)
    win.safety.save_requested.emit()
    saved = load_farm_config()
    assert saved.max_nexts == 33 and saved.daily_attacks == 40
    assert not win.automation.dirty() and not win.safety.dirty()


def _wizard(devices, **kw):
    from cob.ui.wizard import SetupWizard

    calls = []
    w = SetupWizard(None, lambda: devices, lambda: calls.append("refresh"),
                    lambda s: calls.append(("use", s)), lambda: calls.append("launch"),
                    lambda: calls.append("qr"), lambda: calls.append("checks"), **kw)
    return w, calls


def test_wizard_needs_consent_and_a_device(qapp):
    from cob.device.checks import Check

    devices = []
    w, calls = _wizard(devices)
    assert w.pages.currentIndex() == 0 and not w.back.isEnabled()
    w.next.click()
    assert w.pages.currentIndex() == 1 and not w.next.isEnabled()  # risk notice: consent required
    w.consent.setChecked(True)
    w.next.click()
    w.targets["wifi"].click()
    w.next.click()
    assert w.pages.currentIndex() == 3 and w.qr_button.isVisibleTo(w) and not w.launch_button.isVisibleTo(w)
    assert not w.next.isEnabled()  # no device yet
    devices.append(("Phone", "AB12CD34EF"))
    w.qr_button.click()  # pairing done -> list refreshes
    w.device_list.itemAt(0).widget().findChildren(type(w.next))[0].click()  # "Use this device"
    assert ("use", "AB12CD34EF") in calls and w.pages.currentIndex() == 4 and "checks" in calls
    w.show_checks([Check("ADB connection", True, "ok"), Check("Screen size", False, "1080x2400")])
    assert w.check_summary.text().startswith("1/2 checks passed")
    done = []
    w.finished_setup.connect(lambda: done.append(1))
    assert w.next.text().strip() == "GO TO DASHBOARD"
    w.next.click()
    assert done == [1]


def test_wizard_remembers_consent_and_window_marks_done(qapp):
    from cob.core import ui_settings
    from cob.ui.main_window import MainWindow

    w, _ = _wizard([("LDPlayer #0", "emulator-5554")], consented=True)
    w.next.click()
    assert w.next.isEnabled()  # consent already given
    win = MainWindow(devices=lambda: [("LDPlayer #0", "emulator-5554")])
    wiz = win.open_wizard()
    wiz.consent.setChecked(True)
    wiz.finished_setup.emit()
    saved = ui_settings.load()
    assert saved.risk_accepted and saved.wizard_done
    wiz.close()


def test_wizard_tells_how_to_fix_a_locked_phone(qapp):
    from cob.device.checks import Check

    w, _ = _wizard([("Phone", "AB12CD34EF")], consented=True)
    w.targets["usb"].click()
    w.go(3)
    assert "Keep the phone unlocked" in w.connect_help.text()
    w.targets["ldplayer"].click()
    w.go(3)
    assert "unlocked" not in w.connect_help.text()
    w.show_checks([Check("ADB connection", True, "ok"), Check("Phone unlocked", False, "unlock the phone")])
    assert w.check_summary.text().startswith("The phone locked itself")


def test_safety_switches_round_trip_through_farm_json_fields(qapp):
    # #120: on/off fields are switches; their state is part of the page's config.
    from dataclasses import replace

    from cob.ui.pages.safety import SafetyPage

    page = SafetyPage()
    page.set_config(replace(FarmConfig(), resume_after_rest=1))
    assert page.toggles["resume_after_rest"].isChecked() and not page.dirty()
    page.toggles["close_game_resting"].switch.setChecked(True)
    assert page.dirty() and page.config().close_game_resting == 1


def test_pause_button_toggles_the_worker_and_its_label(qapp):
    # #133: Pause / Resume on the run card; the worker holds the farm loop between cycles.
    from cob.ui.main_window import MainWindow
    from cob.ui.worker import FarmWorker

    win = MainWindow(devices=lambda: [("Phone", "AB12CD34EF")])
    worker = FarmWorker(lambda: None, None)
    worker.isRunning = lambda: True
    win._worker = worker
    win.dashboard.set_running(True)
    assert win.dashboard.pause_button.isVisibleTo(win.dashboard)
    win.dashboard.pause_button.click()
    assert worker.is_paused() and "RESUME" in win.dashboard.pause_button.text()
    assert win.shell.state_pill.state == "break"
    win.dashboard.pause_button.click()
    assert not worker.is_paused() and "PAUSE" in win.dashboard.pause_button.text()
    win._worker = None


def test_device_list_shows_before_the_wifi_reconnect_finishes(qapp):
    # #162: the top bar listed devices only after every Wi-Fi reconnect timed out (up to 60 s). Now the
    # adb list shows at once, the reconnect runs after, and a phone that comes back is listed then.
    import threading

    from cob.ui.main_window import MainWindow

    release = threading.Event()
    listed = [[("LDPlayer #0", "emulator-5554")]]

    def reconnect():
        release.wait(5)
        listed.append([("LDPlayer #0", "emulator-5554"), ("Phone", "192.168.1.5:5555")])
        return ["192.168.1.5:5555"]

    win = MainWindow(devices=lambda: listed[-1], background_refresh=True, reconnect=reconnect)
    _wait(qapp, lambda: win.device_combo.count() == 1 and win.device_combo.itemData(0) == "emulator-5554")
    assert win._spinner.busy(win.refresh_button) and win.shell.activity.isVisibleTo(win.shell)
    release.set()
    _wait(qapp, lambda: win.device_combo.count() == 2)
    _wait(qapp, lambda: win._refresh_job is None)
    assert win.refresh_button.isEnabled() and not win._spinner.busy(win.refresh_button)
    assert not win.shell.activity.isVisibleTo(win.shell)


def _wait(qapp, cond, timeout=5.0):
    import time

    end = time.monotonic() + timeout
    while not cond():
        qapp.processEvents()
        assert time.monotonic() < end, "timed out"
        time.sleep(0.01)
