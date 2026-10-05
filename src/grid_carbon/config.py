from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    raw_data_dir: Path
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            raw_data_dir=Path(os.environ.get("RAW_DATA_DIR", "data/raw")),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )
