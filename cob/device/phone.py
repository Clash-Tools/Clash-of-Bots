"""Real Android phones over ADB (USB or wireless debugging).

Templates and coordinates assume a 1600x900 @ 240 frame (D-006). A phone gets that frame through a
temporary display override while the bot runs: `wm size 900x1600` on a portrait phone (the landscape
game then captures as 1600x900, letterboxed on the panel) and `wm density 240`. The phone's own values
are saved to a small file first and put back when the run ends, also after a crash (the next run, or
`cob phone-reset`, restores them). The screen is kept on while plugged in, with a 30 min timeout, for
the same span; those are restored with the display, and never saved as the phone's own (clean_original).

Rotation is locked to landscape too (live, moto g84 on Android 16): at 900x1600 @ 240 the screen is
600 dp wide, which Android 16 treats as a large screen and ignores the game's landscape request; the
game then ran letterboxed inside a portrait display. Locking the rotation restarts the game once.

HUD padding: the game keeps its HUD away from the rounded screen corners on BOTH sides (moto g84: 70 px
at 1600 wide), so a 1600 px display puts every button ~70 px off. The display is made wider instead
(1754 on the g84) until width - 2 x pad = 1600, and the bot sees the middle 1600 px: frames are
cropped and taps shifted by the pad, so the HUD lands where the 1600x900 templates expect it. (First
measured against the camera cutout, 94 px: that left the loot digits 12 px off and broke the OCR.)
"""

from __future__ import annotations

import atexit
import json
import logging
import re
import signal
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from cob.core.paths import user_data_dir
from cob.device.adb import AdbDevice, parse_wm
from cob.device.base import TARGET_DPI, TARGET_SIZE, DeviceError

log = logging.getLogger(__name__)

STAY_ON = "stay_on_while_plugged_in"
STAY_ON_ALL = "7"  # AC + USB + wireless
# system settings saved and put back, with the value set while the bot runs (portrait phones)
ROTATION = {"accelerometer_rotation": "0", "user_rotation": "1"}
# #86: "stay on while plugged in" does nothing on battery, so a Wi-Fi phone timed out and locked mid-run.
SCREEN_TIMEOUT = ("screen_off_timeout", "1800000")  # 30 min while the bot runs; restored afterwards
# Put back instead of the bot's own values when a saved record holds them (a phone stuck awake).
DEFAULT_TIMEOUT = "30000"
DEFAULT_ROTATION = {"accelerometer_rotation": "1", "user_rotation": "0"}


def is_emulator(device: AdbDevice) -> bool:
    """Emulators report ro.kernel.qemu=1 (LDPlayer, Android Studio); phones do not."""
    if device.serial.startswith("emulator-"):
        return True
    return device._shell("getprop ro.kernel.qemu").strip() == "1"


def override_size(physical: tuple[int, int], width: int = TARGET_SIZE[0]) -> tuple[int, int]:
    """`wm size` value (natural orientation) for a landscape game frame `width` x 900 on this panel."""
    h = TARGET_SIZE[1]
    return (h, width) if physical[0] < physical[1] else (width, h)


def cutout_inset(dumpsys_window: str) -> int:
    """Left/right display cutout inset in landscape, from `dumpsys window` (0 when none)."""
    m = re.search(r"DisplayCutout\{insets=Rect\((\d+), (\d+) - (\d+), (\d+)\)", dumpsys_window)
    return max(int(m.group(1)), int(m.group(3))) if m else 0


def corner_radius(dumpsys_window: str) -> int:
    """Rounded screen-corner radius from `dumpsys window` (0 when square)."""
    m = re.search(r"RoundedCorner\{position=\w+, radius=(\d+)", dumpsys_window)
    return int(m.group(1)) if m else 0


def hud_pad(dumpsys_window: str) -> int:
    """How far the game keeps its HUD from each side. Measured on a moto g84 (cutout 94, corners 78
    at 1788 wide): Battle / Build buttons sat ~74-78 px in, i.e. the rounded-corner radius, not the
    cutout. Phones without rounded corners fall back to the cutout inset."""
    return corner_radius(dumpsys_window) or cutout_inset(dumpsys_window)


def _record_file(phone_id: str) -> Path:
    folder = user_data_dir() / "phones"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / (re.sub(r"[^A-Za-z0-9._-]", "_", phone_id) + ".json")


