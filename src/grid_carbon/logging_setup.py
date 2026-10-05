from __future__ import annotations

import logging
import time

FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
HANDLER_NAME = "grid_carbon_console"


def configure_logging(level: str = "INFO") -> None:
    """Log to the console with UTC timestamps.

    Only replaces its own handler, so anything else that has attached one (pytest now,
    Airflow later) keeps working.
    """
    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):
        raise ValueError(f"unknown log level {level!r}")

    formatter = logging.Formatter(FORMAT, datefmt="%Y-%m-%dT%H:%M:%SZ")
    formatter.converter = time.gmtime

    handler = logging.StreamHandler()
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        if existing.get_name() == HANDLER_NAME:
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(numeric)
    logging.getLogger("urllib3").setLevel(max(numeric, logging.INFO))
