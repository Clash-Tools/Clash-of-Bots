"""Safety & Schedule (#42, design D6): breaks, daily limits with today's progress, quiet hours, stop
rules, the read-only spending guarantees, the emergency stop and the account notice (D-027).

Left out: security presets, detection scores, "firmware" claims and a system-wide hotkey (the window's
Esc and the Kill Switch stop the bot; a global hotkey needs OS-specific code)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QPushButton, QVBoxLayout, QWidget

from cob.core.config import FarmConfig
from cob.core.i18n import tr
from cob.tasks import schedule
from cob.ui.pages.automation import ConfigPage
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Banner, Card, CategoryTabs, IconLabel
from cob.ui.widgets import label as text

SAFETY_FIELDS = ("break_every", "break_minutes", "daily_minutes", "daily_attacks", "daily_attacks_max",
                 "quiet_from", "quiet_to", "off_hours", "max_failures", "other_device_wait",
                 "unavailable_wait",
                 "resume_after_rest", "close_game_resting")
SAFETY_CATEGORIES = [  # key, icon, title, subtitle (tabs, #101: no scrolling)
    ("breaks", "bedtime", tr("Breaks & Pacing"), tr("Rests between cycles")),
    ("limits", "timelapse", tr("Daily Limits"), tr("Play time & attacks")),
    ("quiet", "nights_stay", tr("Quiet Hours"), tr("When the bot rests")),
    ("stops", "power_settings_new", tr("Stop Rules"), tr("What ends a run")),
    ("guarantees", "lock", tr("Guarantees"), tr("Spending & emergency stop")),
]


def _rule(icon_name: str, title: str, detail: str, right=None) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(t.MD)
    row.addWidget(IconLabel(icon_name, 22, t.ON_SURFACE_VARIANT), 0, Qt.AlignmentFlag.AlignTop)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    head = text(title)
    head.setStyleSheet("font-weight: 600;")
    texts.addWidget(head)
    texts.addWidget(text(detail, "muted", wrap=True))
    row.addLayout(texts, 1)
    if right is not None:
        row.addWidget(right, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


class SafetyPage(ConfigPage):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("SAFETY ENGINE  •  POLICY & SCHEDULE"), "eyebrowAccent"))
        titles.addWidget(text(tr("Safety & Schedule"), "headline"))
        titles.addWidget(text(tr("Breaks, daily limits, quiet hours and the rules that stop the bot."),
                              "muted"))
        head.addLayout(titles, 1)
        self.defaults_button = QPushButton("  " + tr("Restore safety defaults"))
        self.defaults_button.setObjectName("text")
        self.defaults_button.setIcon(icon("restart_alt", t.PRIMARY, 18))
        self.defaults_button.clicked.connect(lambda: self.set_config(
            replace(self._saved, **{n: getattr(FarmConfig(), n) for n in SAFETY_FIELDS}), mark_saved=False))
        self.save_button = QPushButton("  " + tr("Save"))
        self.save_button.setObjectName("tonal")
        self.save_button.setIcon(icon("check", t.ON_SURFACE, 18))
        self.save_button.clicked.connect(self.save_requested)
        head.addWidget(self.defaults_button, 0, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        self.tabs = CategoryTabs(SAFETY_CATEGORIES, tr("Safety Rules"))
        root.addWidget(self.tabs)
        root.addStretch(1)

        breaks = Card(tr("Breaks & Pacing"), "bedtime", tag=tr("Randomised"))
        breaks.body.addLayout(self._grid("break_every", "break_minutes"))
        self.tabs.add("breaks", breaks)

        daily = Card(tr("Daily Limits"), "timelapse", tag=tr("Resets at midnight"))
        daily.body.addLayout(self._grid("daily_minutes", "daily_attacks", "daily_attacks_max"))
        self.time_bar, self.time_text = self._progress(daily)
        self.attack_bar, self.attack_text = self._progress(daily)
        self.tabs.add("limits", daily)

        quiet = Card(tr("Quiet Hours"), "nights_stay")
        quiet.body.addLayout(self._grid("quiet_from", "quiet_to", "off_hours"))
        self.quiet_text = text("", "muted")
        quiet.body.addWidget(self.quiet_text)
        quiet.body.addWidget(self._toggle(
            "resume_after_rest", "autorenew", tr("Farm on after a rest"),
            tr("Quiet hours, the random rest and daily limits pause the run instead of ending it (checked "
               "every 5 min). A phone on battery may lock meanwhile, which stops the run.")))
        quiet.body.addWidget(self._toggle(
            "close_game_resting", "close", tr("Close the game while resting"),
            tr("Reopened for the next cycle.")))
        self.tabs.add("quiet", quiet)

        rules = Card(tr("Automatic Stop Rules"), "power_settings_new")
        rules.body.addLayout(self._grid("max_failures", "other_device_wait", "unavailable_wait"))
        rules.body.addLayout(_rule("devices", tr("Village opened on another device"),
                                   tr("Stops at once by default, so the bot never fights you for the "
                                      "session. With a wait set, it reloads only after that wait.")))
        rules.body.addLayout(_rule("wifi_off", tr("Device lost"),
                                   tr("LDPlayer is relaunched up to 2 times, a phone is waited for 2 "
                                      "minutes; then the run stops.")))
        rules.body.addLayout(_rule("visibility_off", tr("Unknown screen watchdog"),
                                   tr("After 45 s on an unknown screen the game is restarted and a snapshot "
                                      "is saved (Logs page).")))
        rules.body.addLayout(_rule("savings", tr("Own gold below reserve"),
                                   tr("Searching stops before search fees empty the storage "
                                      "(Automation page).")))
        self.tabs.add("stops", rules)

        guarantees = QWidget()
        g = QVBoxLayout(guarantees)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(t.LG)
        spend = Card(tr("Spending Guarantees"), "lock", tag=tr("Read-only"))
        for line in (tr("Never spends gems or real money"),
                     tr("Exact cost read before every upgrade, or no upgrade"),
                     tr("Your gold / elixir reserve is kept, and the drop is checked afterwards")):
            spend.body.addLayout(_rule("verified", line, ""))
        g.addWidget(spend)
        stop = Card(tr("Emergency Stop"), "keyboard")
        keys = QHBoxLayout()
        key = text(tr("Esc"))
        key.setStyleSheet(f"background: {t.ERROR_CONTAINER}; color: {t.ON_ERROR_CONTAINER}; "
                          f"border-radius: {t.RADIUS}px; padding: 6px 14px; "
                          f"font-family: '{t.FONT_MONO}'; font-weight: 700;")
        keys.addWidget(key)
        keys.addWidget(text(tr("or the KILL SWITCH in the top bar / the tray menu"), "muted"), 1)
        stop.body.addLayout(keys)
        stop.body.addWidget(text(tr("Stops after the current step, so no troop is left half deployed. A "
                                    "system-wide hotkey is not available yet."), "muted", wrap=True))
        g.addWidget(stop)
        g.addWidget(Banner("warning", tr("Account safety"),
                           tr("Automating the game breaks its terms of service and can get an account "
                              "banned. Use a test account, keep sessions short and take breaks.")))
        self.tabs.add("guarantees", guarantees)
        root.addWidget(self.unsaved)
        self.set_usage(0.0, 0)

    def _progress(self, card: Card) -> tuple[QProgressBar, object]:
        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setTextVisible(False)
        label = text("", "mono")
        card.body.addWidget(label)
        card.body.addWidget(bar)
        return bar, label

    def _changed(self, *_args) -> None:
        super()._changed()
        q_from, q_to = self.spins["quiet_from"].value(), self.spins["quiet_to"].value()
        hours = (q_to - q_from) % 24
        quiet = (tr("No quiet hours") if q_from == q_to else
                 tr("The bot will not run {start} – {end} ({hours} h)",
                    start=f"{q_from:02d}:00", end=f"{q_to:02d}:00", hours=hours))
        off = self.spins["off_hours"].value()
        if (start := schedule.off_start(off, date.today(), schedule.install_seed())) is not None:
            quiet += "\n" + tr("Today's random rest: {start} – {end}", start=f"{start:02d}:00",
                               end=f"{(start + off) % 24:02d}:00")
        self.quiet_text.setText(quiet)
        if hasattr(self, "_usage"):
            self.set_usage(*self._usage)

    def set_usage(self, seconds: float, attacks: int) -> None:
        """Today's totals from history.csv, shown against the limits on the form."""
        self._usage = (seconds, attacks)
        minutes, limit_m = seconds / 60, self.spins["daily_minutes"].value()
        limit_a = schedule.daily_attack_limit(self.spins["daily_attacks"].value(),
                                              self.spins["daily_attacks_max"].value(), date.today(),
                                              schedule.install_seed())
        played = f"{int(minutes) // 60}h {int(minutes) % 60:02d}m"
        self.time_text.setText(tr("Today: {played} played of {limit}", played=played,
                                  limit=f"{limit_m // 60}h {limit_m % 60:02d}m") if limit_m
                               else tr("Today: {played} played (no limit)", played=played))
        self.time_bar.setValue(min(1000, round(1000 * minutes / limit_m)) if limit_m else 0)
        self.attack_text.setText(tr("Today: {n} attacks of {limit}", n=attacks, limit=limit_a) if limit_a
                                 else tr("Today: {n} attacks (no limit)", n=attacks))
        self.attack_bar.setValue(min(1000, round(1000 * attacks / limit_a)) if limit_a else 0)
