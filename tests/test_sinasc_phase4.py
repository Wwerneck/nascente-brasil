from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
import json
import shutil

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nascente_brasil.analytics.sinasc import analyze, manual_sample, query_paths
from nascente_brasil.analytics.sinasc_pipeline import run_phase_4, validate_phase_4
from nascente_brasil.config import get_settings
from nascente_brasil.ingestion.sinasc import sha256_file


def fixture_data(tmp_path):
    rows = [
        {"data_nascimento": date(2024, 1, 1), "sexo": "1", "tipo_parto": "2", "peso_nascimento_g": 2499, "semanas_gestacao": 36, "consultas_prenatal_numero": 7},
        {"data_nascimento": date(2024, 2, 1), "sexo": "2", "tipo_parto": "1", "peso_nascimento_g": 2500, "semanas_gestacao": 37, "consultas_prenatal_numero": 6},
        {"data_nascimento": None, "sexo": "0", "tipo_parto": "9", "peso_nascimento_g": 100, "semanas_gestacao": 19, "consultas_prenatal_numero": 51},
        {"data_nascimento": date(2024, 2, 2), "sexo": "1", "tipo_parto": None, "peso_nascimento_g": None, "semanas_gestacao": None, "consultas_prenatal_numero": None},
    ]
    parquet = tmp_path / "silver.parquet"
    silver_csv = tmp_path / "silver.csv"
    pq.write_table(pa.Table.from_pylist(rows), parquet)
    with silver_csv.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return parquet, silver_csv


def test_phase4_formulas_reconciliation_and_missing_month(tmp_path):
    parquet, silver_csv = fixture_data(tmp_path)
    result = analyze(parquet, silver_csv, query_paths(get_settings().root_dir), expected_rows=4)
    national = result["national"]
    assert national["nascidos_vivos"] == 4
    assert national["partos_tipo_conhecido"] == 2
    assert national["partos_cesareos"] == 1
    assert national["pct_cesareos"] == 50.0
    assert national["peso_valido"] == 2
    assert national["baixo_peso"] == 1
    assert national["gestacao_valida"] == 2
    assert national["prematuros"] == 1
    assert national["prenatal_valido"] == 2
    assert national["prenatal_7_mais"] == 1
    assert len(result["monthly"]) == 3
    assert any(row["mes"] is None and row["nascidos_vivos"] == 1 for row in result["monthly"])
    assert result["reconciliation"]["sample_matches"]


def test_phase4_rejects_cross_file_count_mismatch(tmp_path):
    parquet, silver_csv = fixture_data(tmp_path)
    with silver_csv.open("a", encoding="utf-8", newline="") as file_obj:
        file_obj.write("2024-03-01,1,2,3000,39,8\n")
    with pytest.raises(ValueError, match="row counts differ"):
        analyze(parquet, silver_csv, query_paths(get_settings().root_dir))


def test_phase4_rejects_sample_value_mismatch(tmp_path):
    parquet, silver_csv = fixture_data(tmp_path)
    with silver_csv.open("r", encoding="utf-8", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    rows[0]["tipo_parto"] = "1"
    with silver_csv.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="Independent sample differs"):
        analyze(parquet, silver_csv, query_paths(get_settings().root_dir))


def test_manual_sample_limits_rows(tmp_path):
    _, silver_csv = fixture_data(tmp_path)
    assert manual_sample(silver_csv, 2)["nascidos_vivos"] == 2


def test_phase4_pipeline_is_idempotent_and_detects_tampering(tmp_path):
    root = tmp_path
    data_dir = root / "data"
    metadata_dir = data_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    (root / "logs").mkdir()
    (metadata_dir / "ingestion_manifest.csv").touch()
    sql_dir = root / "sql" / "duckdb"
    sql_dir.mkdir(parents=True)
    for name, source in query_paths(get_settings().root_dir).items():
        shutil.copyfile(source, sql_dir / source.name)
    parquet, silver_csv = fixture_data(data_dir)
    raw_hash = "a" * 64
    report = {
        "raw_sha256": raw_hash,
        "rows": 4,
        "silver": {
            "csv": {"path": silver_csv.relative_to(root).as_posix(), "bytes": silver_csv.stat().st_size, "sha256": sha256_file(silver_csv)},
            "parquet": {"path": parquet.relative_to(root).as_posix(), "bytes": parquet.stat().st_size, "sha256": sha256_file(parquet)},
        },
    }
    (metadata_dir / f"sinasc_2024_{raw_hash[:12]}_processing.json").write_text(json.dumps(report), encoding="utf-8")
    settings = replace(get_settings(), root_dir=root, data_dir=data_dir,
                       metadata_dir=metadata_dir, manifest_path=metadata_dir / "ingestion_manifest.csv",
                       log_dir=root / "logs")
    first, built = run_phase_4(settings, sample_size=2)
    assert built
    assert first["national"]["nascidos_vivos"] == 4
    assert not run_phase_4(settings, sample_size=2)[1]
    assert validate_phase_4(settings)["national"]["nascidos_vivos"] == 4
    output = root / first["outputs"]["national"]["path"]
    with output.open("a", encoding="utf-8") as file_obj:
        file_obj.write("changed\n")
    with pytest.raises(ValueError, match="output changed"):
        run_phase_4(settings, sample_size=2)
