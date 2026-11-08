"""History & Analytics (#65, design D7): totals, per-day charts and the cycle log from history.csv.

Only columns that exist are shown: no stars, town hall or strategy (no backing data, SCREENS.md 4.4)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cob.core.i18n import tr
from cob.ui.pages.dashboard import _k
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Card, SegmentedControl, StatTile
from cob.ui.widgets import label as text
from cob.ui.widgets.chart import BarChart

COLUMNS = [("time", tr("Time")), ("mode", tr("Mode")), ("search", tr("Search")), ("nexts", tr("Nexts")),
           ("base_gold", tr("Base gold")), ("base_elixir", tr("Base elixir")), ("attack", tr("Attack")),
           ("gained_gold", tr("+ Gold")), ("gained_elixir", tr("+ Elixir")), ("gained_dark", tr("+ Dark")),
           ("seconds", tr("Duration")), ("reason", tr("Note"))]
NUMERIC = {"nexts", "base_gold", "base_elixir", "gained_gold", "gained_elixir", "gained_dark", "seconds"}
RANGES = [(tr("Today"), 1), (tr("7 days"), 7), (tr("30 days"), 30), (tr("All"), 0)]


def _int(v: str | None) -> int:
    v = (v or "").strip()
    return int(v) if v.lstrip("-").isdigit() else 0


def _day(row: dict[str, str]) -> date | None:
    try:
        return datetime.strptime(row.get("time", "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def filter_rows(rows: list[dict[str, str]], mode: str = "all", days: int = 0, search: str = "",
                today: date | None = None) -> list[dict[str, str]]:
    today = today or date.today()
    first = today - timedelta(days=days - 1) if days else None
    needle = search.strip().lower()
    out = []
    for r in rows:
        if mode != "all" and (r.get("mode") or "home") != mode:  # rows from before the mode column: home
            continue
        if first is not None and ((d := _day(r)) is None or d < first):
            continue
        if needle and not any(needle in (r.get(k) or "").lower() for k, _ in COLUMNS):
            continue
        out.append(r)
    return out


@dataclass
class Totals:
    gold: int = 0
    elixir: int = 0
    dark: int = 0
    attacks: int = 0
    failed: int = 0
    cycles: int = 0
    seconds: int = 0

    @property
    def per_hour(self) -> float:
        return (self.gold + self.elixir) * 3600 / self.seconds if self.seconds else 0.0


def totals(rows: list[dict[str, str]]) -> Totals:
    s = Totals(cycles=len(rows))
    for r in rows:
        s.gold += _int(r.get("gained_gold"))
        s.elixir += _int(r.get("gained_elixir"))
        s.dark += _int(r.get("gained_dark"))
        s.seconds += _int(r.get("seconds"))
        s.attacks += r.get("attack") == "done"
        s.failed += r.get("attack") == "failed"
    return s


def per_day(rows: list[dict[str, str]], days: int, today: date | None = None) -> OrderedDict[date, Totals]:
    """One Totals per calendar day, oldest first; all `days` days present (empty ones too)."""
    today = today or date.today()
    if not days:
        known = [d for r in rows if (d := _day(r))]
        days = min(30, (today - min(known)).days + 1) if known else 7
    out: OrderedDict[date, Totals] = OrderedDict((today - timedelta(days=i), Totals()) for i in
                                                 range(days - 1, -1, -1))
    for r in rows:
        d = _day(r)
        if d in out:
            t_ = out[d]
            t_.gold += _int(r.get("gained_gold"))
            t_.elixir += _int(r.get("gained_elixir"))
            t_.dark += _int(r.get("gained_dark"))
            t_.attacks += r.get("attack") == "done"
            t_.cycles += 1
    return out


def _fmt(key: str, value: str) -> str:
    if key == "seconds" and value.strip().isdigit():
        s = int(value)
        return f"{s // 60}m {s % 60:02d}s"
    if key == "mode":
        return {"bb": tr("Builder Base"), "home": tr("Home")}.get(value, tr("Home"))
    if key.startswith(("gained", "base")) and value.lstrip("-").isdigit():
        v = int(value)
        return f"{v:+,}" if key.startswith("gained") else f"{v:,}"
    return value


class HistoryPage(QWidget):
    export = Signal()
    reload = Signal()

    def __init__(self):
        super().__init__()
        self._rows: list[dict[str, str]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("History & Analytics"), "headline"))
        titles.addWidget(text(tr("Every farm cycle from history.csv: loot, attacks and time."), "muted"))
        head.addLayout(titles, 1)
        self.range = SegmentedControl([(name, days, None) for name, days in RANGES])
        self.range.set_value(7)
        self.mode = SegmentedControl([(tr("All"), "all", None), (tr("Home Village"), "home", "home"),
                                      (tr("Builder Base"), "bb", "construction")])
        for c in (self.range, self.mode):
            c.changed.connect(self.refresh)
            head.addWidget(c, 0, Qt.AlignmentFlag.AlignBottom)
        self.export_button = QPushButton("  " + tr("Export CSV"))
        self.export_button.setObjectName("tonal")
        self.export_button.setIcon(icon("file_download", t.ON_SURFACE, 18))
        self.export_button.clicked.connect(self.export)
        head.addWidget(self.export_button, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        tiles = QGridLayout()
        tiles.setSpacing(t.SM + 4)
        self.tiles = {
            "gold": StatTile(tr("Total gold"), "monetization_on", t.GOLD),
            "elixir": StatTile(tr("Total elixir"), "water_drop", t.ELIXIR),
            "dark": StatTile(tr("Dark elixir"), "opacity", t.DARK_ELIXIR),
            "attacks": StatTile(tr("Attacks"), "swords"),
            "uptime": StatTile(tr("Run time"), "timelapse"),
            "rate": StatTile(tr("Avg yield / hr"), "speed", t.PRIMARY),
        }
        for i, tile in enumerate(self.tiles.values()):
            tiles.addWidget(tile, 0, i)
        root.addLayout(tiles)

        charts = QHBoxLayout()
        charts.setSpacing(t.LG)
        loot = Card(tr("Loot per Day"), "insights")
        self.loot_chart = BarChart([(tr("Gold"), t.GOLD), (tr("Elixir"), t.ELIXIR)])
        loot.body.addWidget(self.loot_chart)
        attacks = Card(tr("Attacks per Day"), "swords")
        self.attack_chart = BarChart([(tr("Attacks"), t.PRIMARY)])
        attacks.body.addWidget(self.attack_chart)
        charts.addWidget(loot, 7)
        charts.addWidget(attacks, 5)
        root.addLayout(charts)

        log_card = Card(tr("Cycle Log"), "format_list_bulleted")
        self.count = text("", "tag")
        log_card.header.addWidget(self.count)
        tools = QHBoxLayout()
        self.search = QLineEdit(placeholderText=tr("Search mode, result, note…"))
        self.search.addAction(icon("search", t.ON_SURFACE_VARIANT, 18),
                              QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.refresh)
        reload_button = QPushButton("  " + tr("Reload"))
        reload_button.setIcon(icon("refresh", t.ON_SURFACE, 18))
        reload_button.clicked.connect(self.reload)
        tools.addWidget(self.search, 1)
        tools.addWidget(reload_button)
        log_card.body.addLayout(tools)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([title.upper() for _, title in COLUMNS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(360)
        log_card.body.addWidget(self.table)
        self.empty = text(tr("No cycles recorded for this filter. Start farming on the Dashboard."), "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        log_card.body.addWidget(self.empty)
        self.summary = text("", "muted")
        log_card.body.addWidget(self.summary)
        root.addWidget(log_card)

    # --- data -----------------------------------------------------------------------------------

    def set_rows(self, rows: list[dict[str, str]], path: str = "") -> None:
        self._rows = list(rows)
        self._path = path
        self.refresh()

    def add_row(self, row: dict[str, str]) -> None:
        self._rows.append(row)
        self.refresh()

    def visible_rows(self) -> list[dict[str, str]]:
        return filter_rows(self._rows, self.mode.value(), self.range.value(), self.search.text())

    def refresh(self, *_args) -> None:
        rows = self.visible_rows()
        tot = totals(rows)
        for key, value, sub in (("gold", tot.gold, tr("{n} cycles", n=tot.cycles)),
                                ("elixir", tot.elixir, ""), ("dark", tot.dark, "")):
            self.tiles[key].set(_k(value), sub)
            self.tiles[key].setToolTip(f"{value:+,}")
        self.tiles["attacks"].set(str(tot.attacks), tr("{done} done / {failed} failed", done=tot.attacks,
                                                       failed=tot.failed))
        self.tiles["uptime"].set(f"{tot.seconds / 3600:.1f} h",
                                 tr("{n} min farming", n=f"{tot.seconds / 60:.0f}"))
        rate = f"{tot.per_hour / 1e6:.2f}M" if tot.per_hour >= 1e6 else f"{tot.per_hour:,.0f}"
        self.tiles["rate"].set(rate, tr("Gold + elixir per hour"))
        days = per_day(rows, self.range.value())
        labels = [d.strftime("%a") if len(days) <= 7 else d.strftime("%d") for d in days]
        self.loot_chart.set_data(labels, [[d.gold, d.elixir] for d in days.values()])
        self.attack_chart.set_data(labels, [[d.attacks] for d in days.values()])

        self.table.setRowCount(0)
        for r in reversed(rows):  # newest first
            i = self.table.rowCount()
            self.table.insertRow(i)
            for c, (key, _) in enumerate(COLUMNS):
                item = QTableWidgetItem(_fmt(key, r.get(key) or ""))
                if key in NUMERIC:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, c, item)
        self.table.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        self.count.setText(tr("{n} CYCLES", n=len(rows)))
        shown = tr("Showing {shown} of {total} cycles", shown=len(rows), total=len(self._rows))
        path = getattr(self, "_path", "")
        self.summary.setText(f"{shown}  •  {path}" if path else shown)
