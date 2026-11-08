import pytest

from cob.device.ldplayer import LdConsole, LdInstance, index_for_serial, ldplayer_major, parse_list2


def test_parse_list2_with_size_fields():
    out = "0,LDPlayer,132456,265432,1,4321,5678,1600,900,240\r\n1,Farm 2,0,0,0,-1,-1,1280,720,240\r\n"
    insts = parse_list2(out)
    assert insts == [
        LdInstance(0, "LDPlayer", True, 4321, 1600, 900, 240),
        LdInstance(1, "Farm 2", False, -1, 1280, 720, 240),
    ]


def test_parse_list2_old_format_and_noise():
    out = "garbage line\n2,Old,0,0,1,99,100\n"
    (inst,) = parse_list2(out)
    assert inst.index == 2 and inst.running and inst.width is None


def test_adb_serials_follow_port_scheme():
    inst = LdInstance(3, "x", True, 1)
    assert inst.adb_serial == "emulator-5560"
    assert inst.adb_tcp == "127.0.0.1:5561"


def test_ldplayer_major_from_registry_subkey():
    assert ldplayer_major("LDPlayer14") == 14
    assert ldplayer_major("ldplayer9") == 9
    assert ldplayer_major("ldplayer") == 0
    assert ldplayer_major("ldmultiplay") is None



@pytest.mark.parametrize("serial, index", [
    ("emulator-5554", 0), ("emulator-5558", 2), ("127.0.0.1:5555", 0), ("127.0.0.1:5561", 3),
    ("emulator-5555", None), ("R58M123", None), ("127.0.0.1:5554", None),
])
def test_index_for_serial(serial, index):
    assert index_for_serial(serial) == index


class _FakeConsole(LdConsole):
    """ldconsole replaced by a script: instance stopped, running after launch + some polls."""

    def __init__(self, boot_polls):
        self.path = "fake"
        self.launched = 0
        self.polls = 0
        self.boot_polls = boot_polls

    def _run(self, *args, timeout=30):
        if args[0] == "launch":
            self.launched += 1
            return ""
        if args[0] == "quit":
            self.calls = [*getattr(self, "calls", []), "quit"]
            self.launched, self.polls = 0, 0
            return ""
        running = self.launched and self.polls >= self.boot_polls
        self.polls += 1
        return f"0,LDPlayer,0,0,{1 if running else 0},1,1,1600,900,240\n"


def test_ensure_running_launches_and_waits(monkeypatch):
    monkeypatch.setattr("cob.device.ldplayer.list_serials", lambda: ["emulator-5554"])
    t = [0.0]
    con = _FakeConsole(boot_polls=4)
    ok = con.ensure_running(0, "emulator-5554", sleep=lambda s: t.__setitem__(0, t[0] + s),
                            clock=lambda: t[0])
    assert ok and con.launched == 1


def test_ensure_running_gives_up(monkeypatch):
    monkeypatch.setattr("cob.device.ldplayer.list_serials", lambda: [])
    t = [0.0]
    con = _FakeConsole(boot_polls=0)
    ok = con.ensure_running(0, "emulator-5554", timeout_s=30, sleep=lambda s: t.__setitem__(0, t[0] + s),
                            clock=lambda: t[0])
    assert not ok and con.launched == 1


def test_restart_quits_then_launches_and_waits(monkeypatch):
    # #132: the game keeps failing inside the instance; restart the whole emulator.
    monkeypatch.setattr("cob.device.ldplayer.list_serials", lambda: ["emulator-5554"])
    con = _FakeConsole(boot_polls=2)
    con.launched = 1  # running now
    assert con.restart(0, "emulator-5554", sleep=lambda s: None)
    assert con.calls == ["quit"] and con.launched == 1
