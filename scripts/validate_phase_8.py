"""Revalidate Phase 8 maternal morbidity outputs from local artifacts."""

from nascente_brasil.transformation.maternal_pipeline import validate_phase_8


if __name__ == "__main__":
    report = validate_phase_8()
    print(f"Phase 8 validation succeeded: {report['audit']['morbidity_rows']} morbidity-coded AIH rows")
