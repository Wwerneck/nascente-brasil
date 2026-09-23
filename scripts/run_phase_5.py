"""Build official IBGE 2024 dimensions and audit SINASC joins."""

from nascente_brasil.logging_config import configure_logging
from nascente_brasil.transformation.ibge_pipeline import run_phase_5


if __name__ == "__main__":
    configure_logging()
    report, built = run_phase_5()
    print("Phase 5 built" if built else "Phase 5 already current")
    print(f"municipalities={report['dimension_rows']['municipio']} sinasc_rows={report['sinasc_rows']}")
    for role, metrics in report["join_metrics"].items():
        print(f"{role}: matched={metrics['matched_rows']} unmatched={metrics['unmatched_left']} rate={metrics['match_rate_pct']}%")