def load_record(phone_id: str) -> dict | None:
    """The phone's own display values ("original") and whether the bot's mode is on ("active").
    Kept after a restore, so "Restore phone screen" always knows the phone's previous aspect ratio."""
    path = _record_file(phone_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text("utf-8"))
    if "original" not in data:  # first phone builds: the values themselves, written while active
        data = {"original": data, "active": True}
    return data


def save_record(phone_id: str, record: dict) -> None:
    _record_file(phone_id).write_text(json.dumps(record, indent=1), "utf-8")


def _bot_display(values: dict) -> bool:
    size = values.get("size")
    return values.get("density") == TARGET_DPI and bool(size) and TARGET_SIZE[1] in size


def _bot_stay_on(values: dict) -> bool:
    return values.get("stay_on") == STAY_ON_ALL


def _bot_timeout(values: dict) -> bool:
    return values.get("system", {}).get(SCREEN_TIMEOUT[0]) == SCREEN_TIMEOUT[1]


def bot_mode(values: dict) -> bool:
    """True when `values` hold any of the bot's own settings (900 x N @ 240, stay-on 7 or the 30 min
    timeout), not the phone's."""
    return _bot_display(values) or _bot_stay_on(values) or _bot_timeout(values)


def clean_original(values: dict) -> dict:
    """Saved "own" values with the bot's settings replaced by Android's defaults.

    Live 2026-11: a record had been saved while the bot's mode was on, so every restore put the bot's
    stay-on (7) back and the phone never slept or locked. Stay-on 7 is never put back, even next to the
    phone's own timeout: a phone that should stay awake while charging is set so again in Developer
    options, while a phone left awake by the bot drains and never locks."""
    if not bot_mode(values):
        return values
    out = {**values, "system": dict(values.get("system", {}))}
    if _bot_display(values):
        out["size"] = out["density"] = None
        if all(out["system"].get(k) == v for k, v in ROTATION.items()):
            out["system"].update(DEFAULT_ROTATION)
    if _bot_stay_on(values):
        out["stay_on"] = "0"
    if _bot_timeout(values):
        out["system"][SCREEN_TIMEOUT[0]] = DEFAULT_TIMEOUT
    return out


