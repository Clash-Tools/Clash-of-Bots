"""Navigator on real fixture frames with a scripted fake device and a fake clock (no real waiting)."""

import pytest

from cob.core.human import Humanizer
from cob.screens.classifier import ScreenClassifier
from cob.screens.navigator import NavConfig, Navigator
from cob.vision.templates import TemplateStore
from tests.fakes import FakeClock, FakeDevice

EXACT = Humanizer(enabled=False)  # exact centres; jitter has its own tests


@pytest.fixture(scope="module")
def classifier():
    return ScreenClassifier(TemplateStore())


def _nav(classifier, dev, **cfg):
    clock = FakeClock()
    return Navigator(dev, classifier, NavConfig(**cfg), clock=clock, sleep=clock.sleep,
                    human=EXACT)


def test_already_home_does_nothing(classifier):
    dev = FakeDevice("home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == [] and dev.actions == []


@pytest.mark.parametrize("start, step, target", [
    ("popup_log", "POPUP_GENERIC:tap close_x close_x_log", (1476, 56)),
    ("popup_upgrade", "POPUP_GENERIC:tap close_x close_x_log", None),
    ("shop", "SHOP:tap shop_close", None),
    ("army", "ARMY:tap close_x", (1547, 83)),
    ("battle_end", "BATTLE_END:tap return_home", (802, 771)),
    ("search_a", "ATTACK_SEARCH:tap end_battle", (115, 670)),
    ("idle_reload", "POPUP_RELOAD:tap reload_button reload_game", (491, 527)),
    ("builder_menu", "BUILDER_MENU:tap builder_close", (1574, 30)),
    ("events_window", "EVENTS_WINDOW:tap events_close", (1320, 67)),
])
def test_one_tap_to_home(classifier, start, step, target):
    dev = FakeDevice(start, "home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == [step]
    assert len(dev.actions) == 1 and dev.actions[0][0] == "tap"
    if target:  # anchor centre, within a few px
        assert abs(dev.actions[0][1] - target[0]) <= 4 and abs(dev.actions[0][2] - target[1]) <= 4


def test_other_device_stops_without_input(classifier):
    dev = FakeDevice("other_device", "home")
    res = _nav(classifier, dev).go_home()
    assert not res.ok and res.stopped_on == "POPUP_OTHER_DEVICE" and dev.actions == []


def test_attack_menu_uses_back(classifier):
    dev = FakeDevice("attack_menu", "home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == ["ATTACK_MENU:back"]
    assert dev.actions == [("key", "KEYCODE_BACK", "attack_menu")]


def test_chain_reload_loading_home(classifier):
    dev = FakeDevice("idle_reload", "loading", "home")
    loading_captures = 0
    plain_capture = dev.capture

    def capture():  # after the reload tap the game loads for 4 captures, then shows home
        nonlocal loading_captures
        if dev.i == 1:
            loading_captures += 1
            if loading_captures > 4:
                dev.i = 2
        return plain_capture()

    dev.capture = capture
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == ["POPUP_RELOAD:tap reload_button reload_game"]


def test_waits_through_loading_then_home(classifier):
    dev = FakeDevice("loading", "home")
    dev.capture_calls = 0
    frames = dev.frames

    def capture():  # loading for 3 captures, then the game shows home by itself
        dev.capture_calls += 1
        return frames[0] if dev.capture_calls <= 3 else frames[1]

    dev.capture = capture
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == [] and dev.actions == []


LAUNCHER = "com.android.launcher3"


def test_another_app_in_front_opens_the_game_at_once(classifier):
    # Live 2026-11-04: the phone was on Android's Screen timeout settings; the game is opened again
    # straight away, without the 5 s wait and without closing it.
    dev = FakeDevice("launcher", "home", foreground=LAUNCHER)
    clock = FakeClock()
    res = Navigator(dev, classifier, NavConfig(), clock=clock, sleep=clock.sleep,
                    human=EXACT).go_home()
    assert res.ok and res.steps == ["UNKNOWN:open game (another app in front)"]
    assert [a[0] for a in dev.actions] == ["start"]
    assert clock.t < 10


def test_game_that_keeps_losing_the_front_is_restarted(classifier):
    dev = FakeDevice("launcher", "home", foreground=LAUNCHER)
    dev.app_start = lambda package: dev.actions.append(("start",))  # something keeps taking the front
    stop = dev.app_stop

    def app_stop(package):
        stop(package)
        dev.foreground = "com.supercell.clashofclans"
        dev._advance()

    dev.app_stop = app_stop
    clock = FakeClock()
    res = Navigator(dev, classifier, NavConfig(), clock=clock, sleep=clock.sleep,
                    human=EXACT).go_home()
    assert res.ok and res.steps == ["UNKNOWN:open game (another app in front)"] * 3 + [
        "UNKNOWN:restart (game not in front)"]


def test_unknown_never_sends_blind_input_and_restarts_once(classifier):
    dev = FakeDevice("launcher")  # game claims focus but the screen is never recognised
    clock = FakeClock()
    res = Navigator(dev, classifier, NavConfig(timeout_s=200, poll_s=5), clock=clock, sleep=clock.sleep,
                    human=EXACT).go_home()
    assert not res.ok and res.steps == ["UNKNOWN:restart"]
    assert [a[0] for a in dev.actions] == ["stop", "start"]  # no Back / taps on an unknown screen


def test_unknown_restart_waits_for_timeout_when_game_in_front(classifier):
    dev = FakeDevice("launcher", "home")
    clock = FakeClock()
    res = Navigator(dev, classifier, NavConfig(poll_s=5), clock=clock, sleep=clock.sleep,
                    human=EXACT).go_home()
    assert res.ok and res.steps == ["UNKNOWN:restart"] and clock.t >= 45


def test_transition_frame_is_not_acted_on(classifier):
    # A popup visible on one frame only (e.g. mid-fade) must not be tapped: confirm=2.
    dev = FakeDevice("popup_log", "home")
    seq = iter([dev.frames[0], dev.frames[1], dev.frames[1]])
    dev.capture = lambda: next(seq)
    res = _nav(classifier, dev).go_home()
    assert res.ok and dev.actions == []


def test_stop_event_aborts(classifier):
    dev = FakeDevice("launcher")
    nav = _nav(classifier, dev)
    nav.stop.set()
    assert not nav.go_home().ok and dev.actions == []


def test_frame_observer_sees_every_classification_and_cannot_break_navigation(classifier):
    dev = FakeDevice("popup_log", "home")
    nav = _nav(classifier, dev)
    seen = []
    nav.on_frame = lambda frame, cls: seen.append(cls.screen)
    assert nav.go_home().ok and seen[:2] == ["POPUP_GENERIC", "POPUP_GENERIC"] and seen[-1] == "HOME"

    def broken(frame, cls):
        raise RuntimeError("preview widget gone")

    nav.on_frame = broken
    assert _nav(classifier, FakeDevice("home")).go_home().ok
    assert nav.go_home().ok


BB_BOAT = "BB_HOME:tap bb_boat_icon else zoom else swipe 1000 300 800 450"


def test_builder_base_takes_the_boat_home(classifier):
    dev = FakeDevice("bb_home_boat", "home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == [BB_BOAT]
    x, y = dev.actions[0][1:3]
    assert abs(x - 1263) <= 4 and abs(y - 204) <= 4


def test_builder_base_results_then_boat(classifier):
    dev = FakeDevice("bb_results", "bb_home_boat", "home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == ["BB_RESULTS:tap bb_return_home", BB_BOAT]


def test_builder_base_drags_map_when_boat_off_screen(classifier):
    dev = FakeDevice("bb_home", "bb_home_boat", "home")  # the drag brings the dock into view
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == [BB_BOAT] * 2
    assert [a[0] for a in dev.actions] == ["swipe", "tap"]


def test_star_bonus_closed_then_boat(classifier):
    dev = FakeDevice("bb_star_bonus", "bb_home_boat", "home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == ["BB_STAR_BONUS:tap bb_bonus_okay", BB_BOAT]


def test_map_drags_are_capped(classifier):
    dev = FakeDevice("bb_home")  # boat never appears, drags change nothing
    res = _nav(classifier, dev, timeout_s=60, poll_s=5).go_home()
    assert not res.ok and sum(a[0] == "swipe" for a in dev.actions) == 6


def test_ldplayer_topup_offer_is_only_closed(classifier):
    dev = FakeDevice("ld_topup_offer", "home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == ["LDPLAYER_TOPUP:tap ld_topup_close"]
    (_, x, y, _), = dev.actions
    assert 1200 <= x <= 1235 and 150 <= y <= 185  # the X, nowhere near an offer or the Top Up button


def test_boost_offer_closed_by_x_never_gems(classifier):
    dev = FakeDevice("boost_dialog", "home")
    res = _nav(classifier, dev).go_home()
    assert res.ok and res.steps == ["BOOST_DIALOG:tap boost_close"]
    (_, x, y, _), = dev.actions
    assert x > 1120 and y < 260  # the X, far from the gem button at (805, 612)


class _PinchDevice:
    """Each pinch shows the next view; the camera stops moving once the list runs out."""

    def __init__(self, views):
        self.views, self.pinches = list(views), 0

    def capture(self):
        return self.views[min(self.pinches, len(self.views) - 1)]

    def pinch(self):
        self.pinches += 1
        return True


def test_zoom_out_pinches_until_the_view_stops_changing(classifier):
    import numpy as np

    views = [np.full((900, 1600, 3), v, np.uint8) for v in (40, 120, 200)]
    dev = _PinchDevice(views)
    assert _nav(classifier, dev).zoom_out(max_pinches=5) == 2 and dev.pinches == 3
    dev = _PinchDevice(views[:1])  # already fully out: one pinch, nothing moved
    assert _nav(classifier, dev).zoom_out() == 0 and dev.pinches == 1
    assert _nav(classifier, FakeDevice("home")).zoom_out() == 0  # no pinch support


class CrashingDevice(FakeDevice):
    """Android's "keeps stopping" dialog over a dead game for the first `crashes` starts."""

    def __init__(self, crashes: int):
        super().__init__("launcher", "home")
        self.crashes_left = crashes
        self.dialog = True

    def crashed(self, package):
        return self.dialog

    def app_start(self, package):
        self.crashes_left -= 1
        self.dialog = self.crashes_left > 0
        if self.dialog:  # died while loading again: the dialog is back, the screen stays unknown
            self.actions.append(("start",))
        else:
            super().app_start(package)


def test_a_game_crash_gets_one_restart(classifier, monkeypatch):
    import cob.screens.navigator as nav_mod

    monkeypatch.setattr(nav_mod, "save_snapshot", lambda frame, label, **kw: None)
    dev = CrashingDevice(crashes=1)
    clock = FakeClock()
    res = Navigator(dev, classifier, NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT).go_home()
    assert res.ok and res.steps == ["UNKNOWN:restart (game crashed)"]
    assert [a[0] for a in dev.actions] == ["stop", "start"]


def test_a_game_that_crashes_again_stops_the_run(classifier, monkeypatch):
    # Live 2026-11-04: `smxuhbhxh.aG: 16` on every start; reopening the game only looped.
    import cob.screens.navigator as nav_mod
    from cob.device.base import GameCrashed

    shots = []
    monkeypatch.setattr(nav_mod, "save_snapshot", lambda frame, label, **kw: shots.append(label))
    dev = CrashingDevice(crashes=5)
    clock = FakeClock()
    with pytest.raises(GameCrashed, match="keeps crashing"):
        Navigator(dev, classifier, NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT).go_home()
    assert [a[0] for a in dev.actions] == ["stop", "start"] and shots == ["game_crashed"] * 2
    assert clock.t < 30


def test_reload_other_device_taps_reload_only_on_that_popup(classifier):
    dev = FakeDevice("other_device")
    nav = Navigator(dev, classifier, NavConfig(), clock=FakeClock(), sleep=lambda s: None, human=EXACT)
    assert nav.reload_other_device()
    (tap,) = [a for a in dev.actions if a[0] == "tap"]
    assert 412 <= tap[1] <= 506 and 510 <= tap[2] <= 544  # the RELOAD button
    home = FakeDevice("home")
    nav = Navigator(home, classifier, NavConfig(), clock=FakeClock(), sleep=lambda s: None, human=EXACT)
    assert not nav.reload_other_device() and home.actions == []


def test_not_responding_dialog_counts_as_a_crash():
    # #132: Android's "isn't responding" dialog has its own window title.
    from cob.device.adb import AdbDevice

    dev = AdbDevice.__new__(AdbDevice)
    coc = "com.supercell.clashofclans"
    for title, want in [(f"Application Not Responding: {coc}", True), (f"Application Error: {coc}", True),
                        (f"{coc}/com.supercell.titan.GameApp", False)]:
        dev._shell = lambda cmd, f=f"mCurrentFocus=Window{{1 u0 {title}}}": f
        assert dev.crashed() is want


class SlowDevice(FakeDevice):
    """Each capture takes `seconds` on the fake clock (phone on Wi-Fi: up to ~5 s per frame)."""

    def __init__(self, clock, seconds, *names, **kw):
        super().__init__(*names, **kw)
        self.clock, self.seconds = clock, seconds

    def capture(self):
        self.clock.t += self.seconds
        return super().capture()


def test_slow_captures_still_confirm_the_screen(classifier):
    # Live 2026-11-05: 5 s captures fit two frames in the 10 s wait, one of them taken mid-change, so the
    # attack gave up while the battle was already showing.
    clock = FakeClock()
    dev = SlowDevice(clock, 6, "~loading", "battle", auto_after=1)
    nav = Navigator(dev, classifier, NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT)
    got = nav.wait_for({"ATTACK_SEARCH", "BATTLE"}, 10)
    assert got is not None and got[0].screen == "BATTLE"


def test_search_turning_into_battle_counts_as_one_streak(classifier):
    # The scout timer runs out between two frames: search then battle are both screens the attack takes.
    clock = FakeClock()
    dev = SlowDevice(clock, 1, "~search_a", "battle", auto_after=1)
    nav = Navigator(dev, classifier, NavConfig(), clock=clock, sleep=clock.sleep, human=EXACT)
    got = nav.wait_for({"ATTACK_SEARCH", "BATTLE"}, 10)
    assert got is not None and got[0].screen == "BATTLE" and clock.t == 2.5  # two frames, one pause


def test_a_timed_out_wait_logs_what_it_saw(classifier, caplog):
    import logging

    from cob.screens.navigator import _runs

    assert _runs(["HOME", "HOME", "UNKNOWN", "HOME"]) == "HOME x2, UNKNOWN, HOME"
    with caplog.at_level(logging.INFO, logger="cob.screens.navigator"):
        assert _nav(classifier, FakeDevice("home")).wait_for({"ARMY"}, 2) is None
    assert any("for ARMY; saw HOME x" in r.getMessage() for r in caplog.records)


def test_an_open_notification_shade_is_closed_not_the_game_restarted(classifier):
    class ShadeDevice(FakeDevice):
        def __init__(self):
            super().__init__("home", "home")
            self.frames[0] = self.frames[0] * 0  # the shade hides every anchor: an unknown screen
            self.collapsed = 0

        def foreground_package(self):
            return "NotificationShade" if not self.collapsed else "com.supercell.clashofclans"

        def collapse_shade(self):
            self.collapsed += 1
            self.i = 1  # the village shows again

    dev = ShadeDevice()
    res = _nav(classifier, dev).go_home()
    assert res.ok and "UNKNOWN:close notification shade" in res.steps and dev.collapsed == 1
    assert not any("restart" in s for s in res.steps)


def test_stuck_loading_or_unknown_marks_the_game_unavailable(classifier):
    # #118: maintenance / server outage: go_home never gets past loading (or an unknown screen).
    for frames in (("loading",), ("launcher",)):
        nav = _nav(classifier, FakeDevice(*frames), timeout_s=200, poll_s=5)
        assert not nav.go_home().ok and nav.game_unavailable() and nav.stuck_on in ("LOADING", "UNKNOWN")
    nav = _nav(classifier, FakeDevice("bb_home"), timeout_s=60, poll_s=5)  # a known screen: not "down"
    assert not nav.go_home().ok and not nav.game_unavailable()
    nav = _nav(classifier, FakeDevice("home"))
    nav.stuck_on = "LOADING"  # from an earlier trip; the next good one clears it
    assert nav.go_home().ok and not nav.game_unavailable()
