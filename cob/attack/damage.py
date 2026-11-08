"""Battle progress from the "Overall Damage" percentage (#78).

The cyan bar above the number is only drawn until the first star; after that the game shows the stars
instead, so a bar reading drops to 0 mid-battle. The number is there from the first hit to the end.
It is the loot-number font drawn larger, so the loot glyphs are scaled up to read it.
"""

from __future__ import annotations

import cv2

from cob.vision.frame import Frame
from cob.vision.ocr import DigitReader
from cob.vision.templates import TemplateStore


def damage_reader(store: TemplateStore, cfg: dict) -> DigitReader:
    scale = float(cfg["scale"])
    glyphs = {k: cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
              for k, img in store.load_dir(cfg["digits"]).items()}
    return DigitReader(glyphs, float(cfg["threshold"]))


def read_damage(reader: DigitReader, frame: Frame, cfg: dict) -> int | None:
    """Overall damage in %; None when the number is not readable (covered, mid-animation)."""
    value = reader.read(frame, tuple(cfg["region"]))
    return value if value is not None and 0 <= value <= 100 else None
