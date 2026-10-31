from datetime import datetime, timedelta, timezone

import pytest

from classes.galatron import next_reset

pytestmark = pytest.mark.offline

UTC = timezone.utc


def test_next_reset_is_the_following_midnight_utc():
    assert next_reset(datetime(2026, 10, 31, 12, 30, tzinfo=UTC)) == datetime(2026, 11, 1, tzinfo=UTC)


def test_an_exact_midnight_belongs_to_the_day_it_starts():
    assert next_reset(datetime(2026, 11, 1, tzinfo=UTC)) == datetime(2026, 11, 2, tzinfo=UTC)


def test_the_last_second_of_a_day_resets_one_second_later():
    last = datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)
    assert next_reset(last) - last == timedelta(seconds=1)


def test_other_timezones_are_read_as_the_utc_day():
    # 01:30 at +02:00 is still the previous UTC day
    local = datetime(2026, 11, 1, 1, 30, tzinfo=timezone(timedelta(hours=2)))
    assert next_reset(local) == datetime(2026, 11, 1, tzinfo=UTC)
