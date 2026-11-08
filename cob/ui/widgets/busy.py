"""Loading feedback for buttons whose work runs in the background (#161): the button is disabled and
its icon turns into a spinning arrow until the job ends, then the button gets its own icon back."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QIcon, QPixmap, QTransform
from PySide6.QtWidgets import QAbstractButton

from cob.ui.style import tokens as t
from cob.ui.style.icons import pixmap


class Spinner(QObject):
    """Rotates one arrow icon on a set of buttons while they are busy."""

    STEP_MS = 80

    def __init__(self, parent: QObject | None = None, size: int = 18):
        super().__init__(parent)
        self._base = pixmap("autorenew", size, t.ON_SURFACE_VARIANT)
        self._angle = 0
        self._buttons: dict[QAbstractButton, QIcon] = {}  # button -> its own icon
        self._timer = QTimer(self, interval=self.STEP_MS)
        self._timer.timeout.connect(self._turn)

    def start(self, *buttons: QAbstractButton) -> None:
        for b in buttons:
            if b in self._buttons:
                continue
            self._buttons[b] = b.icon()
            b.setEnabled(False)
            b.setProperty("busy", True)
        if self._buttons and not self._timer.isActive():
            self._turn()
            self._timer.start()

    def stop(self, *buttons: QAbstractButton) -> None:
        """Own icon back and enabled again; the job's own callback runs after and may disable it (e.g.
        while a run is going)."""
        for b in buttons:
            own = self._buttons.pop(b, None)
            if own is None:
                continue
            b.setIcon(own)
            b.setEnabled(True)
            b.setProperty("busy", False)
        if not self._buttons:
            self._timer.stop()

    def busy(self, button: QAbstractButton) -> bool:
        return button in self._buttons

    def _turn(self) -> None:
        self._angle = (self._angle + 30) % 360
        turned = self._base.transformed(QTransform().rotate(self._angle))
        # rotating grows the pixmap; crop back to the original size around the centre
        dx, dy = (turned.width() - self._base.width()) // 2, (turned.height() - self._base.height()) // 2
        frame = QPixmap(turned.copy(dx, dy, self._base.width(), self._base.height()))
        frame.setDevicePixelRatio(self._base.devicePixelRatio())
        icon = QIcon(frame)
        for b in list(self._buttons):
            try:
                b.setIcon(icon)
            except RuntimeError:  # the button was deleted while busy
                self._buttons.pop(b, None)
