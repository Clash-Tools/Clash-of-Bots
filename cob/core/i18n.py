"""Translations (#103): `tr("English text")` returns the text in the chosen language.

Catalogs are JSON files in assets/i18n/<code>.json: {"_language": "Deutsch", "English text": "Deutscher
Text", ...}. A missing key falls back to the English source text, so a half-done catalog still works.
English is the source language and has no catalog. Placeholders use str.format names:
tr("Stops after {n} cycles", n=5) - translators keep "{n}" in their text.

The language is chosen in Settings, saved in ui.json and set at start-up before the UI is built (like
the theme, D-029). `scripts/i18n.py extract` lists every tr() string for translators.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from cob.core.paths import app_root

log = logging.getLogger(__name__)

SOURCE = "en"
CODE = re.compile(r"^[a-z]{2,3}(_[A-Z]{2})?$")  # "de", "pt_BR"
LANGUAGE = SOURCE
_catalog: dict[str, str] = {}


def catalog_dir() -> Path:
    return app_root() / "assets" / "i18n"


def available() -> dict[str, str]:
    """Language code -> its own name ("Deutsch"); English always first."""
    langs = {SOURCE: "English"}
    folder = catalog_dir()
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        if not CODE.match(path.stem):
            continue  # template.json and the like
        try:
            name = json.loads(path.read_text("utf-8")).get("_language") or path.stem
        except (OSError, ValueError, AttributeError):
            continue
        langs[path.stem] = str(name)
    return langs


def set_language(code: str) -> str:
    """Load `code`'s catalog; unknown or broken catalogs fall back to English. Returns the code in use."""
    global LANGUAGE, _catalog
    LANGUAGE, _catalog = SOURCE, {}
    if code == SOURCE or not CODE.match(code or ""):
        return LANGUAGE
    path = catalog_dir() / f"{code}.json"
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("language %s not loaded (%s): using English", code, exc)
        return LANGUAGE
    if not isinstance(raw, dict):
        return LANGUAGE
    _catalog = {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str) and v and
                not k.startswith("_")}
    LANGUAGE = code
    return LANGUAGE


def tr(text: str, **fmt) -> str:
    s = _catalog.get(text, text)
    if not fmt:
        return s
    try:
        return s.format(**fmt)
    except (KeyError, IndexError, ValueError):  # a translator broke a placeholder: show the English text
        return text.format(**fmt)
