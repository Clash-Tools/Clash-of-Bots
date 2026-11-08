"""Setup tab "Scan QR" dialog: show a pairing QR code and wait for the phone (D-025)."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QVBoxLayout

from cob.core.i18n import tr
from cob.device import qr_pair

STEPS = tr(
    "<b>On the phone</b> (same Wi-Fi as this PC, Android 11 or newer):<ol>"
    "<li>Settings &gt; Developer options &gt; <b>Wireless debugging</b>: turn it on</li>"
    "<li>Tap <b>Pair device with QR code</b></li>"
    "<li>Scan this code</li></ol>"
    "The bot connects by itself afterwards, also after the phone restarts (turn Wireless debugging "
    "on again)."
)


def qr_pixmap(text: str, size: int = 280) -> QPixmap:
    rows = qr_pair.qr_matrix(text)
    n = len(rows)
    img = QImage(n, n, QImage.Format.Format_RGB32)
    dark, light = QColor(0, 0, 0).rgb(), QColor(255, 255, 255).rgb()
    for y, row in enumerate(rows):
        for x, on in enumerate(row):
            img.setPixel(x, y, dark if on else light)
    # Nearest-neighbour scaling keeps the modules sharp for the phone camera.
    return QPixmap.fromImage(img.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.FastTransformation))


class _PairThread(QThread):
    status = Signal(str)
    paired = Signal(str)
    failed = Signal(str)

    def __init__(self, session: qr_pair.QrSession, parent=None):
        super().__init__(parent)
        self.session = session
        self.stop = threading.Event()

    def run(self) -> None:
        try:
            self.paired.emit(qr_pair.pair_and_connect(self.session, on_status=self.status.emit,
                                                      stop=self.stop))
        except Exception as exc:
            self.failed.emit(str(exc))


class QrPairDialog(QDialog):
    """Accepted with `serial` set once the phone is connected."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Pair a phone with a QR code"))
        self.serial: str | None = None
        self.session = qr_pair.new_session()

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.qr = QLabel()
        self.qr.setPixmap(qr_pixmap(self.session.qr_text))
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.qr)
        steps = QLabel(STEPS)
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(steps, 1)
        lay.addLayout(row)
        self.countdown = QLabel()
        self.status = QLabel(tr("Starting…"))
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addWidget(self.countdown)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)

        self._left = int(qr_pair.TIMEOUT_S)
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(self._tick)
        self._tick()
        self._timer.start()

        self._thread = _PairThread(self.session, self)
        self._thread.status.connect(self.status.setText)
        self._thread.paired.connect(self._on_paired)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _tick(self) -> None:
        self.countdown.setText(tr("Code valid for {n} s", n=self._left))
        self._left = max(0, self._left - 1)

    def _on_paired(self, serial: str) -> None:
        self.serial = serial
        self._timer.stop()
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._timer.stop()
        self.countdown.setText("")
        self.status.setText(tr("error: {message}", message=message))
        self.qr.setEnabled(False)
        self.buttons.setStandardButtons(QDialogButtonBox.StandardButton.Close)

    def done(self, result: int) -> None:  # Cancel, Close, Esc and accept all end here
        self._thread.stop.set()
        self._thread.wait(3000)
        super().done(result)
