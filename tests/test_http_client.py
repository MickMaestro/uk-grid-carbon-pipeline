import pytest
import requests
import responses

from grid_carbon.http_client import RetryPolicy, get_with_retries

URL = "https://api.example.test/thing"
POLICY = RetryPolicy(max_attempts=4, base_delay=1.0, max_delay=8.0, jitter=False)


class FakeSleep:
    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


def test_delay_doubles_up_to_the_cap():
    policy = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=False)
    assert [policy.delay_for(n) for n in range(1, 6)] == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_jittered_delay_stays_under_the_cap():
    policy = RetryPolicy(base_delay=1.0, max_delay=30.0)
    for attempt in range(1, 8):
        assert 0 <= policy.delay_for(attempt) <= min(30.0, 2 ** (attempt - 1))


@responses.activate
def test_first_time_success_does_not_wait():
    responses.get(URL, body="ok")
    sleep = FakeSleep()

    assert get_with_retries(URL, policy=POLICY, sleep=sleep).text == "ok"
    assert sleep.waits == []


@responses.activate
def test_server_errors_are_retried():
    responses.get(URL, status=503)
    responses.get(URL, status=502)
    responses.get(URL, body="ok")
    sleep = FakeSleep()

    response = get_with_retries(URL, policy=POLICY, sleep=sleep)

    assert response.status_code == 200
    assert len(responses.calls) == 3
    assert sleep.waits == [1.0, 2.0]


@responses.activate
def test_retry_after_header_is_respected():
    responses.get(URL, status=429, headers={"Retry-After": "3"})
    responses.get(URL, body="ok")
    sleep = FakeSleep()

    get_with_retries(URL, policy=POLICY, sleep=sleep)

    assert sleep.waits == [3.0]


@responses.activate
def test_client_errors_are_not_retried():
    responses.get(URL, status=400)
    sleep = FakeSleep()

    assert get_with_retries(URL, policy=POLICY, sleep=sleep).status_code == 400
    assert len(responses.calls) == 1
    assert sleep.waits == []


@responses.activate
def test_gives_back_the_last_response_when_it_runs_out_of_attempts():
    for _ in range(4):
        responses.get(URL, status=500)
    sleep = FakeSleep()

    assert get_with_retries(URL, policy=POLICY, sleep=sleep).status_code == 500
    assert sleep.waits == [1.0, 2.0, 4.0]


@responses.activate
def test_connection_errors_are_retried_then_raised():
    for _ in range(4):
        responses.get(URL, body=requests.ConnectionError("connection reset"))
    sleep = FakeSleep()

    with pytest.raises(requests.ConnectionError):
        get_with_retries(URL, policy=POLICY, sleep=sleep)

    assert len(responses.calls) == 4
    assert len(sleep.waits) == 3


@responses.activate
def test_sends_a_user_agent_and_extra_headers():
    responses.get(URL, body="ok")

    get_with_retries(URL, headers={"Accept": "application/json"}, policy=POLICY, sleep=FakeSleep())

    sent = responses.calls[0].request.headers
    assert sent["User-Agent"].startswith("uk-grid-carbon-pipeline/")
    assert sent["Accept"] == "application/json"
