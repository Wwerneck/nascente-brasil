"""Streaming conversion of SIH DBC partitions to CSV.GZ and typed Parquet."""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
import gzip
import io
import os
from pathlib import Path
import re
import tempfile

import datasus_dbc
from dbfread import DBF
import pyarrow as pa
import pyarrow.parquet as pq

from nascente_brasil.ingestion.sih import EXPECTED_FIELDS, validate_dbc
from nascente_brasil.ingestion.sinasc import sha256_file


CID_PATTERN = re.compile(r"^[A-Z][0-9]{2}[0-9A-Z]?$")
DIAGNOSIS_FIELDS = ("DIAG_PRINC", "DIAG_SECUN", *(f"DIAGSEC{i}" for i in range(1, 10)))
SILVER_SCHEMA = pa.schema([
    pa.field("arquivo_fonte", pa.string(), False), pa.field("uf_arquivo", pa.string(), False),
    pa.field("competencia", pa.string(), False), pa.field("codigo_municipio_gestor", pa.string()),
    pa.field("especialidade_leito", pa.string()), pa.field("numero_aih", pa.string(), False),
    pa.field("tipo_aih", pa.string()), pa.field("codigo_municipio_residencia", pa.string()),
    pa.field("codigo_ibge_residencia", pa.string()), pa.field("sexo", pa.string()),
    pa.field("uti_dias", pa.int32()), pa.field("uci_dias", pa.int32()),
    pa.field("diarias_acompanhante", pa.int32()), pa.field("quantidade_diarias", pa.int32()),
    pa.field("procedimento_solicitado", pa.string()), pa.field("procedimento_realizado", pa.string()),
    pa.field("valor_servicos_hospitalares", pa.decimal128(14, 2)),
    pa.field("valor_servicos_profissionais", pa.decimal128(14, 2)),
    pa.field("valor_total", pa.decimal128(14, 2)), pa.field("valor_uti", pa.decimal128(14, 2)),
    pa.field("data_internacao", pa.date32()), pa.field("data_saida", pa.date32()),
    pa.field("diagnostico_principal", pa.string()), pa.field("diagnostico_secundario", pa.string()),
    pa.field("motivo_cobranca", pa.string()), pa.field("natureza_juridica", pa.string()),
    pa.field("gestao", pa.string()), pa.field("codigo_municipio_estabelecimento", pa.string()),
    pa.field("codigo_ibge_estabelecimento", pa.string()), pa.field("unidade_idade", pa.string()),
    pa.field("idade", pa.int16()), pa.field("dias_permanencia", pa.int32()),
    pa.field("obito", pa.int8()), pa.field("carater_internacao", pa.string()),
    pa.field("numero_filhos", pa.int16()), pa.field("instrucao", pa.string()),
    pa.field("cid_notificacao", pa.string()), pa.field("gestacao_risco", pa.string()),
    pa.field("sequencia_aih5", pa.string()), pa.field("cbor", pa.string()),
    pa.field("codigo_cnes", pa.string()), pa.field("infeccao_hospitalar", pa.string()),
    pa.field("cid_associado", pa.string()), pa.field("cid_morte", pa.string()),
    pa.field("complexidade", pa.string()), pa.field("financiamento", pa.string()),
    pa.field("raca_cor", pa.string()), pa.field("etnia", pa.string()),
    *[pa.field(f"diagnostico_secundario_{i}", pa.string()) for i in range(1, 10)],
    *[pa.field(f"tipo_diagnostico_secundario_{i}", pa.string()) for i in range(1, 10)],
])


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _code(value, *sentinels: str) -> str | None:
    text = _text(value)
    return None if text is None or text in sentinels else text


def _date(value, quality: dict, field: str) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        quality["invalid_dates"][field] += 1
        return None


def _integer(value) -> int | None:
    return None if value is None or str(value).strip() == "" else int(value)


def _decimal(value) -> Decimal | None:
    return None if value is None or str(value).strip() == "" else Decimal(value).quantize(Decimal("0.01"))


