"""Automation settings (#64, design D5): every farm.json field, grouped by category. The category list
works as tabs: one section at a time, no page scrolling (#101). Unsaved-changes bar and a typed
confirmation before anything may spend resources (D-020).

Categories without a backing feature (Clan Games, building/lab upgrades) are shown as "coming soon"
cards that link to their issues; nothing on this page is decorative."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from cob.core.config import FarmConfig, default_path
from cob.core.i18n import tr
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Banner, Card, CategoryTabs, IconLabel, NumberField, Switch, ToggleRow, UnsavedBar
from cob.ui.widgets import label as text

# farm.json field -> (caption, maximum, step, unit, help); limits mirror cob/core/config.py clamping.
FIELDS = {
    "min_gold_elixir": (tr("Minimum gold + elixir"), 10_000_000, 50_000, "",
                        tr("Skip bases unless gold and elixir together reach this.")),
    "min_dark": (tr("Minimum dark elixir"), 500_000, 1_000, "",
                 tr("Or attack when dark elixir alone reaches this (0 = off).")),
    "max_nexts": (tr("Max 'Next' searches"), 500, 1, tr("skips"),
                  tr("After this many Nexts the current base is taken (each Next costs gold).")),
    "reduce_every": (tr("Lower the minimums every"), 500, 1, tr("skips"),
                     tr("While searching, ask for less loot every this many Nexts (0 = never).")),
    "reduce_percent": (tr("Lower them by"), 50, 1, "%",
                       tr("Of the set minimums, each time.")),
    "reduce_floor": (tr("Never below"), 100, 5, "%",
                     tr("Of the set minimums, however long the search runs.")),
    "halt_full_percent": (tr("No attacks when storages are"), 100, 5, "%",
                          tr("Gold and elixir both this full: stop, or rest with 'Farm on after a rest' "
                             "(0 = off).")),
    "min_own_gold": (tr("Keep at least own gold"), 100_000_000, 10_000, "",
                     tr("Stop searching below this, so search fees never empty the storage.")),
    "loot_stall_s": (tr("End when loot stops for"), 120, 5, "s",
                     tr("After every troop is out, end the battle when no new loot comes in (0 = off).")),
    "end_at_damage": (tr("End at damage"), 100, 5, "%",
                      tr("End the battle once damage reaches this (0 = off).")),
    "collect_minutes": (tr("Collect resources every"), 1440, 5, "min",
                        tr("Mines, collectors, drills and the loot cart (0 = never).")),
    "request_minutes": (tr("Request troops every"), 1440, 5, "min",
                        tr("0 = never. Uses the game's saved request text; the bot types nothing.")),
    "wall_upgrades": (tr("Walls per cycle"), 10, 1, tr("walls"),
                      tr("Cheapest wall first, exact cost checked.")),
    "wall_reserve": (tr("Keep at least gold / elixir"), 100_000_000, 500_000, "",
                     tr("Walls never take gold or elixir below this.")),
    "break_every": (tr("Break every about"), 200, 1, tr("cycles"), tr("Randomised ±2 (0 = no breaks).")),
    "break_minutes": (tr("Break length about"), 120, 1, "min", tr("Randomised 0.6×–1.4×.")),
    "max_failures": (tr("Stop after failed cycles in a row"), 20, 1, tr("cycles"),
                     tr("A cycle fails when the search or the attack does not finish.")),
    "other_device_wait": (tr("Village opened elsewhere: wait"), 240, 5, "min",
                          tr("Then reload and carry on, 3 times in a row at most (0 = stop at once).")),
    "unavailable_wait": (tr("Game down (maintenance): wait"), 60, 5, "min",
                         tr("Game stuck loading: close it, wait (longer each time, 3 h in all), retry "
                            "(0 = count as a failed cycle).")),
    "daily_minutes": (tr("Max play time per day"), 1440, 15, "min",
                      tr("Counted from history.csv, all runs today (0 = no limit).")),
    "daily_attacks": (tr("Max attacks per day"), 1000, 5, tr("attacks"),
                      tr("All runs today (0 = no limit).")),
    "quiet_from": (tr("Quiet from"), 23, 1, ":00", tr("Hour the bot stops starting cycles.")),
    "quiet_to": (tr("Quiet until"), 23, 1, ":00", tr("Same hour as 'from' = no quiet hours.")),
    "daily_attacks_max": (tr("Or up to"), 1000, 5, tr("attacks"),
                          tr("Above the max, each day's limit is drawn from that range (0 = fixed).")),
    "off_hours": (tr("Random rest per day"), 12, 1, "h",
                  tr("One rest of this many hours at a random time each day (0 = none).")),
}

CATEGORIES = [  # key, icon, title, subtitle
    ("farming", "swords", tr("Farming"), tr("Attack thresholds & search")),
    ("battle", "timer", tr("Battle"), tr("When to end an attack")),
    ("builder", "construction", tr("Builder Base"), tr("Attacks & collection")),
    ("collect", "paid", tr("Resource Collectors"), tr("Mines, pumps & cart")),
    ("castle", "shield_person", tr("Clan Castle"), tr("Troop requests")),
    ("games", "military_tech", tr("Clan Games"), tr("Coming soon")),
    ("upgrades", "upgrade", tr("Upgrades"), tr("Walls (spends loot)")),
]


def _confirm_spend(parent: QWidget) -> bool:
    typed, ok = QInputDialog.getText(
        parent, tr("Allow spending"),
        tr("Wall upgrades spend your gold and elixir (never gems).\nType SPEND to allow it:"))
    return ok and typed.strip().upper() == "SPEND"


class _Section(Card):
    def __init__(self, icon_name: str, title: str, subtitle: str):
        super().__init__(padding=t.LG, header=True)
        self.setStyleSheet(f"QFrame[card] {{ border-radius: {t.RADIUS_SHEET}px; }}")
        tile = QFrame()
        tile.setFixedSize(40, 40)
        tile.setStyleSheet(f"background: {t.SECONDARY_CONTAINER}; border-radius: 10px;")
        lay = QHBoxLayout(tile)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(IconLabel(icon_name, 22, t.PRIMARY), 0, Qt.AlignmentFlag.AlignCenter)
        self.header.insertWidget(0, tile, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.setAlignment(Qt.AlignmentFlag.AlignTop)
        texts.addWidget(text(title, "title"))
        texts.addWidget(text(subtitle, "muted", wrap=True))
        self.header.insertLayout(1, texts, 1)


class ConfigPage(QWidget):
    """A page that edits some farm.json fields: number fields, dirty tracking, unsaved bar.

    Each page only owns its own fields; config() lays them over the last loaded FarmConfig, so two pages
    can edit one farm.json (Automation and Safety, #42)."""

    save_requested = Signal()

    def __init__(self):
        super().__init__()
        self._saved = FarmConfig()
        self.spins: dict[str, QSpinBox] = {}
        self.fields: dict[str, NumberField] = {}
        self.toggles: dict[str, ToggleRow] = {}  # 0 / 1 farm.json fields
        self.unsaved = UnsavedBar()
        self.unsaved.save.connect(self.save_requested)
        self.unsaved.discard.connect(lambda: self.set_config(self._saved))

    def _field(self, name: str) -> NumberField:
        caption, maximum, step, unit, hint = FIELDS[name]
        f = NumberField(caption, 0, maximum, 0, unit=unit, hint=hint, step=step)
        f.valueChanged.connect(self._changed)
        self.fields[name] = f
        self.spins[name] = f.spin
        return f

    def _toggle(self, name: str, icon_name: str, title: str, detail: str) -> ToggleRow:
        row = ToggleRow(title, detail, icon_name=icon_name)
        row.switch.toggled.connect(self._changed)
        self.toggles[name] = row
        return row

    def _grid(self, *names: str) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(t.LG)
        grid.setVerticalSpacing(t.MD)
        for i, name in enumerate(names):
            grid.addWidget(self._field(name), i // 2, i % 2)
        return grid

    def _changed(self, *_args) -> None:
        self.unsaved.setVisible(self.dirty())

    def values(self) -> dict[str, int]:
        return {**{name: spin.value() for name, spin in self.spins.items()},
                **{name: int(row.isChecked()) for name, row in self.toggles.items()}}

    def config(self) -> FarmConfig:
        return replace(self._saved, **self.values())

    def set_config(self, cfg: FarmConfig, mark_saved: bool = True) -> None:
        for name, spin in self.spins.items():
            spin.blockSignals(True)
            spin.setValue(getattr(cfg, name))
            spin.blockSignals(False)
        for name, row in self.toggles.items():
            row.switch.blockSignals(True)
            row.switch.setChecked(bool(getattr(cfg, name)))
            row.switch.blockSignals(False)
        if mark_saved:
            self._saved = cfg
        self._changed()

    def mark_saved(self, cfg: FarmConfig | None = None) -> None:
        self._saved = cfg or self.config()
        self._changed()

    def dirty(self) -> bool:
        return self.config() != self._saved


class AutomationPage(ConfigPage):
    def __init__(self, confirm_spend: Callable[[QWidget], bool] = _confirm_spend):
        super().__init__()
        self._confirm_spend = confirm_spend

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("AUTOMATION ENGINE  •  RULES & LOGIC"), "eyebrowAccent"))
        titles.addWidget(text(tr("Automation Settings"), "headline"))
        titles.addWidget(text(tr("Saved in {path}", path=default_path()), "muted"))
        head.addLayout(titles, 1)
        self.defaults_button = QPushButton("  " + tr("Restore defaults"))
        self.defaults_button.setIcon(icon("restart_alt", t.PRIMARY, 18))
        self.defaults_button.setObjectName("text")
        self.defaults_button.clicked.connect(lambda: self.set_config(
            replace(self._saved, **{n: getattr(FarmConfig(), n) for n in self.spins}), mark_saved=False))
        self.save_button = QPushButton("  " + tr("Save"))
        self.save_button.setObjectName("tonal")
        self.save_button.setIcon(icon("check", t.ON_SURFACE, 18))
        self.save_button.clicked.connect(self.save_requested)
        head.addWidget(self.defaults_button, 0, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        self.tabs = CategoryTabs(CATEGORIES, tr("Rule Categories"))
        self.category_buttons, self.stack = self.tabs.buttons, self.tabs.stack
        root.addWidget(self.tabs)
        root.addStretch(1)

        self.sections: dict[str, _Section] = {}
        self._build_sections()
        root.addWidget(self.unsaved)

    # --- layout ---------------------------------------------------------------------------------

    def _add(self, key: str, section: _Section) -> _Section:
        self.sections[key] = section
        self.tabs.add(key, section)
        return section

    def _build_sections(self) -> None:
        s = self._add("farming", _Section("radar", tr("Farming Heuristics"),
                                          tr("Which bases are worth attacking, and when to stop searching.")))
        s.body.addLayout(self._grid("min_gold_elixir", "min_dark", "max_nexts", "min_own_gold",
                                    "reduce_every", "reduce_percent", "reduce_floor", "halt_full_percent"))

        s = self._add("battle", _Section("timer", tr("Ending a Battle"),
                                         tr("Damage that stops growing for 15 s always ends a battle. "
                                            "These end it sooner.")))
        s.body.addLayout(self._grid("loot_stall_s", "end_at_damage"))
        s.body.addWidget(self._toggle(
            "cast_spells", "science", tr("Cast spells"),
            tr("After the troops and hero abilities, every spell lands a little inside the attacked "
               "edge, on the buildings the troops reach first.")))
        s.body.addWidget(self._toggle(
            "two_sides", "swords", tr("Deploy on two sides"),
            tr("Troops spread along two neighbouring edges around a corner instead of one (heroes go to "
               "the corner).")))

        s = self._add("builder", _Section("cabin", tr("Builder Base"),
                                          tr("Choose Builder Base on the Dashboard to run its attacks.")))
        s.body.addWidget(text(tr("Each Builder Base cycle collects the elixir cart and resources, deploys "
                                 "every card and returns by boat. Loot priority and Clock Tower boosts are "
                                 "not built yet."), "muted", wrap=True))

        s = self._add("collect", _Section("savings", tr("Collectors & Loot Cart"),
                                          tr("Collected before the resource read, so it never counts as "
                                             "farmed loot.")))
        s.body.addLayout(self._grid("collect_minutes"))

        s = self._add("castle", _Section("fort", tr("Clan Castle Requests"),
                                         tr("Ask the clan for troops on a timer.")))
        s.body.addLayout(self._grid("request_minutes"))
        s.body.addWidget(Banner("info", tr("Posts to clan chat"),
                                tr("The request uses the text saved in the game. The bot never types "
                                   "messages.")))

        s = self._add("games", _Section("military_tech", tr("Clan Games Automation"),
                                        tr("Pick and finish challenges.")))
        s.header.addWidget(text(tr("COMING SOON"), "tag"))
        s.body.addWidget(text(tr("Planned in issue #1."), "muted"))

        s = self._add("upgrades", _Section("upgrade", tr("Upgrades"),
                                         tr("Spend gold and elixir on walls, safely.")))
        s.header.addWidget(text(tr("SPENDS LOOT"), "tag"))
        s.body.addWidget(Banner("warning", tr("Spending guard"),
                                tr("Off by default. Exact cost read or no spend, your reserve is kept, the "
                                   "drop is checked afterwards, and gems are never used (D-020).")))
        row = QHBoxLayout()
        row.addWidget(IconLabel("fence", 22, t.ON_SURFACE_VARIANT))
        label = text(tr("Upgrade walls"))
        label.setStyleSheet("font-weight: 600;")
        row.addWidget(label, 1)
        self.walls_switch = Switch()
        self.walls_switch.toggled.connect(self._walls_toggled)
        row.addWidget(self.walls_switch)
        s.body.addLayout(row)
        s.body.addLayout(self._grid("wall_upgrades", "wall_reserve"))
        self.upgrades_note = text(tr("Buildings and laboratory upgrades are planned in issue #3."), "muted")
        s.body.addWidget(self.upgrades_note)
        self._apply_flags()

    def _apply_flags(self) -> None:
        """D-038: tabs of features that are not finished stay hidden unless their flag is on."""
        from cob.core import flags

        self.tabs.set_visible("games", flags.enabled("clan_games"))
        self.tabs.set_visible("builder", flags.enabled("builder_base"))
        self.upgrades_note.setVisible(flags.enabled("building_upgrades"))


    # --- behaviour ------------------------------------------------------------------------------

    def show_section(self, key: str) -> None:
        self.tabs.open(key)

    def current_section(self) -> str:
        return self.tabs.current()

    def _walls_toggled(self, on: bool) -> None:
        spin = self.spins["wall_upgrades"]
        if on and spin.value() == 0:
            if not self._confirm_spend(self):
                self.walls_switch.blockSignals(True)
                self.walls_switch.setChecked(False)
                self.walls_switch.blockSignals(False)
                return
            spin.setValue(1)
        elif not on:
            spin.setValue(0)
        self.fields["wall_upgrades"].setEnabled(spin.value() > 0)
        self.fields["wall_reserve"].setEnabled(spin.value() > 0)

    def _changed(self, *_args) -> None:
        on = self.spins["wall_upgrades"].value() > 0
        if self.walls_switch.isChecked() != on:
            self.walls_switch.blockSignals(True)
            self.walls_switch.setChecked(on)
            self.walls_switch.blockSignals(False)
        self.fields["wall_upgrades"].setEnabled(on)
        self.fields["wall_reserve"].setEnabled(on)
        super()._changed()
