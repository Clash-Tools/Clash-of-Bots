"""Decode `screencap` raw output (no PNG encode on device = much faster than `screencap -p`)."""

from __future__ import annotations

import struct

import numpy as np

from cob.device.base import DeviceError

_RGBA_8888 = 1
_RGBX_8888 = 2


def decode_raw(data: bytes) -> np.ndarray:
    """Raw layout: u32 width, u32 height, u32 format, [u32 colorspace on Android 9+], then pixels.

    The colorspace field is detected from total length rather than Android version, because
    emulators report inconsistent versions.
    """
    if len(data) < 12:
        raise DeviceError(f"screencap returned {len(data)} bytes")
    width, height, fmt = struct.unpack_from("<III", data, 0)
    if fmt not in (_RGBA_8888, _RGBX_8888):
        raise DeviceError(f"unsupported screencap pixel format {fmt}")
    pixels = width * height * 4
    for header in (16, 12):
        if len(data) == header + pixels:
            break
    else:
        raise DeviceError(f"screencap size mismatch: {len(data)} bytes for {width}x{height}")
    rgba = np.frombuffer(data, dtype=np.uint8, count=pixels, offset=header).reshape(height, width, 4)
    # RGBA -> BGR (OpenCV order); copy so the frame owns contiguous memory.
    return np.ascontiguousarray(rgba[:, :, 2::-1])