def _silver_row(row: dict, source_file: str, geography: dict[str, str], quality: dict) -> dict:
    residence = _code(row["MUNIC_RES"], "000000")
    establishment = _code(row["MUNIC_MOV"], "000000")
    principal = _code(row["DIAG_PRINC"], "0000")
    if principal is None or not CID_PATTERN.fullmatch(principal):
        quality["invalid_primary_diagnosis"] += 1
    for field in DIAGNOSIS_FIELDS[1:]:
        diagnosis = _code(row[field], "0000", "0")
        if diagnosis is not None and not CID_PATTERN.fullmatch(diagnosis):
            quality["invalid_secondary_diagnosis"] += 1
    admission = _date(row["DT_INTER"], quality, "DT_INTER")
    discharge = _date(row["DT_SAIDA"], quality, "DT_SAIDA")
    if admission and discharge and discharge < admission:
        quality["discharge_before_admission"] += 1
    if residence and residence not in geography:
        quality["unmatched_residence"] += 1
    if establishment and establishment not in geography:
        quality["unmatched_establishment"] += 1
    values = {
        "arquivo_fonte": source_file, "uf_arquivo": source_file[2:4],
        "competencia": f"{_text(row['ANO_CMPT'])}{_text(row['MES_CMPT'])}",
        "codigo_municipio_gestor": _code(row["UF_ZI"], "000000"),
        "especialidade_leito": _text(row["ESPEC"]), "numero_aih": _text(row["N_AIH"]),
        "tipo_aih": _text(row["IDENT"]), "codigo_municipio_residencia": residence,
        "codigo_ibge_residencia": geography.get(residence), "sexo": _text(row["SEXO"]),
        "uti_dias": _integer(row["UTI_MES_TO"]), "uci_dias": _integer(row["UTI_INT_TO"]),
        "diarias_acompanhante": _integer(row["DIAR_ACOM"]), "quantidade_diarias": _integer(row["QT_DIARIAS"]),
        "procedimento_solicitado": _text(row["PROC_SOLIC"]), "procedimento_realizado": _text(row["PROC_REA"]),
        "valor_servicos_hospitalares": _decimal(row["VAL_SH"]), "valor_servicos_profissionais": _decimal(row["VAL_SP"]),
        "valor_total": _decimal(row["VAL_TOT"]), "valor_uti": _decimal(row["VAL_UTI"]),
        "data_internacao": admission, "data_saida": discharge, "diagnostico_principal": principal,
        "diagnostico_secundario": _code(row["DIAG_SECUN"], "0000"), "motivo_cobranca": _text(row["COBRANCA"]),
        "natureza_juridica": _text(row["NAT_JUR"]), "gestao": _text(row["GESTAO"]),
        "codigo_municipio_estabelecimento": establishment,
        "codigo_ibge_estabelecimento": geography.get(establishment), "unidade_idade": _text(row["COD_IDADE"]),
        "idade": _integer(row["IDADE"]), "dias_permanencia": _integer(row["DIAS_PERM"]),
        "obito": _integer(row["MORTE"]), "carater_internacao": _text(row["CAR_INT"]),
        "numero_filhos": _integer(row["NUM_FILHOS"]), "instrucao": _text(row["INSTRU"]),
        "cid_notificacao": _code(row["CID_NOTIF"], "0000"), "gestacao_risco": _text(row["GESTRISCO"]),
        "sequencia_aih5": _code(row["SEQ_AIH5"], "000"), "cbor": _code(row["CBOR"], "000000"),
        "codigo_cnes": _text(row["CNES"]), "infeccao_hospitalar": _text(row["INFEHOSP"]),
        "cid_associado": _code(row["CID_ASSO"], "0000"), "cid_morte": _code(row["CID_MORTE"], "0000"),
        "complexidade": _text(row["COMPLEX"]), "financiamento": _text(row["FINANC"]),
        "raca_cor": _text(row["RACA_COR"]), "etnia": _code(row["ETNIA"], "0000"),
    }
    for index in range(1, 10):
        values[f"diagnostico_secundario_{index}"] = _code(row[f"DIAGSEC{index}"], "0000", "0")
        values[f"tipo_diagnostico_secundario_{index}"] = _code(row[f"TPDISEC{index}"], "0")
    return values


