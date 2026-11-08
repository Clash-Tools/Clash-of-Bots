"""UI v2 shell (#49): navigation, run state, Kill Switch / Esc, status strip, safety-stop classification."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from cob.tasks.farm import FarmStats  # noqa: E402
from cob.ui.shell import BOTTOM_PAGES, PAGES, Shell  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from cob.ui.style import qss

    app = QApplication.instance() or QApplication([])
    qss.apply(app)
    return app


def test_rail_switches_pages(qapp):
    from PySide6.QtWidgets import QLabel

    shell = Shell()
    for key, _, _ in PAGES:
        shell.add_page(key, QLabel(key))
    seen = []
    shell.page_changed.connect(seen.append)
    shell.nav["history"].click()
    assert shell.current_page() == "history" and seen == ["history"]
    assert shell.stack.currentWidget().widget().findChild(QLabel).text() == "history"


def test_state_drives_pill_kill_switch_and_session(qapp, monkeypatch):
    import cob.ui.shell as shell_mod

    now = [100.0]
    monkeypatch.setattr(shell_mod.time, "monotonic", lambda: now[0])
    shell = Shell()
    assert not shell.kill_button.isEnabled() and shell.state_pill.state == "idle"
    fired = []
    shell.kill_switch.connect(lambda: fired.append(1))
    shell.set_state("running")
    assert shell.kill_button.isEnabled()
    shell.kill_button.click()
    assert fired == [1]
    now[0] = 100 + 3725
    shell._tick()
    assert shell.session.text() == "Session: 01h 02m 05s"
    shell.set_state("break")
    assert shell.kill_button.isEnabled() and shell.state_pill.state == "break"
    shell.set_state("stopped")
    now[0] += 50
    shell._tick()
    assert not shell.kill_button.isEnabled() and shell.session.text() == "Session: 01h 02m 05s"  # frozen
    shell.set_step("Searching for a base")
    assert shell.step.text() == "Current step: Searching for a base"


def _window():
    from cob.ui.main_window import MainWindow

    return MainWindow(devices=lambda: [("moto g84 5G", "adb-AB12CD34EF-x")])


def test_main_window_uses_shell_and_esc_stops(qapp, monkeypatch):
    win = _window()
    assert set(win.shell.pages) == {k for k, _, _ in PAGES + BOTTOM_PAGES}
    assert win.shell.current_page() == "dashboard"
    assert "moto g84" in win.shell.connection.text()
    stopped = []
    monkeypatch.setattr(win, "stop", lambda: stopped.append(1))
    assert win.esc_shortcut.key().toString() == "Esc"
    win.esc_shortcut.activated.emit()
    win.shell.kill_switch.emit()
    assert stopped == [1, 1]


@pytest.mark.parametrize("reason, state", [
    ("stopped", "idle"), ("5 cycles done", "idle"), ("30 min elapsed", "idle"),
    ("3 failures in a row", "stopped"), ("device lost: gone", "stopped"),
    ("own gold below reserve", "stopped"),
])
def test_finished_reason_sets_safety_state(qapp, reason, state):
    win = _window()
    win.on_finished(FarmStats(stop_reason=reason))
    assert win.shell.state_pill.state == state
    assert win.shell.step.text().endswith(reason)


def test_background_refresh_does_not_block_the_window(qapp):
    import threading

    from cob.ui.main_window import MainWindow

    release = threading.Event()

    def slow_devices():
        release.wait(5)
        return [("moto g84 5G", "AB12CD34EF")]

    win = MainWindow(devices=slow_devices, background_refresh=True)  # returns while the lookup still runs
    assert win.shell.connection.text() == "Looking for devices…" and not win.refresh_button.isEnabled()
    win.refresh_devices()  # a second request while one runs is folded into it
    assert len(win._jobs) == 1
    seen = []
    win.devices_refreshed.connect(lambda: seen.append(1))
    release.set()
    win._jobs[0].wait(5000)
    qapp.processEvents()
    assert win.device_combo.currentData() == "AB12CD34EF" and seen == [1]
    assert win.refresh_button.isEnabled() and "moto g84" in win.shell.connection.text()
