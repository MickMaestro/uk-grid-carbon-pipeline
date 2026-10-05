"""Saving raw API responses to disk.

Files go in one folder per source per day:

    <raw_root>/<source>/date=YYYY-MM-DD/<filename>
    <raw_root>/<source>/date=YYYY-MM-DD/_manifest.json

The response is saved exactly as it came back. The manifest records where it came from, when it
was fetched and a checksum. Because the path only depends on the source and the day, running the
same day again replaces the files instead of adding another copy.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

MANIFEST_NAME = "_manifest.json"


@dataclass(frozen=True)
class SavedFile:
    path: Path
    manifest_path: Path
    sha256: str
    size_bytes: int


def day_folder(raw_root: Path, source: str, day: date) -> Path:
    return raw_root / source / f"date={day.isoformat()}"


def write_atomically(path: Path, content: bytes) -> None:
    """Write to a temp file next to the target, then swap it into place.

    os.replace is atomic on the same drive, so anyone reading the file sees either the old
    version or the new one, never half of it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save_raw(
    raw_root: Path,
    source: str,
    day: date,
    filename: str,
    content: bytes,
    metadata: dict[str, Any],
) -> SavedFile:
    folder = day_folder(raw_root, source, day)
    path = folder / filename
    manifest_path = folder / MANIFEST_NAME
    sha256 = hashlib.sha256(content).hexdigest()

    manifest = {
        **metadata,
        "source": source,
        "date": day.isoformat(),
        "file": filename,
        "sha256": sha256,
        "size_bytes": len(content),
    }

    # data first, so a manifest never describes a file that isn't there yet
    write_atomically(path, content)
    write_atomically(
        manifest_path, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    )
    return SavedFile(path, manifest_path, sha256, len(content))
