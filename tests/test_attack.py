"""Attack v1: border geometry, troop bar reading and the attack task flow."""

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest

from cob.attack.geometry import DeployConfig, Diamond, deploy_points, find_base, load_attack_config
from cob.attack.troops import SINGLE, SPELL, TROOP, is_used, read_bar
from cob.core.human import Humanizer
from cob.screens.classifier import ScreenClassifier
from cob.screens.navigator import NavConfig, Navigator
from cob.tasks.attack import DONE, FAILED, AttackConfig, AttackTask
from cob.vision.templates import TemplateStore
from tests.fakes import FRAMES, FakeClock, FakeDevice

EXACT = Humanizer(enabled=False)  # exact centres; jitter has its own tests

BAR = Path(__file__).parent / "fixtures" / "bar"
ARMY = [TROOP, TROOP, SINGLE, SINGLE, SINGLE, SINGLE, SINGLE, SPELL, SPELL]  # golems, wall breakers,
# siege, 4 heroes, 2 spells (the test account's saved army)


@pytest.fixture(scope="module")
def cfg():
    return load_attack_config(TemplateStore().root)


def _bar_frame(name: str) -> np.ndarray:
    """Bar strips are stored as lossless PNG (JPEG blurs the level badges); paste into a frame."""
    frame = np.zeros((900, 1600, 3), np.uint8)
    frame[730:900] = cv2.imread(str(BAR / f"{name}.png"))
    return frame


# --- geometry -------------------------------------------------------------------------------


def test_synthetic_diamond_recovered(cfg):
    border, deploy = cfg[:2]
    frame = np.full((900, 1600, 3), (40, 120, 60), np.uint8)  # grass
    corners = np.array([[800, 100], [1350, 500], [800, 900], [250, 500]])  # slope 400/550 = 0.727
    cv2.polylines(frame, [corners], True, (13, 75, 180), 2)  # border colour from live frames (BGR)
    d = find_base(frame, border)
    assert d is not None
    got = d.corners
    for name, (x, y) in (("top", (800, 100)), ("right", (1350, 500)), ("left", (250, 500))):
        assert abs(got[name][0] - x) <= 12 and abs(got[name][1] - y) <= 12, (name, got[name])


def test_deploy_points_lie_outside_the_edge():
    d = Diamond(u_min=400 + 0.73 * 800 - 400, u_max=1500, v_min=-400, v_max=900, k=0.73)
    dep = DeployConfig("top_left", margin=25, t_from=0.1, t_to=0.9, points=8, min_y=0)
    edge, pts = deploy_points(d, dep, ())
    assert edge == "top_left" and len(pts) >= 5  # points off screen are dropped
    for x, y in pts:  # outside the top-left edge means u = y + kx below the border's u_min
        assert y + 0.73 * x < d.u_min - 20


def test_auto_edge_skips_ui_and_offscreen(cfg):
    border, deploy = cfg[:2]
    d = Diamond(u_min=300, u_max=1500, v_min=-700, v_max=200, k=0.73)  # base pushed up and right
    edge, pts = deploy_points(d, deploy, border.ui)
    assert pts and all(not (0 <= y - 730 and y < 900) for _, y in pts)  # never on the troop bar
    assert edge != "top_left" or len(pts) >= 3


@pytest.mark.parametrize("name, left, right", [
    ("search_a", (122, 378), (1516, 414)),
    ("search_b", (150, 383), (1393, 472)),
    ("search_d", (118, 429), (1471, 423)),
    ("search_e", (166, 453), (1293, 443)),
])
def test_border_on_real_bases(cfg, name, left, right):
    border, deploy = cfg[:2]
    d = find_base(cv2.imread(str(FRAMES / f"{name}.jpg")), border)
    assert d is not None
    for corner, (x, y) in (("left", left), ("right", right)):
        gx, gy = d.corners[corner]
        assert abs(gx - x) <= 15 and abs(gy - y) <= 15, (corner, (gx, gy))
    edge, pts = deploy_points(d, deploy, border.ui)
    assert len(pts) >= 6


def test_painted_scenery_outline_is_not_trusted(cfg):
    # Red/orange painted ground passes the colour filter; the fit balloons and must be rejected.
    assert find_base(cv2.imread(str(FRAMES / "search_painted_scenery.jpg")), cfg[0]) is None


