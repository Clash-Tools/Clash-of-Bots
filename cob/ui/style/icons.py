"""Material Symbols icons from bundled SVGs (Apache 2.0), tinted to any colour and cached."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from cob.core.paths import app_root
from cob.ui.style import tokens


def icon_path(name: str, filled: bool = False):
    folder = app_root() / "assets" / "icons" / ("filled" if filled else "outlined")
    path = folder / f"{name}.svg"
    if not path.is_file():
        raise KeyError(f"icon '{name}' is not bundled (assets/icons)")
    return path


@lru_cache(maxsize=512)
def pixmap(name: str, size: int = 20, color: str = tokens.ON_SURFACE, filled: bool = False,
           dpr: float = 2.0) -> QPixmap:
    """The SVGs are single-colour black paths: render, then paint `color` through their alpha."""
    px = max(1, round(size * dpr))
    img = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    QSvgRenderer(str(icon_path(name, filled))).render(painter, QRectF(0, 0, px, px))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(img.rect(), QColor(color))
    painter.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str = tokens.ON_SURFACE, size: int = 20, filled: bool = False,
         disabled_color: str = tokens.OUTLINE) -> QIcon:
    ic = QIcon(pixmap(name, size, color, filled))
    ic.addPixmap(pixmap(name, size, disabled_color, filled), QIcon.Mode.Disabled)
    return ic
