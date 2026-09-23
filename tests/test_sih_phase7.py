from __future__ import annotations

from datetime import date
from decimal import Decimal
import struct

from nascente_brasil.conversion.sih import _silver_row
from nascente_brasil.ingestion.sih import EXPECTED_FIELDS, validate_dbc


def make_dbc_header(path):
    header_length = 32 + 32 * len(EXPECTED_FIELDS) + 1
    header = bytearray(header_length)
    header[0] = 0x03
    header[4:8] = struct.pack("<I", 1)
    header[8:10] = struct.pack("<H", header_length)
    header[10:12] = struct.pack("<H", 702)
    for index, name in enumerate(EXPECTED_FIELDS):
        position = 32 + index * 32
        encoded = name.encode("ascii")
        header[position:position + len(encoded)] = encoded
        header[position + 11] = ord("C")
        header[position + 16] = 1
    header[-1] = 0x0D
    path.write_bytes(header)


def row_fixture():
    row = dict.fromkeys(EXPECTED_FIELDS, "")
    row.update({
        "ANO_CMPT": "2024", "MES_CMPT": "01", "N_AIH": "1224100061118", "IDENT": "1",
        "UF_ZI": "120000", "MUNIC_RES": "120060", "MUNIC_MOV": "120060", "SEXO": "3",
        "UTI_MES_TO": 2, "UTI_INT_TO": 0, "DIAR_ACOM": 1, "QT_DIARIAS": 3,
        "PROC_SOLIC": "0301060010", "PROC_REA": "0301060010", "VAL_SH": Decimal("35.65"),
        "VAL_SP": Decimal("11.62"), "VAL_TOT": Decimal("47.27"), "VAL_UTI": Decimal("0"),
        "DT_INTER": "20240118", "DT_SAIDA": "20240120", "DIAG_PRINC": "O140",
        "DIAG_SECUN": "0000", "IDADE": 29, "DIAS_PERM": 2, "MORTE": 0, "NUM_FILHOS": 1,
        "CNES": "2000121", "ETNIA": "0000", "SEQ_AIH5": "000", "CBOR": "000000",
    })
    return row


def quality_fixture():
    return {"invalid_dates": {"DT_INTER": 0, "DT_SAIDA": 0}, "invalid_primary_diagnosis": 0,
            "invalid_secondary_diagnosis": 0, "discharge_before_admission": 0,
            "unmatched_residence": 0, "unmatched_establishment": 0, "duplicate_aih_in_partition": 0}


def test_sih_dbc_header_contract(tmp_path):
    path = tmp_path / "RDAC2401.dbc"
    make_dbc_header(path)
    check = validate_dbc(path, minimum_size=1)
    assert check.records == 1
    assert check.record_length == 702
    content = bytearray(path.read_bytes())
    content[32] = ord("X")
    path.write_bytes(content)
    try:
        validate_dbc(path, minimum_size=1)
        assert False, "schema drift should fail"
    except ValueError as exc:
        assert "schema drift" in str(exc)


def test_sih_silver_row_types_codes_and_geography():
    quality = quality_fixture()
    result = _silver_row(row_fixture(), "RDAC2401.dbc", {"120060": "1200607"}, quality)
    assert result["competencia"] == "202401"
    assert result["codigo_ibge_residencia"] == "1200607"
    assert result["data_internacao"] == date(2024, 1, 18)
    assert result["valor_total"] == Decimal("47.27")
    assert result["diagnostico_principal"] == "O140"
    assert result["diagnostico_secundario"] is None
    assert result["sequencia_aih5"] is None
    assert quality["invalid_primary_diagnosis"] == 0


def test_sih_silver_row_audits_invalid_values_without_inventing_data():
    row = row_fixture()
    row.update({"DT_INTER": "20241340", "DT_SAIDA": "20240101", "DIAG_PRINC": "BAD!",
                "DIAGSEC1": "?", "MUNIC_RES": "999999", "MUNIC_MOV": "000000"})
    quality = quality_fixture()
    result = _silver_row(row, "RDAC2401.dbc", {}, quality)
    assert result["data_internacao"] is None
    assert result["codigo_ibge_residencia"] is None
    assert result["codigo_municipio_estabelecimento"] is None
    assert quality["invalid_dates"]["DT_INTER"] == 1
    assert quality["invalid_primary_diagnosis"] == 1
    assert quality["invalid_secondary_diagnosis"] == 1
    assert quality["unmatched_residence"] == 1
