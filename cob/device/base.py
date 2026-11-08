"""Device protocol: the only surface the rest of the bot uses to see and touch the game."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

# D-006: every template and coordinate assumes this frame size (landscape).
TARGET_SIZE = (1600, 900)
TARGET_DPI = 240

COC_PACKAGE = "com.supercell.clashofclans"


class DeviceError(RuntimeError):
    """Device unreachable or a command failed."""


class RunBlocked(DeviceError):
    """Something only the user can fix: the run stops at once instead of retrying."""


class PhoneLocked(RunBlocked):
    """The phone shows its lock screen; the bot cannot unlock it (#86)."""


class GameCrashed(RunBlocked):
    """Clash of Clans crashed again right after a restart (Android's "keeps stopping" dialog)."""


class ResolutionMismatch(DeviceError):
    def __init__(self, actual: tuple[int, int], expected: tuple[int, int] = TARGET_SIZE):
        super().__init__(f"device frame {actual[0]}x{actual[1]}, expected {expected[0]}x{expected[1]}")
        self.actual = actual
        self.expected = expected


@runtime_checkable
class Device(Protocol):
    """Coordinates are frame pixels (x right, y down) in the TARGET_SIZE frame."""

    serial: str

    def capture(self) -> np.ndarray:
        """Return current screen as BGR uint8 array, shape (h, w, 3)."""
        ...

    def tap(self, x: int, y: int) -> None: ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None: ...

    def hold(self, x: int, y: int, duration_ms: int) -> None: ...

    def key(self, keycode: str) -> None: ...

    def app_start(self, package: str = COC_PACKAGE) -> None: ...

    def app_stop(self, package: str = COC_PACKAGE) -> None: ...

    def foreground_package(self) -> str | None:
        """Package of the focused app window, None if unknown."""
        ...

    def screen_size(self) -> tuple[int, int]: ...

    # Optional (AdbDevice): pinch(zoom_in=False) -> bool, two-finger zoom with raw touch events.
