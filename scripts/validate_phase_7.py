"""Validate national SIH/SUS Phase 7 products from local artifacts."""

from nascente_brasil.transformation.sih_pipeline import validate_phase_7


if __name__ == "__main__":
    report = validate_phase_7()
    print(f"Phase 7 validation succeeded: {report['source_rows']} AIH rows")
    print(f"files={report['source_files']} distinct_aih={report['summary']['distinct_aih_numbers']}")
