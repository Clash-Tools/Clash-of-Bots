"""UI v2 app shell (#49): top bar, navigation rail, page stack, status strip (SCREENS.md section 2).

The shell only lays out and shows state; MainWindow owns the bot logic and calls the setters."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cob.core.i18n import tr
from cob.core.paths import app_root
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import IconLabel, StatusPill, label

# Rail order and icons follow the designs (SCREENS.md section 2).
PAGES = [
    ("dashboard", tr("Dashboard"), "dashboard"),
    ("devices", tr("Devices"), "devices"),
    ("profiles", tr("Profiles"), "person"),
    ("automation", tr("Automation"), "smart_toy"),
    ("safety", tr("Safety"), "shield"),
    ("history", tr("History"), "history"),
    ("cards", tr("Cards"), "swords"),
    ("logs", tr("Logs"), "terminal"),
    ("settings", tr("Settings"), "settings"),
]
BOTTOM_PAGES = [("health", tr("Health"), "verified")]  # under the rail's stretch (#100)


def logo_pixmap(size: int = 32) -> QPixmap:
    dpr = 2.0
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    path = app_root() / "assets" / "logo.svg"
    if path.is_file():
        p = QPainter(pm)
        QSvgRenderer(str(path)).render(p, QRectF(0, 0, pm.width(), pm.height()))
        p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def logo_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(logo_pixmap(s))
    return ic


class _RailButton(QToolButton):
    def __init__(self, text: str, icon_name: str):
        super().__init__()
        self.icon_name = icon_name
        self.setText(text)
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(22, 22))
        self.setFixedSize(t.RAIL_W - 8, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QToolButton {{ background: transparent; color: {t.ON_SURFACE_VARIANT}; border-radius: 12px; "
            f"font-size: 11px; font-weight: 500; padding: 6px 0 0 0; }} "
            f"QToolButton:hover {{ background: {t.SURFACE_HIGH}; }} "
            f"QToolButton:checked {{ background: {t.SECONDARY_CONTAINER}; color: {t.ON_SURFACE}; "
            f"font-weight: 600; }}")
        self.toggled.connect(self._recolor)
        self._recolor(False)

    def _recolor(self, on: bool) -> None:
        self.setIcon(icon(self.icon_name, t.ON_SURFACE if on else t.ON_SURFACE_VARIANT, 22, filled=on))


class Shell(QWidget):
    """Top bar + rail + stacked pages + status strip."""

    kill_switch = Signal()
    page_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._topbar())
        # #161: a thin moving line under the top bar while any background job runs
        self.activity = QProgressBar()
        self.activity.setRange(0, 0)
        self.activity.setTextVisible(False)
        self.activity.setFixedHeight(3)
        self.activity.setStyleSheet(f"QProgressBar {{ background: transparent; border: none; }} "
                                    f"QProgressBar::chunk {{ background: {t.PRIMARY}; }}")
        sp = self.activity.sizePolicy()
        sp.setRetainSizeWhenHidden(True)  # no layout jump when it shows
        self.activity.setSizePolicy(sp)
        self.activity.hide()
        root.addWidget(self.activity)
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        middle.addWidget(self._rail())
        self.stack = QStackedWidget()
        middle.addWidget(self.stack, 1)
        root.addLayout(middle, 1)
        root.addWidget(self._status_strip())
        self.pages: dict[str, QWidget] = {}
        self._session_start: float | None = None
        self._session_frozen = 0.0
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(self._tick)
        self.set_state("idle")

    # --- building -------------------------------------------------------------------------------

    def _topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setFixedHeight(t.TOPBAR_H)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(t.MD, 0, t.MD, 0)
        lay.setSpacing(t.MD)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(32))
        lay.addWidget(logo)
        name = label("Clash of Bots")
        name.setStyleSheet(f"font-family: '{t.FONT_HEADING}'; font-size: 18px; font-weight: 600;")
        lay.addWidget(name)
        div = QFrame()
        div.setFixedSize(1, 20)
        div.setStyleSheet(f"background: {t.DIVIDER_STRONG};")
        lay.addWidget(div)
        # MainWindow puts its device picker in here (device pill).
        self.device_slot = QHBoxLayout()
        self.device_slot.setSpacing(t.SM)
        lay.addLayout(self.device_slot)
        lay.addStretch(1)
        self.state_pill = StatusPill("idle")
        lay.addWidget(self.state_pill)
        self.kill_button = QPushButton("  " + tr("KILL SWITCH"))
        self.kill_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.kill_button.setFixedHeight(36)
        self.kill_button.clicked.connect(self.kill_switch)
        lay.addWidget(self.kill_button)
        return bar

    def _rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("rail")
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rail.setFixedWidth(t.RAIL_W)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(4, t.SM, 4, t.SM)
        lay.setSpacing(4)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav: dict[str, _RailButton] = {}
        for item in [*PAGES, None, *BOTTOM_PAGES]:
            if item is None:  # main pages on top, Health at the bottom
                lay.addStretch(1)
                continue
            key, text, icon_name = item
            b = _RailButton(text, icon_name)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.nav_group.addButton(b)
            self.nav[key] = b
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        return rail

    def _status_strip(self) -> QWidget:
        strip = QWidget()
        strip.setObjectName("statusStrip")
        strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        strip.setFixedHeight(t.STATUS_H)
        lay = QHBoxLayout(strip)
        lay.setContentsMargins(t.MD, 0, t.MD, 0)
        lay.setSpacing(t.SM)
        self.conn_dot = label("●")
        self.connection = label(tr("No device"))
        self.step_icon = IconLabel("hourglass_empty", 15, t.ON_SURFACE_VARIANT)
        self.step = label(tr("Ready (awaiting start)"))
        for w in (self.conn_dot, self.connection):
            lay.addWidget(w)
        lay.addSpacing(t.LG)
        lay.addWidget(self.step_icon)
        lay.addWidget(self.step, 1)
        lay.addWidget(IconLabel("timer", 15, t.ON_SURFACE_VARIANT))
        self.session = label(tr("Session: {h}h {m}m {s}s", h="00", m="00", s="00"))
        self.session.setStyleSheet(f"font-family: '{t.FONT_MONO}';")
        lay.addWidget(self.session)
        lay.addSpacing(t.MD)
        lay.addWidget(IconLabel("verified_user", 15, t.PRIMARY))
        self.safety = label(tr("Safety guard active • Spending locked"))
        lay.addWidget(self.safety)
        return strip

    # --- pages ----------------------------------------------------------------------------------

    def add_page(self, key: str, widget: QWidget, scroll: bool = True) -> None:
        """Pages get the design's 32 px side margins inside a vertical scroll area."""
        holder = QWidget()
        holder.setObjectName("page")
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(t.XL, t.LG, t.XL, t.LG)
        lay.addWidget(widget)
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setWidget(holder)
            holder = area
        self.pages[key] = widget
        self.stack.addWidget(holder)
        widget.setProperty("stack_index", self.stack.count() - 1)

    def show_page(self, key: str) -> None:
        widget = self.pages[key]
        self.stack.setCurrentIndex(widget.property("stack_index"))
        self.nav[key].setChecked(True)
        self.page_changed.emit(key)

    def current_page(self) -> str:
        return next(k for k, b in self.nav.items() if b.isChecked())

    # --- state ----------------------------------------------------------------------------------

    def set_state(self, state: str, text: str | None = None) -> None:
        """idle / running / break / stopped; drives the pill, Kill Switch and session timer."""
        self.state_pill.set_state(state, text)
        active = state in ("running", "break")
        self.kill_button.setEnabled(active)
        if active:
            self.kill_button.setStyleSheet(
                f"QPushButton {{ background: {t.ERROR_CONTAINER}; color: {t.ON_ERROR_CONTAINER}; "
                f"font-weight: 700; letter-spacing: 1px; border-radius: 18px; padding: 0 16px; }} "
                f"QPushButton:hover {{ background: {t.DANGER_HOVER}; }}")
            self.kill_button.setIcon(icon("stop_circle", t.ON_ERROR_CONTAINER, 18, filled=True))
            self.kill_button.setToolTip(tr("Emergency stop (Esc): stops after the current step"))
            if self._session_start is None:
                self._session_start = time.monotonic()
                self._timer.start()
        else:
            self.kill_button.setStyleSheet(
                f"QPushButton {{ background: {t.SURFACE_HIGH}; color: {t.OUTLINE}; font-weight: 700; "
                f"letter-spacing: 1px; border-radius: 18px; padding: 0 16px; }}")
            self.kill_button.setIcon(icon("stop_circle", t.OUTLINE, 18))
            self.kill_button.setToolTip(tr("Kill switch inactive (bot is idle)"))
            if self._session_start is not None:
                self._session_frozen = time.monotonic() - self._session_start
                self._session_start = None
                self._timer.stop()
            if state == "idle":
                self.set_step(tr("Ready (awaiting start)"), "hourglass_empty")
        self._tick()

    def reset_session(self) -> None:
        self._session_start = None
        self._session_frozen = 0.0
        self._tick()

    def session_seconds(self) -> float:
        if self._session_start is not None:
            return time.monotonic() - self._session_start
        return self._session_frozen

    def _tick(self) -> None:
        s = int(self.session_seconds())
        self.session.setText(tr("Session: {h}h {m}m {s}s", h=f"{s // 3600:02d}", m=f"{s % 3600 // 60:02d}",
                                 s=f"{s % 60:02d}"))

    def set_step(self, text: str, icon_name: str = "radar") -> None:
        color = t.TERTIARY if icon_name == "radar" else t.ON_SURFACE_VARIANT
        self.step_icon.set_icon(icon_name, color)
        self.step.setText(f"Current step: {text}" if icon_name == "radar" else text)

    def set_busy(self, busy: bool) -> None:
        self.activity.setVisible(busy)

    def set_connection(self, text: str, ok: bool) -> None:
        self.connection.setText(text)
        self.conn_dot.setStyleSheet(f"color: {t.PRIMARY if ok else t.OUTLINE};")

    def set_safety(self, text: str) -> None:
        self.safety.setText(text)
