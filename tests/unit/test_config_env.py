from __future__ import annotations

import os

from cancerjev.config import load_local_env


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
