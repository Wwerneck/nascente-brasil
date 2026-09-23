"""Download and validate national SIM 2024 microdata."""

from nascente_brasil.ingestion.sim import ingest_sim_2024


if __name__ == "__main__":
    check, built = ingest_sim_2024()
    print("SIM 2024 RAW downloaded" if built else "SIM 2024 RAW already current")
    print(f"rows={check.records} bytes={check.size} fields={len(check.fields)}")
    print(check.fields)
