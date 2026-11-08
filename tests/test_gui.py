"""GUI on Qt's offscreen platform: filter round-trip, worker signals into the window, stop, log."""

import json
import logging
import os
import threading
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from cob.attack.loot import Loot  # noqa: E402
from cob.core.config import FarmConfig, default_path  # noqa: E402
from cob.tasks.farm import CycleResult, FarmStats  # noqa: E402
from cob.ui.log_bridge import LogBridge, QtLogHandler  # noqa: E402
from cob.ui.main_window import MainWindow  # noqa: E402

DEVICES = [("LDPlayer #0 'LDPlayer' (running, 1600x900@240)", "emulator-5554")]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    # Tear Qt down while Python is still alive: leftover windows/threads destroyed during interpreter
    # shutdown crash PySide on Linux (SIGBUS after all tests passed in CI).
    for w in app.topLevelWidgets():
        worker = getattr(w, "_worker", None)
        if worker is not None:
            worker.request_stop()
            worker.wait(10_000)
        w.close()
        w.deleteLater()
    app.processEvents()
    app.shutdown()


@pytest.fixture
def no_dialogs(monkeypatch):
    shown = []
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, _n=name, **k: shown.append(_n))
    return shown


class FakeParts:
    """What build_farm returns, minus the device: farm_task runs two scripted cycles."""

    def __init__(self, block: threading.Event | None = None):
        self.nav = SimpleNamespace(stop=threading.Event())
        self.block = block
        self.limits = None

    def farm_task(self, limits, on_cycle=None, on_break=None, on_step=None):
        self.limits = limits
        parts = self

        class Task:
            def run(self):
                stats = FarmStats()
                for n in (1, 2):
                    if parts.block is not None:  # wait until the test presses Stop
                        parts.nav.stop.wait(5)
                    if parts.nav.stop.is_set():
                        stats.stop_reason = "stopped"
                        return stats
                    c = CycleResult(n, "accepted", attack="done", gained=Loot(100_000, 50_000, 500),
                                    seconds=180)
                    stats.cycles.append(c)
                    on_cycle(c)
                stats.stop_reason, stats.seconds = "2 cycles done", 360
                return stats

        return Task()


def _run_worker(qapp, win):
    win._worker.wait(10_000)
    qapp.processEvents()  # deliver the queued signals from the worker thread


def test_filter_round_trip(qapp, no_dialogs):
    win = MainWindow(devices=lambda: DEVICES, build=lambda s, c, *_: FakeParts())
    assert win.filter_config() == FarmConfig()
    win.filter_spins["min_gold_elixir"].setValue(600_000)
    win.filter_spins["max_nexts"].setValue(15)
    win.save_filter()
    saved = json.loads(default_path().read_text("utf-8"))
    assert saved["min_gold_elixir"] == 600_000 and saved["max_nexts"] == 15
    assert MainWindow(devices=lambda: DEVICES).filter_config().max_nexts == 15


def test_start_needs_a_device(qapp, no_dialogs):
    win = MainWindow(devices=lambda: [], build=lambda s, c, *_: FakeParts())
    win.start()
    assert no_dialogs == ["warning"] and win._worker is None


def test_farm_run_updates_stats(qapp, no_dialogs):
    built = []
    win = MainWindow(devices=lambda: DEVICES, build=lambda s, c, *_: built.append((s, c)) or FakeParts())
    win.cycles_spin.setValue(2)
    win.start()
    assert not win.start_button.isEnabled() and win.stop_button.isEnabled()
    _run_worker(qapp, win)
    assert built[0][0] == "emulator-5554"
    tiles = {k: v.value.text() for k, v in win.dashboard.tiles.items()}
    assert tiles["cycles"] == "2" and tiles["attacks"] == "2" and tiles["gold"] == "200k"
    assert win.shell.step.text() == "stopped: 2 cycles done" and tiles["rate"] == "3.00M"
    assert win.dashboard.tiles["rate"].toolTip().startswith("gold +2,000,000")
    assert win.dashboard.tiles["gold"].sub.text() == "2.00M / hr"
    assert win.shell.state_pill.state == "idle" and win.dashboard.banner.isHidden()
    assert win.dashboard.last_title.text().startswith("Cycle #2")
    assert win.start_button.isEnabled() and not win.stop_button.isEnabled()


