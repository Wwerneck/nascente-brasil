"""Evaluate official preliminary SINAN gestational-syphilis data without publishing cases."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from zipfile import ZipFile

import datasus_dbc
from dbfread import DBF

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.metadata.manifest import append_manifest, read_manifest
from nascente_brasil.transformation.sih_pipeline import _geography
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


FILE = "SIFGBR24.dbc"
DOC = "Docs_TAB_SINAN.zip"
FIELDS = ("TP_NOT", "ID_AGRAVO", "DT_NOTIFIC", "NU_ANO", "SG_UF_NOT", "ID_MUNICIP",
          "ID_REGIONA", "DT_DIAG", "SEM_DIAG", "NU_IDADE_N", "CS_SEXO", "CS_GESTANT",
          "CS_RACA", "CS_ESCOL_N", "SG_UF", "ID_MN_RESI", "ID_RG_RESI", "ID_PAIS",
          "ID_OCUPA_N", "PRE_UFREL", "PRE_MUNIRE", "TPEVIDENCI", "TPTESTE1",
          "DSTITULO1", "DTTESTE1", "TPCONFIRMA", "TPESQUEMA", "DSMOTIVO",
          "TPMOTPARC", "TPESQPAR", "TRATPARC", "CLASSI_FIN")
SOURCE_URL = "https://www.gov.br/saude/pt-br/acesso-a-informacao/sic/dados-em-transparencia-ativa/svsa/agravos-de-notificacoes"
BASE = "ftp://ftp.datasus.gov.br/dissemin/publicos/SINAN"


def _layout(path: Path) -> dict:
    with path.open("rb") as file_obj:
        prefix = file_obj.read(32)
        if len(prefix) != 32 or prefix[0] != 3:
            raise ValueError("Invalid SINAN DBC header")
        header_length = struct.unpack("<H", prefix[8:10])[0]
        file_obj.seek(0)
        header = file_obj.read(header_length)
    fields = tuple(header[pos:pos + 11].split(b"\0", 1)[0].decode("ascii")
                   for pos in range(32, header_length - 1, 32))
    records = struct.unpack("<I", prefix[4:8])[0]
    if fields != FIELDS or header[-1] != 13 or not 50_000 <= records <= 250_000:
        raise ValueError("SINAN 2024 layout or volume differs")
    return {"records": records, "fields": len(fields), "record_length": struct.unpack("<H", prefix[10:12])[0],
            "schema_version": "dbf-fields-sha256:" + hashlib.sha256(header[32:]).hexdigest()}


def _text(value: bytes) -> str:
    return value.decode("latin1").strip()


def _audit(path: Path, geography: dict[str, str], expected: dict) -> dict:
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".dbf.part", delete=False) as file_obj:
        temp = Path(file_obj.name)
    counters = {field: Counter() for field in ("ID_AGRAVO", "NU_ANO", "CS_SEXO", "CLASSI_FIN")}
    invalid_dates = Counter()
    unmatched_residence = 0
    rows = 0
    try:
        datasus_dbc.decompress(str(path), str(temp))
        table = DBF(temp, encoding="latin1", load=False, raw=True)
        if tuple(table.field_names) != FIELDS or len(table) != expected["records"]:
            raise ValueError("SINAN decompressed DBF differs from DBC")
        for row in table:
            rows += 1
            for field in counters:
                counters[field][_text(row[field])] += 1
            for field in ("DT_NOTIFIC", "DT_DIAG", "DTTESTE1"):
                value = _text(row[field])
                if value and (len(value) != 8 or not value.isdigit()):
                    invalid_dates[field] += 1
            residence = _text(row["ID_MN_RESI"])
            if residence and residence not in geography:
                unmatched_residence += 1
    finally:
        temp.unlink(missing_ok=True)
    if rows != expected["records"] or counters["ID_AGRAVO"] != {"O981": rows} or counters["NU_ANO"] != {"2024": rows}:
        raise ValueError("SINAN 2024 agravo, year or record count differs")
    return {"rows": rows, "agravo": dict(counters["ID_AGRAVO"]), "year": dict(counters["NU_ANO"]),
            "sex": dict(counters["CS_SEXO"]), "final_classification": dict(counters["CLASSI_FIN"]),
            "invalid_date_encoding": dict(invalid_dates), "unmatched_residence": unmatched_residence}


def _manifest(settings: Settings, path: Path, *, records: int, schema: str, directory: str) -> None:
    rows = [row for row in read_manifest(settings.manifest_path) if row["source_name"] == "SINAN_SIFG"
            and row["file_name"] == path.name]
    checksum = sha256_file(path)
    if rows:
        if len(rows) != 1 or rows[0]["checksum"] != checksum or int(rows[0]["records"]) != records:
            raise ValueError(f"SINAN manifest differs: {path.name}")
        return
    append_manifest(settings.manifest_path, {
        "source_name": "SINAN_SIFG", "organization": "Ministerio da Saude / DATASUS",
        "dataset_name": "Sifilis em gestantes 2024 - avaliacao de fonte preliminar",
        "source_url": SOURCE_URL, "download_url": f"{BASE}/{directory}/{path.name}",
        "reference_period": "2024", "extraction_date": datetime.now(timezone.utc).isoformat(),
        "file_format": path.suffix[1:].upper(), "file_name": path.name,
        "file_size_bytes": path.stat().st_size, "checksum": checksum, "records": records,
        "schema_version": schema, "ingestion_status": "success",
        "processing_status": "evaluated_not_integrated", "source_etag": "", "source_last_modified": ""})


def evaluate_phase_10(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    root = settings.data_dir / "raw" / "sinan" / "original"
    dbc, docs = root / FILE, root / DOC
    layout = _layout(dbc)
    with ZipFile(docs) as archive:
        bad = archive.testzip()
        names = archive.namelist()
    if bad or not any(name.endswith("SIFIGEN_DIC_DADOS.pdf") for name in names):
        raise ValueError("SINAN documentation ZIP is corrupt or dictionary missing")
    geography = _geography(settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv")
    audit = _audit(dbc, geography, layout)
    _manifest(settings, dbc, records=layout["records"], schema=layout["schema_version"], directory="DADOS/PRELIM")
    _manifest(settings, docs, records=len(names), schema="zip-entries:" + str(len(names)), directory="DOCS")
    report = {"phase": 10, "status": "evaluated_not_integrated", "period": "2024",
              "source_status": "preliminary", "source": SOURCE_URL,
              "files": {path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
                        for path in (dbc, docs)}, "layout": layout, "audit": audit,
              "decision": "No confirmed-case or cross-source indicator is published because CLASSI_FIN is blank "
                          "for all records and the available file is preliminary. Notifications are not "
                          "equivalent to unique pregnancies or confirmed cases."}
    if audit["final_classification"] != {"": audit["rows"]}:
        raise ValueError("SINAN final classification status changed; reassess integration")
    _write_json_atomic(settings.metadata_dir / "sinan_2024_source_assessment.json", report)
    return report


def validate_phase_10(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    path = settings.metadata_dir / "sinan_2024_source_assessment.json"
    old = json.loads(path.read_text(encoding="utf-8"))
    if evaluate_phase_10(settings) != old:
        raise ValueError("SINAN source assessment changed")
    return old
