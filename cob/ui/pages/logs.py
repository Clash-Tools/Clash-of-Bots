"""Logs (#66, design D8): live log with level chips, keyword/regex filter, follow tail, snapshot preview
for lines that saved a screenshot, and a sanitized diagnostics zip."""

from __future__ import annotations

import re
from collections import Counter, deque
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cob.core.i18n import tr
from cob.ui.log_bridge import LogLine
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Card, Chip, IconLabel
from cob.ui.widgets import label as text

MAX_LINES = 5000
LEVELS = ["ALL", "INFO", "WARNING", "ERROR"]
LEVEL_NAMES = {"ALL": tr("ALL"), "INFO": tr("INFO"), "WARNING": tr("WARN"), "ERROR": tr("ERROR")}  # chips
_COLORS = {"INFO": t.PRIMARY, "WARNING": t.TERTIARY, "ERROR": t.ERROR, "CRITICAL": t.ERROR,
           "DEBUG": t.OUTLINE}
_SNAPSHOT = re.compile(r"snapshot saved: (.+\.png)")


def matches(line: LogLine, level: str, pattern: str) -> bool:
    """Level chip + search box. The search is a case-insensitive regex; invalid regex = plain text."""
    if level != "ALL" and not (line.level == level or (level == "ERROR" and line.level == "CRITICAL")):
        return False
    if not pattern:
        return True
    hay = line.text()
    try:
        return re.search(pattern, hay, re.IGNORECASE) is not None
    except re.error:
        return pattern.lower() in hay.lower()


