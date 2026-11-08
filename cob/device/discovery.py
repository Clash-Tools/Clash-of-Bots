"""Find phones on the local network through the adb server's own mDNS browser (D-025).

With Wireless debugging on, Android 11+ announces itself on the Wi-Fi:
  _adb-tls-connect._tcp   always while Wireless debugging is on; instance "adb-<serial>-<random>"
  _adb-tls-pairing._tcp   only while a pairing screen is open; for QR pairing the instance is the
                          name inside the QR code (see qr_pair.py)
The port changes every time Wireless debugging is switched on, so the bot looks phones up by their
hardware serial (the same id as the phone record in phones/<serial>.json) instead of remembering
IP:port. Discovery is not trust: connecting only works for phones paired with this PC's adb key.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

import adbutils

from cob.core.paths import user_data_dir
from cob.device.adb import ensure_adb_server, list_serials
from cob.device.base import DeviceError

log = logging.getLogger(__name__)

CONNECT = "_adb-tls-connect._tcp"
PAIRING = "_adb-tls-pairing._tcp"
_ADB_NAME = re.compile(r"^adb-(?P<serial>[A-Za-z0-9._-]+?)-[A-Za-z0-9]{6}$")
_ADDRESS = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{1,5}$")  # IPv4 only: what `adb connect` gets


@dataclass(frozen=True)
class Service:
    name: str  # mDNS instance name
    type: str  # CONNECT or PAIRING (others are ignored)
    address: str  # ip:port

    @property
    def serial(self) -> str | None:
        """Hardware serial from an "adb-<serial>-<random>" name (connect services)."""
        m = _ADB_NAME.match(self.name)
        return m.group("serial") if m else None


def _host_command(cmd: str) -> str:
    ensure_adb_server()
    with adbutils.adb.make_connection() as c:
        c.send_command(cmd)
        c.check_okay()
        return c.read_string_block()


def available() -> tuple[bool, str]:
    """(True, version) when this adb server can browse mDNS; old adb builds cannot."""
    try:
        reply = _host_command("host:mdns:check").strip()
    except Exception as exc:  # old adb: "unknown host service"
        return False, f"{type(exc).__name__}: {exc}"
    return reply.startswith("mdns daemon version"), reply


def parse_services(text: str) -> list[Service]:
    """`adb mdns services` lines: "<name>\\t<type>\\t<ip:port>"; the type may end with a dot."""
    out = []
    for line in text.splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 3:
            continue
        name, stype, address = (p.strip() for p in parts)
        stype = stype.rstrip(".")
        if stype in (CONNECT, PAIRING) and _ADDRESS.match(address):
            out.append(Service(name, stype, address))
    return out


def services() -> list[Service]:
    try:
        return parse_services(_host_command("host:mdns:services"))
    except Exception as exc:
        raise DeviceError(f"mDNS discovery failed: {exc}") from exc


def known_phone_ids() -> set[str]:
    """Phones the bot has run on before (one record each, named by hardware serial)."""
    folder = user_data_dir() / "phones"
    return {p.stem for p in folder.glob("*.json") if p.stem != "wireless"}


def connected_names(serials: list[str]) -> set[str]:
    """adb lists phones it auto-connected through mDNS as "<instance>._adb-tls-connect._tcp"."""
    return {s.split("._adb-tls-connect", 1)[0] for s in serials if "._adb-tls-connect" in s}


@dataclass(frozen=True)
class Nearby:
    service: Service
    known: bool  # the bot has a record for this phone (it ran on it before)
    connected: bool


def nearby(list_services: Callable[[], list[Service]] = services,
           serials: Callable[[], list[str]] = list_serials,
           known: Callable[[], set[str]] = known_phone_ids) -> list[Nearby]:
    """Phones announcing Wireless debugging right now (connect services only)."""
    current = serials()
    names = connected_names(current)
    ids = known()
    return [
        Nearby(s, s.serial in ids if s.serial else False, s.address in current or s.name in names)
        for s in list_services()
        if s.type == CONNECT
    ]


def auto_connect(connect: Callable[[str], str] | None = None, **kw) -> list[str]:
    """Connect every known phone that announces itself but is not connected; returns new addresses.

    Phones the bot never ran on are left alone: the user picks those in the GUI (`Nearby phones`).
    """
    from cob.device import wireless

    connect = connect or wireless.connect
    done = []
    for n in nearby(**kw):
        if n.known and not n.connected:
            try:
                done.append(connect(n.service.address))
            except DeviceError as exc:  # not paired with this PC, or gone again
                log.info("phone %s at %s: %s", n.service.serial, n.service.address, exc)
    return done


def find_address(phone_id: str, list_services: Callable[[], list[Service]] = services) -> str | None:
    """Current IP:port of a phone by hardware serial (after Wi-Fi debugging restarted on a new port)."""
    for s in list_services():
        if s.type == CONNECT and s.serial == phone_id:
            return s.address
    return None
