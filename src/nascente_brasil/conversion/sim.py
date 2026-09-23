"""Streaming conversion of national SIM DBC to complete CSV and typed Silver."""

from __future__ import annotations

import csv
from datetime import date, datetime
import gzip
import io
import os
from pathlib import Path
import tempfile

import datasus_dbc
from dbfread import DBF
import pyarrow as pa
import pyarrow.parquet as pq

from nascente_brasil.ingestion.sim import validate_sim_dbc
from nascente_brasil.ingestion.sinasc import sha256_file


SILVER_SCHEMA = pa.schema([
    pa.field("arquivo_fonte", pa.string(), False),
    pa.field("tipo_obito", pa.string()),
    pa.field("data_obito", pa.date32()),
    pa.field("ano_obito", pa.int16()),
    pa.field("data_nascimento", pa.date32()),
    pa.field("idade_original", pa.string()),
    pa.field("sexo", pa.string()),
    pa.field("codigo_municipio_residencia", pa.string()),
    pa.field("codigo_ibge_residencia", pa.string()),
    pa.field("codigo_municipio_ocorrencia", pa.string()),
    pa.field("codigo_ibge_ocorrencia", pa.string()),
    pa.field("causa_basica", pa.string()),
    pa.field("causa_basica_original", pa.string()),
    pa.field("causa_materna_associada", pa.string()),
    pa.field("obito_gravidez", pa.string()),
    pa.field("obito_puerperio", pa.string()),
    pa.field("data_investigacao", pa.date32()),
])


def _text(value) -> str | None:
    result = str(value).strip() if value is not None else ""
    return result or None


def _date(value, quality: dict, field: str) -> date | None:
    value = _text(value)
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%d%m%Y").date()
    except ValueError:
        quality["invalid_dates"][field] += 1
        return None


def _ibge(code: str | None, geography: dict[str, str]) -> str | None:
    if code is None:
        return None
    if len(code) == 7 and code[:6] in geography and geography[code[:6]] == code:
        return code
    return geography.get(code) if len(code) == 6 else None


def _silver_row(row: dict, geography: dict[str, str], quality: dict) -> dict:
    death = _date(row["DTOBITO"], quality, "DTOBITO")
    birth = _date(row["DTNASC"], quality, "DTNASC")
    investigation = _date(row["DTINVESTIG"], quality, "DTINVESTIG")
    residence = _text(row["CODMUNRES"])
    occurrence = _text(row["CODMUNOCOR"])
    ibge_residence = _ibge(residence, geography)
    ibge_occurrence = _ibge(occurrence, geography)
    if residence and not ibge_residence:
        quality["unmatched_residence"] += 1
    if occurrence and not ibge_occurrence:
        quality["unmatched_occurrence"] += 1
    if birth and death and birth > death:
        quality["birth_after_death"] += 1
    cause = _text(row["CAUSABAS"])
    if not cause:
        quality["missing_basic_cause"] += 1
    return {"arquivo_fonte": "DOBR2024.dbc", "tipo_obito": _text(row["TIPOBITO"]),
            "data_obito": death, "ano_obito": death.year if death else None,
            "data_nascimento": birth, "idade_original": _text(row["IDADE"]),
            "sexo": _text(row["SEXO"]), "codigo_municipio_residencia": residence,
            "codigo_ibge_residencia": ibge_residence,
            "codigo_municipio_ocorrencia": occurrence,
            "codigo_ibge_ocorrencia": ibge_occurrence,
            "causa_basica": cause, "causa_basica_original": _text(row["CAUSABAS_O"]),
            "causa_materna_associada": _text(row["CAUSAMAT"]),
            "obito_gravidez": _text(row["OBITOGRAV"]),
            "obito_puerperio": _text(row["OBITOPUERP"]),
            "data_investigacao": investigation}


def convert_sim(dbc_path: Path, csv_path: Path, parquet_path: Path, geography: dict[str, str],
                *, batch_size: int = 20_000) -> dict:
    check = validate_sim_dbc(dbc_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    quality = {"invalid_dates": {"DTOBITO": 0, "DTNASC": 0, "DTINVESTIG": 0},
               "unmatched_residence": 0, "unmatched_occurrence": 0,
               "birth_after_death": 0, "missing_basic_cause": 0}
    temp_dbf = temp_csv = temp_parquet = None
    writer = None
    rows = 0
    try:
        with tempfile.NamedTemporaryFile(dir=dbc_path.parent, suffix=".dbf.part", delete=False) as file_obj:
            temp_dbf = Path(file_obj.name)
        datasus_dbc.decompress(str(dbc_path), str(temp_dbf))
        table = DBF(temp_dbf, encoding="latin1", char_decode_errors="strict", load=False)
        if tuple(table.field_names) != check.fields or len(table) != check.records:
            raise ValueError("SIM DBF differs from DBC header")
        with tempfile.NamedTemporaryFile(dir=parquet_path.parent, suffix=".parquet.part", delete=False) as file_obj:
            temp_parquet = Path(file_obj.name)
        writer = pq.ParquetWriter(temp_parquet, SILVER_SCHEMA, compression="zstd")
        with tempfile.NamedTemporaryFile(dir=csv_path.parent, suffix=".csv.gz.part", delete=False) as csv_file:
            temp_csv = Path(csv_file.name)
            with gzip.GzipFile(filename="", mode="wb", fileobj=csv_file, mtime=0) as gz_file:
                with io.TextIOWrapper(gz_file, encoding="utf-8", newline="") as text_file:
                    csv_writer = csv.writer(text_file, lineterminator="\n")
                    csv_writer.writerow([field.lower() for field in check.fields])
                    batch = []
                    for record in table:
                        row = dict(record)
                        csv_writer.writerow([_text(row[field]) or "" for field in check.fields])
                        batch.append(_silver_row(row, geography, quality))
                        rows += 1
                        if len(batch) >= batch_size:
                            writer.write_table(pa.Table.from_pylist(batch, schema=SILVER_SCHEMA))
                            batch.clear()
                    if batch:
                        writer.write_table(pa.Table.from_pylist(batch, schema=SILVER_SCHEMA))
        writer.close()
        writer = None
        if rows != check.records or pq.ParquetFile(temp_parquet).metadata.num_rows != rows:
            raise ValueError("SIM conversion row count differs")
        os.replace(temp_csv, csv_path)
        temp_csv = None
        os.replace(temp_parquet, parquet_path)
        temp_parquet = None
        return {"rows": rows, "quality": quality,
                "raw_csv": {"path": csv_path, "bytes": csv_path.stat().st_size,
                            "sha256": sha256_file(csv_path)},
                "silver_parquet": {"path": parquet_path, "bytes": parquet_path.stat().st_size,
                                   "sha256": sha256_file(parquet_path)}}
    finally:
        if writer is not None:
            writer.close()
        for temp in (temp_dbf, temp_csv, temp_parquet):
            if temp is not None:
                temp.unlink(missing_ok=True)
