"""Build IBGE dimensions and audit SINASC territorial joins."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

import duckdb

from nascente_brasil.analytics.sinasc import export_csv
from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.ibge import ingest_ibge_raw, read_dtb, read_ufs
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


PIPELINE_VERSION = "phase5-v1"


def _artifact(path: Path, root: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def _dimensions(dtb, ufs: list[dict]) -> dict[str, list[dict]]:
    regions = {str(item["regiao"]["id"]): {"codigo_regiao": str(item["regiao"]["id"]),
                                                  "regiao": item["regiao"]["nome"]} for item in ufs}
    states = {}
    for item in ufs:
        code = str(item["id"])
        states[code] = {"codigo_uf": code, "uf": item["sigla"], "nome_uf": item["nome"],
                        "codigo_regiao": str(item["regiao"]["id"]), "regiao": item["regiao"]["nome"]}
    if set(dtb["codigo_uf"]) != set(states):
        raise ValueError("IBGE DTB UF codes differ from the official UF API")
    if any(row.nome_uf != states[row.codigo_uf]["nome_uf"]
           for row in dtb[["codigo_uf", "nome_uf"]].drop_duplicates().itertuples(index=False)):
        raise ValueError("IBGE DTB UF names differ from the official UF API")
    municipalities = []
    for row in dtb.itertuples(index=False):
        state = states[row.codigo_uf]
        municipalities.append({"codigo_ibge": row.codigo_ibge, "codigo_sinasc_6": row.codigo_ibge[:6],
                               "municipio": row.municipio, **state})
    if len({row["codigo_sinasc_6"] for row in municipalities}) != len(municipalities):
        raise ValueError("IBGE municipality six-digit join keys are not unique")
    return {"regiao": [regions[key] for key in sorted(regions)],
            "estado": [states[key] for key in sorted(states)],
            "municipio": sorted(municipalities, key=lambda row: row["codigo_ibge"])}


def _phase3_input(settings: Settings) -> tuple[dict, Path]:
    reports = sorted(settings.metadata_dir.glob("sinasc_2024_*_processing.json"))
    if len(reports) != 1:
        raise ValueError("Expected one SINASC 2024 Phase 3 report")
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    item = report["silver"]["parquet"]
    path = settings.root_dir / item["path"]
    if not path.is_file() or _artifact(path, settings.root_dir) != item:
        raise ValueError("SINASC Silver Parquet differs from Phase 3 metadata")
    return report, path


def _join(parquet_path: Path, dimensions: dict[str, list[dict]], sql_path: Path) -> list[dict]:
    import pandas as pd
    with duckdb.connect() as connection:
        connection.read_parquet(str(parquet_path)).create_view("sinasc")
        connection.register("dim_municipio", pd.DataFrame(dimensions["municipio"]))
        connection.register("dim_estado", pd.DataFrame(dimensions["estado"]))
        result = connection.execute(sql_path.read_text(encoding="utf-8"))
        columns = [column[0] for column in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]


def _join_metrics(rows: list[dict], dimensions: dict[str, list[dict]], total: int) -> dict:
    metrics = {}
    right_keys = {item["codigo_sinasc_6"] for item in dimensions["municipio"]}
    for role in ("residencia", "ocorrencia"):
        selected = [row for row in rows if row["tipo_codigo"] == role]
        matched = sum(row["registros"] for row in selected if row["match_status"] == "matched")
        reasons = defaultdict(int)
        for row in selected:
            if row["match_status"] != "matched":
                reasons[row["match_status"]] += row["registros"]
        if sum(row["registros"] for row in selected) != total or matched + sum(reasons.values()) != total:
            raise ValueError(f"SINASC territory join does not reconcile: {role}")
        used = {row["codigo_sinasc"] for row in selected if row["match_status"] == "matched"}
        metrics[role] = {
            "left_rows": total, "right_rows": len(right_keys), "matched_rows": matched,
            "unmatched_left": total - matched, "unmatched_right": len(right_keys - used),
            "duplicated_keys": 0, "match_rate_pct": round(100 * matched / total, 4) if total else None,
            "unmatched_by_reason": dict(sorted(reasons.items())),
            "top_unmatched_codes": [
                {"codigo_sinasc": row["codigo_sinasc"], "registros": row["registros"],
                 "reason": row["match_status"]}
                for row in selected if row["match_status"] != "matched"
            ][:20],
        }
    return metrics


def _verify_outputs(report: dict, settings: Settings) -> bool:
    missing = False
    for item in report["outputs"].values():
        path = settings.root_dir / item["path"]
        if not path.exists():
            missing = True
            continue
        if _artifact(path, settings.root_dir) != item:
            raise ValueError(f"Phase 5 output changed: {path}")
    return not missing


def run_phase_5(settings: Settings | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    logger = get_logger("transformation.ibge")
    raw = ingest_ibge_raw(settings)
    phase3, parquet_path = _phase3_input(settings)
    sql_path = settings.root_dir / "sql" / "duckdb" / "sinasc_2024_territory_join.sql"
    report_path = settings.metadata_dir / "ibge_sinasc_2024_territory.json"
    inputs = {"dtb_sha256": raw["IBGE_DTB"]["sha256"], "uf_sha256": raw["IBGE_UF"]["sha256"],
              "silver_sha256": phase3["silver"]["parquet"]["sha256"], "sql_sha256": sha256_file(sql_path)}
    if report_path.exists():
        old = json.loads(report_path.read_text(encoding="utf-8"))
        if old.get("pipeline_version") == PIPELINE_VERSION and old.get("inputs") == inputs and _verify_outputs(old, settings):
            logger.info("IBGE territory already current", extra={"pipeline": "ibge_territory", "status": "skipped"})
            return old, False
    dtb = read_dtb(raw["IBGE_DTB"]["path"])
    ufs = read_ufs(raw["IBGE_UF"]["path"])
    dimensions = _dimensions(dtb, ufs)
    rows = _join(parquet_path, dimensions, sql_path)
    metrics = _join_metrics(rows, dimensions, phase3["rows"])
    outputs = {}
    raw_csv = settings.data_dir / "raw" / "ibge" / "csv"
    reference = settings.data_dir / "reference" / "ibge"
    analytics = settings.data_dir / "processed" / "sinasc" / "analytics"
    data = {
        "dtb_municipios_csv": (raw_csv / "dtb_2024_municipios.csv", dtb.to_dict("records")),
        "ibge_ufs_csv": (raw_csv / "ibge_estados_api.csv", [
            {"codigo_uf": str(item["id"]), "uf": item["sigla"], "nome_uf": item["nome"],
             "codigo_regiao": str(item["regiao"]["id"]), "regiao": item["regiao"]["nome"]}
            for item in ufs]),
        "dim_regiao": (reference / "dim_regiao_2024.csv", dimensions["regiao"]),
        "dim_estado": (reference / "dim_estado_2024.csv", dimensions["estado"]),
        "dim_municipio": (reference / "dim_municipio_2024.csv", dimensions["municipio"]),
        "territory_join": (analytics / "sinasc_2024_territory_join.csv", rows),
    }
    for name, (path, records) in data.items():
        export_csv(path, records)
        outputs[name] = _artifact(path, settings.root_dir)
    report = {"pipeline_version": PIPELINE_VERSION, "processed_at": datetime.now(timezone.utc).isoformat(),
              "reference_period": "2024", "inputs": inputs, "dimension_rows": {name: len(dimensions[name]) for name in dimensions},
              "sinasc_rows": phase3["rows"], "territory_code_groups": len(rows), "join_metrics": metrics, "outputs": outputs}
    _write_json_atomic(report_path, report)
    logger.info("IBGE territory validated", extra={"pipeline": "ibge_territory", "task": "join", "source": "IBGE/SINASC",
                                                "rows_in": phase3["rows"], "rows_out": metrics["residencia"]["matched_rows"],
                                                "rows_invalid": metrics["residencia"]["unmatched_left"], "status": "success"})
    return report, True


def validate_phase_5(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    report_path = settings.metadata_dir / "ibge_sinasc_2024_territory.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    phase3, parquet_path = _phase3_input(settings)
    dtb_path = settings.data_dir / "raw" / "ibge" / "original" / "DTB_2024.zip"
    uf_path = settings.data_dir / "raw" / "ibge" / "original" / "ibge_estados_api.json"
    sql_path = settings.root_dir / "sql" / "duckdb" / "sinasc_2024_territory_join.sql"
    inputs = {"dtb_sha256": sha256_file(dtb_path), "uf_sha256": sha256_file(uf_path),
              "silver_sha256": phase3["silver"]["parquet"]["sha256"], "sql_sha256": sha256_file(sql_path)}
    if report["pipeline_version"] != PIPELINE_VERSION or report["inputs"] != inputs or not _verify_outputs(report, settings):
        raise ValueError("Phase 5 metadata, inputs, SQL or outputs differ")
    dtb = read_dtb(dtb_path)
    ufs = read_ufs(uf_path)
    dimensions = _dimensions(dtb, ufs)
    rows = _join(parquet_path, dimensions, sql_path)
    metrics = _join_metrics(rows, dimensions, phase3["rows"])
    if (report["dimension_rows"] != {name: len(items) for name, items in dimensions.items()}
            or report["territory_code_groups"] != len(rows)
            or report["join_metrics"] != metrics
            or report["sinasc_rows"] != phase3["rows"]):
        raise ValueError("Phase 5 counts or join metrics differ")
    expected = {"dtb_municipios_csv": dtb.to_dict("records"),
                "ibge_ufs_csv": [{"codigo_uf": str(item["id"]), "uf": item["sigla"], "nome_uf": item["nome"],
                                  "codigo_regiao": str(item["regiao"]["id"]), "regiao": item["regiao"]["nome"]} for item in ufs],
                "dim_regiao": dimensions["regiao"], "dim_estado": dimensions["estado"],
                "dim_municipio": dimensions["municipio"], "territory_join": rows}
    for name, records in expected.items():
        path = settings.root_dir / report["outputs"][name]["path"]
        with path.open("r", encoding="utf-8", newline="") as file_obj:
            actual = list(csv.DictReader(file_obj))
        normalized = [{key: "" if value is None else str(value) for key, value in row.items()} for row in records]
        if actual != normalized:
            raise ValueError(f"Phase 5 output content differs: {name}")
    return report
