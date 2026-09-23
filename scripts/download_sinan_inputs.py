"""Download official preliminary gestational syphilis microdata and documentation."""

from ftplib import FTP
import os
from pathlib import Path
import tempfile

from nascente_brasil.config import get_settings
from nascente_brasil.ingestion.sinasc import sha256_file


FILES = {
    "SIFGBR24.dbc": "/dissemin/publicos/SINAN/DADOS/PRELIM",
    "Docs_TAB_SINAN.zip": "/dissemin/publicos/SINAN/DOCS",
}


def main() -> None:
    destination = get_settings().data_dir / "raw" / "sinan" / "original"
    destination.mkdir(parents=True, exist_ok=True)
    with FTP("ftp.datasus.gov.br", timeout=120) as ftp:
        ftp.login()
        for name, directory in FILES.items():
            ftp.cwd(directory)
            size = ftp.size(name)
            path = destination / name
            if path.exists():
                if path.stat().st_size != size:
                    raise ValueError(f"Existing file size differs: {name}")
            else:
                temp = None
                try:
                    with tempfile.NamedTemporaryFile(dir=destination, suffix=".part", delete=False) as file_obj:
                        temp = Path(file_obj.name)
                        ftp.retrbinary(f"RETR {name}", file_obj.write, blocksize=1024 * 1024)
                        file_obj.flush()
                        os.fsync(file_obj.fileno())
                    if temp.stat().st_size != size:
                        raise ValueError(f"Download incomplete: {name}")
                    os.replace(temp, path)
                    temp = None
                finally:
                    if temp is not None:
                        temp.unlink(missing_ok=True)
            print(name, path.stat().st_size, sha256_file(path))


if __name__ == "__main__":
    main()
