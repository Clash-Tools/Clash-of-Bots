"""Logging: live console, one file per session, and a rolling combined log, all in the user data dir.

    logs/cob.log                              everything, rotating (5 MB x 3)
    logs/sessions/session-YYYYMMDD-HHMMSS.log one file per run of the CLI or the window (newest 30 kept)
"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from cob.core.paths import user_data_dir

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_CONSOLE_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"
KEEP_SESSIONS = 30

_session_file: Path | None = None


def log_dir() -> Path:
    path = user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sessions_dir() -> Path:
    path = log_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_log_file() -> Path | None:
    """This run's session log (None before setup_logging)."""
    return _session_file


def latest_session_log() -> Path | None:
    files = sorted(sessions_dir().glob("session-*.log"))
    return files[-1] if files else None


def _prune(folder: Path, keep: int) -> None:
    for old in sorted(folder.glob("session-*.log"))[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass  # still open in another bot window


def setup_logging(verbose: bool = False, console: bool = True, session: bool = True) -> Path | None:
    """Idempotent. Returns this session's log file (None when `session` is False: quick tools)."""
    global _session_file
    root = logging.getLogger()
    if root.handlers:
        return _session_file
    root.setLevel(logging.DEBUG)

    if console:
        stream = logging.StreamHandler()
        stream.setLevel(logging.DEBUG if verbose else logging.INFO)
        stream.setFormatter(logging.Formatter(_CONSOLE_FORMAT, "%H:%M:%S"))
        root.addHandler(stream)

    from cob.core.snapshots import RecentLines

    recent = RecentLines()  # #170: the log lines before a failure go into its report
    recent.setLevel(logging.DEBUG)
    recent.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(recent)

    rolling = RotatingFileHandler(log_dir() / "cob.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    rolling.setLevel(logging.DEBUG)
    rolling.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(rolling)

    if not session:
        _session_file = None
        return None
    folder = sessions_dir()
    _session_file = folder / f"session-{time.strftime('%Y%m%d-%H%M%S')}.log"
    per_session = logging.FileHandler(_session_file, encoding="utf-8")
    per_session.setLevel(logging.DEBUG)
    per_session.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(per_session)
    _prune(folder, KEEP_SESSIONS)

    from cob import __version__

    logging.getLogger("cob").info("Clash of Bots %s - session log %s", __version__, _session_file)
    return _session_file
