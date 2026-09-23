"""Build local SINASC 2024 indicators in DuckDB."""

from nascente_brasil.analytics.sinasc_pipeline import run_phase_4
from nascente_brasil.logging_config import configure_logging


if __name__ == "__main__":
    configure_logging()
    report, built = run_phase_4()
    print("Phase 4 built" if built else "Phase 4 already current")
    print(f"rows={report['national']['nascidos_vivos']} sample={report['reconciliation']['sample_rows']}")
    for name, item in report["outputs"].items():
        print(f"{name}={item['path']}")
