from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    fixture_stage_delay_ms: int
    run_interval_minutes: int
    web_origin: str

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.getenv("CANCERJEV_DATA_DIR", "data")).expanduser().resolve()
        delay = _nonnegative_int("CANCERJEV_FIXTURE_STAGE_DELAY_MS", 500)
        interval = _positive_int("CANCERJEV_RUN_INTERVAL_MINUTES", 60)
        return cls(data_dir, delay, interval, os.getenv("CANCERJEV_WEB_ORIGIN", "http://localhost:3000"))

    @property
    def database_path(self) -> Path:
        return self.data_dir / "cancerjev.db"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / "research.lock"


def _nonnegative_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _positive_int(name: str, default: int) -> int:
    value = _nonnegative_int(name, default)
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value

