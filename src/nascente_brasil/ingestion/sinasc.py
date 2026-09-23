"""Validated, immutable ingestion of the national SINASC 2024 CSV archive."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
from io import TextIOWrapper
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import append_manifest, read_manifest


SOURCE_PAGE = (
    "https://dadosabertos.saude.gov.br/dataset/"
    "sistema-de-informacao-sobre-nascidos-vivos-sinasc/resource/"
    "61145247-d2bb-463a-befc-01dd5a86ff34"
)
DOWNLOAD_URL = (
    "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/"
    "SINASC/csv/SINASC_2024_csv.zip"
)
SOURCE_FILE = "SINASC_2024_csv.zip"
YEAR = "2024"
MIN_ARCHIVE_BYTES = 1_000_000
MAX_ARCHIVE_BYTES = 512_000_000
MIN_RECORDS = 100_000
MAX_UNCOMPRESSED_BYTES = 2_000_000_000
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ArchiveCheck:
    size: int
    checksum: str
    records: int
    schema_version: str
    csv_files: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(
    path: Path,
    *,
    min_size: int = MIN_ARCHIVE_BYTES,
    min_records: int = MIN_RECORDS,
) -> ArchiveCheck:
    size = path.stat().st_size
    if not min_size <= size <= MAX_ARCHIVE_BYTES:
        raise ValueError(f"Implausible SINASC archive size: {size}")

    records = 0
    csv_files = 0
    headers = hashlib.sha256()
    try:
        with ZipFile(path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            if not members or sum(m.file_size for m in members) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Empty or oversized SINASC archive")
            for member in members:
                if not member.filename.lower().endswith(".csv") or member.file_size == 0:
                    raise ValueError(f"Unexpected ZIP member: {member.filename}")
                with archive.open(member) as source:
                    header = source.readline(65536)
                    if not header.endswith((b"\n", b"\r")):
                        raise ValueError(f"Invalid CSV header in {member.filename}")
                    delimiter = ";" if header.count(b";") >= header.count(b",") else ","
                    columns = next(csv.reader([header.decode("utf-8-sig", errors="replace")], delimiter=delimiter))
                    normalized = {column.strip().upper() for column in columns}
                    if not {"DTNASC", "CODMUNRES"}.issubset(normalized):
                        raise ValueError(f"Missing expected SINASC columns in {member.filename}")
                    headers.update(header)
                    with TextIOWrapper(source, encoding="utf-8-sig", errors="replace", newline="") as text_source:
                        records += sum(1 for row in csv.reader(text_source, delimiter=delimiter) if row)
                    csv_files += 1
    except BadZipFile as exc:
        raise ValueError(f"Corrupt SINASC ZIP: {path}") from exc

    if csv_files == 0 or records < min_records:
        raise ValueError(f"Implausible SINASC record count: {records}")
    return ArchiveCheck(size, sha256_file(path), records, f"header-sha256:{headers.hexdigest()}", csv_files)


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _download(session: requests.Session, url: str, directory: Path) -> tuple[Path, dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(3):
        temp_path: Path | None = None
        try:
            with session.get(url, stream=True, timeout=(15, 120)) as response:
                response.raise_for_status()
                length = response.headers.get("Content-Length")
                if length and int(length) > MAX_ARCHIVE_BYTES:
                    raise ValueError("SINASC download exceeds the size limit")
                with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as file_obj:
                    temp_path = Path(file_obj.name)
                    size = 0
                    first = True
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        if first and not chunk.startswith(b"PK\x03\x04"):
                            raise ValueError("SINASC response is not a ZIP file")
                        first = False
                        size += len(chunk)
                        if size > MAX_ARCHIVE_BYTES:
                            raise ValueError("SINASC download exceeds the size limit")
                        file_obj.write(chunk)
                if length and size != int(length):
                    raise ValueError(f"Incomplete SINASC download: {size} of {length} bytes")
                completed_path = temp_path
                temp_path = None
                return completed_path, dict(response.headers)
        except (requests.RequestException, OSError) as exc:
            last_error = exc
            if attempt == 2:
                raise RuntimeError("SINASC download failed after three attempts") from exc
            time.sleep(2**attempt)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
    raise RuntimeError("SINASC download failed") from last_error


def ingest_sinasc_raw(
    settings: Settings | None = None,
    session: requests.Session | None = None,
    *,
    min_size: int = MIN_ARCHIVE_BYTES,
    min_records: int = MIN_RECORDS,
) -> tuple[Path, ArchiveCheck, bool]:
    settings = settings or get_settings()
    settings.validate()
    directory = settings.data_dir / "raw" / "sinasc" / "original"
    directory.mkdir(parents=True, exist_ok=True)
    logger = get_logger("ingestion.sinasc")
    run_id = str(uuid4())
    owned_session = session is None
    session = session or create_session()
    try:
        rows = read_manifest(settings.manifest_path)
        etag = ""
        remote_size = ""
        try:
            head = session.head(DOWNLOAD_URL, timeout=(15, 30), allow_redirects=True)
            head.raise_for_status()
            etag = head.headers.get("ETag", "")
            remote_size = head.headers.get("Content-Length", "")
        except requests.RequestException as exc:
            logger.warning(
                "SINASC HEAD failed; downloading to verify source",
                extra={"run_id": run_id, "pipeline": "sinasc_raw", "task": "check_source", "source": "SINASC", "error": str(exc)},
            )

        if etag and remote_size:
            for row in reversed(rows):
                if (
                    row["source_name"] == "SINASC"
                    and row["reference_period"] == YEAR
                    and row["download_url"] == DOWNLOAD_URL
                    and row["source_etag"] == etag
                    and row["file_size_bytes"] == remote_size
                    and row["ingestion_status"] == "success"
                ):
                    path = directory / row["file_name"]
                    if not path.is_file():
                        logger.warning(
                            "Manifested SINASC RAW file is absent; downloading again",
                            extra={"run_id": run_id, "pipeline": "sinasc_raw", "task": "check_local", "source": "SINASC", "file": str(path)},
                        )
                        break
                    if sha256_file(path) != row["checksum"]:
                        raise ValueError(f"Manifested SINASC RAW file is changed: {path}")
                    check = ArchiveCheck(
                        int(row["file_size_bytes"]), row["checksum"], int(row["records"]),
                        row["schema_version"], 0,
                    )
                    logger.info(
                        "SINASC RAW already current",
                        extra={"run_id": run_id, "pipeline": "sinasc_raw", "task": "check_source", "source": "SINASC", "file": str(path), "status": "skipped"},
                    )
                    return path, check, False

        temp_path, headers = _download(session, DOWNLOAD_URL, directory)
        try:
            check = validate_archive(temp_path, min_size=min_size, min_records=min_records)
            target = directory / f"{Path(SOURCE_FILE).stem}_{check.checksum[:12]}.zip"
            if target.exists():
                if sha256_file(target) != check.checksum:
                    raise ValueError(f"SINASC RAW collision at {target}")
            else:
                os.replace(temp_path, target)
            if not any(
                row["source_name"] == "SINASC"
                and row["reference_period"] == YEAR
                and row["checksum"] == check.checksum
                and row["source_etag"] == headers.get("ETag", "")
                for row in rows
            ):
                append_manifest(settings.manifest_path, {
                    "source_name": "SINASC",
                    "organization": "Ministerio da Saude",
                    "dataset_name": "Nascidos Vivos - 2024",
                    "source_url": SOURCE_PAGE,
                    "download_url": DOWNLOAD_URL,
                    "reference_period": YEAR,
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                    "file_format": "ZIP/CSV",
                    "file_name": target.name,
                    "file_size_bytes": check.size,
                    "checksum": check.checksum,
                    "records": check.records,
                    "schema_version": check.schema_version,
                    "ingestion_status": "success",
                    "processing_status": "raw_validated",
                    "source_etag": headers.get("ETag", ""),
                    "source_last_modified": headers.get("Last-Modified", ""),
                })
            logger.info(
                "SINASC RAW validated",
                extra={"run_id": run_id, "pipeline": "sinasc_raw", "task": "download_validate", "source": "SINASC", "file": str(target), "rows_in": check.records, "rows_out": check.records, "rows_invalid": 0, "status": "success"},
            )
            return target, check, True
        finally:
            if temp_path.exists():
                temp_path.unlink()
    except Exception as exc:
        logger.exception(
            "SINASC RAW ingestion failed",
            extra={"run_id": run_id, "pipeline": "sinasc_raw", "task": "download_validate", "source": "SINASC", "status": "failed", "error": str(exc)},
        )
        raise
    finally:
        if owned_session:
            session.close()
