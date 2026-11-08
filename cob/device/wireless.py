"""Wireless ADB for phones: pair (Android 11+), connect, switch a USB phone to Wi-Fi, reconnect.

Android 11+ "Wireless debugging" shows two addresses: one for pairing (with a 6-digit code, done once)
and one to connect to. Older phones use `adb tcpip 5555` over USB first, then the phone's Wi-Fi IP.
Addresses that connected once are remembered and tried again when the device list is refreshed or a
running bot loses the phone.
"""

from __future__ import annotations

import json
import logging
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor

import adbutils

from cob.core.paths import user_data_dir
from cob.device.adb import AdbDevice, ensure_adb_server, list_serials
from cob.device.base import DeviceError

log = logging.getLogger(__name__)

ADDRESS = re.compile(r"^[A-Za-z0-9.\-]+:\d{1,5}$")  # host:port, nothing else reaches the adb server
PAIRING_CODE = re.compile(r"^\d{6}$")
PAIRING_SECRET = re.compile(r"^[A-Za-z0-9]{6,64}$")  # QR passwords (qr_pair.py); no ":" reaches adb
DEFAULT_PORT = 5555
CONNECT_TIMEOUT_S = 15.0  # live (#79): ~500 ms Wi-Fi round trips made the TLS connect miss a 5 s limit
ADB_PORTS = (30000, 49999)  # Android picks the Wireless debugging port in this range


def _known_file():
    folder = user_data_dir() / "phones"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "wireless.json"


def known() -> list[str]:
    try:
        return [a for a in json.loads(_known_file().read_text("utf-8")) if ADDRESS.match(a)]
    except (OSError, ValueError):
        return []


def remember(address: str) -> None:
    """Newest first, one port per IP: Wireless debugging picks a new port each time it is turned on, so
    older ports of the same phone are dead (live: 8 dead ports made every device refresh take 60 s)."""
    ip = address.rsplit(":", 1)[0]
    addresses = [address] + [a for a in known() if a.rsplit(":", 1)[0] != ip]
    _known_file().write_text(json.dumps(addresses[:8]), "utf-8")


def forget(address: str) -> None:
    _known_file().write_text(json.dumps([a for a in known() if a != address]), "utf-8")


def check_address(address: str) -> str:
    address = address.strip()
    if not ADDRESS.match(address):
        raise DeviceError(f"'{address}' is not an address like 192.168.1.5:5555")
    return address


def pair(address: str, code: str, qr: bool = False) -> str:
    """Android 11+: Settings > Developer options > Wireless debugging > Pair device with pairing code.
    `address` is the IP:port shown in THAT dialog (not the connect port). With `qr`, `code` is the
    password from the bot's QR code instead of the 6-digit code."""
    address, code = check_address(address), code.strip()
    if not (PAIRING_SECRET if qr else PAIRING_CODE).match(code):
        raise DeviceError("the pairing code is the 6 digits shown on the phone")
    ensure_adb_server()
    with adbutils.adb.make_connection() as c:  # what `adb pair` sends to the adb server
        c.send_command(f"host:pair:{code}:{address}")
        c.check_okay()
        reply = c.read_string_block()
    if "Successfully paired" not in reply:
        raise DeviceError(f"pairing failed: {reply.strip() or 'no answer'}")
    log.info("paired with %s", address)
    return reply.strip()


def connect(address: str, timeout: float = CONNECT_TIMEOUT_S) -> str:
    """`adb connect`; returns the address once the phone shows up as a device (and remembers it)."""
    address = check_address(address)
    ensure_adb_server()
    try:
        reply = adbutils.adb.connect(address, timeout=timeout)
    except Exception as exc:  # AdbTimeout when nothing answers at that address
        reply = f"{type(exc).__name__}: {exc}"
    if address not in list_serials():
        raise DeviceError(f"could not connect to {address}: {reply.strip() or 'no answer'} (same Wi-Fi? "
                          "wireless debugging on? Android 11+ phones need pairing first)")
    remember(address)
    drop_offline()
    log.info("connected to %s", address)
    return address


def drop_offline() -> list[str]:
    """Disconnect ip:port entries adb lists as offline: dead leftovers of a failed or replaced connection
    (live: an offline duplicate stayed next to the same phone connected by its mDNS name)."""
    dropped = []
    try:
        for info in adbutils.adb.list():
            if info.state == "offline" and ADDRESS.match(info.serial):
                adbutils.adb.disconnect(info.serial)
                dropped.append(info.serial)
    except Exception as exc:  # cleanup only
        log.debug("drop offline: %s", exc)
    if dropped:
        log.info("dropped offline adb entries: %s", ", ".join(dropped))
    return dropped


def scan_ports(host: str, ports: tuple[int, int] = ADB_PORTS, timeout: float = 1.5,
               parallel: int = 800, alive_timeout: float = 1.0) -> list[int]:
    """Open TCP ports on one host (asyncio connect scan; refused ports answer at once on a LAN).

    Only used for addresses of phones that connected before (#79): when mDNS is silent on the network,
    the phone's new Wireless debugging port is found this way in about 2 s. `alive_timeout`: how long the
    first probe waits for a refusal (tests on loopback give it more: Windows answers slowly there)."""
    import asyncio

    async def probe(port: int, sem: asyncio.Semaphore, found: list[int]) -> None:
        async with sem:
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
            except (OSError, TimeoutError):
                return
            found.append(port)
            writer.close()

    async def alive() -> bool:
        # A phone that is on refuses a closed port at once; an absent host only times out (no 40 s scan).
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, 9), alive_timeout)
            writer.close()
            return True
        except ConnectionRefusedError:
            return True
        except (OSError, TimeoutError):
            return False

    async def run() -> list[int]:
        if not await alive():
            log.info("%s does not answer: not scanning it", host)
            return []
        sem, found = asyncio.Semaphore(parallel), []
        await asyncio.gather(*(probe(p, sem, found) for p in range(ports[0], ports[1] + 1)))
        return sorted(found)

    return asyncio.run(run())


