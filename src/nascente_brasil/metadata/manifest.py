"""Validation helpers for the ingestion manifest."""

from __future__ import annotations

import csv
import os
from pathlib import Path


MANIFEST_COLUMNS = [
    "source_name",
    "organization",
    "dataset_name",
    "source_url",
    "download_url",
    "reference_period",
    "extraction_date",
    "file_format",
    "file_name",
    "file_size_bytes",
    "checksum",
    "records",
    "schema_version",
    "ingestion_status",
    "processing_status",
    "source_etag",
    "source_last_modified",
]


def read_manifest_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj)
        try:
            return next(reader)
        except StopIteration as exc:
            raise ValueError(f"Manifest is empty: {path}") from exc


def validate_manifest_header(path: Path) -> None:
    header = read_manifest_header(path)
    if header != MANIFEST_COLUMNS:
        raise ValueError(
            "Invalid ingestion manifest header. "
            f"Expected {MANIFEST_COLUMNS}, found {header}."
        )


def read_manifest(path: Path) -> list[dict[str, str]]:
    validate_manifest_header(path)
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def append_manifest(path: Path, row: dict[str, str | int]) -> None:
    validate_manifest_header(path)
    if set(row) != set(MANIFEST_COLUMNS):
        raise ValueError("Manifest row does not match the required columns")
    with path.open("a", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=MANIFEST_COLUMNS)
        writer.writerow(row)
        file_obj.flush()
        os.fsync(file_obj.fileno())