@pytest.mark.parametrize("name", ["search_big_base", "search_big_base_b"])
def test_bases_that_fill_the_map_are_found(cfg, name):
    # #164 live (2026-11-04/05): bases whose red no-deploy line runs near the map edge fitted larger than
    # the 1500 x 1150 limit and every attack on them failed. A clean thin red line may now be that big,
    # and deploy points land outside the real line.
    from dataclasses import replace

    from cob.attack.geometry import border_mask, deploy_points

    frame = cv2.imread(str(FRAMES / f"{name}.png"))  # lossless: JPEG wipes out the 1-2 px line
    border, deploy = cfg[0], cfg[1]
    base = find_base(frame, border)
    assert base is not None
    c = base.corners
    assert c["right"][0] - c["left"][0] > 1450  # well past a normal base (1130-1400 px)
    red = border_mask(frame, border)
    _, points = deploy_points(base, replace(deploy, edge="auto"), border.ui, red=red)
    assert len(points) >= 6
    for x, y in points:
        assert 0 <= x < 1600 and 0 <= y < 900 and not red[max(0, y - 6):y + 7, max(0, x - 6):x + 7].any()


def test_full_map_base_has_deploy_room_outside_the_line(cfg):
    # Live 2026-11-05 (phone): a base filling the map, battle already started. The fit must find it and
    # put deploy points on the grass strip outside the red line, on both upper edges.
    from dataclasses import replace

    from cob.attack.geometry import border_mask, deploy_points

    frame = cv2.imread(str(FRAMES / "battle_full_map_base.png"))
    border, deploy = cfg[0], cfg[1]
    base = find_base(frame, border)
    assert base is not None
    red = border_mask(frame, border)
    for edge in ("top_left", "top_right"):
        _, points = deploy_points(base, replace(deploy, edge=edge), border.ui, red=red)
        assert len(points) >= 6
        for x, y in points:
            assert not red[max(0, y - 6):y + 7, max(0, x - 6):x + 7].any()


@pytest.mark.parametrize("name", ["search_tent_scenery", "search_party_scenery", "search_band_scenery"])
def test_red_scenery_bases_are_fitted_on_the_line_alone(cfg, name):
    # #178 live (2026-11-06): striped tents, a party scenery with pink stripes and an orange carpet under
    # the red line all passed the colour filter, the outline came out 1770-1854 px wide and the base was
    # skipped. The outline now comes from the thin line alone and deploy points stay clear of it.
    from dataclasses import replace

    from cob.attack.geometry import deploy_points, red_mask

    frame = cv2.imread(str(FRAMES / f"{name}.png"))
    border, deploy = cfg[0], cfg[1]
    base = find_base(frame, border)
    assert base is not None and base.line_only
    c = base.corners
    assert 1200 < c["right"][0] - c["left"][0] < 1450 and 880 < c["bottom"][1] - c["top"][1] < 1060
    red = red_mask(frame, border, base)
    _, points = deploy_points(base, replace(deploy, edge="auto"), border.ui, red=red)
    assert len(points) >= 6
    for x, y in points:
        assert not red[max(0, y - 6):y + 7, max(0, x - 6):x + 7].any()


def test_painted_scenery_jpeg_is_still_not_trusted(cfg):
    # Too little of the line survives JPEG for the line fit: the base is still skipped.
    assert find_base(cv2.imread(str(FRAMES / "search_painted_scenery.jpg")), cfg[0]) is None


def test_no_border_on_plain_grass(cfg):
    # Only called on confirmed search/battle screens; other screens can contain red UI.
    border = cfg[0]
    assert find_base(np.full((900, 1600, 3), (40, 120, 60), np.uint8), border) is None


# --- troop bar ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["green", "dark_scenery"])
def test_read_bar_kinds(cfg, name):
    cards = read_bar(_bar_frame(name), cfg[2])
    assert [c.kind for c in cards] == ARMY
    assert not any(c.used for c in cards)
    xs = [c.x0 for c in cards]
    assert xs == sorted(xs) and all(b - a >= 100 for a, b in zip(xs, xs[1:], strict=False))


def test_upgrade_arrows_and_x1_counts_do_not_hide_cards(cfg):
    # live 2026-10-21: the old badge reader lost the wizard (x1), the siege and the queen (arrows)
    cards = read_bar(_bar_frame("home_upgrade_arrows"), cfg[2])
    assert [c.kind for c in cards] == [TROOP, TROOP] + [SINGLE] * 5 + [SPELL] * 2


def test_super_troop_red_card_is_a_troop_not_a_spell(cfg):
    # Live 2026-11-07: a Super Valkyrie x17 (red card, hue ~179) read as a spell and was never deployed.
    cards = read_bar(_bar_frame("super_valkyrie_spell"), cfg[2])
    assert [c.kind for c in cards] == [TROOP, SPELL]


