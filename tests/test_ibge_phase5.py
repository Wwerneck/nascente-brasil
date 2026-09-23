from __future__ import annotations

import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nascente_brasil.config import get_settings
from nascente_brasil.ingestion.ibge import read_ufs
from nascente_brasil.transformation.ibge_pipeline import _dimensions, _join, _join_metrics


def sample_dimensions():
    dtb = pd.DataFrame([
        {"codigo_uf": "11", "nome_uf": "Rondonia", "codigo_ibge": "1100015", "municipio": "Municipio A"},
        {"codigo_uf": "12", "nome_uf": "Acre", "codigo_ibge": "1200013", "municipio": "Municipio B"},
    ])
    ufs = [
        {"id": 11, "sigla": "RO", "nome": "Rondonia", "regiao": {"id": 1, "nome": "Norte"}},
        {"id": 12, "sigla": "AC", "nome": "Acre", "regiao": {"id": 1, "nome": "Norte"}},
    ]
    return dtb, ufs


def test_dimensions_use_full_ibge_key_and_unique_sinasc_prefix():
    dtb, ufs = sample_dimensions()
    dims = _dimensions(dtb, ufs)
    assert dims["municipio"][0]["codigo_ibge"] == "1100015"
    assert dims["municipio"][0]["codigo_sinasc_6"] == "110001"
    assert len(dims["regiao"]) == 1
    assert len(dims["estado"]) == 2
    dtb.loc[2] = {"codigo_uf": "11", "nome_uf": "Rondonia", "codigo_ibge": "1100019", "municipio": "Duplicado"}
    with pytest.raises(ValueError, match="not unique"):
        _dimensions(dtb, ufs)
    dtb, ufs = sample_dimensions()
    dtb.loc[0, "nome_uf"] = "Nome divergente"
    dtb.loc[1, "nome_uf"] = "Acre"
    with pytest.raises(ValueError, match="names differ"):
        _dimensions(dtb, ufs)


def test_join_keeps_all_rows_and_classifies_failures(tmp_path):
    dtb, ufs = sample_dimensions()
    dims = _dimensions(dtb, ufs)
    parquet = tmp_path / "sinasc.parquet"
    pq.write_table(pa.Table.from_pylist([
        {"codigo_municipio_residencia": "110001", "codigo_municipio_nascimento": "110001"},
        {"codigo_municipio_residencia": "110000", "codigo_municipio_nascimento": "120001"},
        {"codigo_municipio_residencia": "999999", "codigo_municipio_nascimento": "abc"},
        {"codigo_municipio_residencia": None, "codigo_municipio_nascimento": "110000"},
    ]), parquet)
    sql = get_settings().root_dir / "sql" / "duckdb" / "sinasc_2024_territory_join.sql"
    rows = _join(parquet, dims, sql)
    metrics = _join_metrics(rows, dims, 4)
    assert metrics["residencia"]["matched_rows"] == 1
    assert metrics["residencia"]["unmatched_left"] == 3
    assert metrics["ocorrencia"]["matched_rows"] == 2
    assert metrics["ocorrencia"]["unmatched_left"] == 2
    assert {row["match_status"] for row in rows} == {
        "matched", "municipality_not_in_dtb", "unknown_uf", "missing_code", "invalid_format",
    }
    partial = next(row for row in rows if row["codigo_sinasc"] == "110000")
    assert partial["codigo_ibge"] is None
    assert partial["uf_prefixo"] == "RO"
    with pytest.raises(ValueError, match="does not reconcile"):
        _join_metrics(rows, dims, 5)


def test_ibge_uf_schema_rejects_incomplete_response(tmp_path):
    path = tmp_path / "ufs.json"
    path.write_text(json.dumps([{"id": 11, "sigla": "RO", "regiao": {"id": 1}}] * 27), encoding="utf-8")
    with pytest.raises(ValueError):
        read_ufs(path)
