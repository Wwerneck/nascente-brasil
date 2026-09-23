from __future__ import annotations

import duckdb

from nascente_brasil.conversion.sim import _silver_row
from nascente_brasil.transformation.sim_pipeline import _gold_query


def test_sim_silver_preserves_unknown_geography_and_invalid_dates():
    quality = {"invalid_dates": {"DTOBITO": 0, "DTNASC": 0, "DTINVESTIG": 0},
               "unmatched_residence": 0, "unmatched_occurrence": 0,
               "birth_after_death": 0, "missing_basic_cause": 0}
    row = {"DTOBITO": "01022024", "DTNASC": "bad", "DTINVESTIG": "",
           "CODMUNRES": "999999", "CODMUNOCOR": "110001", "CAUSABAS": "O720",
           "TIPOBITO": "2", "IDADE": "430", "SEXO": "2", "CAUSABAS_O": "O720",
           "CAUSAMAT": "", "OBITOGRAV": "2", "OBITOPUERP": "1"}
    result = _silver_row(row, {"110001": "1100015"}, quality)
    assert result["codigo_ibge_residencia"] is None
    assert result["codigo_ibge_ocorrencia"] == "1100015"
    assert result["causa_basica"] == "O720"
    assert quality["invalid_dates"]["DTNASC"] == 1
    assert quality["unmatched_residence"] == 1


def test_gold_uses_births_as_denominator_and_omits_fetal_count():
    with duckdb.connect() as connection:
        connection.execute("""
            CREATE TABLE births AS SELECT * FROM (VALUES
                ('1100015',), ('1100015',), ('1100015',), ('1100015',)
            ) t(codigo_ibge)
        """)
        connection.execute("""
            CREATE TABLE municipio AS SELECT '1100015' AS codigo_ibge,
                '1' AS codigo_regiao, 'Norte' AS regiao, 'RO' AS uf,
                'Rondonia' AS nome_uf, 'Municipio A' AS municipio
        """)
        connection.execute("""
            CREATE TABLE deaths AS SELECT * FROM (VALUES
                ('1100015', '2', 1, 0, 0, 1, 1, 1),
                ('1100015', '2', 0, 1, 0, 0, 0, 0),
                (NULL, '2', 0, 0, 0, 1, 1, 0)
            ) t(codigo_ibge_residencia, tipo_obito, obito_causa_obstetrica,
                obito_materno_tardio_sequela, causa_indireta_candidata,
                obito_infantil, obito_neonatal, obito_neonatal_precoce)
        """)
        country = connection.execute(_gold_query("brasil"))
        columns = [column[0] for column in country.description]
        national = dict(zip(columns, country.fetchone()))
        local = connection.execute(_gold_query("municipio"))
        local_row = dict(zip([column[0] for column in local.description], local.fetchone()))
    assert "obitos_fetais" not in national
    assert national["nascidos_vivos"] == 4
    assert national["obitos_infantis"] == 2
    assert national["taxa_observada_mortalidade_infantil_por_mil_nv"] == 500
    assert local_row["obitos_infantis"] == 1
