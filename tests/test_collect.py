"""Collector bubbles on real home frames."""

import cv2
import pytest

from cob.core.human import Humanizer
from cob.screens.classifier import ScreenClassifier
from cob.screens.navigator import NavConfig, Navigator
from cob.tasks.collect import BUBBLES, CollectTask, _in_hud
from cob.vision.frame import Frame
from cob.vision.match import match_all
from cob.vision.templates import TemplateStore
from tests.fakes import FRAMES, FakeClock

EXACT = Humanizer(enabled=False)


@pytest.fixture(scope="module")
def store():
    return TemplateStore()


def _bubbles(store, name):
    f = Frame(cv2.imread(str(FRAMES / f"{name}.jpg")))
    return {n: len(match_all(f, store.get(n), None, None)) for n in BUBBLES}


def test_home_frame_bubbles(store):
    assert _bubbles(store, "home") == {"collect_gold": 7, "collect_elixir": 7, "collect_dark": 3}


@pytest.mark.parametrize("name", ["search_a", "bb_home", "army", "battle"])
def test_no_bubbles_where_there_are_none(store, name):
    assert sum(_bubbles(store, name).values()) == 0


def test_hud_is_excluded():
    assert _in_hud(1500, 100) and _in_hud(100, 800) and _in_hud(60, 240) and not _in_hud(800, 450)
    assert not _in_hud(222, 282)  # loot cart next to the trophy button


class CollectDevice:
    """Home with bubbles; after a round of taps the same village without bubbles."""

    serial = "fake"

    def __init__(self):
        self.full = cv2.imread(str(FRAMES / "home.jpg"))
        self.empty = cv2.imread(str(FRAMES / "home_zoomed_no_boat.jpg"))
        self.taps = []

    def capture(self):
        return self.empty if len(self.taps) >= 3 else self.full

    def tap(self, x, y):
        self.taps.append((x, y))

    def foreground_package(self):
        return "com.supercell.clashofclans"


def test_collect_taps_one_bubble_per_type(store):
    dev = CollectDevice()
    clock = FakeClock()
    nav = Navigator(dev, ScreenClassifier(store), NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT)
    out = CollectTask(nav, max_rounds=1).run()
    # one tap per resource type collects them all; never a second tap on a bare collector
    assert out.ok and out.rounds == 1 and out.tapped == {"collect_gold": 1, "collect_elixir": 1,
                                                         "collect_dark": 1} and len(dev.taps) == 3
    assert all(not _in_hud(x, y) for x, y in dev.taps)



def _hits(store, frame, name):
    return match_all(Frame(cv2.imread(str(FRAMES / f"{frame}.jpg"))), store.get(name), None, None)


def test_loot_cart_label_and_panel(store):
    from cob.vision.match import match

    (hit,) = _hits(store, "home_loot_cart", "loot_cart_label")
    assert not _in_hud(*hit.center)
    panel = Frame(cv2.imread(str(FRAMES / "loot_cart_selected.jpg")))
    assert match(panel, store.get("loot_cart_title")) and match(panel, store.get("loot_cart_collect"))


@pytest.mark.parametrize("name", ["search_a", "battle", "army", "bb_home"])
def test_no_loot_cart_where_there_is_none(store, name):
    assert _hits(store, name, "loot_cart_label") == []


class _BbHome:
    """Builder Base home with three full collectors; each bubble tap empties the view of them."""

    serial = "fake"

    def __init__(self):
        self.full = cv2.imread(str(FRAMES / "bb_home.jpg"))
        self.empty = cv2.imread(str(FRAMES / "bb_home_boat.jpg"))  # same screen, no bubbles
        self.taps = []

    def capture(self):
        return self.full if len(self.taps) < 3 else self.empty

    def tap(self, x, y):
        self.taps.append((x, y))

    def key(self, code):
        pass

    def foreground_package(self):
        return "com.supercell.clashofclans"


def test_builder_base_taps_every_bubble_once():
    from cob.tasks.collect import collect_builder_base

    dev, clock = _BbHome(), FakeClock()
    nav = Navigator(dev, ScreenClassifier(TemplateStore()), NavConfig(), clock=clock, sleep=clock.sleep,
                    human=EXACT)
    assert collect_builder_base(nav) == {"gold": 1, "elixir": 1, "gems": 1}
    assert len(dev.taps) == 3 and not any(_in_hud(x, y) for x, y in dev.taps)
