import struct

import numpy as np
import pytest

from cob.device.base import DeviceError
from cob.device.screencap import decode_raw


def _raw(w, h, header_len=16, fmt=1, pixel=(10, 20, 30, 255)):
    head = struct.pack("<III", w, h, fmt) + (b"\0\0\0\0" if header_len == 16 else b"")
    return head + bytes(pixel) * (w * h)


@pytest.mark.parametrize("header_len", [12, 16])
def test_decode_both_header_layouts(header_len):
    frame = decode_raw(_raw(3, 2, header_len))
    assert frame.shape == (2, 3, 3)
    assert frame.dtype == np.uint8
    assert tuple(frame[1, 2]) == (30, 20, 10)  # RGBA -> BGR
    assert frame.flags["C_CONTIGUOUS"]


def test_rejects_truncated():
    with pytest.raises(DeviceError, match="size mismatch"):
        decode_raw(_raw(3, 2)[:-1])


def test_rejects_unknown_format():
    with pytest.raises(DeviceError, match="pixel format"):
        decode_raw(_raw(3, 2, fmt=4))


def test_rejects_short():
    with pytest.raises(DeviceError):
        decode_raw(b"\0" * 5)


def test_read_all_joins_chunks_until_eof():
    from cob.device.adb import _read_all

    class FakeSock:
        def __init__(self, parts):
            self.parts = list(parts)

        def recv(self, _n):
            return self.parts.pop(0) if self.parts else b""

    assert _read_all(FakeSock([b"ab", b"cd", b"e"])) == b"abcde"
