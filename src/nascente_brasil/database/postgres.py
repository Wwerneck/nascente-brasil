"""Transactional PostgreSQL publication of approved reference and Gold CSVs."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import psycopg
from psycopg import sql

from nascente_brasil.config import Settings, get_postgres_dsn, get_settings
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


SCHEMAS = ("raw", "staging", "intermediate", "analytics", "metadata")
LEVELS = ("brasil", "regiao", "estado", "municipio")


def dsn() -> str:
    return get_postgres_dsn()


DDL = """
CREATE TABLE IF NOT EXISTS analytics.dim_municipio (
  codigo_ibge varchar(7) PRIMARY KEY, codigo_sinasc_6 varchar(6) NOT NULL UNIQUE,
  municipio text NOT NULL, codigo_uf varchar(2) NOT NULL, uf varchar(2) NOT NULL,
  nome_uf text NOT NULL, codigo_regiao varchar(1) NOT NULL, regiao text NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics.morbidades (
  nivel_territorial text NOT NULL, competencia integer NOT NULL,
  codigo_territorio text NOT NULL, territorio text NOT NULL,
  grupo_morbidade text NOT NULL, subgrupo text NOT NULL,
  registros_aih bigint NOT NULL, denominador_aih_obstetricas bigint NOT NULL,
  proporcao_aih_obstetricas_pct numeric, dias_permanencia bigint NOT NULL,
  valor_total numeric(18,2) NOT NULL, obitos_hospitalares bigint NOT NULL,
  PRIMARY KEY (nivel_territorial, competencia, codigo_territorio, grupo_morbidade, subgrupo)
);
CREATE TABLE IF NOT EXISTS analytics.mortalidade (
  nivel_territorial text NOT NULL, ano integer NOT NULL,
  codigo_territorio text NOT NULL, territorio text NOT NULL,
  nascidos_vivos bigint NOT NULL, obitos_nao_fetais bigint NOT NULL,
  obitos_causa_obstetrica_cid_o bigint NOT NULL,
  obitos_maternos_tardios_sequelas bigint NOT NULL,
  causas_indiretas_candidatas bigint NOT NULL, obitos_infantis bigint NOT NULL,
  obitos_neonatais bigint NOT NULL, obitos_neonatais_precoces bigint NOT NULL,
  obitos_pos_neonatais bigint NOT NULL,
  razao_observada_causa_obstetrica_por_100mil_nv numeric,
  taxa_observada_mortalidade_infantil_por_mil_nv numeric,
  taxa_observada_mortalidade_neonatal_por_mil_nv numeric,
  PRIMARY KEY (nivel_territorial, ano, codigo_territorio)
);
CREATE TABLE IF NOT EXISTS analytics.nascimentos (
  nivel_territorial text NOT NULL, ano integer NOT NULL, codigo_territorio text NOT NULL,
  territorio text NOT NULL, nascidos_vivos bigint NOT NULL, tipo_parto_informado bigint NOT NULL,
  nascidos_vivos_parto_vaginal bigint NOT NULL, nascidos_vivos_parto_cesareo bigint NOT NULL,
  percentual_cesareas numeric, gestacao_informada bigint NOT NULL,
  nascidos_vivos_prematuros bigint NOT NULL, percentual_prematuridade numeric,
  peso_informado bigint NOT NULL, nascidos_vivos_baixo_peso bigint NOT NULL,
  percentual_baixo_peso numeric, peso_medio_g numeric, apgar5_informado bigint NOT NULL,
  apgar5_menor_7 bigint NOT NULL, percentual_apgar5_menor_7 numeric,
  prenatal_informado bigint NOT NULL, prenatal_7_mais bigint NOT NULL,
  percentual_prenatal_7_mais numeric, idade_mae_informada bigint NOT NULL,
  nascidos_vivos_maes_adolescentes bigint NOT NULL,
  nascidos_vivos_idade_materna_avancada bigint NOT NULL,
  tipo_gravidez_informado bigint NOT NULL, nascidos_vivos_gestacao_multipla bigint NOT NULL,
  PRIMARY KEY (nivel_territorial, ano, codigo_territorio)
);
CREATE TABLE IF NOT EXISTS metadata.load_runs (
  run_id text PRIMARY KEY, loaded_at timestamptz NOT NULL, source_path text NOT NULL,
  target_table text NOT NULL, nivel_territorial text, source_rows bigint NOT NULL,
  loaded_rows bigint NOT NULL, sha256 char(64) NOT NULL
);
CREATE OR REPLACE VIEW analytics.dim_estado AS
SELECT DISTINCT codigo_uf, uf, nome_uf, codigo_regiao, regiao FROM analytics.dim_municipio;
CREATE OR REPLACE VIEW analytics.dim_regiao AS
SELECT DISTINCT codigo_regiao, regiao FROM analytics.dim_municipio;
"""


def _rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj)
        next(reader)
        return sum(1 for _ in reader)


def _copy_csv(connection: psycopg.Connection, path: Path, table: str, columns: list[str],
              *, level: str | None = None) -> int:
    count = _rows(path)
    target = sql.Identifier("analytics", table)
    identifiers = [sql.Identifier(column) for column in columns]
    with connection.cursor() as cursor, path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        copy_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(target, sql.SQL(",").join(identifiers))
        with cursor.copy(copy_sql) as copy:
            for row in reader:
                values = ([level] if level is not None else []) + [row[column] or None for column in reader.fieldnames]
                copy.write_row(values)
    return count


def load_phase_11(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    municipality = settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv"
    inputs = [(municipality, "dim_municipio", None)]
    for domain in ("nascimentos", "morbidades", "mortalidade"):
        inputs.extend((settings.data_dir / "gold" / domain / f"{domain}_{level}.csv", domain, level)
                      for level in LEVELS)
    run_at = datetime.now(timezone.utc)
    loaded = []
    with psycopg.connect(dsn()) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                for schema in SCHEMAS:
                    cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
                cursor.execute(DDL)
                cursor.execute("TRUNCATE analytics.nascimentos, analytics.morbidades, analytics.mortalidade, analytics.dim_municipio CASCADE")
                cursor.execute("TRUNCATE metadata.load_runs")
            for path, table, level in inputs:
                with path.open("r", encoding="utf-8", newline="") as file_obj:
                    source_columns = next(csv.reader(file_obj))
                columns = (["nivel_territorial"] if level is not None else []) + source_columns
                count = _copy_csv(connection, path, table, columns, level=level)
                item = {"path": path.relative_to(settings.root_dir).as_posix(), "table": f"analytics.{table}",
                        "level": level, "rows": count, "sha256": sha256_file(path)}
                loaded.append(item)
                run_id = hashlib_sha(item)
                with connection.cursor() as cursor:
                    cursor.execute("""INSERT INTO metadata.load_runs
                        (run_id, loaded_at, source_path, target_table, nivel_territorial,
                         source_rows, loaded_rows, sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (run_id, run_at, item["path"], item["table"], level, count, count, item["sha256"]))
            expected = {"dim_municipio": sum(i["rows"] for i in loaded if i["table"].endswith("dim_municipio")),
                        "nascimentos": sum(i["rows"] for i in loaded if i["table"].endswith("nascimentos")),
                        "morbidades": sum(i["rows"] for i in loaded if i["table"].endswith("morbidades")),
                        "mortalidade": sum(i["rows"] for i in loaded if i["table"].endswith("mortalidade"))}
            with connection.cursor() as cursor:
                actual = {}
                for table in expected:
                    cursor.execute(sql.SQL("SELECT COUNT(*) FROM analytics.{}").format(sql.Identifier(table)))
                    actual[table] = cursor.fetchone()[0]
            if expected != actual:
                raise ValueError(f"PostgreSQL row reconciliation differs: {expected} != {actual}")
    report = {"phase": 11, "loaded_at": run_at.isoformat(), "database": "nascente_brasil",
              "schemas": list(SCHEMAS), "inputs": loaded, "row_counts": expected}
    _write_json_atomic(settings.metadata_dir / "postgres_phase11_load.json", report)
    return report


def hashlib_sha(item: dict) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()


def validate_phase_11(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    report = json.loads((settings.metadata_dir / "postgres_phase11_load.json").read_text(encoding="utf-8"))
    with psycopg.connect(dsn()) as connection, connection.cursor() as cursor:
        for table, expected in report["row_counts"].items():
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM analytics.{}").format(sql.Identifier(table)))
            if cursor.fetchone()[0] != expected:
                raise ValueError(f"PostgreSQL count differs: {table}")
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT run_id), bool_and(source_rows = loaded_rows) FROM metadata.load_runs")
        runs = cursor.fetchone()
        if runs != (len(report["inputs"]), len(report["inputs"]), True):
            raise ValueError("PostgreSQL load audit differs")
        cursor.execute("SELECT COUNT(*) FROM analytics.dim_regiao")
        if cursor.fetchone()[0] != 5:
            raise ValueError("PostgreSQL region dimension differs")
        cursor.execute("SELECT SUM(obitos_infantis), SUM(nascidos_vivos) FROM analytics.mortalidade WHERE nivel_territorial='brasil'")
        if cursor.fetchone() != (30020, 2389325):
            raise ValueError("PostgreSQL national mortality differs")
        cursor.execute("SELECT nascidos_vivos FROM analytics.nascimentos WHERE nivel_territorial='brasil'")
        if cursor.fetchone()[0] != 2389325:
            raise ValueError("PostgreSQL national births differ")
    return report
