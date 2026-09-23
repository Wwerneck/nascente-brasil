from pathlib import Path

import pandas as pd
import pytest


GOLD = Path("data/gold/nascimentos/nascimentos_brasil.csv")


@pytest.mark.skipif(not GOLD.exists(), reason="Gold de nascimentos ainda não construído")
def test_national_birth_indicators_have_valid_denominators() -> None:
    row = pd.read_csv(GOLD).iloc[0]
    assert row["nascidos_vivos"] == 2_389_325
    pairs = [
        ("nascidos_vivos_parto_cesareo", "tipo_parto_informado"),
        ("nascidos_vivos_prematuros", "gestacao_informada"),
        ("nascidos_vivos_baixo_peso", "peso_informado"),
        ("apgar5_menor_7", "apgar5_informado"),
        ("prenatal_7_mais", "prenatal_informado"),
    ]
    for numerator, denominator in pairs:
        assert 0 <= row[numerator] <= row[denominator] <= row["nascidos_vivos"]


@pytest.mark.skipif(not GOLD.exists(), reason="Gold de nascimentos ainda não construído")
def test_national_birth_percentages_match_counts() -> None:
    row = pd.read_csv(GOLD).iloc[0]
    expected = 100 * row["nascidos_vivos_parto_cesareo"] / row["tipo_parto_informado"]
    assert row["percentual_cesareas"] == pytest.approx(expected, abs=0.0001)
