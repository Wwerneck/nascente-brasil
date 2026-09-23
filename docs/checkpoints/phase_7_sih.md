# Checkpoint - Fase 7 SIH/SUS

FASE: 7 - SIH/SUS.

Objetivo: baixar dados oficiais, compreender granularidade de AIH e
diagnosticos, processar as particoes nacionais de 2024 e validar integralmente
antes de iniciar qualquer analise obstetrica.

O que foi implementado: ingestao resumivel de DBCs com inventario remoto,
manifesto e checksums; preservacao do informe tecnico oficial; conversao
integral para CSV.GZ UTF-8; Silver Parquet tipada e particionada; enriquecimento
IBGE; classificacao temporal CNES; metricas de qualidade; relatorios nacionais;
validador local integral e execucao idempotente.

Arquivos principais: `src/nascente_brasil/ingestion/sih.py`,
`src/nascente_brasil/conversion/sih.py`,
`src/nascente_brasil/transformation/sih_pipeline.py`,
`sql/duckdb/sih_2024_cnes_temporal_join.sql`, `scripts/ingest_sih_2024.py`,
`scripts/run_phase_7.py`, `scripts/validate_phase_7.py` e
`tests/test_sih_phase7.py`.

Dados processados: 324 arquivos RD de 27 UFs e 12 competencias; 113 campos
originais por particao; 14.171.364 registros.

Quantidade de registros: entrada = CSV.GZ = Silver = 14.171.364; removidos =
0; quarentena = 0. Numeros de AIH distintos = 14.048.357; AIH tipo 5 = 133.536.
Join temporal CNES: 14.020.838 no mesmo mes, 146.966 ausentes do recurso de
hospitais/leitos e 3.560 vistos somente em outra competencia.

Testes executados/aprovados: 30 testes Pytest; `pip check`; validador integral
da Fase 7; segunda execucao idempotente.

Problemas encontrados: 764 ocorrencias de diagnostico secundario fora da
forma basica CID-10; 5.208 chaves de AIH duplicadas dentro da particao,
equivalentes a 6.585 repeticoes alem da primeira; 150.526 linhas sem match
CNES na mesma competencia. Problemas tratados: todas as linhas preservadas,
anomalias contabilizadas e classificadas, sem imputacao ou deduplicacao.
Limitacoes remanescentes: SIH e administrativo-financeiro e nao permite contar
pessoas unicas; ausencia no recurso CNES nao implica estabelecimento inexistente.

Validacoes realizadas: inventario, schema, cabecalho, checksum, tamanho e
contagem de cada DBC; manifesto e documento oficial; largura e contagem dos
CSVs; schema, checksum e linhas dos Parquets; reconciliacoes nacionais;
tipos AIH, CID, datas, geografia e join temporal CNES.

Status: CONCLUIDA. A analise obstetrica nao foi iniciada.
