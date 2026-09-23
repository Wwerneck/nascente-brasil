"""FastAPI application exposing only approved, non-municipal analytical marts."""

from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
import psycopg
from psycopg.rows import dict_row

PublicLevel = Literal["brasil", "regiao", "estado"]
Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]

app = FastAPI(
    title="Nascente Brasil API",
    version="1.0.0",
    description="Consulta aos marts validados de saude materno-infantil. Medidas observadas nao substituem estatisticas oficiais corrigidas.",
)


def _dsn() -> str:
    return os.environ.get(
        "NASCENTE_POSTGRES_DSN",
        "postgresql://nascente@127.0.0.1:55432/nascente_brasil",
    )


@contextmanager
def _connection():
    try:
        with psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=5) as connection:
            yield connection
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="Analytical database unavailable") from exc


def _page(query: str, count_query: str, params: dict, limit: int, offset: int) -> dict:
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]
        cursor.execute(query, params | {"limit": limit, "offset": offset})
        items = cursor.fetchall()
    return {"items": items, "pagination": {"total": total, "limit": limit, "offset": offset}}


@app.get("/health")
def health() -> dict:
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1 AS ok")
        cursor.fetchone()
    return {"status": "ok", "database": "ok"}


@app.get("/api/v1/mortalidade")
def mortality(
    nivel: PublicLevel = "brasil",
    codigo_territorio: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
) -> dict:
    filters = ["nivel_territorial = %(nivel)s"]
    params: dict = {"nivel": nivel}
    if codigo_territorio:
        filters.append("codigo_territorio = %(codigo)s")
        params["codigo"] = codigo_territorio
    where = " AND ".join(filters)
    return _page(
        f"SELECT * FROM dbt_marts.mart_mortalidade_territorial WHERE {where} ORDER BY codigo_territorio LIMIT %(limit)s OFFSET %(offset)s",
        f"SELECT COUNT(*) AS total FROM dbt_marts.mart_mortalidade_territorial WHERE {where}",
        params, limit, offset,
    )


@app.get("/api/v1/nascimentos")
def births(
    nivel: PublicLevel = "brasil",
    codigo_territorio: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
) -> dict:
    filters = ["nivel_territorial = %(nivel)s"]
    params: dict = {"nivel": nivel}
    if codigo_territorio:
        filters.append("codigo_territorio = %(codigo)s")
        params["codigo"] = codigo_territorio
    where = " AND ".join(filters)
    return _page(
        f"SELECT * FROM dbt_marts.mart_nascimentos_territoriais WHERE {where} ORDER BY codigo_territorio LIMIT %(limit)s OFFSET %(offset)s",
        f"SELECT COUNT(*) AS total FROM dbt_marts.mart_nascimentos_territoriais WHERE {where}",
        params, limit, offset,
    )


@app.get("/api/v1/morbidades")
def morbidities(
    nivel: PublicLevel = "brasil",
    codigo_territorio: str | None = None,
    grupo: str | None = None,
    competencia: int | None = Query(default=None, ge=202401, le=202412),
    limit: Limit = 100,
    offset: Offset = 0,
) -> dict:
    filters = ["nivel_territorial = %(nivel)s"]
    params: dict = {"nivel": nivel}
    for value, clause, key in ((codigo_territorio, "codigo_territorio = %(codigo)s", "codigo"),
                               (grupo, "grupo_morbidade = %(grupo)s", "grupo"),
                               (competencia, "competencia = %(competencia)s", "competencia")):
        if value is not None:
            filters.append(clause)
            params[key] = value
    where = " AND ".join(filters)
    return _page(
        f"SELECT * FROM dbt_marts.mart_morbidades_territoriais WHERE {where} ORDER BY competencia, codigo_territorio, grupo_morbidade, subgrupo LIMIT %(limit)s OFFSET %(offset)s",
        f"SELECT COUNT(*) AS total FROM dbt_marts.mart_morbidades_territoriais WHERE {where}",
        params, limit, offset,
    )


@app.get("/api/v1/indicadores/brasil")
def national_indicators() -> dict:
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT * FROM dbt_marts.mart_mortalidade_territorial
                          WHERE nivel_territorial='brasil' AND codigo_territorio='BR'""")
        mortality_row = cursor.fetchone()
        cursor.execute("""SELECT * FROM dbt_marts.mart_nascimentos_territoriais
                          WHERE nivel_territorial='brasil' AND codigo_territorio='BR'""")
        birth_row = cursor.fetchone()
        cursor.execute("""SELECT competencia, grupo_morbidade, subgrupo, registros_aih,
                                 denominador_aih_obstetricas, proporcao_aih_obstetricas_pct
                          FROM dbt_marts.mart_morbidades_territoriais
                          WHERE nivel_territorial='brasil'
                          ORDER BY competencia, grupo_morbidade, subgrupo""")
        morbidity_rows = cursor.fetchall()
    if mortality_row is None:
        raise HTTPException(status_code=404, detail="National indicators unavailable")
    return {"nascimentos": birth_row, "mortalidade": mortality_row, "morbidades": morbidity_rows,
            "methodology_notice": "Observed administrative-data measures; consult project methodology."}


@app.get("/api/v1/territorios/municipios")
def municipalities(uf: str | None = Query(default=None, min_length=2, max_length=2),
                   limit: Limit = 100, offset: Offset = 0) -> dict:
    params: dict = {}
    where = "TRUE"
    if uf:
        where = "uf = %(uf)s"
        params["uf"] = uf.upper()
    return _page(
        f"SELECT * FROM analytics.dim_municipio WHERE {where} ORDER BY codigo_ibge LIMIT %(limit)s OFFSET %(offset)s",
        f"SELECT COUNT(*) AS total FROM analytics.dim_municipio WHERE {where}",
        params, limit, offset,
    )
