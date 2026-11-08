"""Recognise troop-bar cards by their picture, and collect the ones not known yet for labelling.

A card's portrait band (below the "xN" count and the hero's pet / equipment icons, above the level badge
and the upgrade arrows) looks the same whatever the count or level, so it identifies the unit. Known
pictures come from the bundled unit database and from cards the user labelled in the app; every other
card seen in a battle is saved once to the "unknown" folder for the Cards page.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cob.attack.troops import Card
from cob.core.paths import user_data_dir

log = logging.getLogger(__name__)

PORTRAIT_ROWS = (795, 838)
PORTRAIT_INSET = 14  # px from each side of the card
FINGERPRINT = (48, 24)  # w, h the portraits are compared at
MATCH = 0.85  # similarity for "this is that unit"
SAME = 0.92  # similarity for "already saved this picture"
MAX_UNKNOWN = 300


def portrait(bgr: np.ndarray, card: Card) -> np.ndarray:
    y0, y1 = PORTRAIT_ROWS
    return bgr[y0:y1, card.x0 + PORTRAIT_INSET:card.x1 - PORTRAIT_INSET].copy()


def fingerprint(img: np.ndarray) -> np.ndarray:
    small = cv2.resize(img, FINGERPRINT, interpolation=cv2.INTER_AREA).astype(np.float32)
    small -= small.mean()
    norm = float(np.linalg.norm(small))
    return small / norm if norm > 1e-6 else small


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Correlation of two fingerprints, -1..1 (colour kept: a spell and a troop can share a shape)."""
    return float((a * b).sum())


@dataclass
class Known:
    unit_id: str
    print: np.ndarray
    path: Path


def cards_dir() -> Path:
    return user_data_dir() / "cards"


class CardLibrary:
    """Known pictures (database + labelled by the user) and the unknown ones waiting for a label."""

    def __init__(self, db_root: Path | None = None, db_cards: dict[str, tuple[str, ...]] | None = None,
                 folder: Path | None = None):
        self.folder = folder or cards_dir()
        self.unknown_dir = self.folder / "unknown"
        self.labelled_dir = self.folder / "labelled"
        self._db = (db_root, db_cards or {})
        self.reload()

    def reload(self) -> None:
        """Read the folders again (the running bot saves new pictures with its own library)."""
        db_root, db_cards = self._db
        self.known: list[Known] = []
        for unit_id, files in db_cards.items():
            for f in files:
                self._add_known(unit_id, Path(db_root or ".") / f)
        for png in sorted(self.labelled_dir.glob("*.png")):
            self._add_known(png.stem.split("-")[0], png)
        self._unknown = [(fingerprint(img), p) for p in sorted(self.unknown_dir.glob("*.png"))
                         if (img := cv2.imread(str(p))) is not None]

    def _add_known(self, unit_id: str, path: Path) -> None:
        img = cv2.imread(str(path))
        if img is not None:
            self.known.append(Known(unit_id, fingerprint(img), path))

    def identify(self, img: np.ndarray) -> tuple[str, float] | None:
        fp = fingerprint(img)
        scores = ((k.unit_id, similarity(fp, k.print)) for k in self.known)
        best = max(scores, key=lambda t: t[1], default=None)
        return best if best and best[1] >= MATCH else None

    def remember(self, img: np.ndarray, kind_guess: str, note: str = "") -> Path | None:
        """Save a picture nobody has labelled yet, once; None when it is known or already saved."""
        if self.identify(img) is not None:
            return None
        fp = fingerprint(img)
        if any(similarity(fp, other) >= SAME for other, _ in self._unknown):
            return None
        if len(self._unknown) >= MAX_UNKNOWN:
            return None
        self.unknown_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        n = 0
        while (path := self.unknown_dir / f"{stamp}-{n:03d}.png").exists():
            n += 1
        cv2.imwrite(str(path), img)
        path.with_suffix(".json").write_text(json.dumps({"kind_guess": kind_guess, "seen": stamp,
                                                         "note": note}), "utf-8")
        self._unknown.append((fp, path))
        return path

    def unknown(self) -> list[Path]:
        return [p for _, p in self._unknown if p.exists()]

    def label(self, path: Path, unit_id: str) -> Path:
        """Move an unknown picture to labelled/<unit_id>[-n].png; the next battle recognises it."""
        self.labelled_dir.mkdir(parents=True, exist_ok=True)
        n, dest = 1, self.labelled_dir / f"{unit_id}.png"
        while dest.exists():
            n += 1
            dest = self.labelled_dir / f"{unit_id}-{n}.png"
        path.replace(dest)
        path.with_suffix(".json").unlink(missing_ok=True)
        self._unknown = [(fp, p) for fp, p in self._unknown if p != path]
        img = cv2.imread(str(dest))
        if img is not None:
            self.known.append(Known(unit_id, fingerprint(img), dest))
        return dest

    def discard(self, path: Path) -> None:
        path.unlink(missing_ok=True)
        path.with_suffix(".json").unlink(missing_ok=True)
        self._unknown = [(fp, p) for fp, p in self._unknown if p != path]


def library() -> CardLibrary:
    from cob import units

    db = units.load()
    return CardLibrary(db.root, {u.id: u.cards for u in db.units.values() if u.cards})


def observe(lib: CardLibrary, bgr: np.ndarray, cards: list[Card]) -> list[str | None]:
    """Unit id per card (None = not known yet; saved for labelling). Never raises."""
    out: list[str | None] = []
    for c in cards:
        try:
            img = portrait(bgr, c)
            hit = lib.identify(img)
            if hit is None:
                lib.remember(img, c.kind)
            out.append(hit[0] if hit else None)
        except Exception as exc:  # recognition must never break an attack
            log.debug("card@%d not observed: %s", c.x0, exc)
            out.append(None)
    return out


def export_labelled(lib: CardLibrary, dest: Path, resolution: str = "1600x900") -> int:
    """Zip the labelled pictures in the data repository's layout (detection/<res>/cards/<id>[-n].png) with
    cards.json listing unit and file, for clash-of-bots-data's tools/import_cards.py. Returns the count."""
    import zipfile

    files = sorted(lib.labelled_dir.glob("*.png"))
    entries = []
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for png in files:
            arc = f"detection/{resolution}/cards/{png.name}"
            z.write(png, arc)
            entries.append({"unit": png.stem.split("-")[0], "file": arc, "resolution": resolution})
        z.writestr("cards.json", json.dumps({"cards": entries}, indent=2) + "\n")
    return len(entries)
