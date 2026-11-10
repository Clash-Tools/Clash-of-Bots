"""Live screen stream from a phone (#20 / #37, D-037): fast, lossy frames for waiting on a screen.

A screenshot over adb costs 1.3 s on a phone over Wi-Fi (median of 99 live cycles, up to 5 s), and 58 % of
a farm run was spent taking them, mostly in loops that only wait for a screen to appear. `screenrecord`
streams the screen as H.264 instead; decoding it here gives the newest frame at once.

H.264 is lossy: on the real test frames every screen is still recognised, but thin red deploy lines and
one loot number are not (any bit rate). So these frames are only ever used to *wait*: the navigator
looks at them until the wanted screen shows, then takes a normal screenshot and acts on that alone.

`screenrecord` stops after 3 minutes at most, sends nothing while the screen stands still, and needs a
size the encoder accepts (multiples of 16). The reader therefore reconnects when a recording ends, keeps
the last frame only while a recording is open, and the caller scales frames back to the display size.
Needs PyAV; without it, or when the phone refuses to record, there is simply no stream and every wait
uses screenshots as before.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable

import numpy as np

log = logging.getLogger(__name__)

TIME_LIMIT_S = 170  # screenrecord allows 180 at most
BIT_RATE = 8_000_000
MAX_EMPTY_OPENS = 3  # recordings in a row without a single frame before the stream gives up


def available() -> bool:
    try:
        import av  # noqa: F401
    except ImportError:
        return False
    return True


def encoder_size(width: int, height: int) -> tuple[int, int]:
    """Largest size the phone's H.264 encoder takes for a width x height screen (live, moto g84:
    1754x900 fails, 1744x896 works)."""
    return width // 16 * 16, height // 16 * 16


def record_command(size: tuple[int, int], bit_rate: int = BIT_RATE, time_limit_s: int = TIME_LIMIT_S) -> str:
    return (f"screenrecord --output-format=h264 --size {size[0]}x{size[1]} --bit-rate {bit_rate} "
            f"--time-limit {time_limit_s} -")


class ScreenStream:
    """Decodes H.264 chunks in a thread and hands out the newest frame.

    open_bytes() starts one recording and yields its bytes until it ends; it is called again after each
    end. latest() is None before the first frame of the current recording, after stop(), and once the
    stream has given up.
    """

    def __init__(self, open_bytes: Callable[[], Iterable[bytes]], *, restart_pause_s: float = 0.5,
                 sleep: Callable[[float], None] | None = None):
        self._open = open_bytes
        self._pause = restart_pause_s
        self._stop = threading.Event()
        self._sleep = sleep or self._stop.wait
        self._lock = threading.Lock()
        self._frame = None  # av.VideoFrame of the open recording
        self._image: np.ndarray | None = None  # its BGR picture, converted on first use
        self._thread: threading.Thread | None = None
        self.frames = 0  # decoded since start (tests, logs)
        self.failed = False  # gave up: the phone does not stream

    def start(self) -> ScreenStream:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self.failed = False
            self._thread = threading.Thread(target=self._run, name="screen-stream", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._drop()
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=3)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self.failed

    def latest(self) -> np.ndarray | None:
        """Newest frame as BGR (a copy), None when there is none to trust."""
        with self._lock:
            if self._frame is None:
                return None
            if self._image is None:
                self._image = self._frame.to_ndarray(format="bgr24")
            return self._image.copy()

    def _drop(self) -> None:
        with self._lock:
            self._frame = self._image = None

    def _run(self) -> None:
        import av

        empty = 0
        while not self._stop.is_set():
            got = 0
            try:
                codec = av.CodecContext.create("h264", "r")
                for chunk in self._open():
                    if self._stop.is_set():
                        break
                    for packet in codec.parse(chunk):
                        for frame in codec.decode(packet):
                            with self._lock:
                                self._frame, self._image = frame, None
                            got += 1
                            self.frames += 1
            except Exception as exc:  # dropped connection, broken data, screenrecord missing ...
                log.debug("screen stream ended: %s", exc)
            self._drop()  # the next recording starts with its own first frame
            if self._stop.is_set():
                break
            empty = 0 if got else empty + 1
            if empty >= MAX_EMPTY_OPENS:
                self.failed = True
                log.warning("screen stream gave no picture %d times; waiting on screenshots instead", empty)
                break
            self._sleep(self._pause)


def adb_bytes(device, command: str, chunk: int = 65536,
              timeout_s: float = 10.0) -> Callable[[], Iterable[bytes]]:
    """open_bytes for an adbutils device: runs `command` through the exec: service (raw bytes)."""

    def open_bytes():
        conn = device.open_transport(timeout=timeout_s)
        try:
            conn.send_command(f"exec:{command}")
            conn.check_okay()
            conn.conn.settimeout(TIME_LIMIT_S + 30)  # a still screen sends nothing for a long time
            while True:
                data = conn.conn.recv(chunk)
                if not data:
                    return
                yield data
        finally:
            conn.close()

    return open_bytes


def wait_first_frame(stream: ScreenStream, timeout_s: float = 5.0, clock=time.monotonic,
                     sleep=time.sleep) -> bool:
    start = clock()
    while clock() - start < timeout_s and stream.running:
        if stream.latest() is not None:
            return True
        sleep(0.05)
    return stream.latest() is not None
