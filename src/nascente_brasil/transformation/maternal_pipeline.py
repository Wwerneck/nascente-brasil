"""Phase 8 maternal morbidity fact and territorial Gold outputs."""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import json
import os
from pathlib import Path
import tempfile

import duckdb
import pyarrow.parquet as pq

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.cid import FILES, ingest_cid, validate_cid_dbf
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import read_manifest
from nascente_brasil.transformation.maternal_cid import build_cid_reference
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


PIPELINE_VERSION = "phase8-v1"
GOLD_LEVELS = {
    "brasil": ("'BR'", "'Brasil'"),
    "regiao": ("m.codigo_regiao", "m.regiao"),
    "estado": ("m.uf", "m.nome_uf"),
    "municipio": ("f.codigo_ibge", "m.municipio"),
}


def _literal(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _artifact(path: Path, root: Path, rows: int) -> dict:
    return {"path": path.relative_to(root).as_posix(), "rows": rows,
            "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _write_copy(connection: duckdb.DuckDBPyConnection, query: str, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as file_obj:
            temp = Path(file_obj.name)
        option = "(FORMAT PARQUET, COMPRESSION ZSTD)" if fmt == "parquet" else "(HEADER, DELIMITER ',')"
        connection.execute(f"COPY ({query}) TO '{_literal(temp)}' {option}")
        os.replace(temp, path)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _source_checks(settings: Settings) -> dict:
    manifest = {(row["source_name"], row["file_name"]): row for row in read_manifest(settings.manifest_path)}
    checks = {}
    for name in FILES:
        path = settings.data_dir / "raw" / "cid" / "original" / name
        item = validate_cid_dbf(path)
        source = manifest.get(("CID10_TABELA", name))
        if source is None or source["checksum"] != item["sha256"] or int(source["records"]) != item["records"]:
            raise ValueError(f"CID source/manifest differs: {name}")
        checks[name] = item["sha256"]
    return checks


def _inputs(settings: Settings) -> dict:
    paths = {
        "phase7_report": settings.metadata_dir / "sih_2024_processing.json",
        "municipality": settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv",
        "classification_code": Path(__file__).with_name("maternal_cid.py"),
        "pipeline_code": Path(__file__),
    }
    checks = {key: sha256_file(path) for key, path in paths.items()}
    checks.update(_source_checks(settings))
    return checks


def _register_views(connection: duckdb.DuckDBPyConnection, settings: Settings, reference: Path) -> None:
    sih = settings.data_dir / "processed" / "sih" / "silver" / "**" / "*.parquet"
    municipality = settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv"
    connection.execute(f"CREATE VIEW sih AS SELECT * FROM read_parquet('{_literal(sih)}')")
    connection.execute(f"CREATE VIEW cid AS SELECT * FROM read_csv('{_literal(reference)}', all_varchar=true)")
    connection.execute(f"CREATE VIEW municipio AS SELECT * FROM read_csv('{_literal(municipality)}', all_varchar=true)")
    connection.execute("""
        CREATE VIEW elegiveis AS
        SELECT s.competencia, s.codigo_ibge_residencia AS codigo_ibge, s.arquivo_fonte,
               s.numero_aih, s.diagnostico_principal AS cid_codigo, s.dias_permanencia,
               s.valor_total, s.obito, c.cid_categoria, c.cid_descricao,
               c.grupo_morbidade, c.subgrupo, c.periodo_obstetrico,
               CAST(c.e_morbidade AS BOOLEAN) AS e_morbidade
        FROM sih s LEFT JOIN cid c ON s.diagnostico_principal = c.cid_codigo
        WHERE s.tipo_aih = '1' AND s.sexo = '3' AND s.diagnostico_principal LIKE 'O%'
    """)


def _audit(connection: duckdb.DuckDBPyConnection) -> dict:
    source = connection.execute("""
        SELECT COUNT(*) AS all_sih,
               COUNT(*) FILTER (WHERE tipo_aih = '1' AND diagnostico_principal LIKE 'O%') AS obstetric_type1,
               COUNT(*) FILTER (WHERE tipo_aih = '1' AND sexo = '3' AND diagnostico_principal LIKE 'O%') AS eligible,
               COUNT(*) FILTER (WHERE tipo_aih = '5' AND diagnostico_principal LIKE 'O%') AS obstetric_type5
        FROM sih
    """).fetchone()
    eligible = connection.execute("""
        SELECT COUNT(*) AS rows,
               COUNT(*) FILTER (WHERE grupo_morbidade IS NULL) AS missing_cid_catalog,
               COUNT(*) FILTER (WHERE codigo_ibge IS NULL) AS missing_geography,
               COUNT(*) FILTER (WHERE e_morbidade) AS morbidity_rows,
               COUNT(*) FILTER (WHERE NOT e_morbidade) AS other_obstetric_rows,
               COUNT(*) - COUNT(DISTINCT arquivo_fonte || ':' || numero_aih) AS repeated_aih_keys
        FROM elegiveis
    """).fetchone()
    if source[2] != eligible[0] or eligible[1] or eligible[2]:
        raise ValueError(f"Maternal CID/geography reconciliation failed: {source}, {eligible}")
    return {"sih_rows": source[0], "obstetric_type1_all_sex": source[1],
            "eligible_type1_sex3": eligible[0], "obstetric_type5": source[3],
            "excluded_other_sex": source[1] - source[2], "morbidity_rows": eligible[3],
            "other_obstetric_rows": eligible[4], "repeated_aih_keys": eligible[5]}


def _fact_query() -> str:
    return """
        SELECT competencia, codigo_ibge, cid_codigo, cid_categoria, cid_descricao,
               grupo_morbidade, subgrupo, periodo_obstetrico, e_morbidade,
               COUNT(*)::BIGINT AS registros_aih,
               SUM(COALESCE(dias_permanencia, 0))::BIGINT AS dias_permanencia,
               SUM(COALESCE(valor_total, 0))::DECIMAL(20, 2) AS valor_total,
               SUM(CASE WHEN obito = 1 THEN 1 ELSE 0 END)::BIGINT AS obitos_hospitalares
        FROM elegiveis
        GROUP BY ALL
    """


def _gold_query(level: str) -> str:
    code, label = GOLD_LEVELS[level]
    return f"""
        WITH grouped AS (
            SELECT f.competencia, {code} AS codigo_territorio, {label} AS territorio,
                   f.grupo_morbidade, f.subgrupo, f.e_morbidade,
                   SUM(f.registros_aih)::BIGINT AS registros_aih,
                   SUM(f.dias_permanencia)::BIGINT AS dias_permanencia,
                   SUM(f.valor_total)::DECIMAL(20,2) AS valor_total,
                   SUM(f.obitos_hospitalares)::BIGINT AS obitos_hospitalares
            FROM fato f JOIN municipio m ON f.codigo_ibge = m.codigo_ibge
            GROUP BY ALL
        ), denominators AS (
            SELECT competencia, codigo_territorio, SUM(registros_aih)::BIGINT AS denominador_aih_obstetricas
            FROM grouped GROUP BY 1, 2
        )
        SELECT g.competencia, g.codigo_territorio, g.territorio, g.grupo_morbidade,
               g.subgrupo, g.registros_aih, d.denominador_aih_obstetricas,
               ROUND(100.0 * g.registros_aih / d.denominador_aih_obstetricas, 4) AS proporcao_aih_obstetricas_pct,
               g.dias_permanencia, g.valor_total, g.obitos_hospitalares
        FROM grouped g JOIN denominators d USING (competencia, codigo_territorio)
        WHERE g.e_morbidade
        ORDER BY 1, 2, 4, 5
    """


def _csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj, strict=True)
        header = next(reader)
        rows = 0
        for row in reader:
            if len(row) != len(header):
                raise ValueError(f"Maternal CSV row width differs: {path}")
            rows += 1
        return rows


def _gold_totals(connection: duckdb.DuckDBPyConnection, path: Path) -> tuple[int, int]:
    source = f"read_csv('{_literal(path)}', all_varchar=true)"
    numerator = connection.execute(f"SELECT SUM(CAST(registros_aih AS BIGINT)) FROM {source}").fetchone()[0]
    denominator = connection.execute(f"""
        SELECT SUM(denominador) FROM (
            SELECT competencia, codigo_territorio,
                   MIN(CAST(denominador_aih_obstetricas AS BIGINT)) AS denominador,
                   MAX(CAST(denominador_aih_obstetricas AS BIGINT)) AS maximo
            FROM {source} GROUP BY 1, 2
        ) WHERE denominador = maximo
    """).fetchone()[0]
    return int(numerator), int(denominator)


def _expected_covered_denominator(connection: duckdb.DuckDBPyConnection, path: Path, level: str) -> int:
    code, _ = GOLD_LEVELS[level]
    result = connection.execute(f"""
        SELECT SUM(f.registros_aih)
        FROM fato f JOIN municipio m ON f.codigo_ibge = m.codigo_ibge
        JOIN (SELECT DISTINCT competencia, codigo_territorio
              FROM read_csv('{_literal(path)}', all_varchar=true)) g
          ON f.competencia = g.competencia AND {code} = g.codigo_territorio
    """).fetchone()[0]
    return int(result)


def run_phase_8(settings: Settings | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    _, raw_built = ingest_cid(settings)
    logger = get_logger("transformation.maternal")
    inputs = _inputs(settings)
    report_path = settings.metadata_dir / "maternal_morbidity_2024_processing.json"
    old = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    if old and old["pipeline_version"] == PIPELINE_VERSION and old["inputs"] == inputs and not raw_built:
        validate_phase_8(settings)
        return old, False
    reference = settings.data_dir / "reference" / "cid" / "cid_materno.csv"
    cid_raw = settings.data_dir / "raw" / "cid" / "original"
    reference_info = build_cid_reference(cid_raw / "CID10.DBF", cid_raw / "CIDCAP10.DBF", reference)
    fact = settings.data_dir / "processed" / "morbidades_maternas" / "fact_morbidades_maternas_2024.parquet"
    gold_root = settings.data_dir / "gold" / "morbidades"
    with duckdb.connect() as connection:
        _register_views(connection, settings, reference)
        audit = _audit(connection)
        _write_copy(connection, _fact_query(), fact, "parquet")
        connection.execute(f"CREATE VIEW fato AS SELECT * FROM read_parquet('{_literal(fact)}')")
        fact_totals = connection.execute("""
            SELECT SUM(registros_aih), SUM(registros_aih) FILTER (WHERE e_morbidade),
                   SUM(registros_aih) FILTER (WHERE NOT e_morbidade),
                   COUNT(DISTINCT competencia), COUNT(DISTINCT codigo_ibge)
            FROM fato
        """).fetchone()
        if fact_totals[:3] != (audit["eligible_type1_sex3"], audit["morbidity_rows"], audit["other_obstetric_rows"]):
            raise ValueError("Maternal fact does not reconcile with eligible source")
        outputs = {}
        for level in GOLD_LEVELS:
            path = gold_root / f"morbidades_{level}.csv"
            _write_copy(connection, _gold_query(level), path, "csv")
            outputs[level] = _artifact(path, settings.root_dir, _csv_rows(path))
        coverage = {}
        for level in GOLD_LEVELS:
            path = settings.root_dir / outputs[level]["path"]
            numerator, denominator = _gold_totals(connection, path)
            expected_covered = _expected_covered_denominator(connection, path, level)
            if numerator != audit["morbidity_rows"] or denominator != expected_covered:
                raise ValueError(f"Maternal Gold reconciliation failed: {level}, {numerator}, {denominator}")
            coverage[level] = {"denominator_covered": denominator,
                               "denominator_without_morbidity_row": audit["eligible_type1_sex3"] - denominator}
    report = {"pipeline_version": PIPELINE_VERSION, "processed_at": datetime.now(timezone.utc).isoformat(),
              "reference_period": "2024", "inputs": inputs,
              "cid_reference": _artifact(reference, settings.root_dir, reference_info["rows"]),
              "cid_groups": reference_info["groups"], "audit": audit,
              "fact": _artifact(fact, settings.root_dir, pq.ParquetFile(fact).metadata.num_rows),
              "fact_competencies": fact_totals[3], "fact_municipalities": fact_totals[4],
              "gold": outputs, "denominator_coverage": coverage}
    _write_json_atomic(report_path, report)
    logger.info("Maternal morbidity Phase 8 validated", extra={"pipeline": "maternal_2024",
                "task": "reconcile", "source": "SIH/CID10", "rows_in": audit["eligible_type1_sex3"],
                "rows_out": audit["morbidity_rows"], "status": "success"})
    return report, True


def validate_phase_8(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    report = json.loads((settings.metadata_dir / "maternal_morbidity_2024_processing.json").read_text(encoding="utf-8"))
    if report["pipeline_version"] != PIPELINE_VERSION or report["inputs"] != _inputs(settings):
        raise ValueError("Maternal inputs or pipeline version differ")
    for item in (report["cid_reference"], report["fact"], *report["gold"].values()):
        path = settings.root_dir / item["path"]
        if not path.exists() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Maternal artifact differs: {path}")
    if pq.ParquetFile(settings.root_dir / report["fact"]["path"]).metadata.num_rows != report["fact"]["rows"]:
        raise ValueError("Maternal fact row count differs")
    with duckdb.connect() as connection:
        reference = settings.root_dir / report["cid_reference"]["path"]
        _register_views(connection, settings, reference)
        audit = _audit(connection)
        if audit != report["audit"]:
            raise ValueError("Maternal source audit differs")
        fact = settings.root_dir / report["fact"]["path"]
        connection.execute(f"CREATE VIEW fato AS SELECT * FROM read_parquet('{_literal(fact)}')")
        totals = connection.execute("SELECT SUM(registros_aih), SUM(registros_aih) FILTER (WHERE e_morbidade) FROM fato").fetchone()
        if totals != (audit["eligible_type1_sex3"], audit["morbidity_rows"]):
            raise ValueError("Maternal fact totals differ")
        for level, item in report["gold"].items():
            path = settings.root_dir / item["path"]
            if _csv_rows(path) != item["rows"]:
                raise ValueError(f"Maternal Gold rows differ: {level}")
            numerator, denominator = _gold_totals(connection, path)
            expected_covered = _expected_covered_denominator(connection, path, level)
            coverage = report["denominator_coverage"][level]
            if (numerator != audit["morbidity_rows"] or denominator != expected_covered
                    or coverage["denominator_covered"] != denominator
                    or coverage["denominator_without_morbidity_row"] != audit["eligible_type1_sex3"] - denominator):
                raise ValueError(f"Maternal Gold sums differ: {level}")
    return report
