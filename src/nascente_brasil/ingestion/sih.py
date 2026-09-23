"""Resumable ingestion of national SIH/SUS reduced AIH files for 2024."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ftplib import FTP, all_errors as ftp_errors
import hashlib
import os
from pathlib import Path
import re
import struct
import tempfile
import time

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import append_manifest, read_manifest


FTP_HOST = "ftp.datasus.gov.br"
FTP_DIRECTORY = "/dissemin/publicos/SIHSUS/200801_/Dados"
SOURCE_PAGE = "https://datasus.saude.gov.br/transferencia-de-arquivos/"
DOCUMENT_FILE = "IT_SIHSUS_1603.pdf"
DOCUMENT_URL = f"ftp://{FTP_HOST}/dissemin/publicos/SIHSUS/200801_/Doc/{DOCUMENT_FILE}"
YEAR = "2024"
UF_CODES = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
            "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO")
EXPECTED_FILES = tuple(f"RD{uf}24{month:02d}.dbc" for uf in UF_CODES for month in range(1, 13))
EXPECTED_FIELDS = (
    "UF_ZI", "ANO_CMPT", "MES_CMPT", "ESPEC", "CGC_HOSP", "N_AIH", "IDENT", "CEP", "MUNIC_RES",
    "NASC", "SEXO", "UTI_MES_IN", "UTI_MES_AN", "UTI_MES_AL", "UTI_MES_TO", "MARCA_UTI",
    "UTI_INT_IN", "UTI_INT_AN", "UTI_INT_AL", "UTI_INT_TO", "DIAR_ACOM", "QT_DIARIAS", "PROC_SOLIC",
    "PROC_REA", "VAL_SH", "VAL_SP", "VAL_SADT", "VAL_RN", "VAL_ACOMP", "VAL_ORTP", "VAL_SANGUE",
    "VAL_SADTSR", "VAL_TRANSP", "VAL_OBSANG", "VAL_PED1AC", "VAL_TOT", "VAL_UTI", "US_TOT", "DT_INTER",
    "DT_SAIDA", "DIAG_PRINC", "DIAG_SECUN", "COBRANCA", "NATUREZA", "NAT_JUR", "GESTAO", "RUBRICA",
    "IND_VDRL", "MUNIC_MOV", "COD_IDADE", "IDADE", "DIAS_PERM", "MORTE", "NACIONAL", "NUM_PROC",
    "CAR_INT", "TOT_PT_SP", "CPF_AUT", "HOMONIMO", "NUM_FILHOS", "INSTRU", "CID_NOTIF", "CONTRACEP1",
    "CONTRACEP2", "GESTRISCO", "INSC_PN", "SEQ_AIH5", "CBOR", "CNAER", "VINCPREV", "GESTOR_COD",
    "GESTOR_TP", "GESTOR_CPF", "GESTOR_DT", "CNES", "CNPJ_MANT", "INFEHOSP", "CID_ASSO", "CID_MORTE",
    "COMPLEX", "FINANC", "FAEC_TP", "REGCT", "RACA_COR", "ETNIA", "SEQUENCIA", "REMESSA", "AUD_JUST",
    "SIS_JUST", "VAL_SH_FED", "VAL_SP_FED", "VAL_SH_GES", "VAL_SP_GES", "VAL_UCI", "MARCA_UCI",
    "DIAGSEC1", "DIAGSEC2", "DIAGSEC3", "DIAGSEC4", "DIAGSEC5", "DIAGSEC6", "DIAGSEC7", "DIAGSEC8",
    "DIAGSEC9", "TPDISEC1", "TPDISEC2", "TPDISEC3", "TPDISEC4", "TPDISEC5", "TPDISEC6", "TPDISEC7",
    "TPDISEC8", "TPDISEC9",
)


@dataclass(frozen=True)
class DbcCheck:
    size: int
    checksum: str
    records: int
    schema_version: str
    header_length: int
    record_length: int


def _read_dbc_fields(header: bytes) -> tuple[str, ...]:
    fields = []
    position = 32
    while position + 32 <= len(header) and header[position] != 0x0D:
        fields.append(header[position:position + 11].split(b"\0", 1)[0].decode("ascii"))
        position += 32
    return tuple(fields)


def validate_dbc(path: Path, *, minimum_size: int = 1_000) -> DbcCheck:
    size = path.stat().st_size
    if not minimum_size <= size <= 100_000_000:
        raise ValueError(f"Implausible SIH DBC size: {path.name} ({size})")
    with path.open("rb") as file_obj:
        prefix = file_obj.read(32)
        if len(prefix) != 32 or prefix[0] != 0x03:
            raise ValueError(f"Invalid SIH DBC header: {path.name}")
        records = struct.unpack("<I", prefix[4:8])[0]
        header_length = struct.unpack("<H", prefix[8:10])[0]
        record_length = struct.unpack("<H", prefix[10:12])[0]
        if not 32 < header_length < 10_000:
            raise ValueError(f"Invalid SIH DBC header length: {path.name}")
        file_obj.seek(0)
        header = file_obj.read(header_length)
    fields = _read_dbc_fields(header)
    if fields != EXPECTED_FIELDS or records < 1 or record_length < 100:
        raise ValueError(f"SIH DBC schema drift or invalid volume: {path.name}")
    signature = hashlib.sha256(header[32:header_length]).hexdigest()
    return DbcCheck(size, sha256_file(path), records, f"dbf-fields-sha256:{signature}", header_length, record_length)


def _connect() -> FTP:
    ftp = FTP(FTP_HOST, timeout=120)
    ftp.login()
    ftp.cwd(FTP_DIRECTORY)
    return ftp


def inventory_2024() -> dict[str, int]:
    with _connect() as ftp:
        names = {name for name in ftp.nlst() if re.fullmatch(r"RD[A-Z]{2}24(?:0[1-9]|1[0-2])\.dbc", name)}
        missing = set(EXPECTED_FILES) - names
        unexpected = names - set(EXPECTED_FILES)
        if missing or unexpected:
            raise ValueError(f"SIH FTP inventory differs; missing={sorted(missing)}, unexpected={sorted(unexpected)}")
        return {name: int(ftp.size(name) or 0) for name in EXPECTED_FILES}


def _download_one(ftp: FTP, name: str, directory: Path, expected_size: int) -> Path:
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as file_obj:
            temp = Path(file_obj.name)
            ftp.retrbinary(f"RETR {name}", file_obj.write, blocksize=1024 * 1024)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        if temp.stat().st_size != expected_size:
            raise ValueError(f"Incomplete SIH download: {name}")
        result, temp = temp, None
        return result
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def ingest_sih_2024(settings: Settings | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    directory = settings.data_dir / "raw" / "sih" / "original"
    directory.mkdir(parents=True, exist_ok=True)
    logger = get_logger("ingestion.sih")
    inventory = inventory_2024()
    manifest = read_manifest(settings.manifest_path)
    indexed = {(row["source_name"], row["file_name"]): row for row in manifest}
    ftp: FTP | None = None
    built = False
    products = {}
    try:
        ftp = _connect()
        for position, name in enumerate(EXPECTED_FILES, start=1):
            path = directory / name
            previous = indexed.get(("SIH_RD", name))
            if path.exists():
                check = validate_dbc(path)
                if check.size != inventory[name]:
                    raise ValueError(f"Local SIH file size differs from FTP: {name}")
                if previous and (previous["checksum"] != check.checksum
                                 or int(previous["records"]) != check.records
                                 or previous["schema_version"] != check.schema_version):
                    raise ValueError(f"Local SIH file differs from manifest: {name}")
            else:
                last_error: Exception | None = None
                for attempt in range(3):
                    try:
                        temp = _download_one(ftp, name, directory, inventory[name])
                        try:
                            check = validate_dbc(temp)
                            os.replace(temp, path)
                        finally:
                            temp.unlink(missing_ok=True)
                        built = True
                        break
                    except (OSError, *ftp_errors) as exc:
                        last_error = exc
                        if ftp is not None:
                            try:
                                ftp.close()
                            except OSError:
                                pass
                        if attempt == 2:
                            raise RuntimeError(f"SIH download failed after retries: {name}") from exc
                        time.sleep(2**attempt)
                        ftp = _connect()
                else:
                    raise RuntimeError(f"SIH download failed: {name}") from last_error
            if not previous:
                period = f"20{name[4:6]}-{name[6:8]}"
                append_manifest(settings.manifest_path, {
                    "source_name": "SIH_RD", "organization": "Ministerio da Saude / DATASUS",
                    "dataset_name": f"SIH/SUS AIH Reduzida {name[2:4]} {period}", "source_url": SOURCE_PAGE,
                    "download_url": f"ftp://{FTP_HOST}{FTP_DIRECTORY}/{name}", "reference_period": period,
                    "extraction_date": datetime.now(timezone.utc).isoformat(), "file_format": "DBC/DBF",
                    "file_name": name, "file_size_bytes": check.size, "checksum": check.checksum,
                    "records": check.records, "schema_version": check.schema_version,
                    "ingestion_status": "success", "processing_status": "raw_validated",
                    "source_etag": "", "source_last_modified": "",
                })
                built = True
            products[name] = {"path": path, "bytes": check.size, "sha256": check.checksum,
                              "records": check.records, "schema_version": check.schema_version}
            if position % 25 == 0 or position == len(EXPECTED_FILES):
                logger.info("SIH RAW ingestion progress", extra={"pipeline": "sih_raw", "task": "download_validate",
                    "source": "SIH", "file": name, "rows_in": sum(item["records"] for item in products.values()),
                    "rows_out": len(products), "status": "running"})
        document_path = directory / DOCUMENT_FILE
        previous_document = indexed.get(("SIH_DOCUMENTACAO_RD", DOCUMENT_FILE))
        ftp.cwd("../Doc")
        document_size = int(ftp.size(DOCUMENT_FILE) or 0)
        if not document_path.exists():
            temp = _download_one(ftp, DOCUMENT_FILE, directory, document_size)
            try:
                os.replace(temp, document_path)
            finally:
                temp.unlink(missing_ok=True)
            built = True
        with document_path.open("rb") as document:
            document_prefix = document.read(5)
        if (not 10_000 <= document_path.stat().st_size <= 10_000_000
                or document_prefix != b"%PDF-"):
            raise ValueError("SIH RD documentation is not a valid PDF")
        document_sha = sha256_file(document_path)
        if previous_document and (previous_document["checksum"] != document_sha
                                  or int(previous_document["file_size_bytes"]) != document_size):
            raise ValueError("SIH RD documentation differs from manifest")
        if not previous_document:
            append_manifest(settings.manifest_path, {
                "source_name": "SIH_DOCUMENTACAO_RD", "organization": "Ministerio da Saude / DATASUS",
                "dataset_name": "Informe Tecnico SIH/SUS - Layout RD", "source_url": SOURCE_PAGE,
                "download_url": DOCUMENT_URL, "reference_period": "layout-2008+",
                "extraction_date": datetime.now(timezone.utc).isoformat(), "file_format": "PDF",
                "file_name": DOCUMENT_FILE, "file_size_bytes": document_size, "checksum": document_sha,
                "records": len(EXPECTED_FIELDS), "schema_version": "sih-rd-layout-2016-03",
                "ingestion_status": "success", "processing_status": "raw_validated",
                "source_etag": "", "source_last_modified": "",
            })
            built = True
        return products, built
    except Exception as exc:
        logger.exception("SIH RAW ingestion failed", extra={"pipeline": "sih_raw", "task": "download_validate",
            "source": "SIH", "status": "failed", "error": str(exc)})
        raise
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except (OSError, *ftp_errors):
                ftp.close()
