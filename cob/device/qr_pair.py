"""Pair a phone by scanning a QR code (Android 11+ "Pair device with QR code"), as Android Studio does.

Flow (D-025):
 1. The bot makes a random service name + password and shows them as a QR code:
    WIFI:T:ADB;S:<name>;P:<password>;;
 2. The phone scans it and announces `_adb-tls-pairing._tcp` with instance <name> on the Wi-Fi.
 3. The bot sees exactly that name over mDNS and pairs with the password (SPAKE2 inside adb).
 4. The phone then announces `_adb-tls-connect._tcp` ("adb-<serial>-<random>"); the bot connects.
Only the phone that scanned this QR can match the random name; the session expires after 2 minutes.
"""

from __future__ import annotations

import logging
import secrets
import string
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from cob.device.base import DeviceError
from cob.device.discovery import CONNECT, PAIRING, Service, services

log = logging.getLogger(__name__)

_ALPHABET = string.ascii_letters + string.digits
TIMEOUT_S = 120.0
AUTO_WAIT_S = 5.0  # time adb gets to auto-connect a freshly paired phone


@dataclass(frozen=True)
class QrSession:
    name: str
    password: str = field(repr=False)  # never logged
    created: float = field(default_factory=time.monotonic)

    @property
    def qr_text(self) -> str:
        return f"WIFI:T:ADB;S:{self.name};P:{self.password};;"


def new_session() -> QrSession:
    # Name and password only use letters/digits: nothing needs escaping in the WIFI: QR format.
    name = "cob-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))
    password = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return QrSession(name, password)


def qr_matrix(text: str) -> list[list[bool]]:
    """QR modules (True = dark) including the quiet zone, for drawing in Qt."""
    import segno

    qr = segno.make(text, error="m", micro=False)
    return [[bool(v) for v in row] for row in qr.matrix_iter(scale=1, border=4)]


def qr_terminal(text: str) -> str:
    """QR as text for `cob pair-qr` (two rows per line with half blocks)."""
    rows = qr_matrix(text)
    if len(rows) % 2:
        rows.append([False] * len(rows[0]))
    glyph = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}
    # Dark modules print as light blocks so the QR reads correctly on dark terminals too.
    return "\n".join(
        "".join(glyph[(not a, not b)] for a, b in zip(top, bottom, strict=True))
        for top, bottom in zip(rows[::2], rows[1::2], strict=True)
    )


Status = Callable[[str], None]


def pair_and_connect(session: QrSession, *, on_status: Status = lambda s: None,
                     stop: threading.Event | None = None, timeout_s: float = TIMEOUT_S,
                     list_services: Callable[[], list[Service]] = services,
                     pair: Callable[[str, str], str] | None = None,
                     connect: Callable[[str], str] | None = None,
                     serials: Callable[[], list[str]] | None = None,
                     poll_s: float = 1.0, clock=time.monotonic, sleep=time.sleep) -> str:
    """Wait for the phone that scanned `session`'s QR, pair, connect. Returns the adb serial to use."""
    from cob.device import wireless
    from cob.device.adb import list_serials

    pair = pair or (lambda address, password: wireless.pair(address, password, qr=True))
    connect = connect or wireless.connect
    serials = serials or list_serials
    wait = stop.wait if stop is not None else sleep

    def expired() -> bool:
        return clock() - session.created > timeout_s

    on_status("Waiting for the phone to scan the QR code...")
    pairing = None
    while pairing is None:
        if stop is not None and stop.is_set():
            raise DeviceError("QR pairing cancelled")
        if expired():
            raise DeviceError("QR code expired: no phone scanned it within 2 minutes (same Wi-Fi?)")
        pairing = next((s for s in list_services() if s.type == PAIRING and s.name == session.name), None)
        if pairing is None:
            wait(poll_s)

    on_status(f"Pairing with {pairing.address}...")
    pair(pairing.address, session.password)

    # The phone announces its connect service from the same IP as the pairing service.
    ip = pairing.address.rsplit(":", 1)[0]
    on_status("Paired. Connecting...")
    # adb connects freshly paired phones by itself (listed by mDNS name); live it took ~1-3 s. Give it
    # AUTO_WAIT_S before connecting by address, otherwise the phone ends up listed twice.
    start = clock()
    deadline = start + 30.0
    while clock() < deadline:
        if stop is not None and stop.is_set():
            raise DeviceError("QR pairing cancelled")
        current = serials()
        for s in list_services():
            if s.type != CONNECT or s.address.rsplit(":", 1)[0] != ip:
                continue
            for serial in current:
                if serial == s.address or serial.startswith(s.name + "."):
                    on_status(f"Connected ({s.serial or s.name}).")
                    return serial
            if clock() - start >= AUTO_WAIT_S:
                address = connect(s.address)
                on_status(f"Connected to {address}.")
                return address
        wait(poll_s)
    raise DeviceError("paired, but the phone did not show a connect address; turn Wireless debugging "
                      "off and on, then press Refresh")
