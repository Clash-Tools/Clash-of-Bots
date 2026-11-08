"""Forward log records to the GUI thread through Qt signals (logging handlers run on any thread)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class LogLine:
    """One record for the Logs page: filterable by level and searchable by text."""

    time: str
    level: str  # INFO / WARNING / ERROR / CRITICAL / DEBUG
    module: str
    message: str

    def text(self) -> str:
        return f"{self.time} {self.level:<7} {self.module}: {self.message}"


class LogBridge(QObject):
    line = Signal(str)  # formatted text (dashboard activity)
    record = Signal(object)  # LogLine (Logs page)


class QtLogHandler(logging.Handler):
    def __init__(self, bridge: LogBridge, level: int = logging.INFO):
        super().__init__(level)
        self.bridge = bridge
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
            line = LogLine(text[:8], record.levelname, record.name.removeprefix("cob."), record.getMessage())
            self.bridge.line.emit(text)
            self.bridge.record.emit(line)
        except RuntimeError:  # window already gone during shutdown
            pass
