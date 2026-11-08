import pytest

from cob.device import discovery, qr_pair
from cob.device.base import DeviceError
from cob.device.discovery import CONNECT, PAIRING, Service
from tests.fakes import FakeClock

MDNS = (
    "adb-AB12CD34EF-Ab12Cd\t_adb-tls-connect._tcp.\t192.168.1.23:41567\n"
    "adb-R5CT30XYZ-Qq9Zz1\t_adb-tls-connect._tcp\t192.168.1.40:39001\n"
    "cob-AbCdEfGh\t_adb-tls-pairing._tcp.\t192.168.1.23:37555\n"
    "printer\t_ipp._tcp\t192.168.1.9:631\n"
    "broken line\n"
    "adb-x-123456\t_adb-tls-connect._tcp\t[fe80::1]:5555\n"
)


def test_parse_services_keeps_adb_ipv4_only():
    found = discovery.parse_services(MDNS)
    assert [(s.name, s.type, s.address) for s in found] == [
        ("adb-AB12CD34EF-Ab12Cd", CONNECT, "192.168.1.23:41567"),
        ("adb-R5CT30XYZ-Qq9Zz1", CONNECT, "192.168.1.40:39001"),
        ("cob-AbCdEfGh", PAIRING, "192.168.1.23:37555"),
    ]
    assert found[0].serial == "AB12CD34EF" and found[2].serial is None


def test_nearby_marks_known_and_connected():
    found = discovery.parse_services(MDNS)
    near = discovery.nearby(lambda: found,
                            lambda: ["adb-R5CT30XYZ-Qq9Zz1._adb-tls-connect._tcp"],
                            lambda: {"AB12CD34EF"})
    assert [(n.service.serial, n.known, n.connected) for n in near] == [
        ("AB12CD34EF", True, False),
        ("R5CT30XYZ", False, True),
    ]


def test_auto_connect_only_known_unconnected_phones():
    found = discovery.parse_services(MDNS)
    tried = []

    def connect(address):
        tried.append(address)
        return address

    done = discovery.auto_connect(connect, list_services=lambda: found, serials=lambda: [],
                                  known=lambda: {"AB12CD34EF"})
    assert done == tried == ["192.168.1.23:41567"]


def test_find_address_by_hardware_serial():
    found = discovery.parse_services(MDNS)
    assert discovery.find_address("R5CT30XYZ", lambda: found) == "192.168.1.40:39001"
    assert discovery.find_address("nope", lambda: found) is None


def test_qr_session_is_random_and_escape_free():
    a, b = qr_pair.new_session(), qr_pair.new_session()
    assert a.name != b.name and a.password != b.password
    assert a.name.startswith("cob-") and a.password.isalnum() and len(a.password) == 12
    assert a.qr_text == f"WIFI:T:ADB;S:{a.name};P:{a.password};;"
    assert a.password not in repr(a)  # never ends up in logs
    rows = qr_pair.qr_matrix(a.qr_text)
    assert len(rows) == len(rows[0]) >= 29 and any(any(r) for r in rows)
    assert "█" in qr_pair.qr_terminal(a.qr_text)


def _flow(services_over_time, serials=lambda: []):
    clock = FakeClock()
    session = qr_pair.QrSession("cob-AbCdEfGh", "pw12345678ab", created=0.0)
    paired, connected, status = [], [], []

    def list_services():
        for t, found in reversed(services_over_time):
            if clock.t >= t:
                return found
        return []

    result = qr_pair.pair_and_connect(
        session, on_status=status.append, list_services=list_services,
        pair=lambda addr, pw: paired.append((addr, pw)) or "ok",
        connect=lambda addr: connected.append(addr) or addr,
        serials=serials, clock=clock, sleep=clock.sleep, poll_s=1.0,
    )
    return result, paired, connected, status


