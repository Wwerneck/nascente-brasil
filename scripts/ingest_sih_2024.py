"""Download and validate all national SIH/SUS RD files for 2024."""

from nascente_brasil.ingestion.sih import ingest_sih_2024
from nascente_brasil.logging_config import configure_logging


if __name__ == "__main__":
    configure_logging()
    products, built = ingest_sih_2024()
    print("SIH 2024 RAW downloaded" if built else "SIH 2024 RAW already current")
    print(f"files={len(products)} records={sum(item['records'] for item in products.values())}")
    print(f"bytes={sum(item['bytes'] for item in products.values())}")
