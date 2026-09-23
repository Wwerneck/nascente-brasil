"""Inspect values of the official preliminary SINAN 2024 DBC."""

from collections import Counter
import os
from pathlib import Path
import tempfile

import datasus_dbc
from dbfread import DBF

from nascente_brasil.config import get_settings


def main() -> None:
    path = get_settings().data_dir / "raw" / "sinan" / "original" / "SIFGBR24.dbc"
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".dbf.part", delete=False) as file_obj:
        temp = Path(file_obj.name)
    try:
        datasus_dbc.decompress(str(path), str(temp))
        table = DBF(temp, encoding="latin1", char_decode_errors="strict", load=False, raw=True)
        fields = ("ID_AGRAVO", "NU_ANO", "CS_SEXO", "CS_GESTANT", "CLASSI_FIN",
                  "ID_MN_RESI", "SG_UF", "DT_NOTIFIC", "DT_DIAG")
        counters = {field: Counter() for field in fields}
        for row in table:
            for field in fields:
                value = row[field].decode("latin1").strip() if isinstance(row[field], bytes) else str(row[field]).strip()
                counters[field][value] += 1
        for field in fields:
            print(field, counters[field].most_common(12), "distinct", len(counters[field]))
    finally:
        os.unlink(temp)


if __name__ == "__main__":
    main()
