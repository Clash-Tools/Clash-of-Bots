"""Health checks (#100): everything the bot needs on the device picked in the top bar, with the fixes
it offers (start LDPlayer, set its resolution). Moved off the Devices page into its own rail tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from cob.core.i18n import tr
from cob.ui.pages.devices import short_serial
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Card, IconLabel
from cob.ui.widgets import label as text


class HealthPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("DEVICE READINESS"), "eyebrowAccent"))
        titles.addWidget(text(tr("Health checks"), "headline"))
        titles.addWidget(text(tr("Everything the bot needs on the device picked in the top bar."), "muted"))
        head.addLayout(titles, 1)
        self.check_button = QPushButton("  " + tr("Run checks"), objectName="primary")
        self.check_button.setIcon(icon("verified", t.ON_PRIMARY_CONTAINER, 20))
        head.addWidget(self.check_button, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(t.LG)
        checks = Card(tr("Checks"), "verified_user")
        self.checked_device = text("", "mono")
        checks.header.addWidget(self.checked_device)
        self.check_grid = QGridLayout()
        self.check_grid.setHorizontalSpacing(t.MD)
        self.check_grid.setVerticalSpacing(t.SM + 2)
        checks.body.addLayout(self.check_grid)
        self.setup_status = text(tr("Press Run checks."), "muted", wrap=True)
        checks.body.addWidget(self.setup_status)
        cols.addWidget(checks, 7, Qt.AlignmentFlag.AlignTop)

        fixes = Card(tr("Fixes"), "construction")
        fixes.body.addWidget(text(tr("Offered when a check fails. LDPlayer only: phones get their screen set "
                                     "by the bot while it runs."), "muted", wrap=True))
        self.launch_button = QPushButton("  " + tr("Start LDPlayer"))
        self.launch_button.setIcon(icon("play_arrow", t.ON_SURFACE, 18))
        self.resize_button = QPushButton("  " + tr("Fix resolution (restarts LDPlayer)"))
        self.resize_button.setIcon(icon("crop_free", t.ON_SURFACE, 18))
        for b in (self.launch_button, self.resize_button):
            b.setEnabled(False)
            fixes.body.addWidget(b)
        cols.addWidget(fixes, 5, Qt.AlignmentFlag.AlignTop)
        root.addLayout(cols)
        root.addStretch(1)

    def set_device(self, serial: str | None) -> None:
        self.checked_device.setText(short_serial(serial) if serial else tr("no device"))
        self.checked_device.setToolTip(serial or "")

    def set_checks(self, results) -> set[str]:
        """Rows of OK / FIX + name + detail; returns the fixes the failed checks offer."""
        while self.check_grid.count():
            self.check_grid.takeAt(0).widget().deleteLater()
        fixes = set()
        for i, c in enumerate(results):
            mark = IconLabel("check_circle" if c.ok else "error", 20, t.PRIMARY if c.ok else t.ERROR,
                             filled=True)
            self.check_grid.addWidget(mark, i, 0, Qt.AlignmentFlag.AlignTop)
            name = text(c.name)
            name.setStyleSheet("font-weight: 600;")
            self.check_grid.addWidget(name, i, 1, Qt.AlignmentFlag.AlignTop)
            self.check_grid.addWidget(text(c.detail, "muted", wrap=True), i, 2)
            if not c.ok and c.fix:
                fixes.add(c.fix)
        self.check_grid.setColumnStretch(2, 1)
        all_ok = bool(results) and all(c.ok for c in results)
        self.setup_status.setText(tr("Ready to farm.") if all_ok
                                  else tr("Fix the red items, then run the checks again."))
        self.launch_button.setEnabled("launch" in fixes)
        self.resize_button.setEnabled("resize" in fixes)
        self.check_button.setEnabled(True)
        return fixes
