"""Grouped bar chart drawn with QPainter (pyside6-essentials has no QtCharts; D-026)."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from cob.core.i18n import tr
from cob.ui.style import tokens as t


def nice_max(value: float) -> float:
    """Round an axis maximum up to 1/2/2.5/5 x 10^n so tick labels stay readable."""
    if value <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * exp:
            return step * exp
    return 10 * exp


def short(v: float) -> str:
    a = abs(v)
    if a >= 1e6:
        return f"{v / 1e6:g}M"
    if a >= 1e3:
        return f"{v / 1e3:g}k"
    return f"{v:g}"


class BarChart(QWidget):
    """Categories on x, one bar per series in each group; optional dashed cap line."""

    def __init__(self, series: list[tuple[str, str]], cap: float | None = None, cap_label: str = ""):
        super().__init__()
        self.series = series  # (name, colour)
        self.categories: list[str] = []
        self.values: list[list[float]] = []
        self.cap, self.cap_label = cap, cap_label
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, categories: list[str], values: list[list[float]]) -> None:
        self.categories, self.values = categories, values
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        small = QFont(t.FONT_BODY)
        small.setPixelSize(11)
        p.setFont(small)
        w, h = self.width(), self.height()
        left, right, top, bottom = 48, 8, 28, 24
        plot = QRectF(left, top, w - left - right, h - top - bottom)

        # legend
        x = left
        for name, color in self.series:
            p.fillRect(QRectF(x, 6, 10, 10), QColor(color))
            p.setPen(QColor(t.ON_SURFACE_VARIANT))
            p.drawText(QRectF(x + 14, 0, 160, 22), Qt.AlignmentFlag.AlignVCenter, name)
            x += 24 + p.fontMetrics().horizontalAdvance(name)

        top_value = max([v for group in self.values for v in group] + [self.cap or 0, 0])
        ymax = nice_max(top_value)
        grid = QPen(QColor(t.OUTLINE_VARIANT))
        grid.setWidthF(0.6)
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(grid)
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            p.setPen(QColor(t.OUTLINE))
            right_mid = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            p.drawText(QRectF(0, y - 8, left - 6, 16), right_mid, short(ymax * i / 4))

        if not self.categories:
            p.setPen(QColor(t.OUTLINE))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, tr("No data in this range"))
            p.end()
            return

        n, k = len(self.categories), max(1, len(self.series))
        slot = plot.width() / n
        bar = min(28.0, slot * 0.7 / k)
        for i, (cat, group) in enumerate(zip(self.categories, self.values, strict=True)):
            x0 = plot.left() + slot * i + (slot - bar * k) / 2
            for j, v in enumerate(group):
                bh = plot.height() * max(0.0, v) / ymax
                r = QRectF(x0 + j * bar, plot.bottom() - bh, bar - 2, bh)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(self.series[j][1]))
                p.drawRoundedRect(r, 3, 3)
            p.setPen(QColor(t.OUTLINE))
            p.drawText(QRectF(plot.left() + slot * i, plot.bottom() + 4, slot, 18),
                       Qt.AlignmentFlag.AlignCenter, cat)

        if self.cap:
            y = plot.bottom() - plot.height() * self.cap / ymax
            pen = QPen(QColor(t.TERTIARY))
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            p.drawText(QRectF(plot.right() - 200, y - 18, 200, 16), Qt.AlignmentFlag.AlignRight,
                       self.cap_label)
        p.end()
