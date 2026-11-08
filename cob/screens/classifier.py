"""Screen classifier: screens.toml lists anchors per screen; first screen (by priority) whose rules
hold wins. Popups get higher priority than the screen underneath them, so they are detected first.

screens.toml:
  [screens.HOME]
  priority = 10
  all  = ["attack_button"]     # every anchor must match
  any  = ["builder_icon", "shop_button"]   # if non-empty, at least one must match
  none = ["next_button"]       # none may match (disambiguates look-alike screens)
  to_home = "wait"             # navigator action towards HOME: wait | back | stop | tap <tpl> [<tpl>...]
                               # | swipe x1 y1 x2 y2; "A else B" runs B when A did nothing
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from cob.vision.frame import Frame, as_frame
from cob.vision.match import Match, match
from cob.vision.templates import TemplateMissing, TemplateStore

log = logging.getLogger(__name__)

UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ScreenDef:
    name: str
    priority: int = 0
    all: tuple[str, ...] = ()
    any: tuple[str, ...] = ()
    none: tuple[str, ...] = ()
    to_home: str = "wait"

    @property
    def anchors(self) -> set[str]:
        return set(self.all) | set(self.any) | set(self.none)


@dataclass
class Classification:
    screen: str
    matches: dict[str, Match] = field(default_factory=dict)  # anchors found while deciding

    @property
    def known(self) -> bool:
        return self.screen != UNKNOWN


def load_screen_defs(path: Path) -> list[ScreenDef]:
    if not path.is_file():
        return []
    data = tomllib.loads(path.read_text("utf-8")).get("screens", {})
    defs = [
        ScreenDef(name, int(d.get("priority", 0)), tuple(d.get("all", ())), tuple(d.get("any", ())),
                  tuple(d.get("none", ())), str(d.get("to_home", "wait")))
        for name, d in data.items()
    ]
    return sorted(defs, key=lambda s: -s.priority)


class ScreenClassifier:
    def __init__(self, store: TemplateStore, defs: list[ScreenDef] | None = None):
        self.store = store
        all_defs = defs if defs is not None else load_screen_defs(store.root / "screens.toml")
        # Screens whose anchors are not captured yet are skipped, so the bot runs with partial assets.
        self.defs = []
        for d in all_defs:
            if missing := sorted(a for a in d.anchors if not store.has(a)):
                log.warning("screen %s disabled, missing templates: %s", d.name, ", ".join(missing))
            elif not (d.all or d.any):
                log.warning("screen %s disabled, no positive anchors", d.name)
            else:
                self.defs.append(d)

    def classify(self, img: Frame | np.ndarray) -> Classification:
        frame = as_frame(img)
        # Memoize per call: anchors are often shared between screens.
        seen: dict[str, Match | None] = {}

        def found(name: str) -> Match | None:
            if name not in seen:
                try:
                    seen[name] = match(frame, self.store.get(name))
                except TemplateMissing:
                    seen[name] = None
            return seen[name]

        for d in self.defs:
            if all(found(a) for a in d.all) and (not d.any or any(found(a) for a in d.any)) \
                    and not any(found(a) for a in d.none):
                return Classification(d.name, {k: v for k, v in seen.items() if v})
        return Classification(UNKNOWN, {k: v for k, v in seen.items() if v})
