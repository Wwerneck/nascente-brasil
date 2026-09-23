"""Recompute and verify Phase 4 indicators against local Phase 3 data."""

from nascente_brasil.analytics.sinasc_pipeline import validate_phase_4


if __name__ == "__main__":
    report = validate_phase_4()
    print(f"Phase 4 validation succeeded: {report['national']['nascidos_vivos']} rows")
