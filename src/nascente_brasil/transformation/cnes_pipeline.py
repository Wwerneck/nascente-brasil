"""Convert, type, enrich and validate CNES hospital capacity snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from unicodedata import combining, normalize

import duckdb
import pandas as pd

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.cnes import SOURCE_COLUMNS, ingest_cnes_raw
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.logging_config import get_logger
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


PIPELINE_VERSION = "phase6-v2"
COLUMN_MAP = {
    "COMP": "competencia", "REGIAO": "regiao_fonte", "UF": "uf", "MUNICIPIO": "municipio_fonte",
    "MOTIVO_DESABILITACAO": "motivo_desabilitacao", "CNES": "codigo_cnes",
    "NOME_ESTABELECIMENTO": "nome_estabelecimento", "RAZAO_SOCIAL": "razao_social",
    "TP_GESTAO": "tipo_gestao", "CO_TIPO_UNIDADE": "codigo_tipo_unidade",
    "DS_TIPO_UNIDADE": "tipo_unidade", "NATUREZA_JURIDICA": "codigo_natureza_juridica",
    "DESC_NATUREZA_JURIDICA": "natureza_juridica", "NO_LOGRADOURO": "logradouro",
    "NU_ENDERECO": "numero_endereco", "NO_COMPLEMENTO": "complemento", "NO_BAIRRO": "bairro",
    "CO_CEP": "cep", "NU_TELEFONE": "telefone", "NO_EMAIL": "email",
    "LEITOS_EXISTENTES": "leitos_existentes", "LEITOS_SUS": "leitos_sus",
    "UTI_TOTAL_EXIST": "uti_total_existentes", "UTI_TOTAL_SUS": "uti_total_sus",
    "UTI_ADULTO_EXIST": "uti_adulto_existentes", "UTI_ADULTO_SUS": "uti_adulto_sus",
    "UTI_PEDIATRICO_EXIST": "uti_pediatrica_existentes", "UTI_PEDIATRICO_SUS": "uti_pediatrica_sus",
    "UTI_NEONATAL_EXIST": "uti_neonatal_existentes", "UTI_NEONATAL_SUS": "uti_neonatal_sus",
    "UTI_QUEIMADO_EXIST": "uti_queimados_existentes", "UTI_QUEIMADO_SUS": "uti_queimados_sus",
    "UTI_CORONARIANA_EXIST": "uti_coronariana_existentes", "UTI_CORONARIANA_SUS": "uti_coronariana_sus",
}
NUMERIC_COLUMNS = tuple(value for key, value in COLUMN_MAP.items() if key.startswith(("LEITOS_", "UTI_")))
IDENTITY_COLUMNS = ("nome_estabelecimento", "razao_social", "uf", "municipio_fonte", "codigo_tipo_unidade",
                    "tipo_unidade", "codigo_natureza_juridica", "natureza_juridica")
TERRITORY_ALIASES = {
    ("BA", "SANTA TERESINHA"): "SANTA TEREZINHA",
    ("CE", "ITAPAGE"): "ITAPAJE",
    ("MG", "BRASOPOLIS"): "BRAZOPOLIS",
    ("MT", "POXOREO"): "POXOREU",
    ("MT", "SANTO ANTONIO DO LEVERGER"): "SANTO ANTONIO DE LEVERGER",
    ("PA", "ELDORADO DOS CARAJAS"): "ELDORADO DO CARAJAS",
    ("PB", "SERIDO"): "SAO VICENTE DO SERIDO",
    ("PE", "BELEM DE SAO FRANCISCO"): "BELEM DO SAO FRANCISCO",
    ("PE", "IGUARACI"): "IGUARACY",
    ("PE", "LAGOA DO ITAENGA"): "LAGOA DE ITAENGA",
    ("RJ", "PARATI"): "PARATY",
    ("RJ", "TRAJANO DE MORAIS"): "TRAJANO DE MORAES",
    ("RN", "AUGUSTO SEVERO"): "CAMPO GRANDE",
    ("RN", "PRESIDENTE JUSCELINO"): "SERRA CAIADA",
    ("RS", "SANTANA DO LIVRAMENTO"): "SANT ANA DO LIVRAMENTO",
    ("SP", "MOJI MIRIM"): "MOGI MIRIM",
    ("SP", "SAO LUIS DO PARAITINGA"): "SAO LUIZ DO PARAITINGA",
}


def _artifact(path: Path, root: Path, rows: int) -> dict:
    return {"path": path.relative_to(root).as_posix(), "rows": rows, "bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def _text_key(value: str) -> str:
    value = "".join(char for char in normalize("NFKD", value) if not combining(char)).upper()
    return re.sub(r"[^A-Z0-9]+", " ", value).strip()


def _atomic_dataframe(frame: pd.DataFrame, path: Path, *, parquet: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as file_obj:
            temp = Path(file_obj.name)
        if parquet:
            frame.to_parquet(temp, index=False)
        else:
            frame.to_csv(temp, index=False, encoding="utf-8", lineterminator="\n")
        os.replace(temp, path)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _load_and_type(path: Path) -> tuple[pd.DataFrame, dict]:
    source = pd.read_csv(path, encoding="latin1", dtype="string", keep_default_na=False)
    if tuple(source.columns) != SOURCE_COLUMNS:
        raise ValueError("CNES source schema differs during transformation")
    frame = source.rename(columns=COLUMN_MAP)
    frame = frame.replace("", pd.NA)
    invalid_numeric = {}
    for column in NUMERIC_COLUMNS:
        converted = pd.to_numeric(frame[column], errors="coerce")
        invalid_numeric[column] = int((frame[column].notna() & converted.isna()).sum())
        frame[column] = converted.astype("Int64")
    if any(invalid_numeric.values()) or frame[list(NUMERIC_COLUMNS)].lt(0).any().any():
        raise ValueError(f"CNES has invalid or negative capacity values: {invalid_numeric}")
    if frame.duplicated(["competencia", "codigo_cnes"]).any():
        raise ValueError("CNES monthly grain is duplicated")
    components_exist = ["uti_adulto_existentes", "uti_pediatrica_existentes", "uti_neonatal_existentes",
                        "uti_queimados_existentes", "uti_coronariana_existentes"]
    components_sus = ["uti_adulto_sus", "uti_pediatrica_sus", "uti_neonatal_sus", "uti_queimados_sus", "uti_coronariana_sus"]
    quality = {
        "invalid_numeric": invalid_numeric,
        "negative_values": int(frame[list(NUMERIC_COLUMNS)].lt(0).sum().sum()),
        "uti_total_existing_component_mismatch": int(frame["uti_total_existentes"].ne(frame[components_exist].sum(axis=1)).sum()),
        "uti_total_sus_component_mismatch": int(frame["uti_total_sus"].ne(frame[components_sus].sum(axis=1)).sum()),
        "leitos_sus_above_existing": int(frame["leitos_sus"].gt(frame["leitos_existentes"]).sum()),
        "uti_sus_above_existing": int(sum(frame[sus].gt(frame[exist]).sum() for sus, exist in (
            ("uti_total_sus", "uti_total_existentes"), ("uti_adulto_sus", "uti_adulto_existentes"),
            ("uti_pediatrica_sus", "uti_pediatrica_existentes"), ("uti_neonatal_sus", "uti_neonatal_existentes"),
            ("uti_queimados_sus", "uti_queimados_existentes"), ("uti_coronariana_sus", "uti_coronariana_existentes")))),
        "missing": {column: int(frame[column].isna().sum()) for column in frame.columns},
    }
    return frame, quality


def _geography(frame: pd.DataFrame, dimension_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    dimension = pd.read_csv(dimension_path, dtype="string", keep_default_na=False)
    dimension["join_key"] = dimension["uf"].map(_text_key) + "|" + dimension["municipio"].map(_text_key)
    if dimension["join_key"].duplicated().any():
        raise ValueError("Normalized IBGE UF/municipality keys are duplicated")
    locations = frame.groupby(["uf", "municipio_fonte"], dropna=False).size().rename("registros").reset_index()
    locations["municipio_normalizado"] = locations["municipio_fonte"].fillna("").map(_text_key)
    locations["municipio_join"] = [TERRITORY_ALIASES.get((uf, name), name)
                                     for uf, name in zip(locations["uf"], locations["municipio_normalizado"])]
    locations["match_method"] = (locations["municipio_join"] != locations["municipio_normalizado"]).map(
        {True: "explicit_alias", False: "normalized_name"})
    locations["join_key"] = locations["uf"].fillna("").map(_text_key) + "|" + locations["municipio_join"]
    lookup = dimension[["join_key", "codigo_ibge", "municipio", "codigo_uf", "nome_uf", "codigo_regiao", "regiao"]]
    audit = locations.merge(lookup, on="join_key", how="left", validate="many_to_one")
    audit["match_status"] = audit["codigo_ibge"].notna().map({True: "matched", False: "unmatched"})
    enriched = frame.copy()
    source_names = enriched["municipio_fonte"].fillna("").map(_text_key)
    joined_names = pd.Series([TERRITORY_ALIASES.get((uf, name), name)
                              for uf, name in zip(enriched["uf"], source_names)], index=enriched.index)
    enriched["territory_match_method"] = joined_names.ne(source_names).map(
        {True: "explicit_alias", False: "normalized_name"})
    enriched["join_key"] = enriched["uf"].fillna("").map(_text_key) + "|" + joined_names
    enriched = enriched.merge(lookup, on="join_key", how="left", validate="many_to_one")
    enriched["territory_match_status"] = enriched["codigo_ibge"].notna().map({True: "matched", False: "unmatched"})
    matched = int(enriched["codigo_ibge"].notna().sum())
    metrics = {"left_rows": len(frame), "right_rows": len(dimension), "matched_rows": matched,
               "unmatched_left": len(frame) - matched, "duplicated_keys": 0,
               "match_rate_pct": round(100 * matched / len(frame), 4),
               "alias_rows": int(enriched["territory_match_method"].eq("explicit_alias").sum()),
               "aliases": [{"uf": uf, "source_name": source, "ibge_name": target}
                           for (uf, source), target in sorted(TERRITORY_ALIASES.items())],
               "unmatched_locations": audit.loc[audit["match_status"] == "unmatched", ["uf", "municipio_fonte", "registros"]].to_dict("records")}
    return enriched.drop(columns="join_key"), audit.drop(columns="join_key"), metrics


def _products(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    fact_columns = ["competencia", "codigo_cnes", "codigo_ibge", "territory_match_status", "territory_match_method", *NUMERIC_COLUMNS]
    fact = frame[fact_columns].copy()
    ordered = frame.sort_values(["codigo_cnes", "competencia"])
    latest = ordered.groupby("codigo_cnes", as_index=False).tail(1).copy()
    observations = ordered.groupby("codigo_cnes").agg(
        competencia_inicio=("competencia", "min"), competencia_fim=("competencia", "max"),
        competencias_observadas=("competencia", "nunique"),
    ).reset_index()
    versions = ordered.groupby("codigo_cnes").apply(
        lambda group: group[list(IDENTITY_COLUMNS)].astype("string").fillna("").drop_duplicates().shape[0],
        include_groups=False,
    ).rename("versoes_atributos").reset_index()
    dim_columns = ["codigo_cnes", *IDENTITY_COLUMNS, "tipo_gestao", "codigo_ibge", "municipio", "codigo_uf",
                   "nome_uf", "codigo_regiao", "regiao", "territory_match_status", "territory_match_method"]
    dimension = latest[dim_columns].merge(observations, on="codigo_cnes", validate="one_to_one").merge(versions, on="codigo_cnes", validate="one_to_one")
    return dimension.sort_values("codigo_cnes"), fact.sort_values(["competencia", "codigo_cnes"])


def _sinasc_audit(sinasc_path: Path, fact: pd.DataFrame, sql_path: Path) -> list[dict]:
    with duckdb.connect() as connection:
        connection.read_parquet(str(sinasc_path)).create_view("sinasc")
        connection.register("fact_capacidade", fact[["competencia", "codigo_cnes"]])
        result = connection.execute(sql_path.read_text(encoding="utf-8"))
        return [{column[0]: value for column, value in zip(result.description, row)} for row in result.fetchall()]


def _verify_outputs(report: dict, settings: Settings) -> bool:
    missing = False
    for item in report["outputs"].values():
        path = settings.root_dir / item["path"]
        if not path.exists():
            missing = True
        elif _artifact(path, settings.root_dir, item["rows"]) != item:
            raise ValueError(f"CNES Phase 6 output changed: {path}")
    return not missing


def run_phase_6(settings: Settings | None = None) -> tuple[dict, bool]:
    settings = settings or get_settings()
    settings.validate()
    raw, _ = ingest_cnes_raw(settings)
    phase3_reports = sorted(settings.metadata_dir.glob("sinasc_2024_*_processing.json"))
    if len(phase3_reports) != 1:
        raise ValueError("Expected one SINASC 2024 processing report")
    phase3 = json.loads(phase3_reports[0].read_text(encoding="utf-8"))
    sinasc_path = settings.root_dir / phase3["silver"]["parquet"]["path"]
    dim_municipio_path = settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv"
    sql_path = settings.root_dir / "sql" / "duckdb" / "sinasc_2024_cnes_temporal_join.sql"
    inputs = {"cnes_sha256": raw["CNES_LEITOS"]["sha256"], "dictionary_sha256": raw["CNES_DICIONARIO_LEITOS"]["sha256"],
              "sinasc_sha256": phase3["silver"]["parquet"]["sha256"], "ibge_dimension_sha256": sha256_file(dim_municipio_path),
              "sql_sha256": sha256_file(sql_path)}
    report_path = settings.metadata_dir / "cnes_leitos_2024_processing.json"
    if report_path.exists():
        old = json.loads(report_path.read_text(encoding="utf-8"))
        if old.get("pipeline_version") == PIPELINE_VERSION and old.get("inputs") == inputs and _verify_outputs(old, settings):
            return old, False
    frame, quality = _load_and_type(raw["CNES_LEITOS"]["path"])
    enriched, territory_audit, territory_metrics = _geography(frame, dim_municipio_path)
    dimension, fact = _products(enriched)
    sinasc_audit = _sinasc_audit(sinasc_path, fact, sql_path)
    if sum(row["registros"] for row in sinasc_audit) != phase3["rows"]:
        raise ValueError("SINASC/CNES temporal join does not reconcile")
    raw_csv = settings.data_dir / "raw" / "cnes" / "csv" / "leitos_2024_utf8.csv"
    silver_csv = settings.data_dir / "processed" / "cnes" / "cnes_leitos_2024_silver.csv"
    silver_parquet = settings.data_dir / "processed" / "cnes" / "cnes_leitos_2024_silver.parquet"
    reference = settings.data_dir / "reference" / "cnes"
    processed = settings.data_dir / "processed" / "cnes"
    artifacts = {
        "raw_csv": (raw_csv, frame, False), "silver_csv": (silver_csv, enriched, False),
        "silver_parquet": (silver_parquet, enriched, True),
        "dim_estabelecimento": (reference / "dim_estabelecimento_2024.csv", dimension, False),
        "fact_capacidade_csv": (processed / "fact_capacidade_hospitalar_2024.csv", fact, False),
        "fact_capacidade_parquet": (processed / "fact_capacidade_hospitalar_2024.parquet", fact, True),
        "territory_audit": (processed / "cnes_2024_territory_audit.csv", territory_audit, False),
        "sinasc_cnes_audit": (processed / "sinasc_2024_cnes_temporal_audit.csv", pd.DataFrame(sinasc_audit), False),
    }
    outputs = {}
    for name, (path, data, parquet) in artifacts.items():
        _atomic_dataframe(data, path, parquet=parquet)
        outputs[name] = _artifact(path, settings.root_dir, len(data))
    report = {"pipeline_version": PIPELINE_VERSION, "processed_at": datetime.now(timezone.utc).isoformat(),
              "reference_period": "2024", "inputs": inputs, "source_rows": len(frame),
              "competencies": sorted(frame["competencia"].unique().tolist()), "distinct_cnes": int(frame["codigo_cnes"].nunique()),
              "dimension_rows": len(dimension), "fact_rows": len(fact), "quality": quality,
              "territory_join": territory_metrics, "sinasc_cnes_join": sinasc_audit, "outputs": outputs}
    _write_json_atomic(report_path, report)
    get_logger("transformation.cnes").info("CNES Phase 6 validated", extra={"pipeline": "cnes_2024", "task": "transform_join",
        "source": "CNES", "rows_in": len(frame), "rows_out": len(fact), "rows_invalid": territory_metrics["unmatched_left"], "status": "success"})
    return report, True


def validate_phase_6(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    settings.validate()
    raw, _ = ingest_cnes_raw(settings)
    report_path = settings.metadata_dir / "cnes_leitos_2024_processing.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    phase3_reports = sorted(settings.metadata_dir.glob("sinasc_2024_*_processing.json"))
    if len(phase3_reports) != 1:
        raise ValueError("Expected one SINASC 2024 processing report")
    phase3 = json.loads(phase3_reports[0].read_text(encoding="utf-8"))
    sinasc_path = settings.root_dir / phase3["silver"]["parquet"]["path"]
    dim_municipio_path = settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv"
    sql_path = settings.root_dir / "sql" / "duckdb" / "sinasc_2024_cnes_temporal_join.sql"
    inputs = {"cnes_sha256": raw["CNES_LEITOS"]["sha256"], "dictionary_sha256": raw["CNES_DICIONARIO_LEITOS"]["sha256"],
              "sinasc_sha256": phase3["silver"]["parquet"]["sha256"], "ibge_dimension_sha256": sha256_file(dim_municipio_path),
              "sql_sha256": sha256_file(sql_path)}
    if report["pipeline_version"] != PIPELINE_VERSION or report["inputs"] != inputs or not _verify_outputs(report, settings):
        raise ValueError("CNES Phase 6 metadata, inputs, SQL or outputs differ")
    frame, quality = _load_and_type(raw["CNES_LEITOS"]["path"])
    enriched, territory_audit, territory_metrics = _geography(frame, dim_municipio_path)
    dimension, fact = _products(enriched)
    sinasc_audit = _sinasc_audit(sinasc_path, fact, sql_path)
    expected = {
        "source_rows": len(frame), "competencies": sorted(frame["competencia"].unique().tolist()),
        "distinct_cnes": int(frame["codigo_cnes"].nunique()), "dimension_rows": len(dimension),
        "fact_rows": len(fact), "quality": quality, "territory_join": territory_metrics,
        "sinasc_cnes_join": sinasc_audit,
    }
    for key, value in expected.items():
        if report[key] != value:
            raise ValueError(f"CNES Phase 6 recomputed value differs: {key}")
    published_fact = pd.read_parquet(settings.root_dir / report["outputs"]["fact_capacidade_parquet"]["path"])
    published_silver = pd.read_parquet(settings.root_dir / report["outputs"]["silver_parquet"]["path"])
    pd.testing.assert_frame_equal(published_fact.reset_index(drop=True), fact.reset_index(drop=True), check_dtype=True)
    pd.testing.assert_frame_equal(published_silver.reset_index(drop=True), enriched.reset_index(drop=True), check_dtype=True)
    if len(territory_audit) != report["outputs"]["territory_audit"]["rows"]:
        raise ValueError("CNES territory audit row count differs")
    return report
