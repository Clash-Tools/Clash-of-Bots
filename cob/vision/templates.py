"""Template store: PNGs + metadata (templates.toml) for one resolution, loaded lazily and cached.

Layout: assets/templates/<W>x<H>/
          templates.toml      [defaults] + [templates.<name>] entries (region, threshold, gray, scales, file)
          <name>.png          default file name if `file` omitted
          digits/<font>/0.png..9.png   glyphs for DigitReader (D-009)
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cob.core.paths import app_root
from cob.device.base import TARGET_SIZE
from cob.vision.frame import Region

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.85


class TemplateMissing(KeyError):
    pass


@dataclass(frozen=True)
class Template:
    name: str
    bgr: np.ndarray
    gray: np.ndarray
    region: Region | None  # where to search; None = whole frame
    threshold: float
    use_gray: bool  # gray is ~3x faster; use color when the anchor differs from look-alikes only by hue
    scales: tuple[float, ...] = (1.0,)  # map objects drawn at the camera zoom: try each, best wins

    @property
    def size(self) -> tuple[int, int]:
        return self.bgr.shape[1], self.bgr.shape[0]


def default_root(size: tuple[int, int] = TARGET_SIZE) -> Path:
    return app_root() / "assets" / "templates" / f"{size[0]}x{size[1]}"


class TemplateStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_root()
        meta_path = self.root / "templates.toml"
        meta = tomllib.loads(meta_path.read_text("utf-8")) if meta_path.is_file() else {}
        self._defaults = meta.get("defaults", {})
        self._meta: dict[str, dict] = meta.get("templates", {})
        self._cache: dict[str, Template] = {}

    def names(self) -> list[str]:
        """Declared in metadata or present as a top-level PNG."""
        pngs = {p.stem for p in self.root.glob("*.png")}
        return sorted(pngs | set(self._meta))

    def has(self, name: str) -> bool:
        return name in self._cache or self._file_for(name).is_file()

    def _file_for(self, name: str) -> Path:
        return self.root / self._meta.get(name, {}).get("file", f"{name}.png")

    def get(self, name: str) -> Template:
        if tpl := self._cache.get(name):
            return tpl
        path = self._file_for(name)
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR) if path.is_file() else None
        if bgr is None:
            raise TemplateMissing(f"template '{name}' not found at {path}")
        meta = {**self._defaults, **self._meta.get(name, {})}
        region = meta.get("region")
        tpl = Template(
            name=name,
            bgr=bgr,
            gray=cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY),
            region=tuple(region) if region else None,
            threshold=float(meta.get("threshold", DEFAULT_THRESHOLD)),
            use_gray=bool(meta.get("gray", True)),
            scales=tuple(float(s) for s in meta.get("scales", (1.0,))),
        )
        self._cache[name] = tpl
        return tpl

    def load_dir(self, sub: str) -> dict[str, np.ndarray]:
        """All PNGs in a subfolder keyed by stem (e.g. digit glyphs). Not cached in metadata."""
        out = {}
        for p in sorted((self.root / sub).glob("*.png")):
            img = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if img is not None:
                out[p.stem] = img
        return out
