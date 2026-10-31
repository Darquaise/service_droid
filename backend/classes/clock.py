from __future__ import annotations

from datetime import datetime, timedelta, timezone

_offset = timedelta()


def now() -> datetime:
    """Naive local time, like ``datetime.now()``, shifted by the test offset."""
    return datetime.now() + _offset


def now_utc() -> datetime:
    """Timezone-aware UTC time, like ``datetime.now(timezone.utc)``, shifted by the test offset."""
    return datetime.now(timezone.utc) + _offset


def advance(delta: timedelta) -> None:
    """Test-only: move the clock forward (or back) by ``delta``."""
    global _offset
    _offset += delta


def reset() -> None:
    """Test-only: drop the offset."""
    global _offset
    _offset = timedelta()
