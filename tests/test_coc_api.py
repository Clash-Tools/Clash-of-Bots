"""Clash of Clans API sync (D-035): request, errors without the key, parsing, unit matching, cache, UI."""

import io
import json
import logging
import os
import urllib.error

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cob.core import coc_api, ui_settings  # noqa: E402
from cob.core.coc_api import CocApiError, Owned, fetch_player, load_cached, parse_player, sync  # noqa: E402
from cob.units import UnitDB  # noqa: E402

TOKEN = "eyJ0eXAiOiJKV1Qi.eyJpc3MiOiJzdXBlcmNlbGwi.c2lnbmF0dXJlLWZha2U"  # shaped like a key, not one
PLAYER = {  # the API's shape, made-up values
    "tag": "#2PQ8Y0L", "name": "Chief", "townHallLevel": 16, "townHallWeaponLevel": 0, "expLevel": 220,
    "trophies": 4321, "builderHallLevel": 10, "clan": {"tag": "#PQ2Y", "name": "Some Clan"},
    "troops": [
        {"name": "Barbarian", "level": 11, "maxLevel": 12, "village": "home"},
        {"name": "Super Valkyrie", "level": 10, "maxLevel": 11, "village": "home",
         "superTroopIsActive": True},
        {"name": "L.A.S.S.I", "level": 10, "maxLevel": 15, "village": "home"},
        {"name": "Log Launcher", "level": 4, "maxLevel": 5, "village": "home"},
        {"name": "Raged Barbarian", "level": 20, "maxLevel": 20, "village": "builderBase"},
        {"name": "Brand New Troop", "level": 1, "maxLevel": 3, "village": "home"},
        "junk",
    ],
    "spells": [{"name": "Earthquake Spell", "level": 5, "maxLevel": 5, "village": "home"},
               {"name": "Totem Spell", "level": 1, "maxLevel": 3, "village": "home"}],
    "heroes": [{"name": "Barbarian King", "level": 90, "maxLevel": 100, "village": "home"},
               {"name": "Battle Machine", "level": 30, "maxLevel": 35, "village": "builderBase"}],
    "heroEquipment": [{"name": "Giant Gauntlet", "level": 18, "maxLevel": 27, "village": "home"}],
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def opener_returning(payload, seen=None):
    def opener(req, timeout):
        if seen is not None:
            seen.append(req)
        return FakeResponse(json.dumps(payload).encode())
    return opener


def opener_raising(exc):
    def opener(req, timeout):
        raise exc
    return opener


@pytest.fixture(scope="module")
def db():
    return UnitDB()


def test_request_carries_only_the_tag_and_the_key():
    seen = []
    assert fetch_player("2pq8y0l", TOKEN, opener=opener_returning(PLAYER, seen))["name"] == "Chief"
    req = seen[0]
    assert req.full_url == "https://api.clashofclans.com/v1/players/%232PQ8Y0L"
    assert req.get_header("Authorization") == f"Bearer {TOKEN}" and req.get_method() == "GET"
    assert req.data is None
    fetch_player("#2PQ8Y0L", TOKEN, base="https://proxy.example.org/v1/",
                 opener=opener_returning(PLAYER, seen))
    assert seen[1].full_url == "https://proxy.example.org/v1/players/%232PQ8Y0L"


@pytest.mark.parametrize("tag,token,base,why", [
    ("", TOKEN, "", "player tag"),
    ("#ABC", TOKEN, "", "player tag"),
    ("#2PQ", "", "", "API key"),
    ("#2PQ", "not-a-key", "", "API key"),
    ("#2PQ", TOKEN, "http://plain.example.org", "https://"),
])
def test_bad_input_never_reaches_the_network(tag, token, base, why):
    with pytest.raises(CocApiError, match=why):
        fetch_player(tag, token, base, opener=opener_raising(AssertionError("network used")))


@pytest.mark.parametrize("exc,why", [
    (urllib.error.HTTPError("u", 403, "Forbidden", {}, None), "public IP"),
    (urllib.error.HTTPError("u", 404, "Not Found", {}, None), "no player"),
    (urllib.error.HTTPError("u", 503, "x", {}, None), "maintenance"),
    (urllib.error.HTTPError("u", 418, "x", {}, None), "HTTP 418"),
    (urllib.error.URLError(OSError("down")), "not reachable"),
    (TimeoutError(), "not reachable"),
])
def test_errors_are_readable_and_never_show_the_key(exc, why, caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(CocApiError, match=why) as info:
        fetch_player("#2PQ", TOKEN, opener=opener_raising(exc))
    assert TOKEN not in str(info.value) and TOKEN not in caplog.text
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_player_units_match_the_unit_database(db):
    p = parse_player(PLAYER, db, 1.0)
    assert (p.tag, p.name, p.town_hall, p.builder_hall, p.trophies, p.clan) == (
        "#2PQ8Y0L", "Chief", 16, 10, 4321, "Some Clan")
    home = p.owned("home")
    assert home["barbarian"].level == 11 and not home["barbarian"].maxed
    assert db.get(home["earthquake_spell"].unit_id).kind == "spell"  # not the event spell of that name
    assert {"super_valkyrie", "lassi", "log_launcher", "totem_spell", "barbarian_king"} <= set(home)
    builder = p.owned("builder")
    assert db.get(builder[next(iter(builder))].unit_id).village == "builder" and len(builder) == 2
    assert p.unmatched() == ["Brand New Troop"]
    assert [e.name for e in p.equipment()] == ["Giant Gauntlet"] and p.equipment()[0].unit_id is None
    assert [h.name for h in p.heroes()] == ["Barbarian King"]
    with pytest.raises(CocApiError):
        parse_player({"reason": "notFound"})


def test_every_pet_and_hero_name_in_the_database_matches(db):
    """API names are the game's own names: each home hero / pet / siege maps to itself."""
    index = coc_api.name_index(db)
    for u in db.units.values():
        if u.kind in ("hero", "pet", "siege", "spell", "troop", "super_troop"):
            assert db.get(index[(coc_api._key(u.name), u.village)]).name == u.name


def test_sync_caches_per_profile_and_reloads(tmp_path, db, caplog):
    caplog.set_level(logging.DEBUG)
    cache = tmp_path / "profiles" / "alt" / "player.json"
    p = sync("#2PQ8Y0L", TOKEN, cache, db=db, opener=opener_returning(PLAYER), clock=lambda: 1234.0)
    assert p.fetched_at == 1234.0 and cache.is_file() and TOKEN not in cache.read_text()
    assert TOKEN not in caplog.text
    again = load_cached(cache, db)
    assert again == p
    cache.write_text("{broken")
    assert load_cached(cache, db) is None and load_cached(tmp_path / "none.json") is None


def test_api_key_and_address_are_validated_in_settings(tmp_path):
    path = tmp_path / "ui.json"
    path.write_text(json.dumps({"coc_api_token": TOKEN, "coc_api_base": "https://proxy.example.org/v1"}))
    s = ui_settings.load(path)
    assert s.coc_api_token == TOKEN and s.coc_api_base == "https://proxy.example.org/v1"
    path.write_text(json.dumps({"coc_api_token": "abc", "coc_api_base": "ftp://x"}))
    s = ui_settings.load(path)
    assert s.coc_api_token == "" and s.coc_api_base == ""


# --- UI -----------------------------------------------------------------------------------------


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_cards_page_lists_own_units_first(qapp, tmp_path, db):
    from cob.attack.cards import CardLibrary
    from cob.ui.pages.cards import CardsPage

    owned = {"golem": Owned("Golem", 12, 13, "home", "troops", "golem")}
    page = CardsPage(CardLibrary(folder=tmp_path), db, owned=lambda: owned)
    page._fill_units(("troop", "super_troop", "event_troop"))
    assert page.unit.itemData(0) == "golem" and "yours, level 12" in page.unit.itemText(0)
    broken = CardsPage(CardLibrary(folder=tmp_path), db, owned=lambda: 1 / 0)
    broken._fill_units(())
    assert broken.unit.count() == len(db.choices("home"))


def test_window_syncs_the_selected_profile(qapp, monkeypatch, db):
    from dataclasses import replace

    from cob.core.profiles import Profile, Profiles
    from cob.ui.main_window import MainWindow

    store = Profiles()
    store.update(Profile("default", "Default", "", "#2PQ8Y0L"))
    win = MainWindow(devices=lambda: [], profiles=store)
    win.profiles_page.request_sync()
    assert "API key in Settings" in win.profiles_page.player.text()

    win.ui_settings = replace(win.ui_settings, coc_api_token=TOKEN)
    calls = []

    def fake_sync(tag, token, cache, base, units_db):
        calls.append((tag, token, cache))
        return sync(tag, token, cache, base, units_db, opener=opener_returning(PLAYER), clock=lambda: 1.0)

    monkeypatch.setattr(coc_api, "sync", fake_sync)
    win.profiles_page.request_sync()
    for job in list(win._jobs):
        job.wait(5_000)
    qapp.processEvents()
    assert calls[0][:2] == ("#2PQ8Y0L", TOKEN) and calls[0][2] == store.player_path("default")
    text = win.profiles_page.player.text()
    assert "Chief #2PQ8Y0L" in text and "Town Hall 16" in text and "Barbarian King 90" in text
    assert win._owned_units()["barbarian"].level == 11

    def failing(*_a):
        raise CocApiError("Clash of Clans API: x")

    monkeypatch.setattr(coc_api, "sync", failing)
    win.profiles_page.request_sync()
    for job in list(win._jobs):
        job.wait(5_000)
    qapp.processEvents()
    assert win.profiles_page.player.text() == "Clash of Clans API: x"
