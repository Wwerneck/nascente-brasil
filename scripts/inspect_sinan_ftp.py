"""Inspect official SINAN FTP directories for 2024 maternal-relevant files."""

from ftplib import FTP


def main() -> None:
    with FTP("ftp.datasus.gov.br", timeout=120) as ftp:
        ftp.login()
        for directory in ("/dissemin/publicos/SINAN",
                          "/dissemin/publicos/SINAN/DADOS",
                          "/dissemin/publicos/SINAN/DADOS/FINAIS",
                          "/dissemin/publicos/SINAN/DADOS/PRELIM",
                          "/dissemin/publicos/SINAN/DOCS"):
            try:
                ftp.cwd(directory)
                names = ftp.nlst()
            except Exception as exc:
                print(directory, type(exc).__name__, str(exc))
                continue
            candidates = [name for name in names if any(term in name.upper()
                          for term in ("SIF", "SG", "GEST", "SIFIL", "DOC", "DIC"))]
            print(directory, len(names), names[:30] if len(names) < 30 else candidates[-80:])


if __name__ == "__main__":
    main()
