"""UI v2 foundation: bundled fonts and icons resolve, widgets build and change state (offscreen)."""

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from cob.ui.style import qss  # noqa: E402
from cob.ui.style import tokens as t  # noqa: E402
from cob.ui.style.fonts import load_fonts  # noqa: E402
from cob.ui.style.icons import icon_path, pixmap  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    qss.apply(a)
    return a


def test_fonts_registered(app):
    families = set(load_fonts())
    assert {t.FONT_BODY, t.FONT_HEADING, t.FONT_MONO} <= families


def test_icon_is_tinted_and_cached(app):
    pm = pixmap("dashboard", 20, t.PRIMARY)
    assert pm is pixmap("dashboard", 20, t.PRIMARY)  # cached
    img = pm.toImage()
    coloured = [img.pixelColor(x, y) for x in range(img.width()) for y in range(img.height())
                if img.pixelColor(x, y).alpha() == 255]
    assert coloured and all(c.name() == t.PRIMARY.lower() for c in coloured)
    with pytest.raises(KeyError):
        icon_path("no_such_icon")


def test_every_icon_named_in_ui_code_is_bundled():
    names = set()
    for py in (ROOT / "cob" / "ui").rglob("*.py"):
        text = py.read_text("utf-8")
        names |= set(re.findall(r'(?:icon|pixmap|IconLabel|icon_name=?)\(\s*"([a-z0-9_]+)"', text))
        # (key, "Title", icon) tuples such as the rail pages and pipeline steps
        names |= set(re.findall(r'\(\s*"[a-z_]+",\s*"[A-Z][^"]*",\s*"([a-z0-9_]+)"\)', text))
    missing = sorted(n for n in names if not (ROOT / "assets" / "icons" / "outlined" / f"{n}.svg").is_file())
    assert names and not missing


def test_widgets_states(app):
    from cob.ui.widgets import SegmentedControl, StatusPill, StepPipeline, Switch

    seg = SegmentedControl([("Home", "home", "home"), ("Builder", "bb", None)])
    seen = []
    seg.changed.connect(seen.append)
    assert seg.value() == "home"
    seg._group.button(1).click()
    assert seg.value() == "bb" and seen == ["bb"]

    pipe = StepPipeline()
    pipe.set_active("attack")
    assert [pipe.steps[k].state for k in pipe.order] == ["done", "done", "active", "queued", "queued"]
    pipe.set_active(None)
    assert {s.state for s in pipe.steps.values()} == {"queued"}

    pill = StatusPill("running")
    assert "RUNNING" in pill.text()
    pill.set_state("stopped", "Stopped")
    assert pill.state == "stopped" and "STOPPED" in pill.text()

    sw = Switch()
    sw.click()
    assert sw.isChecked()
    assert sw.width() == 52 and sw.height() == 32
    sw.click()
    assert not sw.isChecked()


def test_switch_stays_in_place_and_moves_its_thumb(app):
    # #105: the animation targeted QWidget's own "pos", so a toggle threw the switch to (0, 0).
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

    from cob.ui.widgets.controls import Switch

    host = QWidget()
    lay = QHBoxLayout(host)
    lay.addWidget(QLabel("A setting with a long title"))
    sw = Switch()
    lay.addWidget(sw)
    host.resize(500, 80)
    host.show()
    app.processEvents()
    where = sw.geometry()
    assert where.size().width() == 52 and where.x() > 0
    for expected in (1.0, 0.0):
        sw.click()
        loop = QEventLoop()
        QTimer.singleShot(400, loop.quit)
        loop.exec()
        assert sw.geometry() == where and sw.thumb == expected
    sw.setChecked(True)  # hidden: set at once
    host.hide()
    sw.setChecked(False)
    assert sw.thumb == 0.0


def test_dashboard_step_from_worker_thread(app):
    from PySide6.QtCore import QEventLoop, QThread, QTimer, Signal

    from cob.ui.pages.dashboard import DashboardPage

    class Worker(QThread):
        step = Signal(str)

        def run(self):
            self.step.emit("attack")

    page = DashboardPage()
    worker = Worker()
    loop = QEventLoop()
    worker.step.connect(page.set_step)
    worker.finished.connect(loop.quit)
    QTimer.singleShot(3000, loop.quit)
    worker.start()
    loop.exec()
    worker.wait()
    app.processEvents()
    assert page.pipeline.steps["attack"].state == "active"
    # The picture fills the card's spare height (a 240 px cap left an empty band, 2026-11-06), never
    # below 120 px so the page still fits small windows (#99).
    assert page.preview.minimumHeight() == 120 and page.preview.maximumHeight() > 240