class LogsPage(QWidget):
    save_diagnostics = Signal()
    export_reports = Signal()  # #170: zip of the failure reports, screenshots included

    def __init__(self, log_folder: Path | None = None, session_file: Path | None = None):
        super().__init__()
        self._lines: deque[LogLine] = deque(maxlen=MAX_LINES)
        self._counts: Counter[str] = Counter()
        self._folder = log_folder
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)

        head = Card(tone="low", header=True)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("System & Operational Logs"), "headline"))
        self.session = text(tr("This session: {path}", path=session_file) if session_file
                            else tr("Session log: not started"), "muted")
        self.session.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        titles.addWidget(self.session)
        head.header.insertLayout(0, titles, 1)
        self.copy_button = QPushButton("  " + tr("Copy visible"))
        self.copy_button.setIcon(icon("content_copy", t.ON_SURFACE, 18))
        self.copy_button.clicked.connect(self.copy_visible)
        self.open_button = QPushButton("  " + tr("Open folder"))
        self.open_button.setIcon(icon("folder_open", t.ON_SURFACE, 18))
        self.open_button.clicked.connect(self.open_folder)
        self.diag_button = QPushButton("  " + tr("Save diagnostics"))
        self.diag_button.setObjectName("tonal")
        self.diag_button.setIcon(icon("verified_user", t.ON_SURFACE, 18))
        self.diag_button.setToolTip(tr("Zip of the session logs and settings. IP addresses, phone serials, "
                                       "your user name and home folder are removed. Screenshots are not "
                                       "included."))
        self.diag_button.clicked.connect(self.save_diagnostics)
        self.reports_button = QPushButton("  " + tr("Export failure reports"))
        self.reports_button.setObjectName("tonal")
        self.reports_button.setIcon(icon("bug_report", t.ON_SURFACE, 18))
        self.reports_button.setToolTip(tr("Zip of every failure report: the screen when it failed, the base "
                                          "outline the attack used and the log lines before it. Screenshots "
                                          "show player and clan names; IP addresses and serials are removed "
                                          "from the text."))
        self.reports_button.clicked.connect(self.export_reports)
        for b in (self.copy_button, self.open_button, self.diag_button, self.reports_button):
            head.header.addWidget(b)
        root.addWidget(head)

        filters = QHBoxLayout()
        self.search = QLineEdit(placeholderText=tr("Filter by keyword or regex…  (Ctrl+F)"))
        self.search.addAction(icon("search", t.ON_SURFACE_VARIANT, 18),
                              QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.refilter)
        filters.addWidget(self.search, 1)
        self.level_group = QButtonGroup(self)
        self.chips: dict[str, Chip] = {}
        for lvl in LEVELS:
            chip = Chip(LEVEL_NAMES[lvl], checkable=True)
            chip.setChecked(lvl == "ALL")
            self.level_group.addButton(chip)
            chip.clicked.connect(self.refilter)
            self.chips[lvl] = chip
            filters.addWidget(chip)
        self.follow = QCheckBox(tr("Follow tail"))
        self.follow.setChecked(True)
        filters.addWidget(self.follow)
        root.addLayout(filters)

        well = Card(tone="true", padding=t.MD)
        self.view = QListWidget()
        font = QFont(t.FONT_MONO)
        font.setPixelSize(12)
        self.view.setFont(font)
        self.view.setMinimumHeight(420)
        self.view.setUniformItemSizes(True)
        # The app stylesheet sets Inter on every QWidget: the mono font has to be set here too.
        self.view.setStyleSheet(f"QListWidget {{ background: {t.SURFACE_LOWEST}; border: none; "
                                f"font-family: '{t.FONT_MONO}'; font-size: 12px; "
                                f"border-radius: {t.RADIUS}px; padding: 6px; }} "
                                f"QListWidget::item:selected {{ background: {t.SECONDARY_CONTAINER}; }}")
        self.view.currentItemChanged.connect(self._selected)
        well.body.addWidget(self.view)
        self.detail = QWidget()
        d = QHBoxLayout(self.detail)
        d.setContentsMargins(0, 0, 0, 0)
        self.thumb = QLabel()
        self.thumb.setFixedSize(288, 162)
        self.thumb.setStyleSheet(f"background: {t.SURFACE_LOWEST}; border-radius: {t.RADIUS}px;")
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.addWidget(self.thumb)
        info = QVBoxLayout()
        self.detail_title = text(tr("Snapshot"), "title")
        self.detail_path = text("", "mono", wrap=True)
        self.detail_open = QPushButton("  " + tr("Full image"))
        self.detail_open.setIcon(icon("zoom_in", t.ON_SURFACE, 18))
        self.detail_open.clicked.connect(self._open_snapshot)
        info.addWidget(self.detail_title)
        info.addWidget(self.detail_path)
        info.addWidget(self.detail_open, 0, Qt.AlignmentFlag.AlignLeft)
        info.addStretch(1)
        d.addLayout(info, 1)
        self.detail.hide()
        well.body.addWidget(self.detail)
        root.addWidget(well)

        foot = QHBoxLayout()
        foot.addWidget(IconLabel("list_alt", 16, t.ON_SURFACE_VARIANT))
        self.footer = text("", "muted")
        foot.addWidget(self.footer, 1)
        self.wrap = QCheckBox(tr("Wrap lines"))
        self.wrap.toggled.connect(lambda on: self.view.setWordWrap(on))
        foot.addWidget(self.wrap)
        clear = QPushButton("  " + tr("Clear view"))
        clear.setObjectName("text")
        clear.setIcon(icon("delete_sweep", t.PRIMARY, 18))
        clear.clicked.connect(self.clear)
        foot.addWidget(clear)
        root.addLayout(foot)
        self._update_footer()

    # --- data -----------------------------------------------------------------------------------

    def level(self) -> str:
        return next(lvl for lvl, chip in self.chips.items() if chip.isChecked())

    def add(self, line: LogLine) -> None:
        if len(self._lines) == MAX_LINES:  # oldest line drops out of the deque and the view
            self.view.takeItem(0)
        self._lines.append(line)
        self._counts[line.level] += 1
        item = self._item(line)
        self.view.addItem(item)
        item.setHidden(not matches(line, self.level(), self.search.text()))
        if self.follow.isChecked() and not item.isHidden():
            self.view.scrollToBottom()
        self._update_footer()

    def _item(self, line: LogLine) -> QListWidgetItem:
        level = {"WARNING": "WARN", "CRITICAL": "CRIT"}.get(line.level, line.level)
        item = QListWidgetItem(f"{line.time}  {level:<5}  [{line.module}]  {line.message}")
        item.setForeground(QColor(_COLORS.get(line.level, t.ON_SURFACE)) if line.level != "INFO"
                           else QColor(t.ON_SURFACE))
        item.setData(Qt.ItemDataRole.UserRole, line)
        return item

    def refilter(self, *_args) -> None:
        level, pattern = self.level(), self.search.text()
        for i in range(self.view.count()):
            item = self.view.item(i)
            item.setHidden(not matches(item.data(Qt.ItemDataRole.UserRole), level, pattern))
        if self.follow.isChecked():
            self.view.scrollToBottom()
        self._update_footer()

    def visible_lines(self) -> list[LogLine]:
        return [self.view.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.view.count())
                if not self.view.item(i).isHidden()]

    def _update_footer(self) -> None:
        for lvl, chip in self.chips.items():
            n = len(self._lines) if lvl == "ALL" else self._counts[lvl] + (self._counts["CRITICAL"]
                                                                           if lvl == "ERROR" else 0)
            chip.setText(f"{LEVEL_NAMES[lvl]}  {n}")
        shown = sum(1 for i in range(self.view.count()) if not self.view.item(i).isHidden())
        self.footer.setText(tr("Showing {shown} lines (of {total} this session, newest {kept} kept)",
                               shown=shown, total=len(self._lines), kept=MAX_LINES))

    def clear(self) -> None:
        self.view.clear()
        self._lines.clear()
        self._counts.clear()
        self.detail.hide()
        self._update_footer()

    def copy_visible(self) -> None:
        QGuiApplication.clipboard().setText("\n".join(line.text() for line in self.visible_lines()))

    def open_folder(self) -> None:
        if self._folder is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._folder)))

    def _selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        line: LogLine | None = item.data(Qt.ItemDataRole.UserRole) if item else None
        m = _SNAPSHOT.search(line.message) if line else None
        path = Path(m.group(1)) if m else None
        if path is None or not path.is_file():
            self.detail.hide()
            return
        self._snapshot = path
        pm = QPixmap(str(path))
        self.thumb.setPixmap(pm.scaled(self.thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
        self.detail_title.setText(tr("Snapshot  •  {time}", time=line.time))
        self.detail_path.setText(str(path))
        self.detail.show()

    def _open_snapshot(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._snapshot)))
