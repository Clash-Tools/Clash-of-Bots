"""Regression tests on real LDPlayer 14 frames (1600x900, JPEG q95; same results as the PNGs)."""

import tomllib
from pathlib import Path

import cv2
import numpy as np
import pytest

from cob.screens.classifier import ScreenClassifier
from cob.vision.frame import Frame
from cob.vision.ocr import DigitReader
from cob.vision.templates import TemplateStore, default_root

FRAMES = Path(__file__).parent / "fixtures" / "frames"
REGIONS = tomllib.loads((default_root() / "regions.toml").read_text("utf-8"))

SCREENS = {
    "home": "HOME",
    "home_dimmed_reload": "POPUP_RELOAD",
    "idle_reload": "POPUP_RELOAD",
    "other_device": "POPUP_OTHER_DEVICE",
    "loading": "LOADING",
    "attack_menu": "ATTACK_MENU",
    "attack_menu_training": "ARMY_TRAINING",  # #180: army still training
    "army": "ARMY",
    "army_review": "ARMY",
    "popup_log": "POPUP_GENERIC",
    "popup_recipe": "POPUP_GENERIC",
    "popup_upgrade": "POPUP_GENERIC",
    "shop": "SHOP",
    "builder_menu": "BUILDER_MENU",
    "searching": "SEARCHING",
    "search_blocked": "SEARCH_BLOCKED",
    "search_a": "ATTACK_SEARCH",
    "search_b": "ATTACK_SEARCH",
    "search_c": "ATTACK_SEARCH",
    "search_d": "ATTACK_SEARCH",
    "search_e": "ATTACK_SEARCH",
    "search_painted_scenery": "ATTACK_SEARCH",
    "battle": "BATTLE",
    "battle_end": "BATTLE_END",
    "surrender_confirm": "SURRENDER_CONFIRM",
    "launcher": "UNKNOWN",
    "bb_home": "BB_HOME",
    "bb_home_boat": "BB_HOME",
    "bb_attack_menu": "BB_ATTACK_MENU",
    "bb_battle_stage1": "BATTLE",  # shares the Overall Damage panel with the main village
    "bb_results": "BB_RESULTS",
    "bb_searching": "BB_SEARCHING",
    "bb_star_bonus": "BB_STAR_BONUS",
    "ld_topup_offer": "LDPLAYER_TOPUP",
    "boost_dialog": "BOOST_DIALOG",
    "events_window": "EVENTS_WINDOW",
    "home_star_bonus": "HOME_STAR_BONUS",
    "bb_stage1_countdown": "BB_STAGE_WAIT",
    "bb_battle_stage2_countdown": "BB_STAGE_WAIT",
    "home_zoomed_no_boat": "HOME",
}

# gold, elixir, dark: checked by eye against the frames
LOOT = {
    "search_a": (1_091_869, 703_349, 10_896),
    "search_b": (1_005_773, 936_242, 6_735),
    "search_c": (515_483, 507_683, 5_256),
    "search_d": (590_078, 1_218_455, 6_407),
    "search_e": (367_503, 404_004, 2_175),
    "battle": (883_041, 904_702, 9_376),
}

# Own resources in the top-right bar, same glyphs as loot
BAR = {
    "home": (2_235_005, 5_937_378, 50_344),
    "search_a": (2_230_805, 6_052_998, 50_344),
    "battle_end": (2_233_605, 6_052_998, 50_344),
    "search_painted_scenery": (18_544_974, 23_000_000, 192_375),  # 8 digits, full elixir storage
}


def _frame(name: str) -> np.ndarray:
    img = cv2.imread(str(FRAMES / f"{name}.jpg"), cv2.IMREAD_COLOR)
    assert img is not None, f"missing fixture {name}.jpg"
    return img


@pytest.fixture(scope="module")
def store():
    return TemplateStore()


@pytest.fixture(scope="module")
def classifier(store):
    return ScreenClassifier(store)


@pytest.fixture(scope="module")
def loot_reader(store):
    return DigitReader(store.load_dir("digits/loot"))


@pytest.mark.parametrize("name, screen", SCREENS.items())
def test_classify_real_frame(classifier, name, screen):
    assert classifier.classify(Frame(_frame(name))).screen == screen


@pytest.mark.parametrize("name, expected", LOOT.items())
def test_read_search_loot(loot_reader, name, expected):
    frame = Frame(_frame(name))
    loot = REGIONS["loot"]
    got = tuple(loot_reader.read(frame, loot[k]) for k in ("gold", "elixir", "dark"))
    assert got == expected


@pytest.mark.parametrize("name, expected", BAR.items())
def test_read_resource_bar(loot_reader, name, expected):
    frame = Frame(_frame(name))
    bar = REGIONS["bar"]
    assert tuple(loot_reader.read(frame, bar[k]) for k in ("gold", "elixir", "dark")) == expected


@pytest.mark.parametrize("name, cost", [("search_a", "next_search"), ("attack_menu", "find_match")])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_screen_ignores_variable_cost(classifier, name, cost, seed):
    # Search / match costs change with Town Hall and league: scramble them, the screen must not change.
    img = _frame(name)
    x, y, w, h = REGIONS["costs"][cost]
    img[y : y + h, x : x + w] = np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype=np.uint8)
    assert classifier.classify(Frame(img)).screen == SCREENS[name]


@pytest.mark.parametrize("scale", [1.0, 1.02])
@pytest.mark.parametrize("name, want", [
    ("surrender_confirm", "SURRENDER_CONFIRM"), ("idle_reload", "POPUP_RELOAD"),
    ("other_device", "POPUP_OTHER_DEVICE"), ("boost_dialog", "BOOST_DIALOG"),
    ("home_star_bonus", "HOME_STAR_BONUS"),
])
def test_dialogs_at_phone_scale(scale, name, want):
    # #166 live (moto g84): dialogs are drawn ~2 % larger on phones. The Surrender? dialog was not
    # recognised, so every surrender waited 6 s before tapping Okay blind.
    import cv2

    from cob.screens.classifier import ScreenClassifier
    from cob.vision.templates import TemplateStore

    frame = cv2.imread(str(FRAMES / f"{name}.jpg"))
    h, w = frame.shape[:2]
    frame = cv2.warpAffine(frame, cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale), (w, h))
    assert ScreenClassifier(TemplateStore()).classify(frame).screen == want
