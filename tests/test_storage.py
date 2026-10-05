import hashlib
import json
from datetime import date

import pytest

from grid_carbon.storage import MANIFEST_NAME, day_folder, save_raw, write_atomically

DAY = date(2026, 10, 1)


def test_day_folder_layout(tmp_path):
    assert day_folder(tmp_path, "national_intensity", DAY) == (
        tmp_path / "national_intensity" / "date=2026-10-01"
    )


def test_saves_bytes_unchanged(tmp_path):
    content = b'{ \r\n  "data": []\r\n}'

    saved = save_raw(tmp_path, "src", DAY, "response.json", content, {})

    assert saved.path.read_bytes() == content
    assert saved.sha256 == hashlib.sha256(content).hexdigest()
    assert saved.size_bytes == len(content)


def test_manifest_contents(tmp_path):
    saved = save_raw(tmp_path, "src", DAY, "response.json", b"x", {"http_status": 200})

    manifest = json.loads(saved.manifest_path.read_text())

    assert saved.manifest_path.name == MANIFEST_NAME
    assert manifest == {
        "date": "2026-10-01",
        "file": "response.json",
        "http_status": 200,
        "sha256": hashlib.sha256(b"x").hexdigest(),
        "size_bytes": 1,
        "source": "src",
    }


def test_saving_the_same_day_twice_replaces_the_file(tmp_path):
    save_raw(tmp_path, "src", DAY, "response.json", b"first", {})
    save_raw(tmp_path, "src", DAY, "response.json", b"second", {})

    folder = day_folder(tmp_path, "src", DAY)
    assert sorted(p.name for p in folder.iterdir()) == [MANIFEST_NAME, "response.json"]
    assert (folder / "response.json").read_bytes() == b"second"


def test_no_temp_files_left_behind(tmp_path):
    target = tmp_path / "a" / "file.bin"

    write_atomically(target, b"data")

    assert [p.name for p in target.parent.iterdir()] == ["file.bin"]


def test_failed_write_keeps_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")

    def fail(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr("grid_carbon.storage.os.replace", fail)

    with pytest.raises(OSError, match="disk full"):
        write_atomically(target, b"new")

    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["file.bin"]
