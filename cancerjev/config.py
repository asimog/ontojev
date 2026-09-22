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
    gdc_max_requests: int = 150
    gdc_max_bytes: int = 64 * 1024 * 1024
    gdc_per_response_bytes: int = 8 * 1024 * 1024
    gdc_timeout_seconds: float = 30.0
    gdc_cache_enabled: bool = True
    jev_model: str = "jev-1.13.0"
    jev_max_states: int = 1000
    jev_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.getenv("CANCERJEV_DATA_DIR", "data")).expanduser().resolve()
        delay = _nonnegative_int("CANCERJEV_FIXTURE_STAGE_DELAY_MS", 500)
        interval = _positive_int("CANCERJEV_RUN_INTERVAL_MINUTES", 60)
        return cls(
            data_dir=data_dir,
            fixture_stage_delay_ms=delay,
            run_interval_minutes=interval,
            web_origin=os.getenv("CANCERJEV_WEB_ORIGIN", "http://localhost:3000"),
            gdc_max_requests=_positive_int("CANCERJEV_GDC_MAX_REQUESTS", 150),
            gdc_max_bytes=_positive_int("CANCERJEV_GDC_MAX_BYTES", 64 * 1024 * 1024),
            gdc_per_response_bytes=_positive_int("CANCERJEV_GDC_PER_RESPONSE_BYTES", 8 * 1024 * 1024),
            gdc_timeout_seconds=float(os.getenv("CANCERJEV_GDC_TIMEOUT_SECONDS", "30")),
            gdc_cache_enabled=os.getenv("CANCERJEV_GDC_CACHE", "1") not in {"0", "false", "False"},
            jev_model=os.getenv("CANCERJEV_JEV_MODEL", "jev-1.13.0"),
            jev_max_states=_positive_int("CANCERJEV_JEV_MAX_STATES", 1000),
            jev_timeout_seconds=float(os.getenv("CANCERJEV_JEV_TIMEOUT_SECONDS", "30")),
        )

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

