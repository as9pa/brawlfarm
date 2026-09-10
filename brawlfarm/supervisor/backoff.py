"""Offline backoff for instances whose adb probe fails (BlueStacks window closed): wait
2, 4, 8, 16, then 30 minutes between relaunch attempts. In memory only, like the legacy
watchdog; a supervisor restart simply probes again."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

BACKOFF_MINUTES = (2, 4, 8, 16, 30)


@dataclass
class _Entry:
    misses: int = 0
    until: datetime | None = None


@dataclass
class OfflineBackoff:
    _entries: dict[str, _Entry] = field(default_factory=dict)

    def record_miss(self, name: str, now: datetime) -> datetime:
        e = self._entries.setdefault(name, _Entry())
        e.misses += 1
        minutes = BACKOFF_MINUTES[min(e.misses, len(BACKOFF_MINUTES)) - 1]
        e.until = now + timedelta(minutes=minutes)
        return e.until

    def until(self, name: str, now: datetime) -> datetime | None:
        e = self._entries.get(name)
        if e is None or e.until is None or e.until <= now:
            return None
        return e.until

    def misses(self, name: str) -> int:
        e = self._entries.get(name)
        return e.misses if e else 0

    def clear(self, name: str) -> None:
        self._entries.pop(name, None)

    def clear_all(self) -> None:
        self._entries.clear()
