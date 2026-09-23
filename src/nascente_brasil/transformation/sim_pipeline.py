"""National SIM/SINASC 2024 mortality processing and observed indicators."""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import gzip
import json
import os
from pathlib import Path
import tempfile

import duckdb
import pyarrow.parquet as pq

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.conversion.sim import SILVER_SCHEMA, convert_sim
from nascente_brasil.ingestion.sim import FILE, ingest_sim_2024, validate_sim_dbc
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import read_manifest
from nascente_brasil.transformation.sih_pipeline import _geography
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


PIPELINE_VERSION = "phase9-v2"
LEVELS = {
    "brasil": ("'BR'", "'Brasil'"),
    "regiao": ("m.codigo_regiao", "m.regiao"),
    "estado": ("m.uf", "m.nome_uf"),
    "municipio": ("m.codigo_ibge", "m.municipio"),
}


def _literal(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _artifact(path: Path, root: Path, rows: int) -> dict:
    return {"path": path.relative_to(root).as_posix(), "rows": rows,
            "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _paths(settings: Settings) -> tuple[Path, Path, Path]:
    original = settings.data_dir / "raw" / "sim" / "original" / FILE
    raw_csv = settings.data_dir / "raw" / "sim" / "csv" / "DOBR2024.csv.gz"
    silver = settings.data_dir / "processed" / "sim" / "sim_2024_silver.parquet"
    return original, raw_csv, silver


def _sinasc_path(settings: Settings) -> Path:
    paths = sorted((settings.data_dir / "processed" / "sinasc").glob("*_silver.parquet"))
    if len(paths) != 1:
        raise ValueError("Expected exactly one SINASC 2024 Silver Parquet")
    return paths[0]


def _inputs(settings: Settings) -> dict:
    original, _, _ = _paths(settings)
    items = {"sim_dbc": original, "sinasc_silver": _sinasc_path(settings),
             "ibge_municipality": settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv",
             "pipeline_code": Path(__file__), "conversion_code": Path(__file__).parents[1] / "conversion" / "sim.py"}
    return {key: sha256_file(path) for key, path in items.items()}


def _validate_source(settings: Settings) -> dict:
    original, _, _ = _paths(settings)
    check = validate_sim_dbc(original)
    rows = [row for row in read_manifest(settings.manifest_path)
            if row["source_name"] == "SIM_DO" and row["file_name"] == FILE]
    if len(rows) != 1 or rows[0]["checksum"] != check.checksum or int(rows[0]["records"]) != check.records:
        raise ValueError("SIM source manifest differs")
    return {"rows": check.records, "bytes": check.size, "sha256": check.checksum,
            "schema_version": check.schema_version, "fields": check.fields}


def _validate_converted(settings: Settings, expected: dict, *, count_csv: bool) -> dict:
    _, csv_path, silver = _paths(settings)
    if not csv_path.exists() or not silver.exists():
        raise FileNotFoundError("SIM conversion artifacts missing")
    parquet = pq.ParquetFile(silver)
    if parquet.metadata.num_rows != expected["rows"] or not pq.read_schema(silver).equals(SILVER_SCHEMA, check_metadata=False):
        raise ValueError("SIM Silver schema or row count differs")
    if count_csv:
        with gzip.open(csv_path, "rt", encoding="utf-8", newline="") as file_obj:
            reader = csv.reader(file_obj, strict=True)
            if tuple(next(reader)) != tuple(field.lower() for field in expected["fields"]):
                raise ValueError("SIM CSV header differs")
            rows = 0
            for row in reader:
                if len(row) != len(expected["fields"]):
                    raise ValueError("SIM CSV row width differs")
                rows += 1
        if rows != expected["rows"]:
            raise ValueError("SIM CSV row count differs")
    return {"raw_csv": _artifact(csv_path, settings.root_dir, expected["rows"]),
            "silver": _artifact(silver, settings.root_dir, expected["rows"])}


def _views(connection: duckdb.DuckDBPyConnection, settings: Settings) -> None:
    _, _, silver = _paths(settings)
    sinasc = _sinasc_path(settings)
    municipality = settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv"
    connection.execute(f"CREATE VIEW sim AS SELECT * FROM read_parquet('{_literal(silver)}')")
    connection.execute(f"CREATE VIEW sinasc AS SELECT * FROM read_parquet('{_literal(sinasc)}')")
    connection.execute(f"CREATE VIEW municipio AS SELECT * FROM read_csv('{_literal(municipality)}', all_varchar=true)")
    connection.execute("""
        CREATE VIEW deaths AS
        SELECT *, CASE
            WHEN data_nascimento IS NOT NULL AND data_obito IS NOT NULL
                 AND data_obito >= data_nascimento
              THEN date_diff('day', data_nascimento, data_obito)
            ELSE NULL END AS idade_dias_datas,
            CASE WHEN tipo_obito = '2' AND sexo = '2' AND
                regexp_full_match(causa_basica, 'O[0-9]{2}[0-9A-Z]?')
                AND substr(causa_basica, 1, 3) NOT IN ('O96', 'O97')
                THEN 1 ELSE 0 END AS obito_causa_obstetrica,
            CASE WHEN tipo_obito = '2' AND sexo = '2' AND
                (substr(causa_basica, 1, 3) IN ('O96', 'O97'))
                THEN 1 ELSE 0 END AS obito_materno_tardio_sequela,
            CASE WHEN tipo_obito = '2' AND sexo = '2'
                AND (obito_gravidez = '1' OR obito_puerperio = '1')
                AND (substr(causa_basica, 1, 3) IN ('A34', 'F53')
                     OR substr(causa_basica, 1, 3) BETWEEN 'B20' AND 'B24'
                     OR causa_basica IN ('E230', 'M830'))
                THEN 1 ELSE 0 END AS causa_indireta_candidata,
            CASE WHEN tipo_obito <> '2' THEN 0
                 WHEN substr(idade_original, 1, 1) IN ('0','1','2','3') THEN 1
                 WHEN substr(idade_original, 1, 1) IN ('4','5') THEN 0
                 WHEN idade_dias_datas BETWEEN 0 AND 364 THEN 1 ELSE 0 END AS obito_infantil,
            CASE WHEN tipo_obito <> '2' THEN 0
                 WHEN substr(idade_original, 1, 1) IN ('0','1') THEN 1
                 WHEN substr(idade_original, 1, 1) = '2'
                   THEN COALESCE(CAST(TRY_CAST(substr(idade_original, 2, 2) AS INTEGER) <= 27 AS INTEGER), 0)
                 WHEN substr(idade_original, 1, 1) IN ('3','4','5') THEN 0
                 WHEN idade_dias_datas BETWEEN 0 AND 27 THEN 1 ELSE 0 END AS obito_neonatal,
            CASE WHEN tipo_obito <> '2' THEN 0
                 WHEN substr(idade_original, 1, 1) IN ('0','1') THEN 1
                 WHEN substr(idade_original, 1, 1) = '2'
                   THEN COALESCE(CAST(TRY_CAST(substr(idade_original, 2, 2) AS INTEGER) <= 6 AS INTEGER), 0)
                 WHEN substr(idade_original, 1, 1) IN ('3','4','5') THEN 0
                 WHEN idade_dias_datas BETWEEN 0 AND 6 THEN 1 ELSE 0 END AS obito_neonatal_precoce
        FROM sim
    """)
    connection.execute("""
        CREATE VIEW births AS
        SELECT s.codigo_municipio_residencia, m.codigo_ibge, m.codigo_regiao, m.regiao,
               m.uf, m.nome_uf, m.municipio
        FROM sinasc s LEFT JOIN municipio m
          ON s.codigo_municipio_residencia = m.codigo_sinasc_6
        WHERE year(s.data_nascimento) = 2024
    """)


def _summary(connection: duckdb.DuckDBPyConnection) -> dict:
    result = connection.execute("""
        SELECT COUNT(*) AS sim_rows, COUNT(*) FILTER (WHERE ano_obito = 2024) AS deaths_in_2024,
               COUNT(*) FILTER (WHERE tipo_obito = '1') AS fetal,
               COUNT(*) FILTER (WHERE tipo_obito = '2') AS nonfetal,
               COUNT(*) FILTER (WHERE data_obito IS NULL) AS missing_death_date,
               COUNT(*) FILTER (WHERE codigo_ibge_residencia IS NULL) AS unmatched_residence,
               SUM(obito_causa_obstetrica) AS obstetric_basic_cause,
               SUM(obito_materno_tardio_sequela) AS late_maternal_or_sequela,
               SUM(causa_indireta_candidata) AS indirect_candidates,
               SUM(obito_infantil) AS infant, SUM(obito_neonatal) AS neonatal,
               SUM(obito_neonatal_precoce) AS early_neonatal
        FROM deaths
    """)
    summary = dict(zip([column[0] for column in result.description], result.fetchone()))
    births = connection.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE codigo_ibge IS NULL) FROM births").fetchone()
    summary["live_births"] = births[0]
    summary["unmatched_live_births"] = births[1]
    unallocated = connection.execute("""
        SELECT COUNT(*), SUM(obito_causa_obstetrica), SUM(obito_infantil),
               SUM(obito_neonatal), SUM(obito_neonatal_precoce)
        FROM deaths WHERE codigo_ibge_residencia IS NULL
    """).fetchone()
    summary["unallocated_deaths"] = unallocated[0]
    summary["unallocated_obstetric_basic_cause"] = unallocated[1]
    summary["unallocated_infant"] = unallocated[2]
    summary["unallocated_neonatal"] = unallocated[3]
    summary["unallocated_early_neonatal"] = unallocated[4]
    summary["age_code_date_disagreement"] = connection.execute("""
        SELECT COUNT(*) FROM deaths
        WHERE substr(idade_original, 1, 1) IN ('0','1','2','3') AND idade_dias_datas > 364
    """).fetchone()[0]
    if summary["sim_rows"] != summary["deaths_in_2024"] or summary["nonfetal"] + summary["fetal"] != summary["sim_rows"]:
        raise ValueError(f"SIM 2024 year/type reconciliation differs: {summary}")
    if summary["neonatal"] > summary["infant"] or summary["early_neonatal"] > summary["neonatal"]:
        raise ValueError("Infant/neonatal components are inconsistent")
    return summary


def _gold_query(level: str) -> str:
    code, label = LEVELS[level]
    if level == "brasil":
        birth_source = f"SELECT {code} AS codigo_territorio, {label} AS territorio, COUNT(*)::BIGINT AS nascidos_vivos FROM births"
        death_source = f"SELECT {code} AS codigo_territorio, {label} AS territorio,"
        death_join = ""
    else:
        birth_source = (f"SELECT {code} AS codigo_territorio, {label} AS territorio, "
                        "COUNT(*)::BIGINT AS nascidos_vivos FROM births b JOIN municipio m ON b.codigo_ibge = m.codigo_ibge "
                        "GROUP BY 1,2")
        death_source = f"SELECT {code} AS codigo_territorio, {label} AS territorio,"
        death_join = "JOIN municipio m ON d.codigo_ibge_residencia = m.codigo_ibge"
    return f"""
        WITH b AS ({birth_source}), d AS (
            {death_source}
                   COUNT(*) FILTER (WHERE d.tipo_obito = '2')::BIGINT AS obitos_nao_fetais,
                   SUM(d.obito_causa_obstetrica)::BIGINT AS obitos_causa_obstetrica_cid_o,
                   SUM(d.obito_materno_tardio_sequela)::BIGINT AS obitos_maternos_tardios_sequelas,
                   SUM(d.causa_indireta_candidata)::BIGINT AS causas_indiretas_candidatas,
                   SUM(d.obito_infantil)::BIGINT AS obitos_infantis,
                   SUM(d.obito_neonatal)::BIGINT AS obitos_neonatais,
                   SUM(d.obito_neonatal_precoce)::BIGINT AS obitos_neonatais_precoces
            FROM deaths d {death_join} {'' if level == 'brasil' else 'GROUP BY 1,2'}
        )
        SELECT 2024 AS ano, COALESCE(b.codigo_territorio, d.codigo_territorio) AS codigo_territorio,
               COALESCE(b.territorio, d.territorio) AS territorio,
               COALESCE(b.nascidos_vivos, 0) AS nascidos_vivos,
               COALESCE(d.obitos_nao_fetais, 0) AS obitos_nao_fetais,
               COALESCE(d.obitos_causa_obstetrica_cid_o, 0) AS obitos_causa_obstetrica_cid_o,
               COALESCE(d.obitos_maternos_tardios_sequelas, 0) AS obitos_maternos_tardios_sequelas,
               COALESCE(d.causas_indiretas_candidatas, 0) AS causas_indiretas_candidatas,
               COALESCE(d.obitos_infantis, 0) AS obitos_infantis,
               COALESCE(d.obitos_neonatais, 0) AS obitos_neonatais,
               COALESCE(d.obitos_neonatais_precoces, 0) AS obitos_neonatais_precoces,
               COALESCE(d.obitos_infantis, 0) - COALESCE(d.obitos_neonatais, 0) AS obitos_pos_neonatais,
               CASE WHEN b.nascidos_vivos > 0 THEN ROUND(100000.0 * COALESCE(d.obitos_causa_obstetrica_cid_o, 0) / b.nascidos_vivos, 4) END
                   AS razao_observada_causa_obstetrica_por_100mil_nv,
               CASE WHEN b.nascidos_vivos > 0 THEN ROUND(1000.0 * COALESCE(d.obitos_infantis, 0) / b.nascidos_vivos, 4) END
                   AS taxa_observada_mortalidade_infantil_por_mil_nv,
               CASE WHEN b.nascidos_vivos > 0 THEN ROUND(1000.0 * COALESCE(d.obitos_neonatais, 0) / b.nascidos_vivos, 4) END
                   AS taxa_observada_mortalidade_neonatal_por_mil_nv
        FROM b FULL OUTER JOIN d USING (codigo_territorio)
        ORDER BY 2
    """


def _write_csv(connection: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as file_obj:
            temp = Path(file_obj.name)
        connection.execute(f"COPY ({query}) TO '{_literal(temp)}' (HEADER, DELIMITER ',')")
        os.replace(temp, path)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj, strict=True)
        header = next(reader)
        rows = 0
        for row in reader:
            if len(row) != len(header):
                raise ValueError(f"SIM Gold row width differs: {path}")
            rows += 1
    return rows


def _conversion_quality(connection: duckdb.DuckDBPyConnection, settings: Settings) -> dict:
    _, csv_path, _ = _paths(settings)
    raw = _literal(csv_path)
    invalid = connection.execute(f"""
        SELECT COUNT(*) FILTER (WHERE dtobito <> '' AND try_strptime(dtobito, '%d%m%Y') IS NULL),
               COUNT(*) FILTER (WHERE dtnasc <> '' AND try_strptime(dtnasc, '%d%m%Y') IS NULL),
               COUNT(*) FILTER (WHERE dtinvestig <> '' AND try_strptime(dtinvestig, '%d%m%Y') IS NULL)
        FROM read_csv('{raw}', all_varchar=true)
    """).fetchone()
    silver = connection.execute("""
        SELECT COUNT(*) FILTER (WHERE codigo_municipio_residencia IS NOT NULL AND codigo_ibge_residencia IS NULL),
               COUNT(*) FILTER (WHERE codigo_municipio_ocorrencia IS NOT NULL AND codigo_ibge_ocorrencia IS NULL),
               COUNT(*) FILTER (WHERE data_nascimento > data_obito),
               COUNT(*) FILTER (WHERE causa_basica IS NULL)
        FROM sim
    """).fetchone()
    return {"invalid_dates": dict(zip(("DTOBITO", "DTNASC", "DTINVESTIG"), invalid)),
            "unmatched_residence": silver[0], "unmatched_occurrence": silver[1],
            "birth_after_death": silver[2], "missing_basic_cause": silver[3]}


def run_phase_9(settings: Settings | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    _, raw_built = ingest_sim_2024(settings)
    source = _validate_source(settings)
    original, csv_path, silver = _paths(settings)
    inputs = _inputs(settings)
    report_path = settings.metadata_dir / "sim_mortality_2024_processing.json"
    old = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    if old and old["pipeline_version"] == PIPELINE_VERSION and old["inputs"] == inputs and not raw_built:
        validate_phase_9(settings)
        return old, False
    converted_quality = None
    if not csv_path.exists() or not silver.exists():
        geography = _geography(settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv")
        result = convert_sim(original, csv_path, silver, geography)
        converted_quality = result["quality"]
    artifacts = _validate_converted(settings, source, count_csv=True)
    outputs = {}
    with duckdb.connect() as connection:
        _views(connection, settings)
        summary = _summary(connection)
        quality = _conversion_quality(connection, settings)
        if converted_quality is not None and converted_quality != quality:
            raise ValueError("SIM conversion quality differs from independent audit")
        for level in LEVELS:
            path = settings.data_dir / "gold" / "mortalidade" / f"mortalidade_{level}.csv"
            _write_csv(connection, _gold_query(level), path)
            outputs[level] = _artifact(path, settings.root_dir, _csv_rows(path))
        country = settings.root_dir / outputs["brasil"]["path"]
        national = connection.execute(f"SELECT * FROM read_csv('{_literal(country)}')").fetchone()
        if national[3] != summary["live_births"] or national[4] != summary["nonfetal"]:
            raise ValueError("SIM national Gold does not reconcile")
        state = connection.execute(f"SELECT SUM(nascidos_vivos), SUM(obitos_nao_fetais), SUM(obitos_infantis), SUM(obitos_neonatais) FROM read_csv('{_literal(settings.root_dir / outputs['estado']['path'])}')").fetchone()
        if state != (summary["live_births"] - summary["unmatched_live_births"],
                     summary["nonfetal"] - summary["unallocated_deaths"],
                     summary["infant"] - summary["unallocated_infant"],
                     summary["neonatal"] - summary["unallocated_neonatal"]):
            raise ValueError("SIM state totals do not reconcile after unmatched residence")
    report = {"pipeline_version": PIPELINE_VERSION, "processed_at": datetime.now(timezone.utc).isoformat(),
              "reference_period": "2024", "inputs": inputs, "source": {key: value for key, value in source.items() if key != "fields"},
              "artifacts": artifacts, "conversion_quality": quality, "summary": summary, "gold": outputs}
    _write_json_atomic(report_path, report)
    get_logger("transformation.sim").info("SIM Phase 9 built", extra={"pipeline": "sim_2024",
        "task": "reconcile", "source": "SIM/SINASC", "rows_in": source["rows"],
        "rows_out": summary["deaths_in_2024"], "status": "success"})
    return report, True


def validate_phase_9(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    report = json.loads((settings.metadata_dir / "sim_mortality_2024_processing.json").read_text(encoding="utf-8"))
    source = _validate_source(settings)
    if report["pipeline_version"] != PIPELINE_VERSION or report["inputs"] != _inputs(settings):
        raise ValueError("SIM Phase 9 inputs differ")
    artifacts = _validate_converted(settings, source, count_csv=True)
    if artifacts != report["artifacts"]:
        raise ValueError("SIM conversion checksums differ")
    with duckdb.connect() as connection:
        _views(connection, settings)
        summary = _summary(connection)
        if summary != report["summary"]:
            raise ValueError("SIM national summary differs")
        if _conversion_quality(connection, settings) != report["conversion_quality"]:
            raise ValueError("SIM conversion quality differs")
        for level, item in report["gold"].items():
            path = settings.root_dir / item["path"]
            if _artifact(path, settings.root_dir, _csv_rows(path)) != item:
                raise ValueError(f"SIM Gold artifact differs: {level}")
            expected = connection.execute(_gold_query(level)).fetchall()
            actual = connection.execute(f"SELECT * FROM read_csv('{_literal(path)}', types={{'codigo_territorio': 'VARCHAR'}}) ORDER BY 2").fetchall()
            if expected != actual:
                first = next(((left, right) for left, right in zip(expected, actual) if left != right), None)
                raise ValueError(f"SIM Gold content differs: {level}; first={first}; rows={len(expected)}/{len(actual)}")
    return report
