"""Recompute and validate all Phase 6 CNES products."""

from nascente_brasil.transformation.cnes_pipeline import validate_phase_6


if __name__ == "__main__":
    report = validate_phase_6()
    print(f"Phase 6 validation succeeded: {report['source_rows']} monthly snapshots")
    print(f"cnes={report['distinct_cnes']} territory_match={report['territory_join']['match_rate_pct']}%")
