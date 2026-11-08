"""Run one blocking call (device checks, emulator start, a capture) off the GUI thread."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class Job(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object], parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self._fn())
        except Exception as exc:
            log.warning("background job failed: %s", exc)
            self.failed.emit(str(exc))
