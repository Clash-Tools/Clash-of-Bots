"""Phones over ADB: display override set and put back, pinch mapped to the touch panel (no device)."""

import pytest

from cob.device import phone
from cob.device.adb import parse_wm, pinch_paths

PANEL_G84 = (17280, 38400)  # moto g84 5G: 16 panel units per pixel, natural portrait


def test_parse_wm():
    assert parse_wm("Physical size: 1080x2400\n") == ((1080, 2400), None)
    assert parse_wm("Physical size: 1080x2400\nOverride size: 900x1600\n") == ((1080, 2400), (900, 1600))
    assert parse_wm("Physical density: 360\nOverride density: 240\n") == ((360,), (240,))


def test_pinch_on_ldplayer_is_unchanged():
    # natural landscape, panel in pixels: the original x 300 <-> 1300 / 720 <-> 880 at y 450
    assert pinch_paths((1599, 899), (1600, 900), None) == ((300, 1300), (720, 880), (0, 450))


def test_pinch_on_a_portrait_phone_stays_in_the_game_area():
    start, end, (axis, mid) = pinch_paths(PANEL_G84, (1080, 2400), (900, 1600))
    assert axis == 1 and mid == 540 * 16  # fingers move along panel Y, at the panel's middle column
    # 900x1600 fills 1080x1920 of the panel, 240 px letterbox top and bottom
    assert start == (600 * 16, 1800 * 16) and all(240 * 16 <= p <= 2160 * 16 for p in start + end)
    assert pinch_paths(PANEL_G84, (1080, 2400), (900, 1600), zoom_in=True)[0] == end


def test_override_size_follows_the_natural_orientation():
    assert phone.override_size((1080, 2400)) == (900, 1600)
    assert phone.override_size((2400, 1080)) == (1600, 900)


class FakeShell:
    """Phone shell: answers the wm / settings reads and records every command."""

    def __init__(self, size="Physical size: 1080x2400\n", density="Physical density: 360\n", stay_on="0",
                 locked=False, cutout=0.0, corners=0.0):
        self.corners = corners  # rounded-corner radius as a share of the long side (g84: 70 / 1600)
        self.cutout = cutout  # inset as a share of the display's long side (g84: 84 / 1600)
        self.width = 1600
        self.out = {"wm size": size, "wm density": density,
                    f"settings get global {phone.STAY_ON}": stay_on,
                    "settings get system accelerometer_rotation": "1",
                    "settings get system user_rotation": "0",
                    "dumpsys window": "isKeyguardShowing=true" if locked else "isKeyguardShowing=false",
                    "getprop ro.product.model": "moto g84 5G"}
        self.cmds = []

    def __call__(self, cmd):
        self.cmds.append(cmd)
        if cmd.startswith("wm size ") and "x" in cmd:
            self.width = max(int(n) for n in cmd.split()[-1].split("x"))
        if cmd == "dumpsys window" and (self.cutout or self.corners):
            inset, radius = round(self.cutout * self.width), round(self.corners * self.width)
            corners = f" RoundedCorners{{[RoundedCorner{{position=TopLeft, radius={radius}, " * bool(radius)
            return self.out[cmd] + f" DisplayCutout{{insets=Rect({inset}, 0 - 0, 0) waterfall=..." + corners
        return self.out.get(cmd, "")


