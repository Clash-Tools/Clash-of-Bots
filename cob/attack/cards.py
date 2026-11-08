"""Recognise troop-bar cards by their picture, and collect the ones not known yet for labelling.

A card's portrait band (below the "xN" count and the hero's pet / equipment icons, above the level badge
and the upgrade arrows) looks the same whatever the count or level, so it identifies the unit. Known
pictures come from the bundled unit database and from cards the user labelled in the app; every other
card seen in a battle is saved once to the "unknown" folder for the Cards page.

Every unit also has a portrait rendered from the game's own icon (unit database, D-036). A real card
differs from it by the card background (transparent in the portrait), the count / level glyphs (near
white) and a pixel or two of offset, so those are compared with a masked correlation over small shifts.
Real pictures are tried first; a portrait must score PORTRAIT_MATCH and beat the next unit by
PORTRAIT_GAP.
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
PORTRAIT_SIZE = (42, 22)  # w, h portraits are compared at
PORTRAIT_SHIFT = 3  # px (full size) between tried offsets, within the portrait's margin
PORTRAIT_MATCH = 0.82  # real cards scored 0.92-0.99 on their own unit, <= 0.69 on any other
PORTRAIT_GAP = 0.1
GLYPH = 215  # pixels with every channel above this are count / level text: not compared
OPAQUE = 0.6  # portrait alpha above which the icon covers the card background


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


class Portraits:
    """Game-rendered portraits of every unit, as shifted copies ready for one vectorised comparison."""

    def __init__(self, pictures: dict[str, tuple[np.ndarray, int]]):
        """pictures: unit id -> (BGRA portrait with `margin` px around the band, margin)."""
        self.ids: list[str] = []
        colours, masks = [], []
        w, h = PORTRAIT_SIZE
        for unit_id, (img, margin) in pictures.items():
            if img is None or img.ndim != 3 or img.shape[2] != 4:
                continue
            bh, bw = img.shape[0] - 2 * margin, img.shape[1] - 2 * margin
            if bh <= 0 or bw <= 0:
                continue
            steps = range(0, 2 * margin + 1, PORTRAIT_SHIFT) if margin else [0]
            for dy in steps:
                for dx in steps:
                    crop = cv2.resize(img[dy:dy + bh, dx:dx + bw], (w, h), interpolation=cv2.INTER_AREA)
                    colours.append(crop[..., :3].astype(np.float32))
                    masks.append(crop[..., 3] > OPAQUE * 255)
                    self.ids.append(unit_id)
        self.colours = np.array(colours, np.float32).reshape(-1, h, w, 3)
        self.masks = np.array(masks, bool).reshape(-1, h, w)

    def __len__(self) -> int:
        return len(set(self.ids))

    def scores(self, img: np.ndarray) -> dict[str, float]:
        """Best masked correlation per unit for a card's portrait band (BGR)."""
        if not self.ids:
            return {}
        q = cv2.resize(img, PORTRAIT_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)
        m = self.masks & (q.min(axis=2) < GLYPH)[None]  # (n, h, w)
        n = m.sum(axis=(1, 2)).astype(np.float32) * 3
        mm = m[..., None]
        qn = np.where(mm, q[None], 0.0)
        tn = np.where(mm, self.colours, 0.0)
        safe = np.maximum(n, 1.0)[:, None, None, None]
        qc = np.where(mm, qn - qn.sum(axis=(1, 2, 3), keepdims=True) / safe, 0.0)
        tc = np.where(mm, tn - tn.sum(axis=(1, 2, 3), keepdims=True) / safe, 0.0)
        num = (qc * tc).sum(axis=(1, 2, 3))
        den = np.sqrt((qc * qc).sum(axis=(1, 2, 3)) * (tc * tc).sum(axis=(1, 2, 3))) + 1e-6
        corr = np.where(n >= 120, num / den, -1.0)  # too little icon left to compare: no opinion
        best: dict[str, float] = {}
        for unit_id, c in zip(self.ids, corr.tolist(), strict=True):
            if c > best.get(unit_id, -2.0):
                best[unit_id] = c
        return best

    def identify(self, img: np.ndarray) -> tuple[str, float] | None:
        ranked = sorted(self.scores(img).items(), key=lambda kv: kv[1], reverse=True)
        if not ranked or ranked[0][1] < PORTRAIT_MATCH:
            return None
        if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < PORTRAIT_GAP:
            return None
        return ranked[0]


class CardLibrary:
    """Known pictures (database + labelled by the user) and the unknown ones waiting for a label."""

    def __init__(self, db_root: Path | None = None, db_cards: dict[str, tuple[str, ...]] | None = None,
                 folder: Path | None = None, portraits: dict[str, tuple[str, int]] | None = None,
                 kinds: dict[str, str] | None = None):
        self.folder = folder or cards_dir()
        self.unknown_dir = self.folder / "unknown"
        self.labelled_dir = self.folder / "labelled"
        self._db = (db_root, db_cards or {})
        self.kinds = kinds or {}  # unit id -> unit database kind (troop, spell, hero, ...)
        pictures = {u: (cv2.imread(str(Path(db_root or ".") / f), cv2.IMREAD_UNCHANGED), m)
                    for u, (f, m) in (portraits or {}).items()}
        self.portraits = Portraits(pictures)
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
        if best and best[1] >= MATCH:
            return best
        hit = self.portraits.identify(img)
        if hit is not None:  # this run's later battles match the real picture on the fast path
            self.known.append(Known(hit[0], fp, Path()))
        return hit

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
    home = [u for u in db.units.values() if u.village == "home"]
    return CardLibrary(db.root, {u.id: u.cards for u in home if u.cards},
                       portraits={u.id: (u.portrait, u.portrait_margin) for u in home if u.portrait},
                       kinds={u.id: u.kind for u in db.units.values()})


BAR_KIND = {"troop": "troop", "super_troop": "troop", "event_troop": "troop", "spell": "spell",
            "event_spell": "spell", "hero": "single", "siege": "single", "pet": "single"}


def with_unit_kinds(lib: CardLibrary | None, cards: list[Card], names: list[str | None]) -> list[Card]:
    """Cards whose unit is recognised get that unit's bar kind (troop / spell / single) instead of the one
    guessed from the card's colour and order; the others stay as read."""
    from dataclasses import replace

    out = []
    for c, n in zip(cards, names, strict=True):
        kind = BAR_KIND.get(lib.kinds.get(n, "")) if lib is not None and n else None
        if kind and kind != c.kind:
            log.info("card@%d is %s: %s, not %s", c.x0, n, kind, c.kind)
            c = replace(c, kind=kind)
        out.append(c)
    return out


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
