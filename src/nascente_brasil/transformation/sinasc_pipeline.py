"""Reproducible SINASC 2024 conversion and Silver build."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

import pyarrow.parquet as pq

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.conversion.sinasc import (
    convert_zip_to_csv, verify_converted_csv,
)
from nascente_brasil.ingestion.sinasc import DOWNLOAD_URL, YEAR, sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import read_manifest
from nascente_brasil.transformation.sinasc import transform_silver

PIPELINE_VERSION = "phase3-v3"


def _write_json_atomic(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".part", delete=False
        ) as file_obj:
            temp = Path(file_obj.name)
            json.dump(content, file_obj, ensure_ascii=False, indent=2)
            file_obj.write("\n")
        os.replace(temp, path)
        temp = None
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def _verify_artifact(item: dict, root: Path) -> None:
    path = root / item["path"]
    if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
        raise ValueError(f"Processed SINASC artifact is missing or changed: {path}")


def _relative_artifact(item: dict, root: Path) -> dict:
    path = Path(item["path"])
    relative = path.relative_to(root) if path.is_absolute() else path
    return {**item, "path": relative.as_posix()}


def process_sinasc_2024(settings: Settings | None = None, *, chunk_rows: int = 50_000) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    logger = get_logger("transformation.sinasc")
    rows = [
        row for row in read_manifest(settings.manifest_path)
        if row["source_name"] == "SINASC"
        and row["reference_period"] == YEAR
        and row["download_url"] == DOWNLOAD_URL
        and row["ingestion_status"] == "success"
    ]
    if not rows:
        raise ValueError("No validated SINASC 2024 RAW file in manifest")
    source = rows[-1]
    source_zip = settings.data_dir / "raw" / "sinasc" / "original" / source["file_name"]
    if not source_zip.is_file() or sha256_file(source_zip) != source["checksum"]:
        raise ValueError("SINASC RAW ZIP does not match its manifest checksum")
    expected_rows = int(source["records"])
    short_hash = source["checksum"][:12]
    raw_csv = settings.data_dir / "raw" / "sinasc" / "csv" / f"sinasc_2024_{short_hash}.csv"
    silver_csv = settings.data_dir / "processed" / "sinasc" / f"sinasc_2024_{short_hash}_silver.csv"
    silver_parquet = settings.data_dir / "processed" / "sinasc" / f"sinasc_2024_{short_hash}_silver.parquet"
    report_path = settings.metadata_dir / f"sinasc_2024_{short_hash}_processing.json"

    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["raw_sha256"] != source["checksum"] or report["rows"] != expected_rows:
            raise ValueError("SINASC processing metadata conflicts with RAW manifest")
        if report.get("pipeline_version") in {"phase3-v2", PIPELINE_VERSION}:
            artifacts = (report["raw_csv"], report["silver"]["csv"], report["silver"]["parquet"])
            if all((settings.root_dir / item["path"]).exists() for item in artifacts):
                for item in artifacts:
                    _verify_artifact(item, settings.root_dir)
                parquet_path = settings.root_dir / report["silver"]["parquet"]["path"]
                if pq.ParquetFile(parquet_path).metadata.num_rows != expected_rows:
                    raise ValueError("SINASC Silver Parquet row count differs")
                if report.get("pipeline_version") != PIPELINE_VERSION or any(
                    Path(item["path"]).is_absolute() for item in artifacts
                ):
                    report["raw_csv"] = _relative_artifact(report["raw_csv"], settings.root_dir)
                    report["silver"]["csv"] = _relative_artifact(report["silver"]["csv"], settings.root_dir)
                    report["silver"]["parquet"] = _relative_artifact(report["silver"]["parquet"], settings.root_dir)
                    report["raw_zip"] = source_zip.relative_to(settings.root_dir).as_posix()
                    report["pipeline_version"] = PIPELINE_VERSION
                    _write_json_atomic(report_path, report)
                logger.info("SINASC Silver already current", extra={"pipeline": "sinasc_silver", "status": "skipped"})
                return report, False
            for item in artifacts:
                if (settings.root_dir / item["path"]).exists():
                    _verify_artifact(item, settings.root_dir)

    try:
        if raw_csv.exists():
            converted = verify_converted_csv(raw_csv, expected_rows)
        else:
            converted = convert_zip_to_csv(source_zip, raw_csv, expected_rows)
    except ValueError as exc:
        if "schema drift" in str(exc):
            _write_json_atomic(
                settings.metadata_dir / f"sinasc_2024_{short_hash}_schema_drift.json",
                {"raw_sha256": source["checksum"], "detected_at": datetime.now(timezone.utc).isoformat(), "error": str(exc)},
            )
        raise

    silver = transform_silver(raw_csv, silver_csv, silver_parquet, expected_rows, chunk_rows=chunk_rows)
    report = {
        "source": source["source_url"],
        "pipeline_version": PIPELINE_VERSION,
        "raw_zip": source_zip.relative_to(settings.root_dir).as_posix(),
        "raw_sha256": source["checksum"],
        "reference_period": YEAR,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "rows": expected_rows,
        "raw_csv": _relative_artifact(converted, settings.root_dir),
        "silver": {
            **silver,
            "csv": _relative_artifact(silver["csv"], settings.root_dir),
            "parquet": _relative_artifact(silver["parquet"], settings.root_dir),
        },
    }
    _write_json_atomic(report_path, report)
    logger.info(
        "SINASC Silver validated",
        extra={"pipeline": "sinasc_silver", "task": "convert_transform", "source": "SINASC", "file": str(silver_csv), "rows_in": expected_rows, "rows_out": silver["rows"], "rows_invalid": sum(silver["quality"]["invalid_numeric"].values()), "status": "success"},
    )
    return report, True
