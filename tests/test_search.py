"""Farm config, loot filter and the search task (fixture frames on a scripted fake device)."""

import json
from pathlib import Path

import pytest

from cob.attack.loot import Loot, LootReader, better, worth_attacking
from cob.core.config import FarmConfig, load_farm_config, save_farm_config
from cob.core.human import Humanizer
from cob.screens.classifier import ScreenClassifier
from cob.screens.navigator import NavConfig, Navigator
from cob.tasks.search import ACCEPTED, FAILED, LOW_GOLD, MAX_NEXTS, SearchOutcome, SearchTask
from cob.vision.ocr import DigitReader
from cob.vision.regions import load_regions
from cob.vision.templates import TemplateStore
from tests.fakes import FakeClock, FakeDevice

EXACT = Humanizer(enabled=False)  # exact centres; jitter has its own tests

# --- config ---------------------------------------------------------------------------------


def test_config_defaults_when_missing(tmp_path):
    assert load_farm_config(tmp_path / "nope.json") == FarmConfig()


def test_config_roundtrip(tmp_path):
    cfg = FarmConfig(min_gold_elixir=500_000, min_dark=0, max_nexts=10, min_own_gold=20_000)
    assert load_farm_config(save_farm_config(cfg, tmp_path / "farm.json")) == cfg


def test_config_clamps_and_rejects_bad_values(tmp_path, caplog):
    p = tmp_path / "farm.json"
    p.write_text(json.dumps({"max_nexts": 9999, "min_dark": -5, "min_gold_elixir": "lots",
                             "min_own_gold": True, "unknown": 1}), "utf-8")
    cfg = load_farm_config(p)
    assert cfg.max_nexts == 500 and cfg.min_dark == 0
    assert cfg.min_gold_elixir == FarmConfig().min_gold_elixir  # wrong type -> default
    assert cfg.min_own_gold == FarmConfig().min_own_gold  # bool is not an int here


@pytest.mark.parametrize("text", ["{broken", "[1, 2]"])
def test_config_unreadable_falls_back(tmp_path, text):
    p = tmp_path / "farm.json"
    p.write_text(text, "utf-8")
    assert load_farm_config(p) == FarmConfig()


# --- filter ---------------------------------------------------------------------------------

CFG = FarmConfig()


@pytest.mark.parametrize("loot, ok", [
    (Loot(400_000, 400_000, 0), True),  # exactly 800k
    (Loot(400_000, 399_999, 0), False),
    (Loot(10_000, 10_000, 8_000), True),  # dark rule
    (Loot(10_000, 10_000, 7_999), False),
])
def test_worth_attacking(loot, ok):
    assert worth_attacking(loot, CFG) is ok


def test_dark_rule_disabled_with_zero():
    assert not worth_attacking(Loot(0, 0, 50_000), FarmConfig(min_dark=0))


def test_better_keeps_richest():
    a, b = Loot(500_000, 100_000, 0), Loot(300_000, 400_000, 0)
    assert better(None, a) == a and better(a, b) == b and better(b, a) == b


# --- search task ----------------------------------------------------------------------------

LOOT_A = Loot(1_091_869, 703_349, 10_896)  # search_a passes
LOOT_E = Loot(367_503, 404_004, 2_175)  # search_e fails (771k, dark 2k)


@pytest.fixture(scope="module")
def parts():
    store = TemplateStore()
    regions = load_regions(store.root)
    digits = DigitReader(store.load_dir("digits/loot"))
    return ScreenClassifier(store), LootReader(digits, regions["loot"]), LootReader(digits, regions["bar"])


@pytest.mark.parametrize("name, want", [
    ("wide_a", Loot(35_644, 320_921, 4_206)),
    ("wide_b", Loot(548_370, 607_216, 5_241)),
    ("wide_c", Loot(1_358_928, 1_334_275, 7_618)),
    ("wide_d", Loot(320_000, 183_055, 300)),
])
def test_loot_rows_keep_their_leading_digit(parts, name, want):
    # #91: elixir and dark start a few px left of gold; the old region (x 80) cut their first digit
    # (320 921 read as 20 921, 4 206 as 206). Real crops of the loot rows, frame rows 100..250.
    import cv2
    import numpy as np

    from cob.vision.frame import Frame

    frame = np.zeros((900, 1600, 3), np.uint8)
    frame[100:250, 0:260] = cv2.imread(str(Path(__file__).parent / "fixtures" / "bar" / f"loot_{name}.png"))
    assert parts[1].read(Frame(frame)) == want


