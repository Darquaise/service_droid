from datetime import datetime, timedelta

import pytest

from classes import clock

pytestmark = pytest.mark.offline


@pytest.fixture(autouse=True)
def _clean_clock():
    clock.reset()
    yield
    clock.reset()


def test_now_is_naive_local_time_like_datetime_now():
    before = datetime.now()
    now = clock.now()
    after = datetime.now()
    assert now.tzinfo is None
    assert before <= now <= after


def test_now_utc_is_timezone_aware_utc():
    now = clock.now_utc()
    assert now.tzinfo is not None and now.utcoffset() == timedelta(0)


def test_advance_shifts_both_clocks_and_reset_drops_the_shift():
    clock.advance(timedelta(days=2))
    assert timedelta(days=1, hours=23) < clock.now() - datetime.now() < timedelta(days=2, minutes=1)
    assert timedelta(days=1, hours=23) < clock.now_utc() - datetime.now(clock.now_utc().tzinfo) < timedelta(days=2, minutes=1)

    clock.advance(timedelta(hours=-48))
    assert abs(clock.now() - datetime.now()) < timedelta(seconds=1)

    clock.advance(timedelta(days=5))
    clock.reset()
    assert abs(clock.now() - datetime.now()) < timedelta(seconds=1)
