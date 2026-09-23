"""Validated ingestion of the official CNES hospital beds 2024 dataset."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import os
from pathlib import Path
import tempfile

import requests

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sinasc import create_session, sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import append_manifest, read_manifest


SOURCE_PAGE = "https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos"
CSV_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_2024.csv"
DICTIONARY_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Dicion%C3%A1rio_Leito_hospitalar.pdf"
YEAR = "2024"
CSV_FILE = "Leitos_2024.csv"
DICTIONARY_FILE = "Dicionario_Leito_hospitalar.pdf"
SOURCE_COLUMNS = (
    "COMP", "REGIAO", "UF", "MUNICIPIO", "MOTIVO_DESABILITACAO", "CNES",
    "NOME_ESTABELECIMENTO", "RAZAO_SOCIAL", "TP_GESTAO", "CO_TIPO_UNIDADE",
    "DS_TIPO_UNIDADE", "NATUREZA_JURIDICA", "DESC_NATUREZA_JURIDICA",
    "NO_LOGRADOURO", "NU_ENDERECO", "NO_COMPLEMENTO", "NO_BAIRRO", "CO_CEP",
    "NU_TELEFONE", "NO_EMAIL", "LEITOS_EXISTENTES", "LEITOS_SUS", "UTI_TOTAL_EXIST",
    "UTI_TOTAL_SUS", "UTI_ADULTO_EXIST", "UTI_ADULTO_SUS", "UTI_PEDIATRICO_EXIST",
    "UTI_PEDIATRICO_SUS", "UTI_NEONATAL_EXIST", "UTI_NEONATAL_SUS",
    "UTI_QUEIMADO_EXIST", "UTI_QUEIMADO_SUS", "UTI_CORONARIANA_EXIST",
    "UTI_CORONARIANA_SUS",
)


@dataclass(frozen=True)
class CnesCheck:
    size: int
    checksum: str
    records: int
    schema_version: str
    competencies: tuple[str, ...]


def validate_cnes_csv(path: Path, *, min_records: int = 80_000, min_size: int = 10_000_000,
                      expected_competencies: tuple[str, ...] | None = None) -> CnesCheck:
    size = path.stat().st_size
    if not min_size <= size <= 100_000_000:
        raise ValueError(f"Implausible CNES CSV size: {size}")
    records = 0
    competencies: set[str] = set()
    keys: set[tuple[str, str]] = set()
    with path.open("r", encoding="latin1", newline="") as file_obj:
        reader = csv.DictReader(file_obj, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_COLUMNS:
            raise ValueError("CNES CSV schema drift detected")
        for row in reader:
            records += 1
            competence, cnes = row["COMP"], row["CNES"]
            if not (len(competence) == 6 and competence.isdigit() and competence.startswith(YEAR)):
                raise ValueError(f"Invalid CNES competence: {competence}")
            if not (len(cnes) == 7 and cnes.isdigit()):
                raise ValueError(f"Invalid CNES code: {cnes}")
            key = (competence, cnes)
            if key in keys:
                raise ValueError(f"Duplicated CNES competence key: {key}")
            keys.add(key)
            competencies.add(competence)
    expected = expected_competencies or tuple(f"2024{month:02d}" for month in range(1, 13))
    if records < min_records or tuple(sorted(competencies)) != expected:
        raise ValueError(f"Implausible CNES rows or competencies: {records}, {sorted(competencies)}")
    schema_hash = hashlib.sha256(",".join(SOURCE_COLUMNS).encode("ascii")).hexdigest()
    return CnesCheck(size, sha256_file(path), records, f"columns-sha256:{schema_hash}", expected)


def validate_dictionary(path: Path) -> dict:
    size = path.stat().st_size
    if not 100_000 <= size <= 5_000_000 or path.read_bytes()[:5] != b"%PDF-":
        raise ValueError("CNES dictionary is not a plausible PDF")
    return {"size": size, "sha256": sha256_file(path)}


def _download(session: requests.Session, url: str, directory: Path, expected_prefix: bytes) -> tuple[Path, dict]:
    temp: Path | None = None
    try:
        with session.get(url, stream=True, timeout=(15, 120)) as response:
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as file_obj:
                temp = Path(file_obj.name)
                total = 0
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        total += len(chunk)
                        if total > 100_000_000:
                            raise ValueError("CNES download exceeds size limit")
                        file_obj.write(chunk)
            length = response.headers.get("Content-Length")
            if length and int(length) != total:
                raise ValueError("Incomplete CNES download")
            with temp.open("rb") as file_obj:
                prefix = file_obj.read(len(expected_prefix))
            if not prefix.startswith(expected_prefix):
                raise ValueError("CNES response content does not match expected format")
            result, temp = temp, None
            return result, dict(response.headers)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def ingest_cnes_raw(settings: Settings | None = None, session: requests.Session | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    directory = settings.data_dir / "raw" / "cnes" / "original"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(settings.manifest_path)
    owned = session is None
    session = session or create_session()
    logger = get_logger("ingestion.cnes")
    built = False
    try:
        products = {}
        for source_name, filename, url, prefix, validator, fmt in (
            ("CNES_LEITOS", CSV_FILE, CSV_URL, b'"COMP"', validate_cnes_csv, "CSV"),
            ("CNES_DICIONARIO_LEITOS", DICTIONARY_FILE, DICTIONARY_URL, b"%PDF-", validate_dictionary, "PDF"),
        ):
            path = directory / filename
            headers = {}
            if not path.exists():
                temp, headers = _download(session, url, directory, prefix)
                try:
                    validator(temp)
                    os.replace(temp, path)
                    built = True
                finally:
                    temp.unlink(missing_ok=True)
            check = validator(path)
            size = check.size if isinstance(check, CnesCheck) else check["size"]
            digest = check.checksum if isinstance(check, CnesCheck) else check["sha256"]
            records = check.records if isinstance(check, CnesCheck) else 34
            previous = [row for row in manifest if row["source_name"] == source_name and row["reference_period"] == YEAR]
            if previous and any(row["checksum"] != digest or int(row["file_size_bytes"]) != size
                                or row["download_url"] != url for row in previous):
                raise ValueError(f"CNES local source differs from manifest: {path}")
            if not previous:
                append_manifest(settings.manifest_path, {
                    "source_name": source_name, "organization": "Ministerio da Saude",
                    "dataset_name": "Hospitais e Leitos 2024" if fmt == "CSV" else "Dicionario Hospitais e Leitos",
                    "source_url": SOURCE_PAGE, "download_url": url, "reference_period": YEAR,
                    "extraction_date": datetime.now(timezone.utc).isoformat(), "file_format": fmt,
                    "file_name": filename, "file_size_bytes": size, "checksum": digest, "records": records,
                    "schema_version": check.schema_version if isinstance(check, CnesCheck) else "dictionary-34-fields-v1",
                    "ingestion_status": "success", "processing_status": "raw_validated",
                    "source_etag": headers.get("ETag", ""), "source_last_modified": headers.get("Last-Modified", ""),
                })
                built = True
            products[source_name] = {"path": path, "bytes": size, "sha256": digest, "records": records}
        logger.info("CNES RAW validated", extra={"pipeline": "cnes_raw", "task": "download_validate", "source": "CNES",
                                                 "file": str(products["CNES_LEITOS"]["path"]), "rows_in": products["CNES_LEITOS"]["records"],
                                                 "rows_out": products["CNES_LEITOS"]["records"], "rows_invalid": 0, "status": "success"})
        return products, built
    except Exception as exc:
        logger.exception("CNES RAW ingestion failed", extra={"pipeline": "cnes_raw", "task": "download_validate", "source": "CNES", "status": "failed", "error": str(exc)})
        raise
    finally:
        if owned:
            session.close()
