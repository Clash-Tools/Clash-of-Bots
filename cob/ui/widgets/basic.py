"""Display widgets: labels, cards, stat tiles, pills, chips, banners, the unsaved-changes bar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from cob.core.i18n import tr
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon, pixmap


def label(text: str = "", role: str | None = None, wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if role:
        lab.setProperty("role", role)
    lab.setWordWrap(wrap)
    return lab


def eyebrow(text: str, accent: bool = False) -> QLabel:
    """Small uppercase section label ("CYCLES LIMIT")."""
    return label(text.upper(), "eyebrowAccent" if accent else "eyebrow")


class IconLabel(QLabel):
    """A Material Symbol as a label (not clickable)."""

    def __init__(self, name: str, size: int = 20, color: str = t.ON_SURFACE_VARIANT, filled: bool = False):
        super().__init__()
        self.setFixedSize(size, size)
        self.set_icon(name, color, filled)
        self._size = size

    def set_icon(self, name: str, color: str, filled: bool = False) -> None:
        self.setPixmap(pixmap(name, self.width(), color, filled))


class Card(QFrame):
    """Rounded surface with an optional header row: icon, title, right-aligned tag/actions.

    Put content into `card.body` (a QVBoxLayout)."""

    def __init__(self, title: str = "", icon_name: str | None = None, tag: str | None = None,
                 tone: str = "true", padding: int = t.LG, header: bool = False):
        super().__init__()
        self.setProperty("card", tone)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(padding, padding, padding, padding)
        outer.setSpacing(t.MD)
        self.header = QHBoxLayout()
        self.header.setSpacing(t.SM)
        if icon_name:
            self.header.addWidget(IconLabel(icon_name, 22, t.PRIMARY))
        self.title = label(title, "title")
        if title:
            self.header.addWidget(self.title)
        self.header.addStretch(1)
        if tag:
            self.tag = label(tag.upper(), "tag")
            self.header.addWidget(self.tag)
        if title or icon_name or tag or header:
            outer.addLayout(self.header)
        self.body = QVBoxLayout()
        self.body.setSpacing(t.MD)
        outer.addLayout(self.body)


class StatTile(QFrame):
    """KPI tile: eyebrow + icon dot, big mono value, small sub line ("+0 harvested")."""

    def __init__(self, caption: str, icon_name: str, color: str = t.ON_SURFACE, unit: str = ""):
        super().__init__()
        self.setProperty("card", "true")
        self.setMinimumHeight(128)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(t.MD + 4, t.MD + 4, t.MD + 4, t.MD)
        top = QHBoxLayout()
        top.addWidget(eyebrow(caption))
        top.addStretch(1)
        dot = QLabel()
        dot.setFixedSize(28, 28)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setPixmap(pixmap(icon_name, 16, color, filled=True))
        dot.setStyleSheet(f"background: {t.OVERLAY_SOFT}; border-radius: 14px;")
        top.addWidget(dot)
        lay.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.value = label("0", "stat")
        self.value.setStyleSheet(f"color: {color};")
        row.addWidget(self.value)
        if unit:
            u = label(unit, "muted")
            row.addWidget(u, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        lay.addLayout(row)
        self.sub = label("", "mono")
        self.sub.setStyleSheet(f"color: {color if color != t.ON_SURFACE else t.ON_SURFACE_VARIANT};")
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str | None = None) -> None:
        self.value.setText(value)
        if sub is not None:
            self.sub.setText(sub)


_PILL = {  # state -> (background, text, dot)
    "idle": (t.SURFACE_HIGH, t.ON_SURFACE_VARIANT, t.OUTLINE),
    "running": (t.PRIMARY_CONTAINER, t.ON_PRIMARY_CONTAINER, t.PRIMARY),
    "break": (t.WARNING_TINT, t.ON_TERTIARY_CONTAINER, t.TERTIARY),
    "stopped": (t.ERROR_CONTAINER, t.ON_ERROR_CONTAINER, t.ERROR),
    "connecting": (t.SECONDARY_CONTAINER, t.ON_SURFACE, t.SECONDARY),
}
_PILL_TEXT = {"idle": tr("Idle"), "running": tr("Running"), "break": tr("Break"), "stopped": tr("Stopped"),
              "connecting": tr("Connecting")}  # shown when the caller passes no text


class StatusPill(QLabel):
    """Run-state pill: dot + UPPERCASE state text; colour per state (icon + text, never colour alone)."""

    def __init__(self, state: str = "idle", text: str | None = None):
        super().__init__()
        self.setFixedHeight(28)  # radius must stay <= half the height or Qt draws square corners
        self.set_state(state, text)

    def set_state(self, state: str, text: str | None = None) -> None:
        bg, fg, dot = _PILL.get(state, _PILL["idle"])
        self.state = state
        caption = (text or _PILL_TEXT.get(state, state)).upper()
        self.setText(f"<span style='color:{dot}'>●</span>&nbsp;&nbsp;{caption}")
        self.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 14px; padding: 0 14px; "
                           "font-size: 12px; font-weight: 600; letter-spacing: 1px;")


class Chip(QPushButton):
    """Small rounded chip: optional icon, checkable for filters."""

    def __init__(self, text: str, icon_name: str | None = None, checkable: bool = False,
                 color: str = t.ON_SURFACE_VARIANT):
        super().__init__(text)
        self.setProperty("chip", True)
        self.setCheckable(checkable)
        if icon_name:
            self.setIcon(icon(icon_name, color, 16))
        self.setCursor(Qt.CursorShape.PointingHandCursor)


_BANNER = {
    "error": (t.ERROR_CONTAINER, t.ON_ERROR_CONTAINER, "gpp_maybe"),
    "warning": (t.WARNING_TINT, t.ON_TERTIARY_CONTAINER, "warning"),
    "info": (t.SURFACE_HIGH, t.ON_SURFACE, "info"),
}


class Banner(QFrame):
    """Full-width message: icon, title + text, optional action button."""

    action = Signal()

    def __init__(self, tone: str = "info", title: str = "", text: str = "", action_text: str | None = None):
        super().__init__()
        bg, fg, ic = _BANNER[tone]
        self.setStyleSheet(f"QFrame {{ background: {bg}; border-radius: {t.RADIUS_CARD}px; }} "
                           f"QLabel {{ color: {fg}; background: transparent; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(t.MD + 4, t.MD, t.MD, t.MD)
        lay.setSpacing(t.MD)
        lay.addWidget(IconLabel(ic, 24, fg, filled=True), 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title = label(title)
        self.title.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {fg};")
        self.text = label(text, wrap=True)
        texts.addWidget(self.title)
        texts.addWidget(self.text)
        lay.addLayout(texts, 1)
        if action_text:
            btn = QPushButton(action_text)
            btn.setStyleSheet(f"background: {t.OVERLAY}; color: {fg};")
            btn.clicked.connect(self.action)
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_text(self, title: str, text: str) -> None:
        self.title.setText(title)
        self.text.setText(text)


class UnsavedBar(QFrame):
    """Sticky bar shown while a form has unsaved changes: message + Discard / Save."""

    discard = Signal()
    save = Signal()

    def __init__(self, message: str = tr("You have unsaved changes")):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background: {t.SURFACE_HIGHEST}; border-radius: {t.RADIUS_CARD}px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(t.MD + 4, t.SM, t.SM, t.SM)
        lay.addWidget(IconLabel("info", 18, t.TERTIARY))
        lay.addWidget(label(message), 1)
        d = QPushButton(tr("Discard"))
        d.setObjectName("text")
        d.clicked.connect(self.discard)
        s = QPushButton(tr("Save changes"))
        s.setObjectName("tonal")
        s.setIcon(icon("check", t.ON_SURFACE, 18))
        s.clicked.connect(self.save)
        lay.addWidget(d)
        lay.addWidget(s)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.hide()


def hline() -> QWidget:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {t.DIVIDER};")
    return line
