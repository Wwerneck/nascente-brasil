"""Download and validate the official national SINASC 2024 RAW archive."""

from nascente_brasil.ingestion.sinasc import ingest_sinasc_raw
from nascente_brasil.logging_config import configure_logging


if __name__ == "__main__":
    configure_logging()
    path, check, downloaded = ingest_sinasc_raw()
    action = "downloaded" if downloaded else "already current"
    print(f"SINASC RAW {action}: {path}")
    print(f"bytes={check.size} records={check.records} sha256={check.checksum}")
