import random

from cob.core.human import Humanizer


def test_tap_stays_inside_the_middle_of_the_box():
    h = Humanizer(rng=random.Random(1))
    pts = [h.in_box(100, 200, 50, 40) for _ in range(500)]
    assert all(100 + 0.2 * 50 - 1 <= x <= 100 + 0.8 * 50 + 1 for x, _ in pts)
    assert all(200 + 0.2 * 40 - 1 <= y <= 200 + 0.8 * 40 + 1 for _, y in pts)
    assert len(set(pts)) > 100  # really varies


def test_disabled_is_exact_centre():
    assert Humanizer(enabled=False).in_box(100, 200, 50, 40) == (125, 220)
    assert Humanizer(enabled=False).near(10, 20) == (10, 20)


def test_near_is_bounded_and_seeded():
    a = [Humanizer(rng=random.Random(7)).near(500, 300) for _ in range(3)]
    assert len(set(a)) == 1  # same seed, same result
    h = Humanizer(rng=random.Random(2))
    assert all(abs(x - 500) <= 6 and abs(y - 300) <= 6 for x, y in (h.near(500, 300) for _ in range(200)))
