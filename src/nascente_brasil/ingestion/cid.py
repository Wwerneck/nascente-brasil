"""Official DATASUS CID-10 reference tables from the SIM FTP."""

from __future__ import annotations

from datetime import datetime, timezone
from ftplib import FTP
import os
from pathlib import Path
import tempfile

from dbfread import DBF

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import append_manifest, read_manifest


HOST = "ftp.datasus.gov.br"
DIRECTORY = "/dissemin/publicos/SIM/CID10/TABELAS"
FILES = ("CID10.DBF", "CIDCAP10.DBF")


def validate_cid_dbf(path: Path) -> dict:
    if not 1_000 <= path.stat().st_size <= 5_000_000:
        raise ValueError(f"Invalid CID DBF size: {path.name}")
    table = DBF(path, encoding="latin1", char_decode_errors="strict", load=False)
    fields = tuple(table.field_names)
    if len(fields) < 2 or len(table) < (1_000 if path.name == "CID10.DBF" else 10):
        raise ValueError(f"Invalid CID DBF structure: {path.name}")
    return {"path": path, "bytes": path.stat().st_size, "sha256": sha256_file(path),
            "records": len(table), "fields": fields}


def ingest_cid(settings: Settings | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    directory = settings.data_dir / "raw" / "cid" / "original"
    directory.mkdir(parents=True, exist_ok=True)
    indexed = {(row["source_name"], row["file_name"]): row for row in read_manifest(settings.manifest_path)}
    products = {}
    built = False
    logger = get_logger("ingestion.cid")
    with FTP(HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(DIRECTORY)
        for name in FILES:
            size = int(ftp.size(name) or 0)
            path = directory / name
            if not path.exists():
                temp = None
                try:
                    with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as file_obj:
                        temp = Path(file_obj.name)
                        ftp.retrbinary(f"RETR {name}", file_obj.write, blocksize=1024 * 1024)
                        file_obj.flush()
                        os.fsync(file_obj.fileno())
                    if temp.stat().st_size != size:
                        raise ValueError(f"Incomplete CID download: {name}")
                    validate_cid_dbf(temp)
                    os.replace(temp, path)
                    temp = None
                finally:
                    if temp is not None:
                        temp.unlink(missing_ok=True)
                built = True
            check = validate_cid_dbf(path)
            if check["bytes"] != size:
                raise ValueError(f"CID source file changed: {name}")
            prior = indexed.get(("CID10_TABELA", name))
            if prior and (prior["checksum"] != check["sha256"] or int(prior["records"]) != check["records"]):
                raise ValueError(f"CID manifest differs: {name}")
            if not prior:
                append_manifest(settings.manifest_path, {
                    "source_name": "CID10_TABELA", "organization": "Ministerio da Saude / DATASUS",
                    "dataset_name": "CID-10 tabelas SIM", "source_url": f"ftp://{HOST}{DIRECTORY}/",
                    "download_url": f"ftp://{HOST}{DIRECTORY}/{name}", "reference_period": "CID-10",
                    "extraction_date": datetime.now(timezone.utc).isoformat(), "file_format": "DBF",
                    "file_name": name, "file_size_bytes": check["bytes"], "checksum": check["sha256"],
                    "records": check["records"], "schema_version": ",".join(check["fields"]),
                    "ingestion_status": "success", "processing_status": "raw_validated",
                    "source_etag": "", "source_last_modified": "",
                })
                built = True
            products[name] = check
            logger.info("CID reference validated", extra={"pipeline": "cid_raw", "task": "download_validate",
                        "source": "CID10", "file": name, "rows_in": check["records"],
                        "rows_out": check["records"], "status": "success"})
    return products, built
