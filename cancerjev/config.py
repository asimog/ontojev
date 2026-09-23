from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

from cancerjev.gdc.transport import BudgetCaps

ENV_LOCAL_FILENAME = ".env.local"

# Documented hard ceilings (docs/GDC_BUDGETS.md). Operational settings may lower
# these but may never raise them; an above-default value is rejected at load time.
_DOCUMENTED_CAPS = BudgetCaps()
GDC_MAX_REQUESTS_HARD_CAP = _DOCUMENTED_CAPS.max_requests
GDC_MAX_BYTES_HARD_CAP = _DOCUMENTED_CAPS.max_bytes
GDC_PER_RESPONSE_BYTES_HARD_CAP = _DOCUMENTED_CAPS.per_response_bytes
GDC_TIMEOUT_SECONDS_HARD_CAP = _DOCUMENTED_CAPS.timeout_seconds
JEV_MAX_STATES_HARD_CAP = 1000
# Documented ceiling for one Jev provider request. Like the GDC socket timeout,
# the default equals the hard cap: operational settings may lower it only.
JEV_TIMEOUT_SECONDS_HARD_CAP = 30.0
# Generated hypothesis text is optional and provider-dependent. The model identity must be
# pinned/versioned (the default is OpenRouter's ``deepseek/deepseek-v4.1-flash``), the credential
# is read from the environment by the provider adapter only, and the ceiling is documented. The
# ceiling is 120 s because a reasoning model spends part of its bounded completion on reasoning
# before returning content (observed live), not because a limit was enlarged to finish work.
LLM_TIMEOUT_SECONDS_HARD_CAP = 120.0
DEFAULT_LLM_MODEL = "deepseek/deepseek-v4.1-flash"


def load_local_env(path: Path | None = None) -> int:
    """Load local development variables from ``.env.local`` (stdlib only).

    Local convenience for keys such as ``TYPESAFE_API_KEY`` and
    ``OPENROUTER_API_KEY``. Values already present in the process environment
    always win, blank values are ignored, and values are never logged or
    persisted. Set ``CANCERJEV_NO_DOTENV=1`` to disable, or
    ``CANCERJEV_ENV_FILE`` to point at another file. Returns the number of
    variables set.
    """
    if os.getenv("CANCERJEV_NO_DOTENV", "").strip().lower() in {"1", "true", "yes"}:
        return 0
    target = path or Path(os.getenv("CANCERJEV_ENV_FILE", ENV_LOCAL_FILENAME))
    if not target.is_absolute():
        target = Path.cwd() / target
    if not target.is_file():
        return 0
    loaded = 0
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not _is_env_name(key) or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not value:
            continue
        os.environ[key] = value
        loaded += 1
    return loaded


def _is_env_name(name: str) -> bool:
    return bool(name) and not name[0].isdigit() and all(char == "_" or char.isalnum() for char in name)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    fixture_stage_delay_ms: int
    run_interval_minutes: int
    web_origin: str
    gdc_max_requests: int = 150
    gdc_max_bytes: int = 64 * 1024 * 1024
    gdc_per_response_bytes: int = 5 * 1024 * 1024
    gdc_timeout_seconds: float = 30.0
    gdc_cache_enabled: bool = True
    jev_model: str = "jev-1.13.0"
    jev_max_states: int = 1000
    jev_timeout_seconds: float = 30.0
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_seconds: float = 120.0

    @classmethod
    def from_env(cls) -> Settings:
        load_local_env()
        data_dir = Path(os.getenv("CANCERJEV_DATA_DIR", "data")).expanduser().resolve()
        delay = _nonnegative_int("CANCERJEV_FIXTURE_STAGE_DELAY_MS", 500)
        interval = _positive_int("CANCERJEV_RUN_INTERVAL_MINUTES", 60)
        return cls(
            data_dir=data_dir,
            fixture_stage_delay_ms=delay,
            run_interval_minutes=interval,
            web_origin=os.getenv("CANCERJEV_WEB_ORIGIN", "http://localhost:3000"),
            gdc_max_requests=_bounded_int("CANCERJEV_GDC_MAX_REQUESTS", 150, GDC_MAX_REQUESTS_HARD_CAP),
            gdc_max_bytes=_bounded_int("CANCERJEV_GDC_MAX_BYTES", 64 * 1024 * 1024, GDC_MAX_BYTES_HARD_CAP),
            gdc_per_response_bytes=_bounded_int(
                "CANCERJEV_GDC_PER_RESPONSE_BYTES", 5 * 1024 * 1024, GDC_PER_RESPONSE_BYTES_HARD_CAP,
            ),
            gdc_timeout_seconds=_bounded_seconds(
                "CANCERJEV_GDC_TIMEOUT_SECONDS", 30.0, GDC_TIMEOUT_SECONDS_HARD_CAP,
            ),
            gdc_cache_enabled=os.getenv("CANCERJEV_GDC_CACHE", "1") not in {"0", "false", "False"},
            jev_model=os.getenv("CANCERJEV_JEV_MODEL", "jev-1.13.0"),
            jev_max_states=_bounded_int("CANCERJEV_JEV_MAX_STATES", 1000, JEV_MAX_STATES_HARD_CAP),
            jev_timeout_seconds=_bounded_seconds(
                "CANCERJEV_JEV_TIMEOUT_SECONDS", 30.0, JEV_TIMEOUT_SECONDS_HARD_CAP,
            ),
            llm_model=os.getenv("CANCERJEV_LLM_MODEL", DEFAULT_LLM_MODEL).strip(),
            llm_timeout_seconds=_bounded_seconds(
                "CANCERJEV_LLM_TIMEOUT_SECONDS", 120.0, LLM_TIMEOUT_SECONDS_HARD_CAP,
            ),
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


def _bounded_int(name: str, default: int, maximum: int) -> int:
    value = _positive_int(name, default)
    if value > maximum:
        raise ValueError(f"{name} must not exceed the documented hard cap {maximum}")
    return value


def _bounded_seconds(name: str, default: float, maximum: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    if value > maximum:
        raise ValueError(f"{name} must not exceed the documented hard cap {maximum}")
    return value

