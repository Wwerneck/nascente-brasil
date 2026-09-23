"""Build and integrate the official CNES hospital capacity snapshots for 2024."""

from nascente_brasil.logging_config import configure_logging
from nascente_brasil.transformation.cnes_pipeline import run_phase_6


if __name__ == "__main__":
    configure_logging()
    report, built = run_phase_6()
    print("Phase 6 built" if built else "Phase 6 already current")
    print(f"rows={report['source_rows']} cnes={report['distinct_cnes']} competencies={len(report['competencies'])}")
    print(f"territory_matched={report['territory_join']['matched_rows']} unmatched={report['territory_join']['unmatched_left']}")
    for item in report["sinasc_cnes_join"]:
        print(f"sinasc_{item['match_status']}={item['registros']}")
