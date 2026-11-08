"""Farm loop in a QThread. The window only sees signals: cycle_done, finished_stats, failed."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import cv2
from PySide6.QtCore import QThread, Signal

from cob.tasks.farm import FarmLimits
from cob.tasks.wiring import FarmParts, bb_farm_task

log = logging.getLogger(__name__)


class FarmWorker(QThread):
    cycle_done = Signal(object)  # CycleResult
    finished_stats = Signal(object)  # FarmStats
    failed = Signal(str)
    resting = Signal(float)  # break length in seconds
    preview = Signal(object, str)  # small BGR frame, screen name (throttled)
    step = Signal(str)  # farm loop step: collect / search / attack / return / break

    PREVIEW_EVERY_S = 2.0
    PREVIEW_SIZE = (480, 270)

    def __init__(self, build: Callable[[], FarmParts], limits: FarmLimits, parent=None, mode: str = "home"):
        super().__init__(parent)
        self._mode = mode  # "home" (home village farm) or "bb" (Builder Base attacks)
        self._last_preview = 0.0
        self._build = build
        self._limits = limits
        self._stop_requested = threading.Event()
        self._pause = threading.Event()  # #133: shared with the farm task; set = hold between cycles
        self._parts: FarmParts | None = None

    def run(self) -> None:
        try:
            self._parts = self._build()
            nav = getattr(self._parts, "nav", None)
            if nav is not None and hasattr(nav, "on_frame"):
                nav.on_frame = self._on_frame  # reuse the bot's own captures: no extra adb traffic
            if self._stop_requested.is_set():
                self._parts.nav.stop.set()
            if self._mode == "bb":
                task = bb_farm_task(self._parts, self._limits, on_cycle=self.cycle_done.emit,
                                    on_break=self.resting.emit, on_step=self.step.emit)
            else:
                task = self._parts.farm_task(self._limits, on_cycle=self.cycle_done.emit,
                                             on_break=self.resting.emit, on_step=self.step.emit)
            task.pause = self._pause
            self.finished_stats.emit(task.run())
        except Exception as exc:  # device missing, assets broken, ...: show it, never crash the GUI
            log.exception("farm worker failed")
            self.failed.emit(str(exc))
        finally:
            if self._parts is not None:
                try:
                    self._parts.close()
                except Exception:
                    log.exception("closing the device failed")

    def _on_frame(self, frame, cls) -> None:
        now = time.monotonic()
        if now - self._last_preview < self.PREVIEW_EVERY_S:
            return
        self._last_preview = now
        self.preview.emit(cv2.resize(frame.bgr, self.PREVIEW_SIZE, interpolation=cv2.INTER_AREA), cls.screen)

    def set_paused(self, paused: bool) -> None:
        """#133: hold after the current cycle (paused) or carry on; session stats are kept."""
        if paused:
            self._pause.set()
        else:
            self._pause.clear()

    def is_paused(self) -> bool:
        return self._pause.is_set()

    def request_stop(self) -> None:
        """Finish the current step and stop (Ctrl+C equivalent); safe before the bot is built."""
        self._stop_requested.set()
        if self._parts is not None:
            self._parts.nav.stop.set()
