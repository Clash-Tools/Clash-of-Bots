"""Main window: Farm (device, run, stats, live preview), Settings, Setup, History and Log tabs."""

from __future__ import annotations

import logging
import shutil
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QProcess, Qt, QTime, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cob import __version__
from cob.core import history, ui_settings
from cob.core.config import FarmConfig, load_farm_config, save_farm_config
from cob.core.i18n import tr
from cob.tasks.farm import CycleResult, FarmStats
from cob.tasks.wiring import FarmParts, build_farm, farm_limits
from cob.ui.jobs import Job
from cob.ui.pages.automation import AutomationPage
from cob.ui.pages.dashboard import DashboardPage
from cob.ui.pages.devices import DevicesPage
from cob.ui.pages.health import HealthPage
from cob.ui.pages.history import HistoryPage
from cob.ui.pages.logs import LogsPage
from cob.ui.pages.safety import SafetyPage
from cob.ui.pages.settings import SettingsPage
from cob.ui.shell import Shell, logo_icon
from cob.ui.style import tokens
from cob.ui.style.icons import icon
from cob.ui.widgets import Card
from cob.ui.widgets import label as text_label
from cob.ui.widgets.busy import Spinner
from cob.ui.wizard import SetupWizard
from cob.ui.worker import FarmWorker

log = logging.getLogger(__name__)


def reconnect_wifi() -> list[str]:
    """Wi-Fi phones from before come back into adb's list, also on a new port (slow: network timeouts)."""
    from cob.device.wireless import reconnect_all

    return reconnect_all()


def list_devices() -> list[tuple[str, str]]:
    """(label, adb serial) for running adb devices plus LDPlayer instances (running or not). Fast: only
    what adb already holds; reconnect_wifi() brings remembered Wi-Fi phones back separately."""
    out: dict[str, str] = {}
    try:
        from cob.device.adb import list_serials
        from cob.device.phone import phone_label

        for serial in list_serials():
            out[serial] = device_name(phone_label(serial), serial)
    except Exception as exc:
        log.warning("adb: %s", exc)
    try:
        from cob.device.ldplayer import LdConsole

        for inst in LdConsole().list():
            state = tr("running") if inst.running else tr("stopped")
            size = f"{inst.width}x{inst.height}@{inst.dpi}" if inst.width else "?"
            out[inst.adb_serial] = tr("LDPlayer #{index} '{name}' ({state}, {size})", index=inst.index,
                                      name=inst.name, state=state, size=size)
    except Exception as exc:
        log.info("LDPlayer: %s", exc)
    return [(label, serial) for serial, label in out.items()]


def device_name(label: str | None, serial: str) -> str:
    """'moto g84 5G  •  Wi-Fi' for the top bar: the model and how it is connected. The adb serial (an
    mDNS name like adb-AB12CD34EF-x1Yz9Q._adb-tls-connect._tcp on Wi-Fi) is only in the tooltip."""
    if not label:
        return serial
    model = label.removeprefix("Phone ").rsplit(" (", 1)[0]
    wifi = ":" in serial or "._adb-tls-connect" in serial
    return tr("{model}  •  {link}", model=model, link=tr("Wi-Fi") if wifi else tr("USB"))


def _run_checks(serial):
    from cob.device.checks import run_checks

    return run_checks(serial)


def _run_fix(action, serial):
    from cob.device.checks import fix

    return fix(action, serial)


def _phone_action(action: str, serial: str | None, address: str = "", code: str = "") -> str:
    """Setup tab phone buttons (run in a Job thread); returns the message to show."""
    from cob.device import phone, wireless

    if action == "connect":
        return tr("Connected to {address}. Pick it in the top bar.", address=wireless.connect(address))
    if action == "pair":
        wireless.pair(address, code)
        return tr("Paired. Now enter the address shown under Wireless debugging and press Connect.")
    if not serial:
        raise ValueError(tr("pick the phone in the top bar first"))
    if action == "wifi":
        return tr("Now also on Wi-Fi at {address}; the USB cable can be unplugged.",
                  address=wireless.usb_to_wifi(serial))
    if action == "restore":
        restored = phone.restore(serial)
        return (tr("Phone screen restored to its own settings ({restored}).", restored=restored) if restored
                else tr("Nothing saved for this phone: the bot never changed its screen."))
    raise ValueError(f"unknown phone action {action!r}")


