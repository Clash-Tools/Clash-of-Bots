from cob.screens.classifier import UNKNOWN, ScreenClassifier, ScreenDef
from cob.vision.templates import TemplateStore
from tests.conftest import blank_frame, make_patch, paste

DEFS = [
    ScreenDef("POPUP", 90, any=("c",)),
    ScreenDef("SEARCH", 40, all=("a", "b")),
    ScreenDef("HOME", 10, all=("a",), none=("b",)),
    ScreenDef("NEEDS_MISSING", 5, all=("ghost",)),
]


def _clf(tpl_dir):
    return ScreenClassifier(TemplateStore(tpl_dir), DEFS)


def test_missing_anchor_disables_screen(tpl_dir):
    assert [d.name for d in _clf(tpl_dir).defs] == ["POPUP", "SEARCH", "HOME"]


def test_home_vs_search_disambiguated_by_none(tpl_dir):
    clf = _clf(tpl_dir)
    home = paste(blank_frame(), make_patch(1), 100, 700)
    assert clf.classify(home).screen == "HOME"
    search = paste(home.copy(), make_patch(2), 1200, 100)
    result = clf.classify(search)
    assert result.screen == "SEARCH" and set(result.matches) == {"a", "b"}


def test_popup_wins_by_priority(tpl_dir):
    frame = paste(paste(blank_frame(), make_patch(1), 100, 700), make_patch(3), 800, 400)
    assert _clf(tpl_dir).classify(frame).screen == "POPUP"


def test_unknown(tpl_dir):
    result = _clf(tpl_dir).classify(blank_frame())
    assert result.screen == UNKNOWN and not result.known


def test_default_screens_file_parses():
    from cob.screens.classifier import load_screen_defs
    from cob.vision.templates import default_root

    defs = load_screen_defs(default_root() / "screens.toml")
    assert defs[0].name == "LOADING" and defs[-1].name == "HOME"
