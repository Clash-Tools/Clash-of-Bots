"""#119: storage fill from the home screen's resource bars (real frames + painted bars)."""

from pathlib import Path

import cv2
import pytest

from cob.attack.storage import BAR_LEFT, BAR_RIGHT, BARS, storage_fill

FRAMES = Path(__file__).parent / "fixtures" / "frames"


def test_fill_of_a_real_home_screen():
    # home.jpg: 2,235,005 gold shows as a sliver, 5,937,378 elixir as about a fifth of the bar.
    fill = storage_fill(cv2.imread(str(FRAMES / "home.jpg")))
    assert fill["gold"] == pytest.approx(0.015, abs=0.01)
    assert fill["elixir"] == pytest.approx(0.20, abs=0.02)


@pytest.mark.parametrize("share", [0.0, 0.5, 1.0])
def test_painted_bars_read_back(share):
    frame = cv2.imread(str(FRAMES / "home.jpg"))
    colours = {"gold": (40, 200, 250), "elixir": (220, 60, 200)}  # BGR fill colours
    for kind, (_, _, y0, y1) in BARS.items():
        frame[y0:y1, BAR_LEFT:BAR_RIGHT + 1] = (60, 60, 60)  # empty bar
        width = round(share * (BAR_RIGHT - BAR_LEFT + 1))
        if width:
            frame[y0 + 8:y1 - 8, BAR_RIGHT + 1 - width:BAR_RIGHT + 1] = colours[kind]
            frame[y0 + 18:y0 + 22, BAR_RIGHT - 40:BAR_RIGHT - 37] = (255, 255, 255)  # a digit stroke
    fill = storage_fill(frame)
    assert fill["gold"] == pytest.approx(share, abs=0.01) and fill["elixir"] == pytest.approx(share, abs=0.01)
