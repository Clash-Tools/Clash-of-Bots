"""Named read regions (regions.toml next to the templates): coordinates stay in data, not code."""

from __future__ import annotations

import tomllib
from pathlib import Path

from cob.vision.frame import Region


def load_regions(root: Path) -> dict[str, dict[str, Region]]:
    """{"loot": {"gold": (x, y, w, h), ...}, "bar": {...}, ...}; empty if the file is missing."""
    path = Path(root) / "regions.toml"
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text("utf-8"))
    return {
        group: {name: tuple(int(v) for v in box) for name, box in items.items()}
        for group, items in data.items()
        if isinstance(items, dict)
    }
