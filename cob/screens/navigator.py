"""Navigator: get back to HOME from wherever the game is, using each screen's `to_home` action.

Acts only on a screen seen on `confirm` consecutive frames, so transition frames (fades, pop-in
animations) never trigger taps. UNKNOWN never gets blind input (Back can exit the game): wait, and
restart the app if it is not in front or stays unrecognised too long.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import cv2
import numpy as np

from cob.core.human import Humanizer
from cob.core.snapshots import save_snapshot
from cob.device.base import COC_PACKAGE, Device, GameCrashed, PhoneLocked
from cob.screens.classifier import UNKNOWN, Classification, ScreenClassifier
from cob.vision.frame import Frame
from cob.vision.match import match
from cob.vision.templates import TemplateMissing

log = logging.getLogger(__name__)

HOME = "HOME"
LOADING = "LOADING"
UNAVAILABLE = frozenset({LOADING, UNKNOWN})  # #118: go_home stuck here = game down (maintenance, servers)


@dataclass(frozen=True)
class NavConfig:
    timeout_s: float = 240.0  # covers a full battle (3 min) left to run out
    confirm: int = 2  # consecutive equal classifications before acting
    settle_s: float = 1.0  # pause after an action so the UI can react
    poll_s: float = 0.5  # pause between captures while waiting
    unknown_check_s: float = 5.0  # UNKNOWN this long -> check the game is the foreground app
    unknown_restart_s: float = 45.0  # UNKNOWN this long with the game in front -> restart it
    restart_wait_s: float = 5.0  # pause after a restart before looking again
    max_swipes: int = 6  # map drags per go_home (small steps: a HUD button can hide the target)
    max_restarts: int = 1
    max_crashes: int = 1  # crash dialogs answered with a restart before the run stops
    max_fronts: int = 3  # times another app in front is answered by opening the game, before a restart


@dataclass
class NavResult:
    ok: bool
    steps: list[str] = field(default_factory=list)  # "SCREEN:action" in order, for logs and tests
    stopped_on: str | None = None  # screen whose action is "stop" (e.g. village open on another device)


class Navigator:
    def __init__(self, device: Device, classifier: ScreenClassifier, config: NavConfig | None = None, *,
                 stop: threading.Event | None = None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] | None = None, human: Humanizer | None = None):
        self.device = device
        self.last_unwanted = None  # (screen, frame) last seen instead of what a wait_for wanted
        self.human = human or Humanizer()  # shared by the tasks for all taps
        self.on_frame: Callable[[Frame, Classification], None] | None = None  # GUI live preview
        self._swipes = 0  # map drags in the current go_home
        self._zoomed = False  # one zoom-out per go_home
        self._crashes = 0  # crash dialogs since the village (or another wanted screen) last showed
        self.stuck_on: str | None = None  # #118: LOADING / UNKNOWN when the last go_home timed out there
        self.classifier = classifier
        self.store = classifier.store
        self.cfg = config or NavConfig()
        self.stop = stop or threading.Event()
        self._clock = clock
        self._sleep = sleep or self._interruptible_sleep
        self._actions = {d.name: d.to_home for d in classifier.defs}

    def _interruptible_sleep(self, seconds: float) -> None:
        self.stop.wait(seconds)

    def tap_match(self, hit) -> None:
        """Tap somewhere inside a matched template (not always its centre pixel)."""
        self.device.tap(*self.human.in_box(hit.x, hit.y, hit.w, hit.h))

    def now(self) -> float:
        """Monotonic seconds (fake clock in tests)."""
        return self._clock()

    def sleep(self, seconds: float) -> None:
        """Pause that the stop event interrupts (fake clock in tests)."""
        self._sleep(seconds)

    def classify(self) -> tuple[Classification, Frame]:
        frame = Frame(self.device.capture())
        cls = self.classifier.classify(frame)
        if self.on_frame is not None:
            try:
                self.on_frame(frame, cls)
            except Exception as exc:  # a preview must never break the bot
                log.debug("on_frame observer failed: %s", exc)
        return cls, frame

    def wait_for(self, screens: set[str] | frozenset[str], timeout_s: float
                 ) -> tuple[Classification, Frame] | None:
        """Wait until one of `screens` is seen on `confirm` consecutive frames; None on timeout/stop.

        Screens can open seconds after the tap (shop ~4.5 s), so never act before this confirms.
        """
        start = self._clock()
        last, streak, tries = None, 0, 0
        seen: list[str] = []
        self.last_unwanted = None
        # Slow captures (phone on Wi-Fi: up to ~5 s each) fit only one or two frames in a short timeout,
        # so a confirm always gets its frames even past the deadline (live 2026-11-05: an attack gave up
        # 10 s after the battle screen was already showing).
        while not self.stop.is_set() and (self._clock() - start <= timeout_s or tries <= self.cfg.confirm):
            cls, frame = self.classify()
            tries += 1
            # Any of the wanted screens counts towards the streak: search turning into the battle when the
            # scout timer runs out is still a screen the caller can work with.
            same = cls.screen == last or (cls.screen in screens and last in screens)
            streak = streak + 1 if same else 1
            last = cls.screen
            seen.append(cls.screen)
            if cls.screen not in screens:
                self.last_unwanted = (cls.screen, frame)
            if cls.screen in screens and streak >= self.cfg.confirm:
                return cls, frame
            self._sleep(self.cfg.poll_s)
        # #170: what was on screen instead, for the failure report's log
        log.info("waited %.0f s for %s; saw %s", self._clock() - start, "/".join(sorted(screens)),
                 _runs(seen) or "nothing")
        return None

    def wait_leave(self, screen: str, timeout_s: float) -> bool:
        """Wait until `screen` is gone (e.g. the old base after Next); False on timeout/stop."""
        start = self._clock()
        while not self.stop.is_set() and self._clock() - start <= timeout_s:
            if self.classify()[0].screen != screen:
                return True
            self._sleep(self.cfg.poll_s)
        return False

    def go_home(self, arrive: frozenset[str] | set[str] = frozenset({HOME})) -> NavResult:
        """Follow to_home actions until one of `arrive` is confirmed (default: the home village).

        Builder Base tasks pass {HOME, BB_HOME} so a BB screen counts as arrived instead of being
        left by boat.
        """
        result = NavResult(ok=False)
        self.stuck_on = None
        self._swipes = 0
        self._zoomed = False
        start = self._clock()
        last, streak = None, 0
        unknown_since: float | None = None
        restarts = fronts = 0
        while not self.stop.is_set():
            if self._clock() - start > self.cfg.timeout_s:
                log.warning("go_home timed out after %.0fs: %s", self.cfg.timeout_s, " > ".join(result.steps))
                self.stuck_on = last if last in UNAVAILABLE else None
                return result
            cls, frame = self.classify()
            screen = cls.screen
            streak = streak + 1 if screen == last else 1
            last = screen
            if streak < self.cfg.confirm:
                self._sleep(self.cfg.poll_s)
                continue

            if screen in arrive:
                self._crashes = 0
                result.ok = True
                return result

            if screen == UNKNOWN:
                now = self._clock()
                first = unknown_since is None
                unknown_since = now if first else unknown_since
                waited = now - unknown_since
                reason = None
                if first or waited >= self.cfg.unknown_check_s:
                    self._check_unlocked()
                    if self._game_crashed(frame):
                        self._step(result, screen, "restart (game crashed)")
                        self.device.app_stop(COC_PACKAGE)  # also closes Android's dialog
                        self.device.app_start(COC_PACKAGE)
                        unknown_since, streak = None, 0
                        self._sleep(self.cfg.restart_wait_s)
                        continue
                    if self._shade_open():
                        # #178: the notification shade over the game hides every anchor: close it.
                        self._step(result, screen, "close notification shade")
                        self._close_shade()
                        unknown_since, streak = None, 0
                        self._sleep(self.cfg.poll_s)
                        continue
                    if self._game_not_in_front():
                        if fronts < self.cfg.max_fronts:
                            # Another app (settings, launcher, a notification's app) over the game:
                            # open the game again at once, without closing it (#147).
                            self._step(result, screen, "open game (another app in front)")
                            self.device.app_start(COC_PACKAGE)
                            fronts += 1
                            unknown_since, streak = None, 0
                            self._sleep(self.cfg.restart_wait_s)
                            continue
                        reason = "restart (game not in front)"
                if reason is None and waited >= self.cfg.unknown_restart_s:
                    reason = "restart"
                if reason and restarts < self.cfg.max_restarts:
                    self._step(result, screen, reason)
                    save_snapshot(frame.bgr, f"unknown_before_{reason.split()[0]}", device=self.device)
                    self.device.app_stop(COC_PACKAGE)
                    self.device.app_start(COC_PACKAGE)
                    restarts += 1
                    unknown_since, streak = None, 0
                    self._sleep(self.cfg.restart_wait_s)
                else:
                    self._sleep(self.cfg.poll_s)
                continue

            unknown_since = None
            action = self._actions.get(screen, "wait")
            if action == "stop":
                self._step(result, screen, "stop")
                log.warning("nav: stopped on %s", screen)
                result.stopped_on = screen
                return result
            if self._do(action, frame, cls):
                self._step(result, screen, action)
                streak = 0  # the screen should change; re-confirm before acting again
                self._sleep(self.cfg.settle_s)
            else:
                self._sleep(self.cfg.poll_s)
        return result

    def game_unavailable(self) -> bool:
        """#118: the last go_home ran out of time on the loading screen or an unrecognised one (after
        its restart): maintenance, a server outage or an update screen, not something a tap fixes."""
        return self.stuck_on is not None

    def _check_unlocked(self) -> None:
        """Phones only: an unknown screen may be the lock screen (portrait, nothing matches). Wake the
        screen once; still locked -> PhoneLocked, because restarting the game cannot help (#86)."""
        locked = getattr(self.device, "locked", None)
        if not callable(locked) or not locked():
            return
        self.device.key("KEYCODE_WAKEUP")
        self._sleep(1.0)
        if locked():
            raise PhoneLocked("phone locked during the run: unlock it and start again")

    def reload_other_device(self) -> bool:
        """Tap RELOAD on "Another device is connecting to this Village" (#117, only after the opt-in
        wait: reloading takes the village back from whoever opened it). False when that popup is not up."""
        cls, frame = self.classify()
        if cls.screen != "POPUP_OTHER_DEVICE":
            return False
        return self._do("tap other_device_reload", frame, cls)

    def _game_crashed(self, frame: Frame) -> bool:
        """Android's "Clash of Clans keeps stopping" dialog is up. The first crash gets one restart; a
        second one before the village shows stops the run: restarting a game that dies while loading
        only loops (live 2026-11-04, `smxuhbhxh.aG: 16` on every start)."""
        crashed = getattr(self.device, "crashed", None)
        try:
            if not callable(crashed) or not crashed(COC_PACKAGE):
                return False
        except Exception as exc:  # a failed probe is not a crash
            log.debug("crash probe failed: %s", exc)
            return False
        self._crashes += 1
        save_snapshot(frame.bgr, "game_crashed", device=self.device)
        log.warning("Clash of Clans crashed (%d time(s) since the village last showed)", self._crashes)
        if self._crashes > self.cfg.max_crashes:
            raise GameCrashed("Clash of Clans keeps crashing or not responding. Open it on the device by "
                              "hand; if it still stops, update or reinstall it, then start again.")
        return True

    SHADE_WINDOWS = ("NotificationShade", "StatusBar")

    def _shade_open(self) -> bool:
        try:
            return self.device.foreground_package() in self.SHADE_WINDOWS
        except Exception as exc:
            log.debug("foreground probe failed: %s", exc)
            return False

    def _close_shade(self) -> None:
        collapse = getattr(self.device, "collapse_shade", None)
        try:
            collapse() if collapse is not None else self.device.key("KEYCODE_BACK")
        except Exception as exc:
            log.warning("could not close the notification shade: %s", exc)

    def _game_not_in_front(self) -> bool:
        try:
            pkg = self.device.foreground_package()
        except Exception as exc:  # a failed probe must not trigger a restart by itself
            log.debug("foreground probe failed: %s", exc)
            return False
        return pkg is not None and pkg != COC_PACKAGE

    def _step(self, result: NavResult, screen: str, action: str) -> None:
        log.info("nav: %s -> %s", screen, action)
        result.steps.append(f"{screen}:{action}")

    def _do(self, action: str, frame: Frame, cls: Classification) -> bool:
        """Run one to_home action ('stop' is handled by go_home). False for 'wait' / no tap target.

        "A else B" runs B when A did nothing (e.g. tap the boat, else drag the map to bring it in view).
        """
        if " else " in action:
            first, fallback = action.split(" else ", 1)
            return self._do(first, frame, cls) or self._do(fallback, frame, cls)
        verb, *args = action.split()
        if verb == "wait":
            return False
        if verb == "back":
            self.device.key("KEYCODE_BACK")
            return True
        if verb == "tap":
            for name in args:
                hit = cls.matches.get(name) or self._find(frame, name)
                if hit is not None:
                    self.tap_match(hit)
                    return True
            log.debug("nav: none of %s visible", args)
            return False
        if verb == "zoom":  # zoom the camera out; nothing done when it is already fully out
            if self._zoomed:
                return False
            self._zoomed = True
            return self.zoom_out() > 0
        if verb == "swipe":  # drag the map on a confirmed screen, never on UNKNOWN (D-015)
            if self._swipes >= self.cfg.max_swipes:
                return False  # stop dragging; the unknown-screen / timeout rules take over
            self._swipes += 1
            x1, y1, x2, y2 = (int(a) for a in args[:4])
            self.device.swipe(x1, y1, x2, y2, 600)
            return True
        raise ValueError(f"unknown to_home action {action!r}")

    def zoom_out(self, max_pinches: int = 3, settle_s: float = 1.0, min_change: float = 8.0) -> int:
        """Pinch until the camera stops moving (live: one pinch from a zoomed-in camera changes the
        view by ~40 grey levels, a pinch at full zoom-out by ~2, i.e. animation noise). Every screen
        keeps its own zoom: the battle view does NOT inherit the village zoom. Returns pinches that
        moved the camera; 0 when the device cannot pinch."""
        if not hasattr(self.device, "pinch"):
            return 0
        moved = 0
        before = _thumb(self.device.capture())
        for _ in range(max_pinches):
            if not self.device.pinch():
                return moved
            self.sleep(settle_s)
            after = _thumb(self.device.capture())
            change = float(np.abs(after - before).mean())
            log.debug("zoom out: view change %.1f", change)
            if change < min_change:
                break
            moved += 1
            before = after
        return moved

    def _find(self, frame: Frame, name: str):
        try:
            return match(frame, self.store.get(name))
        except TemplateMissing:
            return None


def _thumb(bgr: np.ndarray) -> np.ndarray:
    """Small grey copy of the playfield (HUD rows cut off) for "did the camera move" checks."""
    h = bgr.shape[0]
    return cv2.resize(cv2.cvtColor(bgr[h // 6:h * 4 // 5], cv2.COLOR_BGR2GRAY), (160, 64)).astype(np.int16)


def _runs(screens: list[str]) -> str:
    """'HOME x3, UNKNOWN, ATTACK_MENU x2': consecutive classifications, run-length encoded."""
    out: list[list] = []
    for name in screens:
        if out and out[-1][0] == name:
            out[-1][1] += 1
        else:
            out.append([name, 1])
    return ", ".join(name if n == 1 else f"{name} x{n}" for name, n in out)