def _task(parts, dev, cfg=CFG):
    clf, loot, bar = parts
    clock = FakeClock()
    nav = Navigator(dev, clf, NavConfig(), clock=clock, sleep=clock.sleep,
                    human=EXACT)
    return SearchTask(nav, loot, bar, cfg)


def _taps(dev):
    return [a[3] for a in dev.actions if a[0] == "tap"]  # which screen each tap landed on


def test_dry_run_nexts_until_filter_passes_then_leaves(parts):
    dev = FakeDevice("home", "attack_menu", "~searching", "search_e", "~searching", "search_a", "home")
    out = _task(parts, dev).run(dry_run=True)
    assert out.status == ACCEPTED and out.attack
    assert out.loot == LOOT_A and out.nexts == 1 and out.seen == [LOOT_E, LOOT_A]
    assert out.best_skipped == LOOT_E
    # Battle, Find a Match, Next on e, End Battle on a (dry run) - each on its confirmed screen
    assert _taps(dev) == ["home", "attack_menu", "search_e", "search_a"]
    assert dev.showing == "home"


def test_wet_run_stays_on_accepted_base(parts):
    dev = FakeDevice("home", "attack_menu", "~searching", "search_a", "home")
    out = _task(parts, dev).run(dry_run=False)
    assert out.status == ACCEPTED and dev.showing == "search_a"
    assert _taps(dev) == ["home", "attack_menu"]  # no End Battle: the attack task takes over


def test_army_review_confirmed_with_attack(parts):
    dev = FakeDevice("home", "attack_menu", "army_review", "~searching", "search_a", "home")
    out = _task(parts, dev).run(dry_run=True)
    assert out.status == ACCEPTED and out.loot == LOOT_A
    assert _taps(dev) == ["home", "attack_menu", "army_review", "search_a"]


def test_army_review_without_attack_button_fails_safely(parts):
    dev = FakeDevice("home", "attack_menu", "army", "home")  # Edit Army view: brown Battle, no Attack!
    out = _task(parts, dev).run(dry_run=True)
    assert out.status == FAILED and "army" in out.reason and dev.showing == "home"


def test_max_nexts_takes_current_base(parts):
    dev = FakeDevice("home", "attack_menu", "~searching", "search_e", "home")
    out = _task(parts, dev, FarmConfig(max_nexts=0)).run(dry_run=True)
    assert out.status == MAX_NEXTS and out.attack and out.loot == LOOT_E and out.nexts == 0


def test_low_own_gold_never_starts_search(parts):
    dev = FakeDevice("home")  # own gold 2,235,005
    out = _task(parts, dev, FarmConfig(min_own_gold=3_000_000)).run()
    assert out.status == LOW_GOLD and not out.attack and out.own_gold == 2_235_005
    assert dev.actions == []


def test_low_own_gold_during_search_ends_battle(parts):
    # home 2,235,005 passes; own gold on the search_e frame is lower -> stop after the first base
    dev = FakeDevice("home", "attack_menu", "~searching", "search_e", "home")
    out = _task(parts, dev, FarmConfig(min_own_gold=2_232_000, max_nexts=5)).run(dry_run=False)
    assert out.status == LOW_GOLD and not out.attack
    assert _taps(dev)[-1] == "search_e" and dev.showing == "home"  # End Battle, back home


def test_attack_menu_never_opens_fails_safely(parts):
    dev = FakeDevice("home", "home", "home", "home")  # Battle taps do nothing
    out = _task(parts, dev).run()
    assert out.status == FAILED and not out.attack and "after 3 Battle taps" in out.reason
    assert _taps(dev) == ["home", "home", "home"]


def test_ignored_battle_tap_is_retried(parts):
    # Fresh game start: the first Battle tap is ignored, the second opens the menu.
    dev = FakeDevice("home", "home", "attack_menu", "~searching", "search_a", "home")
    out = _task(parts, dev).run(dry_run=True)
    assert out.status == ACCEPTED and _taps(dev)[:3] == ["home", "home", "attack_menu"]


def test_other_device_blocks_search(parts):
    dev = FakeDevice("other_device")
    out = _task(parts, dev).run()
    assert out.status == FAILED and out.reason == "stopped on POPUP_OTHER_DEVICE" and dev.actions == []


