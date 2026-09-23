"""Convert the national SIM DBC to full CSV and typed Silver."""

from nascente_brasil.config import get_settings
from nascente_brasil.conversion.sim import convert_sim
from nascente_brasil.transformation.sih_pipeline import _geography


if __name__ == "__main__":
    settings = get_settings()
    geography = _geography(settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv")
    result = convert_sim(
        settings.data_dir / "raw" / "sim" / "original" / "DOBR2024.dbc",
        settings.data_dir / "raw" / "sim" / "csv" / "DOBR2024.csv.gz",
        settings.data_dir / "processed" / "sim" / "sim_2024_silver.parquet",
        geography,
    )
    print(result)
