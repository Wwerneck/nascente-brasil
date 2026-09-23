"""Independent validation of manifested SINASC CSV and Silver outputs."""

from __future__ import annotations

import csv
import json

import pyarrow.parquet as pq

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.conversion.sinasc import OUTPUT_COLUMNS, verify_converted_csv
from nascente_brasil.ingestion.sinasc import DOWNLOAD_URL, YEAR, sha256_file
from nascente_brasil.metadata.manifest import read_manifest
from nascente_brasil.transformation.sinasc import ARROW_SCHEMA
from nascente_brasil.transformation.sinasc_pipeline import PIPELINE_VERSION


def validate_phase_3(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    source_rows = [
        row for row in read_manifest(settings.manifest_path)
        if row["source_name"] == "SINASC"
        and row["reference_period"] == YEAR
        and row["download_url"] == DOWNLOAD_URL
        and row["ingestion_status"] == "success"
    ]
    if not source_rows:
        raise ValueError("SINASC 2024 RAW record is absent")
    source = source_rows[-1]
    raw_zip = settings.data_dir / "raw" / "sinasc" / "original" / source["file_name"]
    if sha256_file(raw_zip) != source["checksum"]:
        raise ValueError("SINASC RAW checksum differs from manifest")

    short_hash = source["checksum"][:12]
    report_path = settings.metadata_dir / f"sinasc_2024_{short_hash}_processing.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected_rows = int(source["records"])
    if report["pipeline_version"] != PIPELINE_VERSION or report["rows"] != expected_rows:
        raise ValueError("SINASC processing metadata version or row count differs")

    raw_csv = report["raw_csv"]
    verified_raw = verify_converted_csv(settings.root_dir / raw_csv["path"], expected_rows)
    if verified_raw["sha256"] != raw_csv["sha256"] or verified_raw["bytes"] != raw_csv["bytes"]:
        raise ValueError("Converted SINASC CSV does not match metadata")

    silver_csv = report["silver"]["csv"]
    with (settings.root_dir / silver_csv["path"]).open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj, strict=True)
        if tuple(next(reader)) != OUTPUT_COLUMNS:
            raise ValueError("SINASC Silver CSV header differs from schema")
        silver_rows = sum(1 for row in reader if len(row) == len(OUTPUT_COLUMNS))
    if silver_rows != expected_rows or sha256_file(settings.root_dir / silver_csv["path"]) != silver_csv["sha256"]:
        raise ValueError("SINASC Silver CSV differs from metadata")

    silver_parquet = report["silver"]["parquet"]
    parquet_path = settings.root_dir / silver_parquet["path"]
    parquet_file = pq.ParquetFile(parquet_path)
    if parquet_file.metadata.num_rows != expected_rows or not parquet_file.schema_arrow.equals(ARROW_SCHEMA, check_metadata=False):
        raise ValueError("SINASC Silver Parquet count or schema differs")
    if sha256_file(parquet_path) != silver_parquet["sha256"]:
        raise ValueError("SINASC Silver Parquet checksum differs")
    return report
