from datetime import date, datetime, timezone

import pytest

from grid_carbon.uk_time import (
    half_hours_in_uk_day,
    parse_api_time,
    parse_date,
    uk_day_bounds,
    uk_today,
)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_winter_day_lines_up_with_utc():
    assert uk_day_bounds(date(2026, 1, 15)) == (utc(2026, 1, 15), utc(2026, 1, 16))


def test_summer_day_starts_an_hour_earlier_in_utc():
    assert uk_day_bounds(date(2026, 10, 1)) == (utc(2026, 9, 30, 23), utc(2026, 10, 1, 23))


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 10, 1), 48),
        (date(2026, 1, 15), 48),
        (date(2026, 3, 29), 46),  # clocks went forward
        (date(2025, 10, 26), 50),  # clocks went back
        (date(2026, 10, 25), 50),
        (date(2024, 3, 31), 46),
    ],
)
def test_half_hours_in_uk_day(day, expected):
    assert half_hours_in_uk_day(day) == expected


def test_parse_api_time():
    assert parse_api_time("2026-09-30T23:30Z") == utc(2026, 9, 30, 23, 30)


@pytest.mark.parametrize("bad", ["2026-09-30T23:30", "2026-09-30 23:30Z", "30/09/2026"])
def test_parse_api_time_rejects_other_formats(bad):
    with pytest.raises(ValueError):
        parse_api_time(bad)


def test_uk_today_rolls_over_at_uk_midnight():
    # 23:30 UTC on 1 October is already 00:30 on the 2nd in London
    assert uk_today(utc(2026, 10, 1, 23, 30)) == date(2026, 10, 2)
    assert uk_today(utc(2026, 12, 1, 23, 30)) == date(2026, 12, 1)


def test_parse_date():
    assert parse_date("2026-10-01") == date(2026, 10, 1)


@pytest.mark.parametrize("bad", ["01/10/2026", "2026-13-01", "yesterday", ""])
def test_parse_date_rejects_other_formats(bad):
    with pytest.raises(ValueError, match="expected a date like"):
        parse_date(bad)
