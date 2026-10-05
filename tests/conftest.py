from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def normal_day() -> bytes:
    """/intensity/date/2026-10-01 as the API returned it: 48 half hours, all with actuals."""
    return load("intensity_date_2026-10-01.json")


@pytest.fixture
def clocks_back_day() -> bytes:
    """/intensity/date/2025-10-26, the day the clocks went back: 50 half hours."""
    return load("intensity_date_2025-10-26.json")


@pytest.fixture
def unfinished_day() -> bytes:
    """/intensity/date/2026-10-05 fetched mid-afternoon: the last 17 half hours have no actual."""
    return load("intensity_date_2026-10-05_partial.json")
