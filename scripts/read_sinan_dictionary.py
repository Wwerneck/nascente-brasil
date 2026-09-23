"""Read the official gestational syphilis data dictionary from the source ZIP."""

import io
from zipfile import ZipFile

from pypdf import PdfReader

from nascente_brasil.config import get_settings


def main() -> None:
    archive_path = get_settings().data_dir / "raw" / "sinan" / "original" / "Docs_TAB_SINAN.zip"
    with ZipFile(archive_path) as archive:
        for suffix in ("SIFIGEN_DIC_DADOS.pdf", "SIFIGEN_NOTA_INFORMATIVA.pdf"):
            name = next(name for name in archive.namelist() if name.endswith(suffix))
            reader = PdfReader(io.BytesIO(archive.read(name)))
            print("FILE", suffix, "PAGES", len(reader.pages))
            for index, page in enumerate(reader.pages):
                print("PAGE", index + 1)
                print((page.extract_text() or "")[:20000])


if __name__ == "__main__":
    main()
