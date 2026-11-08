"""Setup checks with plain-language results and a fix action where one exists (GUI device helper)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from cob.device.adb import AdbDevice, list_serials
from cob.device.base import COC_PACKAGE, TARGET_DPI, TARGET_SIZE, DeviceError
from cob.device.ldplayer import LdConsole, LdInstance, index_for_serial

log = logging.getLogger(__name__)

LAUNCH, RESIZE = "launch", "resize"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str | None = None  # LAUNCH / RESIZE when the helper can fix it with a button


def _instance(console: LdConsole | None, index: int | None) -> LdInstance | None:
    if console is None or index is None:
        return None
    try:
        return console.instance(index)
    except Exception as exc:
        log.info("ldconsole list failed: %s", exc)
        return None


def phone_checks(serial: str) -> list[Check] | None:
    """Checks for a real phone (None when `serial` is an emulator or not connected)."""
    from cob.device.phone import PhoneDevice, is_emulator

    try:
        if serial not in list_serials():
            return None
        dev = PhoneDevice(serial)
        if is_emulator(dev):
            return None
        out = [Check("ADB connection", True, f"phone {dev.model()} ({serial})")]
        physical, _ = dev.display()
        out.append(Check("Display mode", True, f"{physical[0]}x{physical[1]} now; landscape 1600x900 game "
                                               f"area @ {TARGET_DPI} dpi while the bot runs, then restored"))
        out.append(Check("Phone unlocked", not dev.locked(), "unlock the phone and keep it plugged in"
                         if dev.locked() else "unlocked"))
        can_pinch = dev._touch_device() is not None
        out.append(Check("Zoom (pinch)", can_pinch, ("through root (su)" if getattr(dev, "_su", False)
                                                     else "touch events allowed") if can_pinch else
                         "needs root: grant Shell (com.android.shell) superuser in Magisk / KernelSU; "
                         "without it battles start zoomed in"))
        has_coc = dev.has_package(COC_PACKAGE)
        out.append(Check("Clash of Clans installed", has_coc, COC_PACKAGE if has_coc else "not installed"))
        return out
    except DeviceError as exc:
        return [Check("Device responds", False, str(exc))]


def run_checks(serial: str | None) -> list[Check]:
    """Everything the bot needs, in the order a user would fix it. Never raises."""
    if serial and index_for_serial(serial) is None and (phone := phone_checks(serial)) is not None:
        return phone  # a phone needs no LDPlayer
    out: list[Check] = []
    try:
        console: LdConsole | None = LdConsole()
        out.append(Check("LDPlayer installed", True, str(console.path.parent)))
    except DeviceError as exc:
        console = None
        out.append(Check("LDPlayer installed", False, f"{exc}"))
    index = index_for_serial(serial) if serial else None
    inst = _instance(console, index)
    if serial is None:
        out.append(Check("Device selected", False, "pick a device (LDPlayer instance) first"))
        return out
    if inst is not None:
        if not inst.running:
            out.append(Check(f"LDPlayer #{inst.index} running", False, "instance is stopped", LAUNCH))
            return out
        out.append(Check(f"LDPlayer #{inst.index} running", True, inst.name))
        size_ok = (inst.width, inst.height, inst.dpi) == (*TARGET_SIZE, TARGET_DPI)
        detail = f"{inst.width}x{inst.height} @ {inst.dpi} dpi"
        if not size_ok:
            detail += f" - needs {TARGET_SIZE[0]}x{TARGET_SIZE[1]} @ {TARGET_DPI}"
        out.append(Check("Instance resolution", size_ok, detail, None if size_ok else RESIZE))
    try:
        serials = list_serials()
    except DeviceError as exc:
        out.append(Check("adb", False, str(exc)))
        return out
    if serial not in serials:
        hint = ("LDPlayer: Settings > Other settings > ADB debugging (local connection), then restart"
                if inst is not None else "device not connected")
        out.append(Check("ADB connection", False, hint))
        return out
    out.append(Check("ADB connection", True, serial))
    try:
        dev = AdbDevice(serial)
        size = dev.screen_size()
        out.append(Check("Screen size", size == TARGET_SIZE, f"{size[0]}x{size[1]}",
                         None if size == TARGET_SIZE or inst is None else RESIZE))
        has_coc = dev.has_package(COC_PACKAGE)
        out.append(Check("Clash of Clans installed", has_coc, COC_PACKAGE if has_coc else "not installed"))
    except DeviceError as exc:
        out.append(Check("Device responds", False, str(exc)))
    return out


def fix(action: str, serial: str) -> bool:
    """Run a fix button's action; True when the emulator is up afterwards."""
    console = LdConsole()
    index = index_for_serial(serial)
    if index is None:
        raise DeviceError(f"{serial} is not an LDPlayer instance")
    if action == RESIZE:
        console.set_resolution(index)
        console.quit(index)  # resolution applies on the next start
    elif action != LAUNCH:
        raise ValueError(f"unknown fix {action!r}")
    return console.ensure_running(index, serial)
