"""Helpers for UK days and the API's UTC timestamps.

The API groups data by UK calendar day but labels every half hour in UTC, so a day's
boundaries move by an hour during British Summer Time, and the days the clocks change are
an hour shorter or longer than usual.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
HALF_HOUR = timedelta(minutes=30)
API_TIME_FORMAT = "%Y-%m-%dT%H:%MZ"


def uk_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC start and end of a UK calendar day."""
    start = datetime.combine(day, time.min, tzinfo=UK)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=UK)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def half_hours_in_uk_day(day: date) -> int:
    """48 on a normal day, 46 when the clocks go forward and 50 when they go back."""
    start, end = uk_day_bounds(day)
    return (end - start) // HALF_HOUR


def parse_api_time(value: str) -> datetime:
    """Parse a timestamp like 2026-10-01T23:30Z into an aware UTC datetime."""
    return datetime.strptime(value, API_TIME_FORMAT).replace(tzinfo=timezone.utc)


def uk_today(now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(UK).date()


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"expected a date like 2026-10-01, got {value!r}") from None
