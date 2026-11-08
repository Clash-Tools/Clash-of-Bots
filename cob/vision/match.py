"""Template matching on cached Frames. TM_CCOEFF_NORMED: score in [-1, 1], 1 = identical."""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from cob.vision.frame import Frame, Region, as_frame, clip_region, crop
from cob.vision.templates import Template


@dataclass(frozen=True)
class Match:
    name: str
    x: int  # top-left in frame pixels
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


def _score_map(frame: Frame, tpl: Template, region: Region | None) -> tuple[np.ndarray, Region] | None:
    rx, ry, rw, rh = clip_region(region if region is not None else tpl.region, frame.size)
    tw, th = tpl.size
    if rw < tw or rh < th:
        return None
    if tpl.use_gray:
        hay, needle = crop(frame.gray, (rx, ry, rw, rh)), tpl.gray
    else:
        hay, needle = crop(frame.bgr, (rx, ry, rw, rh)), tpl.bgr
    res = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
    # Flat template/patch -> NaN scores; treat as no match.
    np.nan_to_num(res, copy=False, nan=-1.0)
    return res, (rx, ry, rw, rh)


def rescaled(tpl: Template, s: float) -> Template:
    """`tpl` resized by `s` (a single-scale template)."""
    if s == 1.0:
        return replace(tpl, scales=(1.0,))
    bgr = cv2.resize(tpl.bgr, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
    return replace(tpl, bgr=bgr, gray=cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), scales=(1.0,))


def match(img: Frame | np.ndarray, tpl: Template, region: Region | None = None,
          threshold: float | None = None) -> Match | None:
    """Best match at or above threshold, else None. A template with several `scales` is tried at each
    (best score wins), for things drawn at the camera zoom."""
    frame = as_frame(img)
    if len(tpl.scales) > 1:
        hits = [match(frame, rescaled(tpl, s), region, threshold) for s in tpl.scales]
        return max((h for h in hits if h is not None), key=lambda h: h.score, default=None)
    out = _score_map(frame, tpl, region)
    if out is None:
        return None
    res, (rx, ry, _, _) = out
    _, score, _, (mx, my) = cv2.minMaxLoc(res)
    if score < (tpl.threshold if threshold is None else threshold):
        return None
    return Match(tpl.name, rx + mx, ry + my, tpl.size[0], tpl.size[1], float(score))


def match_all(img: Frame | np.ndarray, tpl: Template, region: Region | None = None,
              threshold: float | None = None, max_results: int = 50,
              min_dist: float = 0.5) -> list[Match]:
    """All non-overlapping matches, best first.

    Greedy NMS on the score map: take the peak, blank a window of `min_dist` x template size around it,
    repeat. Cheaper than collecting all hits then pruning, and max_results bounds the cost.
    """
    frame = as_frame(img)
    out = _score_map(frame, tpl, region)
    if out is None:
        return []
    res, (rx, ry, _, _) = out
    thr = tpl.threshold if threshold is None else threshold
    tw, th = tpl.size
    sx, sy = max(1, int(tw * min_dist)), max(1, int(th * min_dist))
    found: list[Match] = []
    while len(found) < max_results:
        _, score, _, (mx, my) = cv2.minMaxLoc(res)
        if score < thr:
            break
        found.append(Match(tpl.name, rx + mx, ry + my, tw, th, float(score)))
        res[max(0, my - sy) : my + sy + 1, max(0, mx - sx) : mx + sx + 1] = -1.0
    return found
