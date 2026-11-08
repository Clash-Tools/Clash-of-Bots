"""Clan castle request: anchors on real frames and the cancel-only towards-home path (fast)."""

import cv2
import pytest

from cob.core.config import FarmConfig
from cob.screens.classifier import ScreenClassifier
from cob.vision.frame import Frame
from cob.vision.match import match
from cob.vision.templates import TemplateStore
from tests.fakes import FRAMES


@pytest.fixture(scope="module")
def store():
    return TemplateStore()


def _f(name):
    return Frame(cv2.imread(str(FRAMES / f"{name}.jpg")))


def test_off_by_default():
    assert FarmConfig().request_minutes == 0


def test_castle_panel_and_dialog_anchors(store):
    panel = _f("cc_selected")
    assert match(panel, store.get("cc_panel_title")) and match(panel, store.get("cc_request_button"))
    dialog = _f("request_dialog")
    send, cancel = match(dialog, store.get("request_send")), match(dialog, store.get("request_cancel"))
    assert send and cancel and send.center[0] > cancel.center[0]


def test_dialog_screen_goes_home_by_cancel_never_send(store):
    clf = ScreenClassifier(store)
    assert clf.classify(_f("request_dialog")).screen == "REQUEST_DIALOG"
    assert {d.name: d.to_home for d in clf.defs}["REQUEST_DIALOG"] == "tap request_cancel"


def test_gem_request_now_button_is_never_matched(store):
    # After a request the castle offers "Request Now!" for gems: it must not look like the Request button.
    assert match(_f("cc_request_now_gems"), store.get("cc_request_button")) is None
