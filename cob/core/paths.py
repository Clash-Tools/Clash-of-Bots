"""Resolve app and bundled-tool locations for source runs and frozen (Nuitka) builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    # Nuitka sets __compiled__ on every compiled module; PyInstaller sets sys.frozen.
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Folder holding the exe (frozen) or the repo root (source)."""
    if is_frozen():
        # sys.executable, not argv[0]: started through a PATH symlink (/usr/bin/clashofbots) argv[0]
        # is the bare command name, which would resolve against the working directory.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def tools_dir() -> Path:
    return app_root() / "tools"


def user_data_dir() -> Path:
    """Per-user writable folder for settings, logs, captures."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "ClashOfBots"
    path.mkdir(parents=True, exist_ok=True)
    return path