@pytest.fixture
def fake_phone(monkeypatch, tmp_path):
    monkeypatch.setattr(phone, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(phone.atexit, "register", lambda fn: None)
    monkeypatch.setattr(phone.PhoneDevice, "sleep_s", staticmethod(lambda s: None))

    def make(**kw):
        dev = object.__new__(phone.PhoneDevice)
        dev.serial, dev._active, dev.x0, dev._phone_id = "AB12CD34EF", False, 0, "AB12CD34EF"
        dev._shell = FakeShell(**kw)
        return dev

    return make


def test_begin_sets_the_bot_display_and_end_restores_the_phone(fake_phone, tmp_path):
    dev = fake_phone()
    dev.begin()
    assert {"wm size 900x1600", "wm density 240", f"settings put global {phone.STAY_ON} 7",
            "settings put system user_rotation 1"} <= set(dev._shell.cmds)
    dev.end()
    assert dev._shell.cmds[-5:] == [f"settings put global {phone.STAY_ON} 0",
                                    "settings put system accelerometer_rotation 1",
                                    "settings put system user_rotation 0",
                                    "wm size reset", "wm density reset"]
    record = phone.load_record("AB12CD34EF")  # kept: the button can always restore the phone's own values
    assert record["active"] is False and record["original"]["size"] is None


def test_own_override_survives_a_crashed_run(fake_phone):
    first = fake_phone(size="Physical size: 1080x2400\nOverride size: 1080x2340\n",
                       density="Physical density: 360\nOverride density: 400\n")
    first.begin()  # ... and the bot crashes: end() never runs
    second = fake_phone(size="Physical size: 1080x2400\nOverride size: 900x1600\n",
                        density="Physical density: 360\nOverride density: 240\n")
    second.begin()  # must not save the bot's own 900x1600 as "the phone's values"
    second.end()
    assert second._shell.cmds[-2:] == ["wm size 1080x2340", "wm density 400"]


def test_locked_phone_stops_with_a_clear_message(fake_phone):
    from cob.device.base import DeviceError

    with pytest.raises(DeviceError, match="locked"):
        fake_phone(locked=True).begin()


def test_display_is_widened_around_the_camera_cutout(fake_phone):
    # moto g84: inset 84 at 1600 wide and the game pads both sides -> 1788 wide, bot sees x 94..1694
    dev = fake_phone(cutout=84 / 1600)
    dev.begin()
    assert "wm size 900x1788" in dev._shell.cmds and dev.x0 == 94
    sent = []
    dev._shell = sent.append
    dev.tap(100, 200)
    dev.swipe(10, 20, 30, 40, 500)
    assert sent == ["input tap 194 200", "input swipe 104 20 124 40 500"]


def _fake_phone(serial, begun):
    return type("Dev", (), {"serial": serial, "phone_id": "AB12CD34EF",
                            "begin": lambda self: begun.append(1),
                            "rebind": lambda self, s: setattr(self, "serial", s)})()


def test_reconnect_waits_for_the_phone_and_restarts_display_mode(monkeypatch):
    import cob.device.adb as adb
    import cob.device.discovery as discovery
    import cob.device.wireless as wireless
    from tests.fakes import FakeClock

    clock = FakeClock()
    monkeypatch.setattr(adb, "list_serials", lambda: ["AB12CD34EF"] if clock.t >= 6 else [])
    monkeypatch.setattr(wireless, "reconnect_all", lambda: [])
    monkeypatch.setattr(discovery, "find_address", lambda phone_id: None)
    begun = []
    dev = _fake_phone("AB12CD34EF", begun)
    assert phone.reconnect(dev, clock=clock, sleep=clock.sleep) and begun == [1] and clock.t == 6
    monkeypatch.setattr(adb, "list_serials", lambda: [])
    assert not phone.reconnect(dev, timeout_s=10, clock=clock, sleep=clock.sleep)


def test_reconnect_follows_a_wifi_phone_to_its_new_port(monkeypatch):
    import cob.device.adb as adb
    import cob.device.discovery as discovery
    import cob.device.wireless as wireless
    from tests.fakes import FakeClock

    clock = FakeClock()
    connected = []
    monkeypatch.setattr(adb, "list_serials", lambda: list(connected))
    monkeypatch.setattr(wireless, "reconnect_all", lambda: connected.append("192.168.1.23:41999") or [])
    monkeypatch.setattr(discovery, "find_address", lambda phone_id: "192.168.1.23:41999")
    begun = []
    dev = _fake_phone("192.168.1.23:37001", begun)
    assert phone.reconnect(dev, clock=clock, sleep=clock.sleep)
    assert dev.serial == "192.168.1.23:41999" and begun == [1]


def test_current_serial_matches_mdns_names_and_new_ports():
    serials = ["emulator-5554", "adb-AB12CD34EF-Ab12Cd._adb-tls-connect._tcp"]
    assert phone.current_serial("AB12CD34EF", serials, lambda _id: None) == serials[1]
    assert phone.current_serial("X1", ["10.0.0.5:4000"], lambda _id: "10.0.0.5:4000") == "10.0.0.5:4000"
    assert phone.current_serial("X1", [], lambda _id: "10.0.0.5:4000") is None


def test_pinch_sends_only_events_the_panel_has():
    from cob.device.adb import AdbDevice

    def pinch_on(caps, wm):
        dev = object.__new__(AdbDevice)
        dev.serial, dev._touch, dev._panel_max, dev._touch_caps = "x", "/dev/input/event9", PANEL_G84, caps
        sent = []
        dev._shell = lambda cmd: wm if cmd == "wm size" else sent.append(cmd) or ""
        assert dev.pinch()
        return sent[0].split(";")

    g84 = pinch_on({"BTN_TOOL_FINGER", "ABS_MT_TOUCH_MAJOR"},
                   "Physical size: 1080x2400\nOverride size: 900x1788\n")
    assert not any(" 3 58 " in e for e in g84)  # no pressure axis on the goodix panel
    assert "sendevent /dev/input/event9 1 325 1" in g84 and g84[-2:] == [
        "sendevent /dev/input/event9 1 325 0", "sendevent /dev/input/event9 0 0 0"]
    ld = pinch_on({"ABS_MT_PRESSURE", "BTN_TOOL_FINGER"}, "Physical size: 1600x900\n")
    assert any(e.endswith(" 3 58 1") for e in ld)  # LDPlayer needs pressure


def test_pinch_is_off_when_the_panel_refuses_events():
    from cob.device.adb import AdbDevice

    dev = object.__new__(AdbDevice)
    dev.serial = "AB12CD34EF"
    getevent = "\n".join(["add device 1: /dev/input/event9",
                          "  ABS_MT_POSITION_X : value 0, min 0, max 17280,",
                          "  ABS_MT_POSITION_Y : value 0, min 0, max 38400,"])
    answers = {"getevent -lp": getevent, "sendevent /dev/input/event9 0 0 0 2>&1; echo rc=$?":
               "sendevent: /dev/input/event9: Permission denied\nrc=1"}
    dev._shell = lambda cmd: answers.get(cmd, "")
    assert dev._touch_device() is None and dev.pinch() is False  # zoom_out() then reports 0 moves


def test_rooted_phone_pinches_through_su():
    from cob.device.adb import AdbDevice

    dev = object.__new__(AdbDevice)
    dev.serial = "AB12CD34EF"
    getevent = "\n".join(["add device 1: /dev/input/event9", "  BTN_TOOL_FINGER  ABS_MT_TOUCH_MAJOR",
                          "  ABS_MT_POSITION_X : value 0, min 0, max 17280,",
                          "  ABS_MT_POSITION_Y : value 0, min 0, max 38400,"])
    answers = {"getevent -lp": getevent,
               "sendevent /dev/input/event9 0 0 0 2>&1; echo rc=$?": "Permission denied\nrc=1",
               "su -c 'sendevent /dev/input/event9 0 0 0' 2>&1; echo rc=$?": "rc=0",
               "wm size": "Physical size: 1080x2400\nOverride size: 900x1788"}
    sent = []
    dev._shell = lambda cmd: answers.get(cmd) or sent.append(cmd) or ""
    assert dev.pinch() and sent[-1].startswith("su -c 'sendevent /dev/input/event9")


def test_hud_pad_follows_the_rounded_corners_when_there_are_some(fake_phone):
    # moto g84: corners 70 at 1600 (78 at 1788) are what the game pads its HUD with, not the cutout
    dev = fake_phone(cutout=84 / 1600, corners=70 / 1600)
    dev.begin()
    assert "wm size 900x1754" in dev._shell.cmds and dev.x0 == 77


def test_restore_button_works_any_time_and_follows_the_users_own_changes(fake_phone, monkeypatch):
    dev = fake_phone(size="Physical size: 1080x2400\nOverride size: 1080x2340\n")
    dev.begin()
    dev.end()  # normal stop
    dev._shell.cmds.clear()
    assert dev.end(force=True)  # the manual button still knows the phone's own 1080x2340
    assert "wm size 1080x2340" in dev._shell.cmds
    # the user picks another resolution between runs: the next run records that one
    later = fake_phone(size="Physical size: 1080x2400\n")
    later.begin()
    assert phone.load_record("AB12CD34EF")["original"]["size"] is None
    monkeypatch.setattr(phone, "PhoneDevice", lambda serial: later)
    assert phone.restore("192.168.1.5:5555") == "native size, native density"


def test_an_earlier_process_does_not_undo_a_later_run(fake_phone):
    # #93 live: a GUI that had finished its own run closed while a new run was starting; its atexit
    # end() restored the phone mid-begin, so the new run kept a bot size and its own end() did nothing.
    gui = fake_phone()
    gui.begin()
    gui.end()  # its run stopped normally
    run = fake_phone()
    run.begin()
    gui._shell.cmds.clear()
    assert not gui.end()  # the GUI quits: atexit end() of a device that is no longer in charge
    assert gui._shell.cmds == [] and phone.load_record("AB12CD34EF")["active"] is True
    assert run.end() and run._shell.cmds[-2] == "wm size reset"


def test_usb_and_wifi_share_one_record(fake_phone):
    usb = fake_phone(size="Physical size: 1080x2400\nOverride size: 1080x2340\n")
    usb.begin()  # bot mode on over USB ... then the cable is pulled; the phone is reached over Wi-Fi
    wifi = fake_phone(size="Physical size: 1080x2400\nOverride size: 900x1754\n")
    wifi.serial = "192.168.1.5:5555"
    wifi.begin()  # same hardware serial: keeps the saved own values, not the bot's 900x1754
    wifi.end()
    assert "wm size 1080x2340" in wifi._shell.cmds


def test_phone_frames_arrive_gzip_compressed(monkeypatch):
    import gzip
    import struct

    import numpy as np

    import cob.device.adb as adb

    pixels = np.zeros((900, 1754, 4), np.uint8)
    pixels[..., 0] = 200  # red
    raw = struct.pack("<IIII", 1754, 900, 1, 0) + pixels.tobytes()
    sent = []

    class Conn:
        conn = None

        def send_command(self, cmd):
            sent.append(cmd)

        def check_okay(self):
            pass

        def close(self):
            pass

    dev = object.__new__(phone.PhoneDevice)
    dev.serial, dev.x0 = "10.0.0.23:5555", 77
    dev._dev = type("D", (), {"open_transport": lambda self, timeout=None: Conn()})()
    monkeypatch.setattr(adb, "_read_all", lambda sock: gzip.compress(raw, 1))
    frame = dev.capture()
    assert sent == ["exec:screencap | gzip -1 -c"] and frame.shape == (900, 1600, 3)
    assert tuple(frame[450, 800]) == (0, 0, 200)  # BGR: decoded, then cropped to the game area


def test_screen_timeout_is_raised_for_the_run_and_restored(fake_phone):
    dev = fake_phone()
    dev._shell.out["settings get system screen_off_timeout"] = "30000"
    dev.begin()
    assert "settings put system screen_off_timeout 1800000" in dev._shell.cmds
    dev.end()
    assert "settings put system screen_off_timeout 30000" in dev._shell.cmds[-6:]


def test_navigator_stops_on_a_locked_phone_and_wakes_a_dark_one():
    from types import SimpleNamespace

    from cob.device.base import PhoneLocked
    from cob.screens.navigator import Navigator

    keys = []
    states = iter([True, True])  # locked before and after the wake key
    nav = object.__new__(Navigator)
    nav.device = SimpleNamespace(locked=lambda: next(states), key=keys.append)
    nav._sleep = lambda s: None
    with pytest.raises(PhoneLocked):
        nav._check_unlocked()
    assert keys == ["KEYCODE_WAKEUP"]
    states = iter([True, False])  # only the screen was off: waking it is enough
    nav.device = SimpleNamespace(locked=lambda: next(states), key=keys.append)
    nav._check_unlocked()
    nav.device = SimpleNamespace(key=keys.append)  # LDPlayer: no lock check at all
    nav._check_unlocked()


STUCK = {"size": [900, 1754], "density": 240, "stay_on": "7",
         "system": {"accelerometer_rotation": "0", "user_rotation": "0", "screen_off_timeout": "1800000"}}


def test_restore_never_puts_the_bots_screen_on_settings_back(fake_phone):
    # Live 2026-11 (moto g84): the saved "own" values were the bot's, so every restore left the phone
    # on stay-on 7 with a 30 min timeout and it never slept or locked.
    phone.save_record("AB12CD34EF", {"original": STUCK, "active": False})
    dev = fake_phone()
    assert dev.end(force=True)
    assert {"wm size reset", "wm density reset", f"settings put global {phone.STAY_ON} 0",
            "settings put system screen_off_timeout 30000"} <= set(dev._shell.cmds)
    assert not phone.bot_mode(phone.load_record("AB12CD34EF")["original"])


def test_begin_does_not_save_the_bots_mode_as_the_phones_own(fake_phone):
    phone.save_record("AB12CD34EF", {"original": STUCK, "active": False})
    dev = fake_phone(size="Physical size: 1080x2400\nOverride size: 900x1754\n",
                     density="Physical density: 360\nOverride density: 240\n", stay_on="7")
    dev._shell.out["settings get system screen_off_timeout"] = "1800000"
    dev.begin()
    dev.end()
    assert {"wm size reset", f"settings put global {phone.STAY_ON} 0",
            "settings put system screen_off_timeout 30000"} <= set(dev._shell.cmds[-6:])


def test_stay_awake_is_never_put_back_even_with_the_phones_own_timeout():
    # Live 2026-11-03 (moto g84): the record held stay-on 7 next to the phone's own 15 s timeout, so
    # every restore kept the screen on while charging and the phone never locked.
    own = {"size": None, "density": None, "stay_on": "7", "system": {"screen_off_timeout": "15000"}}
    assert phone.clean_original(own) == {**own, "stay_on": "0"}


def test_a_second_ctrl_c_does_not_cut_the_restore_short(fake_phone):
    # Live 2026-11-04: Ctrl+C reached both uv and the bot; the second SIGINT stopped the atexit restore
    # after the size, so the phone kept stay-on 7 and the 30 min timeout.
    import signal

    dev = fake_phone()
    dev.begin()
    shell = dev._shell

    class Interrupting:
        cmds = shell.cmds

        def __call__(self, cmd):
            if cmd.startswith("settings put global"):
                # arrives in the middle of the restore; raise_signal, not os.kill: on Windows os.kill
                # terminates the process (it killed the v0.5.0 Windows build's test run)
                signal.raise_signal(signal.SIGINT)
            return shell(cmd)

    dev._shell = Interrupting()
    with pytest.raises(KeyboardInterrupt):  # passed on once the phone is back
        dev.end()
    assert {f"settings put global {phone.STAY_ON} 0", "wm size reset", "wm density reset"} <= set(shell.cmds)
    assert phone.load_record("AB12CD34EF")["active"] is False
