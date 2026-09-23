"""Independently revalidate SIM 2024 mortality products."""

from nascente_brasil.transformation.sim_pipeline import validate_phase_9


if __name__ == "__main__":
    report = validate_phase_9()
    print(f"Phase 9 validation succeeded: {report['summary']['sim_rows']} death records")
