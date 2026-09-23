# Checkpoint - Fase 13 Airflow

FASE: 13 - Airflow.

Objetivo: transformar scripts aprovados em DAGs e validar pipeline, retries,
dependencias e falhas.

Implementado: Docker Desktop com Engine Linux; Airflow 2.10.5 em imagem
oficial, LocalExecutor, PostgreSQL, scheduler e webserver; dbt isolado em
virtualenv para evitar conflito de SQLAlchemy/protobuf; DAG manual de
publicação com cinco tarefas e dois retries por tarefa.

Execução principal: `validate_sim_phase9`, `validate_sinan_phase10`,
`build_birth_indicators`, `load_postgres_phase11` e `build_dbt_phase12`
concluíram em sucesso. Scheduler,
webserver e PostgreSQL ficaram saudaveis. `pip check` passou nos ambientes
Airflow e dbt.

Falhas/retries: `nascente_failure_probe` executou `exit 42`, fez duas
tentativas (`try_number=2`, `max_tries=1`) e encerrou a DAG em `failed`, como
esperado. O primeiro build revelou conflito de dependencias; corrigido com
isolamento de dbt e imagem reconstruida.

Interface local: `http://localhost:8080`, usuario/senha de desenvolvimento
`admin`/`admin`; nao utilizar essas credenciais fora do ambiente local.

Status: CONCLUIDA.
