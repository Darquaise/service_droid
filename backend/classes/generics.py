from __future__ import annotations

from datetime import datetime
from typing import Iterable


class SettingTimeline:
    """Generic Setting Timeline"""

    __slots__ = "default", "periods"

    def __init__(self, default: float, periods: Iterable[tuple[datetime, float]] = ()):
        self.default = default
        self.periods = sorted(periods, key=lambda p: p[0])

    @property
    def current(self) -> float:
        return self.periods[-1][1] if self.periods else self.default

    @property
    def start(self) -> datetime | None:
        return self.periods[0][0] if self.periods else None

    def value_at(self, when: datetime) -> float:
        if not self.periods:
            return self.default
        value = self.periods[0][1]  # before the first period the oldest value applies
        for valid_from, period_value in self.periods:
            if valid_from > when:
                break
            value = period_value
        return value

    def add(self, value: float, valid_from: datetime) -> None:
        self.periods.append((valid_from, value))
        self.periods.sort(key=lambda p: p[0])