def test_stop_button_stops_the_loop(qapp, no_dialogs):
    parts = FakeParts(block=threading.Event())
    win = MainWindow(devices=lambda: DEVICES, build=lambda s, c, *_: parts)
    win.start()
    win.stop()
    _run_worker(qapp, win)
    assert parts.nav.stop.is_set() and win.shell.step.text() == "stopped: stopped"


def test_build_error_is_shown_not_raised(qapp, no_dialogs):
    def boom(serial, cfg, *_):
        raise RuntimeError("device emulator-5554 not reachable")

    win = MainWindow(devices=lambda: DEVICES, build=boom)
    win.start()
    _run_worker(qapp, win)
    assert no_dialogs == ["critical"] and "not reachable" in win.shell.step.text()
    assert win.shell.state_pill.state == "stopped" and not win.dashboard.banner.isHidden()
    assert win.dashboard.banner.title.text() == "Farming stopped"  # an error, not a safety rule
    # Live 2026-11-06: the next run still showed "Stopped: <old error>" under the pipeline.
    win._build = lambda s, c: FakeParts()
    win.start()
    assert win.dashboard.banner.isHidden() and "Stopped" not in win.dashboard.pipeline_info.text()
    _run_worker(qapp, win)


def test_army_recipe_is_saved_with_the_settings(qapp):
    # #185: the dashboard's army recipe goes into farm.json and comes back from it.
    win = MainWindow(devices=lambda: DEVICES)
    win.dashboard.army.setCurrentIndex(win.dashboard.army.findData(3))
    assert win.filter_config().army_recipe == 3
    win.set_filter(FarmConfig(army_recipe=2))
    assert win.dashboard.army_recipe() == 2 and win.filter_config().army_recipe == 2
    win.dashboard.set_running(True)
    assert not win.dashboard.army.isEnabled()


def test_device_names_are_short():
    from cob.ui.main_window import device_name

    wifi = "adb-AB12CD34EF-x1Yz9Q._adb-tls-connect._tcp"
    assert device_name("Phone moto g84 5G (AB12CD34EF)", wifi) == "moto g84 5G  •  Wi-Fi"
    assert device_name("Phone moto g84 5G (AB12CD34EF)", "AB12CD34EF") == "moto g84 5G  •  USB"
    assert device_name(None, "emulator-5554") == "emulator-5554"


def test_log_lines_reach_the_window(qapp):
    win = MainWindow(devices=lambda: DEVICES)
    bridge = LogBridge()
    win.connect_log(bridge)
    handler = QtLogHandler(bridge)
    logger = logging.getLogger("cob.test_gui")
    logger.addHandler(handler)
    try:
        logger.warning("hello from the bot")
    finally:
        logger.removeHandler(handler)
    qapp.processEvents()
    lines = win.logs.visible_lines()
    assert lines[-1].message == "hello from the bot" and lines[-1].level == "WARNING"
    assert not hasattr(win.dashboard, "activity")


def _wait_jobs(qapp, win):
    for job in list(win._jobs):
        job.wait(10_000)
    qapp.processEvents()


def test_setup_checks_render_and_enable_fixes(qapp, no_dialogs):
    from cob.device.checks import Check

    results = [Check("LDPlayer installed", True, "C:/LDPlayer/LDPlayer14"),
               Check("Instance resolution", False, "1280x720 @ 240 dpi - needs 1600x900 @ 240", "resize")]
    fixes = []
    win = MainWindow(devices=lambda: DEVICES, checks=lambda serial: results,
                     fixer=lambda action, serial: fixes.append((action, serial)) or True)
    win.run_checks()
    _wait_jobs(qapp, win)
    assert win.resize_button.isEnabled() and not win.launch_button.isEnabled()
    assert "Fix the red items" in win.setup_status.text() and win.check_grid.count() == 6
    win.run_fix("resize")
    _wait_jobs(qapp, win)
    _wait_jobs(qapp, win)  # the fix re-runs the checks
    assert fixes == [("resize", "emulator-5554")]


