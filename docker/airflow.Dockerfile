FROM apache/airflow:2.10.5-python3.11

USER airflow
COPY --chown=airflow:0 pyproject.toml /opt/nascente/pyproject.toml
COPY --chown=airflow:0 src /opt/nascente/src
RUN pip install --no-cache-dir --no-deps /opt/nascente \
    && pip install --no-cache-dir "datasus-dbc>=0.1.3,<0.2" "dbfread>=2,<3" \
       "psycopg[binary]>=3.2,<4" "pypdf>=6,<7" "duckdb>=1,<2" "odfpy>=1.4,<2" \
    && python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install --no-cache-dir \
       "dbt-core>=1.11,<2" "dbt-postgres>=1.11,<2"

COPY --chown=airflow:0 scripts /opt/nascente/scripts
COPY --chown=airflow:0 dbt /opt/nascente/dbt
WORKDIR /opt/nascente
