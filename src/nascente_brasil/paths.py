"""Canonical project paths used by scripts and tests."""

from __future__ import annotations

from pathlib import Path

from nascente_brasil.config import get_settings


DATA_SOURCES = ("sinasc", "cnes", "sih", "sim", "sinan", "ibge")


def required_directories() -> list[Path]:
    settings = get_settings()
    root = settings.root_dir

    directories = [
        root / "data",
        root / "data" / "metadata",
        root / "data" / "quarantine",
        root / "data" / "reference" / "cid",
        root / "data" / "reference" / "ibge",
        root / "logs",
        root / "tests",
        root / "scripts",
        root / "docs" / "architecture",
        root / "docs" / "methodology",
        root / "docs" / "data_dictionary",
        root / "docs" / "data_quality",
        root / "docs" / "sources",
        root / "docs" / "lineage",
        root / "docs" / "checkpoints",
        root / "airflow" / "dags",
        root / "dbt",
        root / "sql" / "duckdb",
        root / "sql" / "postgres",
        root / "api",
        root / "dashboard",
        root / "notebooks",
        root / "docker",
    ]

    for source in DATA_SOURCES:
        directories.extend(
            [
                root / "data" / "raw" / source / "original",
                root / "data" / "raw" / source / "csv",
                root / "data" / "processed" / source,
            ]
        )

    directories.extend(
        [
            root / "data" / "processed" / "morbidades_maternas",
            root / "data" / "gold" / "nacional",
            root / "data" / "gold" / "regional",
            root / "data" / "gold" / "estadual",
            root / "data" / "gold" / "municipal",
            root / "data" / "gold" / "morbidades",
        ]
    )

    return directories
