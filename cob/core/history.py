"""Cycle history: one CSV row per farm cycle in the user data folder (CLI and GUI both append)."""

from __future__ import annotations

import csv
import logging
import time
from pathlib import Path

from cob.core.paths import user_data_dir
from cob.tasks.farm import CycleResult

log = logging.getLogger(__name__)

COLUMNS = ["time", "cycle", "search", "nexts", "base_gold", "base_elixir", "base_dark", "attack",
           "gained_gold", "gained_elixir", "gained_dark", "seconds", "reason", "mode"]
MODES = ("home", "bb")  # "mode" column: home village farming or Builder Base attacks; "" in old rows


def history_path() -> Path:
    return user_data_dir() / "history.csv"


def to_row(cycle: CycleResult, when: float | None = None, mode: str = "home") -> dict[str, str]:
    base, gained = cycle.loot, cycle.gained
    return {
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(when)),
        "cycle": str(cycle.n),
        "search": cycle.search,
        "nexts": str(cycle.nexts),
        "base_gold": str(base.gold) if base else "",
        "base_elixir": str(base.elixir) if base else "",
        "base_dark": str(base.dark) if base else "",
        "attack": cycle.attack,
        "gained_gold": str(gained.gold) if gained else "",
        "gained_elixir": str(gained.elixir) if gained else "",
        "gained_dark": str(gained.dark) if gained else "",
        "seconds": f"{cycle.seconds:.0f}",
        "reason": cycle.reason,
        "mode": mode,
    }


def _upgrade_header(path: Path) -> None:
    """Files from older versions lack newer columns: rewrite once with the current header (old rows get
    empty values), via a temp file so a crash cannot lose the history."""
    with path.open(newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
        if header == COLUMNS or not header:
            return
        f.seek(0)
        rows = list(csv.DictReader(f))
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)
    log.info("history file upgraded to columns %s", ", ".join(COLUMNS))


def append(cycle: CycleResult, path: Path | None = None, mode: str = "home") -> None:
    """Add one row; history must never stop the bot, so errors are only logged."""
    path = path or history_path()
    try:
        if path.exists():
            _upgrade_header(path)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, COLUMNS)
            if new:
                w.writeheader()
            w.writerow(to_row(cycle, mode=mode))
    except OSError as exc:
        log.warning("history not written: %s", exc)


def read(limit: int = 500, path: Path | None = None) -> list[dict[str, str]]:
    """Newest `limit` rows, oldest first."""
    path = path or history_path()
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except (OSError, csv.Error) as exc:
        log.warning("history unreadable: %s", exc)
        return []
    return rows[-limit:]
