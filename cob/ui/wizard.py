"""First-run setup wizard (#51, design D10): welcome, risk consent, target, connect, diagnostics.

The wizard drives the window's own actions (refresh devices, start LDPlayer, QR pairing, health checks)
through callbacks, so it adds no device code of its own. Fake handshake stats from the design (transport
speed, FPS, test ping) are left out."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cob.core.i18n import tr
from cob.ui.pages.devices import device_icon
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Banner, Card, IconLabel, StepPipeline
from cob.ui.widgets import label as text

LOCK_CHECK = "Phone unlocked"  # name used by cob.device.checks
STEPS = [("welcome", tr("Welcome"), "home"), ("risk", tr("Risk notice"), "gavel"),
         ("target", tr("Target"), "devices"), ("connect", tr("Connect"), "cable"),
         ("checks", tr("Diagnostics"), "verified")]
TARGETS = [("ldplayer", "desktop_windows", "LDPlayer 9 / 14", tr("Emulator on this PC. Recommended.")),
           ("usb", "usb", tr("Android phone (USB)"), tr("USB debugging on, cable plugged in.")),
           ("wifi", "wifi_tethering", tr("Android phone (Wi-Fi)"),
            tr("Pair by scanning a QR code (Android 11+)."))]


class _Choice(QPushButton):
    def __init__(self, icon_name: str, title: str, detail: str):
        super().__init__()
        self.setCheckable(True)
        self.setMinimumHeight(140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton {{ background: {t.SURFACE}; border: 2px solid transparent; border-radius: 12px; "
            f"text-align: left; padding: 12px; }} QPushButton:checked {{ border-color: {t.PRIMARY}; "
            f"background: {t.SURFACE_HIGH}; }}")
        lay = QVBoxLayout(self)
        lay.addWidget(IconLabel(icon_name, 28, t.PRIMARY))
        head = text(title)
        head.setStyleSheet("font-weight: 700; background: transparent;")
        lay.addWidget(head)
        lay.addWidget(text(detail, "muted", wrap=True))
        lay.addStretch(1)


class SetupWizard(QDialog):
    finished_setup = Signal()

    def __init__(self, parent: QWidget | None, devices: Callable[[], list[tuple[str, str]]],
                 refresh: Callable[[], None], use_device: Callable[[str], None],
                 launch_ldplayer: Callable[[], None], pair_qr: Callable[[], None],
                 run_checks: Callable[[], None], consented: bool = False):
        super().__init__(parent)
        self.setWindowTitle(tr("Clash of Bots setup"))
        self.setMinimumSize(900, 640)
        self._devices, self._refresh, self._use = devices, refresh, use_device
        self._launch, self._pair, self._run_checks = launch_ldplayer, pair_qr, run_checks
        self.setStyleSheet(f"QDialog {{ background: {t.SURFACE_LOW}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(t.XL, t.LG, t.XL, t.LG)
        root.setSpacing(t.LG)
        head = QHBoxLayout()
        head.addWidget(IconLabel("security", 28, t.PRIMARY, filled=True))
        titles = QVBoxLayout()
        titles.addWidget(text(tr("Initial Setup"), "headline"))
        titles.addWidget(text(tr("Five short steps to a working device."), "muted"))
        head.addLayout(titles, 1)
        head.addWidget(text("  " + tr("LOCAL ONLY"), "tag"), 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)
        self.stepper = StepPipeline(STEPS)
        root.addWidget(self.stepper)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("QStackedWidget { background: transparent; }")  # app QSS paints pages BG
        for build in (self._welcome, self._risk, self._target, self._connect, self._checks):
            self.pages.addWidget(build())
        root.addWidget(self.pages, 1)

        foot = QHBoxLayout()
        self.back = QPushButton("  " + tr("Previous step"))
        self.back.setIcon(icon("arrow_back", t.ON_SURFACE, 18))
        self.back.clicked.connect(lambda: self.go(self.pages.currentIndex() - 1))
        self.exit = QPushButton(tr("Exit wizard"))
        self.exit.setObjectName("text")
        self.exit.clicked.connect(self.reject)
        self.next = QPushButton("  " + tr("NEXT"), objectName="primary")
        self.next.setIcon(icon("arrow_forward", t.ON_PRIMARY_CONTAINER, 20))
        self.next.clicked.connect(self._next)
        foot.addWidget(self.back)
        foot.addStretch(1)
        foot.addWidget(self.exit)
        foot.addWidget(self.next)
        root.addLayout(foot)
        self.consent.setChecked(consented)
        self.go(0)

    # --- pages ----------------------------------------------------------------------------------

    def _welcome(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(text(tr("YOUR FARMING CO-PILOT"), "eyebrowAccent"))
        lay.addWidget(text(tr("Clash of Bots farms loot for you on an emulator or a phone"), "title"))
        lay.addWidget(text(tr("It reads the screen on this PC, attacks bases that meet your loot filter, "
                              "takes breaks and stops on its own safety rules."), "muted", wrap=True))
        cards = QHBoxLayout()
        for ic, title, detail in (
                ("shield", tr("Local only"), tr("No logins, no telemetry, no cloud.")),
                ("coffee", tr("Paced like a person"), tr("Breaks, daily limits, quiet hours.")),
                ("insights", tr("Loot first"), tr("Skips bases below your filter."))):
            c = Card(title, ic, tone="true", padding=t.MD)
            c.body.addWidget(text(detail, "muted", wrap=True))
            cards.addWidget(c)
        lay.addLayout(cards)
        lay.addStretch(1)
        return w

    def _risk(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(text(tr("Terms of service & account safety"), "title"))
        lay.addWidget(Banner("warning", tr("Automating the game breaks its terms of service"),
                             tr("Supercell can ban accounts that use bots. Use a test account first, keep "
                                "runs short and do not run the bot while you play on another device.")))
        self.consent = QCheckBox(tr("I understand the risk, take responsibility for my accounts and will "
                                    "start on a test account."))
        self.consent.toggled.connect(self._update_buttons)
        lay.addWidget(self.consent)
        lay.addStretch(1)
        return w

    def _target(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(text(tr("Where will the game run?"), "title"))
        row = QHBoxLayout()
        self.target_group = QButtonGroup(self)
        self.targets: dict[str, _Choice] = {}
        for key, ic, title, detail in TARGETS:
            c = _Choice(ic, title, detail)
            self.target_group.addButton(c)
            self.targets[key] = c
            row.addWidget(c)
        self.targets["ldplayer"].setChecked(True)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _connect(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.connect_title = text("", "title")
        self.connect_help = text("", "muted", wrap=True)
        lay.addWidget(self.connect_title)
        lay.addWidget(self.connect_help)
        actions = QHBoxLayout()
        self.refresh_button = QPushButton("  " + tr("Refresh devices"))
        self.refresh_button.setIcon(icon("refresh", t.ON_SURFACE, 18))
        self.refresh_button.clicked.connect(lambda: (self._refresh(), self._show_devices()))
        self.launch_button = QPushButton("  " + tr("Start LDPlayer"))
        self.launch_button.setIcon(icon("play_arrow", t.ON_SURFACE, 18))
        self.launch_button.clicked.connect(self._launch)
        self.qr_button = QPushButton("  " + tr("Scan QR code"))
        self.qr_button.setIcon(icon("phone_android", t.ON_SURFACE, 18))
        self.qr_button.clicked.connect(lambda: (self._pair(), self._show_devices()))
        for b in (self.refresh_button, self.launch_button, self.qr_button):
            actions.addWidget(b)
        actions.addStretch(1)
        lay.addLayout(actions)
        self.device_list = QVBoxLayout()
        self.device_list.setSpacing(t.SM)
        lay.addLayout(self.device_list)
        lay.addStretch(1)
        return w

    def _checks(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        head = QHBoxLayout()
        head.addWidget(text(tr("Pre-flight health check"), "title"), 1)
        rerun = QPushButton("  " + tr("Run checks"))
        rerun.setIcon(icon("refresh", t.ON_SURFACE, 18))
        rerun.clicked.connect(self._run_checks)
        head.addWidget(rerun)
        lay.addLayout(head)
        self.check_rows = QGridLayout()
        self.check_rows.setVerticalSpacing(t.SM)
        lay.addLayout(self.check_rows)
        self.check_summary = text(tr("Running checks…"), "muted", wrap=True)
        lay.addWidget(self.check_summary)
        lay.addStretch(1)
        return w

    # --- behaviour ------------------------------------------------------------------------------

    def target(self) -> str:
        return next(k for k, c in self.targets.items() if c.isChecked())

    def go(self, index: int) -> None:
        index = max(0, min(index, len(STEPS) - 1))
        self.pages.setCurrentIndex(index)
        self.stepper.set_active(STEPS[index][0])
        if STEPS[index][0] == "connect":
            self._prepare_connect()
        if STEPS[index][0] == "checks":
            self._run_checks()
        self._update_buttons()

    def _next(self) -> None:
        if self.pages.currentIndex() == len(STEPS) - 1:
            self.finished_setup.emit()
            self.accept()
        else:
            self.go(self.pages.currentIndex() + 1)

    def _update_buttons(self, *_args) -> None:
        i = self.pages.currentIndex()
        self.back.setEnabled(i > 0)
        last = i == len(STEPS) - 1
        self.next.setText("  " + (tr("GO TO DASHBOARD") if last else tr("NEXT")))
        blocked = STEPS[i][0] == "risk" and not self.consent.isChecked()
        blocked |= STEPS[i][0] == "connect" and not self._real_devices()
        self.next.setEnabled(not blocked)

    def _prepare_connect(self) -> None:
        target = self.target()
        title, help_ = {
            "ldplayer": (tr("Start LDPlayer"),
                         tr("Start the emulator (or press Start LDPlayer), turn on ADB debugging in LDPlayer "
                            "settings, then press Refresh devices.")),
            "usb": (tr("Plug in the phone"),
                    tr("Settings > Developer options > USB debugging on, allow this computer on the phone, "
                       "then press Refresh devices.")),
            "wifi": (tr("Pair over Wi-Fi"),
                     tr("Phone and PC on the same Wi-Fi. Press Scan QR code, then on the phone: Developer "
                        "options > Wireless debugging > Pair device with QR code.")),
        }[target]
        if target != "ldplayer":
            # Live (#81): the phone locked itself during setup and the first start was refused.
            help_ += " " + tr("Keep the phone unlocked with the screen on until setup is finished.")
        self.connect_title.setText(title)
        self.connect_help.setText(help_)
        self.launch_button.setVisible(target == "ldplayer")
        self.qr_button.setVisible(target == "wifi")
        self._show_devices()

    def _real_devices(self) -> list[tuple[str, str]]:
        return [(label, serial) for label, serial in self._devices() if serial]

    def _show_devices(self) -> None:
        while self.device_list.count():
            if w := self.device_list.takeAt(0).widget():
                w.hide()
                w.setParent(None)
        devices = self._real_devices()
        for label, serial in devices:
            row = QFrame()
            row.setStyleSheet(f"QFrame {{ background: {t.SURFACE}; border-radius: 12px; }}")
            r = QHBoxLayout(row)
            r.addWidget(IconLabel(device_icon(serial), 22, t.PRIMARY))
            r.addWidget(text(label), 1)
            use = QPushButton(tr("Use this device"))
            use.clicked.connect(lambda _=False, s=serial: self._pick(s))
            r.addWidget(use)
            self.device_list.addWidget(row)
        if not devices:
            self.device_list.addWidget(text(tr("No device found yet."), "muted"))
        self._update_buttons()

    def show_checks(self, results) -> None:
        while self.check_rows.count():
            if w := self.check_rows.takeAt(0).widget():
                w.setParent(None)
        for i, c in enumerate(results):
            self.check_rows.addWidget(IconLabel("check_circle" if c.ok else "error", 20,
                                                t.PRIMARY if c.ok else t.ERROR, filled=True), i, 0)
            name = text(c.name)
            name.setStyleSheet("font-weight: 600;")
            self.check_rows.addWidget(name, i, 1)
            self.check_rows.addWidget(text(c.detail, "muted", wrap=True), i, 2)
        ok = bool(results) and all(c.ok for c in results)
        passed = sum(c.ok for c in results)
        if any(c.name == LOCK_CHECK and not c.ok for c in results):
            self.check_summary.setText(tr("The phone locked itself: unlock it, keep the screen on, then "
                                          "press Run checks."))
            return
        self.check_summary.setText(
            tr("All {passed}/{total} checks passed. Ready to farm.", passed=passed, total=len(results)) if ok
            else tr("{passed}/{total} checks passed. The Devices page has the fixes; you can finish now and "
                    "fix them there.", passed=passed, total=len(results)))

    def _pick(self, serial: str) -> None:
        self._use(serial)
        self.go(self.pages.currentIndex() + 1)
