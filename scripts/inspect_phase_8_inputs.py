"""Inspect observed SIH obstetric diagnosis and AIH distributions."""

import duckdb

from nascente_brasil.config import get_settings


if __name__ == "__main__":
    pattern = (get_settings().data_dir / "processed" / "sih" / "silver" / "**" / "*.parquet").as_posix()
    with duckdb.connect() as connection:
        for sql in (
            "SELECT substr(diagnostico_principal, 1, 3) cid, COUNT(*) n "
            "FROM read_parquet(?) WHERE diagnostico_principal LIKE 'O%' GROUP BY 1 ORDER BY n DESC LIMIT 30",
            "SELECT tipo_aih, sexo, COUNT(*) n FROM read_parquet(?) "
            "WHERE diagnostico_principal LIKE 'O%' GROUP BY 1, 2 ORDER BY n DESC",
            "SELECT COUNT(*) FROM read_parquet(?) WHERE tipo_aih = '1' AND diagnostico_principal LIKE 'O%'",
        ):
            print(connection.execute(sql, [pattern]).fetchall())
