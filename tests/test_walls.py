"""Wall spend-safety checks: pure functions and single fixture reads (fast)."""

import cv2
import numpy as np
import pytest

from cob.attack.loot import Loot
from cob.core.config import FarmConfig
from cob.tasks.walls import (
    CONFIRM_COST,
    CONFIRM_ICON,
    ELIXIR,
    GOLD,
    cost_is_red,
    drop_matches,
    hammer_icon_box,
    icon_resource,
    pick_resource,
)
from cob.vision.frame import Frame
from cob.vision.match import match_all
from cob.vision.ocr import DigitReader
from cob.vision.templates import TemplateStore
from tests.fakes import FRAMES

COST = 1_500_000


@pytest.fixture(scope="module")
def store():
    return TemplateStore()


def test_off_by_default():
    assert FarmConfig().wall_upgrades == 0 and FarmConfig().wall_reserve == 1_000_000


@pytest.mark.parametrize("own, expected", [
    (Loot(8_500_000, 6_400_000, 0), GOLD),
    (Loot(2_000_000, 6_400_000, 0), ELIXIR),  # gold would drop below the 1M reserve
    (Loot(2_000_000, 2_400_000, 0), None),  # neither stays above the reserve
    (Loot(2_500_000, 0, 0), GOLD),  # exactly the reserve left is allowed
])
def test_pick_resource_keeps_reserve(own, expected):
    assert pick_resource(own, COST, 1_000_000) == expected


def test_drop_must_match_cost():
    before = Loot(8_504_022, 6_419_337, 67_495)
    assert drop_matches(before, Loot(7_004_022, 6_419_337, 67_495), GOLD, COST)
    assert not drop_matches(before, Loot(8_504_022, 6_419_337, 67_495), GOLD, COST)  # nothing spent
    assert not drop_matches(before, Loot(5_504_022, 6_419_337, 67_495), GOLD, COST)  # spent too much


def test_panel_buttons_gold_and_elixir_never_ring(store):
    frame = cv2.imread(str(FRAMES / "wall_panel.jpg"))
    hammers = match_all(Frame(frame), store.get("upgrade_hammer"), (0, 680, 1600, 220), 0.8)
    assert sorted(icon_resource(frame, hammer_icon_box(h)) for h in hammers) == [ELIXIR, GOLD]
    assert all(h.x < 690 for h in hammers)  # the Wall Ring button (x ~ 700) is never a hammer


def test_confirm_cost_read_and_checks():
    strip = cv2.imread(str(FRAMES.parent / "bar" / "wall_confirm_cost.png"))
    frame = np.zeros((900, 1600, 3), np.uint8)
    frame[760:860, 990:1260] = strip
    digits = DigitReader(TemplateStore().load_dir("digits/cost"))
    assert digits.read(Frame(frame), CONFIRM_COST) == COST
    assert icon_resource(frame, CONFIRM_ICON) == GOLD and not cost_is_red(frame, CONFIRM_COST)


def test_red_cost_is_detected():
    frame = np.zeros((900, 1600, 3), np.uint8)
    x, y, w, h = CONFIRM_COST
    frame[y + 10:y + 30, x + 20:x + 120] = (40, 40, 230)  # red text
    assert cost_is_red(frame, CONFIRM_COST)
