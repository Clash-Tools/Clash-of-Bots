"""#185: load a Saved Recipe as the army when a run starts."""

import pytest

from cob.core.human import Humanizer
from cob.screens.classifier import ScreenClassifier
from cob.screens.navigator import NavConfig, Navigator
from cob.tasks.army import ArmyRecipe, recipe_row
from cob.vision.templates import TemplateStore
from tests.fakes import FakeClock, FakeDevice


@pytest.fixture(scope="module")
def classifier():
    return ScreenClassifier(TemplateStore())


def _recipe(classifier, dev):
    clock = FakeClock()
    nav = Navigator(dev, classifier, NavConfig(), clock=clock, sleep=clock.sleep,
                    human=Humanizer(enabled=False))
    return ArmyRecipe(nav)


@pytest.mark.parametrize("menu", ["attack_menu", "attack_menu_training"])
def test_recipe_row_is_tapped_through_edit_army(classifier, menu):
    # Battle -> menu (also the "Attack available in" one) -> Edit Army -> Saved Recipes arrow -> row 2.
    dev = FakeDevice("home", menu, "army", "army_recipes_open", "army", "home")
    assert _recipe(classifier, dev).select(2)
    taps = [a[1:3] for a in dev.actions if a[0] == "tap"]
    assert recipe_row(2) in taps and taps.index(recipe_row(2)) == 3  # the fourth tap picks the row
    assert dev.showing == "home"


def test_a_missing_step_keeps_the_army_and_goes_home(classifier):
    dev = FakeDevice("home", "attack_menu", "home")  # Edit Army tap does nothing: no army screen
    assert not _recipe(classifier, dev).select(1)


def test_slot_out_of_range(classifier):
    with pytest.raises(ValueError):
        _recipe(classifier, FakeDevice("home")).select(5)


def _farm(script, prepare, cycles):
    import random

    from cob.tasks.farm import FarmLimits, FarmTask

    clock = FakeClock()
    task = FarmTask(script.search, script.attack, script.own, FarmLimits(max_cycles=cycles), clock=clock,
                    sleep=clock.sleep, rng=random.Random(0), prepare=prepare)
    return task.run()


def test_farm_prepares_once_before_the_first_cycle():
    from tests.test_farm import Script, accepted

    calls = []
    stats = _farm(Script([accepted(), accepted()]), lambda: calls.append(1), 2)
    assert calls == [1] and len(stats.cycles) == 2


def test_failed_preparation_does_not_stop_the_run():
    from tests.test_farm import Script, accepted

    def boom():
        raise RuntimeError("army screen gone")

    assert _farm(Script([accepted()]), boom, 1).stop_reason == "1 cycles done"


def test_an_ignored_tap_is_tapped_again(classifier):
    # Live (moto g84): the first tap on a screen that has just opened is often ignored.
    class Lazy(FakeDevice):
        def __init__(self, *names):
            super().__init__(*names)
            self.ignored = False

        def tap(self, x, y):
            if self.showing == "attack_menu" and not self.ignored:  # the first Edit Army tap is lost
                self.ignored = True
                self.actions.append(("tap", x, y, self.showing))
                return
            super().tap(x, y)

    dev = Lazy("home", "attack_menu", "army", "army_recipes_open", "army", "home")
    assert _recipe(classifier, dev).select(1)
    assert dev.ignored
