"""Validated ingestion of the national 2024 SIM death file."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ftplib import FTP
import hashlib
import os
from pathlib import Path
import struct
import tempfile

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sih import UF_CODES
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import append_manifest, read_manifest


HOST = "ftp.datasus.gov.br"
DIRECTORY = "/dissemin/publicos/SIM/CID10/DORES"
FILE = "DOBR2024.dbc"
SOURCE_URL = "https://www.gov.br/saude/pt-br/acesso-a-informacao/sic/dados-em-transparencia-ativa/svsa/mortalidade"


@dataclass(frozen=True)
class SimCheck:
    size: int
    checksum: str
    records: int
    fields: tuple[str, ...]
    schema_version: str
    record_length: int


def validate_sim_dbc(path: Path) -> SimCheck:
    size = path.stat().st_size
    if not 10_000_000 <= size <= 500_000_000:
        raise ValueError(f"Implausible SIM DBC size: {size}")
    with path.open("rb") as file_obj:
        prefix = file_obj.read(32)
        if len(prefix) != 32 or prefix[0] != 0x03:
            raise ValueError("Invalid SIM DBC header")
        records = struct.unpack("<I", prefix[4:8])[0]
        header_length = struct.unpack("<H", prefix[8:10])[0]
        record_length = struct.unpack("<H", prefix[10:12])[0]
        if not 32 < header_length < 12_000 or not 100 < record_length < 5_000:
            raise ValueError("Invalid SIM DBF layout")
        file_obj.seek(0)
        header = file_obj.read(header_length)
    fields = tuple(header[position:position + 11].split(b"\0", 1)[0].decode("ascii")
                   for position in range(32, header_length - 1, 32))
    required = {"DTOBITO", "CAUSABAS", "CAUSAMAT", "CODMUNRES", "TIPOBITO", "SEXO",
                "IDADE", "OBITOGRAV", "OBITOPUERP", "NUDIASINF"}
    if not required <= set(fields) or len(fields) != 87 or records < 1_000_000 or header[-1] != 0x0D:
        raise ValueError("SIM national DBC schema or volume differs")
    schema = "dbf-fields-sha256:" + hashlib.sha256(header[32:header_length]).hexdigest()
    return SimCheck(size, sha256_file(path), records, fields, schema, record_length)


def ingest_sim_2024(settings: Settings | None = None) -> tuple[SimCheck, bool]:
    settings = settings or get_settings()
    settings.validate()
    directory = settings.data_dir / "raw" / "sim" / "original"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / FILE
    prior = next((row for row in read_manifest(settings.manifest_path)
                  if row["source_name"] == "SIM_DO" and row["file_name"] == FILE), None)
    logger = get_logger("ingestion.sim")
    built = False
    with FTP(HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(DIRECTORY)
        names = set(ftp.nlst())
        state_files = {f"DO{uf}2024.dbc" for uf in UF_CODES}
        if FILE not in names or not state_files <= names:
            raise ValueError("SIM 2024 national/state FTP inventory is incomplete")
        remote_size = int(ftp.size(FILE) or 0)
        if not path.exists():
            temp = None
            try:
                with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as file_obj:
                    temp = Path(file_obj.name)
                    ftp.retrbinary(f"RETR {FILE}", file_obj.write, blocksize=1024 * 1024)
                    file_obj.flush()
                    os.fsync(file_obj.fileno())
                if temp.stat().st_size != remote_size:
                    raise ValueError("Incomplete SIM national download")
                check = validate_sim_dbc(temp)
                os.replace(temp, path)
                temp = None
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
            built = True
        check = validate_sim_dbc(path)
        if check.size != remote_size:
            raise ValueError("SIM national file size differs from FTP")
    if prior and (prior["checksum"] != check.checksum or int(prior["records"]) != check.records
                  or prior["schema_version"] != check.schema_version):
        raise ValueError("SIM national file differs from manifest")
    if not prior:
        append_manifest(settings.manifest_path, {
            "source_name": "SIM_DO", "organization": "Ministerio da Saude / DATASUS",
            "dataset_name": "Declaracoes de Obito nacionais 2024", "source_url": SOURCE_URL,
            "download_url": f"ftp://{HOST}{DIRECTORY}/{FILE}", "reference_period": "2024",
            "extraction_date": datetime.now(timezone.utc).isoformat(), "file_format": "DBC",
            "file_name": FILE, "file_size_bytes": check.size, "checksum": check.checksum,
            "records": check.records, "schema_version": check.schema_version,
            "ingestion_status": "success", "processing_status": "raw_validated",
            "source_etag": "", "source_last_modified": "",
        })
        built = True
    logger.info("SIM 2024 RAW validated", extra={"pipeline": "sim_2024", "task": "download_validate",
                "source": "SIM", "file": FILE, "rows_in": check.records,
                "rows_out": check.records, "status": "success"})
    return check, built
