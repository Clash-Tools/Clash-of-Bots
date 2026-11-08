"""#166: device I/O counters and batched taps."""

from cob.core.timing import IoStats
from cob.device.adb import AdbDevice


def test_io_stats_reports_only_calls_made_between_snapshots():
    io = IoStats()
    io.add("capture", 1.0)
    before = io.snapshot()
    io.add("capture", 0.5)
    io.add("input", 0.25)
    assert IoStats.since(before, io.snapshot()) == "capture 1x 0.5s, input 1x 0.2s"
    assert IoStats.since(io.snapshot(), io.snapshot()) == "-"


def test_tap_many_sends_all_taps_in_one_shell_call():
    dev = AdbDevice.__new__(AdbDevice)
    dev.serial = "x"
    sent = []

    class Shell:
        def shell(self, cmd, timeout):
            sent.append(cmd)
            return ""

    dev._dev = Shell()
    dev.tap_many([(1, 2), (3.7, 4)])
    dev.tap_many([])
    assert sent == ["input tap 1 2;input tap 3 4"]
    assert dev.io.calls["input"] == 1


def _raw(width, height, header=16):
    import struct

    import numpy as np

    pixels = np.arange(width * height * 4, dtype=np.uint32).astype(np.uint8).reshape(height, width, 4)
    return struct.pack("<IIII", width, height, 1, 0)[:header] + pixels.tobytes(), pixels


def test_capture_rows_fills_only_the_asked_rows():
    import numpy as np

    dev = AdbDevice.__new__(AdbDevice)
    dev.serial, dev.compress_capture = "x", False
    raw, pixels = _raw(8, 6)
    sent = []

    def exec_bytes(cmd):
        sent.append(cmd)
        if "tail" in cmd:  # what the phone's tail -c +N | head -c M sends back
            n = int(cmd.split("tail -c +")[1].split()[0]) - 1
            m = int(cmd.split("head -c ")[1])
            return raw[n:n + m]
        return raw

    dev._exec_bytes = exec_bytes
    full = dev.capture_rows(2, 4)  # layout unknown yet: a full capture
    assert full.shape == (6, 8, 3) and len(sent) == 1
    part = dev.capture_rows(2, 4)
    assert "tail -c +81 | head -c 64" in sent[-1]  # 16 header + 2 rows of 32 bytes
    assert (part[2:4] == pixels[2:4, :, 2::-1]).all() and not part[:2].any() and not part[4:].any()
    assert np.array_equal(part[2:4], full[2:4])


def test_capture_rows_falls_back_to_a_full_frame_when_the_cut_fails():
    dev = AdbDevice.__new__(AdbDevice)
    dev.serial, dev.compress_capture = "x", False
    raw, _ = _raw(8, 6)
    dev._exec_bytes = lambda cmd: b"short" if "tail" in cmd else raw
    dev.capture()
    frame = dev.capture_rows(2, 4)
    assert frame.shape == (6, 8, 3) and frame[0].any()  # the full frame, not a cut
