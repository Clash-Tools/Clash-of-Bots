"""How full the gold and elixir storages are, from the resource bar on the home screen (#119).

The fill colour grows from the icon end of each bar (x 1529) to the left; the empty part is dark grey,
so the run of fill-coloured pixels from the right edge is the filled share. Every row of a bar gives
the same run (digits sit on top but the run tolerates small gaps), so the longest run is taken.
Dark elixir is left out: its fill is near black and does not stand out from the empty bar."""

from __future__ import annotations

import cv2
import numpy as np

from cob.vision.frame import Frame

BAR_RIGHT, BAR_LEFT = 1529, 1256  # fill area of the gold / elixir bars, 1600x900 frame
# kind -> (hue low, hue high, first row, last row) in OpenCV HSV (hue 0-179)
BARS = {"gold": (15, 35, 28, 70), "elixir": (140, 160, 88, 132)}
_MIN_SAT = _MIN_VAL = 110
_GAP = 6  # px of non-fill tolerated inside the run (digit outlines)


def _run(row: np.ndarray, lo: int, hi: int) -> int:
    """Fill run length (px) leftwards from BAR_RIGHT in one HSV row."""
    hsv = row[BAR_LEFT:BAR_RIGHT + 1][::-1]
    fill = (hsv[:, 0] >= lo) & (hsv[:, 0] <= hi) & (hsv[:, 1] > _MIN_SAT) & (hsv[:, 2] > _MIN_VAL)
    n, gap = 0, 0
    for i, on in enumerate(fill):
        if on:
            n, gap = i + 1, 0
        else:
            gap += 1
            if gap > _GAP:
                break
    return n


def storage_fill(frame: Frame | np.ndarray) -> dict[str, float]:
    """kind -> filled share 0..1 of the gold and elixir storages (home village screen)."""
    bgr = frame.bgr if isinstance(frame, Frame) else frame
    out = {}
    for kind, (lo, hi, y0, y1) in BARS.items():
        hsv = cv2.cvtColor(bgr[y0:y1], cv2.COLOR_BGR2HSV)
        out[kind] = max(_run(row, lo, hi) for row in hsv) / (BAR_RIGHT - BAR_LEFT + 1)
    return out