def test_used_cards_mid_battle(cfg):
    cards = read_bar(_bar_frame("green"), cfg[2])
    later = _bar_frame("battle_used")
    assert [is_used(later, c, cfg[2]) for c in cards] == [k != SPELL for k in ARMY]


# --- task -----------------------------------------------------------------------------------


class BattleDevice:
    """Search screen with a full bar until enough taps, then battle end, then home. A field tap
    after a card tap greys that card out (`refuse` = field taps that place nothing)."""

    serial = "fake"

    def __init__(self, taps_to_end: int, bar: str = "green", end: str = "battle_end"):
        self.search = cv2.imread(str(FRAMES / "search_a.jpg"))
        self.search[730:900] = cv2.imread(str(BAR / f"{bar}.png"))
        self.used = self.search.copy()
        self.used[730:900] = cv2.imread(str(BAR / "battle_used.png"))
        self.end = cv2.imread(str(FRAMES / f"{end}.jpg"))
        self.home = cv2.imread(str(FRAMES / "home.jpg"))
        self.taps: list[tuple[int, int]] = []
        self.taps_to_end = taps_to_end
        self.returned = False
        self.selected: int | None = None
        self.refuse = 0
        self.frame = self.search.copy()

    def capture(self):
        if self.returned:
            return self.home
        if len(self.taps) >= self.taps_to_end:
            self.late = getattr(self, "late", 0) + 1
            if self.late > 1:  # the frame right after the last tap still shows the battle
                return self.end
        return self.frame.copy()

    def tap(self, x, y):
        if len(self.taps) >= self.taps_to_end and 700 < x < 900 and 740 < y < 810:
            self.returned = True  # Return Home
        if len(self.taps) >= self.taps_to_end and 400 < x < 600 and 510 < y < 545:
            self.returned = True  # TRY AGAIN / RELOAD GAME reloads into the village
        self.taps.append((x, y))
        if y > 730:
            self.selected = x
        elif self.selected is not None:
            if self.refuse > 0:
                self.refuse -= 1
            else:  # placed: grey out the selected card (cards are ~110 px wide)
                a, b = self.selected - 60, self.selected + 60
                grey = cv2.cvtColor(self.used[730:900, a:b], cv2.COLOR_BGR2GRAY)
                self.frame[730:900, a:b] = cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)

    def key(self, keycode):
        pass

    def foreground_package(self):
        return "com.supercell.clashofclans"


def _attack(cfg, dev, nav_cfg=None):
    clock = FakeClock()
    nav = Navigator(dev, ScreenClassifier(TemplateStore()), nav_cfg or NavConfig(), clock=clock,
                    sleep=clock.sleep, human=EXACT)
    return AttackTask(nav, *cfg, AttackConfig()), clock


def test_attack_deploys_troops_then_singles_and_returns_home(cfg):
    dev = BattleDevice(taps_to_end=33)  # + 2 spell cards: a card tap and one cast each
    task, clock = _attack(cfg, dev)
    out = task.run()
    assert out.status == DONE and dev.returned
    assert out.deployed == {TROOP: 2, SINGLE: 5, SPELL: 2}
    bar_y = [y for _, y in dev.taps[:-1] if y > 730]  # last tap is Return Home on the end screen
    assert bar_y and all(y == 795 for y in bar_y)  # bar taps on the card face, above the upgrade arrow
    field_taps = [(x, y) for x, y in dev.taps[:-1] if y < 730]
    assert field_taps and all(not (x < 330 and y < 250) for x, y in field_taps)  # never on the UI
    spell_x = [c.center[0] for c in read_bar(_bar_frame("green"), cfg[2]) if c.kind == SPELL]
    after = [i for i, (x, y) in enumerate(dev.taps) if y == 795 and abs(x - spell_x[0]) < 30][0]
    cast = dev.taps[after + 1]
    assert cast[1] < 730 and cast not in task._points  # inside the edge, not on a deploy point


def test_spells_can_be_left_out(cfg):
    dev = BattleDevice(taps_to_end=40)
    task, _ = _attack(cfg, dev)
    task.cfg = AttackConfig(cast_spells=False)
    out = task.run()
    assert out.deployed[SPELL] == 0
    spell_x = [c.center[0] for c in read_bar(_bar_frame("green"), cfg[2]) if c.kind == SPELL]
    assert not any(abs(x - sx) < 30 for x, y in dev.taps if y == 795 for sx in spell_x)