def _update_error(message: str) -> str:
    """Plain words for the usual update-check failures."""
    if "404" in message:
        return tr("the release list is not reachable (the GitHub repository is private or was renamed)")
    if "403" in message or "rate limit" in message.lower():
        return tr("GitHub is limiting requests right now; try again in an hour")
    if "timed out" in message or "urlopen error" in message or "Name or service" in message:
        return tr("no connection to GitHub")
    return message


def _grab(serial):
    from cob.device.adb import AdbDevice
    from cob.screens import ScreenClassifier
    from cob.vision.frame import Frame
    from cob.vision.templates import TemplateStore

    frame = Frame(AdbDevice(serial).capture())
    return frame.bgr, ScreenClassifier(TemplateStore()).classify(frame).screen


class MainWindow(QMainWindow):
    devices_refreshed = Signal()

    def __init__(self, devices: Callable[[], list[tuple[str, str]]] = list_devices,
                 build: Callable[[str, FarmConfig], FarmParts] | None = None,
                 checks: Callable = _run_checks, fixer: Callable = _run_fix, grab: Callable = _grab,
                 tray: bool = False, phone: Callable = _phone_action, background_refresh: bool = False,
                 reconnect: Callable[[], list[str]] | None = None):
        super().__init__()
        self._devices = devices
        self._reconnect = reconnect  # slow Wi-Fi reconnect, run after the fast list is shown
        self._spinner = Spinner(self)  # loading icon on buttons whose job runs (#161)
        self._build = build or (lambda serial, cfg: build_farm(serial, cfg=cfg))
        self._checks, self._fixer, self._grab, self._phone = checks, fixer, grab, phone
        # #80: the real device lookup (adb reconnects, mDNS, ldconsole) can take ~10 s on slow Wi-Fi, so the
        # app runs it in a Job; tests pass fast fakes and keep the synchronous path.
        self._background_refresh = background_refresh
        self._refresh_job: Job | None = None
        self._worker: FarmWorker | None = None
        self._jobs: list[Job] = []
        self._cycles: list[CycleResult] = []
        self._mode = "home"
        self.setWindowTitle(f"Clash of Bots {__version__}")
        self.setWindowIcon(logo_icon())
        self.resize(1040, 720)

        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.shell = Shell()
        self.shell.kill_switch.connect(lambda: self.stop())
        self._device_picker()
        self.shell.add_page("dashboard", self._farm_tab())
        self.shell.add_page("devices", self._setup_tab())
        self.shell.add_page("automation", self._settings_tab())
        self.shell.add_page("safety", self._safety_page())
        self.shell.add_page("history", self._history_tab(), scroll=False)
        self.shell.add_page("logs", self._log_tab(), scroll=False)
        self.shell.add_page("settings", self._settings_page(tray))
        self.shell.add_page("health", self._health_page())
        self.shell.show_page("dashboard")
        self.setCentralWidget(self.shell)
        # Esc = emergency stop everywhere in the window (designs: "Stop farming (Esc)").
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=lambda: self.stop())
        self.tray = self._make_tray() if tray and QSystemTrayIcon.isSystemTrayAvailable() else None

        self.load_filter()
        self.refresh_devices()
        self.load_history()
        self._set_running(False)

    # --- tabs -----------------------------------------------------------------------------------

    def _device_picker(self) -> None:
        """Device pill in the top bar: picker + refresh (was the Farm tab's Device box)."""
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(260)
        self.device_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.device_combo.setToolTip(tr("Device the bot runs on"))
        self.device_combo.currentIndexChanged.connect(self._device_changed)
        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(icon("refresh", tokens.ON_SURFACE_VARIANT, 18))
        self.refresh_button.setToolTip(tr("Refresh devices (also reconnects Wi-Fi phones)"))
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.shell.device_slot.addWidget(self.device_combo)
        self.shell.device_slot.addWidget(self.refresh_button)

    def _device_changed(self) -> None:
        serial = self.device_combo.currentData()
        name = self.device_combo.currentText() if serial else tr("No device")
        self.shell.set_connection(name, bool(serial))
        if hasattr(self, "devices"):
            self.devices.set_devices([(self.device_combo.itemText(i), self.device_combo.itemData(i))
                                      for i in range(self.device_combo.count())], serial)
        if hasattr(self, "health"):
            self.health.set_device(serial)

    def _health_page(self) -> QWidget:
        """Health checks (#100), own rail tab; widgets keep their old Setup-tab names."""
        self.health = h = HealthPage()
        for name in ("check_grid", "check_button", "launch_button", "resize_button", "setup_status"):
            setattr(self, name, getattr(h, name))
        h.check_button.clicked.connect(self.run_checks)
        h.launch_button.clicked.connect(lambda: self.run_fix("launch"))
        h.resize_button.clicked.connect(lambda: self.run_fix("resize"))
        h.set_device(self.device_combo.currentData())
        return h

    def _safety_page(self) -> QWidget:
        """Safety & Schedule (#42): breaks, daily limits, quiet hours, stop rules (D-027)."""
        from cob.tasks.wiring import history_usage

        self.safety = page = SafetyPage()
        page.save_requested.connect(self.save_filter)
        self.shell.page_changed.connect(
            lambda key: page.set_usage(*history_usage()) if key == "safety" else None)
        return page

    def _settings_page(self, tray: bool) -> QWidget:
        """Settings page (#67): preferences in ui.json, config export / import / reset."""
        self.ui_settings = ui_settings.load()
        has_tray = tray and QSystemTrayIcon.isSystemTrayAvailable()
        self.settings_page = page = SettingsPage(self.ui_settings, has_tray)
        page.changed.connect(self._save_ui_settings)
        page.export_config.connect(self.export_config)
        page.import_config.connect(self.import_config)
        page.reset_config.connect(self.reset_config)
        page.test_notification.connect(
            lambda: self._notify("Clash of Bots", tr("Notifications work."), "test"))
        page.run_wizard.connect(self.open_wizard)
        page.restart_requested.connect(self.restart_app)
        page.check_updates.connect(self.check_updates)
        if self.ui_settings.check_updates:  # opt-in (#104): once per start, after the window is up
            QTimer.singleShot(5000, lambda: self.check_updates(quiet=True))
        self.shell.page_changed.connect(lambda key: page.refresh_usage() if key == "settings" else None)
        return page

    def _save_ui_settings(self, settings) -> None:
        self.ui_settings = settings
        ui_settings.save(settings)
        self.settings_page.set_settings(settings)

    def check_updates(self, quiet: bool = False) -> None:
        """Ask GitHub for a newer release (#104) in the background. quiet: the start-up check only says
        something (tray message) when an update exists, never on errors."""
        from cob.core import updates

        def done(info) -> None:
            self.settings_page.show_update(info)
            if info.available:
                self._notify("Clash of Bots", tr("Version {tag} is available: see Settings > Release.",
                                                 tag=info.newer[0].tag), "update")

        def failed(message: str) -> None:
            log.info("update check failed: %s", message)
            if not quiet:
                self.settings_page.show_update_error(_update_error(message))
            else:
                self.settings_page.update_button.setEnabled(True)

        self._start_job(lambda: updates.check(updates.fetch()), done, failed,
                        busy=(self.settings_page.update_button,))

    def restart_app(self) -> bool:
        """Start a new copy of the app and close this one (theme / accent apply at start-up)."""
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "Clash of Bots", tr("Stop farming first, then restart."))
            return False
        frozen = getattr(sys, "frozen", False) or "__compiled__" in globals()
        args = sys.argv[1:] if frozen else sys.argv  # the exe itself, or `python -m cob ...`
        if not QProcess.startDetached(sys.executable, args):
            QMessageBox.warning(self, "Clash of Bots",
                                tr("Could not restart: close and open the app yourself."))
            return False
        QApplication.quit()
        return True

    def open_wizard(self) -> SetupWizard:
        """First-run setup (#51); it uses the window's own device actions."""
        def devices() -> list[tuple[str, str]]:
            return [(self.device_combo.itemText(i), self.device_combo.itemData(i))
                    for i in range(self.device_combo.count())]

        self._wizard = w = SetupWizard(self, devices, self.refresh_devices, self._use_device,
                                       lambda: self.run_fix("launch"), self.pair_with_qr, self.run_checks,
                                       consented=self.ui_settings.risk_accepted)
        w.consent.toggled.connect(
            lambda on: self._save_ui_settings(replace(self.ui_settings, risk_accepted=on)))
        w.finished_setup.connect(
            lambda: self._save_ui_settings(replace(self.ui_settings, wizard_done=True)))
        self.devices_refreshed.connect(w._show_devices)
        w.finished.connect(lambda _r: (self.devices_refreshed.disconnect(w._show_devices),
                                       setattr(self, "_wizard", None)))
        w.open()
        return w

    def export_config(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(self, tr("Export settings"), "clash-of-bots-farm.json",
                                              "JSON (*.json)")
        if dest:
            save_farm_config(self.filter_config(), Path(dest))
            log.info("settings exported to %s", dest)

    def import_config(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, tr("Import settings"), "", "JSON (*.json)")
        if src:
            # load_farm_config validates and clamps every field; the form shows the result unsaved.
            self.automation.set_config(load_farm_config(Path(src)), mark_saved=False)
            self.shell.show_page("automation")
            log.info("settings imported from %s (not saved yet)", src)

    def reset_config(self) -> None:
        answer = QMessageBox.question(self, "Clash of Bots",
                                      tr("Reset every automation setting to its default and save?"))
        if answer == QMessageBox.StandardButton.Yes:
            self.set_filter(FarmConfig())
            self.save_filter()

    def _coming_soon(self, title: str, icon_name: str, text: str) -> QWidget:
        card = Card(title, icon_name, tag=tr("Coming soon"))
        card.body.addWidget(text_label(text, "muted", wrap=True))
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(card)
        lay.addStretch(1)
        return holder

    def _set_status(self, text: str, state: str | None = None, icon_name: str = "radar") -> None:
        """Current step in the status strip (+ run state); icon_name: "info" when stopped, "gpp_maybe" on
        an error (passed in, as the translated text can't be checked)."""
        if state:
            self.shell.set_state(state)
        self.shell.set_step(text, icon_name)

    def _farm_tab(self) -> QWidget:
        """Dashboard page (#63); the old attribute names stay as aliases for the rest of the window."""
        self.dashboard = d = DashboardPage()
        self.cycles_spin, self.minutes_spin = d.cycles.spin, d.minutes.spin
        self.start_button, self.stop_button, self.grab_button = d.start_button, d.stop_button, d.grab_button
        self.preview = d.preview
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        d.pause_button.clicked.connect(self.toggle_pause)
        self.grab_button.clicked.connect(self.grab_preview)
        d.review_logs.connect(lambda: self.shell.show_page("logs"))
        return d

    def _settings_tab(self) -> QWidget:
        """Automation page (#64); filter_spins / save / defaults keep their old names."""
        self.automation = page = AutomationPage()
        self.filter_spins = page.spins
        self.save_button, self.defaults_button = page.save_button, page.defaults_button
        page.save_requested.connect(self.save_filter)
        return page

    def _setup_tab(self) -> QWidget:
        """Devices page (#50); its widgets keep the old Setup-tab names (aliases below)."""
        self.devices = d = DevicesPage()
        for name in ("qr_button", "find_button", "wifi_address", "connect_button", "pair_address",
                     "pair_code", "pair_button", "wifi_button", "restore_button", "phone_status"):
            setattr(self, name, getattr(d, name))
        d.refresh.connect(self.refresh_devices)
        d.qr_button.clicked.connect(self.pair_with_qr)
        d.find_button.clicked.connect(self.find_nearby)
        d.connect_button.clicked.connect(lambda: self.run_phone("connect"))
        d.pair_button.clicked.connect(lambda: self.run_phone("pair"))
        d.wifi_button.clicked.connect(lambda: self.run_phone("wifi"))
        d.restore_button.clicked.connect(lambda: self.run_phone("restore"))
        d.connect_address.connect(self.connect_nearby)
        d.use_device.connect(self._use_device)
        return d

    def _use_device(self, serial: str) -> None:
        if (i := self.device_combo.findData(serial)) >= 0:
            self.device_combo.setCurrentIndex(i)

    def run_phone(self, action: str) -> None:
        if action == "restore" and self._worker is not None and self._worker.isRunning():
            self.phone_status.setText(tr("Stop the bot first: it restores the phone itself when it stops."))
            return
        serial = self.device_combo.currentData()
        address = (self.pair_address if action == "pair" else self.wifi_address).text()
        code = self.pair_code.text()
        buttons = (self.connect_button, self.pair_button, self.wifi_button, self.restore_button)
        for b in buttons:
            b.setEnabled(False)
        self.phone_status.setText(tr("working…"))

        def done(message: str) -> None:
            self.phone_status.setText(message)
            for b in buttons:
                b.setEnabled(True)
            if action in ("connect", "wifi"):
                self.refresh_devices()

        def failed(message: str) -> None:
            done(tr("error: {message}", message=message))

        self._start_job(lambda: self._phone(action, serial, address, code), done, failed,
                        busy=tuple(b for b in buttons if b is not None))

    def pair_with_qr(self) -> None:
        from cob.device import discovery
        from cob.ui.qr_dialog import QrPairDialog

        ok, detail = discovery.available()
        if not ok:
            self.phone_status.setText(tr("This adb cannot find phones on the network ({detail}). Update "
                                         "adb (platform-tools) or use the pairing code below.",
                                         detail=detail))
            return
        dialog = QrPairDialog(self)
        if dialog.exec() and dialog.serial:
            self.phone_status.setText(tr("Connected to {address}. Pick it in the top bar.",
                                         address=dialog.serial))
            self.refresh_devices()

    def find_nearby(self) -> None:
        from cob.device import discovery

        self.find_button.setEnabled(False)
        self.phone_status.setText(tr("looking for phones on this network…"))

        def done(found) -> None:
            self.find_button.setEnabled(True)
            self.devices.set_nearby(found)
            self.phone_status.setText("")

        def failed(message: str) -> None:
            self.find_button.setEnabled(True)
            self.phone_status.setText(tr("error: {message}", message=message))

        self._start_job(discovery.nearby, done, failed, busy=(self.find_button,))

    def connect_nearby(self, address: str) -> None:
        self.wifi_address.setText(address)
        self.run_phone("connect")

    def _history_tab(self) -> QWidget:
        """History page (#65); history_table / history_summary stay as aliases."""
        self.history = page = HistoryPage()
        self.history_table, self.history_summary = page.table, page.summary
        page.export.connect(self.export_history)
        page.reload.connect(self.load_history)
        return page

    def _log_tab(self) -> QWidget:
        """Logs page (#66)."""
        from cob.core.log import log_dir, session_log_file

        self.logs = LogsPage(log_dir(), session_log_file())
        self.logs.save_diagnostics.connect(self.save_diagnostics)
        self.logs.export_reports.connect(self.export_failure_reports)
        return self.logs

    def export_failure_reports(self) -> None:
        """#170: zip every failure report (screen, base outline, log lines) with this session's log."""
        from cob.core.log import session_log_file
        from cob.core.snapshots import export_reports, list_reports

        if not list_reports():
            QMessageBox.information(self, tr("Export failure reports"), tr("No failures recorded yet."))
            return
        stamp = QTime.currentTime().toString("HHmmss")
        name = f"clash-of-bots-failures-{stamp}.zip"
        dest, _ = QFileDialog.getSaveFileName(self, tr("Export failure reports"), name, "Zip (*.zip)")
        if not dest:
            return
        logs = [p for p in (session_log_file(),) if p is not None]
        count = export_reports(Path(dest), logs=logs)
        log.info("%d failure report(s) exported: %s", count, dest)

    def connect_log(self, bridge) -> None:
        """Send live log records to the Logs page."""
        bridge.record.connect(self.logs.add)

    def save_diagnostics(self) -> None:
        from cob.core.diagnostics import build_zip
        from cob.core.log import latest_session_log, log_dir, session_log_file

        stamp = QTime.currentTime().toString("HHmmss")
        name = f"clash-of-bots-diagnostics-{stamp}.zip"
        dest, _ = QFileDialog.getSaveFileName(self, tr("Save diagnostics"), name, "Zip (*.zip)")
        if not dest:
            return
        logs = [p for p in {session_log_file(), latest_session_log(), log_dir() / "cob.log"} if p is not None]
        build_zip(Path(dest), logs, {"device": self.device_combo.currentText()})
        log.info("diagnostics saved (private details removed): %s", dest)

    def _make_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(logo_icon(), self)
        tray.setToolTip(self.windowTitle())
        menu = QMenu()
        show = QAction(tr("Show"), self)
        show.triggered.connect(self.showNormal)
        self.tray_stop = QAction(tr("Stop farming"), self)
        self.tray_stop.triggered.connect(self.stop)
        quit_action = QAction(tr("Quit"), self)
        quit_action.triggered.connect(self.close)
        menu.addActions([show, self.tray_stop, quit_action])
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: self.showNormal()
                               if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()
        self._tray_menu = menu
        return tray

    def _notify(self, title: str, text: str, kind: str = "safety") -> None:
        """kind: safety / finished / break / test, filtered by the Settings toggles."""
        s = self.ui_settings
        wanted = {"safety": s.notify_safety_stop, "finished": s.notify_finished, "break": s.notify_breaks,
                  "test": True}.get(kind, True)
        if not wanted:
            return
        if self.tray is not None:
            self.tray.showMessage(title, text, logo_icon(), 8000)
        self._send_alert(title, text, kind == "test")

    def _send_alert(self, title: str, text: str, report: bool = False) -> None:
        """#43: the same alert to Discord / Telegram when set, in the background. report: show the
        result on the Settings page (the Test notification button)."""
        from cob.core import notify

        targets = notify.Targets.of(self.ui_settings)
        if not targets.any:
            if report:
                self.settings_page.alert_status.setText(tr("No Discord or Telegram set: tray only."))
            return
        done = self.settings_page.show_alert_result if report else (lambda _errors: None)
        self._start_job(lambda: notify.send(targets, title, text), done, lambda message: done([message]),
                        busy=(self.settings_page.test_button,) if report else ())

    # --- device ---------------------------------------------------------------------------------

    def refresh_devices(self) -> None:
        if not self._background_refresh:
            self._apply_devices(self._devices())
            return
        if self._refresh_job is not None:  # one lookup at a time; its result covers this request too
            return
        self.refresh_button.setEnabled(False)
        self.shell.set_connection(tr("Looking for devices…"), False)

        def finish() -> None:
            self._refresh_job = None
            self.refresh_button.setEnabled(self._worker is None or not self._worker.isRunning())
            self._device_changed()  # the status strip said "Looking for Wi-Fi phones…" until now

        def reconnected(back) -> None:
            if back:  # a Wi-Fi phone came back: list again (fast)
                self._refresh_job = self._start_job(self._devices, lambda found: (finish(),
                                                                                  self._apply_devices(found)),
                                                    lambda _m: finish(), busy=self._refresh_buttons())
            else:
                finish()

        def listed(found) -> None:
            self._apply_devices(found)  # what adb holds now shows at once (#162: it took up to 60 s)
            if self._reconnect is None:
                finish()
                return
            self.shell.set_connection(tr("Looking for Wi-Fi phones…"), bool(found))
            self._refresh_job = self._start_job(self._reconnect, reconnected, lambda m: (
                log.info("Wi-Fi reconnect failed: %s", m), finish()), busy=self._refresh_buttons())

        def failed(message: str) -> None:
            finish()
            log.warning("device lookup failed: %s", message)
            self._apply_devices([])

        self._refresh_job = self._start_job(self._devices, listed, failed, busy=self._refresh_buttons())

    def _refresh_buttons(self) -> tuple:
        return (self.refresh_button, self.devices.recheck_button)

    def _apply_devices(self, found: list[tuple[str, str]]) -> None:
        current = self.device_combo.currentData()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for label, serial in found:
            self.device_combo.addItem(label, serial)
            self.device_combo.setItemData(self.device_combo.count() - 1, serial, Qt.ItemDataRole.ToolTipRole)
        if current is not None and (i := self.device_combo.findData(current)) >= 0:
            self.device_combo.setCurrentIndex(i)
        if self.device_combo.count() == 0:
            self.device_combo.addItem(tr("No device found - see Devices"), None)
        self.device_combo.blockSignals(False)
        self._device_changed()
        self.devices_refreshed.emit()

    def _start_job(self, fn: Callable, done: Callable, failed: Callable, busy: tuple = ()) -> Job:
        """Run `fn` in a thread. `busy` buttons are disabled with a spinning icon until it ends (#161);
        they get their state back first, so `done` / `failed` can still change it."""
        job = Job(fn, self)
        self._spinner.start(*busy)
        job.done.connect(lambda *_: self._spinner.stop(*busy))
        job.failed.connect(lambda *_: self._spinner.stop(*busy))
        job.done.connect(done)
        job.failed.connect(failed)
        job.finished.connect(lambda: self._job_ended(job))
        self._jobs.append(job)
        self.shell.set_busy(True)
        job.start()
        return job

    def _job_ended(self, job: Job) -> None:
        if job in self._jobs:
            self._jobs.remove(job)
        self.shell.set_busy(bool(self._jobs))

    def run_checks(self) -> None:
        serial = self.device_combo.currentData()
        self.setup_status.setText(tr("checking…"))
        self.check_button.setEnabled(False)
        self._start_job(lambda: self._checks(serial), self._show_checks, self._setup_failed,
                        busy=(self.check_button,))

    def _show_checks(self, results) -> None:
        self.health.set_checks(results)
        if getattr(self, "_wizard", None) is not None:
            self._wizard.show_checks(results)

    def run_fix(self, action: str) -> None:
        serial = self.device_combo.currentData()
        if not serial:
            return
        self.setup_status.setText(tr("working… (LDPlayer can take a minute to start)"))
        for b in (self.check_button, self.launch_button, self.resize_button):
            b.setEnabled(False)

        def after(_ok) -> None:
            self.refresh_devices()
            self.run_checks()

        busy = self.launch_button if action == "launch" else self.resize_button
        self._start_job(lambda: self._fixer(action, serial), after, self._setup_failed, busy=(busy,))

    def _setup_failed(self, message: str) -> None:
        self.setup_status.setText(tr("error: {message}", message=message))
        self.check_button.setEnabled(True)

    def grab_preview(self) -> None:
        serial = self.device_combo.currentData()
        if not serial:
            return
        self.grab_button.setEnabled(False)

        def shown(result) -> None:
            self.show_preview(*result)
            self.grab_button.setEnabled(self._worker is None or not self._worker.isRunning())

        def failed(message: str) -> None:
            self.dashboard.preview_failed(message)
            self.grab_button.setEnabled(True)

        self._start_job(lambda: self._grab(serial), shown, failed, busy=(self.grab_button,))

    def show_preview(self, bgr: np.ndarray, screen: str) -> None:
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
        self.dashboard.set_preview(QPixmap.fromImage(img), screen)

    # --- settings -------------------------------------------------------------------------------

    def filter_config(self) -> FarmConfig:
        """farm.json as edited on the Automation and Safety pages (each owns its own fields)."""
        return replace(self.automation.config(), **self.safety.values(),
                       army_recipe=self.dashboard.army_recipe())

    def set_filter(self, cfg: FarmConfig) -> None:
        self.automation.set_config(cfg)
        self.safety.set_config(cfg)
        self.dashboard.set_army_recipe(cfg.army_recipe)
        self.dashboard.set_guardrails(cfg)

    def load_filter(self) -> None:
        self.set_filter(load_farm_config())

    def save_filter(self) -> None:
        cfg = self.filter_config()
        path = save_farm_config(cfg)
        self.automation.mark_saved(cfg)
        self.safety.mark_saved(cfg)
        self.dashboard.set_guardrails(self.filter_config())
        log.info("settings saved to %s", path)

    # --- history --------------------------------------------------------------------------------

    def load_history(self) -> None:
        self.history.set_rows(history.read(limit=20_000), str(history.history_path()))

    def export_history(self) -> None:
        src = history.history_path()
        if not src.exists():
            QMessageBox.information(self, "Clash of Bots", tr("No history yet."))
            return
        dest, _ = QFileDialog.getSaveFileName(self, tr("Export history"), "clash-of-bots-history.csv",
                                              "CSV (*.csv)")
        if dest:
            shutil.copyfile(src, dest)
            log.info("history exported to %s", dest)

    # --- run ------------------------------------------------------------------------------------

    def start(self) -> None:
        serial = self.device_combo.currentData()
        if not serial:
            QMessageBox.warning(self, "Clash of Bots",
                                tr("Pick a device first (top bar; Devices page to connect)."))
            return
        cfg = self.filter_config()
        save_farm_config(cfg)
        limits = farm_limits(cfg, self.cycles_spin.value(), float(self.minutes_spin.value()))
        self._cycles = []
        self._max_cycles = self.cycles_spin.value()
        self._show_stats(FarmStats())
        mode = self._mode = self.dashboard.mode.value()
        self._worker = FarmWorker(lambda: self._build(serial, cfg), limits, self, mode=mode)
        self._worker.cycle_done.connect(self.on_cycle)
        self._worker.resting.connect(self.on_break)
        self._worker.preview.connect(self.show_preview)
        self._worker.step.connect(self.dashboard.set_step)
        self._worker.finished_stats.connect(self.on_finished)
        self._worker.failed.connect(self.on_failed)
        self._worker.finished.connect(lambda: self._set_running(False))
        self._set_running(True)
        what = "Builder Base attacks" if mode == "bb" else "farming"
        self.shell.reset_session()
        name = self.device_combo.currentText()
        self._set_status(tr("Builder Base attacks on {serial}", serial=name) if mode == "bb"
                         else tr("farming on {serial}", serial=name), "running")
        log.info("%s on %s: %s, %s", what, serial, cfg, limits)
        self._worker.start()

    def toggle_pause(self) -> None:
        """#133: Pause holds the run after the current cycle (never mid-battle); Resume carries on."""
        if self._worker is None or not self._worker.isRunning():
            return
        paused = not self._worker.is_paused()
        self._worker.set_paused(paused)
        self.dashboard.set_paused(paused)
        if paused:
            self._set_status(tr("pausing after the current cycle…"), icon_name="info")
            self.shell.set_state("break", tr("Paused"))
        else:
            self._set_status(tr("resumed"), "running")

    def stop(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._set_status(tr("stopping after the current step…"))
            self._worker.request_stop()

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.dashboard.set_running(running)
        self.refresh_button.setEnabled(not running and self._refresh_job is None)
        for w in (self.device_combo, self.save_button, self.defaults_button,
                  self.check_button, *self.filter_spins.values(), *self.safety.spins.values()):
            w.setEnabled(not running)
        if running:
            self.launch_button.setEnabled(False)
            self.resize_button.setEnabled(False)
        if self.tray is not None:
            self.tray_stop.setEnabled(running)
        if running:
            self.shell.set_state("running")
        elif self.shell.state_pill.state in ("running", "break"):
            self.shell.set_state("idle")

    # --- signals from the worker ----------------------------------------------------------------

    def on_cycle(self, cycle: CycleResult) -> None:
        self._cycles.append(cycle)
        self._show_stats(FarmStats(cycles=list(self._cycles)))
        self._set_status(tr("farming"), "running")
        self.dashboard.set_last_cycle(cycle)
        self.history.add_row(history.to_row(cycle, mode=self._mode))

    def on_break(self, seconds: float) -> None:
        until = QTime.currentTime().addSecs(int(seconds)).toString("HH:mm")
        self._set_status(tr("on a break until {until} ({minutes} min)", until=until,
                            minutes=f"{seconds / 60:.1f}"), "break")
        self._notify(tr("Break"), tr("Resting until {until}", until=until), "break")

    def on_finished(self, stats: FarmStats) -> None:
        self._show_stats(stats)
        # A user stop or a reached limit is a normal end; anything else is a safety stop.
        normal = stats.stop_reason == "stopped" or stats.stop_reason.endswith(("cycles done", "min elapsed"))
        self._set_status(tr("stopped: {reason}", reason=stats.stop_reason), "idle" if normal else "stopped",
                         "info")
        self.dashboard.set_step(None)
        if not normal:
            self.dashboard.show_safety_stop(stats.stop_reason)
        g = stats.gained
        self._notify(tr("Farming stopped"),
                     tr("{reason}\n{attacks} attacks, gold {gold}", reason=stats.stop_reason,
                        attacks=stats.attacks, gold=f"{g.gold:+,}"),
                     "finished" if normal else "safety")

    def on_failed(self, message: str) -> None:
        self._set_status(tr("error: {message}", message=message), "stopped", "gpp_maybe")
        self.dashboard.show_error(message)
        self._notify(tr("Farming failed"), message)
        QMessageBox.critical(self, "Clash of Bots", tr("Farming stopped:\n{message}", message=message))

    def _show_stats(self, stats: FarmStats) -> None:
        self.dashboard.set_stats(stats, getattr(self, "_max_cycles", 0))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API name)
        if self._worker is not None and self._worker.isRunning():
            answer = QMessageBox.question(self, "Clash of Bots", tr("Farming is running. Stop it and quit?"))
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.request_stop()
            self._worker.wait(60_000)
        for job in list(self._jobs):
            job.wait(5_000)
        if self.tray is not None:
            self.tray.hide()
        event.accept()
