"""Register the bundled fonts (OFL) so the stylesheet's families resolve on every PC."""

from __future__ import annotations

import logging

from PySide6.QtGui import QFontDatabase

from cob.core.paths import app_root

log = logging.getLogger(__name__)

_loaded: list[str] | None = None


def load_fonts() -> list[str]:
    """Idempotent; returns the family names now available (empty when the assets are missing)."""
    global _loaded
    if _loaded is not None:
        return _loaded
    families: list[str] = []
    for path in sorted((app_root() / "assets" / "fonts").glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            log.warning("font %s could not be loaded", path.name)
            continue
        families += QFontDatabase.applicationFontFamilies(font_id)
    _loaded = families
    return families
