# Checkpoint - Fase 6 CNES

FASE: 6 - CNES.

Objetivo: ingerir, converter, validar e processar dados reais de hospitais e
leitos, construir a dimensao de estabelecimento, preservar a temporalidade e
integrar territorialmente com IBGE e temporalmente com SINASC.

O que foi implementado: ingestao idempotente com validacao de conteudo,
manifesto e checksums; conversao Latin-1 para UTF-8; Silver CSV/Parquet;
dimensao de estabelecimento; fato mensal de capacidade; aliases territoriais
auditaveis; SQL de join SINASC/CNES por competencia; qualidade e validacao
integral reproduzivel.

Arquivos principais: `src/nascente_brasil/ingestion/cnes.py`,
`src/nascente_brasil/transformation/cnes_pipeline.py`,
`sql/duckdb/sinasc_2024_cnes_temporal_join.sql`, `scripts/run_phase_6.py`,
`scripts/validate_phase_6.py` e `tests/test_cnes_phase6.py`.

Dados processados: 85.225 snapshots mensais, 7.284 codigos CNES, 12
competencias e 2.389.325 registros SINASC auditados.

Quantidade de registros: entrada = Silver = fato = 85.225; removidos = 0;
duplicados = 0; quarentena = 0. Dimensao = 7.284. Join territorial CNES:
85.225 relacionados, zero nao relacionados. Join temporal SINASC:
2.327.259 no mesmo mes e 62.066 em status explicitamente classificados.

Testes executados/aprovados: 27 testes Pytest; validador completo da Fase 6;
`pip check`; segunda execucao idempotente.

Problemas encontrados: 17 nomes municipais divergentes; discrepancia do tipo
documentado de `COMP`; registros SINASC sem codigo ou sem presenca no recurso
de hospitais/leitos. Problemas corrigidos: aliases explicitos, competencia de
seis digitos preservada e cobertura do join classificada. Problemas ainda
existentes: o recurso nao contem classificacao de leitos obstetricos; esse
indicador nao foi fabricado. A ausencia de um CNES neste recurso nao equivale
a ausencia no cadastro completo.

Validacoes realizadas: schema, encoding, competencias, chave mensal, tipos,
ranges, somas de UTI, relacao SUS/existente, geografia, temporalidade,
reconciliacao SINASC, checksums e comparacao integral dos Parquets recomputados.

Status: CONCLUIDA.
