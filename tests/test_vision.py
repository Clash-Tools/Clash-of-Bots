import threading

import cv2
import numpy as np
import pytest

from cob.vision.agree import read_stable
from cob.vision.color import GREEN, RED, hsv_fraction
from cob.vision.frame import Frame, clip_region
from cob.vision.match import match, match_all
from cob.vision.ocr import DigitReader
from cob.vision.templates import TemplateMissing, TemplateStore
from tests.conftest import blank_frame, make_patch, paste


def test_store_loads_metadata_and_caches(tpl_dir):
    store = TemplateStore(tpl_dir)
    a, b = store.get("a"), store.get("b")
    assert a.threshold == 0.9 and a.region is None
    assert b.region == (1000, 0, 600, 300)
    assert store.get("a") is a
    assert store.names() == ["a", "b", "c"]
    with pytest.raises(TemplateMissing):
        store.get("nope")


def test_match_finds_exact_location(tpl_dir):
    store = TemplateStore(tpl_dir)
    frame = paste(blank_frame(), make_patch(1), 700, 500)
    m = match(frame, store.get("a"))
    assert m is not None and (m.x, m.y) == (700, 500) and m.score > 0.99
    assert m.center == (730, 520)
    assert match(frame, store.get("c")) is None


def test_region_limits_search(tpl_dir):
    store = TemplateStore(tpl_dir)
    frame = paste(blank_frame(), make_patch(2), 100, 600)  # outside b's region
    assert match(frame, store.get("b")) is None
    assert match(frame, store.get("b"), region=(0, 0, 1600, 900)) is not None


def test_match_all_returns_each_copy_once(tpl_dir):
    store = TemplateStore(tpl_dir)
    frame = blank_frame()
    spots = [(100, 100), (400, 300), (1200, 700)]
    for x, y in spots:
        paste(frame, make_patch(3), x, y)
    hits = match_all(frame, store.get("c"))
    assert sorted((h.x, h.y) for h in hits) == spots


def test_region_smaller_than_template_is_no_match(tpl_dir):
    store = TemplateStore(tpl_dir)
    assert match(blank_frame(), store.get("a"), region=(0, 0, 10, 10)) is None
    assert clip_region((1590, 890, 50, 50), (1600, 900)) == (1590, 890, 10, 10)


def test_hsv_fraction():
    frame = np.zeros((100, 100, 3), np.uint8)
    frame[:, :50] = (0, 0, 255)  # BGR red
    frame[:, 50:] = (0, 255, 0)  # BGR green
    f = Frame(frame)
    assert hsv_fraction(f, (0, 0, 50, 100), RED) == pytest.approx(1.0)
    assert hsv_fraction(f, None, GREEN) == pytest.approx(0.5)


def _glyphs():
    out = {}
    for d in "0123456789":
        img = np.zeros((40, 26, 3), np.uint8)
        cv2.putText(img, d, (2, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
        out[d] = img
    return out


def test_digit_reader_reads_number_left_to_right():
    glyphs = _glyphs()
    frame = np.zeros((200, 400, 3), np.uint8)
    for i, d in enumerate("120587"):
        paste(frame, glyphs[d], 50 + i * 26, 80)
    reader = DigitReader(glyphs, threshold=0.9)
    assert reader.read(frame, (40, 70, 200, 60)) == 120587
    assert reader.read(frame, (300, 0, 100, 60)) is None


def test_read_stable_needs_agreement():
    values = iter([5, 6, 6])
    assert read_stable(lambda: None, lambda _f: next(values), need=2, interval_s=0) == 6
    noisy = iter([1, 2, 3, 4])
    assert read_stable(lambda: None, lambda _f: next(noisy), need=2, max_frames=4, interval_s=0) is None


def test_read_stable_stops_on_event():
    stop = threading.Event()
    stop.set()
    assert read_stable(lambda: None, lambda _f: 1, need=3, stop=stop, interval_s=0) is None


def test_read_stable_uses_a_frame_already_captured():
    # The search screen's confirmed frame counts as the first loot read: one capture less per base.
    captured = []
    value = read_stable(lambda: captured.append(1) or "frame", lambda _f: 7, need=2, interval_s=0,
                        first="first")
    assert value == 7 and len(captured) == 1