def test_grab_shows_preview(qapp, no_dialogs):
    import numpy as np

    frame = np.zeros((900, 1600, 3), np.uint8)
    frame[:, :800] = (0, 0, 255)
    win = MainWindow(devices=lambda: DEVICES, grab=lambda serial: (frame, "HOME"))
    win.grab_preview()
    _wait_jobs(qapp, win)
    assert win.preview.pixmap() is not None and not win.preview.pixmap().isNull()
    assert win.dashboard.scene.text() == "HOME" and win.dashboard.updated.text() == "updated just now"


def test_history_tab_loads_file_and_adds_new_cycles(qapp, no_dialogs):
    from cob.core import history

    history.append(CycleResult(1, "accepted", 0, Loot(600_000, 500_000, 4_000), "done",
                               Loot(400_000, 300_000, 2_000), 200))
    win = MainWindow(devices=lambda: DEVICES)
    assert win.history_table.rowCount() >= 1 and "cycles" in win.history_summary.text()
    before = win.history_table.rowCount()
    win.on_cycle(CycleResult(9, "accepted", 0, Loot(1, 2, 3), "done", Loot(7_000, 8_000, 9), 50))
    assert win.history_table.rowCount() == before + 1
    assert win.history_table.item(0, 7).text() == "+7,000"  # newest on top, "+ Gold" column
    assert win.history_summary.text().startswith(f"Showing {before + 1} of")


def test_theme_and_icon(qapp):
    from PySide6.QtGui import QPalette

    from cob.ui.theme import app_icon, apply_dark

    apply_dark(qapp)
    assert not app_icon().isNull()
    assert qapp.palette().color(QPalette.ColorRole.Window).getRgb()[:3] == (43, 45, 49)


def test_builder_base_mode_runs_bb_loop(qapp, no_dialogs, monkeypatch):
    import cob.ui.worker as worker

    used = []

    def fake_bb(parts, limits, on_cycle=None, on_break=None, on_step=None):
        used.append("bb")
        return parts.farm_task(limits, on_cycle, on_break, on_step)

    monkeypatch.setattr(worker, "bb_farm_task", fake_bb)
    win = MainWindow(devices=lambda: DEVICES, build=lambda s, c, *_: FakeParts())
    win.dashboard.mode.set_value("bb")
    win.start()
    assert "Builder Base" in win.shell.step.text() and not win.dashboard.mode.isEnabled()
    _run_worker(qapp, win)
    assert used == ["bb"]


def test_phone_buttons_pass_the_fields_and_show_the_answer(qapp, no_dialogs):
    calls = []

    def phone(action, serial, address, code):
        calls.append((action, serial, address, code))
        if action == "pair":
            raise RuntimeError("pairing failed: wrong code")
        return f"{action} ok"

    phones = [("Phone moto g84 5G (AB12CD34EF)", "AB12CD34EF")]
    win = MainWindow(devices=lambda: phones, phone=phone)
    win.wifi_address.setText("192.168.1.5:5555")
    win.pair_address.setText("192.168.1.5:41234")
    win.pair_code.setText("123456")
    win.run_phone("connect")
    _wait_jobs(qapp, win)
    assert win.phone_status.text() == "connect ok" and win.restore_button.isEnabled()
    win.run_phone("pair")
    _wait_jobs(qapp, win)
    assert win.phone_status.text().startswith("error: pairing failed")
    win.run_phone("restore")
    _wait_jobs(qapp, win)
    assert calls == [("connect", "AB12CD34EF", "192.168.1.5:5555", "123456"),
                     ("pair", "AB12CD34EF", "192.168.1.5:41234", "123456"),
                     ("restore", "AB12CD34EF", "192.168.1.5:5555", "123456")]
