from __future__ import annotations

from dataclasses import replace
import csv
from io import StringIO
import json
from zipfile import ZipFile

import pandas as pd
import pyarrow.parquet as pq
import pytest

from nascente_brasil.conversion.sinasc import (
    OUTPUT_COLUMNS, SOURCE_COLUMNS, convert_zip_to_csv, verify_converted_csv,
)
from nascente_brasil.transformation.sinasc import transform_silver
from nascente_brasil.config import get_settings
from nascente_brasil.ingestion.sinasc import DOWNLOAD_URL, sha256_file
from nascente_brasil.metadata.manifest import MANIFEST_COLUMNS
from nascente_brasil.transformation.sinasc_pipeline import process_sinasc_2024
from nascente_brasil.validation.sinasc_phase3 import validate_phase_3


def make_zip(path, *, drift: bool = False) -> None:
    text = StringIO(newline="")
    writer = csv.writer(text, delimiter=";", lineterminator="\n")
    header = SOURCE_COLUMNS[:-1] if drift else SOURCE_COLUMNS
    writer.writerow(header)
    for date, age, weight in (("01012024", "29", "3200"), ("32132024", "abc", "9999")):
        row = dict.fromkeys(header, "")
        row.update({
            "DTNASC": date,
            "CODMUNNASC": "001234",
            "CODMUNRES": "000001",
            "IDADEMAE": age,
            "PESO": weight,
            "PARTO": "2",
            "SEXO": "1",
            "APGAR1": "09",
            "APGAR5": "99",
            "SEMAGESTAC": "39",
            "CONSPRENAT": "09",
        })
        writer.writerow([row[name] for name in header])
    with ZipFile(path, "w") as archive:
        archive.writestr("SINASC_2024.csv", text.getvalue().encode("utf-8"))


def test_conversion_and_silver_preserve_codes_and_account_for_invalid_values(tmp_path) -> None:
    source = tmp_path / "source.zip"
    raw_csv = tmp_path / "raw.csv"
    silver_csv = tmp_path / "silver.csv"
    parquet = tmp_path / "silver.parquet"
    make_zip(source)

    converted = convert_zip_to_csv(source, raw_csv, expected_rows=2)
    verified = verify_converted_csv(raw_csv, expected_rows=2)
    result = transform_silver(raw_csv, silver_csv, parquet, expected_rows=2, chunk_rows=1)

    assert converted["sha256"] == verified["sha256"]
    assert result["rows"] == 2
    raw = pd.read_csv(raw_csv, dtype="string", keep_default_na=False)
    silver = pd.read_csv(silver_csv, dtype="string", keep_default_na=False)
    assert tuple(raw.columns) == OUTPUT_COLUMNS
    assert raw["codigo_municipio_residencia"].tolist() == ["000001", "000001"]
    assert silver["codigo_municipio_residencia"].tolist() == ["000001", "000001"]
    assert silver["data_nascimento"].tolist() == ["2024-01-01", ""]
    assert silver["idade_mae"].tolist() == ["29", ""]
    assert silver["apgar_5min"].tolist() == ["", ""]
    assert result["quality"]["invalid_numeric"]["idade_mae"] == 1
    assert result["quality"]["invalid_date"]["data_nascimento"] == 1
    assert result["quality"]["sentinel_to_null"]["peso_nascimento_g"] == 1
    schema = pq.read_schema(parquet)
    assert str(schema.field("idade_mae").type) == "int64"
    assert str(schema.field("codigo_municipio_residencia").type) == "string"
    assert pq.ParquetFile(parquet).metadata.num_rows == 2


def test_conversion_rejects_schema_drift_and_leaves_no_output(tmp_path) -> None:
    source = tmp_path / "source.zip"
    output = tmp_path / "raw.csv"
    make_zip(source, drift=True)

    with pytest.raises(ValueError, match="schema drift"):
        convert_zip_to_csv(source, output, expected_rows=2)

    assert not output.exists()
    assert list(tmp_path.glob("*.part")) == []


def test_dictionary_covers_source_schema() -> None:
    dictionary = (get_settings().root_dir / "docs" / "data_dictionary" / "sinasc.md").read_text(encoding="utf-8")
    for column in SOURCE_COLUMNS:
        assert f"| {column} |" in dictionary


def test_pipeline_is_portable_and_rebuilds_missing_outputs(tmp_path) -> None:
    data_dir = tmp_path / "data"
    metadata_dir = data_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    source_dir = data_dir / "raw" / "sinasc" / "original"
    source_dir.mkdir(parents=True)
    source_zip = source_dir / "source.zip"
    make_zip(source_zip)
    manifest = metadata_dir / "ingestion_manifest.csv"
    row = dict.fromkeys(MANIFEST_COLUMNS, "")
    row.update({
        "source_name": "SINASC", "reference_period": "2024",
        "download_url": DOWNLOAD_URL, "ingestion_status": "success",
        "file_name": source_zip.name, "checksum": sha256_file(source_zip),
        "records": "2",
    })
    with manifest.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    settings = replace(
        get_settings(), root_dir=tmp_path, data_dir=data_dir,
        metadata_dir=metadata_dir, manifest_path=manifest, log_dir=log_dir,
    )

    first, built = process_sinasc_2024(settings, chunk_rows=1)
    assert built
    assert not first["raw_csv"]["path"].startswith(str(tmp_path))
    validate_phase_3(settings)

    report_path = metadata_dir / f"sinasc_2024_{row['checksum'][:12]}_processing.json"
    original_report = report_path.read_text(encoding="utf-8")
    second, built = process_sinasc_2024(settings, chunk_rows=1)
    assert not built
    assert second["raw_csv"]["sha256"] == first["raw_csv"]["sha256"]
    assert report_path.read_text(encoding="utf-8") == original_report

    for item in (first["raw_csv"], first["silver"]["csv"], first["silver"]["parquet"]):
        (tmp_path / item["path"]).unlink()
    rebuilt, built = process_sinasc_2024(settings, chunk_rows=1)
    assert built
    assert rebuilt["rows"] == 2
    assert json.loads(report_path.read_text(encoding="utf-8"))["raw_csv"]["path"] == first["raw_csv"]["path"]
