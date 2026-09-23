# Checkpoint - Fase 3 SINASC CSV e Silver

Status: CONCLUIDA

Objetivo: converter o SINASC nacional 2024 sem alterar o ZIP RAW, criar CSV
local padronizado, tipar a Silver, testar e relatar qualidade.

Implementado:

- contrato de 62 colunas observado no CSV nacional;
- conversao em fluxo para CSV UTF-8, preservando valores e zeros a esquerda;
- deteccao de schema drift com interrupcao e diagnostico em metadados;
- transformacao em lotes de 50.000 linhas com tipos explicitos;
- Silver CSV e Parquet com schema Arrow estavel;
- metadados com caminhos relativos, SHA-256 de cada produto e metricas;
- dicionario completo e relatorio de qualidade;
- validacao independente e reconstruibilidade testada.

Arquivo fonte: `data/raw/sinasc/original/SINASC_2024_csv_27e55de6359e.zip`.
CSV RAW: `data/raw/sinasc/csv/sinasc_2024_27e55de6359e.csv`
(559.423.769 bytes, SHA-256 `f03bdf49605e4388233b32528365e2d2ad6175ef34f98f3c1a50a4fb597ccd9b`).
Silver CSV: `data/processed/sinasc/sinasc_2024_27e55de6359e_silver.csv`
(559.174.644 bytes, SHA-256 `eb106e1b0f3e6a0a4414d75631263bfe7168e0b9154a38f50634352471ffd7c5`).
Silver Parquet: `data/processed/sinasc/sinasc_2024_27e55de6359e_silver.parquet`
(58.921.500 bytes, SHA-256 `4222c57d4d69422faa7e838bc0031f90422731ff1cee336dfc72abd5b603c8f4`).

Registros: 2.389.325 na origem, RAW CSV, Silver CSV e Parquet; nenhum descarte.
Inconsistencias: nulos, sentinelas, codigos ignorados e valores fora de faixa
documentados em `docs/data_quality/sinasc_2024.md`. Os extremos plausiveis
para revisao foram preservados.

Validacoes:

- `.\.venv\Scripts\python.exe -m pytest`: 15 testes aprovados;
- testes unitarios para zeros a esquerda, tipos, sentinelas, datas, drift,
  idempotencia e reconstruibilidade;
- processamento nacional completo sem erro;
- `scripts/validate_phase_3.py` aprovou linhas, checksums e schema;
- segunda execucao retornou `already current`;
- `pip check` sem conflitos.

Problema corrigido: PyArrow inferia precisao de timestamp diferente entre
lotes com datas validas e nulas. Um schema Arrow explicito estabilizou a
escrita Parquet. Os caminhos dos metadados foram tornados relativos ao projeto.

Pendencias da Fase 3: nenhuma. Indicadores e DuckDB pertencem a Fase 4.
