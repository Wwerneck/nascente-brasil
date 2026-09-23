"""Verify the manifested SINASC RAW archive without contacting the source."""

from nascente_brasil.config import get_settings
from nascente_brasil.ingestion.sinasc import DOWNLOAD_URL, YEAR, validate_archive
from nascente_brasil.metadata.manifest import read_manifest


def main() -> int:
    settings = get_settings()
    settings.validate()
    rows = [
        row for row in read_manifest(settings.manifest_path)
        if row["source_name"] == "SINASC"
        and row["reference_period"] == YEAR
        and row["download_url"] == DOWNLOAD_URL
        and row["ingestion_status"] == "success"
    ]
    if not rows:
        raise ValueError("No successful SINASC 2024 RAW ingestion in manifest")
    row = rows[-1]
    path = settings.data_dir / "raw" / "sinasc" / "original" / row["file_name"]
    check = validate_archive(path)
    if (
        check.checksum != row["checksum"]
        or check.size != int(row["file_size_bytes"])
        or check.records != int(row["records"])
        or check.schema_version != row["schema_version"]
    ):
        raise ValueError("SINASC RAW does not match its manifest record")
    print(f"Phase 2 validation succeeded: {path}")
    print(f"bytes={check.size} records={check.records} sha256={check.checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
