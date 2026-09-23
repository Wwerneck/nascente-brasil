"""Local DuckDB indicators and independent SINASC reconciliation."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import duckdb


COUNT_COLUMNS = (
    "nascidos_vivos", "partos_tipo_conhecido", "partos_cesareos",
    "peso_valido", "baixo_peso", "gestacao_valida", "prematuros",
    "prenatal_valido", "prenatal_7_mais",
)
QUERY_NAMES = ("national", "monthly", "sex")


def query_paths(root: Path) -> dict[str, Path]:
    return {name: root / "sql" / "duckdb" / f"sinasc_2024_{name}.sql" for name in QUERY_NAMES}


def _rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    result = connection.execute(sql)
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _number(value: str | None) -> int | None:
    return int(value) if value else None


def manual_sample(csv_path: Path, limit: int) -> dict[str, int]:
    counts = dict.fromkeys(COUNT_COLUMNS, 0)
    with csv_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for index, row in enumerate(reader):
            if index >= limit:
                break
            counts["nascidos_vivos"] += 1
            delivery = row["tipo_parto"]
            if delivery in ("1", "2"):
                counts["partos_tipo_conhecido"] += 1
            if delivery == "2":
                counts["partos_cesareos"] += 1
            weight = _number(row["peso_nascimento_g"])
            if weight is not None and 200 <= weight <= 7000:
                counts["peso_valido"] += 1
                if weight < 2500:
                    counts["baixo_peso"] += 1
            weeks = _number(row["semanas_gestacao"])
            if weeks is not None and 20 <= weeks <= 45:
                counts["gestacao_valida"] += 1
                if weeks < 37:
                    counts["prematuros"] += 1
            visits = _number(row["consultas_prenatal_numero"])
            if visits is not None and 0 <= visits <= 50:
                counts["prenatal_valido"] += 1
                if visits >= 7:
                    counts["prenatal_7_mais"] += 1
    return counts


def count_csv_rows(csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj, strict=True)
        width = len(next(reader))
        count = 0
        for row in reader:
            if len(row) != width:
                raise ValueError("Silver CSV has a row with the wrong number of columns")
            count += 1
    return count


def analyze(parquet_path: Path, csv_path: Path, sql_paths: dict[str, Path], *,
            expected_rows: int | None = None, sample_size: int = 1000) -> dict:
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    queries = {name: path.read_text(encoding="utf-8") for name, path in sql_paths.items()}
    with duckdb.connect() as connection:
        connection.read_parquet(str(parquet_path)).create_view("sinasc")
        national = _rows(connection, queries["national"])[0]
        monthly = _rows(connection, queries["monthly"])
        sex = _rows(connection, queries["sex"])
        csv_rows = count_csv_rows(csv_path)
        if csv_rows != national["nascidos_vivos"] or (expected_rows is not None and csv_rows != expected_rows):
            raise ValueError("Silver CSV, Parquet and expected row counts differ")
        for column in COUNT_COLUMNS:
            if sum(row[column] for row in monthly) != national[column]:
                raise ValueError(f"Monthly aggregation differs: {column}")
        if sum(row["nascidos_vivos"] for row in sex) != national["nascidos_vivos"]:
            raise ValueError("Sex aggregation differs from national total")
        actual_sample_size = min(sample_size, csv_rows)
        sample = manual_sample(csv_path, actual_sample_size)
        with duckdb.connect() as sample_connection:
            sample_connection.read_parquet(str(parquet_path)).limit(actual_sample_size).create_view("sinasc")
            sql_sample = _rows(sample_connection, queries["national"])[0]
        for column in COUNT_COLUMNS:
            if sample[column] != sql_sample[column]:
                raise ValueError(f"Independent sample differs: {column}")
    return {"national": national, "monthly": monthly, "sex": sex,
            "reconciliation": {"silver_csv_rows": csv_rows, "sample_rows": actual_sample_size,
                               "sample_counts": sample, "monthly_matches": True,
                               "sex_matches": True, "sample_matches": True}}


def export_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Cannot export empty indicator table")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    try:
        with temp.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: value.isoformat() if isinstance(value, date) else value
                                 for key, value in row.items()})
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
