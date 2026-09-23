"""Show SINAN 2024 layout and relevant documentation inventory."""

import struct
from zipfile import ZipFile

from nascente_brasil.config import get_settings


def main() -> None:
    root = get_settings().data_dir / "raw" / "sinan" / "original"
    with (root / "SIFGBR24.dbc").open("rb") as file_obj:
        prefix = file_obj.read(32)
        header_length = struct.unpack("<H", prefix[8:10])[0]
        file_obj.seek(0)
        header = file_obj.read(header_length)
    fields = [header[pos:pos + 11].split(b"\0", 1)[0].decode("ascii")
              for pos in range(32, header_length - 1, 32)]
    print("records", struct.unpack("<I", prefix[4:8])[0], "record_length",
          struct.unpack("<H", prefix[10:12])[0], "fields", len(fields))
    print(fields)
    with ZipFile(root / "Docs_TAB_SINAN.zip") as archive:
        names = archive.namelist()
        print("documentation_entries", len(names))
        print("documentation_sample", names[:50])
        print("documentation_tail", names[-80:])
        print([name for name in names if any(term in name.lower()
              for term in ("sifil", "sifg", "sifilis", "gest"))][:100])


if __name__ == "__main__":
    main()
