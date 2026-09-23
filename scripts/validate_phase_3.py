"""Validate all SINASC Phase 3 outputs from local files and metadata."""

from nascente_brasil.validation.sinasc_phase3 import validate_phase_3


if __name__ == "__main__":
    report = validate_phase_3()
    print(f"Phase 3 validation succeeded: {report['rows']} rows")
    print(f"raw_csv={report['raw_csv']['sha256']}")
    print(f"silver_csv={report['silver']['csv']['sha256']}")
    print(f"silver_parquet={report['silver']['parquet']['sha256']}")
