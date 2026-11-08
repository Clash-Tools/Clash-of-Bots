"""HSV color checks: cheap confirmations (red = unaffordable cost, green = active button, ...).

OpenCV HSV ranges: H 0-179, S 0-255, V 0-255.
"""

from __future__ import annotations

import cv2
import numpy as np

from cob.vision.frame import Frame, Region, as_frame, clip_region, crop

HSV = tuple[int, int, int]

# Red wraps around hue 0, so it needs two ranges.
RED = (((0, 120, 120), (8, 255, 255)), ((170, 120, 120), (179, 255, 255)))
GREEN = (((40, 120, 100), (80, 255, 255)),)
WHITE = (((0, 0, 200), (179, 40, 255)),)


def hsv_fraction(img: Frame | np.ndarray, region: Region | None,
                 ranges: tuple[tuple[HSV, HSV], ...]) -> float:
    """Fraction of pixels in region inside any of the HSV ranges."""
    frame = as_frame(img)
    r = clip_region(region, frame.size)
    patch = crop(frame.hsv, r)
    if patch.size == 0:
        return 0.0
    mask = np.zeros(patch.shape[:2], dtype=np.uint8)
    for lo, hi in ranges:
        mask |= cv2.inRange(patch, np.array(lo, np.uint8), np.array(hi, np.uint8))
    return float(np.count_nonzero(mask)) / mask.size


def mean_bgr(img: Frame | np.ndarray, region: Region) -> tuple[float, float, float]:
    frame = as_frame(img)
    b, g, r = crop(frame.bgr, clip_region(region, frame.size)).reshape(-1, 3).mean(axis=0)
    return float(b), float(g), float(r)
