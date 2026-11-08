"""Failure reports (#170): whenever something goes wrong, save a folder with the screen, any extra images
(the base outline the attack worked from), the log lines leading up to it and the details as JSON.

    reports/<time>_<label>/screen.png    the frame when it failed
                           base.png      (attack) red line, fitted outline and deploy points drawn on it
                           log.txt       the last log lines before the failure
                           report.json   label, time, version and the details passed in

The Logs page zips them all (export_reports) so a failed base can be looked at later or shared.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import zipfile
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from cob.core.paths import user_data_dir

log = logging.getLogger(__name__)

KEEP = 100  # newest report folders kept
RECENT_LINES = 400  # log lines kept in memory for log.txt
SCREEN = "screen.png"

_recent: deque[str] = deque(maxlen=RECENT_LINES)


class RecentLines(logging.Handler):
    """Keeps the newest formatted log lines in memory, for the report's log.txt."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _recent.append(self.format(record))
        except Exception:  # logging must never fail the caller
            pass


def recent_lines() -> list[str]:
    return list(_recent)


def snapshot_dir() -> Path:
    path = user_data_dir() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _free_folder(parent: Path, name: str) -> Path:
    path, n = parent / name, 2
    while path.exists():
        path, n = parent / f"{name}-{n}", n + 1
    return path


def other_app(device) -> str | None:
    """Package of the app in front when it is not the game (the user picked up the phone), else None."""
    from cob.device.base import COC_PACKAGE

    try:
        package = device.foreground_package()
    except Exception:  # no answer: assume the game
        return None
    return package if package and package != COC_PACKAGE else None


def placeholder(shape: tuple[int, ...], text: str) -> np.ndarray:
    out = np.zeros((shape[0], shape[1], 3) if len(shape) >= 2 else (900, 1600, 3), np.uint8)
    cv2.putText(out, text, (40, out.shape[0] // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2,
                cv2.LINE_AA)
    return out


def save_snapshot(frame: np.ndarray, label: str, folder: Path | None = None, keep: int = KEEP,
                  details: dict | None = None, images: dict[str, np.ndarray] | None = None,
                  device=None) -> Path | None:
    """Write a report folder `<time>_<label>/` and return its screen.png; keep only the newest `keep`
    report folders. Never raises: diagnostics must never break the bot.

    `device`: when another app is in front, its screen (someone's messages, profiles...) is not kept:
    screen.png is a plain placeholder naming the app instead."""
    try:
        if frame is None:
            raise ValueError("no frame")
        if device is not None and (app := other_app(device)):
            frame = placeholder(frame.shape, f"another app was in front: {app}")
            details = {**(details or {}), "foreground_app": app}
        parent = folder or snapshot_dir()
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:60]
        out = _free_folder(parent, f"{time.strftime('%Y%m%d-%H%M%S')}_{safe}")
        out.mkdir(parents=True)
        screen = out / SCREEN
        if not cv2.imwrite(str(screen), frame):
            raise OSError(f"could not write {screen}")
        for name, image in (images or {}).items():
            try:
                cv2.imwrite(str(out / f"{name}.png"), image)
            except Exception as exc:
                log.debug("report image %s not saved: %s", name, exc)
        from cob import __version__

        info = {"label": label, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "version": __version__,
                "details": details or {}}
        (out / "report.json").write_text(json.dumps(info, indent=2, default=str), "utf-8")
        (out / "log.txt").write_text("\n".join(recent_lines()) + "\n", "utf-8")
        for old in list_reports(parent)[:-keep] if keep else []:
            shutil.rmtree(old, ignore_errors=True)
        log.info("snapshot saved: %s", screen)
        return screen
    except Exception as exc:
        log.warning("snapshot failed: %s", exc)
        return None


def list_reports(folder: Path | None = None) -> list[Path]:
    """Report folders, oldest first."""
    parent = folder or snapshot_dir()
    if not parent.is_dir():
        return []
    return sorted(p for p in parent.iterdir() if p.is_dir() and (p / SCREEN).is_file())


def export_reports(dest: Path, folder: Path | None = None, logs: list[Path] | tuple[Path, ...] = ()) -> int:
    """Zip every report folder (screens as they are, text sanitized) plus the given log files.
    Returns the number of reports in the zip."""
    from cob.core.diagnostics import known_serials, sanitize

    serials = known_serials()
    reports = list_reports(folder)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for report in reports:
            for f in sorted(report.iterdir()):
                arc = f"reports/{report.name}/{f.name}"
                if f.suffix in (".txt", ".json"):
                    z.writestr(arc, sanitize(f.read_text("utf-8", errors="replace"), serials))
                elif f.is_file():
                    z.write(f, arc, zipfile.ZIP_STORED)  # PNG is compressed already
        for path in logs:
            if path.is_file():
                z.writestr(f"logs/{path.name}", sanitize(path.read_text("utf-8", errors="replace"), serials))
    return len(reports)
