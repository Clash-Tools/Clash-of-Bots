"""Live screen stream (D-037): H.264 decoding, reconnects, giving up, and how waits use it."""

import threading
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
import pytest

from cob.device import stream as st
from cob.screens.classifier import ScreenClassifier
from cob.screens.navigator import NavConfig, Navigator
from cob.vision.templates import TemplateStore

av = pytest.importorskip("av")
FRAMES = Path(__file__).parent / "fixtures" / "frames"


def h264(images: list[np.ndarray], size=(1600, 896)) -> bytes:
    """An Annex-B H.264 stream like screenrecord's, one frame per image."""
    enc = av.CodecContext.create("libx264", "w")
    enc.width, enc.height, enc.pix_fmt = size[0], size[1], "yuv420p"
    enc.bit_rate, enc.time_base = st.BIT_RATE, Fraction(1, 30)
    enc.options = {"preset": "ultrafast", "tune": "zerolatency"}
    out = b""
    for i, img in enumerate(images):
        f = av.VideoFrame.from_ndarray(cv2.resize(img, size, interpolation=cv2.INTER_AREA), format="bgr24")
        f.pts = i
        out += b"".join(bytes(p) for p in enc.encode(f))
    return out + b"".join(bytes(p) for p in enc.encode(None))


def chunks(data: bytes, n: int = 4096):
    return [data[i:i + n] for i in range(0, len(data), n)]


def frame(name: str) -> np.ndarray:
    return cv2.imread(str(FRAMES / f"{name}.jpg"))


def test_encoder_size_and_command():
    assert st.encoder_size(1754, 900) == (1744, 896)  # live: 1754x900 fails on the g84, 1744x896 works
    cmd = st.record_command((1744, 896))
    assert "--output-format=h264" in cmd and "--size 1744x896" in cmd and cmd.endswith(" -")
    assert f"--time-limit {st.TIME_LIMIT_S}" in cmd and st.TIME_LIMIT_S < 180


def test_stream_decodes_the_newest_frame_and_reconnects():
    data = h264([frame("home"), frame("battle")])
    opened, release = [], threading.Event()

    def open_bytes():
        opened.append(1)
        yield from chunks(data)
        if len(opened) >= 2:
            release.wait(5)  # the second recording stays open, like a live screen

    s = st.ScreenStream(open_bytes, restart_pause_s=0.01).start()
    try:
        assert st.wait_first_frame(s, timeout_s=10)
        deadline = threading.Event()
        while len(opened) < 2 and not deadline.wait(0.02):
            pass
        st.wait_first_frame(s, timeout_s=10)
        img = s.latest()
        assert img.shape == (896, 1600, 3) and s.frames >= 2 and len(opened) == 2
        assert not s.failed and s.running
    finally:
        release.set()
        s.stop()
    assert s.latest() is None and not s.running


def test_a_phone_that_never_streams_is_given_up():
    def open_bytes():
        return iter([b"not video"])

    s = st.ScreenStream(open_bytes, restart_pause_s=0.0).start()
    s._thread.join(5)
    assert s.failed and not s.running and s.latest() is None


class PeekDevice:
    """Screenshots and a lossy live stream showing the same sequence; counts each kind."""

    serial = "fake"

    def __init__(self, *names, change_after_peeks: int = 3):
        self.names = list(names)
        self.exact = [frame(n) for n in names]
        self.lossy = [cv2.GaussianBlur(f, (3, 3), 0) for f in self.exact]
        self.i, self.peeks, self.captures = 0, 0, 0
        self.change_after = change_after_peeks

    def peek(self):
        self.peeks += 1
        if self.peeks % self.change_after == 0:
            self.i = min(self.i + 1, len(self.names) - 1)
        return self.lossy[self.i]

    def capture(self):
        self.captures += 1
        return self.exact[self.i]


@pytest.fixture(scope="module")
def classifier():
    return ScreenClassifier(TemplateStore())


def nav_for(dev, classifier):
    return Navigator(dev, classifier, NavConfig(poll_s=0), sleep=lambda s: None)


def test_waits_watch_the_stream_and_confirm_with_screenshots(classifier):
    dev = PeekDevice("home", "home", "battle", change_after_peeks=3)
    got = nav_for(dev, classifier).wait_for({"BATTLE"}, timeout_s=60)
    assert got is not None and got[0].screen == "BATTLE"
    assert got[1].bgr is dev.exact[2]  # the frame handed back is the exact screenshot
    assert dev.captures == 2 and dev.peeks >= 6  # 2 confirming screenshots, the waiting on the stream


def test_waits_without_a_stream_use_screenshots(classifier):
    class NoStream(PeekDevice):
        def peek(self):
            self.peeks += 1
            return None

    dev = NoStream("battle")
    got = nav_for(dev, classifier).wait_for({"BATTLE"}, timeout_s=10)
    assert got[0].screen == "BATTLE" and dev.captures == 2


def test_a_stream_error_falls_back_to_screenshots(classifier):
    class Broken(PeekDevice):
        def peek(self):
            raise RuntimeError("decoder broke")

    dev = Broken("home")
    assert nav_for(dev, classifier).wait_for({"HOME"}, timeout_s=10)[0].screen == "HOME"


def test_wait_leave_watches_the_stream(classifier):
    dev = PeekDevice("search_a", "searching", change_after_peeks=4)
    assert nav_for(dev, classifier).wait_leave("ATTACK_SEARCH", timeout_s=60)
    assert dev.captures == 1  # only the change seen on the stream was checked with a screenshot


def test_phone_peek_scales_and_crops_to_the_game_area():
    from cob.device.phone import PhoneDevice

    phone = PhoneDevice.__new__(PhoneDevice)
    phone.x0, phone._width = 77, 1754
    phone._stream = None
    assert phone.peek() is None

    class Latest:
        def latest(self):
            img = np.zeros((896, 1744, 3), np.uint8)
            img[:, 872:] = 255  # right half white
            return img

    phone._stream = Latest()
    out = phone.peek()
    assert out.shape == (900, 1600, 3) and out[450, 790].max() < 60 and out[450, 810].min() > 200
    assert phone.io.calls["peek"] == 1


def test_live_stream_is_off_by_default_and_validated(tmp_path):
    import json

    from cob.core.config import FarmConfig, load_farm_config

    assert FarmConfig().live_stream == 0
    p = tmp_path / "farm.json"
    p.write_text(json.dumps({"live_stream": 5}))
    assert load_farm_config(p).live_stream == 1
