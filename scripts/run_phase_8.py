"""Build maternal morbidity reference, fact and four territorial Gold CSVs."""

from nascente_brasil.transformation.maternal_pipeline import run_phase_8


if __name__ == "__main__":
    report, built = run_phase_8()
    print("Phase 8 built" if built else "Phase 8 already current")
    print(report["audit"])
    print({level: item["rows"] for level, item in report["gold"].items()})
