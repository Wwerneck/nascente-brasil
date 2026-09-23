"""Validated, locally cached official IBGE 2024 territorial inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from unicodedata import combining, normalize
from zipfile import BadZipFile, ZipFile

import pandas as pd
import requests

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sinasc import create_session, sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.metadata.manifest import append_manifest, read_manifest


YEAR = "2024"
DTB_URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2024/DTB_2024.zip"
UF_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
DTB_MEMBER = "RELATORIO_DTB_BRASIL_2024_MUNICIPIOS.ods"
DTB_FILE = "DTB_2024.zip"
UF_FILE = "ibge_estados_api.json"


def read_dtb(path: Path) -> pd.DataFrame:
    if not 100_000 <= path.stat().st_size <= 20_000_000:
        raise ValueError("IBGE DTB archive size is implausible")
    try:
        with ZipFile(path) as archive:
            members = archive.namelist()
            if DTB_MEMBER not in members or any(not name.endswith((".ods", ".xls")) for name in members):
                raise ValueError("IBGE DTB ZIP member schema changed")
            if archive.testzip() is not None:
                raise ValueError("IBGE DTB ZIP CRC failed")
            frame = pd.read_excel(BytesIO(archive.read(DTB_MEMBER)), engine="odf", header=6, dtype=str)
    except BadZipFile as exc:
        raise ValueError("IBGE DTB ZIP is corrupt") from exc
    expected = ["UF", "Nome_UF", "Regiao Geografica Intermediaria", "Nome Regiao Geografica Intermediaria",
                "Regiao Geografica Imediata", "Nome Regiao Geografica Imediata", "Municipio",
                "Codigo Municipio Completo", "Nome_Municipio"]
    actual = ["".join(c for c in normalize("NFKD", name) if not combining(c))
              for name in frame.columns[:9]]
    if actual != expected or len(frame) < 5500 or len(frame) > 5600:
        raise ValueError(f"IBGE DTB municipal schema or volume changed: {actual}, {len(frame)}")
    frame = frame.iloc[:, :9].copy()
    frame.columns = ("codigo_uf", "nome_uf", "codigo_regiao_intermediaria", "nome_regiao_intermediaria",
                     "codigo_regiao_imediata", "nome_regiao_imediata", "codigo_municipio_5",
                     "codigo_ibge", "municipio")
    if (frame[["codigo_uf", "nome_uf", "codigo_ibge", "municipio"]].isna().any().any()
            or frame[["codigo_uf", "nome_uf", "codigo_ibge", "municipio"]].eq("").any().any()
            or not frame["codigo_ibge"].str.fullmatch(r"\d{7}").all()
            or frame["codigo_ibge"].duplicated().any()
            or frame["codigo_ibge"].str[:6].duplicated().any()
            or not (frame["codigo_ibge"].str[:2] == frame["codigo_uf"]).all()
            or frame["codigo_uf"].nunique() != 27):
        raise ValueError("IBGE DTB municipal codes are invalid or duplicated")
    return frame


def read_ufs(path: Path) -> list[dict]:
    if not 1000 <= path.stat().st_size <= 1_000_000:
        raise ValueError("IBGE UF API response size is implausible")
    try:
        items = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("IBGE UF API response is not valid JSON") from exc
    if (not isinstance(items, list) or len(items) != 27
            or len({str(item["id"]) for item in items}) != 27
            or len({item["sigla"] for item in items}) != 27
            or {item["regiao"]["id"] for item in items} != {1, 2, 3, 4, 5}):
        raise ValueError("IBGE UF API schema or count changed")
    return items


def _download(session: requests.Session, url: str, directory: Path, *, zip_file: bool) -> tuple[Path, dict]:
    temp: Path | None = None
    try:
        with session.get(url, stream=True, timeout=(15, 120)) as response:
            response.raise_for_status()
            length = response.headers.get("Content-Length")
            if length and int(length) > 20_000_000:
                raise ValueError("IBGE response exceeds size limit")
            with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as file_obj:
                temp = Path(file_obj.name)
                size = 0
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    size += len(chunk)
                    if size > 20_000_000:
                        raise ValueError("IBGE response exceeds size limit")
                    file_obj.write(chunk)
            if length and int(length) != size:
                raise ValueError("Incomplete IBGE download")
            with temp.open("rb") as file_obj:
                first = file_obj.read(4)
            if zip_file and not first.startswith(b"PK\x03\x04"):
                raise ValueError("IBGE DTB response is not a ZIP")
            if not zip_file and first[:1] != b"[":
                raise ValueError("IBGE UF response is not a JSON list")
            result = temp
            temp = None
            return result, dict(response.headers)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def ingest_ibge_raw(settings: Settings | None = None, session: requests.Session | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    directory = settings.data_dir / "raw" / "ibge" / "original"
    directory.mkdir(parents=True, exist_ok=True)
    existing = read_manifest(settings.manifest_path)
    owned = session is None
    session = session or create_session()
    logger = get_logger("ingestion.ibge")
    result = {}
    try:
        for name, filename, url, validator, period, format_name in (
            ("IBGE_DTB", DTB_FILE, DTB_URL, read_dtb, YEAR, "ZIP/ODS"),
            ("IBGE_UF", UF_FILE, UF_URL, read_ufs, "snapshot", "JSON"),
        ):
            path = directory / filename
            headers = {}
            if not path.exists():
                temp, headers = _download(session, url, directory, zip_file=name == "IBGE_DTB")
                try:
                    validator(temp)
                    os.replace(temp, path)
                finally:
                    temp.unlink(missing_ok=True)
            data = validator(path)
            digest = sha256_file(path)
            previous = [row for row in existing if row["source_name"] == name and row["reference_period"] == period]
            if previous and any(row["checksum"] != digest or int(row["file_size_bytes"]) != path.stat().st_size
                                or int(row["records"]) != len(data) or row["download_url"] != url for row in previous):
                raise ValueError(f"Existing IBGE input differs from manifested snapshot: {path}")
            if not previous:
                append_manifest(settings.manifest_path, {
                    "source_name": name, "organization": "IBGE", "dataset_name": "Divisao Territorial Brasileira 2024" if name == "IBGE_DTB" else "Localidades - Estados",
                    "source_url": url, "download_url": url, "reference_period": period,
                    "extraction_date": datetime.now(timezone.utc).isoformat(), "file_format": format_name,
                    "file_name": filename, "file_size_bytes": path.stat().st_size, "checksum": digest,
                    "records": len(data), "schema_version": "dtb-2024-municipios-v1" if name == "IBGE_DTB" else "localidades-estados-v1",
                    "ingestion_status": "success", "processing_status": "raw_validated",
                    "source_etag": headers.get("ETag", ""), "source_last_modified": headers.get("Last-Modified", ""),
                })
            result[name] = {"path": path, "sha256": digest, "rows": len(data)}
            logger.info("IBGE RAW validated", extra={"pipeline": "ibge_raw", "task": "validate", "source": name,
                                                  "file": str(path), "rows_in": len(data), "rows_out": len(data), "rows_invalid": 0, "status": "success"})
        return result
    except Exception as exc:
        logger.exception("IBGE RAW ingestion failed", extra={"pipeline": "ibge_raw", "task": "validate", "source": "IBGE", "status": "failed", "error": str(exc)})
        raise
    finally:
        if owned:
            session.close()
