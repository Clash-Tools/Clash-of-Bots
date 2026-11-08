"""Widget gallery for UI v2 (`cob ui-gallery`): every shared widget in its states, for visual review."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import (
    Banner,
    Card,
    Chip,
    NumberField,
    SegmentedControl,
    StatTile,
    StatusPill,
    StepPipeline,
    ToggleRow,
    UnsavedBar,
    eyebrow,
    label,
)


def build_gallery() -> QWidget:
    page = QWidget()
    page.setObjectName("page")
    lay = QVBoxLayout(page)
    lay.setContentsMargins(t.XL, t.LG, t.XL, t.LG)
    lay.setSpacing(t.LG)
    lay.addWidget(eyebrow("UI v2 foundation", accent=True))
    lay.addWidget(label("Widget gallery", "display"))

    row = QHBoxLayout()
    for state in ("idle", "running", "break", "stopped", "connecting"):
        row.addWidget(StatusPill(state))
    row.addStretch(1)
    lay.addLayout(row)

    row = QHBoxLayout()
    start = QPushButton("  START FARMING", objectName="primary")
    start.setIcon(icon("play_arrow", t.ON_PRIMARY_CONTAINER, 22, filled=True))
    stop = QPushButton("  STOP FARMING  (Esc)", objectName="danger")
    stop.setIcon(icon("stop_circle", t.ON_ERROR_CONTAINER, 22, filled=True))
    grab = QPushButton("  Grab picture")
    grab.setIcon(icon("photo_camera", t.ON_SURFACE, 18))
    tonal, text = QPushButton("Recalibrate", objectName="tonal"), QPushButton("Read more", objectName="text")
    for b in (start, stop, grab, tonal, text):
        row.addWidget(b)
    row.addStretch(1)
    lay.addLayout(row)

    tiles = QGridLayout()
    tiles.setSpacing(t.MD)
    for i, (cap, ic, col, val, sub, unit) in enumerate([
        ("Gold", "monetization_on", t.GOLD, "1,284,500", "+340,000 harvested", ""),
        ("Elixir", "water_drop", t.ELIXIR, "980,120", "+310,000 harvested", ""),
        ("Dark elixir", "opacity", t.DARK_ELIXIR, "12,850", "+1,850 harvested", ""),
        ("Attacks", "swords", t.ON_SURFACE, "14", "12 won / 2 lost", ""),
        ("Cycles", "autorenew", t.ON_SURFACE, "7", "Session complete: 58%", ""),
        ("Loot / hr", "trending_up", t.PRIMARY, "412k", "Gold + elixir", "/hr"),
    ]):
        tile = StatTile(cap, ic, col, unit)
        tile.set(val, sub)
        tiles.addWidget(tile, i // 3, i % 3)
    lay.addLayout(tiles)

    pipe = Card("Active Cycle Pipeline", "linear_scale", tag="Sequential state machine")
    steps = StepPipeline()
    steps.set_active("attack")
    pipe.body.addWidget(steps)
    lay.addWidget(pipe)

    form = Card("Run Configuration", "tune")
    form.body.addWidget(SegmentedControl([("Home Village", "home", "home"),
                                          ("Builder Base", "bb", "construction")]))
    nums = QHBoxLayout()
    nums.addWidget(NumberField("Cycles limit", 0, 9999, 0, hint="0 = unlimited"))
    nums.addWidget(NumberField("Time limit", 0, 1440, 120, unit="min", hint="2h 00m hard stop"))
    form.body.addLayout(nums)
    form.body.addWidget(ToggleRow("Collect resources", "Tap full collectors before each search", True,
                                  "savings"))
    form.body.addWidget(ToggleRow("Upgrade walls", "Spends gold or elixir; off by default", False, "fence"))
    chips = QHBoxLayout()
    for caption, ic in (("Breaks every 8 cycles", "coffee"), ("Spending: OFF", "lock"),
                        ("Daily limit 4 h", "schedule")):
        chips.addWidget(Chip(caption, ic))
    for level in ("INFO", "WARN", "ERROR"):
        chips.addWidget(Chip(level, checkable=True))
    chips.addStretch(1)
    form.body.addLayout(chips)
    lay.addWidget(form)

    lay.addWidget(Banner("error", "Stopped by safety rule", "The village was opened on another device. "
                         "The bot stopped and will not continue on its own.", "Review"))
    lay.addWidget(Banner("warning", "On break", "Resting 5 min after 8 cycles (randomised)."))
    bar = UnsavedBar()
    bar.show()
    lay.addWidget(bar)
    lay.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(page)
    scroll.resize(1280, 1600)
    return scroll
