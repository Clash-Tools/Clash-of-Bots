"""Cards page (troop detection): label the troop-bar cards the bot saw but does not know yet.

Each battle saves pictures of unrecognised cards. Pick the unit for a picture once and the bot recognises
that card from the next battle on; Export writes the labelled pictures for the clash-of-bots-data
repository so every user gets them.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cob.core.i18n import tr
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Card
from cob.ui.widgets import label as text

KIND_NAMES = {"troop": tr("Troop"), "super_troop": tr("Super troop"), "event_troop": tr("Event troop"),
              "siege": tr("Siege machine"), "hero": tr("Hero"), "pet": tr("Pet"), "spell": tr("Spell"),
              "event_spell": tr("Event spell")}
GUESS = {"troop": ("troop", "super_troop", "event_troop"), "spell": ("spell", "event_spell"),
         "single": ("hero", "siege", "pet")}


class CardsPage(QWidget):
    export_requested = Signal()

    def __init__(self, library=None, db=None, owned=None):
        super().__init__()
        self.lib = library
        self.db = db
        # D-035: unit id -> coc_api.Owned of the active profile's last sync; owned units are listed first
        self._owned = owned or (lambda: {})
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)

        head = Card(tone="low", header=True)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("Troop Cards"), "headline"))
        self.summary = text("", "muted", wrap=True)
        titles.addWidget(self.summary)
        head.header.insertLayout(0, titles, 1)
        self.refresh_button = QPushButton("  " + tr("Refresh"))
        self.refresh_button.setIcon(icon("refresh", t.ON_SURFACE, 18))
        self.refresh_button.clicked.connect(self.refresh)
        self.open_button = QPushButton("  " + tr("Open folder"))
        self.open_button.setIcon(icon("folder_open", t.ON_SURFACE, 18))
        self.open_button.clicked.connect(self.open_folder)
        self.export_button = QPushButton("  " + tr("Export labelled"))
        self.export_button.setObjectName("tonal")
        self.export_button.setIcon(icon("file_upload", t.ON_SURFACE, 18))
        self.export_button.clicked.connect(self.export_requested)
        for b in (self.refresh_button, self.open_button, self.export_button):
            head.header.addWidget(b)
        root.addWidget(head)

        body = QHBoxLayout()
        body.setSpacing(t.LG)
        seen = Card(tr("Not recognised yet"), "visibility")
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(166, 86))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setSpacing(t.SM)
        self.grid.currentItemChanged.connect(self._selected)
        seen.body.addWidget(self.grid)
        body.addWidget(seen, 3)

        form = Card(tr("Label this card"), "sell")
        self.preview = text("", "muted")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(100)
        form.body.addWidget(self.preview)
        self.guess = text("", "muted", wrap=True)
        form.body.addWidget(self.guess)
        self.unit = QComboBox()
        self.unit.setEditable(True)
        self.unit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.unit.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.unit.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        form.body.addWidget(self.unit)
        buttons = QHBoxLayout()
        self.label_button = QPushButton("  " + tr("Save label"))
        self.label_button.setIcon(icon("check", t.ON_SURFACE, 18))
        self.label_button.clicked.connect(self.save_label)
        self.discard_button = QPushButton("  " + tr("Discard"))
        self.discard_button.setIcon(icon("delete_sweep", t.ON_SURFACE, 18))
        self.discard_button.clicked.connect(self.discard)
        buttons.addWidget(self.label_button)
        buttons.addWidget(self.discard_button)
        form.body.addLayout(buttons)
        form.body.addWidget(text(tr("Pick the unit shown on the card. The bot recognises it from the next "
                                    "battle on; Export shares your labels with the unit database."),
                                 "muted", wrap=True))
        form.body.addStretch(1)
        body.addWidget(form, 2)
        root.addLayout(body, 1)
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt)
        super().showEvent(event)
        self.refresh()  # pictures saved by a battle since the page was last open

    # --- data -----------------------------------------------------------------------------------

    def _ensure(self) -> None:
        if self.lib is None:
            from cob.attack.cards import library

            self.lib = library()
        if self.db is None:
            from cob import units

            self.db = units.load()

    def refresh(self) -> None:
        self._ensure()
        self.lib.reload()
        self.grid.clear()
        for path in self.lib.unknown():
            item = QListWidgetItem(QIcon(QPixmap(str(path))), "")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(self._kind_guess(path) or path.name)
            self.grid.addItem(item)
        labelled = len(list(self.lib.labelled_dir.glob("*.png"))) if self.lib.labelled_dir.exists() else 0
        pictures = sum(len(u.cards) for u in self.db.units.values())
        self.summary.setText(tr("{unknown} not recognised  •  {labelled} labelled by you  •  unit database "
                                "{version} ({pictures} pictures)", unknown=self.grid.count(),
                                labelled=labelled, version=self.db.version, pictures=pictures))
        self.export_button.setEnabled(labelled > 0)
        if self.grid.count():
            self.grid.setCurrentRow(0)
        else:
            self._selected(None)

    def _kind_guess(self, path: Path) -> str:
        try:
            return json.loads(path.with_suffix(".json").read_text("utf-8")).get("kind_guess", "")
        except (OSError, ValueError):
            return ""

    def _selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        has = item is not None
        for w in (self.unit, self.label_button, self.discard_button):
            w.setEnabled(has)
        if not has:
            self.preview.setText(tr("Nothing to label. Cards the bot does not know show up here after a "
                                    "battle."))
            self.guess.setText("")
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.preview.setPixmap(QPixmap(str(path)).scaled(249, 129, Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation))
        guess = self._kind_guess(path)
        kinds = GUESS.get(guess, ())
        self.guess.setText(tr("Bar read it as: {kind}", kind=guess) if guess else "")
        self._fill_units(kinds)

    def _fill_units(self, first_kinds: tuple[str, ...]) -> None:
        try:
            owned = self._owned() or {}
        except Exception:  # a broken sync file must not break labelling
            owned = {}
        units = self.db.choices("home")
        # stable: likely kinds first, and within them the units this account has (clan castle troops may
        # still be others)
        units.sort(key=lambda u: (u.kind not in first_kinds, u.id not in owned))
        self.unit.clear()
        for u in units:
            mine = owned.get(u.id)
            extra = "  •  " + tr("yours, level {level}", level=mine.level) if mine else ""
            self.unit.addItem(f"{u.name}  ({KIND_NAMES.get(u.kind, u.kind)}){extra}", u.id)
        self.unit.setCurrentIndex(-1)
        self.unit.setEditText("")
        self.unit.lineEdit().setPlaceholderText(tr("Type or pick the unit…"))

    def _current_path(self) -> Path | None:
        item = self.grid.currentItem()
        return Path(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def save_label(self) -> None:
        path = self._current_path()
        unit_id = self.unit.currentData()
        if path is None or not unit_id:
            self.guess.setText(tr("Pick a unit from the list first."))
            return
        self.lib.label(path, unit_id)
        self.refresh()

    def discard(self) -> None:
        path = self._current_path()
        if path is not None:
            self.lib.discard(path)
            self.refresh()

    def open_folder(self) -> None:
        self._ensure()
        self.lib.folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.lib.folder)))
