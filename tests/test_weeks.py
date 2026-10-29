from datetime import date

import pytest

from app.weeks import week_days, week_start_of


@pytest.mark.parametrize(
    "day,week_start,expected",
    [
        (date(2026, 10, 30), 5, date(2026, 10, 24)),  # Friday, Saturday start: the Saturday before
        (date(2026, 10, 31), 5, date(2026, 10, 31)),  # the Saturday itself
        (date(2026, 10, 29), 0, date(2026, 10, 26)),  # Thursday, Monday start
        (date(2026, 11, 1), 6, date(2026, 11, 1)),  # Sunday start on a Sunday
    ],
)
def test_week_start_of(day, week_start, expected):
    assert week_start_of(day, week_start) == expected


def test_week_days():
    days = week_days(date(2026, 10, 31))
    assert len(days) == 7 and days[0] == date(2026, 10, 31) and days[-1] == date(2026, 11, 6)
