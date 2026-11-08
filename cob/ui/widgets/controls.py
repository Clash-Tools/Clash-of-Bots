"""Input widgets: segmented control, M3 switch, toggle row, number field with unit and hint."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets.basic import eyebrow, label


class SegmentedControl(QFrame):
    """Exclusive options in a dark track ("Home Village | Builder Base"); `changed` emits the value."""

    changed = Signal(object)

    def __init__(self, options: list[tuple[str, object, str | None]]):
        """options: (text, value, icon name or None)."""
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background: {t.SURFACE_LOWEST}; border-radius: 10px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self._group = QButtonGroup(self)
        self._values: dict[int, object] = {}
        for i, (text, value, icon_name) in enumerate(options):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if icon_name:
                b.setIcon(icon(icon_name, t.ON_SURFACE, 18))
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {t.ON_SURFACE_VARIANT}; border-radius: 8px; "
                f"padding: 8px 16px; }} QPushButton:checked {{ background: {t.PRIMARY_CONTAINER}; "
                f"color: {t.ON_PRIMARY_CONTAINER}; font-weight: 600; }} "
                f"QPushButton:hover:!checked {{ background: {t.SURFACE_HIGH}; }}")
            self._group.addButton(b, i)
            self._values[i] = value
            lay.addWidget(b, 1)
        self._group.idClicked.connect(lambda i: self.changed.emit(self._values[i]))
        if options:
            self._group.button(0).setChecked(True)

    def value(self) -> object:
        return self._values[self._group.checkedId()]

    def set_value(self, value: object) -> None:
        for i, v in self._values.items():
            if v == value:
                self._group.button(i).setChecked(True)


class Switch(QAbstractButton):
    """Material 3 switch: 52x32 track, animated thumb.

    The animated value is the Qt property "thumb" (0 = off, 1 = on). It must not be called "pos":
    that is QWidget's own position property, and animating it moved the switch to its parent's
    corner on every toggle while the thumb never moved (#105)."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(52, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._thumb = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"thumb", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(52, 32)

    def _get_thumb(self) -> float:
        return self._thumb

    def _set_thumb(self, v: float) -> None:
        self._thumb = v
        self.update()

    thumb = Property(float, _get_thumb, _set_thumb)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        if not self.isVisible():  # loading settings into a hidden page: no animation to watch
            self._set_thumb(1.0 if on else 0.0)
            return
        self._anim.setStartValue(self._thumb)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt API name)
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.update()

    @staticmethod
    def _mix(a: str, b: str, k: float) -> QColor:
        ca, cb = QColor(a), QColor(b)
        return QColor.fromRgbF(ca.redF() + (cb.redF() - ca.redF()) * k,
                               ca.greenF() + (cb.greenF() - ca.greenF()) * k,
                               ca.blueF() + (cb.blueF() - ca.blueF()) * k)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = max(0.0, min(1.0, self._thumb))  # colours and size follow the thumb, so nothing jumps
        enabled = self.isEnabled()
        track = self._mix(t.SURFACE_HIGHEST, t.PRIMARY, k)
        border = self._mix(t.OUTLINE, t.PRIMARY, k)
        if not enabled:
            track.setAlphaF(0.4)
        p.setBrush(track)
        p.setPen(border if enabled else Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(1, 1, 50, 30), 15, 15)
        d = 16 + 8 * k
        if enabled and self.underMouse():
            d += 2
        cx = 16 + (36 - 16) * k
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._mix(t.OUTLINE, t.ON_PRIMARY, k))
        p.drawEllipse(QRectF(cx - d / 2, 16 - d / 2, d, d))
        p.end()


class ToggleRow(QFrame):
    """Title + description on the left, switch on the right (settings lists)."""

    def __init__(self, title: str, description: str = "", checked: bool = False,
                 icon_name: str | None = None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, t.SM, 0, t.SM)
        lay.setSpacing(t.MD)
        if icon_name:
            from cob.ui.widgets.basic import IconLabel

            lay.addWidget(IconLabel(icon_name, 22, t.ON_SURFACE_VARIANT), 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        head = label(title)
        head.setStyleSheet("font-weight: 600;")
        texts.addWidget(head)
        if description:
            texts.addWidget(label(description, "muted", wrap=True))
        lay.addLayout(texts, 1)
        self.switch = Switch(checked)
        lay.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)

    def isChecked(self) -> bool:  # noqa: N802 - Qt naming
        return self.switch.isChecked()

    def setChecked(self, on: bool) -> None:  # noqa: N802
        self.switch.setChecked(on)


class NumberField(QWidget):
    """Eyebrow caption, mono spin box with a unit suffix, hint line under it ("Unlimited continuous")."""

    valueChanged = Signal(int)  # noqa: N815 - Qt naming

    def __init__(self, caption: str, minimum: int, maximum: int, value: int = 0, unit: str = "",
                 hint: str = "", step: int = 1):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(eyebrow(caption))
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        self.spin.setGroupSeparatorShown(True)
        if unit:
            self.spin.setSuffix(f"  {unit}")
        self.spin.setMinimumHeight(44)
        self.spin.valueChanged.connect(self.valueChanged)
        lay.addWidget(self.spin)
        self.hint = QLabel(hint)
        self.hint.setProperty("role", "muted")
        self.hint.setVisible(bool(hint))
        lay.addWidget(self.hint)

    def value(self) -> int:
        return self.spin.value()

    def setValue(self, v: int) -> None:  # noqa: N802
        self.spin.setValue(v)

    def set_hint(self, text: str) -> None:
        self.hint.setText(text)
        self.hint.setVisible(bool(text))
