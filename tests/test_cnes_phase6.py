from __future__ import annotations

import csv
from datetime import date

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nascente_brasil.config import get_settings
from nascente_brasil.ingestion.cnes import SOURCE_COLUMNS, validate_cnes_csv
from nascente_brasil.transformation.cnes_pipeline import (
    NUMERIC_COLUMNS, _geography, _load_and_type, _products, _sinasc_audit,
)


def source_row(competence: str, cnes: str, municipality: str = "ITAPAGE") -> dict:
    row = dict.fromkeys(SOURCE_COLUMNS, "")
    row.update({
        "COMP": competence, "REGIAO": "NORDESTE", "UF": "CE", "MUNICIPIO": municipality,
        "CNES": cnes, "NOME_ESTABELECIMENTO": "HOSPITAL TESTE", "RAZAO_SOCIAL": "HOSPITAL TESTE LTDA",
        "TP_GESTAO": "M", "CO_TIPO_UNIDADE": "05", "DS_TIPO_UNIDADE": "HOSPITAL GERAL",
        "NATUREZA_JURIDICA": "2062", "DESC_NATUREZA_JURIDICA": "PRIVADO",
        "NO_LOGRADOURO": "RUA A", "NU_ENDERECO": "1", "NO_BAIRRO": "CENTRO", "CO_CEP": "60000000",
        "LEITOS_EXISTENTES": "10", "LEITOS_SUS": "8", "UTI_TOTAL_EXIST": "3", "UTI_TOTAL_SUS": "2",
        "UTI_ADULTO_EXIST": "1", "UTI_ADULTO_SUS": "1", "UTI_PEDIATRICO_EXIST": "1",
        "UTI_PEDIATRICO_SUS": "0", "UTI_NEONATAL_EXIST": "1", "UTI_NEONATAL_SUS": "1",
        "UTI_QUEIMADO_EXIST": "0", "UTI_QUEIMADO_SUS": "0", "UTI_CORONARIANA_EXIST": "0",
        "UTI_CORONARIANA_SUS": "0",
    })
    return row


def write_source(path, rows):
    with path.open("w", encoding="latin1", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=SOURCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_dimension(path):
    pd.DataFrame([{
        "codigo_ibge": "2306306", "codigo_sinasc_6": "230630", "municipio": "Itapajé",
        "codigo_uf": "23", "uf": "CE", "nome_uf": "Ceará", "codigo_regiao": "2", "regiao": "Nordeste",
    }]).to_csv(path, index=False)


def test_cnes_typing_geography_and_temporal_products(tmp_path):
    source = tmp_path / "cnes.csv"
    dimension_path = tmp_path / "municipios.csv"
    rows = [source_row("202401", "0000001"), source_row("202402", "0000001")]
    rows[1]["NOME_ESTABELECIMENTO"] = "HOSPITAL TESTE NOVO"
    write_source(source, rows)
    write_dimension(dimension_path)
    frame, quality = _load_and_type(source)
    enriched, audit, metrics = _geography(frame, dimension_path)
    dimension, fact = _products(enriched)
    assert quality["uti_total_existing_component_mismatch"] == 0
    assert all(str(frame[column].dtype) == "Int64" for column in NUMERIC_COLUMNS)
    assert metrics["matched_rows"] == 2
    assert metrics["alias_rows"] == 2
    assert audit.iloc[0]["match_method"] == "explicit_alias"
    assert fact["codigo_ibge"].tolist() == ["2306306", "2306306"]
    assert len(dimension) == 1
    assert dimension.iloc[0]["competencias_observadas"] == 2
    assert dimension.iloc[0]["versoes_atributos"] == 2
    assert dimension.iloc[0]["nome_estabelecimento"] == "HOSPITAL TESTE NOVO"


def test_cnes_rejects_invalid_capacity_and_duplicate_grain(tmp_path):
    source = tmp_path / "cnes.csv"
    rows = [source_row("202401", "0000001"), source_row("202401", "0000001")]
    write_source(source, rows)
    with pytest.raises(ValueError, match="duplicated"):
        _load_and_type(source)


def test_cnes_raw_validation_checks_schema_competence_and_key(tmp_path):
    source = tmp_path / "cnes.csv"
    write_source(source, [source_row("202401", "0000001")])
    check = validate_cnes_csv(source, min_records=1, min_size=1, expected_competencies=("202401",))
    assert check.records == 1
    write_source(source, [source_row("202401", "0000001"), source_row("202401", "0000001")])
    with pytest.raises(ValueError, match="Duplicated"):
        validate_cnes_csv(source, min_records=1, min_size=1, expected_competencies=("202401",))
    bad = source_row("202401", "0000001")
    bad.pop("NO_EMAIL")
    with source.open("w", encoding="latin1", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(bad))
        writer.writeheader()
        writer.writerow(bad)
    with pytest.raises(ValueError, match="schema drift"):
        validate_cnes_csv(source, min_records=1, min_size=1, expected_competencies=("202401",))
    rows = [source_row("202401", "0000001")]
    rows[0]["LEITOS_EXISTENTES"] = "invalid"
    write_source(source, rows)
    with pytest.raises(ValueError, match="invalid or negative"):
        _load_and_type(source)


def test_sinasc_cnes_join_classifies_and_reconciles(tmp_path):
    parquet = tmp_path / "sinasc.parquet"
    pq.write_table(pa.Table.from_pylist([
        {"data_nascimento": date(2024, 1, 2), "codigo_estabelecimento": "0000001"},
        {"data_nascimento": date(2024, 2, 2), "codigo_estabelecimento": "0000001"},
        {"data_nascimento": date(2024, 1, 2), "codigo_estabelecimento": "9999999"},
        {"data_nascimento": date(2024, 1, 2), "codigo_estabelecimento": None},
        {"data_nascimento": None, "codigo_estabelecimento": "0000001"},
        {"data_nascimento": date(2024, 1, 2), "codigo_estabelecimento": "ABC"},
    ]), parquet)
    fact = pd.DataFrame([{"competencia": "202401", "codigo_cnes": "0000001"}])
    sql = get_settings().root_dir / "sql" / "duckdb" / "sinasc_2024_cnes_temporal_join.sql"
    audit = _sinasc_audit(parquet, fact, sql)
    counts = {row["match_status"]: row["registros"] for row in audit}
    assert sum(counts.values()) == 6
    assert counts == {
        "cnes_seen_other_competence": 1, "invalid_cnes_format": 1, "matched_same_competence": 1,
        "missing_birth_date": 1, "missing_cnes_code": 1, "not_in_hospital_beds_2024": 1,
    }
