from nascente_brasil.database.postgres import validate_phase_11

if __name__ == "__main__":
    print("Phase 11 validation succeeded:", validate_phase_11()["row_counts"])
