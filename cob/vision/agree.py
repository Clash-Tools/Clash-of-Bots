"""Never trust one frame: re-read until consecutive frames agree (screens fade and pop in)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from cob.vision.frame import Frame


def read_stable[T](capture: Callable[[], Frame], read: Callable[[Frame], T | None], need: int = 2,
                max_frames: int = 6, interval_s: float = 0.15,
                stop: threading.Event | None = None, first: Frame | None = None) -> T | None:
    """Return a value once `need` consecutive frames read the same non-None value, else None.
    `first`: a frame the caller already captured, used as the first frame (one capture less)."""
    last: T | None = None
    streak = 0
    for i in range(max_frames):
        if i == 0 and first is not None:
            value = read(first)
            streak, last = (1 if value is not None else 0), value
            continue
        if i:
            if stop is None:
                time.sleep(interval_s)
            elif stop.wait(interval_s):
                return None
        value = read(capture())
        if value is not None and value == last:
            streak += 1
        else:
            streak = 1 if value is not None else 0
        last = value
        if streak >= need:
            return value
    return None
