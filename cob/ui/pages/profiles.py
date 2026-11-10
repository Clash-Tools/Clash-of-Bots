"""Profiles page (#2): accounts / devices with their own farm settings, and running them in turn.

Each profile has a name, the device it farms on, an optional player tag (Clash of Clans API sync) and
whether it takes part in "Run profiles in turn". The Automation and Safety pages edit the active
profile's settings; the top bar switches the active profile.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cob.core.i18n import tr
from cob.core.profiles import DEFAULT_ID, MAX_NAME, Profile, Profiles, normalize_tag
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Card
from cob.ui.widgets import label as text


def shown(p: Profile) -> str:
    """The name to show: the untouched Default profile is called "Default" in the UI language."""
    return tr("Default") if p.id == DEFAULT_ID and p.name == "Default" else p.name


def _ask_name(parent: QWidget, title: str, default: str) -> str | None:
    name, ok = QInputDialog.getText(parent, title, tr("Profile name:"), QLineEdit.EchoMode.Normal, default)
    return name.strip() if ok and name.strip() else None


def _confirm_delete(parent: QWidget, name: str) -> bool:
    answer = QMessageBox.question(parent, "Clash of Bots",
                                  tr("Delete the profile '{name}' and its settings? Its history rows stay.",
                                     name=name))
    return answer == QMessageBox.StandardButton.Yes


class ProfilesPage(QWidget):
    changed = Signal()  # profiles added, removed, renamed or edited: the top bar lists them again
    use_requested = Signal(str)  # profile id to make active
    rotation_requested = Signal()
    sync_requested = Signal(str)  # profile id: fetch its player from the Clash of Clans API (D-035)

    def __init__(self, store: Profiles, ask_name=_ask_name, confirm_delete=_confirm_delete):
        super().__init__()
        self.store = store
        self._ask_name, self._confirm_delete = ask_name, confirm_delete
        self._devices: list[tuple[str, str]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)

        head = Card(tone="low", header=True)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("Profiles"), "headline"))
        self.summary = text("", "muted", wrap=True)
        titles.addWidget(self.summary)
        head.header.insertLayout(0, titles, 1)
        self.new_button = QPushButton("  " + tr("New"))
        self.new_button.setIcon(icon("person", t.ON_SURFACE, 18))
        self.new_button.clicked.connect(self.new_profile)
        self.copy_button = QPushButton("  " + tr("Duplicate"))
        self.copy_button.setIcon(icon("content_copy", t.ON_SURFACE, 18))
        self.copy_button.clicked.connect(self.duplicate)
        self.delete_button = QPushButton("  " + tr("Delete"))
        self.delete_button.setIcon(icon("delete_sweep", t.ON_SURFACE, 18))
        self.delete_button.clicked.connect(self.delete)
        for b in (self.new_button, self.copy_button, self.delete_button):
            head.header.addWidget(b)
        root.addWidget(head)

        body = QHBoxLayout()
        body.setSpacing(t.LG)
        listing = Card(tr("Your profiles"), "format_list_bulleted")
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._selected)
        listing.body.addWidget(self.list)
        body.addWidget(listing, 2)

        form_card = Card(tr("Profile"), "person")
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setMaxLength(MAX_NAME)
        self.device = QComboBox()
        self.device.setToolTip(tr("The device this profile farms on. LDPlayer instances are started when "
                                  "their turn comes."))
        self.tag = QLineEdit()
        self.tag.setPlaceholderText("#ABC123")
        self.tag.setToolTip(tr("Your player tag (Profile in the game). Used by the Clash of Clans API sync; "
                               "optional."))
        self.rotation = QCheckBox(tr("Run in turn with the other profiles"))
        form.addRow(tr("Name"), self.name)
        form.addRow(tr("Device"), self.device)
        form.addRow(tr("Player tag"), self.tag)
        form.addRow("", self.rotation)
        form_card.body.addLayout(form)
        self.form_status = text("", "muted", wrap=True)
        form_card.body.addWidget(self.form_status)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("  " + tr("Save profile"))
        self.save_button.setObjectName("tonal")
        self.save_button.setIcon(icon("check", t.ON_SURFACE, 18))
        self.save_button.clicked.connect(self.save)
        self.use_button = QPushButton("  " + tr("Use this profile"))
        self.use_button.setIcon(icon("done", t.ON_SURFACE, 18))
        self.use_button.clicked.connect(self.use)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.use_button)
        form_card.body.addLayout(buttons)

        self.api_title = text(tr("CLASH OF CLANS ACCOUNT"), "eyebrow")
        form_card.body.addWidget(self.api_title)
        self.player = text("", "muted", wrap=True)
        self.player.setTextFormat(Qt.TextFormat.PlainText)
        form_card.body.addWidget(self.player)
        self.sync_button = QPushButton("  " + tr("Sync from Clash of Clans"))
        self.sync_button.setIcon(icon("refresh", t.ON_SURFACE, 18))
        self.sync_button.setToolTip(tr("Reads this profile's troops, spells, heroes and equipment from the "
                                       "official Clash of Clans API (API key in Settings)."))
        self.sync_button.clicked.connect(self.request_sync)
        form_card.body.addWidget(self.sync_button, 0, Qt.AlignmentFlag.AlignLeft)
        form_card.body.addStretch(1)
        body.addWidget(form_card, 3)
        root.addLayout(body, 1)

        turn = Card(tr("Run profiles in turn"), "format_list_numbered")
        turn.body.addWidget(text(tr(
            "Farms each ticked profile with its own settings, one after another, until its run limits "
            "(Dashboard) or a safety rule stop it; then the next one starts. Stop ends the whole turn. "
            "Give every profile its own device (an LDPlayer instance each): the bot never signs in to or "
            "switches Supercell ID accounts."), "muted", wrap=True))
        row = QHBoxLayout()
        self.turn_label = text("", "muted")
        self.run_button = QPushButton("  " + tr("Run in turn"))
        self.run_button.setObjectName("primary")
        self.run_button.setIcon(icon("play_arrow", t.ON_PRIMARY_CONTAINER, 18, filled=True))
        self.run_button.clicked.connect(self.rotation_requested)
        row.addWidget(self.turn_label, 1)
        row.addWidget(self.run_button)
        turn.body.addLayout(row)
        root.addWidget(turn)
        self.turn_card = turn
        self._apply_flags(form)
        self.refresh()

    def _apply_flags(self, form) -> None:
        """D-038: running in turn and the Clash of Clans API sync are experimental."""
        from cob.core import flags

        self.rotation_enabled = flags.enabled("profile_rotation")
        self.api_enabled = flags.enabled("coc_api_sync")
        self.turn_card.setVisible(self.rotation_enabled)
        self.rotation.setVisible(self.rotation_enabled)
        for w in (self.tag, self.api_title, self.player, self.sync_button):
            w.setVisible(self.api_enabled)
        if (label := form.labelForField(self.tag)) is not None:
            label.setVisible(self.api_enabled)

    # --- data -----------------------------------------------------------------------------------

    def set_devices(self, devices: list[tuple[str, str]]) -> None:
        """(label, serial) from the top bar's device list."""
        self._devices = [(label, serial) for label, serial in devices if serial]
        self._fill_devices(self._current())

    def refresh(self, select: str | None = None) -> None:
        keep = select or (self._current().id if self._current() else self.store.active_id)
        self.list.blockSignals(True)
        self.list.clear()
        for p in self.store.profiles:
            marks = []
            if p.id == self.store.active_id:
                marks.append(tr("active"))
            if p.rotation:
                marks.append(tr("in turn"))
            item = QListWidgetItem(shown(p) + (f"   ({', '.join(marks)})" if marks else ""))
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.list.addItem(item)
            if p.id == keep:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._selected(self.list.currentItem())
        turn = self.store.rotation()
        self.summary.setText(tr("{count} profiles  •  active: {name}", count=len(self.store.profiles),
                                name=shown(self.store.active)))
        self.turn_label.setText(", ".join(shown(p) for p in turn) if turn else tr("No profile ticked yet."))
        self.run_button.setEnabled(bool(turn))

    def _current(self) -> Profile | None:
        item = self.list.currentItem()
        return self.store.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _fill_devices(self, p: Profile | None) -> None:
        self.device.clear()
        self.device.addItem(tr("Device picked in the top bar"), "")
        for label, serial in self._devices:
            self.device.addItem(label, serial)
        if p is not None and p.serial:
            if (i := self.device.findData(p.serial)) < 0:  # not connected now: keep showing it
                self.device.addItem(tr("{serial} (not found now)", serial=p.serial), p.serial)
                i = self.device.count() - 1
            self.device.setCurrentIndex(i)

    def _selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        p = self._current() if item is not None else None
        for w in (self.name, self.device, self.tag, self.rotation, self.save_button, self.use_button,
                  self.copy_button, self.sync_button):
            w.setEnabled(p is not None)
        self.delete_button.setEnabled(p is not None and p.id != DEFAULT_ID)
        self.form_status.setText("")
        if p is None:
            return
        self.name.setText(shown(p))
        self.tag.setText(p.player_tag)
        self.rotation.setChecked(p.rotation)
        self._fill_devices(p)
        self.use_button.setEnabled(p.id != self.store.active_id)
        self.show_player(self._cached(p.id))

    def _cached(self, profile_id: str):
        from cob import units
        from cob.core.coc_api import load_cached

        return load_cached(self.store.player_path(profile_id), units.load())

    def show_player(self, player) -> None:
        """The profile's last sync (coc_api.Player), or how to get one."""
        p = self._current()
        if player is None:
            self.player.setText(tr("Not synced yet. Set the player tag, save, then Sync.") if p and not
                                p.player_tag else tr("Not synced yet."))
            return
        lines = [tr("{name} {tag}  •  Town Hall {th}  •  {trophies} trophies", name=player.name,
                    tag=player.tag, th=player.town_hall, trophies=f"{player.trophies:,}")]
        heroes = player.heroes()
        if heroes:
            lines.append(", ".join(f"{h.name} {h.level}" for h in heroes))
        home = player.owned("home")
        kinds = {"troops": 0, "spells": 0}
        for u in home.values():
            if u.group in kinds:
                kinds[u.group] += 1
        maxed = sum(u.maxed for u in home.values())
        lines.append(tr("{troops} troops, {spells} spells, {equipment} hero equipment; {maxed} at max level",
                        troops=kinds["troops"], spells=kinds["spells"], equipment=len(player.equipment()),
                        maxed=maxed))
        when = (time.strftime("%Y-%m-%d %H:%M", time.localtime(player.fetched_at)) if player.fetched_at
                else "-")
        lines.append(tr("Synced {when}", when=when))
        self.player.setText("\n".join(lines))

    def show_sync_error(self, message: str) -> None:
        self.player.setText(message)

    def request_sync(self) -> None:
        p = self._current()
        if p is None:
            return
        if not p.player_tag:
            self.player.setText(tr("Set the player tag and save the profile first."))
            return
        self.player.setText(tr("Syncing…"))
        self.sync_requested.emit(p.id)

    # --- actions --------------------------------------------------------------------------------

    def save(self) -> None:
        p = self._current()
        if p is None:
            return
        tag_text = self.tag.text().strip()
        tag = normalize_tag(tag_text)
        if tag_text and not tag:
            self.form_status.setText(tr("That is not a player tag (letters and digits after #, "
                                        "e.g. #2PQ8Y0L)."))
            return
        saved = self.store.update(Profile(p.id, self.name.text(), self.device.currentData() or "", tag,
                                          self.rotation.isChecked()))
        self.refresh(saved.id)
        self.form_status.setText(tr("Saved."))
        self.changed.emit()

    def use(self) -> None:
        p = self._current()
        if p is not None:
            self.use_requested.emit(p.id)

    def new_profile(self) -> None:
        self._add(None, tr("New profile"))

    def duplicate(self) -> None:
        p = self._current()
        if p is not None:
            self._add(p.id, tr("{name} copy", name=shown(p)))

    def _add(self, copy_from: str | None, default: str) -> None:
        name = self._ask_name(self, tr("New profile"), default)
        if not name:
            return
        try:
            p = self.store.add(name, copy_from)
        except ValueError as exc:
            self.form_status.setText(str(exc))
            return
        self.refresh(p.id)
        self.changed.emit()

    def delete(self) -> None:
        p = self._current()
        if p is None or p.id == DEFAULT_ID or not self._confirm_delete(self, shown(p)):
            return
        self.store.remove(p.id)
        self.refresh(self.store.active_id)
        self.changed.emit()
