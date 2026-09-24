"""Load the approved public snapshot into an empty managed PostgreSQL database."""

from __future__ import annotations

import csv
from pathlib import Path

import psycopg
from psycopg import sql

from nascente_brasil.config import get_postgres_dsn
from nascente_brasil.database.postgres import DDL, SCHEMAS


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_LEVELS = ("brasil", "regiao", "estado")


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
