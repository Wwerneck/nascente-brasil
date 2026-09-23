"""Evaluate official SINAN 2024 source suitability."""

from nascente_brasil.validation.sinan_phase10 import evaluate_phase_10


if __name__ == "__main__":
    report = evaluate_phase_10()
    print(report["status"], report["audit"])
