"""GET requests with retries."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import requests

from grid_carbon import __version__

logger = logging.getLogger(__name__)

# Worth retrying: rate limiting and server-side errors. A 400 or 404 means the request itself is
# wrong, and asking again won't change the answer.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

REPO_URL = "https://github.com/MickMaestro/uk-grid-carbon-pipeline"
USER_AGENT = f"uk-grid-carbon-pipeline/{__version__} (+{REPO_URL})"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: bool = True

    def delay_for(self, attempt: int) -> float:
        """Seconds to wait after the given failed attempt (counting from 1).

        Doubles each time up to max_delay. With jitter the wait is picked at random below that
        cap, so lots of clients that failed together don't all retry at the same moment.
        """
        cap = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
        return random.uniform(0, cap) if self.jitter else cap  # noqa: S311


def _retry_after(response: requests.Response) -> float | None:
    try:
        return max(0.0, float(response.headers["Retry-After"]))
    except (KeyError, ValueError):
        return None  # missing, or given as a date, which we don't bother parsing


def get_with_retries(
    url: str,
    *,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
    policy: RetryPolicy | None = None,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> requests.Response:
    """GET a URL, retrying timeouts, dropped connections and retryable status codes.

    Returns the last response whatever its status, so the caller decides what counts as an
    error. Raises the network error if no attempt got a response at all. Tests pass in their own
    session and sleep so nothing touches the network or actually waits.
    """
    policy = policy or RetryPolicy()
    http = session or requests.Session()
    all_headers = {"User-Agent": USER_AGENT, **(headers or {})}

    for attempt in range(1, policy.max_attempts + 1):
        last_go = attempt == policy.max_attempts
        try:
            response = http.get(url, params=params, headers=all_headers, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            if last_go:
                logger.error("GET %s failed after %d attempts: %s", url, attempt, exc)
                raise
            wait = policy.delay_for(attempt)
            logger.warning(
                "GET %s failed (%s), attempt %d of %d. Retrying in %.1fs",
                url,
                type(exc).__name__,
                attempt,
                policy.max_attempts,
                wait,
            )
            sleep(wait)
            continue

        if response.status_code in RETRY_STATUSES and not last_go:
            wait = _retry_after(response)
            wait = min(policy.delay_for(attempt) if wait is None else wait, policy.max_delay)
            logger.warning(
                "GET %s returned %d, attempt %d of %d. Retrying in %.1fs",
                url,
                response.status_code,
                attempt,
                policy.max_attempts,
                wait,
            )
            sleep(wait)
            continue

        return response

    raise AssertionError("unreachable")  # pragma: no cover
