"""Where a cycle's time goes (#166): device I/O counters and per-step durations, logged per cycle."""

from __future__ import annotations

from collections import defaultdict


class IoStats:
    """Count and total seconds per kind of device call (capture, input, shell)."""

    def __init__(self):
        self.calls: dict[str, int] = defaultdict(int)
        self.seconds: dict[str, float] = defaultdict(float)

    def add(self, kind: str, seconds: float) -> None:
        self.calls[kind] += 1
        self.seconds[kind] += seconds

    def snapshot(self) -> dict[str, tuple[int, float]]:
        return {k: (self.calls[k], self.seconds[k]) for k in self.calls}

    @staticmethod
    def since(before: dict[str, tuple[int, float]], after: dict[str, tuple[int, float]]) -> str:
        """'capture 41x 14.2s, input 30x 9.8s' for the calls made between two snapshots."""
        parts = []
        for k, (n, s) in sorted(after.items()):
            n0, s0 = before.get(k, (0, 0.0))
            if n > n0:
                parts.append(f"{k} {n - n0}x {s - s0:.1f}s")
        return ", ".join(parts) or "-"
