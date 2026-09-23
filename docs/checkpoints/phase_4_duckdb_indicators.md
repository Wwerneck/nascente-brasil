# Checkpoint - Fase 4

Status: concluida e validada no arquivo nacional SINASC 2024.

## Artefatos

- Consultas: `sql/duckdb/sinasc_2024_national.sql`, `sinasc_2024_monthly.sql` e `sinasc_2024_sex.sql`.
- Execucao: `scripts/run_phase_4.py`.
- Validacao independente e reproducao: `scripts/validate_phase_4.py`.
- Tabelas CSV pequenas: `data/processed/sinasc/analytics/`.
- Metadados, checksums e reconciliacoes: `data/metadata/sinasc_2024_27e55de6359e_indicators.json`.
- Formulas e limites: `docs/methodology/indicators_sinasc_2024.md`.

## Evidencia

- 2.389.325 registros no CSV Silver e no Parquet.
- 12 grupos mensais e 3 grupos de sexo; somas reconciliadas com o total nacional.
- Os nove componentes de contagem da amostra de 1.000 registros conferem entre Python e DuckDB.
- 20 testes automatizados passaram, incluindo exclusoes, falhas de reconciliacao, idempotencia e adulteracao de artefato.
- Segunda execucao de publicacao foi idempotente.

Sem dados territoriais adicionais ou infraestrutura da Fase 5 nesta entrega.
