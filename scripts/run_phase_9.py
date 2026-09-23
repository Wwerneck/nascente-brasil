"""Build and validate national SIM/SINASC mortality indicators for 2024."""

from nascente_brasil.transformation.sim_pipeline import run_phase_9


if __name__ == "__main__":
    report, built = run_phase_9()
    print("Phase 9 built" if built else "Phase 9 already current")
    print(report["summary"])
    print({level: item["rows"] for level, item in report["gold"].items()})
