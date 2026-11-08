"""LDPlayer integration: ldconsole.exe wrapper for discovery/launch/resize + ADB device per instance."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cob.device.adb import AdbDevice, connect, list_serials
from cob.device.base import TARGET_DPI, TARGET_SIZE, DeviceError, ResolutionMismatch

log = logging.getLogger(__name__)

# Installers write HKCU\Software\XuanZhi\LDPlayer<major> (seen: LDPlayer14); leidian is the legacy vendor key.
_REGISTRY_VENDORS = (r"Software\XuanZhi", r"Software\leidian")
_DEFAULT_DIRS = (
    r"C:\LDPlayer\LDPlayer14",
    r"C:\LDPlayer\LDPlayer9",
    r"D:\LDPlayer\LDPlayer14",
    r"D:\LDPlayer\LDPlayer9",
)


@dataclass(frozen=True)
class LdInstance:
    index: int
    name: str
    running: bool
    pid: int
    width: int | None = None
    height: int | None = None
    dpi: int | None = None

    @property
    def adb_serial(self) -> str:
        # LDPlayer maps instance n to emulator console port 5554+2n (adb sees emulator-<port>).
        return f"emulator-{5554 + 2 * self.index}"

    @property
    def adb_tcp(self) -> str:
        return f"127.0.0.1:{5555 + 2 * self.index}"


def parse_list2(output: str) -> list[LdInstance]:
    """Parse `ldconsole list2`.

    Line: index,title,top_hwnd,bind_hwnd,android_started,pid,vbox_pid[,width,height,dpi]
    Older builds omit the size fields.
    """
    instances = []
    for line in output.splitlines():
        parts = [p.strip() for p in line.strip().split(",")]
        if len(parts) < 7 or not parts[0].isdigit():
            continue
        size = [int(p) if p.lstrip("-").isdigit() else None for p in parts[7:10]] + [None] * 3
        instances.append(
            LdInstance(
                index=int(parts[0]),
                name=parts[1],
                running=parts[4] == "1",
                pid=int(parts[5]) if parts[5].lstrip("-").isdigit() else -1,
                width=size[0],
                height=size[1],
                dpi=size[2],
            )
        )
    return instances


def index_for_serial(serial: str) -> int | None:
    """LDPlayer instance for an adb serial: emulator-5554+2n or 127.0.0.1:5555+2n -> n."""
    if m := re.fullmatch(r"emulator-(\d+)", serial):
        port = int(m.group(1)) - 5554
    elif m := re.fullmatch(r"(?:127\.0\.0\.1|localhost):(\d+)", serial):
        port = int(m.group(1)) - 5555
    else:
        return None
    return port // 2 if port >= 0 and port % 2 == 0 else None


def ldplayer_major(subkey: str) -> int | None:
    """'LDPlayer14' -> 14, 'ldplayer9' -> 9; None for other subkeys (e.g. ldmultiplay)."""
    m = re.fullmatch(r"ldplayer(\d+)?", subkey, re.IGNORECASE)
    if m is None:
        return None
    return int(m.group(1) or 0)


def _registry_install_dirs() -> list[str]:
    """InstallDir of every LDPlayer registry entry, newest major version first."""
    import winreg

    found: list[tuple[int, str]] = []
    for vendor in _REGISTRY_VENDORS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, vendor) as root:
                subkeys = [winreg.EnumKey(root, i) for i in range(winreg.QueryInfoKey(root)[0])]
                for sub in subkeys:
                    major = ldplayer_major(sub)
                    if major is None:
                        continue
                    try:
                        with winreg.OpenKey(root, sub) as k:
                            install_dir, _ = winreg.QueryValueEx(k, "InstallDir")
                    except OSError:
                        continue
                    found.append((major, install_dir))
        except OSError:
            continue
    return [d for _, d in sorted(found, key=lambda t: t[0], reverse=True)]


def find_ldconsole() -> Path | None:
    """Order: COB_LDCONSOLE env > registry InstallDir > common install folders."""
    if env := os.environ.get("COB_LDCONSOLE"):
        return Path(env)
    if sys.platform != "win32":
        return None
    for install_dir in _registry_install_dirs():
        candidate = Path(install_dir) / "ldconsole.exe"
        if candidate.is_file():
            return candidate
    for d in _DEFAULT_DIRS:
        candidate = Path(d) / "ldconsole.exe"
        if candidate.is_file():
            return candidate
    return None


class LdConsole:
    def __init__(self, path: Path | None = None):
        self.path = path or find_ldconsole()
        if self.path is None:
            raise DeviceError("ldconsole.exe not found: install LDPlayer or set COB_LDCONSOLE")

    def _run(self, *args: str, timeout: float = 30) -> str:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.run(
            [str(self.path), *args], capture_output=True, timeout=timeout, creationflags=flags
        )
        # ldconsole prints in the system ANSI codepage (often GBK on CN builds).
        return proc.stdout.decode("utf-8", errors="replace")

    def list(self) -> list[LdInstance]:
        return parse_list2(self._run("list2"))

    def launch(self, index: int) -> None:
        self._run("launch", "--index", str(index))

    def quit(self, index: int) -> None:
        self._run("quit", "--index", str(index))

    def restart(self, index: int, serial: str, settle_s: float = 5.0,
                sleep: Callable[[float], None] = time.sleep) -> bool:
        """Quit the instance, then launch it and wait for adb (#132: the game keeps failing in it)."""
        log.warning("LDPlayer #%d: restarting the emulator", index)
        self.quit(index)
        sleep(settle_s)
        return self.ensure_running(index, serial, sleep=sleep)

    def instance(self, index: int) -> LdInstance | None:
        return next((i for i in self.list() if i.index == index), None)

    def ensure_running(self, index: int, serial: str, timeout_s: float = 150.0,
                       sleep: Callable[[float], None] = time.sleep,
                       clock: Callable[[], float] = time.monotonic) -> bool:
        """Launch the instance if it is not running and wait until Android booted and adb sees it."""
        start = clock()
        inst = self.instance(index)
        if inst is None:
            raise DeviceError(f"LDPlayer instance {index} does not exist")
        if not inst.running:
            log.warning("LDPlayer #%d is not running; launching it", index)
            self.launch(index)
        while clock() - start < timeout_s:
            inst = self.instance(index)
            if inst is not None and inst.running:
                try:
                    if serial in list_serials():
                        log.info("LDPlayer #%d up after %.0f s", index, clock() - start)
                        return True
                except DeviceError:
                    pass
            sleep(3)
        log.error("LDPlayer #%d did not come up within %.0f s", index, timeout_s)
        return False

    def set_resolution(self, index: int, width: int = TARGET_SIZE[0], height: int = TARGET_SIZE[1],
                       dpi: int = TARGET_DPI) -> None:
        """Takes effect after instance restart."""
        self._run("modify", "--index", str(index), "--resolution", f"{width},{height},{dpi}")


class LDPlayerDevice(AdbDevice):
    """AdbDevice bound to an LDPlayer instance; verifies the D-006 resolution contract."""

    def __init__(self, instance: LdInstance):
        serial = instance.adb_serial
        if serial not in list_serials():
            connect(instance.adb_tcp)
            serial = instance.adb_tcp
        super().__init__(serial)
        self.instance = instance

    def check_resolution(self) -> None:
        size = self.screen_size()
        if size != TARGET_SIZE:
            raise ResolutionMismatch(size)
