"""Recheck the SINAN source assessment and manifest."""

from nascente_brasil.validation.sinan_phase10 import validate_phase_10


if __name__ == "__main__":
    report = validate_phase_10()
    print("Phase 10 validation succeeded:", report["audit"]["rows"], "source records")
