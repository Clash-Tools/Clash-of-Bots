"""Wireless ADB helpers without a phone: address checks, pairing request, remembered addresses."""

from types import SimpleNamespace

import pytest

from cob.device import wireless
from cob.device.base import DeviceError


@pytest.fixture(autouse=True)
def tmp_data(monkeypatch, tmp_path):
    monkeypatch.setattr(wireless, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(wireless, "ensure_adb_server", lambda: None)


@pytest.mark.parametrize("bad", ["192.168.1.5", "192.168.1.5:abc", "1.2.3.4:5555; reboot", ""])
def test_only_plain_host_port_addresses(bad):
    with pytest.raises(DeviceError):
        wireless.check_address(bad)
    assert wireless.check_address(" 192.168.1.5:41234 ") == "192.168.1.5:41234"


class FakeConnection:
    def __init__(self, reply):
        self.reply, self.sent = reply, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_command(self, cmd):
        self.sent.append(cmd)

    def check_okay(self):
        pass

    def read_string_block(self):
        return self.reply


def test_pair_sends_the_adb_server_pair_request(monkeypatch):
    conn = FakeConnection("Successfully paired to 192.168.1.5:41234 [guid=adb-AB12CD34EF]")
    monkeypatch.setattr(wireless.adbutils, "adb", SimpleNamespace(make_connection=lambda: conn))
    assert wireless.pair("192.168.1.5:41234", "123456").startswith("Successfully paired")
    assert conn.sent == ["host:pair:123456:192.168.1.5:41234"]
    with pytest.raises(DeviceError, match="6 digits"):
        wireless.pair("192.168.1.5:41234", "12ab")
    monkeypatch.setattr(wireless.adbutils, "adb",
                        SimpleNamespace(make_connection=lambda: FakeConnection("Failed: Wrong password")))
    with pytest.raises(DeviceError, match="Wrong password"):
        wireless.pair("192.168.1.5:41234", "654321")


def test_connected_addresses_are_remembered_and_retried(monkeypatch):
    online = {"emulator-5554"}
    tried = []

    def adb_connect(addr, timeout=None):
        tried.append(addr)
        online.add(addr)
        return f"connected to {addr}"

    monkeypatch.setattr(wireless.adbutils, "adb", SimpleNamespace(connect=adb_connect))
    monkeypatch.setattr(wireless, "list_serials", lambda: sorted(online))
    assert wireless.connect("192.168.1.5:5555") == "192.168.1.5:5555"
    assert wireless.known() == ["192.168.1.5:5555"]
    online.discard("192.168.1.5:5555")  # Wi-Fi blip
    assert wireless.reconnect_known() == ["192.168.1.5:5555"] and tried.count("192.168.1.5:5555") == 2
    assert wireless.reconnect_known() == []  # already connected: nothing to do


def test_failed_connect_is_not_remembered(monkeypatch):
    monkeypatch.setattr(wireless.adbutils, "adb", SimpleNamespace(connect=lambda a, timeout=None: "failed"))
    monkeypatch.setattr(wireless, "list_serials", lambda: [])
    with pytest.raises(DeviceError, match="pairing first"):
        wireless.connect("192.168.1.5:5555")
    assert wireless.known() == []


def test_wifi_ip_from_ip_addr():
    out = "3: wlan0: <UP>\n    inet 192.168.1.5/24 brd 192.168.1.255 scope global"
    dev = SimpleNamespace(_shell=lambda cmd: out)
    assert wireless.wifi_ip(dev) == "192.168.1.5"
    assert wireless.wifi_ip(SimpleNamespace(_shell=lambda cmd: "Device \"wlan0\" does not exist.")) is None


def test_other_network_is_reported_before_switching():
    assert wireless.same_network("192.168.1.18", ["192.168.1.7"])
    assert not wireless.same_network("192.168.1.18", ["10.0.0.76"])  # live: phone and PC apart
    assert wireless.same_network("192.168.1.18", [])  # PC address unknown: just try


def test_connect_timeout_is_a_device_error(monkeypatch):
    def timeout(addr, timeout=None):
        raise TimeoutError("adb read timeout")

    monkeypatch.setattr(wireless.adbutils, "adb", SimpleNamespace(connect=timeout))
    monkeypatch.setattr(wireless, "list_serials", lambda: [])
    with pytest.raises(DeviceError, match="TimeoutError"):
        wireless.connect("192.168.1.18:5555")


def test_one_port_per_phone_is_remembered():
    # Live 2026-11-05: 8 remembered ports (6 of them dead ports of the same two phones) made every
    # device refresh take 60 s. A new port replaces the old one of the same IP.
    for port in (37493, 39957, 41737):
        wireless.remember(f"192.168.1.201:{port}")
    wireless.remember("192.168.1.44:42391")
    assert wireless.known() == ["192.168.1.44:42391", "192.168.1.201:41737"]


def test_reconnect_known_tries_all_addresses_at_once(monkeypatch):
    import threading
    import time

    gate = threading.Barrier(3, timeout=2)  # only passes when all three connects run together

    def slow_connect(addr, timeout=None):
        gate.wait()
        time.sleep(0.2)
        return "failed"

    monkeypatch.setattr(wireless.adbutils, "adb", SimpleNamespace(connect=slow_connect))
    monkeypatch.setattr(wireless, "list_serials", lambda: [])
    monkeypatch.setattr(wireless, "known", lambda: ["10.0.0.1:5555", "10.0.0.2:5555", "10.0.0.3:5555"])
    start = time.monotonic()
    assert wireless.reconnect_known() == []
    assert time.monotonic() - start < 1.5  # in parallel: one timeout, not three
