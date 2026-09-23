"""Project configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import dotenv_values


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    project_name: str
    environment: str
    root_dir: Path
    data_dir: Path
    metadata_dir: Path
    manifest_path: Path
    log_dir: Path
    log_level: str
    timezone: str

    @classmethod
    def from_env(cls) -> "Settings":
        root_dir = _project_root()
        file_values = dotenv_values(root_dir / ".env")

        def value(name: str, default: str) -> str:
            return os.environ.get(name) or file_values.get(name) or default

        data_dir = root_dir / value("NASCENTE_DATA_DIR", "data")
        metadata_dir = root_dir / value("NASCENTE_METADATA_DIR", "data/metadata")
        log_dir = root_dir / value("NASCENTE_LOG_DIR", "logs")
        manifest_path = root_dir / value(
            "NASCENTE_MANIFEST_PATH", "data/metadata/ingestion_manifest.csv"
        )

        return cls(
            project_name=value("NASCENTE_PROJECT_NAME", "NASCENTE BRASIL"),
            environment=value("NASCENTE_ENV", "local"),
            root_dir=root_dir,
            data_dir=data_dir,
            metadata_dir=metadata_dir,
            manifest_path=manifest_path,
            log_dir=log_dir,
            log_level=value("NASCENTE_LOG_LEVEL", "INFO").upper(),
            timezone=value("NASCENTE_TIMEZONE", "America/Sao_Paulo"),
        )

    def validate(self) -> None:
        missing = [
            path
            for path in (self.root_dir, self.data_dir, self.metadata_dir, self.log_dir)
            if not path.exists()
        ]
        if missing:
            formatted = ", ".join(str(path) for path in missing)
            raise FileNotFoundError(f"Required project paths are missing: {formatted}")

        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Ingestion manifest not found: {self.manifest_path}")


def get_settings() -> Settings:
    return Settings.from_env()
