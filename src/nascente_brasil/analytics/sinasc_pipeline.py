"""Publish versioned Phase 4 indicator artifacts after reconciliation."""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import json
from pathlib import Path

from nascente_brasil.analytics.sinasc import analyze, export_csv, query_paths
from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


PIPELINE_VERSION = "phase4-v1"


def _artifact(path: Path, root: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def _inputs(settings: Settings) -> tuple[dict, Path, Path, Path]:
    reports = sorted(settings.metadata_dir.glob("sinasc_2024_*_processing.json"))
    if len(reports) != 1:
        raise ValueError("Expected one validated SINASC 2024 Phase 3 report")
    phase3 = json.loads(reports[0].read_text(encoding="utf-8"))
    csv_item = phase3["silver"]["csv"]
    parquet_item = phase3["silver"]["parquet"]
    csv_path = settings.root_dir / csv_item["path"]
    parquet_path = settings.root_dir / parquet_item["path"]
    for path, item in ((csv_path, csv_item), (parquet_path, parquet_item)):
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Phase 3 input differs from metadata: {path}")
    return phase3, reports[0], csv_path, parquet_path


def _verify_outputs(report: dict, settings: Settings) -> bool:
    existing = [settings.root_dir / item["path"] for item in report["outputs"].values()]
    if not all(path.exists() for path in existing):
        for item in report["outputs"].values():
            path = settings.root_dir / item["path"]
            if path.exists() and _artifact(path, settings.root_dir) != item:
                raise ValueError(f"Phase 4 output changed: {path}")
        return False
    for item in report["outputs"].values():
        path = settings.root_dir / item["path"]
        if _artifact(path, settings.root_dir) != item:
            raise ValueError(f"Phase 4 output changed: {path}")
    return True


def run_phase_4(settings: Settings | None = None, *, sample_size: int = 1000) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    phase3, processing_path, csv_path, parquet_path = _inputs(settings)
    short_hash = phase3["raw_sha256"][:12]
    report_path = settings.metadata_dir / f"sinasc_2024_{short_hash}_indicators.json"
    paths = query_paths(settings.root_dir)
    sql_checksums = {name: sha256_file(path) for name, path in paths.items()}
    if report_path.exists():
        old = json.loads(report_path.read_text(encoding="utf-8"))
        if (old.get("pipeline_version") == PIPELINE_VERSION
                and old.get("source_parquet_sha256") == phase3["silver"]["parquet"]["sha256"]
                and old.get("source_csv_sha256") == phase3["silver"]["csv"]["sha256"]
                and old.get("sql_sha256") == sql_checksums
                and old.get("sample_size") == sample_size
                and _verify_outputs(old, settings)):
            return old, False
    result = analyze(parquet_path, csv_path, paths, expected_rows=phase3["rows"], sample_size=sample_size)
    output_dir = settings.data_dir / "processed" / "sinasc" / "analytics"
    outputs = {}
    for name in ("national", "monthly", "sex"):
        path = output_dir / f"sinasc_2024_{short_hash}_{name}.csv"
        rows = result[name] if isinstance(result[name], list) else [result[name]]
        export_csv(path, rows)
        outputs[name] = _artifact(path, settings.root_dir)
    report = {
        "pipeline_version": PIPELINE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase3_report": processing_path.relative_to(settings.root_dir).as_posix(),
        "source_parquet_sha256": phase3["silver"]["parquet"]["sha256"],
        "source_csv_sha256": phase3["silver"]["csv"]["sha256"],
        "sql_sha256": sql_checksums,
        "sample_size": sample_size,
        "national": result["national"],
        "monthly_groups": len(result["monthly"]),
        "sex_groups": len(result["sex"]),
        "reconciliation": result["reconciliation"],
        "outputs": outputs,
    }
    _write_json_atomic(report_path, report)
    return report, True


def validate_phase_4(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    phase3, _, csv_path, parquet_path = _inputs(settings)
    short_hash = phase3["raw_sha256"][:12]
    report_path = settings.metadata_dir / f"sinasc_2024_{short_hash}_indicators.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report["pipeline_version"] != PIPELINE_VERSION
            or report["source_parquet_sha256"] != phase3["silver"]["parquet"]["sha256"]
            or report["source_csv_sha256"] != phase3["silver"]["csv"]["sha256"]
            or report["sql_sha256"] != {name: sha256_file(path) for name, path in query_paths(settings.root_dir).items()}
            or not _verify_outputs(report, settings)):
        raise ValueError("Phase 4 metadata, SQL or outputs differ")
    result = analyze(parquet_path, csv_path, query_paths(settings.root_dir),
                     expected_rows=phase3["rows"], sample_size=report["sample_size"])
    if (result["national"] != report["national"]
            or result["reconciliation"] != report["reconciliation"]
            or len(result["monthly"]) != report["monthly_groups"]
            or len(result["sex"]) != report["sex_groups"]):
        raise ValueError("Phase 4 indicators differ from metadata")
    for name, item in report["outputs"].items():
        expected = result[name] if isinstance(result[name], list) else [result[name]]
        with (settings.root_dir / item["path"]).open("r", encoding="utf-8", newline="") as file_obj:
            actual = list(csv.DictReader(file_obj))
        normalized = [
            {key: value.isoformat() if hasattr(value, "isoformat") else "" if value is None else str(value)
             for key, value in row.items()}
            for row in expected
        ]
        if actual != normalized:
            raise ValueError(f"Phase 4 {name} CSV differs from query")
    return report
