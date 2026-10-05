"""National carbon intensity for one UK day, from /intensity/date/{date}.

The response is saved as it came back. Parsing here is only to check it's what we expect
before it gets saved; cleaning and reshaping happen later in the warehouse.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from grid_carbon import __version__
from grid_carbon.http_client import RetryPolicy, get_with_retries
from grid_carbon.storage import save_raw
from grid_carbon.uk_time import (
    HALF_HOUR,
    half_hours_in_uk_day,
    parse_api_time,
    uk_day_bounds,
    uk_today,
)

logger = logging.getLogger(__name__)

SOURCE = "national_intensity"
BASE_URL = "https://api.carbonintensity.org.uk"
FILENAME = "intensity.json"
FIRST_DAY = date(2017, 9, 12)  # earliest day the API has data for
INDEX_BANDS = frozenset({"very low", "low", "moderate", "high", "very high"})


class BadResponseError(ValueError):
    """The API answered, but not with data we can use."""


@dataclass(frozen=True)
class HalfHour:
    start: datetime
    end: datetime
    forecast: int
    actual: int | None
    index: str


@dataclass(frozen=True)
class ExtractResult:
    day: date
    status: str  # "saved" or "no_data"
    half_hours: int = 0
    missing_actuals: int = 0
    path: Path | None = None


def _is_reading(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def parse_intensity(text: str) -> list[HalfHour]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        raise BadResponseError(f"response isn't JSON: {text[:100]!r}") from None

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise BadResponseError(f"expected an object with a 'data' list, got {text[:100]!r}")

    half_hours = []
    for i, item in enumerate(data):
        try:
            start = parse_api_time(item["from"])
            end = parse_api_time(item["to"])
            forecast = item["intensity"]["forecast"]
            actual = item["intensity"]["actual"]
            index = item["intensity"]["index"]
        except (KeyError, TypeError, ValueError):
            raise BadResponseError(f"half hour {i} is malformed: {item!r}") from None

        if end - start != HALF_HOUR:
            raise BadResponseError(f"half hour {i} runs from {start} to {end}")
        if not _is_reading(forecast) or not (actual is None or _is_reading(actual)):
            raise BadResponseError(f"half hour {i} has odd readings: {item['intensity']!r}")
        if index not in INDEX_BANDS:
            raise BadResponseError(f"half hour {i} has an unknown index {index!r}")

        half_hours.append(HalfHour(start, end, forecast, actual, index))
    return half_hours


def check_day(half_hours: list[HalfHour], day: date) -> None:
    """Make sure every half hour falls inside the UK day we asked for.

    A wrong date is an error. A missing or duplicated half hour only gets a warning: the file
    is still the API's answer, and judging whether a day is complete is a job for the data
    tests further down the line.
    """
    start, end = uk_day_bounds(day)
    outside = [h for h in half_hours if h.start < start or h.end > end]
    if outside:
        raise BadResponseError(
            f"asked for {day} but got half hours outside it, starting {outside[0].start}"
        )

    expected = half_hours_in_uk_day(day)
    distinct = len({h.start for h in half_hours})
    if len(half_hours) != expected or distinct != expected:
        logger.warning(
            "Expected %d half hours for %s, got %d (%d distinct)",
            expected,
            day,
            len(half_hours),
            distinct,
        )


def extract_day(
    day: date,
    raw_root: Path,
    *,
    session: requests.Session | None = None,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> ExtractResult:
    """Download one UK day of national carbon intensity and save it to the raw folder."""
    url = f"{BASE_URL}/intensity/date/{day.isoformat()}"
    logger.info("Fetching national carbon intensity for %s", day)

    response = get_with_retries(
        url,
        headers={"Accept": "application/json"},
        session=session,
        policy=policy,
        sleep=sleep,
    )
    response.raise_for_status()
    half_hours = parse_intensity(response.text)

    if not half_hours:
        if day < FIRST_DAY:
            logger.info("No data for %s, the API's history starts on %s", day, FIRST_DAY)
        else:
            logger.warning("The API returned no data for %s", day)
        return ExtractResult(day, "no_data")

    check_day(half_hours, day)

    missing = sum(h.actual is None for h in half_hours)
    if missing and day < uk_today(now()):
        logger.warning(
            "%d half hours on %s have no actual reading yet. Run this day again later to fill "
            "them in.",
            missing,
            day,
        )
    elif missing:
        logger.info(
            "%d half hours on %s haven't happened yet, so have forecasts only", missing, day
        )

    fetched_at = now().astimezone(timezone.utc)
    saved = save_raw(
        raw_root,
        SOURCE,
        day,
        FILENAME,
        response.content,
        metadata={
            "url": response.url,
            "http_status": response.status_code,
            "fetched_at": fetched_at.isoformat(timespec="seconds"),
            "half_hours": len(half_hours),
            "expected_half_hours": half_hours_in_uk_day(day),
            "missing_actuals": missing,
            "pipeline_version": __version__,
        },
    )
    logger.info("Saved %d half hours for %s to %s", len(half_hours), day, saved.path)
    return ExtractResult(day, "saved", len(half_hours), missing, saved.path)
