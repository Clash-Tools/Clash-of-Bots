"""Dashboard / "Mission Control" (#63): designs D1 idle, D2 running, D3 stopped by a safety rule.

Only real data is shown: the live view, the farm loop step, FarmStats, the last CycleResult, the
farm.json guardrails and the log. Design elements without a backing feature (FPS, detection boxes,
stars, thermal readings) are left out (SCREENS.md 4.1)."""

from __future__ import annotations

import time

from PySide6.QtCore import QEvent, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cob.attack.loot import Loot
from cob.core.config import FarmConfig
from cob.core.i18n import tr
from cob.device.base import TARGET_SIZE
from cob.tasks.farm import CycleResult, FarmStats
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import (
    Banner,
    Card,
    Chip,
    IconLabel,
    NumberField,
    SegmentedControl,
    StatTile,
    StepPipeline,
)
from cob.ui.widgets import label as text


def _k(n: int) -> str:
    """Compact signed number for tiles: 1,234 / 12.3k / 1.53M."""
    a = abs(n)
    sign = "-" if n < 0 else ""
    if a >= 1_000_000:
        return f"{sign}{a / 1e6:.2f}M"
    if a >= 10_000:
        return f"{sign}{a / 1e3:.0f}k"
    return f"{n:,}"


class _Preview(QLabel):
    """Well that shows the latest frame scaled to fit (16:9 kept). It fills the rest of the card, at
    least 120 px, so the dashboard fits without scrolling from 1366x768 up (#99) and has no empty band
    on taller windows."""

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(120)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {t.SURFACE_LOWEST}; border-radius: {t.RADIUS}px; "
                           f"color: {t.ON_SURFACE_VARIANT};")
        self._source: QPixmap | None = None
        self.setText(tr("No picture yet - press Grab picture, or start farming"))

    def set_frame(self, pm: QPixmap) -> None:
        self._source = pm
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source is not None:
            self.setPixmap(self._source.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))


