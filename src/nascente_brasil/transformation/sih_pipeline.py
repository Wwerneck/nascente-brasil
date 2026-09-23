"""Partitioned national SIH/SUS 2024 processing and reconciliation."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import csv
import gzip
import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.conversion.sih import SILVER_SCHEMA, convert_partition
from nascente_brasil.ingestion.sih import DOCUMENT_FILE, EXPECTED_FIELDS, EXPECTED_FILES, ingest_sih_2024, validate_dbc
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import read_manifest
from nascente_brasil.transformation.cnes_pipeline import _atomic_dataframe
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


PIPELINE_VERSION = "phase7-v1"


def _relative(item: dict, root: Path) -> dict:
    path = Path(item["path"])
    return {**item, "path": path.relative_to(root).as_posix()}


def _verify_artifact(item: dict, root: Path, *, parquet: bool = False) -> bool:
    path = root / item["path"]
    if not path.exists():
        return False
    if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
        raise ValueError(f"SIH processed artifact changed: {path}")
    if parquet and pq.ParquetFile(path).metadata.num_rows != item["rows"]:
        raise ValueError(f"SIH Parquet row count changed: {path}")
    return True


def _geography(path: Path) -> dict[str, str]:
    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    if frame["codigo_sinasc_6"].duplicated().any():
        raise ValueError("IBGE six-digit keys are duplicated")
    return dict(zip(frame["codigo_sinasc_6"], frame["codigo_ibge"]))


def _partition_paths(settings: Settings, name: str) -> tuple[Path, Path]:
    uf, competence = name[2:4], f"20{name[4:8]}"
    raw_csv = settings.data_dir / "raw" / "sih" / "csv" / f"uf={uf}" / f"competencia={competence}" / name.replace(".dbc", ".csv.gz")
    parquet = settings.data_dir / "processed" / "sih" / "silver" / f"uf={uf}" / f"competencia={competence}" / name.replace(".dbc", ".parquet")
    return raw_csv, parquet


def _partition_current(item: dict, raw: dict, geography_sha: str, settings: Settings) -> bool:
    return (item.get("pipeline_version") == PIPELINE_VERSION
            and item.get("source_sha256") == raw["sha256"]
            and item.get("geography_sha256") == geography_sha
            and item.get("rows") == raw["records"]
            and _verify_artifact(item["raw_csv"], settings.root_dir)
            and _verify_artifact(item["silver_parquet"], settings.root_dir, parquet=True))


def _query_summary(parquet_glob: str, expected_rows: int, expected_files: int) -> dict:
    with duckdb.connect() as connection:
        parquet_literal = parquet_glob.replace("'", "''")
        connection.execute(f"CREATE VIEW sih AS SELECT * FROM read_parquet('{parquet_literal}')")
        national = connection.execute("""
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT arquivo_fonte) AS files,
                   COUNT(DISTINCT competencia) AS competencies,
                   COUNT(DISTINCT numero_aih) AS distinct_aih_numbers,
                   COUNT(*) FILTER (WHERE tipo_aih = '1') AS type_1_rows,
                   COUNT(*) FILTER (WHERE tipo_aih = '5') AS type_5_rows,
                   COUNT(*) FILTER (WHERE tipo_aih NOT IN ('1', '5') OR tipo_aih IS NULL) AS other_type_rows,
                   COUNT(*) FILTER (WHERE diagnostico_principal IS NULL) AS missing_primary_diagnosis,
                   COUNT(*) FILTER (WHERE diagnostico_secundario IS NOT NULL
                       OR diagnostico_secundario_1 IS NOT NULL OR diagnostico_secundario_2 IS NOT NULL
                       OR diagnostico_secundario_3 IS NOT NULL OR diagnostico_secundario_4 IS NOT NULL
                       OR diagnostico_secundario_5 IS NOT NULL OR diagnostico_secundario_6 IS NOT NULL
                       OR diagnostico_secundario_7 IS NOT NULL OR diagnostico_secundario_8 IS NOT NULL
                       OR diagnostico_secundario_9 IS NOT NULL) AS rows_with_secondary_diagnosis,
                   COUNT(*) FILTER (WHERE codigo_municipio_residencia IS NOT NULL AND codigo_ibge_residencia IS NULL) AS unmatched_residence,
                   COUNT(*) FILTER (WHERE codigo_municipio_estabelecimento IS NOT NULL AND codigo_ibge_estabelecimento IS NULL) AS unmatched_establishment,
                   SUM(dias_permanencia) AS stay_days,
                   SUM(valor_total) AS total_value
            FROM sih
        """).fetchone()
        columns = [item[0] for item in connection.description]
        summary = dict(zip(columns, national))
        if summary["rows"] != expected_rows or summary["files"] != expected_files or summary["competencies"] != 12:
            raise ValueError(f"SIH national reconciliation failed: {summary}")
        duplicate_partition_keys = connection.execute("""
            SELECT COUNT(*) FROM (
                SELECT arquivo_fonte, numero_aih FROM sih GROUP BY 1, 2 HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        result = connection.execute("""
            SELECT competencia, COUNT(*) AS registros, COUNT(DISTINCT numero_aih) AS aih_distintas,
                   SUM(dias_permanencia) AS dias_permanencia, SUM(valor_total) AS valor_total
            FROM sih GROUP BY 1 ORDER BY 1
        """)
        by_competence = pd.DataFrame(result.fetchall(), columns=[column[0] for column in result.description])
        result = connection.execute("""
            SELECT arquivo_fonte, uf_arquivo, competencia, COUNT(*) AS registros,
                   COUNT(DISTINCT numero_aih) AS aih_distintas
            FROM sih GROUP BY 1, 2, 3 ORDER BY 1
        """)
        by_file = pd.DataFrame(result.fetchall(), columns=[column[0] for column in result.description])
    summary["total_value"] = str(summary["total_value"])
    summary["duplicate_aih_keys_within_partition"] = duplicate_partition_keys
    return {"national": summary, "by_competence": by_competence, "by_file": by_file}


def _cnes_audit(sih_glob: str, capacity_path: Path, sql_path: Path) -> list[dict]:
    with duckdb.connect() as connection:
        sih_literal = sih_glob.replace("'", "''")
        capacity_literal = capacity_path.as_posix().replace("'", "''")
        connection.execute(f"CREATE VIEW sih AS SELECT * FROM read_parquet('{sih_literal}')")
        connection.execute(f"CREATE VIEW capacidade AS SELECT competencia, codigo_cnes FROM read_parquet('{capacity_literal}')")
        result = connection.execute(sql_path.read_text(encoding="utf-8"))
        columns = [item[0] for item in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]


def run_phase_7(settings: Settings | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    logger = get_logger("transformation.sih")
    raw, raw_built = ingest_sih_2024(settings)
    documentation_path = settings.data_dir / "raw" / "sih" / "original" / DOCUMENT_FILE
    documentation_sha = sha256_file(documentation_path)
    geography_path = settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv"
    geography_sha = sha256_file(geography_path)
    geography = _geography(geography_path)
    state_path = settings.metadata_dir / "sih_2024_processing_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"partitions": {}}
    built = raw_built
    pending = []
    for name in EXPECTED_FILES:
        item = state["partitions"].get(name)
        if item and _partition_current(item, raw[name], geography_sha, settings):
            continue
        csv_path, parquet_path = _partition_paths(settings, name)
        pending.append((name, csv_path, parquet_path))
    if pending:
        workers = min(8, os.cpu_count() or 1, len(pending))
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(convert_partition, raw[name]["path"], csv_path, parquet_path, geography): name
                       for name, csv_path, parquet_path in pending}
            for completed, future in enumerate(as_completed(futures), start=1):
                name = futures[future]
                result = future.result()
                result["raw_csv"] = {**_relative(result["raw_csv"], settings.root_dir), "rows": result["rows"]}
                result["silver_parquet"] = {**_relative(result["silver_parquet"], settings.root_dir), "rows": result["rows"]}
                state["partitions"][name] = {"pipeline_version": PIPELINE_VERSION,
                    "source_sha256": raw[name]["sha256"], "geography_sha256": geography_sha, **result}
                state["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_json_atomic(state_path, state)
                built = True
                if completed % 20 == 0 or completed == len(pending):
                    logger.info("SIH processing progress", extra={"pipeline": "sih_2024", "task": "convert_partition",
                        "source": "SIH", "file": name,
                        "rows_in": sum(item["rows"] for item in state["partitions"].values()),
                        "rows_out": len(state["partitions"]), "status": "running"})
    if set(state["partitions"]) != set(EXPECTED_FILES):
        raise ValueError("SIH partition processing is incomplete")
    expected_rows = sum(raw[name]["records"] for name in EXPECTED_FILES)
    parquet_root = settings.data_dir / "processed" / "sih" / "silver"
    parquet_glob = (parquet_root / "**" / "*.parquet").as_posix()
    summary = _query_summary(parquet_glob, expected_rows, len(EXPECTED_FILES))
    capacity_path = settings.data_dir / "processed" / "cnes" / "fact_capacidade_hospitalar_2024.parquet"
    cnes_sql = settings.root_dir / "sql" / "duckdb" / "sih_2024_cnes_temporal_join.sql"
    cnes_audit = _cnes_audit(parquet_glob, capacity_path, cnes_sql)
    if sum(item["registros"] for item in cnes_audit) != expected_rows:
        raise ValueError("SIH/CNES temporal join does not reconcile")
    analytics_dir = settings.data_dir / "processed" / "sih" / "analytics"
    competence_path = analytics_dir / "sih_2024_by_competence.csv"
    files_path = analytics_dir / "sih_2024_by_partition.csv"
    cnes_path = analytics_dir / "sih_2024_cnes_temporal_audit.csv"
    _atomic_dataframe(summary["by_competence"], competence_path)
    _atomic_dataframe(summary["by_file"], files_path)
    _atomic_dataframe(pd.DataFrame(cnes_audit), cnes_path)
    quality_keys = next(iter(state["partitions"].values()))["quality"].keys()
    quality = {}
    for key in quality_keys:
        values = [item["quality"][key] for item in state["partitions"].values()]
        if isinstance(values[0], dict):
            quality[key] = {subkey: sum(value[subkey] for value in values) for subkey in values[0]}
        else:
            quality[key] = sum(values)
    outputs = {
        "by_competence": {"path": competence_path.relative_to(settings.root_dir).as_posix(), "rows": len(summary["by_competence"]),
                          "bytes": competence_path.stat().st_size, "sha256": sha256_file(competence_path)},
        "by_partition": {"path": files_path.relative_to(settings.root_dir).as_posix(), "rows": len(summary["by_file"]),
                         "bytes": files_path.stat().st_size, "sha256": sha256_file(files_path)},
        "cnes_audit": {"path": cnes_path.relative_to(settings.root_dir).as_posix(), "rows": len(cnes_audit),
                       "bytes": cnes_path.stat().st_size, "sha256": sha256_file(cnes_path)},
    }
    report = {"pipeline_version": PIPELINE_VERSION, "processed_at": datetime.now(timezone.utc).isoformat(),
              "reference_period": "2024", "source_files": len(EXPECTED_FILES), "source_rows": expected_rows,
              "source_bytes": sum(raw[name]["bytes"] for name in EXPECTED_FILES),
              "source_checksums_sha256": hashlib_of_checksums(raw), "geography_sha256": geography_sha,
              "documentation": {"path": documentation_path.relative_to(settings.root_dir).as_posix(),
                                "bytes": documentation_path.stat().st_size, "sha256": documentation_sha},
              "silver_schema": str(SILVER_SCHEMA), "summary": summary["national"], "quality": quality,
              "cnes_join": cnes_audit, "sql_sha256": sha256_file(cnes_sql), "outputs": outputs,
              "partition_state": state_path.relative_to(settings.root_dir).as_posix()}
    report_path = settings.metadata_dir / "sih_2024_processing.json"
    old = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    comparable = {key: value for key, value in report.items() if key != "processed_at"}
    if old and {key: value for key, value in old.items() if key != "processed_at"} == comparable and not built:
        return old, False
    _write_json_atomic(report_path, report)
    logger.info("SIH Phase 7 validated", extra={"pipeline": "sih_2024", "task": "reconcile", "source": "SIH",
        "rows_in": expected_rows, "rows_out": summary["national"]["rows"], "rows_invalid": quality["invalid_primary_diagnosis"],
        "status": "success"})
    return report, True


def hashlib_of_checksums(raw: dict) -> str:
    import hashlib
    digest = hashlib.sha256()
    for name in EXPECTED_FILES:
        digest.update(name.encode("ascii"))
        digest.update(raw[name]["sha256"].encode("ascii"))
    return digest.hexdigest()


def validate_phase_7(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    report = json.loads((settings.metadata_dir / "sih_2024_processing.json").read_text(encoding="utf-8"))
    state = json.loads((settings.metadata_dir / "sih_2024_processing_state.json").read_text(encoding="utf-8"))
    if report["pipeline_version"] != PIPELINE_VERSION or set(state["partitions"]) != set(EXPECTED_FILES):
        raise ValueError("SIH Phase 7 report or partition inventory differs")
    manifest = read_manifest(settings.manifest_path)
    manifest_rows = {(row["source_name"], row["file_name"]): row for row in manifest}
    sih_manifest = [row for row in manifest if row["source_name"] == "SIH_RD"]
    if len(sih_manifest) != len(EXPECTED_FILES) or {row["file_name"] for row in sih_manifest} != set(EXPECTED_FILES):
        raise ValueError("SIH manifest inventory differs")
    raw = {}
    total_csv_rows = 0
    for name in EXPECTED_FILES:
        path = settings.data_dir / "raw" / "sih" / "original" / name
        check = validate_dbc(path)
        manifest_row = manifest_rows[("SIH_RD", name)]
        if (manifest_row["checksum"] != check.checksum
                or int(manifest_row["file_size_bytes"]) != check.size
                or int(manifest_row["records"]) != check.records
                or manifest_row["schema_version"] != check.schema_version):
            raise ValueError(f"SIH manifest reconciliation differs: {name}")
        raw[name] = {"path": path, "bytes": check.size, "sha256": check.checksum, "records": check.records}
        item = state["partitions"][name]
        if not _partition_current(item, raw[name], report["geography_sha256"], settings):
            raise ValueError(f"SIH partition differs: {name}")
        parquet_path = settings.root_dir / item["silver_parquet"]["path"]
        if not pq.read_schema(parquet_path).equals(SILVER_SCHEMA, check_metadata=False):
            raise ValueError(f"SIH Parquet schema differs: {name}")
        csv_path = settings.root_dir / item["raw_csv"]["path"]
        with gzip.open(csv_path, "rt", encoding="utf-8", newline="") as file_obj:
            reader = csv.reader(file_obj, strict=True)
            if tuple(next(reader)) != tuple(field.lower() for field in EXPECTED_FIELDS):
                raise ValueError(f"SIH CSV header differs: {name}")
            rows = 0
            for row in reader:
                if len(row) != len(EXPECTED_FIELDS):
                    raise ValueError(f"SIH CSV row width differs: {name}")
                rows += 1
        if rows != check.records:
            raise ValueError(f"SIH CSV row count differs: {name}")
        total_csv_rows += rows
    expected_rows = sum(item["records"] for item in raw.values())
    if (report["source_files"] != len(EXPECTED_FILES) or report["source_rows"] != expected_rows
            or report["source_bytes"] != sum(item["bytes"] for item in raw.values())
            or report["source_checksums_sha256"] != hashlib_of_checksums(raw)
            or total_csv_rows != expected_rows):
        raise ValueError("SIH source and converted CSV reconciliation differs")
    document_path = settings.root_dir / report["documentation"]["path"]
    document_manifest = manifest_rows.get(("SIH_DOCUMENTACAO_RD", DOCUMENT_FILE))
    if (document_manifest is None or not document_path.exists()
            or document_path.stat().st_size != report["documentation"]["bytes"]
            or sha256_file(document_path) != report["documentation"]["sha256"]
            or document_manifest["checksum"] != report["documentation"]["sha256"]):
        raise ValueError("SIH documentation reconciliation differs")
    parquet_glob = (settings.data_dir / "processed" / "sih" / "silver" / "**" / "*.parquet").as_posix()
    summary = _query_summary(parquet_glob, expected_rows, len(EXPECTED_FILES))
    if summary["national"] != report["summary"]:
        raise ValueError("SIH national metrics differ")
    capacity_path = settings.data_dir / "processed" / "cnes" / "fact_capacidade_hospitalar_2024.parquet"
    sql_path = settings.root_dir / "sql" / "duckdb" / "sih_2024_cnes_temporal_join.sql"
    cnes_audit = _cnes_audit(parquet_glob, capacity_path, sql_path)
    if cnes_audit != report["cnes_join"] or sha256_file(sql_path) != report["sql_sha256"]:
        raise ValueError("SIH/CNES join differs")
    for item in report["outputs"].values():
        if not _verify_artifact(item, settings.root_dir):
            raise ValueError("SIH summary output is absent")
    return report
