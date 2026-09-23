"""Structured logging utilities for pipelines and validation scripts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging import Logger
from pathlib import Path
from typing import Any

from nascente_brasil.config import Settings, get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in (
            "run_id",
            "pipeline",
            "task",
            "source",
            "file",
            "rows_in",
            "rows_out",
            "rows_invalid",
            "status",
            "error",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.log_dir / "nascente_brasil.log"

    logger = logging.getLogger("nascente_brasil")
    logger.setLevel(settings.log_level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    return log_path


def get_logger(name: str) -> Logger:
    return logging.getLogger(f"nascente_brasil.{name}")
