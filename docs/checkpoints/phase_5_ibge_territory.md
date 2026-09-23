# Checkpoint - Fase 5 IBGE

FASE: 5 - IBGE.

Objetivo: construir referencia territorial oficial de 2024 e auditar o join
com SINASC 2024 sem descartar registros.

O que foi implementado: download/cache e validacao dos dois insumos IBGE,
conversao em CSV, dimensoes de regiao/UF/municipio, SQL de relacionamento,
metricas de cobertura e validacao reproduzivel.

Arquivos principais: `src/nascente_brasil/ingestion/ibge.py`,
`src/nascente_brasil/transformation/ibge_pipeline.py`,
`sql/duckdb/sinasc_2024_territory_join.sql`, `scripts/run_phase_5.py`,
`scripts/validate_phase_5.py`, `tests/test_ibge_phase5.py`.

Dados processados: DTB 2024 (5.571 geocodigos), API de UFs (27), SINASC Silver
2024 (2.389.325 registros), nas duas perspectivas territoriais.

Testes executados/aprovados: 23 testes Pytest; validacao completa da Fase 5;
`pip check`; segunda execucao idempotente.

Problemas encontrados: 54 codigos de residencia e 2 de ocorrencia nao possuem
municipio na DTB. Problemas corrigidos: nenhuma perda de registro; todos os
codigos sem match foram classificados, contados e expostos em CSV. Problemas
ainda existentes: o significado oficial especifico dos codigos terminados em
`0000` nao foi confirmado; nenhum municipio foi inferido.

Validacoes realizadas: ZIP/CRC e schema ODS, JSON da API, 27 UFs e 5 regioes,
unicidade das chaves de 7 e 6 digitos, nomes de UF, totais do join, checksums
dos insumos e produtos, recomputacao do SQL e comparacao integral com os CSVs.

Status: CONCLUIDA para o escopo da Fase 5, com registros nao relacionados
explicitamente preservados e documentados.
