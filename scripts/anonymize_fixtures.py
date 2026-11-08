"""Blur player, clan and opponent names in test screenshots before they are committed.

    python scripts/anonymize_fixtures.py tests/fixtures/frames/new_frame.jpg [...]

Names sit in a few fixed places at the 1600x900 game area; each box is blurred hard enough that no text
is left, while the colours around it (and every template the tests match) stay as they were. Pick the box
set from the screen type: --kind home | battle | bb_battle | log, or let it guess from the file name.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

BOXES = {  # x, y, w, h at 1600x900
    "home": [(150, 58, 240, 74)],  # own name + clan next to the Town Hall badge
    "battle": [(72, 6, 280, 78)],  # opponent name + clan, top left of search / battle / results
    # defender name (left), attacker name + clan (right); the "Attacker" label above stays sharp
    "bb_battle": [(74, 64, 310, 36), (1272, 43, 250, 56)],
    "log": [(110, 195, 330, 60), (110, 392, 330, 60), (110, 590, 330, 60), (110, 786, 330, 60)],
    "home_clan_label": [(735, 100, 170, 34)],  # clan name label over the clan castle
}


def guess(name: str) -> list[str]:
    if name.startswith("bb_battle") or name.startswith("bb_stage") or name == "bb_results.jpg":
        return ["bb_battle"]
    if name.startswith(("search_", "battle", "surrender")):
        return ["battle"]
    if name.startswith("popup_log"):
        return ["log", "home"]
    if name == "home_zoomed_no_boat.jpg":
        return ["home", "home_clan_label"]
    return ["home"]


def blur(img, box) -> None:
    x, y, w, h = box
    roi = img[y:y + h, x:x + w]
    small = cv2.resize(roi, (max(1, w // 30), max(1, h // 30)), interpolation=cv2.INTER_AREA)
    img[y:y + h, x:x + w] = cv2.GaussianBlur(cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR),
                                             (21, 21), 0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--kind", action="append", choices=sorted(BOXES))
    a = p.parse_args(argv)
    for f in a.files:
        img = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
        if img is None or img.shape[:2] != (900, 1600):
            print(f"skip {f}: not a 1600x900 frame")
            continue
        kinds = a.kind or guess(f.name)
        for k in kinds:
            for box in BOXES[k]:
                blur(img, box)
        # Near-lossless: the red deploy line is 1-2 px wide and a normal re-save moves the base fit.
        params = ([cv2.IMWRITE_JPEG_QUALITY, 100,
                   cv2.IMWRITE_JPEG_SAMPLING_FACTOR, cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444]
                  if f.suffix.lower() == ".jpg" else [])
        cv2.imwrite(str(f), img, params)
        print(f"{f}: {', '.join(kinds)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
