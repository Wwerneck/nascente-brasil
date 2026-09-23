# Checkpoint - Fase 8 Morbidades Maternas

FASE: 8 - Morbidades maternas.

Objetivo: criar classificacao CID auditavel, fato de morbidades, indicadores e
quatro CSVs Gold territoriais com numeradores, denominadores e duplicidades
validados.

O que foi implementado: ingestao de CID-10 oficial DATASUS; referencia de 502
codigos obstetricos; classificacao analitica de 14 grupos, incluindo 11 grupos
marcados como morbidade; fato por competencia, municipio de residencia e CID
principal; Gold nacional, regional, estadual e municipal; reconciliacao
territorial, checksums, validacao local, testes e idempotencia.

Arquivos criados: `src/nascente_brasil/ingestion/cid.py`,
`src/nascente_brasil/transformation/maternal_cid.py`,
`src/nascente_brasil/transformation/maternal_pipeline.py`, scripts da Fase 8,
`tests/test_maternal_phase8.py`, referencia em `data/reference/cid/`, fato em
`data/processed/morbidades_maternas/` e quatro CSVs em `data/gold/morbidades/`.

Dados processados: SIH/SUS 2024 Silver, 14.171.364 linhas; CID10.DBF com
14.257 codigos; CIDCAP10.DBF com 22 capitulos.

Quantidade de registros: 2.115.667 AIHs tipo 1 com CID O; 1.740 excluidas
por sexo informado diferente de `3`; 2.113.927 elegiveis = 873.345
classificados como morbidade + 1.240.582 outros registros obstetricos.
Fato com 573.131 linhas agregadas; 0 linhas perdidas nos joins CID/IBGE.
Gold com 240, 1.177, 5.895 e 218.479 linhas, respectivamente.

Testes executados/aprovados: testes Pytest da classificacao e denominador,
suitem completa, validador integral da fase, `pip check` e segunda execucao
idempotente.

Problemas encontrados: ZIP CID historico inacessivel; substituido por DBFs
oficiais no FTP DATASUS. O40-O43 e O12 exigiram revisao taxonomica antes da
publicacao. Gold municipal nao possui linha para municipio/mes sem morbidade:
23.835 registros elegiveis ficam apenas no fato e na cobertura do denominador.

Problemas corrigidos: fonte oficial alternativa validada, grupos ajustados,
numeradores e denominadores reconciliados em quatro niveis. Problemas ainda
existentes: nenhuma taxa populacional ou por nascidos vivos; celulas municipais
pequenas exigem politica de supressao antes de publicacao externa.

Validacoes realizadas: fonte, manifesto, schema CID, catalogo completo de
codigos O, AIH tipo 1, sexo, geografia, recorte de CID principal, exclusoes,
duplicidades, soma do fato, soma Gold, cobertura do denominador, checksums e
idempotencia.

Status: CONCLUIDA.
