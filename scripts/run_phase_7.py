"""Convert and validate national SIH/SUS reduced AIH data for 2024."""

from nascente_brasil.logging_config import configure_logging
from nascente_brasil.transformation.sih_pipeline import run_phase_7


if __name__ == "__main__":
    configure_logging()
    report, built = run_phase_7()
    print("Phase 7 built" if built else "Phase 7 already current")
    print(f"files={report['source_files']} rows={report['source_rows']} bytes={report['source_bytes']}")
    print(f"distinct_aih={report['summary']['distinct_aih_numbers']} type5={report['summary']['type_5_rows']}")
    for item in report["cnes_join"]:
        print(f"{item['match_status']}={item['registros']}")
