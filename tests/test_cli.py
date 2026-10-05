from datetime import date

import pytest
import responses

from grid_carbon import cli
from grid_carbon.extractors import intensity


def url_for(day):
    return f"{intensity.BASE_URL}/intensity/date/{day}"


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr("grid_carbon.http_client.time.sleep", lambda _: None)


@responses.activate
def test_fetches_the_given_day(tmp_path, normal_day):
    responses.get(url_for("2026-10-01"), body=normal_day)

    assert cli.main(["intensity", "--date", "2026-10-01", "--raw-dir", str(tmp_path)]) == 0
    assert (tmp_path / "national_intensity" / "date=2026-10-01" / "intensity.json").exists()


@responses.activate
def test_defaults_to_yesterday(tmp_path, normal_day, monkeypatch):
    monkeypatch.setattr(cli, "uk_today", lambda: date(2026, 10, 2))
    responses.get(url_for("2026-10-01"), body=normal_day)

    assert cli.main(["intensity", "--raw-dir", str(tmp_path)]) == 0


@responses.activate
def test_raw_dir_comes_from_the_environment(tmp_path, normal_day, monkeypatch):
    monkeypatch.setenv("RAW_DATA_DIR", str(tmp_path / "from_env"))
    responses.get(url_for("2026-10-01"), body=normal_day)

    assert cli.main(["intensity", "--date", "2026-10-01"]) == 0
    assert (tmp_path / "from_env" / "national_intensity" / "date=2026-10-01").is_dir()


@responses.activate
def test_failure_exits_with_1(tmp_path, caplog):
    responses.get(url_for("2026-10-01"), status=400, body="bad request")

    assert cli.main(["intensity", "--date", "2026-10-01", "--raw-dir", str(tmp_path)]) == 1
    assert "Couldn't fetch" in caplog.text


def test_bad_date_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["intensity", "--date", "01/10/2026"])

    assert exc.value.code == 2
    assert "expected a date like" in capsys.readouterr().err
