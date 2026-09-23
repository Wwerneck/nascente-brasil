"""Recompute IBGE 2024 dimensions and SINASC territorial joins."""

from nascente_brasil.transformation.ibge_pipeline import validate_phase_5


if __name__ == "__main__":
    report = validate_phase_5()
    print(f"Phase 5 validation succeeded: {report['sinasc_rows']} SINASC rows")
    for role, metrics in report["join_metrics"].items():
        print(f"{role}: matched={metrics['matched_rows']} unmatched={metrics['unmatched_left']}")