def test_refused_deploy_tap_is_retried_at_another_point(cfg):
    dev = BattleDevice(taps_to_end=10**9)
    task, _ = _attack(cfg, dev)
    cards = read_bar(dev.capture(), cfg[2])
    hero = [c for c in cards if c.kind == SINGLE][0]
    from cob.tasks.deploy import place_unit

    dev.refuse = 2  # the first two spots are inside the red line
    points = [(300 + 40 * i, 300) for i in range(8)]
    assert place_unit(task.nav, hero, points)
    field = [t for t in dev.taps if t[1] < 730]
    assert len(field) == 3 and len(set(field)) == 3  # three different spots
    dev.refuse = 99
    assert not place_unit(task.nav, [c for c in cards if c.kind == SINGLE][1], points)


def test_next_unit_goes_straight_to_the_point_that_worked(cfg):
    # #166 live: one hero tried 7 refused points (~4 s each) and the next hero tried the same 7 again.
    from cob.tasks.deploy import PointMemory, place_unit

    dev = BattleDevice(taps_to_end=10**9)
    task, _ = _attack(cfg, dev)
    singles = [c for c in read_bar(dev.capture(), cfg[2]) if c.kind == SINGLE]
    points = [(300 + 40 * i, 300) for i in range(8)]
    memory = PointMemory()
    dev.refuse = 2
    assert place_unit(task.nav, singles[0], points, memory=memory)
    worked = [t for t in dev.taps if t[1] < 730][-1]
    assert memory.good == [worked] and len(memory.bad) == 2
    dev.taps.clear()
    assert place_unit(task.nav, singles[1], points, memory=memory)
    assert [t for t in dev.taps if t[1] < 730] == [worked]  # no refused point tried again


