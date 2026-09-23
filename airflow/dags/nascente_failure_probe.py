"""Manual-only failure probe used to validate Airflow retry behavior."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="nascente_failure_probe",
    description="Intentional failure; a successful run would indicate a broken probe.",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    default_args={"owner": "nascente-brasil", "retries": 1,
                  "retry_delay": timedelta(seconds=5)},
    tags=["validation", "manual-only"],
) as dag:
    BashOperator(task_id="intentional_failure", bash_command="exit 42")
