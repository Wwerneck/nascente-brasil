"""Load the approved public snapshot into an empty managed PostgreSQL database."""

from __future__ import annotations

import csv
from pathlib import Path

import psycopg
from psycopg import sql

from nascente_brasil.config import get_postgres_dsn


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_LEVELS = ("brasil", "regiao", "estado")
SCHEMAS = ("analytics", "metadata")
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
CREATE OR REPLACE VIEW analytics.dim_estado AS
SELECT DISTINCT codigo_uf, uf, nome_uf, codigo_regiao, regiao FROM analytics.dim_municipio;
CREATE OR REPLACE VIEW analytics.dim_regiao AS
SELECT DISTINCT codigo_regiao, regiao FROM analytics.dim_municipio;
"""


def insert_csv(connection, table: str, path: Path, level: str | None = None) -> None:
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        columns = (["nivel_territorial"] if level else []) + list(reader.fieldnames or [])
        rows = []
        for row in reader:
            values = ([level] if level else []) + [row[column] or None for column in reader.fieldnames or []]
            rows.append(values)
    query = sql.SQL("INSERT INTO analytics.{} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with connection.cursor() as cursor:
        cursor.executemany(query, rows)


def main() -> None:
    with psycopg.connect(get_postgres_dsn(), connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(20240924)")
            for schema in SCHEMAS:
                cursor.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
                )
            cursor.execute(DDL)
            cursor.execute("SELECT COUNT(*) FROM analytics.nascimentos")
            populated = cursor.fetchone()[0] > 0

        if not populated:
            insert_csv(
                connection,
                "dim_municipio",
                ROOT / "data/reference/ibge/dim_municipio_2024.csv",
            )
            for domain in ("nascimentos", "mortalidade", "morbidades"):
                for level in PUBLIC_LEVELS:
                    insert_csv(
                        connection,
                        domain,
                        ROOT / f"data/deploy/{domain}_{level}.csv",
                        level,
                    )

        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS dbt_marts")
            cursor.execute("DROP TABLE IF EXISTS dbt_marts.mart_nascimentos_territoriais")
            cursor.execute("""CREATE TABLE dbt_marts.mart_nascimentos_territoriais AS
                SELECT * FROM analytics.nascimentos
                WHERE tipo_parto_informado <= nascidos_vivos
                  AND gestacao_informada <= nascidos_vivos
                  AND peso_informado <= nascidos_vivos
                  AND apgar5_informado <= nascidos_vivos
                  AND prenatal_informado <= nascidos_vivos
                  AND idade_mae_informada <= nascidos_vivos
                  AND tipo_gravidez_informado <= nascidos_vivos""")
            cursor.execute("DROP TABLE IF EXISTS dbt_marts.mart_mortalidade_territorial")
            cursor.execute("""CREATE TABLE dbt_marts.mart_mortalidade_territorial AS
                SELECT *, CASE WHEN nascidos_vivos > 0
                    THEN round(1000.0 * obitos_pos_neonatais / nascidos_vivos, 4)
                    END AS taxa_observada_mortalidade_pos_neonatal_por_mil_nv
                FROM analytics.mortalidade
                WHERE obitos_neonatais <= obitos_infantis
                  AND obitos_neonatais_precoces <= obitos_neonatais""")
            cursor.execute("DROP TABLE IF EXISTS dbt_marts.mart_morbidades_territoriais")
            cursor.execute("""CREATE TABLE dbt_marts.mart_morbidades_territoriais AS
                SELECT * FROM analytics.morbidades
                WHERE registros_aih >= 0 AND denominador_aih_obstetricas > 0""")
    print("Cloud analytical database is ready.")


if __name__ == "__main__":
    main()