def test_qr_flow_pairs_only_our_name_then_connects_same_ip():
    other = Service("cob-SOMEONEx", PAIRING, "192.168.1.77:40000")
    ours = Service("cob-AbCdEfGh", PAIRING, "192.168.1.23:37555")
    conn = Service("adb-AB12CD34EF-Ab12Cd", CONNECT, "192.168.1.23:41567")
    elsewhere = Service("adb-R5CT30XYZ-Qq9Zz1", CONNECT, "192.168.1.40:39001")
    result, paired, connected, status = _flow([(0, [other, elsewhere]), (3, [other, ours, elsewhere]),
                                               (5, [elsewhere, conn])])
    assert paired == [("192.168.1.23:37555", "pw12345678ab")]
    assert connected == ["192.168.1.23:41567"] and result == "192.168.1.23:41567"
    assert status[0].startswith("Waiting") and status[-1].startswith("Connected")


def test_qr_flow_uses_adb_auto_connected_serial():
    ours = Service("cob-AbCdEfGh", PAIRING, "192.168.1.23:37555")
    conn = Service("adb-AB12CD34EF-Ab12Cd", CONNECT, "192.168.1.23:41567")
    auto = "adb-AB12CD34EF-Ab12Cd._adb-tls-connect._tcp"
    result, _, connected, _ = _flow([(0, [ours]), (2, [conn])], serials=lambda: [auto])
    assert result == auto and connected == []


def test_qr_flow_expires():
    with pytest.raises(DeviceError, match="expired"):
        _flow([(0, [])])


def test_reconnect_known_skips_phones_adb_holds_by_mdns_name(monkeypatch):
    from cob.device import wireless

    monkeypatch.setattr(wireless, "known", lambda: ["192.168.1.23:41567", "192.168.1.50:5555"])
    monkeypatch.setattr(wireless, "list_serials", lambda: ["adb-AB12CD34EF-Ab12Cd._adb-tls-connect._tcp"])
    monkeypatch.setattr(discovery, "services", lambda: discovery.parse_services(MDNS))
    tried = []
    monkeypatch.setattr(wireless.adbutils.adb, "connect", lambda addr, timeout: tried.append(addr))
    wireless.reconnect_known()
    assert tried == ["192.168.1.50:5555"]


def test_scan_ports_finds_a_listening_port():
    import socket

    from cob.device import wireless

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    port = srv.getsockname()[1]
    try:
        # alive_timeout: a refused loopback connection takes ~2 s on Windows runners (CI v0.4.0 failed on 1 s)
        found = wireless.scan_ports("127.0.0.1", (port - 20, port + 20), timeout=2.0, alive_timeout=5.0)
        assert found == [port]
    finally:
        srv.close()
    assert wireless.scan_ports("192.0.2.1", (40000, 40010), timeout=0.3, alive_timeout=0.3) == []  # TEST-NET


def test_reconnect_by_scan_only_for_remembered_unconnected_ips(monkeypatch):
    from cob.device import wireless

    monkeypatch.setattr(wireless, "known", lambda: ["192.168.1.201:37001", "192.168.1.201:41000",
                                                    "192.168.1.50:5555"])
    scanned, tried = [], []

    def scan(ip):
        scanned.append(ip)
        return [37473, 40000] if ip == "192.168.1.201" else []

    def connect(address):
        tried.append(address)
        if address.endswith(":37473"):
            raise wireless.DeviceError("not adb")  # first open port is something else
        return address

    back = wireless.reconnect_by_scan(scan, serials=lambda: ["192.168.1.50:5555"], connect_fn=connect)
    assert scanned == ["192.168.1.201"]  # .50 is already connected; each IP scanned once
    assert tried == ["192.168.1.201:37473", "192.168.1.201:40000"] and back == ["192.168.1.201:40000"]


def test_drop_offline_only_removes_dead_address_entries(monkeypatch):
    from types import SimpleNamespace

    from cob.device import wireless

    infos = [SimpleNamespace(serial="192.168.1.201:37473", state="offline"),
             SimpleNamespace(serial="adb-AB12CD34EF-x1Yz9Q._adb-tls-connect._tcp", state="device"),
             SimpleNamespace(serial="emulator-5554", state="offline")]
    gone = []
    monkeypatch.setattr(wireless.adbutils.adb, "list", lambda: infos)
    monkeypatch.setattr(wireless.adbutils.adb, "disconnect", gone.append)
    assert wireless.drop_offline() == ["192.168.1.201:37473"] and gone == ["192.168.1.201:37473"]
