"""Inspect SIM age encoding and territorial coverage during Phase 9 validation."""

from __future__ import annotations

import duckdb

from nascente_brasil.config import get_settings
from nascente_brasil.transformation.sim_pipeline import _gold_query, _views


def main() -> None:
    with duckdb.connect() as connection:
        _views(connection, get_settings())
        checks = {
            "age_units": "SELECT substr(idade_original, 1, 1), COUNT(*) FROM deaths GROUP BY 1 ORDER BY 1",
            "age_disagreement": """
                SELECT COUNT(*) FILTER (WHERE substr(idade_original, 1, 1) IN ('0','1','2','3')) AS encoded_infant,
                       COUNT(*) FILTER (WHERE idade_dias_datas BETWEEN 0 AND 364) AS dated_infant,
                       COUNT(*) FILTER (WHERE substr(idade_original, 1, 1) IN ('0','1','2','3')
                           AND idade_dias_datas > 364) AS encoded_only,
                       COUNT(*) FILTER (WHERE substr(idade_original, 1, 1) = '4'
                           AND idade_dias_datas BETWEEN 0 AND 364) AS dated_only_with_adult_code,
                       COUNT(*) FILTER (WHERE idade_original IS NULL AND idade_dias_datas BETWEEN 0 AND 364)
                           AS dated_without_code
                FROM deaths
            """,
            "neonatal_disagreement": """
                SELECT COUNT(*) FILTER (WHERE obito_neonatal = 1 AND substr(idade_original,1,1) NOT IN ('0','1','2')),
                       COUNT(*) FILTER (WHERE obito_neonatal_precoce = 1 AND substr(idade_original,1,1) NOT IN ('0','1','2')),
                       COUNT(*) FILTER (WHERE substr(idade_original,1,1) = '9' AND idade_dias_datas BETWEEN 0 AND 364)
                FROM deaths
            """,
            "unmatched_deaths": """
                SELECT COUNT(*), SUM(obito_causa_obstetrica), SUM(obito_infantil), SUM(obito_neonatal)
                FROM deaths WHERE codigo_ibge_residencia IS NULL
            """,
            "maternal_sex": """
                SELECT sexo, COUNT(*) FROM deaths
                WHERE regexp_full_match(causa_basica, 'O[0-9]{2}[0-9A-Z]?')
                GROUP BY 1 ORDER BY 1
            """,
        }
        for name, query in checks.items():
            print(name, connection.execute(query).fetchall())
        expected = connection.execute(_gold_query("regiao")).fetchall()
        actual = connection.execute("SELECT * FROM read_csv('data/gold/mortalidade/mortalidade_regiao.csv') ORDER BY 2").fetchall()
        print("regional_first_difference", next(((a, b) for a, b in zip(expected, actual) if a != b), None))


if __name__ == "__main__":
    main()