@contextmanager
def _no_interrupt():
    """Ctrl+C held back while the phone's settings are put back. Live 2026-11-04: a second SIGINT (uv
    passes one on as well) cut the atexit restore after the size, leaving the phone awake for good."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    pending = []
    old = signal.signal(signal.SIGINT, lambda *a: pending.append(a))
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, old)
    if pending and callable(old):
        old(*pending[0])


def describe(values: dict) -> str:
    size, density = values.get("size"), values.get("density")
    size_text = f"{size[0]}x{size[1]}" if size else "native size"
    density_text = f"{density} dpi" if density else "native density"
    out = f"{size_text}, {density_text}"
    timeout = values.get("system", {}).get(SCREEN_TIMEOUT[0])
    if timeout and timeout.isdigit():
        out += f", screen off after {int(timeout) // 1000} s"
    if values.get("stay_on") not in (None, "", "0", "null"):
        out += ", stays on while charging"
    return out


class PhoneDevice(AdbDevice):
    """AdbDevice that puts the phone into the bot's display mode (begin) and back (end)."""

    compress_capture = True

    def __init__(self, serial: str):
        super().__init__(serial)
        self._active = False
        self.x0 = 0  # frame/tap offset: how far the game pads its HUD from the screen edge

    def capture(self, retries: int = 2):
        frame = super().capture(retries)
        if self.x0 and frame.shape[1] >= self.x0 + TARGET_SIZE[0]:
            frame = frame[:, self.x0:self.x0 + TARGET_SIZE[0]].copy()
        return frame

    def capture_rows(self, y0: int, y1: int):
        frame = super().capture_rows(y0, y1)
        if self.x0 and frame.shape[1] >= self.x0 + TARGET_SIZE[0]:
            frame = frame[:, self.x0:self.x0 + TARGET_SIZE[0]].copy()
        return frame

    def tap(self, x: int, y: int) -> None:
        super().tap(x + self.x0, y)

    def tap_many(self, points: list[tuple[int, int]]) -> None:
        super().tap_many([(x + self.x0, y) for x, y in points])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        super().swipe(x1 + self.x0, y1, x2 + self.x0, y2, duration_ms)

    def hold(self, x: int, y: int, duration_ms: int) -> None:
        super().hold(x + self.x0, y, duration_ms)

    def model(self) -> str:
        return self._shell("getprop ro.product.model").strip() or self.serial

    @property
    def phone_id(self) -> str:
        """Hardware serial: the same phone over USB (AB12CD34EF) or Wi-Fi (192.168.1.5:5555) shares
        one record of its own display values."""
        if getattr(self, "_phone_id", None) is None:
            self._phone_id = self._shell("getprop ro.serialno").strip() or self.serial
        return self._phone_id

    def own_values(self) -> dict:
        """The phone's display settings as they are now (what a restore puts back)."""
        size = parse_wm(self._shell("wm size"))[1]
        density = parse_wm(self._shell("wm density"))[1]
        return {"size": list(size) if size else None, "density": density[0] if density else None,
                "stay_on": self._shell(f"settings get global {STAY_ON}").strip(),
                "system": {k: self._shell(f"settings get system {k}").strip()
                           for k in (*ROTATION, SCREEN_TIMEOUT[0])}}

    def apply_values(self, values: dict) -> None:
        # Screen-on first: a phone left awake is worse than one left at the bot's size.
        stay_on = values.get("stay_on")
        if stay_on and stay_on != "null":
            self._shell(f"settings put global {STAY_ON} {stay_on}")
        else:
            self._shell(f"settings delete global {STAY_ON}")
        for key, value in values.get("system", {}).items():
            if value and value != "null":
                self._shell(f"settings put system {key} {value}")
        size = values.get("size")
        self._shell(f"wm size {size[0]}x{size[1]}" if size else "wm size reset")
        density = values.get("density")
        self._shell(f"wm density {density}" if density else "wm density reset")

    def begin(self) -> None:
        record = load_record(self.phone_id)
        if record is None or not record.get("active"):
            # Not in the bot's mode now: what the phone shows is its own setup (refreshed every run, so
            # a size or density the user changed since is what comes back).
            own = self.own_values()
            if bot_mode(own):  # still in the bot's mode although nothing says so: keep the older values
                log.warning("phone %s is still in the bot's display mode; not saving that as its own",
                            self.serial)
                last = record["original"] if record else {}
                own = last if last and not bot_mode(last) else clean_original(own)
            record = {"original": own, "active": True}
            save_record(self.phone_id, record)
        # else: the last run did not end cleanly; the saved values are still the phone's own
        physical, _ = self.display()
        w, h = override_size(physical)
        self._shell(f"wm size {w}x{h}")
        self._shell(f"wm density {TARGET_DPI}")
        self._shell(f"settings put global {STAY_ON} {STAY_ON_ALL}")
        self._shell(f"settings put system {SCREEN_TIMEOUT[0]} {SCREEN_TIMEOUT[1]}")
        if physical[0] < physical[1]:
            for key, value in ROTATION.items():
                self._shell(f"settings put system {key} {value}")
        self.key("KEYCODE_WAKEUP")
        self._active = True
        atexit.register(self.end)
        if self.locked():  # before measuring: the lock screen reports no cutout
            self.end()  # the run never starts: give the phone its display back now
            raise DeviceError(f"phone {self.serial} is locked: unlock it, then start again")
        width, self.x0 = self._fit_cutout(physical)
        log.info("phone %s (%s): display %dx%d @ %d (game area x %d..%d) while the bot runs", self.serial,
                 self.model(), width, TARGET_SIZE[1], TARGET_DPI, self.x0, self.x0 + TARGET_SIZE[0])

    def _fit_cutout(self, physical: tuple[int, int]) -> tuple[int, int]:
        """Widen the display until the HUD area (width - 2 x pad) is 1600; returns (width, pad).
        The pad (rounded corners, in logical px) grows a little with the width, so re-measure."""
        width, pad = TARGET_SIZE[0], 0
        for _ in range(4):
            self.sleep_s(1.5)  # rotation / size change settles
            pad = hud_pad(self._shell("dumpsys window"))
            if width - 2 * pad == TARGET_SIZE[0]:
                return width, pad
            width = TARGET_SIZE[0] + 2 * pad
            w, h = override_size(physical, width)
            self._shell(f"wm size {w}x{h}")
        log.warning("phone %s: HUD pad still moving (width %d, pad %d); using it", self.serial, width, pad)
        return width, (width - TARGET_SIZE[0]) // 2

    @staticmethod
    def sleep_s(seconds: float) -> None:
        time.sleep(seconds)

    def end(self, force: bool = False) -> bool:
        """Put the phone's own display values back. Without force only while the bot's mode is on and
        this device turned it on (safe to call twice, or without begin): an earlier process's atexit
        end() must not undo a later run's mode (#93: a closing GUI restored a run mid-begin, and the
        run's size came back without its density). force = the manual "Restore phone screen" button.
        False when nothing is saved for this phone or it is unreachable."""
        with _no_interrupt():  # also covers saving the record
            return self._end(force)

    def _end(self, force: bool) -> bool:
        try:
            record = load_record(self.phone_id)
            if record is None or not (force or (self._active and record.get("active"))):
                return False
            record["original"] = clean_original(record["original"])
            self.apply_values(record["original"])
        except DeviceError as exc:  # unplugged: stays active, the next run (or the button) restores
            log.warning("phone %s: display not restored yet (%s)", self.serial, exc)
            return False
        record["active"] = False
        save_record(self.phone_id, record)
        self._active = False
        log.info("phone %s: display restored (%s)", self.serial, describe(record["original"]))
        return True

    def locked(self) -> bool:
        """Lock screen up (live, Android 16: `isKeyguardShowing=true` in `dumpsys window`)."""
        return "isKeyguardShowing=true" in self._shell("dumpsys window")


