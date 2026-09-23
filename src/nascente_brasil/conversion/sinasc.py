"""Lossless value conversion from the SINASC ZIP to local UTF-8 CSV."""

from __future__ import annotations

import csv
from io import TextIOWrapper
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

from nascente_brasil.ingestion.sinasc import sha256_file


SOURCE_COLUMNS = (
    "contador", "ORIGEM", "CODESTAB", "CODMUNNASC", "LOCNASC", "IDADEMAE",
    "ESTCIVMAE", "ESCMAE", "CODOCUPMAE", "QTDFILVIVO", "QTDFILMORT",
    "CODMUNRES", "GESTACAO", "GRAVIDEZ", "PARTO", "CONSULTAS", "DTNASC",
    "HORANASC", "SEXO", "APGAR1", "APGAR5", "RACACOR", "PESO",
    "IDANOMAL", "DTCADASTRO", "CODANOMAL", "NUMEROLOTE", "VERSAOSIST",
    "DTRECEBIM", "DIFDATA", "OPORT_DN", "DTRECORIGA", "NATURALMAE",
    "CODMUNNATU", "CODUFNATU", "ESCMAE2010", "SERIESCMAE", "DTNASCMAE",
    "RACACORMAE", "QTDGESTANT", "QTDPARTNOR", "QTDPARTCES", "IDADEPAI",
    "DTULTMENST", "SEMAGESTAC", "TPMETESTIM", "CONSPRENAT", "MESPRENAT",
    "TPAPRESENT", "STTRABPART", "STCESPARTO", "TPNASCASSI", "TPFUNCRESP",
    "TPDOCRESP", "DTDECLARAC", "ESCMAEAGR1", "STDNEPIDEM", "STDNNOVA",
    "CODPAISRES", "TPROBSON", "PARIDADE", "KOTELCHUCK",
)

COLUMN_NAMES = {
    "CODESTAB": "codigo_estabelecimento",
    "CODMUNNASC": "codigo_municipio_nascimento",
    "CODMUNRES": "codigo_municipio_residencia",
    "DTNASC": "data_nascimento",
    "IDADEMAE": "idade_mae",
    "CONSPRENAT": "consultas_prenatal_numero",
    "CONSULTAS": "consultas_prenatal_categoria",
    "GESTACAO": "gestacao_categoria",
    "SEMAGESTAC": "semanas_gestacao",
    "PARTO": "tipo_parto",
    "GRAVIDEZ": "tipo_gravidez",
    "PESO": "peso_nascimento_g",
    "SEXO": "sexo",
    "APGAR1": "apgar_1min",
    "APGAR5": "apgar_5min",
    "LOCNASC": "local_nascimento",
    "ESCMAE2010": "escolaridade_mae_2010",
    "RACACORMAE": "raca_cor_mae",
}

OUTPUT_COLUMNS = tuple(COLUMN_NAMES.get(name, name.lower()) for name in SOURCE_COLUMNS)


def convert_zip_to_csv(source_zip: Path, output_csv: Path, expected_rows: int) -> dict[str, str | int]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    rows = 0
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=output_csv.parent,
            suffix=".part", delete=False,
        ) as target:
            temp_path = Path(target.name)
            writer = csv.writer(target, delimiter=",", lineterminator="\n")
            writer.writerow(OUTPUT_COLUMNS)
            with ZipFile(source_zip) as archive:
                members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
                if len(members) != 1:
                    raise ValueError(f"Expected one SINASC CSV in ZIP, found {len(members)}")
                with archive.open(members[0]) as compressed:
                    with TextIOWrapper(compressed, encoding="utf-8-sig", errors="strict", newline="") as source:
                        reader = csv.reader(source, delimiter=";", strict=True)
                        header = tuple(next(reader))
                        if header != SOURCE_COLUMNS:
                            added = sorted(set(header) - set(SOURCE_COLUMNS))
                            removed = sorted(set(SOURCE_COLUMNS) - set(header))
                            raise ValueError(f"SINASC schema drift: added={added}, removed={removed}, order_changed={not added and not removed}")
                        for row in reader:
                            if len(row) != len(SOURCE_COLUMNS):
                                raise ValueError(f"SINASC row {rows + 1} has {len(row)} columns")
                            writer.writerow(row)
                            rows += 1
        if rows != expected_rows:
            raise ValueError(f"SINASC row count changed: expected {expected_rows}, found {rows}")
        if output_csv.exists():
            raise FileExistsError(f"Derived RAW CSV already exists: {output_csv}")
        os.replace(temp_path, output_csv)
        temp_path = None
        return {"path": str(output_csv), "rows": rows, "bytes": output_csv.stat().st_size, "sha256": sha256_file(output_csv)}
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def verify_converted_csv(path: Path, expected_rows: int) -> dict[str, str | int]:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj, delimiter=",", strict=True)
        if tuple(next(reader)) != OUTPUT_COLUMNS:
            raise ValueError(f"Converted SINASC CSV schema differs: {path}")
        rows = 0
        for row in reader:
            if len(row) != len(OUTPUT_COLUMNS):
                raise ValueError(f"Converted SINASC row {rows + 1} has {len(row)} columns")
            rows += 1
    if rows != expected_rows:
        raise ValueError(f"Converted SINASC row count differs: {rows} vs {expected_rows}")
    return {"path": str(path), "rows": rows, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
