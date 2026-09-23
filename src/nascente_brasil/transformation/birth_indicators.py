"""Build validated 2024 SINASC birth indicators by residence territory."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import duckdb

from nascente_brasil.config import Settings, get_settings
from nascente_brasil.ingestion.sinasc import sha256_file
from nascente_brasil.transformation.sinasc_pipeline import _write_json_atomic


VERSION = "birth-indicators-v1"
LEVELS = {
    "brasil": ("'BR'", "'Brasil'", ""),
    "regiao": ("m.codigo_regiao", "m.regiao", "GROUP BY 2,3"),
    "estado": ("m.uf", "m.nome_uf", "GROUP BY 2,3"),
    "municipio": ("m.codigo_ibge", "m.municipio", "GROUP BY 2,3"),
}


def _literal(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _inputs(settings: Settings) -> tuple[Path, Path]:
    silver = sorted((settings.data_dir / "processed" / "sinasc").glob("*_silver.parquet"))
    if len(silver) != 1:
        raise ValueError("Expected exactly one SINASC Silver Parquet")
    return silver[0], settings.data_dir / "reference" / "ibge" / "dim_municipio_2024.csv"


def _query(level: str) -> str:
    code, label, group = LEVELS[level]
    join = "" if level == "brasil" else "JOIN municipio m ON s.codigo_municipio_residencia = m.codigo_sinasc_6"
    return f"""
      SELECT 2024 AS ano, {code} AS codigo_territorio, {label} AS territorio,
        COUNT(*)::BIGINT AS nascidos_vivos,
        COUNT(*) FILTER (WHERE tipo_parto IN ('1','2'))::BIGINT AS tipo_parto_informado,
        COUNT(*) FILTER (WHERE tipo_parto='1')::BIGINT AS nascidos_vivos_parto_vaginal,
        COUNT(*) FILTER (WHERE tipo_parto='2')::BIGINT AS nascidos_vivos_parto_cesareo,
        ROUND(100.0 * COUNT(*) FILTER (WHERE tipo_parto='2') /
          NULLIF(COUNT(*) FILTER (WHERE tipo_parto IN ('1','2')), 0), 4) AS percentual_cesareas,
        COUNT(*) FILTER (WHERE semanas_gestacao BETWEEN 20 AND 45)::BIGINT AS gestacao_informada,
        COUNT(*) FILTER (WHERE semanas_gestacao BETWEEN 20 AND 36)::BIGINT AS nascidos_vivos_prematuros,
        ROUND(100.0 * COUNT(*) FILTER (WHERE semanas_gestacao BETWEEN 20 AND 36) /
          NULLIF(COUNT(*) FILTER (WHERE semanas_gestacao BETWEEN 20 AND 45), 0), 4) AS percentual_prematuridade,
        COUNT(peso_nascimento_g)::BIGINT AS peso_informado,
        COUNT(*) FILTER (WHERE peso_nascimento_g < 2500)::BIGINT AS nascidos_vivos_baixo_peso,
        ROUND(100.0 * COUNT(*) FILTER (WHERE peso_nascimento_g < 2500) /
          NULLIF(COUNT(peso_nascimento_g), 0), 4) AS percentual_baixo_peso,
        ROUND(AVG(peso_nascimento_g), 2) AS peso_medio_g,
        COUNT(apgar_5min)::BIGINT AS apgar5_informado,
        COUNT(*) FILTER (WHERE apgar_5min < 7)::BIGINT AS apgar5_menor_7,
        ROUND(100.0 * COUNT(*) FILTER (WHERE apgar_5min < 7) /
          NULLIF(COUNT(apgar_5min), 0), 4) AS percentual_apgar5_menor_7,
        COUNT(consultas_prenatal_numero)::BIGINT AS prenatal_informado,
        COUNT(*) FILTER (WHERE consultas_prenatal_numero >= 7)::BIGINT AS prenatal_7_mais,
        ROUND(100.0 * COUNT(*) FILTER (WHERE consultas_prenatal_numero >= 7) /
          NULLIF(COUNT(consultas_prenatal_numero), 0), 4) AS percentual_prenatal_7_mais,
        COUNT(idade_mae)::BIGINT AS idade_mae_informada,
        COUNT(*) FILTER (WHERE idade_mae BETWEEN 10 AND 19)::BIGINT AS nascidos_vivos_maes_adolescentes,
        COUNT(*) FILTER (WHERE idade_mae >= 35)::BIGINT AS nascidos_vivos_idade_materna_avancada,
        COUNT(*) FILTER (WHERE tipo_gravidez IN ('1','2','3'))::BIGINT AS tipo_gravidez_informado,
        COUNT(*) FILTER (WHERE tipo_gravidez IN ('2','3'))::BIGINT AS nascidos_vivos_gestacao_multipla
      FROM sinasc s {join}
      WHERE year(data_nascimento)=2024
      {group}
      ORDER BY 2
    """


def _rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj)
        next(reader)
        return sum(1 for _ in reader)


def build_birth_indicators(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    silver, municipality = _inputs(settings)
    output_dir = settings.data_dir / "gold" / "nascimentos"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    with duckdb.connect() as connection:
        connection.execute(f"CREATE VIEW sinasc AS SELECT * FROM read_parquet('{_literal(silver)}')")
        connection.execute(f"CREATE VIEW municipio AS SELECT * FROM read_csv('{_literal(municipality)}', all_varchar=true)")
        for level in LEVELS:
            path = output_dir / f"nascimentos_{level}.csv"
            connection.execute(f"COPY ({_query(level)}) TO '{_literal(path)}' (HEADER, DELIMITER ',')")
            outputs[level] = {"path": path.relative_to(settings.root_dir).as_posix(), "rows": _rows(path),
                              "sha256": sha256_file(path), "bytes": path.stat().st_size}
        national = connection.execute(_query("brasil")).fetchone()
        if national[3] != 2_389_325:
            raise ValueError("National SINASC total differs")
        state_total = connection.execute("SELECT SUM(nascidos_vivos) FROM read_csv(?)", [str(output_dir / "nascimentos_estado.csv")]).fetchone()[0]
        unmatched = national[3] - state_total
    report = {"version": VERSION, "built_at": datetime.now(timezone.utc).isoformat(),
              "inputs": {"sinasc_silver": sha256_file(silver), "municipality": sha256_file(municipality)},
              "outputs": outputs, "national_births": national[3], "unmatched_residence": unmatched}
    _write_json_atomic(settings.metadata_dir / "birth_indicators_2024.json", report)
    return report


def validate_birth_indicators(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    report = json.loads((settings.metadata_dir / "birth_indicators_2024.json").read_text(encoding="utf-8"))
    silver, municipality = _inputs(settings)
    if report["version"] != VERSION or report["inputs"] != {
        "sinasc_silver": sha256_file(silver), "municipality": sha256_file(municipality)}:
        raise ValueError("Birth indicator inputs differ")
    for level, item in report["outputs"].items():
        path = settings.root_dir / item["path"]
        if _rows(path) != item["rows"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Birth indicator output differs: {level}")
    return report