def pc_addresses() -> list[str]:
    """This PC's IPv4 addresses (for "same network?" hints)."""
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return sorted({i[4][0] for i in infos if not i[4][0].startswith(("127.", "169.254."))})


def same_network(ip: str, others: list[str]) -> bool:
    """Same /24 as one of `others` (home routers); unknown PC addresses count as "maybe"."""
    return not others or any(o.rsplit(".", 1)[0] == ip.rsplit(".", 1)[0] for o in others)


def wifi_ip(device: AdbDevice) -> str | None:
    """The phone's IPv4 address on Wi-Fi (wlan0), None when it is not on Wi-Fi."""
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/", device._shell("ip -f inet addr show wlan0"))
    return m.group(1) if m else None


def usb_to_wifi(serial: str, port: int = DEFAULT_PORT) -> str:
    """Phone on USB -> same phone over Wi-Fi (`adb tcpip`, then connect to its IP). Returns the address.
    The USB cable can be unplugged afterwards; the setting lasts until the phone restarts."""
    device = AdbDevice(serial)
    ip = wifi_ip(device)
    if ip is None:
        raise DeviceError(f"{serial} is not on Wi-Fi: connect the phone to the same network as this PC")
    pcs = pc_addresses()
    if not same_network(ip, pcs):
        raise DeviceError(f"the phone is on another network ({ip}) than this PC ({', '.join(pcs)}): "
                          "connect both to the same Wi-Fi")
    adbutils.adb.device(serial).tcpip(port)
    address = f"{ip}:{port}"
    for _ in range(5):  # adbd restarts in TCP mode
        time.sleep(1.5)
        try:
            return connect(address)
        except DeviceError:
            continue
    raise DeviceError(f"{serial} switched to Wi-Fi, but {address} does not answer")


def _mdns_connected_addresses(current: list[str]) -> set[str]:
    """Addresses of phones adb already holds under their mDNS name (connecting the address too would
    list the same phone twice)."""
    if not any("._adb-tls-connect" in s for s in current):
        return set()
    try:
        from cob.device import discovery

        names = discovery.connected_names(current)
        return {s.address for s in discovery.services() if s.name in names}
    except DeviceError:
        return set()


def reconnect_known(timeout: float = 3.0) -> list[str]:
    """Try every remembered address that is not connected right now, all at once; returns the ones that
    came up. One port per IP is tried (the newest), so a refresh costs one timeout at most."""
    addresses = list(dict.fromkeys(_newest_per_ip(known())))
    if not addresses:
        return []
    try:
        current = set(list_serials())
    except DeviceError:
        return []
    covered = _mdns_connected_addresses(current)
    todo = [a for a in addresses if a not in current and a not in covered]

    def attempt(address: str) -> None:
        try:
            adbutils.adb.connect(address, timeout=timeout)
        except Exception as exc:  # offline phone: quietly skip
            log.debug("reconnect %s: %s", address, exc)

    if todo:
        with ThreadPoolExecutor(max_workers=len(todo)) as pool:
            list(pool.map(attempt, todo))
    try:
        now = set(list_serials())
    except DeviceError:
        return []
    return [a for a in todo if a in now]


def _newest_per_ip(addresses: list[str]) -> list[str]:
    seen, out = set(), []
    for a in addresses:  # known() is newest first
        ip = a.rsplit(":", 1)[0]
        if ip not in seen:
            seen.add(ip)
            out.append(a)
    return out


def reconnect_by_scan(scan=scan_ports, serials=list_serials, connect_fn=None) -> list[str]:
    """Remembered phone IPs that are not connected: find the new adb port by scanning, then connect."""
    connect_fn = connect_fn or (lambda a: connect(a))
    try:
        current = serials()
    except DeviceError:
        return []
    connected_ips = {s.rsplit(":", 1)[0] for s in current if ADDRESS.match(s)}
    ips = [ip for ip in dict.fromkeys(a.rsplit(":", 1)[0] for a in known()) if ip not in connected_ips]

    def one(ip: str) -> str | None:
        for port in scan(ip):
            try:
                return connect_fn(f"{ip}:{port}")
            except DeviceError as exc:  # another open port, or not paired with this PC
                log.info("scan %s:%d: %s", ip, port, exc)
        return None

    if not ips:
        return []
    with ThreadPoolExecutor(max_workers=len(ips)) as pool:  # each host's alive check waits ~1 s
        return [a for a in pool.map(one, ips) if a]


def reconnect_all() -> list[str]:
    """Remembered addresses, known phones found by mDNS (D-025), then a port scan of remembered phone IPs
    when nothing else brought a Wi-Fi phone back (#79: mDNS can be silent on a network)."""
    back = reconnect_known()
    try:
        from cob.device import discovery

        back += discovery.auto_connect()
    except DeviceError as exc:  # adb without mDNS: remembered addresses only
        log.debug("mDNS reconnect skipped: %s", exc)
    if not back and not _any_wifi_phone_connected():
        back += reconnect_by_scan()
    drop_offline()
    return back


def _any_wifi_phone_connected() -> bool:
    try:
        return any(ADDRESS.match(s) or "._adb-tls-connect" in s for s in list_serials())
    except DeviceError:
        return False