def test_gallery_renders(app):
    from cob.ui.gallery import build_gallery

    w = build_gallery()
    page = w.widget()
    page.resize(1280, page.sizeHint().height())
    img = page.grab().toImage()
    assert img.width() >= 1200 and img.height() > 800
    assert img.pixelColor(5, 5).name() == t.BG.lower()


def test_themes_and_accents_rebind_the_tokens():
    # #102: dark / light / AMOLED with an accent; apply() always starts from the defaults.
    from cob.ui.style import tokens as t

    try:
        t.apply("light", "blue")
        assert (t.THEME, t.ACCENT, t.BG, t.PRIMARY, t.ON_PRIMARY) == ("light", "blue", "#F5FAF9", "#1F5FBF",
                                                                     "#FFFFFF")
        assert t.OVERLAY.startswith("rgba(0,0,0")
        t.apply("amoled", "pink")
        assert t.BG == "#000000" and t.PRIMARY == "#FFB0C8" and t.ERROR == "#FFB4AB"  # light ERROR undone
        t.apply("nope", "nope")
        assert (t.THEME, t.ACCENT, t.BG, t.PRIMARY) == ("dark", "teal", "#081425", "#80D5CB")
    finally:
        t.apply()


def test_ui_json_keeps_only_known_theme_values(tmp_path):
    import json

    from cob.core import ui_settings

    p = tmp_path / "ui.json"
    p.write_text(json.dumps({"theme": "amoled", "accent": "purple"}))
    assert (ui_settings.load(p).theme, ui_settings.load(p).accent) == ("amoled", "purple")
    p.write_text(json.dumps({"theme": "neon", "accent": 3}))
    assert (ui_settings.load(p).theme, ui_settings.load(p).accent) == ("dark", "teal")


def test_settings_page_theme_choice_and_restart(app):
    from cob.core.ui_settings import UiSettings
    from cob.ui.pages.settings import SettingsPage

    page = SettingsPage(UiSettings())
    seen, restarts = [], []
    page.changed.connect(seen.append)
    page.restart_requested.connect(lambda: restarts.append(1))
    assert not page.restart_button.isVisibleTo(page)
    page.theme._group.button(2).click()  # AMOLED
    page.accents["orange"].click()
    assert (seen[-1].theme, seen[-1].accent) == ("amoled", "orange")
    page.set_settings(seen[-1])
    assert page.restart_button.isVisibleTo(page) and "Restart" in page.theme_note.text()
    page.restart_button.click()
    assert restarts == [1]


def test_translations_fall_back_to_english(tmp_path, monkeypatch):
    # #103: tr() looks the text up in assets/i18n/<code>.json; anything missing stays English.
    import json

    from cob.core import i18n

    (tmp_path / "de.json").write_text(json.dumps({"_language": "Deutsch", "Settings": "Einstellungen",
                                                  "Stops after {n} cycles": "Stopp nach {n} Zyklen",
                                                  "Broken {n}": "Kaputt {x}"}), "utf-8")
    (tmp_path / "template.json").write_text("{}", "utf-8")
    monkeypatch.setattr(i18n, "catalog_dir", lambda: tmp_path)
    try:
        assert i18n.available() == {"en": "English", "de": "Deutsch"}
        assert i18n.set_language("de") == "de"
        assert i18n.tr("Settings") == "Einstellungen" and i18n.tr("Logs") == "Logs"
        assert i18n.tr("Stops after {n} cycles", n=5) == "Stopp nach 5 Zyklen"
        assert i18n.tr("Broken {n}", n=1) == "Broken 1"  # a broken placeholder shows the English text
        assert i18n.set_language("xx") == "en" and i18n.tr("Settings") == "Settings"
        assert i18n.set_language("../etc") == "en"
    finally:
        i18n.set_language("en")


def test_every_tr_string_is_in_the_template():
    # scripts/i18n.py extract must be re-run when tr() strings change, so translators see them.
    import importlib.util
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("i18n_script", root / "scripts" / "i18n.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    template = json.loads((root / "assets" / "i18n" / "template.json").read_text("utf-8"))
    assert set(mod.strings()) == {k for k in template if not k.startswith("_")}
