"""Generic ADB device: raw screencap capture + `input` shell commands.

Input via `input tap` costs ~100-250 ms per call (JVM start on device). Good enough for M0;
a faster input backend (uiautomator2 / scrcpy control socket) plugs in behind the same methods later.
"""

from __future__ import annotations

import gzip
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import adbutils
import numpy as np

from cob.core.paths import tools_dir
from cob.core.timing import IoStats
from cob.device.base import COC_PACKAGE, DeviceError
from cob.device.screencap import decode_raw

log = logging.getLogger(__name__)


def find_adb() -> Path | None:
    """Order: COB_ADB env > bundled tools/adb > adb on PATH."""
    if env := os.environ.get("COB_ADB"):
        return Path(env)
    exe = "adb.exe" if sys.platform == "win32" else "adb"
    bundled = tools_dir() / "adb" / exe
    if bundled.is_file():
        return bundled
    found = shutil.which("adb")
    return Path(found) if found else None


def parse_wm(text: str) -> tuple[tuple[int, ...], tuple[int, ...] | None]:
    """`wm size` / `wm density` output -> (physical, override or None); sizes as (w, h), density (d,)."""
    physical: tuple[int, ...] = ()
    override = None
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        nums = tuple(int(n) for n in value.strip().split("x") if n.strip().isdigit())
        if key.strip().startswith("Physical"):
            physical = nums
        elif key.strip().startswith("Override"):
            override = nums
    return physical, override


# Pinch finger paths along the screen's long axis, as fractions of the game area (LDPlayer frame:
# x 300 <-> 1300 and 720 <-> 880 of 1600, at mid height): zoom out = far apart -> close together.
PINCH_FAR, PINCH_NEAR = (300 / 1600, 1300 / 1600), (720 / 1600, 880 / 1600)


