"""Alert management: deduplication, cooldowns, visual/haptic dispatch."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Alert:
    kind: str            # e.g. sound:doorbell, vision:warning
    title: str
    body: str = ""
    priority: int = 1    # 0=info 1=important 2=critical
    timestamp: float = field(default_factory=time.time)


class AlertManager:
    """Suppresses repeated alerts with per-kind cooldowns."""

    def __init__(self, default_cooldown: float = 8.0,
                 cooldowns: dict[str, float] | None = None,
                 clock=time.time):
        self.default_cooldown = default_cooldown
        self.cooldowns = cooldowns or {}
        self.clock = clock
        self._last_sent: dict[str, float] = {}
        self._subscribers: list[Callable[[Alert], None]] = []
        self.history: list[Alert] = []

    def subscribe(self, fn: Callable[[Alert], None]) -> None:
        self._subscribers.append(fn)

    def _cooldown_for(self, kind: str) -> float:
        return self.cooldowns.get(kind, self.default_cooldown)

    def raise_alert(self, alert: Alert) -> bool:
        """Returns True if the alert was dispatched (not suppressed)."""
        cd = self._cooldown_for(alert.kind)
        last = self._last_sent.get(alert.kind)
        if last is not None and (self.clock() - last) < cd:
            return False
        self._last_sent[alert.kind] = self.clock()
        self.history.append(alert)
        for fn in self._subscribers:
            try:
                fn(alert)
            except Exception:
                pass
        return True

    def reset(self) -> None:
        self._last_sent.clear()
        self.history.clear()
