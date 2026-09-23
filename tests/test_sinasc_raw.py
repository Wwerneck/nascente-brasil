from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import csv
from zipfile import ZipFile

import pytest

from nascente_brasil.config import get_settings
from nascente_brasil.ingestion.sinasc import ingest_sinasc_raw, validate_archive
from nascente_brasil.metadata.manifest import MANIFEST_COLUMNS, read_manifest


def archive_bytes(value: str = "20240101") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "SINASC_2024.csv",
            f"DTNASC,CODMUNRES\n{value},3304557\n{value},3550308\n",
        )
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, payload: bytes, etag: str) -> None:
        self.payload = payload
        self.headers = {"ETag": etag, "Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield self.payload


class FakeSession:
    def __init__(self, payload: bytes, etag: str = '"v1"') -> None:
        self.payload = payload
        self.etag = etag
        self.get_calls = 0

    def head(self, *_args, **_kwargs):
        return FakeResponse(self.payload, self.etag)

    def get(self, *_args, **_kwargs):
        self.get_calls += 1
        return FakeResponse(self.payload, self.etag)


def test_valid_archive_counts_rows_and_fingerprint(tmp_path) -> None:
    path = tmp_path / "valid.zip"
    path.write_bytes(archive_bytes())

    check = validate_archive(path, min_size=1, min_records=2)

    assert check.records == 2
    assert check.csv_files == 1
    assert len(check.checksum) == 64
    assert check.schema_version.startswith("header-sha256:")


def test_rejects_non_zip_and_missing_csv_columns(tmp_path) -> None:
    html = tmp_path / "html.zip"
    html.write_bytes(b"<html>temporary error</html>")
    with pytest.raises(ValueError):
        validate_archive(html, min_size=1, min_records=2)

    invalid = tmp_path / "invalid.zip"
    with ZipFile(invalid, "w") as archive:
        archive.writestr("bad.csv", "name,age\na,1\n")
    with pytest.raises(ValueError, match="Missing expected SINASC columns"):
        validate_archive(invalid, min_size=1, min_records=1)


def test_ingestion_is_idempotent_and_preserves_changed_source(tmp_path) -> None:
    data_dir = tmp_path / "data"
    metadata_dir = data_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    manifest = metadata_dir / "ingestion_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as file_obj:
        csv.writer(file_obj).writerow(MANIFEST_COLUMNS)
    settings = replace(
        get_settings(), root_dir=tmp_path, data_dir=data_dir,
        metadata_dir=metadata_dir, manifest_path=manifest, log_dir=log_dir,
    )
    session = FakeSession(archive_bytes())

    first_path, first_check, downloaded = ingest_sinasc_raw(
        settings, session, min_size=1, min_records=2
    )
    assert downloaded
    assert first_path.is_file()
    assert first_check.records == 2
    assert len(read_manifest(manifest)) == 1

    second_path, _, downloaded = ingest_sinasc_raw(
        settings, session, min_size=1, min_records=2
    )
    assert not downloaded
    assert second_path == first_path
    assert session.get_calls == 1
    assert len(read_manifest(manifest)) == 1

    first_path.unlink()
    restored_path, _, downloaded = ingest_sinasc_raw(
        settings, session, min_size=1, min_records=2
    )
    assert downloaded
    assert restored_path == first_path
    assert session.get_calls == 2
    assert len(read_manifest(manifest)) == 1

    session.etag = '"v2"'
    session.payload = archive_bytes("20240202")
    third_path, _, downloaded = ingest_sinasc_raw(
        settings, session, min_size=1, min_records=2
    )
    assert downloaded
    assert third_path != first_path
    assert first_path.is_file()
    assert len(read_manifest(manifest)) == 2

    third_path.write_bytes(third_path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="is changed"):
        ingest_sinasc_raw(settings, session, min_size=1, min_records=2)
    assert len(read_manifest(manifest)) == 2


def test_html_response_never_enters_manifest(tmp_path) -> None:
    data_dir = tmp_path / "data"
    metadata_dir = data_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    manifest = metadata_dir / "ingestion_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as file_obj:
        csv.writer(file_obj).writerow(MANIFEST_COLUMNS)
    settings = replace(
        get_settings(), root_dir=tmp_path, data_dir=data_dir,
        metadata_dir=metadata_dir, manifest_path=manifest, log_dir=log_dir,
    )

    with pytest.raises(ValueError, match="not a ZIP"):
        ingest_sinasc_raw(settings, FakeSession(b"<html>error</html>"), min_size=1, min_records=1)
    assert read_manifest(manifest) == []
    assert list((data_dir / "raw" / "sinasc" / "original").iterdir()) == []