def pinch_paths(panel_max: tuple[int, int], physical: tuple[int, int], logical: tuple[int, int] | None,
                zoom_in: bool = False) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Touch-panel coordinates for a two-finger pinch: ((start_a, start_b), (end_a, end_b), (axis, mid)).

    Raw touch events use panel units in the device's natural orientation (LDPlayer: pixels, landscape;
    moto g84: 16 units per pixel, portrait), not frame pixels. The game fills `logical` (a `wm size`
    override, else the physical size) scaled to fit and centred in `physical`. The gesture is symmetric
    around the centre, so whether the game runs at rotation 90 or 270 does not matter. axis 0 = the
    fingers move along panel X, 1 = along panel Y; mid = the other coordinate.
    """
    pw, ph = physical
    lw, lh = logical or physical
    scale = min(pw / lw, ph / lh)
    cw, ch = lw * scale, lh * scale  # game area in physical pixels, natural orientation
    ox, oy = (pw - cw) / 2, (ph - ch) / 2
    to_panel_x = (panel_max[0] + 1) / pw
    to_panel_y = (panel_max[1] + 1) / ph
    if pw >= ph:  # natural landscape: long axis is X
        def along(f: float) -> int:
            return int((ox + cw * f) * to_panel_x)
        axis, mid = 0, int((oy + ch / 2) * to_panel_y)
    else:  # natural portrait (phones): long axis is Y
        def along(f: float) -> int:
            return int((oy + ch * f) * to_panel_y)
        axis, mid = 1, int((ox + cw / 2) * to_panel_x)
    far = (along(PINCH_FAR[0]), along(PINCH_FAR[1]))
    near = (along(PINCH_NEAR[0]), along(PINCH_NEAR[1]))
    start, end = (near, far) if zoom_in else (far, near)
    return start, end, (axis, mid)


def _read_all(sock, chunk: int = 1 << 20) -> bytes:
    """Read a socket to EOF in linear time.

    adbutils' read_until_close does `content += 4 KiB chunk`, which is quadratic: ~1.4 s for one
    5.8 MB 1600x900 frame on LDPlayer 14; this reads it in ~0.3 s (0.46 s per capture).
    """
    parts = []
    while data := sock.recv(chunk):
        parts.append(data)
    return b"".join(parts)


def ensure_adb_server() -> None:
    """adbutils talks to the adb server socket; start the server if none is listening."""
    try:
        adbutils.adb.server_version()
        return
    except Exception:
        pass
    adb = find_adb()
    if adb is None:
        raise DeviceError("adb not found: set COB_ADB or put adb in tools/adb/")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.run([str(adb), "start-server"], check=True, capture_output=True, creationflags=flags)


def list_serials() -> list[str]:
    ensure_adb_server()
    return [d.serial for d in adbutils.adb.device_list()]


def connect(addr: str) -> None:
    """`adb connect host:port` (LDPlayer also exposes 127.0.0.1:5555+2n)."""
    ensure_adb_server()
    msg = adbutils.adb.connect(addr, timeout=5)
    log.debug("adb connect %s: %s", addr, msg)


class AdbDevice:
    @property
    def io(self) -> IoStats:
        """Capture / input / shell call counts and time (#166), created on first use."""
        stats = self.__dict__.get("_io")
        if stats is None:
            stats = self.__dict__["_io"] = IoStats()
        return stats

    def __init__(self, serial: str):
        ensure_adb_server()
        self.serial = serial
        self._dev = adbutils.adb.device(serial)
        try:
            self._dev.get_state()
        except Exception as exc:
            raise DeviceError(f"device {serial} not reachable: {exc}") from exc

    def rebind(self, serial: str) -> None:
        """Same device under a new adb serial (Wi-Fi phone back on another port / mDNS name)."""
        self.serial = serial
        self._dev = adbutils.adb.device(serial)

    def _shell(self, cmd: str) -> str:
        t0 = time.monotonic()
        try:
            return self._dev.shell(cmd, timeout=15)
        except Exception as exc:
            raise DeviceError(f"{self.serial}: shell '{cmd}' failed: {exc}") from exc
        finally:
            self.io.add("input" if cmd.startswith("input ") else "shell", time.monotonic() - t0)

    def capture(self, retries: int = 2) -> np.ndarray:
        """Screen as BGR. Retries short glitches; a stopped emulator still fails after the retries."""
        for attempt in range(retries + 1):
            try:
                t0 = time.monotonic()
                frame = self._capture_once()
                self.io.add("capture", time.monotonic() - t0)
                return frame
            except DeviceError as exc:
                if attempt == retries:
                    raise
                log.warning("%s (retry %d/%d)", exc, attempt + 1, retries)
                time.sleep(0.5)
        raise AssertionError("unreachable")

    compress_capture = False  # PhoneDevice: gzip on the device (phones: faster on USB and Wi-Fi)

    _raw_layout: tuple[int, int, int] | None = None  # width, height, header bytes of the last full frame

    def capture_rows(self, y0: int, y1: int) -> np.ndarray:
        """A full-size frame with only rows y0..y1 filled (the rest black): the phone cuts the rows out of
        the raw frame and sends only those (#166, live over Wi-Fi: the card strip 0.5 s, the screen
        2.2 s). Before the first full capture the layout is unknown, so that one is a full capture."""
        if self._raw_layout is None:
            return self.capture()
        width, height, header = self._raw_layout
        y0, y1 = max(0, int(y0)), min(height, int(y1))
        row = width * 4
        t0 = time.monotonic()
        cut = f"tail -c +{header + y0 * row + 1} | head -c {(y1 - y0) * row}"
        try:
            data = self._exec_bytes(f"exec:screencap | {cut}")
        except Exception as exc:  # no tail/head, a dropped connection...: the full capture retries
            log.debug("%s: screencap rows failed (%s); full capture", self.serial, exc)
            data = b""
        if len(data) != (y1 - y0) * row:  # resolution changed under us: start over with a full frame
            self._raw_layout = None
            return self.capture()
        frame = np.zeros((height, width, 3), np.uint8)
        frame[y0:y1] = np.frombuffer(data, np.uint8).reshape(y1 - y0, width, 4)[:, :, 2::-1]
        self.io.add("capture_rows", time.monotonic() - t0)
        return frame

    def _exec_bytes(self, cmd: str) -> bytes:
        conn = self._dev.open_transport(timeout=10)
        try:
            conn.send_command(cmd)
            conn.check_okay()
            return _read_all(conn.conn)
        finally:
            conn.close()

    def _capture_once(self) -> np.ndarray:
        # exec: service gives a raw byte stream; shell: may run under a PTY on old adbd and
        # rewrite LF to CRLF, corrupting pixel data.
        # Phones: the raw frame (6-10 MB) is the bottleneck. gzip -1 on the phone sends ~1/5 of it
        # (live, moto g84: USB 0.72 -> 0.32 s, Wi-Fi 1.54 -> 0.34 s). LDPlayer keeps raw (local, fast).
        cmd = "exec:screencap | gzip -1 -c" if self.compress_capture else "exec:screencap"
        try:
            data = self._exec_bytes(cmd)
            if self.compress_capture:
                data = gzip.decompress(data)
        except Exception as exc:
            raise DeviceError(f"{self.serial}: screencap failed: {exc}") from exc
        frame = decode_raw(data)
        h, w = frame.shape[:2]
        self._raw_layout = (w, h, len(data) - w * h * 4)
        return frame

    def tap(self, x: int, y: int) -> None:
        self._shell(f"input tap {int(x)} {int(y)}")

    def tap_many(self, points: list[tuple[int, int]]) -> None:
        """Several taps in one shell call, in order: one adb round trip instead of one per tap (live,
        phone on Wi-Fi: ~0.45 s per call, so 6 taps took 3.6 s one by one and 2.3 s batched)."""
        if points:
            self._shell(";".join(f"input tap {int(x)} {int(y)}" for x, y in points))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}")

    def hold(self, x: int, y: int, duration_ms: int) -> None:
        # Swipe to the same point = long press of given length.
        self.swipe(x, y, x, y, duration_ms)

    def key(self, keycode: str) -> None:
        self._shell(f"input keyevent {keycode}")

    def app_start(self, package: str = COC_PACKAGE) -> None:
        # LDPlayer 14 ships without `monkey`; resolve the launcher activity and use `am start`.
        intent = "-c android.intent.category.LAUNCHER"
        out = self._shell(f"cmd package resolve-activity --brief {intent} {package}")
        component = next((ln.strip() for ln in reversed(out.splitlines()) if "/" in ln), None)
        if component is None:
            raise DeviceError(f"{self.serial}: no launcher activity for {package}: {out.strip()!r}")
        self._shell(f"am start -n {component}")

    def app_stop(self, package: str = COC_PACKAGE) -> None:
        self._shell(f"am force-stop {package}")

    def crashed(self, package: str = COC_PACKAGE) -> bool:
        """Android's crash or "isn't responding" dialog for `package` has the focus:
        "Window{... Application Error: <pkg>}" / "Window{... Application Not Responding: <pkg>}" (#132)."""
        focus = self._shell("dumpsys window | grep mCurrentFocus")
        return f"Application Error: {package}" in focus or f"Application Not Responding: {package}" in focus

    def foreground_package(self) -> str | None:
        # mCurrentFocus=Window{621fa86 u0 com.supercell.clashofclans/com.supercell.titan.GameApp}
        for line in self._shell("dumpsys window | grep mCurrentFocus").splitlines():
            tokens = line.replace("}", " ").split()
            for token in tokens:
                if "/" in token:
                    return token.split("/", 1)[0]
            # A system window has a name, no package/activity: mCurrentFocus=Window{1a2 u0 NotificationShade}
            # (#178: the pulled-down shade, with someone's messages, counted as "the game is in front").
            if "Window{" in line and len(tokens) >= 3:
                return tokens[-1]
        return None

    def collapse_shade(self) -> None:
        """Close the notification shade / quick settings (pulled down over the game)."""
        self._shell("cmd statusbar collapse")

    def _touch_device(self) -> str | None:
        """Multi-touch input node (has ABS_MT_POSITION_X), e.g. /dev/input/event4 on LDPlayer 14,
        /dev/input/event9 on a moto g84. Also remembers the panel's X/Y maximum."""
        if getattr(self, "_touch", None) is None:
            self._touch, self._panel_max, self._touch_caps, self._su = "", None, set(), False
            node, xy, caps = None, {}, set()
            for line in self._shell("getevent -lp").splitlines():
                if line.startswith("add device"):
                    if xy.keys() >= {"X", "Y"}:
                        break
                    node, xy, caps = line.split(":", 1)[1].strip(), {}, set()
                for axis in ("X", "Y"):
                    if f"ABS_MT_POSITION_{axis}" in line and " max " in line:
                        xy[axis] = int(line.split(" max ", 1)[1].split(",")[0])
                caps.update(c for c in ("BTN_TOOL_FINGER", "ABS_MT_PRESSURE", "ABS_MT_TOUCH_MAJOR")
                            if c in line)
            if node and xy.keys() >= {"X", "Y"}:
                # A bare SYN is harmless; on a normal (non-rooted) phone SELinux refuses the write
                # ("Permission denied", live: moto g84, Android 16), so raw-event pinch is impossible.
                probe = self._shell(f"sendevent {node} 0 0 0 2>&1; echo rc=$?")
                rooted = "rc=0" not in probe and "rc=0" in self._shell(
                    f"su -c 'sendevent {node} 0 0 0' 2>&1; echo rc=$?")  # rooted phone, shell granted
                if "rc=0" in probe or rooted:
                    self._touch, self._panel_max, self._touch_caps = node, (xy["X"], xy["Y"]), caps
                    self._su = rooted
                    if rooted:
                        log.info("%s: touch events through su (root)", self.serial)
                else:
                    log.warning("%s: cannot send touch events to %s (%s); no pinch zoom on this device",
                                self.serial, node, probe.strip().splitlines()[0])
        return self._touch or None

    def display(self) -> tuple[tuple[int, int], tuple[int, int] | None]:
        """(physical size, override size or None) from `wm size`, natural orientation."""
        physical, override = parse_wm(self._shell("wm size"))
        if len(physical) != 2:
            raise DeviceError(f"{self.serial}: cannot read the screen size")
        return physical, override if override and len(override) == 2 else None

    def pinch(self, zoom_in: bool = False, steps: int = 10) -> bool:
        """Two-finger pinch with raw multi-touch events (`input` has no pinch). Default zooms OUT.
        Returns False when no multi-touch device is found."""
        dev = self._touch_device()
        if dev is None:
            return False
        physical, override = self.display()
        a, b, (axis, mid) = pinch_paths(self._panel_max, physical, override, zoom_in)

        def ev(t: int, c: int, v: int) -> str:
            return f"sendevent {dev} {t} {c} {v}"

        # Only events the panel has (live: a moto g84 goodix panel has no pressure axis but reports
        # BTN_TOOL_FINGER + touch size; without them the first tap after a pinch was lost).
        caps = self._touch_caps or {"ABS_MT_PRESSURE"}  # LDPlayer: pressure needed (D-016 notes)
        down = [ev(3, 58, 1)] if "ABS_MT_PRESSURE" in caps else []
        down += [ev(3, 48, 8)] if "ABS_MT_TOUCH_MAJOR" in caps else []

        cmds: list[str] = []
        for i in range(steps + 1):
            f = i / steps
            along = (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f))
            for slot, p in enumerate(along):
                x, y = (p, mid) if axis == 0 else (mid, p)
                cmds.append(ev(3, 47, slot))  # ABS_MT_SLOT
                if i == 0:
                    cmds += [ev(3, 57, 100 + slot), *down]  # TRACKING_ID, pressure / touch size
                cmds += [ev(3, 53, x), ev(3, 54, y)]  # POSITION_X / _Y
            if i == 0:
                cmds.append(ev(1, 330, 1))  # BTN_TOUCH down
                if "BTN_TOOL_FINGER" in caps:
                    cmds.append(ev(1, 325, 1))
            cmds.append(ev(0, 0, 0))  # SYN_REPORT
        for slot in (0, 1):
            cmds += [ev(3, 47, slot), *([ev(3, 58, 0)] if "ABS_MT_PRESSURE" in caps else []),
                     ev(3, 57, 4294967295)]  # lift fingers
        cmds += [ev(3, 47, 0), ev(1, 330, 0)]  # back to slot 0, as a real panel leaves it
        if "BTN_TOOL_FINGER" in caps:
            cmds.append(ev(1, 325, 0))
        cmds.append(ev(0, 0, 0))
        script = ";".join(cmds)
        self._shell(f"su -c '{script}'" if getattr(self, "_su", False) else script)
        return True

    def has_package(self, package: str) -> bool:
        return f"package:{package}" in self._shell(f"pm list packages {package}").split()

    def screen_size(self) -> tuple[int, int]:
        """Size of the frames capture() returns (already rotated, unlike `wm size`)."""
        frame = self.capture()
        return frame.shape[1], frame.shape[0]
