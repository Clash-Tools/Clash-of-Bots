"""Builder Base: two-stage attack and getting there by boat, on real BB fixture frames."""

import cv2
import pytest

from cob.attack.geometry import load_attack_config
from cob.core.human import Humanizer
from cob.screens.classifier import ScreenClassifier
from cob.screens.navigator import NavConfig, Navigator
from cob.tasks.builder import DONE, FAILED, BbAttackTask, go_to_builder_base
from cob.vision.templates import TemplateStore
from tests.fakes import FRAMES, FakeClock

BAR = FRAMES.parent / "bar"

EXACT = Humanizer(enabled=False)


def _img(name):
    return cv2.imread(str(FRAMES / f"{name}.jpg"))


class BbDevice:
    """Scripted BB battle. Phases change on the taps a player would make; battle phases advance
    after a number of captures (the game moving on by itself)."""

    serial = "fake"

    def __init__(self, two_stages=True, start="bb_home"):
        self.f = {n: _img(n) for n in ("home", "home_zoomed_no_boat", "bb_home", "bb_home_boat",
                                       "bb_attack_menu", "bb_searching", "bb_stage1_countdown",
                                       "bb_battle_stage1", "bb_battle_stage2_countdown", "bb_results")}
        # troop bars from lossless strips (JPEG blurs the level badges, D-017)
        strips = (("bb_stage1_countdown", "bb_stage1"), ("bb_battle_stage2_countdown", "bb_stage2"))
        for frame, strip in strips:
            self.f[frame][730:900] = cv2.imread(str(BAR / f"{strip}.png"))
        self.f["bb_battle_stage2"] = self.f["bb_battle_stage1"].copy()  # fighting, same bar as its countdown
        self.f["bb_battle_stage1"][730:900] = self.f["bb_stage1_countdown"][730:900]
        self.f["bb_battle_stage2"][730:900] = self.f["bb_battle_stage2_countdown"][730:900]
        self.phase = start
        self.two_stages = two_stages
        self.captures_in_phase = 0
        self.taps = []
        self.card_taps = {"stage1": 0, "stage2": 0}
        self.selected = None
        self.placed: set[int] = set()  # x of cards placed this stage: drawn greyed out

    def capture(self):
        self.captures_in_phase += 1
        auto = {"bb_searching": ("stage1_wait", 2), "stage1_battle": ("stage1_done", 12),
                "stage2_battle": ("results", 12)}
        if self.phase in auto and self.captures_in_phase > auto[self.phase][1]:
            self._go(auto[self.phase][0])
        if self.phase == "stage1_done":
            self._go("stage2_wait" if self.two_stages else "results")
        frame = self.f[{"stage1_wait": "bb_stage1_countdown", "stage1_battle": "bb_battle_stage1",
                        "stage2_wait": "bb_battle_stage2_countdown", "stage2_battle": "bb_battle_stage2",
                        "results": "bb_results"}.get(self.phase, self.phase)].copy()
        if "stage" in self.phase:
            for x in self.placed:  # greyed out: no colour, darker
                bar = frame[745:885, x - 50:x + 50]
                grey = cv2.cvtColor(cv2.cvtColor(bar, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
                frame[745:885, x - 50:x + 50] = grey // 2 + 40
        return frame

    def _go(self, phase):
        if phase == "stage2_wait":
            self.placed = set()
        self.phase, self.captures_in_phase = phase, 0

    def tap(self, x, y):
        self.taps.append((x, y, self.phase))
        if self.phase in ("home", "home_boat") and 1240 < x < 1290 and 180 < y < 230:
            self._go("bb_home")
        elif self.phase == "bb_home" and x < 200 and y > 700:
            self._go("bb_attack_menu")
        elif self.phase == "bb_attack_menu" and 1060 < x < 1320 and 540 < y < 640:
            self._go("bb_searching")
        elif "stage" in self.phase and y > 760:
            self.card_taps["stage1" if self.phase.startswith("stage1") else "stage2"] += 1
            self.selected = x
        elif "stage" in self.phase and y < 730 and self.selected is not None:
            self.placed.add(self.selected)  # a troop landed: battle starts
            if self.phase.endswith("_wait"):
                self._go("stage1_battle" if self.phase == "stage1_wait" else "stage2_battle")
        elif self.phase == "results" and 700 < x < 900 and 690 < y < 810:
            self._go("bb_home")

    def swipe(self, *a):
        self.taps.append(("swipe", *a))

    def key(self, code):
        pass

    def foreground_package(self):
        return "com.supercell.clashofclans"


@pytest.fixture(scope="module")
def parts():
    store = TemplateStore()
    return ScreenClassifier(store), load_attack_config(store.root)


def _task(parts, dev):
    clf, (border, deploy, bar, _) = parts
    clock = FakeClock()
    nav = Navigator(dev, clf, NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT)
    return BbAttackTask(nav, border, deploy, bar), clock


def test_two_stage_battle_deploys_twice_and_returns_home(parts):
    dev = BbDevice(two_stages=True)
    task, _ = _task(parts, dev)
    out = task.run()
    assert out.status == DONE and out.stages == 2, out
    assert out.deployed[0] == 5  # hero + 4 cards in stage 1
    assert out.deployed[1] == 1  # only the stage-2 reinforcement is unused in the stage-2 frame
    assert dev.phase == "bb_home"


def test_battle_ending_in_stage_one(parts):
    dev = BbDevice(two_stages=False)
    task, _ = _task(parts, dev)
    out = task.run()
    assert out.status == DONE and out.stages == 1 and dev.phase == "bb_home"


def test_never_taps_the_spell_or_empty_slots(parts):
    dev = BbDevice()
    task, _ = _task(parts, dev)
    task.run()
    bar_taps = [(x, y) for x, y, *_ in dev.taps if isinstance(x, int) and y > 760]
    assert bar_taps and all(x < 900 for x, _ in bar_taps)  # empty slots start at x ~ 765+ only in stage 2


def test_go_to_builder_base_by_boat(parts):
    clf, _ = parts
    dev = BbDevice(start="bb_home_boat")
    dev.f["bb_home_boat"] = _img("bb_home_boat")
    clock = FakeClock()
    nav = Navigator(dev, clf, NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT)
    # starting in BB already: nothing to do
    dev.phase = "bb_home"
    assert go_to_builder_base(nav) and dev.taps == []


def test_unreachable_builder_base_fails_safely(parts):
    clf, (border, deploy, bar, _) = parts

    class Stuck(BbDevice):
        def capture(self):
            return self.f["home_zoomed_no_boat"]  # boat off screen, drags change nothing

    dev = Stuck()
    clock = FakeClock()
    nav = Navigator(dev, clf, NavConfig(timeout_s=60), clock=clock, sleep=clock.sleep, human=EXACT)
    out = BbAttackTask(nav, border, deploy, bar).run()
    assert out.status == FAILED and "Builder Base" in out.reason
    assert all(t[0] == "swipe" for t in dev.taps)  # only map drags, never blind taps


def test_bb_farm_loop_counts_attacks_without_resource_reads(parts):
    from types import SimpleNamespace

    from cob.tasks.farm import FarmLimits
    from cob.tasks.wiring import bb_farm_task

    results = iter(["done", "failed", "done"])
    calls = []

    class FakeBb:
        def run(self):
            calls.append(1)
            return SimpleNamespace(status=next(results), reason="")

    import threading

    fake_parts = SimpleNamespace(nav=SimpleNamespace(stop=threading.Event()), bb=FakeBb(), recover=None,
                                 bb_resources=None, bb_maintain=lambda: None)
    clock = FakeClock()
    task = bb_farm_task(fake_parts, FarmLimits(max_cycles=3))
    task._clock, task._sleep = clock, clock.sleep
    stats = task.run()
    assert len(calls) == 3 and stats.attacks == 2 and stats.stop_reason == "3 cycles done"


def _strip(name):
    import numpy as np

    frame = np.zeros((900, 1600, 3), np.uint8)
    frame[730:900] = cv2.imread(str(BAR / f"{name}.png"))
    return frame


@pytest.mark.parametrize("name, count", [("bb_upgrade_arrows", 7), ("bb_stage1", 5)])
def test_bb_cards_found_whatever_the_badges_look_like(name, count):
    from cob.attack.troops import find_cards

    cards = find_cards(_strip(name))  # x1 counts + green upgrade arrows broke the badge reader
    assert len(cards) == count and not any(c.used for c in cards)


def test_bb_stage2_offers_only_the_unused_reinforcement():
    from cob.attack.troops import find_cards

    assert len(find_cards(_strip("bb_stage2"))) == 1



def test_only_the_machine_gets_a_second_tap(parts):
    dev = BbDevice(two_stages=False)
    task, _ = _task(parts, dev)
    task.run()
    from collections import Counter

    per_card = Counter(x for x, y, *_ in dev.taps if isinstance(x, int) and y > 760)
    others = {x: n for x, n in per_card.items() if x >= 200}
    assert any(x < 200 and n == 2 for x, n in per_card.items())  # the machine: deploy + ability
    assert others and all(n == 1 for n in others.values())  # troop cards: one tap each, never a re-tap
