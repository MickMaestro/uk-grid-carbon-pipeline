"""Command line entry point.

carbon-ingest intensity --date 2026-10-01
carbon-ingest intensity              # defaults to yesterday, UK time
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

import requests

from grid_carbon.config import Settings
from grid_carbon.extractors import intensity
from grid_carbon.logging_setup import configure_logging
from grid_carbon.uk_time import parse_date, uk_today

logger = logging.getLogger("grid_carbon.cli")


def _date(value: str):
    try:
        return parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="carbon-ingest",
        description="Download a day of Carbon Intensity API data into the raw data folder.",
    )
    sources = parser.add_subparsers(dest="source", required=True, metavar="SOURCE")

    national = sources.add_parser("intensity", help="national carbon intensity")
    national.add_argument(
        "--date", type=_date, help="UK day to fetch as YYYY-MM-DD (default: yesterday)"
    )
    national.add_argument(
        "--raw-dir", type=Path, help="where to save files (default: RAW_DATA_DIR or data/raw)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    settings = Settings.from_env()
    args = build_parser().parse_args(argv)
    configure_logging(settings.log_level)

    day = args.date or uk_today() - timedelta(days=1)
    raw_root = args.raw_dir or settings.raw_data_dir

    try:
        result = intensity.extract_day(day, raw_root)
    except (requests.RequestException, intensity.BadResponseError) as exc:
        logger.error("Couldn't fetch national intensity for %s: %s", day, exc)
        return 1

    logger.info(
        "Done: %s %s, %d half hours, %d without actuals",
        day,
        result.status,
        result.half_hours,
        result.missing_actuals,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
