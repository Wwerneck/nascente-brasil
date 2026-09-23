"""Chunked SINASC Silver transformation with explicit quality accounting."""

from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nascente_brasil.conversion.sinasc import OUTPUT_COLUMNS
from nascente_brasil.ingestion.sinasc import sha256_file


CHUNK_ROWS = 50_000
NUMERIC_FIELDS = {
    "idade_mae": (99, 10, 65),
    "semanas_gestacao": (99, 20, 45),
    "consultas_prenatal_numero": (99, 0, 50),
    "peso_nascimento_g": (9999, 200, 7000),
    "apgar_1min": (99, 0, 10),
    "apgar_5min": (99, 0, 10),
}
CATEGORY_VALUES = {
    "tipo_parto": {"1", "2", "9"},
    "sexo": {"0", "1", "2", "9"},
    "tipo_gravidez": {"1", "2", "3", "9"},
}
ARROW_SCHEMA = pa.schema([
    pa.field(
        column,
        pa.timestamp("us") if column == "data_nascimento"
        else pa.int64() if column in NUMERIC_FIELDS else pa.string(),
    )
    for column in OUTPUT_COLUMNS
])


def transform_silver(
    input_csv: Path,
    output_csv: Path,
    output_parquet: Path,
    expected_rows: int,
    *,
    chunk_rows: int = CHUNK_ROWS,
) -> dict:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    csv_temp: Path | None = None
    parquet_temp: Path | None = None
    writer: pq.ParquetWriter | None = None
    metrics: dict[str, Counter] = {
        "missing": Counter(),
        "invalid_numeric": Counter(),
        "invalid_date": Counter(),
        "sentinel_to_null": Counter(),
        "out_of_range_retained": Counter(),
        "unexpected_category_retained": Counter(),
        "unknown_category_retained": Counter(),
        "invalid_municipality_code_retained": Counter(),
    }
    rows = 0
    try:
        csv_fd, csv_name = tempfile.mkstemp(dir=output_csv.parent, suffix=".part")
        parquet_fd, parquet_name = tempfile.mkstemp(dir=output_parquet.parent, suffix=".part")
        os.close(csv_fd)
        os.close(parquet_fd)
        csv_temp = Path(csv_name)
        parquet_temp = Path(parquet_name)
        with csv_temp.open("w", encoding="utf-8", newline="") as csv_file:
            for chunk in pd.read_csv(
                input_csv, dtype="string", keep_default_na=False, na_filter=False,
                chunksize=chunk_rows, encoding="utf-8",
            ):
                if tuple(chunk.columns) != OUTPUT_COLUMNS:
                    raise ValueError("Converted SINASC CSV schema differs from contract")
                rows += len(chunk)
                for field, (sentinel, low, high) in NUMERIC_FIELDS.items():
                    raw = chunk[field].str.strip()
                    valid_digits = raw.str.fullmatch(r"\d+")
                    parsed = pd.to_numeric(raw.where(valid_digits), errors="coerce").astype("Int64")
                    bad = raw.ne("") & parsed.isna()
                    sent = parsed.eq(sentinel).fillna(False)
                    metrics["invalid_numeric"][field] += int(bad.sum())
                    metrics["sentinel_to_null"][field] += int(sent.sum())
                    parsed = parsed.mask(sent)
                    outlier = (parsed.lt(low) | parsed.gt(high)).fillna(False)
                    metrics["out_of_range_retained"][field] += int(outlier.sum())
                    metrics["missing"][field] += int(parsed.isna().sum())
                    chunk[field] = parsed

                raw_date = chunk["data_nascimento"].str.strip()
                parsed_date = pd.to_datetime(
                    raw_date.mask(raw_date.eq("")), format="%d%m%Y", errors="coerce"
                )
                metrics["invalid_date"]["data_nascimento"] += int(
                    (raw_date.ne("") & parsed_date.isna()).sum()
                )
                metrics["missing"]["data_nascimento"] += int(parsed_date.isna().sum())
                metrics["out_of_range_retained"]["data_nascimento_year"] += int(
                    (parsed_date.notna() & parsed_date.dt.year.ne(2024)).sum()
                )
                chunk["data_nascimento"] = parsed_date

                for field, allowed in CATEGORY_VALUES.items():
                    values = chunk[field].str.strip()
                    metrics["unexpected_category_retained"][field] += int(
                        (values.ne("") & ~values.isin(allowed)).sum()
                    )
                    metrics["missing"][field] += int(values.eq("").sum())
                    unknown_code = "0" if field == "sexo" else "9"
                    metrics["unknown_category_retained"][field] += int(values.eq(unknown_code).sum())
                    chunk[field] = values

                for field in ("codigo_municipio_nascimento", "codigo_municipio_residencia"):
                    values = chunk[field].str.strip()
                    metrics["invalid_municipality_code_retained"][field] += int(
                        (values.ne("") & ~values.str.fullmatch(r"\d{6,7}")).sum()
                    )
                    metrics["missing"][field] += int(values.eq("").sum())
                    chunk[field] = values

                table = pa.Table.from_pandas(
                    chunk, schema=ARROW_SCHEMA, preserve_index=False, safe=True
                )
                if writer is None:
                    writer = pq.ParquetWriter(parquet_temp, table.schema, compression="zstd")
                writer.write_table(table)

                csv_chunk = chunk.assign(
                    data_nascimento=chunk["data_nascimento"].dt.strftime("%Y-%m-%d")
                )
                csv_chunk.to_csv(
                    csv_file, index=False, header=rows == len(chunk), na_rep="",
                    lineterminator="\n",
                )
        if writer is None:
            raise ValueError("Converted SINASC CSV has no rows")
        writer.close()
        writer = None
        if rows != expected_rows:
            raise ValueError(f"Silver row count differs: expected {expected_rows}, found {rows}")
        if pq.ParquetFile(parquet_temp).metadata.num_rows != rows:
            raise ValueError("Silver Parquet row count differs from CSV")
        os.replace(csv_temp, output_csv)
        csv_temp = None
        os.replace(parquet_temp, output_parquet)
        parquet_temp = None
        return {
            "rows": rows,
            "csv": {"path": str(output_csv), "bytes": output_csv.stat().st_size, "sha256": sha256_file(output_csv)},
            "parquet": {"path": str(output_parquet), "bytes": output_parquet.stat().st_size, "sha256": sha256_file(output_parquet)},
            "quality": {key: dict(value) for key, value in metrics.items()},
        }
    finally:
        if writer is not None:
            writer.close()
        for path in (csv_temp, parquet_temp):
            if path is not None and path.exists():
                path.unlink()
