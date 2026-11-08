"""Request clan castle reinforcements (free-tier "Request donations").

Posts the game's own request (the saved message in the dialog) to the player's clan chat, so it is
opt-in: farm.json `request_minutes` (0 = off). Flow: home -> "Request" label over the clan castle ->
castle panel -> Request -> "Request Reinforcements" -> Send. Nothing is typed by the bot.
No label (castle full, request pending, cooldown in game) = nothing to do.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from cob.screens.navigator import HOME, Navigator
from cob.tasks.collect import SCALES, scaled
from cob.vision.match import match

log = logging.getLogger(__name__)


@dataclass
class RequestOutcome:
    sent: bool
    reason: str = ""


class RequestTask:
    def __init__(self, nav: Navigator):
        self.nav = nav

    def _find(self, name: str):
        return match(self.nav.classify()[1], self.nav.store.get(name))

    def _find_label(self, frame):
        """The "Request" label scales with the village zoom: try a few sizes, keep the best hit."""
        tpl = self.nav.store.get("cc_request_label")
        best = None
        for scale in SCALES:
            hit = match(frame, scaled(tpl, scale), None, 0.75)
            if hit is not None and (best is None or hit.score > best.score):
                best = hit
        return best

    def run(self) -> RequestOutcome:
        out = self._run()
        log.info("request: %s%s", "sent" if out.sent else "not sent",
                 f" ({out.reason})" if out.reason else "")
        self.nav.go_home()  # closes the dialog (Cancel / X) whenever we stopped early
        return out

    def _run(self) -> RequestOutcome:
        if not self.nav.go_home().ok or self.nav.wait_for({HOME}, 10) is None:
            return RequestOutcome(False, "not home")
        label = self._find_label(self.nav.classify()[1])
        if label is None:
            return RequestOutcome(False, "no Request label (castle full or request already pending)")
        x, y = label.center
        self.nav.device.tap(x, y + 40)  # the castle under its label
        self.nav.sleep(2.0)
        if self._find("cc_panel_title") is None:
            return RequestOutcome(False, "clan castle panel did not open")
        button = self._find("cc_request_button")
        if button is None:
            return RequestOutcome(False, "no Request button on the castle panel")
        self.nav.tap_match(button)
        self.nav.sleep(2.0)
        if self._find("request_dialog_title") is None:
            return RequestOutcome(False, "request dialog did not open")
        send = self._find("request_send")
        if send is None:
            return RequestOutcome(False, "no Send button")
        self.nav.tap_match(send)
        self.nav.sleep(2.0)
        if self._find("request_dialog_title") is not None:
            return RequestOutcome(False, "dialog still open after Send")
        return RequestOutcome(True)