def _raw_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value).strip()


def convert_partition(dbc_path: Path, csv_gz_path: Path, parquet_path: Path,
                      geography: dict[str, str], *, batch_size: int = 25_000) -> dict:
    source_check = validate_dbc(dbc_path)
    csv_gz_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dbf: Path | None = None
    temp_csv: Path | None = None
    temp_parquet: Path | None = None
    writer: pq.ParquetWriter | None = None
    quality = {"invalid_dates": {"DT_INTER": 0, "DT_SAIDA": 0}, "invalid_primary_diagnosis": 0,
               "invalid_secondary_diagnosis": 0, "discharge_before_admission": 0,
               "unmatched_residence": 0, "unmatched_establishment": 0, "duplicate_aih_in_partition": 0}
    rows = 0
    seen_aih: set[str] = set()
    try:
        with tempfile.NamedTemporaryFile(dir=dbc_path.parent, suffix=".dbf.part", delete=False) as file_obj:
            temp_dbf = Path(file_obj.name)
        datasus_dbc.decompress(str(dbc_path), str(temp_dbf))
        table = DBF(temp_dbf, encoding="latin1", char_decode_errors="strict", load=False)
        if tuple(table.field_names) != EXPECTED_FIELDS or len(table) != source_check.records:
            raise ValueError(f"Decompressed SIH DBF differs from DBC header: {dbc_path.name}")
        with tempfile.NamedTemporaryFile(dir=csv_gz_path.parent, suffix=".csv.gz.part", delete=False) as csv_file:
            temp_csv = Path(csv_file.name)
            with gzip.GzipFile(filename="", mode="wb", fileobj=csv_file, mtime=0) as gz_file:
                with io.TextIOWrapper(gz_file, encoding="utf-8", newline="") as text_file:
                    csv_writer = csv.writer(text_file, lineterminator="\n")
                    csv_writer.writerow([field.lower() for field in EXPECTED_FIELDS])
                    batch = []
                    with tempfile.NamedTemporaryFile(dir=parquet_path.parent, suffix=".parquet.part", delete=False) as parquet_file:
                        temp_parquet = Path(parquet_file.name)
                    writer = pq.ParquetWriter(temp_parquet, SILVER_SCHEMA, compression="zstd")
                    for record in table:
                        row = dict(record)
                        csv_writer.writerow([_raw_value(row[field]) for field in EXPECTED_FIELDS])
                        number = _text(row["N_AIH"])
                        if number in seen_aih:
                            quality["duplicate_aih_in_partition"] += 1
                        seen_aih.add(number)
                        batch.append(_silver_row(row, dbc_path.name, geography, quality))
                        rows += 1
                        if len(batch) >= batch_size:
                            writer.write_table(pa.Table.from_pylist(batch, schema=SILVER_SCHEMA))
                            batch.clear()
                    if batch:
                        writer.write_table(pa.Table.from_pylist(batch, schema=SILVER_SCHEMA))
        writer.close()
        writer = None
        if rows != source_check.records or pq.ParquetFile(temp_parquet).metadata.num_rows != rows:
            raise ValueError(f"SIH partition row reconciliation failed: {dbc_path.name}")
        os.replace(temp_csv, csv_gz_path)
        temp_csv = None
        os.replace(temp_parquet, parquet_path)
        temp_parquet = None
        return {"rows": rows, "quality": quality,
                "raw_csv": {"path": csv_gz_path, "bytes": csv_gz_path.stat().st_size, "sha256": sha256_file(csv_gz_path)},
                "silver_parquet": {"path": parquet_path, "bytes": parquet_path.stat().st_size, "sha256": sha256_file(parquet_path)}}
    finally:
        if writer is not None:
            writer.close()
        for temp in (temp_dbf, temp_csv, temp_parquet):
            if temp is not None:
                temp.unlink(missing_ok=True)
