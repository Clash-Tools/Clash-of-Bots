"""Scripted fake device + clock for task tests on real fixture frames (no real waiting)."""

from pathlib import Path

import cv2

FRAMES = Path(__file__).parent / "fixtures" / "frames"
COC = "com.supercell.clashofclans"


class FakeDevice:
    """Shows frames in order. A tap / Back / app start moves to the next frame (the game reacted).

    A name prefixed with "~" advances by itself after `auto_after` captures (loading, clouds).
    """

    serial = "fake"

    def __init__(self, *names: str, foreground: str = COC, auto_after: int = 2):
        self.auto = [n.startswith("~") for n in names]
        self.names = [n.lstrip("~") for n in names]
        self.frames = [cv2.imread(str(FRAMES / f"{n}.jpg")) for n in self.names]
        self.foreground = foreground
        self.auto_after = auto_after
        self.i = 0
        self._captures_here = 0
        self.actions: list[tuple] = []

    @property
    def showing(self) -> str:
        return self.names[self.i]

    def capture(self):
        frame = self.frames[self.i]
        self._captures_here += 1
        if self.auto[self.i] and self._captures_here >= self.auto_after:
            self._advance()
        return frame

    def _advance(self):
        self.i = min(self.i + 1, len(self.frames) - 1)
        self._captures_here = 0

    def tap(self, x, y):
        self.actions.append(("tap", x, y, self.showing))
        self._advance()

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        self.actions.append(("swipe", x1, y1, x2, y2, self.showing))
        self._advance()

    def key(self, keycode):
        self.actions.append(("key", keycode, self.showing))
        self._advance()

    def foreground_package(self):
        return self.foreground

    def app_stop(self, package):
        self.actions.append(("stop",))

    def app_start(self, package):
        self.actions.append(("start",))
        self.foreground = package
        self._advance()


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s
