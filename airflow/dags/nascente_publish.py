"""Orchestrate already validated Nascente Brasil publication steps."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


ENV = {
    "PYTHONPATH": "/opt/nascente/src",
    "NASCENTE_DATA_DIR": "/opt/nascente/data",
    "NASCENTE_METADATA_DIR": "/opt/nascente/data/metadata",
    "NASCENTE_LOG_DIR": "/opt/nascente/logs",
    "NASCENTE_MANIFEST_PATH": "/opt/nascente/data/metadata/ingestion_manifest.csv",
    "NASCENTE_POSTGRES_DSN": "postgresql://nascente:nascente@postgres:5432/nascente_brasil",
    "NASCENTE_POSTGRES_HOST": "postgres",
    "NASCENTE_POSTGRES_PORT": "5432",
    "NASCENTE_POSTGRES_USER": "nascente",
    "NASCENTE_POSTGRES_PASSWORD": "nascente",
    "NASCENTE_POSTGRES_DATABASE": "nascente_brasil",
}


with DAG(
    dag_id="nascente_brasil_publish",
    description="Validate approved files, publish PostgreSQL, and build dbt marts.",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    default_args={"owner": "nascente-brasil", "retries": 2,
                  "retry_delay": timedelta(minutes=1)},
    tags=["materno-infantil", "data-quality"],
) as dag:
    validate_sim = BashOperator(
        task_id="validate_sim_phase9",
        bash_command="python scripts/validate_phase_9.py",
        cwd="/opt/nascente",
        env=ENV,
    )
    validate_sinan = BashOperator(
        task_id="validate_sinan_phase10",
        bash_command="python scripts/validate_phase_10.py",
        cwd="/opt/nascente",
        env=ENV,
    )
    build_births = BashOperator(
        task_id="build_birth_indicators",
        bash_command="python scripts/build_birth_indicators.py",
        cwd="/opt/nascente",
        env=ENV,
    )
    load_postgres = BashOperator(
        task_id="load_postgres_phase11",
        bash_command="python scripts/run_phase_11.py && python scripts/validate_phase_11.py",
        cwd="/opt/nascente",
        env=ENV,
    )
    build_dbt = BashOperator(
        task_id="build_dbt_phase12",
        bash_command="/home/airflow/dbt-venv/bin/dbt build --project-dir dbt --profiles-dir dbt",
        cwd="/opt/nascente",
        env=ENV,
    )
    validate_sim >> validate_sinan >> build_births >> load_postgres >> build_dbt
