"""Cycle step pipeline (Collect -> Search -> Attack -> Return -> Break) with per-step state."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from cob.core.i18n import tr
from cob.ui.style import tokens as t
from cob.ui.style.icons import pixmap

# state -> (circle bg, icon colour, caption, caption colour)
_STATES = {
    "pending": (t.SURFACE_HIGH, t.OUTLINE, tr("Pending"), t.OUTLINE),
    "queued": (t.SURFACE_HIGH, t.ON_SURFACE_VARIANT, tr("Queued"), t.OUTLINE),
    "active": (t.PRIMARY_CONTAINER, t.ON_PRIMARY_CONTAINER, tr("Active"), t.PRIMARY),
    "done": (t.SECONDARY_CONTAINER, t.PRIMARY, tr("Done"), t.ON_SURFACE_VARIANT),
    "failed": (t.ERROR_CONTAINER, t.ON_ERROR_CONTAINER, tr("Failed"), t.ERROR),
}

DEFAULT_STEPS = [
    ("collect", tr("Collect"), "energy_savings_leaf"), ("search", tr("Search"), "travel_explore"),
    ("attack", tr("Attack"), "swords"), ("return", tr("Return"), "cottage"), ("break", tr("Break"), "coffee"),
]


class _Step(QWidget):
    def __init__(self, index: int, title: str, icon_name: str):
        super().__init__()
        self.icon_name = icon_name
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.circle = QLabel()
        self.circle.setFixedSize(44, 44)
        self.circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.circle, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = QLabel(f"{index}. {title}")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption = QLabel()
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.title)
        lay.addWidget(self.caption)
        self.set_state("queued")

    def set_state(self, state: str, caption: str | None = None) -> None:
        bg, fg, default_caption, cap_color = _STATES[state]
        self.state = state
        self.circle.setStyleSheet(f"background: {bg}; border-radius: 22px;")
        try:
            self.circle.setPixmap(pixmap(self.icon_name, 20, fg, filled=state == "active"))
        except KeyError:
            self.circle.setText("•")
        active = state == "active"
        self.title.setStyleSheet(f"font-size: 13px; color: {t.PRIMARY if active else t.ON_SURFACE_VARIANT}; "
                                 f"font-weight: {600 if active else 500};")
        self.caption.setText(caption or default_caption)
        self.caption.setStyleSheet(f"font-size: 11px; color: {cap_color};")


class StepPipeline(QWidget):
    """Steps joined by a line; the line is drawn under the circles in paintEvent."""

    def __init__(self, steps: list[tuple[str, str, str]] = DEFAULT_STEPS):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.steps: dict[str, _Step] = {}
        self.order = [key for key, _, _ in steps]
        for i, (key, title, icon_name) in enumerate(steps, 1):
            w = _Step(i, title, icon_name)
            self.steps[key] = w
            lay.addWidget(w, 1)

    def set_active(self, key: str | None) -> None:
        """Steps before `key` done, `key` active, later ones queued; None resets all to queued."""
        idx = self.order.index(key) if key in self.order else -1
        for i, k in enumerate(self.order):
            self.steps[k].set_state("done" if i < idx else "active" if i == idx else "queued")
        self.update()

    def set_state(self, key: str, state: str, caption: str | None = None) -> None:
        self.steps[key].set_state(state, caption)
        self.update()

    def paintEvent(self, _event) -> None:
        if len(self.order) < 2:
            return
        p = QPainter(self)
        p.setPen(QPen(QColor(t.OUTLINE_VARIANT), 2))
        first, last = self.steps[self.order[0]], self.steps[self.order[-1]]
        y = first.mapTo(self, first.circle.geometry().center()).y()
        x0 = first.mapTo(self, first.circle.geometry().center()).x() + 22
        x1 = last.mapTo(self, last.circle.geometry().center()).x() - 22
        p.drawLine(QPointF(x0, y), QPointF(x1, y))
        p.end()
