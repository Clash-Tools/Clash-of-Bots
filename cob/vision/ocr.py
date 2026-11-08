"""Reading numbers and text (D-009).

DigitReader: per-digit glyph templates -> ~1 ms reads for loot/resource numbers (hot path).
TesseractOCR: slow subprocess OCR for rare free text (player names, labels).
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cob.core.paths import tools_dir
from cob.vision.frame import Frame, Region, as_frame, clip_region, crop
from cob.vision.match import match_all
from cob.vision.templates import Template

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DigitHit:
    digit: str
    x: int
    w: int
    score: float


class DigitReader:
    """Reads an integer from a region by matching each glyph 0-9 and ordering hits left to right.

    Glyphs must be cropped tight from real frames at the target resolution, one font per reader
    (loot numbers and resource bar use different sizes).
    """

    def __init__(self, glyphs: dict[str, np.ndarray], threshold: float = 0.8):
        digits = {k: v for k, v in glyphs.items() if k.isdigit() and len(k) == 1}
        if not digits:
            raise ValueError("no digit glyphs (expected files 0.png..9.png)")
        self.threshold = threshold
        self._tpls = [
            Template(k, img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None, threshold, True)
            for k, img in sorted(digits.items())
        ]

    def hits(self, img: Frame | np.ndarray, region: Region) -> list[DigitHit]:
        frame = as_frame(img)
        raw = [
            DigitHit(m.name, m.x, m.w, m.score)
            for tpl in self._tpls
            for m in match_all(frame, tpl, region, self.threshold, max_results=12)
        ]
        # Different glyphs can fire on the same spot (3 vs 8): keep best score per horizontal slot.
        raw.sort(key=lambda h: -h.score)
        kept: list[DigitHit] = []
        for h in raw:
            if all(abs(h.x - k.x) >= min(h.w, k.w) * 0.6 for k in kept):
                kept.append(h)
        return sorted(kept, key=lambda h: h.x)

    def read(self, img: Frame | np.ndarray, region: Region) -> int | None:
        hits = self.hits(img, region)
        return int("".join(h.digit for h in hits)) if hits else None


def find_tesseract() -> Path | None:
    """Order: COB_TESSERACT env > bundled tools/tesseract > PATH > default Windows install."""
    if env := os.environ.get("COB_TESSERACT"):
        return Path(env)
    exe = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    bundled = tools_dir() / "tesseract" / exe
    if bundled.is_file():
        return bundled
    if found := shutil.which("tesseract"):
        return Path(found)
    default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    return default if sys.platform == "win32" and default.is_file() else None


def preprocess_text(patch_bgr: np.ndarray, scale: int = 3, white_text: bool = True) -> np.ndarray:
    """Upscale + binarize. CoC text is white with dark outline; keep only bright pixels as ink."""
    gray = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if white_text:
        _, bw = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY)
    else:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return 255 - bw  # tesseract prefers dark text on light background


class TesseractOCR:
    def __init__(self, exe: Path | None = None):
        import pytesseract  # lazy: only text OCR needs it

        self._pt = pytesseract
        exe = exe or find_tesseract()
        if exe is None:
            raise RuntimeError("tesseract not found: set COB_TESSERACT or bundle tools/tesseract")
        pytesseract.pytesseract.tesseract_cmd = str(exe)
        tessdata = exe.parent / "tessdata"
        if tessdata.is_dir():
            os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))

    def read_text(self, img: Frame | np.ndarray, region: Region, psm: int = 7,
                  whitelist: str | None = None, white_text: bool = True) -> str:
        frame = as_frame(img)
        patch = crop(frame.bgr, clip_region(region, frame.size))
        config = f"--psm {psm}"
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"
        return self._pt.image_to_string(preprocess_text(patch, white_text=white_text), config=config).strip()
