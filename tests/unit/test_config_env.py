from __future__ import annotations

import os

import pytest

from cancerjev.config import (
    DEFAULT_LLM_MODEL,
    JEV_TIMEOUT_SECONDS_HARD_CAP,
    LLM_TIMEOUT_SECONDS_HARD_CAP,
    Settings,
    load_local_env,
)


def test_loads_values_and_ignores_comments_blanks_and_invalid_names(tmp_path, monkeypatch):
    for name in ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "CANCERJEV_JEV_MODEL", "EMPTY", "INVALID-NAME"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "# local secrets\n\n"
        "TYPESAFE_API_KEY=ts-secret\n"
        "OPENROUTER_API_KEY='or-secret'\n"
        'export CANCERJEV_JEV_MODEL="jev-1.13.0"\n'
        "EMPTY=\n"
        "INVALID-NAME=x\n",
        encoding="utf-8",
    )
    assert load_local_env(env_file) == 3
    assert os.environ["TYPESAFE_API_KEY"] == "ts-secret"
    assert os.environ["OPENROUTER_API_KEY"] == "or-secret"
    assert os.environ["CANCERJEV_JEV_MODEL"] == "jev-1.13.0"
    assert "EMPTY" not in os.environ
    assert "INVALID-NAME" not in os.environ


def test_existing_environment_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-env")
    env_file = tmp_path / ".env.local"
    env_file.write_text("TYPESAFE_API_KEY=file-value\n", encoding="utf-8")
    assert load_local_env(env_file) == 0
    assert os.environ["TYPESAFE_API_KEY"] == "real-env"


def test_missing_file_and_opt_out_are_inert(tmp_path, monkeypatch):
    assert load_local_env(tmp_path / "absent.env") == 0
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text("OPENROUTER_API_KEY=or-value\n", encoding="utf-8")
    assert load_local_env(env_file) == 0
    assert "OPENROUTER_API_KEY" not in os.environ


def test_above_hard_cap_settings_are_rejected(monkeypatch):
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_GDC_MAX_REQUESTS", "151")
    with pytest.raises(ValueError):
        Settings.from_env()
    monkeypatch.setenv("CANCERJEV_JEV_TIMEOUT_SECONDS", str(JEV_TIMEOUT_SECONDS_HARD_CAP + 1))
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize("value", ["nan", "0", "-0.5"])
def test_impossible_jev_timeouts_are_rejected(monkeypatch, value):
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_JEV_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_lowered_caps_and_timeouts_are_accepted_and_effective(monkeypatch):
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_JEV_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("CANCERJEV_GDC_MAX_REQUESTS", "10")
    monkeypatch.setenv("CANCERJEV_GDC_PER_RESPONSE_BYTES", "1024")
    monkeypatch.setenv("CANCERJEV_JEV_MAX_STATES", "2")
    settings = Settings.from_env()
    assert settings.jev_timeout_seconds == 12.5
    assert settings.gdc_max_requests == 10
    assert settings.gdc_per_response_bytes == 1024
    assert settings.jev_max_states == 2


def test_llm_settings_exist_without_holding_credentials(monkeypatch):
    """Generated text is an opt-in provider: model and timeout are settings, the key is not."""
    import dataclasses

    names = {field.name for field in dataclasses.fields(Settings)}
    assert {"llm_model", "llm_timeout_seconds"} <= names
    assert not {name for name in names
                if "key" in name.lower() or "token" in name.lower() or "credential" in name.lower()}
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    assert Settings.from_env().llm_model == DEFAULT_LLM_MODEL
    monkeypatch.setenv("CANCERJEV_LLM_MODEL", "deepseek/deepseek-v4.1-flash")
    assert Settings.from_env().llm_model == "deepseek/deepseek-v4.1-flash"
    monkeypatch.setenv("CANCERJEV_LLM_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError):
        Settings.from_env()
    monkeypatch.setenv("CANCERJEV_LLM_TIMEOUT_SECONDS", str(LLM_TIMEOUT_SECONDS_HARD_CAP + 1))
    with pytest.raises(ValueError):
        Settings.from_env()
