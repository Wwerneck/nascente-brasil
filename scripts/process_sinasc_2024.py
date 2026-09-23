"""Build local CSV RAW and typed Silver artifacts from the SINASC 2024 ZIP."""

from nascente_brasil.logging_config import configure_logging
from nascente_brasil.transformation.sinasc_pipeline import process_sinasc_2024


if __name__ == "__main__":
    configure_logging()
    report, built = process_sinasc_2024()
    print("SINASC Silver built" if built else "SINASC Silver already current")
    print(f"rows={report['rows']} raw_csv={report['raw_csv']['path']}")
    print(f"silver_csv={report['silver']['csv']['path']}")
    print(f"silver_parquet={report['silver']['parquet']['path']}")
