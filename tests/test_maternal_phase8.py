from __future__ import annotations

import duckdb
import pytest

from nascente_brasil.transformation.maternal_cid import classify
from nascente_brasil.transformation.maternal_pipeline import _gold_query


@pytest.mark.parametrize(("code", "group", "subgroup", "morbidity"), [
    ("O140", "transtornos_hipertensivos", "pre_eclampsia", True),
    ("O151", "transtornos_hipertensivos", "eclampsia", True),
    ("O130", "transtornos_hipertensivos", "hipertensao_gestacional", True),
    ("O120", "outras_condicoes_maternas", "edema_proteinuria_sem_hipertensao", True),
    ("O244", "disturbios_metabolicos", "diabetes_na_gestacao", True),
    ("O720", "hemorragias", "hemorragia_pos_parto", True),
    ("O850", "infeccoes", "infeccao_puerperal", True),
    ("O880", "complicacoes_vasculares", "embolia_obstetrica", True),
    ("O990", "outras_condicoes_maternas", "anemia_complicando_gestacao", True),
    ("O800", "parto", "via_ou_tipo_de_parto", False),
    ("O340", "assistencia_obstetrica", "assistencia_materna_ou_fetal", False),
    ("O420", "complicacoes_gestacao", "liquido_membranas_ou_placenta", True),
])
def test_classification(code, group, subgroup, morbidity):
    result = classify(code)
    assert result[0] == group
    assert result[1] == subgroup
    assert result[3] is morbidity


def test_non_obstetric_code_rejected():
    with pytest.raises(ValueError, match="Invalid obstetric CID"):
        classify("P000")


def test_gold_denominator_includes_delivery_but_numerator_does_not():
    with duckdb.connect() as connection:
        connection.execute("""
            CREATE TABLE fato AS SELECT * FROM (VALUES
                ('202401', '1100015', 'parto', 'parto', false, 8, 16, 80.00, 0),
                ('202401', '1100015', 'hemorragias', 'hemorragia_pos_parto', true, 2, 5, 20.00, 1)
            ) AS t(competencia, codigo_ibge, grupo_morbidade, subgrupo, e_morbidade,
                   registros_aih, dias_permanencia, valor_total, obitos_hospitalares)
        """)
        connection.execute("""
            CREATE TABLE municipio AS SELECT '1100015' AS codigo_ibge, '1' AS codigo_regiao,
                'Norte' AS regiao, 'RO' AS uf, 'Rondonia' AS nome_uf,
                'Alta Floresta D Oeste' AS municipio
        """)
        rows = connection.execute(_gold_query("municipio")).fetchall()
    assert len(rows) == 1
    assert rows[0][3:7] == ("hemorragias", "hemorragia_pos_parto", 2, 10)
    assert rows[0][7] == 20.0