class CountDevice(BattleDevice):
    """Phone dragons (#92): each field tap places one; only the count changes until the last one
    greys the card out. Count rows from real strips (x15 -> x3), and only those above y 760: the
    whole-card check scored a live 6-dragon round under its 3.0 threshold."""

    def __init__(self, troops: int):
        super().__init__(taps_to_end=10**9)
        self.frame[730:900] = cv2.imread(str(BAR / "dragons_x15.png"))
        self.fewer = self.frame.copy()
        self.fewer[742:760] = cv2.imread(str(BAR / "dragons_x3.png"))[12:30]
        self.full = self.frame.copy()
        self.troops = self.start = troops

    def tap(self, x, y):
        self.taps.append((x, y))
        if y > 730 or self.troops == 0:
            return
        self.troops -= 1
        # the count shown changes with every placement: alternate the two real strips per 6-tap round
        self.frame = (self.fewer if (self.troops // 6) % 2 != (self.start // 6) % 2 else self.full).copy()
        if self.troops == 0:  # last one placed: the card greys out
            grey = cv2.cvtColor(self.frame[745:885, 110:230], cv2.COLOR_BGR2GRAY)
            self.frame[745:885, 110:230] = cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)


def test_troops_are_placed_until_the_card_greys_out(cfg):
    # #92 live: 15 dragons, the count change was missed, so each 6-tap round looked refused and 3 stayed.
    dev = CountDevice(troops=15)
    task, _ = _attack(cfg, dev)
    card = next(c for c in read_bar(dev.capture(), cfg[2]) if c.kind == TROOP)
    taps, ok = task._deploy_troop(card, [(300 + 40 * i, 300) for i in range(8)])
    assert ok and dev.troops == 0 and taps == 18  # three rounds of 6


def test_a_large_stack_is_placed_in_full(cfg):
    # #98: the old fixed 80-tap cap left 150 barbarians short; rounds now go on while the count changes.
    dev = CountDevice(troops=150)
    task, _ = _attack(cfg, dev)
    card = next(c for c in read_bar(dev.capture(), cfg[2]) if c.kind == TROOP)
    taps, ok = task._deploy_troop(card, [(300 + 40 * i, 300) for i in range(8)])
    assert ok and dev.troops == 0 and taps == 150


def test_a_round_that_places_nothing_stops_the_card(cfg):
    # Points refused part-way (the red line moved): no endless tapping, the caller tries further out.
    dev = CountDevice(troops=40)
    task, _ = _attack(cfg, dev)
    card = next(c for c in read_bar(dev.capture(), cfg[2]) if c.kind == TROOP)
    real_tap = dev.tap
    dev.tap = lambda x, y: real_tap(x, y) if len(dev.taps) < 13 else dev.taps.append((x, y))  # refused
    taps, ok = task._deploy_troop(card, [(300 + 40 * i, 300) for i in range(8)])
    assert not ok and taps <= 24 and dev.troops > 0


def test_troop_tap_limit_does_not_claim_complete(cfg):
    dev = CountDevice(troops=100)
    task, _ = _attack(cfg, dev)
    task.cfg = AttackConfig(max_taps_per_troop=7, check_every=6)
    card = next(c for c in read_bar(dev.capture(), cfg[2]) if c.kind == TROOP)
    taps, ok = task._deploy_troop(card, [(300 + 40 * i, 300) for i in range(8)])
    assert not ok and taps == 7 and dev.troops == 93


def test_attack_fails_safely_without_bar(cfg):
    dev = BattleDevice(taps_to_end=999)
    dev.frame[730:900] = 0  # no troop bar
    task, _ = _attack(cfg, dev, NavConfig(timeout_s=20, poll_s=5))  # the fake never leaves the search
    out = task.run()
    assert out.status == FAILED and "bar" in out.reason
    assert all(y < 730 or y > 900 for _, y in dev.taps) or not dev.taps


def test_connection_lost_mid_battle_fails_fast(cfg):
    dev = BattleDevice(taps_to_end=29, end="home_dimmed_reload")  # Connection lost / TRY AGAIN
    task, clock = _attack(cfg, dev)
    out = task.run()
    assert out.status == FAILED and out.reason == "battle interrupted (POPUP_RELOAD)"
    assert clock.t < 60  # did not sit out the 240 s battle timeout


def test_village_after_the_battle_ends_the_watch(cfg):
    # #135 live: after a 3-star win the results screen went unseen and the village came up; that is
    # the end of the battle, not a 240 s timeout.
    dev = BattleDevice(taps_to_end=29, end="home")
    task, clock = _attack(cfg, dev)
    out = task.run()
    assert out.status == DONE and out.ended_by == "home"
    assert clock.t < 60


def test_return_home_lower_on_the_screen_still_ends_the_battle(cfg):
    dev = BattleDevice(taps_to_end=29)
    dev.end = np.roll(dev.end, 50, axis=0)  # a results layout with the button further down
    task, _ = _attack(cfg, dev)
    assert task.nav.classify()[0].screen != "BATTLE_END"  # still the search screen
    dev.taps = [(0, 0)] * 29
    dev.late = 1  # past the frame that still shows the battle
    assert task.nav.classify()[0].screen == "BATTLE_END"


def test_stopping_mid_battle_is_not_reported_as_a_stuck_battle(cfg):
    # The 12:00 "battle did not end" on 10-29 was the Stop button.
    dev = WatchDevice(pcts=[2, 5], end_after=1000)
    task, _ = _attack(cfg, dev)
    watch = task._watch_battle

    def stopped_watch(out):
        task.nav.stop.set()
        return watch(out)

    task._watch_battle = stopped_watch
    out = task.run()
    assert out.status == FAILED and out.reason == "stopped"


DAMAGE_PANEL = (slice(590, 710), slice(1320, 1600))  # crops in fixtures/bar/damage_<pct>.png


def _damage_panel(pct) -> np.ndarray:
    """Real Overall Damage panels (2 and 5 % with the bar, 62 and 94 % with stars); None = unreadable."""
    if pct is None:  # label kept (it marks the BATTLE screen), number blanked
        panel = cv2.imread(str(BAR / "damage_5.png"))
        panel[55:, 100:] = 40
        return panel
    return cv2.imread(str(BAR / f"damage_{pct}.png"))


class WatchDevice(BattleDevice):
    """After deployment: battle frame whose damage % follows `pcts` (one value per capture, last
    repeats); Surrender / End Battle -> confirm dialog -> Okay -> battle end -> Return Home -> home.
    `starred`: the frame after the first star (End Battle button, no damage bar)."""

    def __init__(self, pcts, end_after=None, starred=False):
        super().__init__(taps_to_end=10**9)
        self.battle = cv2.imread(str(FRAMES / ("battle_starred.jpg" if starred else "battle.jpg")))
        self.confirm = cv2.imread(str(FRAMES / "surrender_confirm.jpg"))
        self.pcts = list(pcts)
        self.end_after = end_after  # captures in battle before it ends by itself
        self.phase = "deploy"
        self.battle_captures = 0
        self.surrendered = False

    def capture(self):
        if self.returned:
            return self.home
        if self.phase == "deploy":
            return super().capture()
        if self.phase in ("confirm",):
            return self.confirm
        if self.phase == "end":
            return self.end
        self.battle_captures += 1
        if self.end_after is not None and self.battle_captures > self.end_after:
            self.phase = "end"
            return self.end
        frame = self.battle.copy()
        frame[DAMAGE_PANEL] = _damage_panel(self.pcts[min(self.battle_captures - 1, len(self.pcts) - 1)])
        return frame

    def tap(self, x, y):
        super().tap(x, y)  # cards grey out as they are placed
        if self.phase == "deploy" and len(self.taps) >= 29:  # army deployed, abilities fired
            self.phase = "battle"
        elif self.phase == "battle" and x < 220 and 630 < y < 710:
            self.phase = "confirm"
        elif self.phase == "confirm" and 880 < x < 1060 and 530 < y < 630:
            self.phase, self.surrendered = "end", True
        elif self.phase == "end" and 700 < x < 900 and 740 < y < 810:
            self.returned = True


@pytest.mark.parametrize("pct", [2, 5, 62, 94])
def test_damage_percent_is_read_with_and_without_the_bar(cfg, pct):
    from cob.attack.damage import damage_reader, read_damage
    from cob.vision.frame import Frame

    frame = np.zeros((900, 1600, 3), np.uint8)
    frame[DAMAGE_PANEL] = _damage_panel(pct)
    assert read_damage(damage_reader(TemplateStore(), cfg[3]), Frame(frame), cfg[3]) == pct


def test_stalled_damage_surrenders(cfg):
    dev = WatchDevice(pcts=[2, 5])  # stops growing at 5 %
    task, clock = _attack(cfg, dev)
    out = task.run()
    assert out.status == DONE and out.ended_by == "surrender" and dev.surrendered and dev.returned
    assert out.damage == 5


def test_stall_after_a_star_surrenders_with_end_battle(cfg):
    # #78 live: after the first star the bar is gone and the red button says End Battle.
    dev = WatchDevice(pcts=[62], starred=True)
    task, clock = _attack(cfg, dev)
    out = task.run()
    assert out.status == DONE and out.ended_by == "surrender" and dev.surrendered and dev.returned
    assert out.damage == 62


def test_growing_damage_never_surrenders(cfg):
    dev = WatchDevice(pcts=[2] * 4 + [5] * 4 + [62] * 4 + [94] * 4, end_after=16)  # rising until the end
    task, _ = _attack(cfg, dev)
    out = task.run()
    assert out.status == DONE and out.ended_by == "battle_end" and not dev.surrendered and out.damage == 94


def test_deploy_points_are_pushed_off_the_red_line():
    # The real red line bulges past the fitted diamond around one building: the point there must move
    # outward until no red pixel is near it (the game refuses taps on / inside the line).
    from cob.attack.geometry import RED_CLEARANCE, outward

    d = Diamond(u_min=400 + 0.73 * 800 - 400, u_max=1500, v_min=-400, v_max=900, k=0.73)
    dep = DeployConfig("top_left", margin=25, t_from=0.1, t_to=0.9, points=8, min_y=0)
    _, plain = deploy_points(d, dep, ())
    red = np.zeros((900, 1600), bool)
    x, y = plain[3]
    red[y - 4:y + 5, x - 4:x + 5] = True  # a red bulge right where point 3 would go
    _, checked = deploy_points(d, dep, (), red=red)
    assert len(checked) == len(plain) and checked[:3] == plain[:3]  # clear points stay put
    nx, ny = checked[3]
    assert not red[ny - RED_CLEARANCE:ny + RED_CLEARANCE + 1, nx - RED_CLEARANCE:nx + RED_CLEARANCE + 1].any()
    ox, oy = outward("top_left", 0.73)
    assert (nx - x) * ox + (ny - y) * oy > 0  # moved away from the base, not into it


def test_zero_damage_waits_for_troops_to_walk_in(cfg):
    # #78: units dropped far out deal no damage for a while; 15 s at 0 % is not a stall yet.
    dev = WatchDevice(pcts=[None] * 7 + [2] * 4 + [5] * 4 + [62] * 4 + [94] * 4, end_after=23)
    task, _ = _attack(cfg, dev)
    out = task.run()
    assert out.status == DONE and out.ended_by == "battle_end" and not dev.surrendered


def test_no_damage_at_all_surrenders_after_the_grace(cfg, tmp_path, monkeypatch):
    import cob.tasks.attack as attack_mod

    shots = []
    monkeypatch.setattr(attack_mod, "save_snapshot", lambda frame, label, **kw: shots.append(label))
    dev = WatchDevice(pcts=[None])
    task, clock = _attack(cfg, dev)
    out = task.run()
    assert out.ended_by == "surrender" and dev.surrendered and shots == ["stall_surrender_0pct"]


def _watch_attack(cfg, dev, attack_cfg):
    from cob.attack.loot import LootReader
    from cob.vision.ocr import DigitReader
    from cob.vision.regions import load_regions

    store = TemplateStore()
    loot = LootReader(DigitReader(store.load_dir("digits/loot")), load_regions(store.root)["loot"])
    clock = FakeClock()
    nav = Navigator(dev, ScreenClassifier(store), NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT)
    attack_cfg = replace(attack_cfg, cast_spells=False)  # the scripted damage frames follow the troops
    return AttackTask(nav, *cfg, attack_cfg, loot=loot)


def test_loot_that_stops_coming_in_ends_the_battle(cfg, tmp_path, monkeypatch):
    # #114: damage still creeps up, but the Available Loot rows (883,041 / 904,702 / 9,376 on the
    # fixture) no longer change: farming is over.
    import cob.tasks.attack as attack_mod

    shots = []
    monkeypatch.setattr(attack_mod, "save_snapshot", lambda frame, label, **kw: shots.append(label))
    dev = WatchDevice(pcts=[2, 2, 5, 5, 62, 62, 94, 94], end_after=30)
    out = _watch_attack(cfg, dev, AttackConfig(loot_stall_s=9)).run()
    assert out.status == DONE and out.ended_by == "surrender" and dev.surrendered
    assert out.damage < 94 and shots and shots[0].startswith("loot_stall_")


def test_loot_stall_is_off_by_default(cfg):
    dev = WatchDevice(pcts=[2] * 4 + [5] * 4 + [62] * 4 + [94] * 4, end_after=16)
    out = _watch_attack(cfg, dev, AttackConfig()).run()
    assert out.ended_by == "battle_end" and not dev.surrendered


def test_battle_ends_at_the_damage_target(cfg, monkeypatch):
    import cob.tasks.attack as attack_mod

    monkeypatch.setattr(attack_mod, "save_snapshot", lambda frame, label, **kw: None)
    dev = WatchDevice(pcts=[2, 5, 62, 94], end_after=30)
    out = _watch_attack(cfg, dev, AttackConfig(end_at_damage=60)).run()
    assert out.ended_by == "surrender" and dev.surrendered and out.damage == 62


def test_failure_report_draws_the_base_the_attack_used(cfg, monkeypatch):
    # #170: a failed attack saves the screen and the frame it worked from, with the red line, the fitted
    # outline and the deploy points drawn, so a failed base can be looked at later.
    import cob.tasks.attack as attack_mod
    from cob.tasks.attack import FAILED, AttackOutcome

    saved = {}
    monkeypatch.setattr(attack_mod, "save_snapshot",
                        lambda frame, label, **kw: saved.update(label=label, **kw))
    task, _ = _attack(cfg, FakeDevice("battle"))
    task._base_frame = cv2.imread(str(FRAMES / "battle_full_map_base.png"))
    task._points = [(200, 380), (250, 340)]
    task._report(AttackOutcome(FAILED, edge="top_left", points=2, reason="no room to deploy"))
    assert saved["label"] == "attack_failed_no room to deploy"
    assert saved["details"]["edge"] == "top_left" and saved["details"]["reason"] == "no room to deploy"
    base = saved["images"]["base"]
    assert base.shape == task._base_frame.shape and (base != task._base_frame).any()


def test_base_drawing_without_a_base(cfg):
    from cob.attack.geometry import draw_base

    grass = np.full((900, 1600, 3), (40, 120, 60), np.uint8)
    assert draw_base(grass, cfg[0], cfg[1]).shape == grass.shape


def test_two_sides_join_two_neighbouring_edges_at_their_corner():
    # #44: one path along two adjacent edges, continuous through the shared corner.
    from cob.attack.geometry import EDGES, DeployConfig, Diamond, deploy_points, deploy_sides

    base = Diamond(700, 1300, -100, 500, 0.73)
    cfg = DeployConfig("auto", 30, 0.1, 0.9, 9, 0)
    one = deploy_points(base, cfg, ())
    assert deploy_sides(base, cfg, (), 1) == one
    label, pts = deploy_sides(base, cfg, (), 2)
    first, second = label.split("+")
    assert first == one[0] and second in EDGES and second != first
    shared = set(EDGES[first][:2]) & set(EDGES[second][:2])
    assert len(shared) == 1 and len(pts) > len(one[1])
    # the two faces meet at the corner: the biggest jump between neighbours is the corner turn, not a
    # jump across the base
    gaps = [abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(pts, pts[1:], strict=False)]
    assert max(gaps) < 3 * sorted(gaps)[len(gaps) // 2]


@pytest.mark.parametrize("name", ["search_a", "search_b", "battle"])
def test_two_sides_on_real_frames_stay_clear_of_the_line(cfg, name):
    from dataclasses import replace

    from cob.attack.geometry import border_mask, deploy_points, deploy_sides

    frame = cv2.imread(str(FRAMES / f"{name}.jpg"))
    border, deploy = cfg[0], replace(cfg[1], edge="auto")
    base = find_base(frame, border)
    assert base is not None
    red = border_mask(frame, border)
    _, one = deploy_points(base, deploy, border.ui, red=red)
    label, pts = deploy_sides(base, deploy, border.ui, 2, red=red)
    assert "+" in label and len(pts) > len(one)
    for x, y in pts:
        assert 0 <= x < 1600 and 0 <= y < 900 and not red[max(0, y - 6):y + 7, max(0, x - 6):x + 7].any()


class SpellDevice(CountDevice):
    """A x5 spell card: every cast changes the count; the last one greys the card out."""

    def tap(self, x, y):
        self.taps.append((x, y))
        if y > 730 or self.troops == 0:
            return
        self.troops -= 1
        self.frame = (self.full if self.troops % 2 else self.fewer).copy()  # start is full: 4 -> fewer
        if self.troops == 0:
            grey = cv2.cvtColor(self.frame[745:885, 110:230], cv2.COLOR_BGR2GRAY)
            self.frame[745:885, 110:230] = cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)


def test_a_spell_card_is_cast_one_tap_at_a_time_until_empty(cfg):
    dev = SpellDevice(troops=5)
    task, _ = _attack(cfg, dev)
    card = next(c for c in read_bar(dev.capture(), cfg[2]) if c.kind == TROOP)
    targets = [(500 + 30 * i, 400) for i in range(6)]
    taps, ok = task._cast_spell(card, targets)
    assert ok and taps == 5 and dev.troops == 0
    field = [t for t in dev.taps if t[1] < 730]
    assert len(set(field)) == 5  # different spots


def test_a_counted_card_left_of_the_heroes_is_a_troop_whatever_its_colour():
    # The bar is troops, siege, heroes, then spells: order beats a hue that wanders into the spell band.
    from cob.attack.troops import Card, by_order

    bar = [Card(0, 110, SPELL, False), Card(120, 230, TROOP, False), Card(240, 350, SINGLE, False),
           Card(360, 470, SPELL, False)]
    assert [c.kind for c in by_order(bar)] == [TROOP, TROOP, SINGLE, SPELL]
    no_heroes = [Card(0, 110, SPELL, False), Card(120, 230, TROOP, False)]
    assert by_order(no_heroes) == no_heroes  # nothing to anchor on: colours decide


class _Frames:
    """Hands out frames in order (the last one repeats) and counts the screenshots."""

    serial = "fake"

    def __init__(self, *names):
        self.frames = [cv2.imread(str(FRAMES / f"{n}.jpg")) for n in names]
        self.captures = 0

    def capture(self):
        self.captures += 1
        return self.frames[min(self.captures - 1, len(self.frames) - 1)]


def test_a_base_outline_is_looked_for_again_when_the_line_is_not_showing(cfg):
    # live: the red line fades in and out during scouting; a frame without it must not lose the attack
    dev = _Frames("army", "army", "search_a")
    task, clock = _attack(cfg, dev)
    frame, base = task._find_base()
    assert base is not None and dev.captures == 3 and frame.bgr is dev.frames[2]
    assert task._base_frame is dev.frames[2]


def test_no_outline_after_every_look_gives_the_base_up(cfg):
    dev = _Frames("army")
    task, clock = _attack(cfg, dev)
    frame, base = task._find_base()
    assert base is None and dev.captures == task.cfg.border_looks
    task.nav.stop.set()
    dev2 = _Frames("army")
    task2, _ = _attack(cfg, dev2)
    task2.nav.stop.set()
    assert task2._find_base()[1] is None and dev2.captures == 1  # Stop ends the looking at once
