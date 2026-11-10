"""Settings / Preferences (#67, design D9): appearance, tray + notifications, data folder, config
export/import/reset, release channel and about. No update check over the network (CONSTRAINTS)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from cob import __version__
from cob.core import coc_api, i18n, notify, ui_settings
from cob.core.i18n import tr
from cob.core.paths import user_data_dir
from cob.ui.shell import logo_pixmap
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Card, CategoryTabs, IconLabel, SegmentedControl, ToggleRow
from cob.ui.widgets import label as text

RELEASES_URL = "https://github.com/Clash-Tools/Clash-of-Bots/releases"

DEVELOPER_WARNING = tr("Developer options turn on features that are not finished or not checked live "
                       "yet. They can fail during a run, waste troops or misread screens. Use them only "
                       "on a test account and report what you find.")


def confirm_developer(parent: QWidget) -> bool:
    """Ask before showing the Developer options: their features are not finished (D-038)."""
    answer = QMessageBox.warning(parent, tr("Turn on Developer options?"), DEVELOPER_WARNING,
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No)
    return answer == QMessageBox.StandardButton.Yes
class VersionLabel(QLabel):
    """The version text; clicking it seven times unlocks the Developer options (D-038)."""

    unlock = Signal()
    CLICKS = 7

    def __init__(self, text_: str):
        super().__init__(text_)
        self.setProperty("role", "mono")
        self._clicks = 0

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt)
        self._clicks += 1
        if self._clicks >= self.CLICKS:
            self._clicks = 0
            self.unlock.emit()
        super().mousePressEvent(event)


SETTINGS_CATEGORIES = [  # key, icon, title, subtitle (tabs, #101: no scrolling)
    ("appearance", "palette", tr("Appearance"), tr("Theme")),
    ("notifications", "notifications", tr("Tray & Notifications"), tr("Alerts and start-up")),
    ("data", "folder_data", tr("Data & Storage"), tr("Folder, export, reset")),
    ("release", "system_update_alt", tr("Release"), tr("Version and updates")),
    ("about", "info", tr("About"), tr("Licence and privacy")),
    ("developer", "bug_report", "Developer options", "Feature flags"),  # hidden until unlocked (D-038)
]


ACCENT_NAMES = {"teal": tr("Teal"), "blue": tr("Blue"), "purple": tr("Purple"), "orange": tr("Orange"),
                "pink": tr("Pink"), "green": tr("Green")}


def channel(version: str = __version__) -> str:
    for name in ("alpha", "beta", "rc"):
        if f"-{name}." in version:
            return {"alpha": tr("Alpha"), "beta": tr("Beta"), "rc": tr("Release candidate")}[name]
    return tr("Stable")


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


class SettingsPage(QWidget):
    changed = Signal(object)  # UiSettings
    export_config = Signal()
    import_config = Signal()
    reset_config = Signal()
    test_notification = Signal()
    run_wizard = Signal()
    restart_requested = Signal()  # theme / accent change: they apply at start-up
    check_updates = Signal()  # Check for updates pressed (the window runs it in the background)

    def __init__(self, settings: ui_settings.UiSettings | None = None, tray_available: bool = True):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("APP & DATA"), "eyebrowAccent"))
        titles.addWidget(text(tr("Preferences"), "headline"))
        titles.addWidget(text(tr("How the app looks, notifies you and keeps its data."), "muted"))
        head.addLayout(titles, 1)
        local = text("  " + tr("LOCAL ONLY"), "tag")
        head.addWidget(local, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        self.tabs = CategoryTabs(SETTINGS_CATEGORIES, tr("Preferences"))
        root.addWidget(self.tabs)
        root.addStretch(1)

        look = Card(tr("Appearance"), "palette")
        look.body.addWidget(text(tr("THEME"), "eyebrow"))
        self.theme = SegmentedControl([(tr("Dark"), "dark", "dark_mode"),
                                       (tr("Light"), "light", "light_mode"),
                                       (tr("AMOLED"), "amoled", "nights_stay")])
        self.theme.changed.connect(self._emit)
        look.body.addWidget(self.theme)
        look.body.addWidget(text(tr("ACCENT COLOUR"), "eyebrow"))
        swatches = QHBoxLayout()
        swatches.setSpacing(t.SM + 4)
        self.accents: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for name in ui_settings.CHOICES["accent"]:
            dark, light = t.ACCENTS[name]
            sw = QPushButton()
            sw.setCheckable(True)
            sw.setFixedSize(36, 36)
            sw.setToolTip(ACCENT_NAMES[name])
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            colour = light[0] if t.THEME == "light" else dark[2]
            sw.setStyleSheet(f"QPushButton {{ background: {colour}; border-radius: 18px; "
                             f"border: 2px solid transparent; }} "
                             f"QPushButton:checked {{ border: 3px solid {t.ON_SURFACE}; }}")
            sw.clicked.connect(self._emit)
            group.addButton(sw)
            swatches.addWidget(sw)
            self.accents[name] = sw
        swatches.addStretch(1)
        look.body.addLayout(swatches)
        look.body.addWidget(text(tr("LANGUAGE"), "eyebrow"))
        self.language = QComboBox()
        for code, name in i18n.available().items():
            self.language.addItem(name, code)
        self.language.setToolTip(tr("More languages come as translation files in assets/i18n."))
        self.language.currentIndexChanged.connect(self._emit)
        look.body.addWidget(self.language)
        restart = QHBoxLayout()
        self.theme_note = text("", "muted", wrap=True)
        restart.addWidget(self.theme_note, 1)
        self.restart_button = QPushButton("  " + tr("Restart now"))
        self.restart_button.setIcon(icon("restart_alt", t.ON_SURFACE, 18))
        self.restart_button.clicked.connect(self.restart_requested)
        restart.addWidget(self.restart_button)
        look.body.addLayout(restart)
        self.tabs.add("appearance", look)

        system = Card(tr("Tray & Notifications"), "notifications")
        self.test_button = QPushButton("  " + tr("Test notification"))
        self.test_button.setIcon(icon("send_time_extension", t.ON_SURFACE, 18))
        self.test_button.clicked.connect(self.test_notification)
        system.header.addWidget(self.test_button)
        self.start_minimized = ToggleRow(tr("Start minimised to the system tray"),
                                         tr("The window opens from the tray icon; farming controls stay in "
                                         "its menu."))
        self.notify_safety = ToggleRow(tr("Safety stops and errors"),
                                       tr("A safety rule or an error stopped farming."))
        self.notify_finished = ToggleRow(tr("Farming finished"),
                                         tr("A limit was reached or you pressed Stop."))
        self.notify_breaks = ToggleRow(tr("Breaks"), tr("A rest between cycles starts."))
        for row in (self.start_minimized, self.notify_safety, self.notify_finished, self.notify_breaks):
            system.body.addWidget(row)
            row.switch.toggled.connect(self._emit)
        if not tray_available:  # the alert toggles still drive Discord / Telegram
            self.start_minimized.setEnabled(False)
            system.body.addWidget(text(tr("No system tray on this desktop: alerts go only to Discord or "
                                          "Telegram."), "muted"))
        system.body.addWidget(text(tr("PHONE ALERTS (OPTIONAL)"), "eyebrow"))
        self.discord = QLineEdit(placeholderText=tr("Discord webhook URL"))
        self.telegram_token = QLineEdit(placeholderText=tr("Telegram bot token"))
        self.telegram_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.telegram_chat = QLineEdit(placeholderText=tr("Chat id"))
        self.telegram_chat.setMaximumWidth(180)
        self.discord.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        system.body.addWidget(self.discord)
        telegram = QHBoxLayout()
        telegram.addWidget(self.telegram_token, 1)
        telegram.addWidget(self.telegram_chat)
        system.body.addLayout(telegram)
        self.alert_status = text("", "muted", wrap=True)
        system.body.addWidget(self.alert_status)
        self.coc_title = text(tr("CLASH OF CLANS API (OPTIONAL)"), "eyebrow")
        system.body.addWidget(self.coc_title)
        self.coc_token = QLineEdit(placeholderText=tr("API key from developer.clashofclans.com"))
        self.coc_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.coc_base = QLineEdit(placeholderText=coc_api.DEFAULT_BASE)
        self.coc_base.setToolTip(tr("Leave empty for the official API. A proxy with a fixed IP address can "
                                    "go here when your own address changes."))
        system.body.addWidget(self.coc_token)
        system.body.addWidget(self.coc_base)
        self.coc_status = text("", "muted", wrap=True)
        system.body.addWidget(self.coc_status)
        from cob.core import flags

        for w in (self.coc_title, self.coc_token, self.coc_base, self.coc_status):  # D-038: experimental
            w.setVisible(flags.enabled("coc_api_sync"))
        for edit in (self.discord, self.telegram_token, self.telegram_chat, self.coc_token, self.coc_base):
            edit.editingFinished.connect(self._alerts_edited)
        self.tabs.add("notifications", system)

        data = Card(tr("Data & Local Storage"), "folder_data")
        self.used = text("", "tag")
        data.header.addWidget(self.used)
        row = QHBoxLayout()
        row.addWidget(IconLabel("dns", 18, t.ON_SURFACE_VARIANT))
        self.folder = text(str(user_data_dir()), "mono")
        self.folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.folder, 1)
        open_button = QPushButton("  " + tr("Open folder"))
        open_button.setIcon(icon("open_in_new", t.ON_SURFACE, 18))
        open_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_data_dir()))))
        row.addWidget(open_button)
        data.body.addLayout(row)
        self.usage = QVBoxLayout()
        self.usage.setSpacing(6)
        data.body.addLayout(self.usage)
        buttons = QHBoxLayout()
        exp = QPushButton("  " + tr("Export settings (.json)"))
        exp.setIcon(icon("file_download", t.ON_SURFACE, 18))
        exp.clicked.connect(self.export_config)
        imp = QPushButton("  " + tr("Import settings"))
        imp.setIcon(icon("file_upload", t.ON_SURFACE, 18))
        imp.clicked.connect(self.import_config)
        reset = QPushButton("  " + tr("Reset automation to defaults"))
        reset.setObjectName("text")
        reset.setStyleSheet(f"color: {t.ERROR};")
        reset.setIcon(icon("restart_alt", t.ERROR, 18))
        reset.clicked.connect(self.reset_config)
        for b in (exp, imp):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(reset)
        data.body.addLayout(buttons)
        self.tabs.add("data", data)

        rel = Card(tr("Release"), "system_update_alt", tag=channel())
        rel.body.addWidget(text(tr("Version {v}", v=__version__), "title"))
        rel.body.addWidget(text(tr("Checking reads this app's release list on GitHub; nothing about you or "
                                "your device is sent, and nothing is downloaded."), "muted", wrap=True))
        row = QHBoxLayout()
        self.update_button = QPushButton("  " + tr("Check for updates"), objectName="tonal")
        self.update_button.setIcon(icon("sync", t.ON_SURFACE, 18))
        self.update_button.clicked.connect(self._check_clicked)
        row.addWidget(self.update_button)
        self.release_button = QPushButton("  " + tr("Open releases page"))
        self.release_button.setIcon(icon("open_in_new", t.ON_SURFACE, 18))
        self.release_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self._release_url)))
        row.addWidget(self.release_button)
        row.addStretch(1)
        rel.body.addLayout(row)
        self.update_status = text("", wrap=True)
        rel.body.addWidget(self.update_status)
        self.changelog = QTextBrowser()
        self.changelog.setOpenExternalLinks(True)
        self.changelog.setMinimumHeight(220)
        self.changelog.setStyleSheet(f"font-family: '{t.FONT_BODY}'; font-size: 13px;")  # not the log font
        self.changelog.hide()
        rel.body.addWidget(self.changelog)
        self.check_at_start = ToggleRow(tr("Check for updates at start-up"),
                                        tr("Once per start, in the background. Off by default."))
        self.check_at_start.switch.toggled.connect(self._emit)
        rel.body.addWidget(self.check_at_start)
        self._release_url = RELEASES_URL
        self.tabs.add("release", rel)

        privacy = Card(tr("Local by design"), "enhanced_encryption", tone="low")
        for line in (tr("Screens are read on this computer only"), tr("No account logins, no telemetry"),
                     tr("Diagnostics are saved only when you ask, with private details removed")):
            r = QHBoxLayout()
            r.addWidget(IconLabel("check", 16, t.PRIMARY))
            r.addWidget(text(line, "muted"), 1)
            privacy.body.addLayout(r)

        about = Card(tr("About"), "info")
        row = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(logo_pixmap(48))
        row.addWidget(logo)
        names = QVBoxLayout()
        names.addWidget(text(tr("Clash of Bots"), "title"))
        self.version_label = VersionLabel(f"{__version__}  •  {channel()}")
        self.version_label.unlock.connect(self.unlock_developer)
        names.addWidget(self.version_label)
        row.addLayout(names, 1)
        about.body.addLayout(row)
        about.body.addWidget(text(tr("Automating the game breaks its terms of service and can get an account "
                                  "banned. Use a test account."), "muted", wrap=True))
        wizard = QPushButton("  " + tr("Run setup wizard"))
        wizard.setIcon(icon("restart_alt", t.ON_SURFACE, 18))
        wizard.clicked.connect(self.run_wizard)
        about.body.addWidget(wizard, 0, Qt.AlignmentFlag.AlignLeft)
        about_page = QWidget()
        ab = QVBoxLayout(about_page)
        ab.setContentsMargins(0, 0, 0, 0)
        ab.setSpacing(t.LG)
        ab.addWidget(about)
        ab.addWidget(privacy)
        self._developer_page()
        ab.addWidget(self.developer_card)
        self.tabs.add("about", about_page)

        self.set_settings(settings or ui_settings.UiSettings())

    # --- developer options (D-038) ---------------------------------------------------------------

    confirm = staticmethod(confirm_developer)  # tests replace it

    def _developer_page(self) -> None:
        from cob.core import flags

        self.flags = flags.load()  # what is saved; the running app keeps what it started with
        self._syncing = False
        self.developer_card = Card(tr("Developer options"), "bug_report", tone="low")
        self.developer_switch = ToggleRow(tr("Show developer options"),
                                          tr("Feature flags for testers. Unfinished features may fail "
                                             "during a run: use a test account."),
                                          self.flags.developer, icon_name="warning")
        self.developer_switch.switch.toggled.connect(self._developer_toggled)
        self.developer_card.body.addWidget(self.developer_switch)
        card = Card("Developer options", "bug_report", tag="HIDDEN")
        card.setProperty("i18n_exempt", True)  # English only: for testers and contributors
        card.body.addWidget(text("Feature flags for work that is not finished or not checked live yet. "
                                 "Changes apply after a restart. Each flag is tracked by its issue on the "
                                 "project board.", "muted", wrap=True))
        self.flag_rows: dict[str, ToggleRow] = {}
        for f in flags.FLAGS:
            issue = f"  •  issue #{f.issue}" if f.issue else ""
            row = ToggleRow(f"{f.title}  [{f.stage}]", f"{f.description}{issue}", self.flags.enabled(f.key))
            row.switch.toggled.connect(lambda on, k=f.key: self._flag_toggled(k, on))
            card.body.addWidget(row)
            self.flag_rows[f.key] = row
        bottom = QHBoxLayout()
        self.flags_note = text("", "muted", wrap=True)
        bottom.addWidget(self.flags_note, 1)
        self.flags_restart = QPushButton("  " + tr("Restart now"))
        self.flags_restart.setIcon(icon("restart_alt", t.ON_SURFACE, 18))
        self.flags_restart.clicked.connect(self.restart_requested)
        self.flags_restart.hide()
        bottom.addWidget(self.flags_restart)
        hide = QPushButton("  Hide developer options")
        hide.clicked.connect(lambda: self.set_developer(False))
        bottom.addWidget(hide)
        card.body.addLayout(bottom)
        self.tabs.add("developer", card)
        self.tabs.buttons["developer"].setProperty("i18n_exempt", True)
        self.tabs.set_visible("developer", self.flags.developer)

    def unlock_developer(self) -> None:
        self.set_developer(True)
        self.tabs.open("developer")

    def set_developer(self, on: bool) -> None:
        self.flags.developer = on
        self._save_flags()
        self.tabs.set_visible("developer", on)
        if self.developer_switch.isChecked() != on:
            self._syncing = True  # the switch follows; no second question
            self.developer_switch.setChecked(on)
            self._syncing = False

    def _developer_toggled(self, on: bool) -> None:
        if self._syncing:
            return
        if on and not self.confirm(self):
            self.set_developer(False)  # declined: the switch goes back off
        elif on:
            self.unlock_developer()
        else:
            self.set_developer(False)

    def _flag_toggled(self, key: str, on: bool) -> None:
        from cob.core import flags

        self.flags.set(key, on)
        self._save_flags()
        pending = self.flags.values != flags.current().values
        self.flags_note.setText("Restart to apply the changed flags." if pending else "")
        self.flags_restart.setVisible(pending)

    def _save_flags(self) -> None:
        from cob.core import flags

        try:
            flags.save(self.flags)
        except OSError as exc:
            self.flags_note.setText(f"Flags not saved: {exc}")

    # --- data -----------------------------------------------------------------------------------

    def settings(self) -> ui_settings.UiSettings:
        return ui_settings.UiSettings(
            wizard_done=self._base.wizard_done, risk_accepted=self._base.risk_accepted,
            start_minimized=self.start_minimized.isChecked(),
            notify_safety_stop=self.notify_safety.isChecked(),
            notify_finished=self.notify_finished.isChecked(),
            notify_breaks=self.notify_breaks.isChecked(),
            discord_webhook=self._alert_value(self.discord, notify.valid_discord, "discord_webhook"),
            telegram_token=self._alert_value(self.telegram_token, notify.valid_telegram_token,
                                             "telegram_token"),
            telegram_chat=self._alert_value(self.telegram_chat, notify.valid_telegram_chat, "telegram_chat"),
            coc_api_token=self._alert_value(self.coc_token, coc_api.valid_token, "coc_api_token"),
            coc_api_base=self._alert_value(self.coc_base, coc_api.valid_base, "coc_api_base"),
            check_updates=self.check_at_start.isChecked(),
            theme=self.theme.value(),
            accent=next((n for n, b in self.accents.items() if b.isChecked()), self._base.accent),
            language=self.language.currentData() or self._base.language,
        )

    def set_settings(self, s: ui_settings.UiSettings) -> None:
        self._base = s  # keeps the fields this page does not show (wizard state)
        self._loading = True
        self.start_minimized.setChecked(s.start_minimized)
        self.notify_safety.setChecked(s.notify_safety_stop)
        self.notify_finished.setChecked(s.notify_finished)
        self.notify_breaks.setChecked(s.notify_breaks)
        for edit, valid, value in ((self.discord, notify.valid_discord, s.discord_webhook),
                                   (self.telegram_token, notify.valid_telegram_token, s.telegram_token),
                                   (self.telegram_chat, notify.valid_telegram_chat, s.telegram_chat),
                                   (self.coc_token, coc_api.valid_token, s.coc_api_token),
                                   (self.coc_base, coc_api.valid_base, s.coc_api_base)):
            typed = edit.text().strip()
            if typed == "" or valid(typed):  # a typo stays in the box with its warning, not saved
                edit.setText(value)
        self._show_alert_status()
        self.check_at_start.setChecked(s.check_updates)
        self.theme.set_value(s.theme)
        if s.accent in self.accents:
            self.accents[s.accent].setChecked(True)
        i = self.language.findData(s.language)
        self.language.setCurrentIndex(i if i >= 0 else 0)
        pending = (s.theme, s.accent, s.language) != (t.THEME, t.ACCENT, i18n.LANGUAGE)
        self.theme_note.setText(tr("Restart to apply the new look or language.") if pending else
                                tr("Theme, accent and language apply after a restart."))
        self.restart_button.setVisible(pending)
        self._loading = False

    def _alert_value(self, edit: QLineEdit, valid, name: str) -> str:
        """The typed value when it is empty or well formed, else the saved one (a typo never wipes it)."""
        v = edit.text().strip()
        return v if v == "" or valid(v) else getattr(self._base, name)

    def _alerts_edited(self) -> None:
        self._show_alert_status()
        self._emit()

    def _show_coc_status(self) -> None:
        tok, base = self.coc_token.text().strip(), self.coc_base.text().strip()
        if tok and not coc_api.valid_token(tok):
            msg = tr("Not saved, that is not an API key (copy the whole key from "
                     "developer.clashofclans.com).")
        elif base and not coc_api.valid_base(base):
            msg = tr("Not saved, the API address must start with https://.")
        elif tok:
            msg = tr("Key set. Sync a profile on the Profiles page. The key only works from the IP addresses "
                     "it lists.")
        else:
            msg = tr("Optional: create a key at developer.clashofclans.com (allow this computer's public IP "
                     "address) and paste it here to sync your troops, spells and heroes. Only your player "
                     "tag is sent, to the Clash of Clans API.")
        self.coc_status.setText(msg)

    def _show_alert_status(self) -> None:
        self._show_coc_status()
        d, tok, chat = (e.text().strip() for e in (self.discord, self.telegram_token, self.telegram_chat))
        bad = []
        if d and not notify.valid_discord(d):
            bad.append(tr("the Discord webhook URL"))
        if tok and not notify.valid_telegram_token(tok):
            bad.append(tr("the Telegram bot token"))
        if chat and not notify.valid_telegram_chat(chat):
            bad.append(tr("the Telegram chat id"))
        if bad:
            msg = tr("Not saved, check {fields}.", fields=", ".join(bad))
        elif bool(tok) != bool(chat):
            msg = tr("Telegram needs both the bot token and the chat id.")
        elif d or tok:
            msg = tr("Alerts also go to your phone. Only the alert text is sent. Press Test notification.")
        else:
            msg = tr("Paste a Discord webhook, or a Telegram bot token and chat id, to get alerts on "
                     "your phone.")
        self.alert_status.setText(msg)

    def show_alert_result(self, errors: list) -> None:
        self.alert_status.setText(tr("Sent.") if not errors else
                                  tr("Not sent: {errors}", errors="; ".join(errors)))

    def _check_clicked(self) -> None:
        self.update_button.setEnabled(False)
        self.update_status.setText(tr("Checking…"))
        self.check_updates.emit()

    def show_update(self, info) -> None:
        """info: cob.core.updates.UpdateInfo."""
        self.update_button.setEnabled(True)
        if info.available:
            latest = info.newer[0]
            self.update_status.setText(tr("Version {v} is available ({n} release(s) newer than yours).",
                                          v=latest.tag.lstrip("v"), n=len(info.newer)))
            self._release_url = latest.url or RELEASES_URL
            self.release_button.setText("  " + tr("Open the {v} release page", v=latest.tag))
            self.changelog.setMarkdown(info.changelog())
            self.changelog.show()
        else:
            self.update_status.setText(tr("You have the latest version ({v}).", v=info.current))
            self._release_url = RELEASES_URL
            self.release_button.setText("  " + tr("Open releases page"))
            self.changelog.hide()

    def show_update_error(self, message: str) -> None:
        self.update_button.setEnabled(True)
        self.update_status.setText(tr("Could not check for updates: {why}", why=message))
        self.changelog.hide()

    def _emit(self, *_args) -> None:
        if not getattr(self, "_loading", False):
            self.changed.emit(self.settings())

    def show_usage(self, sizes: dict[str, int]) -> None:
        while self.usage.count():
            item = self.usage.takeAt(0)
            if item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.setParent(None)
        total = sum(sizes.values()) or 1
        self.used.setText(f"{human_size(sum(sizes.values()))} USED")
        for name, n in sizes.items():
            r = QHBoxLayout()
            cap = text(name, "muted")
            cap.setFixedWidth(140)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(1000 * n / total))
            bar.setTextVisible(False)
            r.addWidget(cap)
            r.addWidget(bar, 1)
            val = text(human_size(n), "mono")
            val.setFixedWidth(80)
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            r.addWidget(val)
            self.usage.addLayout(r)

    def refresh_usage(self) -> None:
        self.show_usage(ui_settings.folder_sizes())
