"""Dark Fusion theme and the generated app icon (no image assets to keep in sync)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

ACCENT = QColor(232, 176, 44)  # Clash gold
GOOD = "#5fbf5f"
BAD = "#e0605a"


def apply_dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    base, window, text = QColor(30, 31, 34), QColor(43, 45, 49), QColor(225, 225, 225)
    for role, color in (
        (QPalette.ColorRole.Window, window), (QPalette.ColorRole.WindowText, text),
        (QPalette.ColorRole.Base, base), (QPalette.ColorRole.AlternateBase, window),
        (QPalette.ColorRole.Text, text), (QPalette.ColorRole.Button, QColor(53, 55, 60)),
        (QPalette.ColorRole.ButtonText, text), (QPalette.ColorRole.ToolTipBase, window),
        (QPalette.ColorRole.ToolTipText, text), (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, QColor(20, 20, 20)), (QPalette.ColorRole.Link, ACCENT),
    ):
        p.setColor(role, color)
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(120, 120, 120))
    app.setPalette(p)
    app.setStyleSheet("QGroupBox { font-weight: bold; } QPushButton#primary { background: #b8860b; "
                      "color: #111; font-weight: bold; padding: 6px 14px; } "
                      "QPushButton#primary:disabled { background: #5a4a20; color: #888; }")


def app_icon(size: int = 256) -> QIcon:
    """Gold shield-ish badge with crossed sword strokes, drawn at runtime."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    qp = QPainter(pm)
    qp.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88)
    qp.setBrush(QBrush(QColor(43, 45, 49)))
    qp.setPen(QPen(ACCENT, size * 0.06))
    qp.drawRoundedRect(r, size * 0.2, size * 0.2)
    qp.setPen(QPen(QColor(230, 230, 230), size * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    qp.drawLine(int(size * 0.3), int(size * 0.7), int(size * 0.7), int(size * 0.3))
    qp.drawLine(int(size * 0.3), int(size * 0.3), int(size * 0.7), int(size * 0.7))
    qp.setPen(ACCENT)
    f = QFont("Segoe UI", int(size * 0.13), QFont.Weight.Black)
    qp.setFont(f)
    qp.drawText(QRectF(0, size * 0.72, size, size * 0.22), Qt.AlignmentFlag.AlignCenter, "CoB")
    qp.end()
    return QIcon(pm)
