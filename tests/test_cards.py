"""Unit database and troop-bar card recognition (step 2 of troop detection)."""

import tomllib
from pathlib import Path

import cv2
import numpy as np
import pytest

from cob.attack.cards import CardLibrary, fingerprint, observe, portrait, similarity
from cob.attack.troops import read_bar
from cob.units import UnitDB

BAR = Path(__file__).parent / "fixtures" / "bar"
CFG = tomllib.loads((Path(__file__).parents[1] / "assets/templates/1600x900/attack.toml").read_text())["bar"]


def _frame(name: str) -> np.ndarray:
    f = np.zeros((900, 1600, 3), np.uint8)
    f[730:900] = cv2.imread(str(BAR / f"{name}.png"))
    return f


def _cards(name: str):
    f = _frame(name)
    return f, read_bar(f, CFG)


def test_bundled_unit_database_loads():
    db = UnitDB()
    assert db.version.startswith("data-v") and len(db) >= 140
    sv = db.get("super_valkyrie")
    assert sv.kind == "super_troop" and sv.super_of == "valkyrie" and sv.dark and sv.housing_space == 20
    assert db.get("totem_spell").is_spell
    picks = db.choices()
    assert picks[0].kind == "troop" and picks[-1].kind in ("spell", "event_spell")
    assert all(u.village == "home" for u in picks)


def test_same_unit_matches_across_counts_and_levels_others_do_not():
    # golem x11 level 15 (green) and x12 level 17 (home_upgrade_arrows); the wall breaker is another unit
    f1, c1 = _cards("green")
    f2, c2 = _cards("home_upgrade_arrows")
    golem_a, golem_b = (fingerprint(portrait(f, c[0])) for f, c in ((f1, c1), (f2, c2)))
    breaker = fingerprint(portrait(f1, c1[1]))
    assert similarity(golem_a, golem_b) > 0.95
    assert similarity(golem_a, breaker) < 0.8


def test_unknown_cards_are_saved_once_then_labelled_and_recognised(tmp_path):
    lib = CardLibrary(folder=tmp_path)
    f, cards = _cards("green")
    assert observe(lib, f, cards) == [None] * len(cards)
    saved = lib.unknown()
    assert len(saved) == len(cards) and all(p.with_suffix(".json").exists() for p in saved)
    observe(lib, f, cards)  # the same bar again: nothing new
    assert len(lib.unknown()) == len(cards)

    first = sorted(saved)[0]
    dest = lib.label(first, "golem")
    assert dest.name == "golem.png" and not first.exists()
    assert observe(lib, f, cards)[0] == "golem"
    # a fresh library (next run) reads the labelled folder
    again = CardLibrary(folder=tmp_path)
    f2, c2 = _cards("home_upgrade_arrows")
    assert observe(again, f2, c2)[0] == "golem"
    before = len(again.unknown())
    assert before >= len(cards) - 1  # the 8 still unlabelled + cards only that bar has
    observe(again, f, cards)
    assert len(again.unknown()) == before  # the first bar's cards are all saved already


def test_discard_and_cap(tmp_path, monkeypatch):
    import cob.attack.cards as cards_mod

    lib = CardLibrary(folder=tmp_path)
    f, cards = _cards("green")
    observe(lib, f, cards)
    lib.discard(lib.unknown()[0])
    assert len(lib.unknown()) == len(cards) - 1
    monkeypatch.setattr(cards_mod, "MAX_UNKNOWN", 0)
    assert CardLibrary(folder=tmp_path / "x").remember(portrait(f, cards[0]), "troop") is None


def test_observe_never_raises(tmp_path):
    lib = CardLibrary(folder=tmp_path)
    f, cards = _cards("green")
    assert observe(lib, f[:10], cards) is not None  # a frame too small for the portrait band


@pytest.mark.parametrize("name", ["green", "super_valkyrie_spell"])
def test_database_pictures_are_used(tmp_path, name):
    f, cards = _cards(name)
    pic = tmp_path / "db" / "detection" / "1600x900" / "cards" / "x.png"
    pic.parent.mkdir(parents=True)
    cv2.imwrite(str(pic), portrait(f, cards[0]))
    db_cards = {"some_unit": ("detection/1600x900/cards/x.png",)}
    lib = CardLibrary(tmp_path / "db", db_cards, folder=tmp_path / "u")
    assert observe(lib, f, cards)[0] == "some_unit"
