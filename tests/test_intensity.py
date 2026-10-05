import json
import logging
from datetime import date, datetime, timezone

import pytest
import requests
import responses

from grid_carbon.extractors import intensity
from grid_carbon.http_client import RetryPolicy
from grid_carbon.storage import MANIFEST_NAME, day_folder

NO_RETRY_WAIT = RetryPolicy(max_attempts=2, base_delay=0, jitter=False)


def url_for(day):
    return f"{intensity.BASE_URL}/intensity/date/{day.isoformat()}"


def run(day, raw_root, now=datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)):
    return intensity.extract_day(
        day, raw_root, policy=NO_RETRY_WAIT, sleep=lambda _: None, now=lambda: now
    )


def warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


# parsing


def test_parses_a_real_day(normal_day):
    half_hours = intensity.parse_intensity(normal_day.decode())

    assert len(half_hours) == 48
    first = half_hours[0]
    assert first.start == datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)
    assert (first.forecast, first.actual, first.index) == (161, 181, "high")


def test_empty_data_parses_to_nothing():
    assert intensity.parse_intensity('{"data": []}') == []


@pytest.mark.parametrize(
    "body",
    [
        "<html>Bad gateway</html>",
        '{"error": {"code": "400 Bad Request"}}',
        '{"data": {"from": "2026-10-01T00:00Z"}}',
    ],
)
def test_rejects_responses_that_are_not_intensity_data(body):
    with pytest.raises(intensity.BadResponseError):
        intensity.parse_intensity(body)


def half_hour(**changes):
    item = {
        "from": "2026-10-01T11:00Z",
        "to": "2026-10-01T11:30Z",
        "intensity": {"forecast": 117, "actual": 116, "index": "moderate"},
    }
    item["intensity"].update(changes.pop("intensity", {}))
    item.update(changes)
    return json.dumps({"data": [item]})


@pytest.mark.parametrize(
    "body",
    [
        half_hour(to="2026-10-01T12:00Z"),
        half_hour(**{"from": "01/10/2026 11:00"}),
        half_hour(intensity={"forecast": -5}),
        half_hour(intensity={"actual": "116"}),
        half_hour(intensity={"forecast": True}),
        half_hour(intensity={"index": "medium"}),
    ],
)
def test_rejects_malformed_half_hours(body):
    with pytest.raises(intensity.BadResponseError, match="half hour 0"):
        intensity.parse_intensity(body)


def test_null_actual_is_allowed():
    [h] = intensity.parse_intensity(half_hour(intensity={"actual": None}))
    assert h.actual is None


# checking the day


def test_clocks_going_back_gives_50_half_hours_without_a_warning(clocks_back_day, caplog):
    half_hours = intensity.parse_intensity(clocks_back_day.decode())

    intensity.check_day(half_hours, date(2025, 10, 26))

    assert len(half_hours) == 50
    assert warnings(caplog) == []


def test_data_for_another_day_is_rejected(normal_day):
    half_hours = intensity.parse_intensity(normal_day.decode())

    with pytest.raises(intensity.BadResponseError, match="outside"):
        intensity.check_day(half_hours, date(2026, 10, 2))


def test_missing_half_hours_only_warn(normal_day, caplog):
    half_hours = intensity.parse_intensity(normal_day.decode())[:-2]

    intensity.check_day(half_hours, date(2026, 10, 1))

    assert warnings(caplog) == ["Expected 48 half hours for 2026-10-01, got 46 (46 distinct)"]


# extracting a day


@responses.activate
def test_saves_the_response_unchanged(tmp_path, normal_day):
    responses.get(url_for(date(2026, 10, 1)), body=normal_day)

    result = run(date(2026, 10, 1), tmp_path)

    assert result.status == "saved"
    assert (result.half_hours, result.missing_actuals) == (48, 0)
    assert result.path == day_folder(tmp_path, "national_intensity", date(2026, 10, 1)) / (
        "intensity.json"
    )
    assert result.path.read_bytes() == normal_day


@responses.activate
def test_writes_a_manifest(tmp_path, normal_day):
    responses.get(url_for(date(2026, 10, 1)), body=normal_day)

    result = run(date(2026, 10, 1), tmp_path)

    manifest = json.loads((result.path.parent / MANIFEST_NAME).read_text())
    assert manifest["url"] == url_for(date(2026, 10, 1))
    assert manifest["http_status"] == 200
    assert manifest["fetched_at"] == "2026-10-06T09:00:00+00:00"
    assert manifest["half_hours"] == manifest["expected_half_hours"] == 48
    assert manifest["missing_actuals"] == 0


@responses.activate
def test_running_a_day_twice_leaves_one_copy(tmp_path, normal_day):
    responses.get(url_for(date(2026, 10, 1)), body=normal_day)

    run(date(2026, 10, 1), tmp_path)
    run(date(2026, 10, 1), tmp_path)

    folder = day_folder(tmp_path, "national_intensity", date(2026, 10, 1))
    assert sorted(p.name for p in folder.iterdir()) == [MANIFEST_NAME, "intensity.json"]


@responses.activate
def test_unfinished_past_day_is_saved_with_a_warning(tmp_path, unfinished_day, caplog):
    responses.get(url_for(date(2026, 10, 5)), body=unfinished_day)

    result = run(date(2026, 10, 5), tmp_path)

    assert result.status == "saved"
    assert result.missing_actuals == 17
    assert any("Run this day again later" in w for w in warnings(caplog))


@responses.activate
def test_today_without_all_actuals_is_normal(tmp_path, unfinished_day, caplog):
    responses.get(url_for(date(2026, 10, 5)), body=unfinished_day)

    result = run(
        date(2026, 10, 5), tmp_path, now=datetime(2026, 10, 5, 14, 45, tzinfo=timezone.utc)
    )

    assert result.missing_actuals == 17
    assert warnings(caplog) == []


@responses.activate
def test_day_before_the_history_starts(tmp_path, caplog):
    responses.get(url_for(date(2017, 1, 1)), json={"data": []})

    with caplog.at_level(logging.INFO):
        result = run(date(2017, 1, 1), tmp_path)

    assert result.status == "no_data"
    assert not (tmp_path / "national_intensity").exists()
    assert "history starts on 2017-09-12" in caplog.text
    assert warnings(caplog) == []


@responses.activate
def test_empty_day_inside_the_history_warns(tmp_path, caplog):
    responses.get(url_for(date(2026, 10, 1)), json={"data": []})

    assert run(date(2026, 10, 1), tmp_path).status == "no_data"
    assert warnings(caplog) == ["The API returned no data for 2026-10-01"]


@responses.activate
def test_wrong_day_in_the_response_saves_nothing(tmp_path, normal_day):
    responses.get(url_for(date(2026, 10, 2)), body=normal_day)

    with pytest.raises(intensity.BadResponseError):
        run(date(2026, 10, 2), tmp_path)

    assert not (tmp_path / "national_intensity").exists()


@responses.activate
def test_client_error_raises(tmp_path):
    responses.get(url_for(date(2026, 10, 1)), status=400, json={"error": "bad request"})

    with pytest.raises(requests.HTTPError):
        run(date(2026, 10, 1), tmp_path)


@responses.activate
def test_server_error_is_retried(tmp_path, normal_day):
    responses.get(url_for(date(2026, 10, 1)), status=503)
    responses.get(url_for(date(2026, 10, 1)), body=normal_day)

    assert run(date(2026, 10, 1), tmp_path).status == "saved"
    assert len(responses.calls) == 2
