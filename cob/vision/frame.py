"""Frame wrapper caching derived images, so N matches on one frame convert to gray/HSV only once."""

from __future__ import annotations

import time
from functools import cached_property

import cv2
import numpy as np

Region = tuple[int, int, int, int]  # x, y, w, h in frame pixels


class Frame:
    def __init__(self, bgr: np.ndarray, ts: float | None = None):
        if bgr.ndim != 3 or bgr.shape[2] != 3:
            raise ValueError(f"expected BGR image, got shape {bgr.shape}")
        self.bgr = bgr
        self.ts = time.monotonic() if ts is None else ts

    @property
    def size(self) -> tuple[int, int]:
        return self.bgr.shape[1], self.bgr.shape[0]

    @cached_property
    def gray(self) -> np.ndarray:
        return cv2.cvtColor(self.bgr, cv2.COLOR_BGR2GRAY)

    @cached_property
    def hsv(self) -> np.ndarray:
        return cv2.cvtColor(self.bgr, cv2.COLOR_BGR2HSV)


def as_frame(img: Frame | np.ndarray) -> Frame:
    return img if isinstance(img, Frame) else Frame(img)


def clip_region(region: Region | None, size: tuple[int, int]) -> Region:
    """Clamp region to the frame; None means whole frame."""
    w, h = size
    if region is None:
        return 0, 0, w, h
    x, y, rw, rh = region
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w, x + rw), min(h, y + rh)
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def crop(img: np.ndarray, region: Region) -> np.ndarray:
    x, y, w, h = region
    return img[y : y + h, x : x + w]
