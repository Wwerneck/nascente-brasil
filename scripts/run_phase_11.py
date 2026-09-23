from nascente_brasil.database.postgres import load_phase_11

if __name__ == "__main__":
    print(load_phase_11()["row_counts"])
