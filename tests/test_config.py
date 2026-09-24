from __future__ import annotations

import json
from importlib.metadata import version

import pytest

from nascente_brasil import config

from nascente_brasil import Settings, get_settings
from nascente_brasil.logging_config import configure_logging, get_logger


def test_package_imports_settings() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.project_name == "NASCENTE BRASIL"
    assert settings.root_dir.name == "nascente-brasil"
    assert version("nascente-brasil") == "0.1.0"


def test_dotenv_values_and_environment_precedence(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "NASCENTE_PROJECT_NAME=From File\nNASCENTE_TIMEZONE=UTC\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "_project_root", lambda: tmp_path)
    monkeypatch.setenv("NASCENTE_PROJECT_NAME", "From Environment")
    monkeypatch.delenv("NASCENTE_TIMEZONE", raising=False)

    settings = config.Settings.from_env()

    assert settings.project_name == "From Environment"
    assert settings.timezone == "UTC"


def test_settings_validate_current_project() -> None:
    settings = get_settings()
    settings.validate()
    assert settings.manifest_path.exists()


def test_postgres_dsn_is_required_outside_explicit_local_mode() -> None:
    with pytest.raises(config.ConfigurationError):
        config.get_postgres_dsn({"NASCENTE_ENV": "production"})
    with pytest.raises(config.ConfigurationError):
        config.get_postgres_dsn({})


def test_postgres_dsn_preserves_managed_ssl_configuration() -> None:
    dsn = "postgresql://user:encoded%40password@db.example.com:5432/nascente?sslmode=require"
    assert config.get_postgres_dsn({"NASCENTE_POSTGRES_DSN": dsn}) == dsn


def test_structured_logging_writes_json_line() -> None:
    settings = get_settings()
    log_path = configure_logging(settings)
    logger = get_logger("test")

    logger.info(
        "logging test event",
        extra={
            "run_id": "test-run",
            "pipeline": "phase_1_foundation",
            "task": "test_logging",
            "status": "success",
        },
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["message"] == "logging test event"
    assert payload["pipeline"] == "phase_1_foundation"
    assert payload["status"] == "success"