def phone_label(serial: str) -> str | None:
    """'Phone moto g84 5G (AB12CD34EF)' for a phone, None for an emulator or an unreachable serial."""
    try:
        dev = AdbDevice(serial)
        if is_emulator(dev):
            return None
        return f"Phone {dev._shell('getprop ro.product.model').strip() or '?'} ({serial})"
    except DeviceError:
        return None


def current_serial(phone_id: str, serials: list[str], find_address=None) -> str | None:
    """adb serial a phone has right now: Wi-Fi debugging restarts on a new port, and adb may list
    mDNS-connected phones as "adb-<serial>-<random>._adb-tls-connect._tcp"."""
    for s in serials:
        if s == phone_id or s.startswith(f"adb-{phone_id}-"):
            return s
    if find_address is None:
        from cob.device.discovery import find_address
    try:
        address = find_address(phone_id)
    except DeviceError:
        return None
    return address if address in serials else None


def reconnect(device: PhoneDevice, timeout_s: float = 120.0, poll_s: float = 3.0,
              clock=time.monotonic, sleep=time.sleep) -> bool:
    """Farm-loop recovery for a phone that dropped off adb (USB hiccup, Wi-Fi blip): wait for it to
    come back (over Wi-Fi: reconnect to it, also on a new port), then put the bot's display mode back
    on (the phone's own values stay saved meanwhile)."""
    from cob.device.adb import list_serials
    from cob.device.wireless import reconnect_all

    phone_id = device.phone_id  # cached before the drop
    start = clock()
    while clock() - start < timeout_s:
        try:
            serials = list_serials()
            if device.serial not in serials:
                reconnect_all()
                serials = list_serials()
                serial = current_serial(phone_id, serials)
                if serial and serial != device.serial:
                    log.info("phone %s is back as %s", phone_id, serial)
                    device.rebind(serial)
            if device.serial in serials:
                device.begin()
                log.info("phone %s back after %.0f s", device.serial, clock() - start)
                return True
        except DeviceError as exc:
            log.info("phone %s not ready yet: %s", device.serial, exc)
        sleep(poll_s)
    log.error("phone %s did not come back within %.0f s", device.serial, timeout_s)
    return False


def open_device(serial: str) -> AdbDevice:
    """The right device class for a serial: phones get PhoneDevice (display mode started)."""
    dev = AdbDevice(serial)
    if is_emulator(dev):
        return dev
    phone = PhoneDevice(serial)
    phone.begin()
    return phone


def restore(serial: str) -> str | None:
    """`cob phone-reset` / the Setup tab's "Restore phone screen": put the phone's own size, density,
    rotation and screen-on setting back, also when the bot thinks its mode is already off. Returns
    what was restored, None when nothing is saved for this phone (nothing is changed then)."""
    dev = PhoneDevice(serial)
    record = load_record(dev.phone_id)
    if record is None or not dev.end(force=True):
        return None
    return describe(record["original"])