class DashboardPage(QWidget):
    review_logs = Signal()

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.MD)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.eyebrow = text(tr("AUTOMATION COPILOT  •  HOME VILLAGE"), "eyebrowAccent")
        titles.addWidget(self.eyebrow)
        titles.addWidget(text(tr("Mission Control"), "headline"))
        head.addLayout(titles, 1)
        root.addLayout(head)

        self.banner = Banner("error", tr("Automation halted by a safety rule"), "", tr("Review logs"))
        self.banner.action.connect(self.review_logs)
        self.banner.hide()
        root.addWidget(self.banner)

        # No scrolling from 1366x768 (#99): KPI row, then view | controls, then pipeline | guardrails. On
        # a tall window the last cycle sits under the controls (no empty band beside the view); on a
        # short one it joins the bottom row, as the column would not fit.
        root.addLayout(self._tiles())
        top = QHBoxLayout()
        top.setSpacing(t.MD)
        top.addWidget(self._live_card(), 2)  # grows and shrinks with the window (the preview)
        self._side = QVBoxLayout()
        self._side.setSpacing(t.MD)
        self._side.addWidget(self._run_card())
        self._side.addStretch(1)
        top.addLayout(self._side, 1)
        root.addLayout(top, 1)
        self._bottom = QHBoxLayout()
        self._bottom.setSpacing(t.MD)
        self._last = self._last_card()
        for card in (self._pipeline_card(), self._last, self._guard_card()):
            card.body.addStretch(1)  # same row height: keep each card's content at its top
            self._bottom.addWidget(card, 1)
        root.addLayout(self._bottom)
        self._tall = False
        self._watched = None

        self._updated_at: float | None = None
        self._ago = QTimer(self, interval=1000)
        self._ago.timeout.connect(self._tick_ago)
        self._ago.start()
        self.set_stats(FarmStats())  # after every card: it also fills the pipeline's cycle counter
        self.set_running(False)

    # --- layout ---------------------------------------------------------------------------------

    TALL_WINDOW = 1000  # px: from here the last-cycle card fits under the run controls

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        win = self.window()
        if win is not self and win is not self._watched:
            win.installEventFilter(self)
            self._watched = win
        self._place_last(win.height())

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self._watched and event.type() == QEvent.Type.Resize:
            self._place_last(obj.height())
        return False

    def _place_last(self, window_height: int) -> None:
        tall = window_height >= self.TALL_WINDOW
        if tall == self._tall:
            return
        self._tall = tall
        if tall:
            self._bottom.removeWidget(self._last)
            self._side.takeAt(self._side.count() - 1)  # the stretch under the run card
            self._side.addWidget(self._last, 1)
            self._bottom.setStretch(0, 2)
        else:
            self._side.removeWidget(self._last)
            self._side.addStretch(1)
            self._bottom.insertWidget(1, self._last, 1)
            self._bottom.setStretch(0, 1)

    # --- cards ----------------------------------------------------------------------------------

    def _live_card(self) -> Card:
        card = Card(tr("Live Game View"), "videocam", tag=f"{TARGET_SIZE[0]}×{TARGET_SIZE[1]}")
        self.updated = text("", "muted")
        card.header.addWidget(self.updated)
        self.grab_button = QPushButton("  " + tr("Grab picture"))
        self.grab_button.setIcon(icon("photo_camera", t.ON_SURFACE, 18))
        card.header.addWidget(self.grab_button)
        scene = QHBoxLayout()
        scene.setSpacing(t.SM)
        self.scene_dot = text("●")
        self.scene_dot.setStyleSheet(f"color: {t.OUTLINE};")
        scene.addWidget(self.scene_dot)
        scene.addWidget(text(tr("DETECTED SCENE"), "eyebrowAccent"))
        self.scene = text("-")
        scene.addWidget(self.scene)
        scene.addStretch(1)
        card.body.addLayout(scene)
        self.preview = _Preview()
        card.body.addWidget(self.preview, 1)  # the picture takes the card's spare height
        return card

    def _pipeline_card(self) -> Card:
        card = Card(tr("Active Cycle Pipeline"), "linear_scale")
        self.iteration = text("", "mono")
        card.header.addWidget(self.iteration)
        self.pipeline = StepPipeline()
        card.body.addWidget(self.pipeline)
        info = QHBoxLayout()
        info.addWidget(IconLabel("info", 16, t.ON_SURFACE_VARIANT))
        self.pipeline_info = text(tr("Collect runs first; breaks follow your Safety settings."), "muted",
                                  wrap=True)
        info.addWidget(self.pipeline_info, 1)
        card.body.addLayout(info)
        return card

    def _run_card(self) -> Card:
        card = Card(tr("Run Configuration"), "tune")
        self.mode = SegmentedControl([(tr("Home Village"), "home", "home"),
                                      (tr("Builder Base"), "bb", "construction")])
        self.mode.changed.connect(lambda v: self.eyebrow.setText(
            tr("AUTOMATION COPILOT  •  BUILDER BASE") if v == "bb"
            else tr("AUTOMATION COPILOT  •  HOME VILLAGE")))
        card.body.addWidget(self.mode)
        nums = QHBoxLayout()
        nums.setSpacing(t.MD)
        self.cycles = NumberField(tr("Cycles limit"), 0, 10_000, 5, hint=tr("0 = unlimited"))
        self.minutes = NumberField(tr("Time limit"), 0, 24 * 60, 0, unit="min", hint=tr("0 = no limit"))
        self.cycles.valueChanged.connect(self._limit_hints)
        self.minutes.valueChanged.connect(self._limit_hints)
        nums.addWidget(self.cycles)
        nums.addWidget(self.minutes)
        card.body.addLayout(nums)
        # #185: the game's Saved Recipes; the chosen one is loaded as the army when the run starts.
        army = QHBoxLayout()
        army.setSpacing(t.MD)
        army.addWidget(text(tr("ARMY RECIPE"), "eyebrow"))
        self.army = QComboBox()
        self.army.addItem(tr("Keep current army"), 0)
        for n in range(1, 5):
            self.army.addItem(tr("Saved Recipe {n}", n=n), n)
        self.army.setMinimumHeight(40)
        self.army.setToolTip(tr("Loaded from the game's Army screen (Saved Recipes) when a home-village run "
                                "starts. Recipe 1 is the top row of that list."))
        army.addWidget(self.army, 1)
        card.body.addLayout(army)
        self.start_button = QPushButton("  " + tr("START FARMING"), objectName="primary")
        self.start_button.setIcon(icon("play_arrow", t.ON_PRIMARY_CONTAINER, 22, filled=True))
        self.stop_button = QPushButton("  " + tr("STOP FARMING  (Esc)"), objectName="danger")
        self.stop_button.setIcon(icon("stop_circle", t.ON_ERROR_CONTAINER, 22, filled=True))
        self.pause_button = QPushButton("  " + tr("PAUSE"), objectName="tonal")
        self.pause_button.setIcon(icon("pause", t.ON_SURFACE, 22, filled=True))
        self.pause_button.setToolTip(tr("Hold after the current cycle; the session stats are kept."))
        card.body.addWidget(self.start_button)
        run = QHBoxLayout()
        run.setSpacing(t.SM)
        self.pause_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        run.addWidget(self.pause_button, 1)  # as tall as the Stop button beside it
        run.addWidget(self.stop_button, 2)
        card.body.addLayout(run)
        self._limit_hints()
        return card

    def _tiles(self) -> QHBoxLayout:
        grid = QHBoxLayout()
        grid.setSpacing(t.SM + 4)
        self.tiles = {
            "gold": StatTile(tr("Gold"), "monetization_on", t.GOLD),
            "elixir": StatTile(tr("Elixir"), "water_drop", t.ELIXIR),
            "dark": StatTile(tr("Dark elixir"), "opacity", t.DARK_ELIXIR),
            "attacks": StatTile(tr("Attacks"), "swords"),
            "cycles": StatTile(tr("Cycles"), "autorenew"),
            "rate": StatTile(tr("Loot / hr"), "trending_up", t.PRIMARY),
        }
        for tile in self.tiles.values():
            tile.setMinimumHeight(0)  # compact KPI strip: tighter padding than the default tile
            tile.layout().setContentsMargins(t.MD, t.SM + 4, t.MD, t.SM + 4)
            tile.layout().setSpacing(2)
            grid.addWidget(tile, 1)
        return grid

    def _last_card(self) -> Card:
        card = Card(tr("Last Completed Cycle"), "history", tag=tr("Latest"))
        self.last_title = text(tr("No cycle yet"))
        self.last_title.setStyleSheet("font-weight: 600;")
        self.last_detail = text(tr("Loot gained and the outcome of each cycle show here."), "muted",
                                wrap=True)
        self.last_loot = QWidget()
        row = QHBoxLayout(self.last_loot)
        row.setContentsMargins(0, 0, 0, 0)
        self.last_gold, self.last_elixir, self.last_dark = (text("", "mono") for _ in range(3))
        for lab, ic, col in ((self.last_gold, "monetization_on", t.GOLD),
                             (self.last_elixir, "water_drop", t.ELIXIR),
                             (self.last_dark, "opacity", t.DARK_ELIXIR)):
            row.addWidget(IconLabel(ic, 16, col, filled=True))
            lab.setStyleSheet(f"color: {col}; font-weight: 600;")
            row.addWidget(lab)
            row.addSpacing(t.SM)
        row.addStretch(1)
        card.body.addWidget(self.last_title)
        card.body.addWidget(self.last_loot)
        self.last_loot.hide()  # icons without numbers until the first cycle
        card.body.addWidget(self.last_detail)
        return card

    def _guard_card(self) -> Card:
        card = Card(tr("Active Safety Guardrails"), "verified_user")
        self.guard_count = text("", "mono")
        card.header.addWidget(self.guard_count)
        self.guard_chips = QGridLayout()
        self.guard_chips.setSpacing(t.SM)
        card.body.addLayout(self.guard_chips)
        return card

    # --- updates --------------------------------------------------------------------------------

    def _limit_hints(self, *_args) -> None:
        c, m = self.cycles.value(), self.minutes.value()
        self.cycles.set_hint(tr("Unlimited continuous") if c == 0 else tr("Stops after 1 cycle") if c == 1
                             else tr("Stops after {n} cycles", n=c))
        self.minutes.set_hint(tr("No time limit") if m == 0
                              else tr("{h}h {m}m hard stop", h=m // 60, m=f"{m % 60:02d}"))

    def army_recipe(self) -> int:
        return int(self.army.currentData() or 0)

    def set_army_recipe(self, slot: int) -> None:
        i = self.army.findData(int(slot))
        self.army.setCurrentIndex(i if i >= 0 else 0)

    def set_running(self, running: bool) -> None:
        self.start_button.setVisible(not running)
        self.stop_button.setVisible(running)
        self.pause_button.setVisible(running)
        if not running:
            self.set_paused(False)
        for w in (self.mode, self.cycles, self.minutes, self.grab_button, self.army):
            w.setEnabled(not running)
        if running:  # a new run: nothing from the last one may still say "Stopped"
            self.banner.hide()
            self.pipeline.set_active(None)
            self.pipeline_info.setText(tr("Collect runs first; breaks follow your Safety settings."))

    @Slot(str)
    def set_paused(self, paused: bool) -> None:
        self.pause_button.setText("  " + (tr("RESUME") if paused else tr("PAUSE")))
        self.pause_button.setIcon(icon("play_arrow" if paused else "pause", t.ON_SURFACE, 22, filled=True))

    def set_step(self, step: str | None) -> None:
        self.pipeline.set_active(step)

    def set_preview(self, pm: QPixmap, screen: str) -> None:
        self.preview.set_frame(pm)
        self.scene.setText(screen)
        self.scene_dot.setStyleSheet(f"color: {t.OUTLINE if screen == 'UNKNOWN' else t.PRIMARY};")
        self._updated_at = time.monotonic()
        self._tick_ago()

    def preview_failed(self, message: str) -> None:
        self.updated.setText(tr("Grab failed: {message}", message=message))

    def _tick_ago(self) -> None:
        if self._updated_at is None:
            return
        s = int(time.monotonic() - self._updated_at)
        self.updated.setText(tr("updated just now") if s < 2 else tr("updated {s} s ago", s=s) if s < 120
                             else tr("updated {m} min ago", m=s // 60))

    def set_stats(self, stats: FarmStats, max_cycles: int = 0) -> None:
        g = stats.gained
        seconds = stats.seconds or sum(c.seconds for c in stats.cycles)
        per_h = 3600 / seconds if stats.attacks and seconds > 0 else 0.0
        for key, value in (("gold", g.gold), ("elixir", g.elixir), ("dark", g.dark)):
            sub = (tr("{n} / hr", n=_k(int(value * per_h))) if per_h
                   else tr("+0 farmed") if not stats.cycles else "-")
            self.tiles[key].set(_k(value), sub)
        failed = sum(1 for c in stats.cycles if c.attack == "failed")
        self.tiles["attacks"].set(str(stats.attacks), tr("{done} done / {failed} failed",
                                                             done=stats.attacks, failed=failed))
        n = len(stats.cycles)
        errors = sum(1 for c in stats.cycles if c.search == "error")
        sub = (tr("Session complete: {pct}%", pct=min(100, round(100 * n / max_cycles))) if max_cycles
               else tr("1 error") if errors == 1 else tr("{n} errors", n=errors) if errors
               else tr("No errors"))
        self.tiles["cycles"].set(str(n), sub)
        total = (g.gold + g.elixir) * per_h
        self.tiles["rate"].set(_k(int(total)) if per_h else "0", tr("Gold + elixir per hour") if per_h
                               else tr("Awaiting first attack"))
        self.tiles["rate"].setToolTip(tr("gold {gold}, elixir {elixir}, dark {dark} per hour",
                                         gold=f"{g.gold * per_h:+,.0f}", elixir=f"{g.elixir * per_h:+,.0f}",
                                         dark=f"{g.dark * per_h:+,.0f}") if per_h else "")
        self.iteration.setText(tr("Cycle {n} / {total}", n=n + 1, total=max_cycles or "∞")
                               if n or max_cycles else "")

    def set_last_cycle(self, cycle: CycleResult) -> None:
        gained = cycle.gained or Loot(0, 0, 0)
        outcomes = {"done": tr("Attack done"), "failed": tr("Attack failed")}
        outcome = outcomes.get(cycle.attack, tr("No attack"))
        self.last_title.setText(tr("Cycle #{n}  •  {outcome}", n=cycle.n, outcome=outcome))
        self.last_loot.show()
        self.last_gold.setText(f"{gained.gold:+,}")
        self.last_elixir.setText(f"{gained.elixir:+,}")
        self.last_dark.setText(f"{gained.dark:+,}")
        detail = tr("Search: {search}, {nexts} Next  •  {seconds} s", search=cycle.search, nexts=cycle.nexts,
                    seconds=f"{cycle.seconds:.0f}")
        if cycle.reason:
            detail += f"  •  {cycle.reason}"
        self.last_detail.setText(detail)

    def set_guardrails(self, cfg: FarmConfig) -> None:
        while self.guard_chips.count():
            item = self.guard_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        quiet = cfg.quiet_from != cfg.quiet_to
        rules = [
            ("coffee", tr("Breaks every ~{n} cycles", n=cfg.break_every) if cfg.break_every
             else tr("Breaks: OFF"), cfg.break_every > 0),
            ("lock" if not cfg.wall_upgrades else "lock_reset",
             tr("Spending: OFF") if not cfg.wall_upgrades
             else tr("Walls: {n} per cycle", n=cfg.wall_upgrades), True),
            ("savings", tr("Keep ≥ {gold} gold", gold=_k(cfg.min_own_gold)), cfg.min_own_gold > 0),
            ("schedule", tr("Daily limit {h}h {m}m", h=cfg.daily_minutes // 60,
                            m=f"{cfg.daily_minutes % 60:02d}")
             if cfg.daily_minutes else tr("Daily limit: OFF"), cfg.daily_minutes > 0),
            ("nights_stay", tr("Quiet {start}–{end}h", start=f"{cfg.quiet_from:02d}",
                               end=f"{cfg.quiet_to:02d}") if quiet else tr("Quiet hours: OFF"), quiet),
            ("paid", tr("Never spends gems"), True),
        ]
        for i, (ic, caption, ok) in enumerate(rules):
            chip = Chip(caption, ic, color=t.PRIMARY if ok else t.OUTLINE)
            chip.setEnabled(True)
            chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.guard_chips.addWidget(chip, i // 2, i % 2)  # 2 columns: the card is a third wide
        active = sum(1 for _, _, ok in rules if ok)
        self.guard_count.setText(tr("{active} / {total} ON", active=active, total=len(rules)))

    def show_safety_stop(self, reason: str) -> None:
        self.banner.set_text(tr("Automation halted by a safety rule"),
                             tr("{reason}. The bot stopped and will not continue on its own; check the log, "
                                "then start again.", reason=reason))
        self.banner.show()
        self.pipeline_info.setText(tr("Stopped: {reason}", reason=reason))

    def show_error(self, message: str) -> None:
        """The run could not go on (phone locked, device gone...): say so in the banner, not as a
        safety rule."""
        self.banner.set_text(tr("Farming stopped"), message)
        self.banner.show()
        self.pipeline_info.setText(tr("Stopped: {reason}", reason=message))

    def hide_safety_stop(self) -> None:
        self.banner.hide()