def test_search_blocked_goes_home(parts):
    dev = FakeDevice("home", "attack_menu", "search_blocked", "home")
    out = _task(parts, dev).run(dry_run=False)
    assert out.status == FAILED and "try again later" in out.reason and dev.showing == "home"
    assert _taps(dev)[-1] == "search_blocked"  # Return Home on the cloud screen


def test_next_base_without_captured_clouds_is_still_read(parts):
    # #88: with ~1 s captures the clouds between bases are never seen; the loot change shows the new base.
    dev = FakeDevice("home", "attack_menu", "~searching", "search_e", "search_a", "home")
    task = _task(parts, dev)
    out = task.run(dry_run=False)
    assert out.status == ACCEPTED and out.loot == LOOT_A and out.nexts == 1
    assert task.nav.now() < 40  # no 30 s wait for a screen change that never comes


def test_battle_started_by_the_scout_timer_is_attacked(parts):
    dev = FakeDevice("home", "attack_menu", "~searching", "search_e", "battle")
    out = _task(parts, dev).run(dry_run=False)
    assert out.status == ACCEPTED and out.attack and out.reason == "scout timer ran out"
    assert out.nexts == 1 and out.loot is None and dev.showing == "battle"


def test_minimums_drop_every_n_nexts_down_to_the_floor():
    # #113: MyBot's search reduction, 5 % of the set values every 10 Nexts, never below 50 %.
    from cob.attack.loot import minimums

    cfg = FarmConfig(min_gold_elixir=800_000, min_dark=8_000, reduce_every=10, reduce_percent=5,
                     reduce_floor=50)
    assert minimums(cfg, 0) == minimums(cfg, 9) == (800_000, 8_000)
    assert minimums(cfg, 10) == (760_000, 7_600)
    assert minimums(cfg, 30) == (680_000, 6_800)
    assert minimums(cfg, 500) == (400_000, 4_000)
    assert minimums(FarmConfig(), 400) == (800_000, 8_000)  # off by default


def test_a_lowered_minimum_takes_a_base_skipped_before(parts):
    # search_e has 771k gold + elixir: skipped at 800k, taken once one Next lowered the minimum by 5 %.
    dev = FakeDevice("home", "attack_menu", "~searching", "search_e", "~searching", "search_e", "home")
    cfg = FarmConfig(reduce_every=1, reduce_percent=5)
    out = _task(parts, dev, cfg).run(dry_run=True)
    assert out.status == ACCEPTED and out.nexts == 1 and out.loot == LOOT_E
    assert worth_attacking(LOOT_E, cfg, 1) and not worth_attacking(LOOT_E, cfg, 0)


def test_army_still_training_is_an_army_wait(parts, monkeypatch):
    # #180 live (moto g84): right after an attack the menu shows "Attack available in: 39s" instead of
    # Find a Match; it was an unknown screen and counted as a failed search.
    import cob.tasks.search as search_mod
    from cob.tasks.search import ARMY_NOT_READY

    shots = []
    monkeypatch.setattr(search_mod, "save_snapshot", lambda *a, **kw: shots.append(a[1]))
    dev = FakeDevice("home", "attack_menu_training", "home")
    out = _task(parts, dev).run(dry_run=False)
    assert out.status == FAILED and out.reason == ARMY_NOT_READY
    assert shots == []  # no failure report for an army wait
    assert dev.showing == "home"  # left the menu


def test_next_base_skips_the_shown_base_and_searches_on(parts):
    # the attack could not see search_e's outline: Next, and the next base that passes is attacked
    dev = FakeDevice("search_e", "~searching", "search_a", "home")
    task = _task(parts, dev)
    before = SearchOutcome(ACCEPTED, None, 2)
    out = task.next_base(before)
    assert out.status == ACCEPTED and out.nexts == 3 and dev.showing == "search_a"
    assert _taps(dev) == ["search_e"]  # only Next; never went home


def test_next_base_that_has_to_stop_leaves_the_search(parts):
    dev = FakeDevice("search_e", "~searching", "search_e", "home")
    task = _task(parts, dev, FarmConfig(min_own_gold=10**9))  # own gold below reserve after the Next
    out = task.next_base(SearchOutcome(ACCEPTED, None, 0))
    assert out.status == LOW_GOLD and not out.attack
