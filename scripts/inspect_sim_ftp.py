"""Read only the national SIM DBC header from the official FTP."""

from ftplib import FTP
import struct

from nascente_brasil.ingestion.sim import DIRECTORY, FILE, HOST


class HeaderReceived(Exception):
    pass


if __name__ == "__main__":
    chunks = bytearray()

    def receive(block):
        chunks.extend(block)
        if len(chunks) >= 16_384:
            raise HeaderReceived

    ftp = FTP(HOST, timeout=30)
    try:
        ftp.login()
        ftp.cwd(DIRECTORY)
        try:
            ftp.retrbinary(f"RETR {FILE}", receive)
        except HeaderReceived:
            pass
    finally:
        ftp.close()
    header_length = struct.unpack("<H", chunks[8:10])[0]
    record_length = struct.unpack("<H", chunks[10:12])[0]
    records = struct.unpack("<I", chunks[4:8])[0]
    fields = tuple(chunks[p:p + 11].split(b"\0", 1)[0].decode("ascii")
                   for p in range(32, header_length - 1, 32))
    print("header", chunks[0], header_length, record_length, records, len(fields), chunks[header_length - 1])
    print(fields)
