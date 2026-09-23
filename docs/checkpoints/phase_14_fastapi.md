# Checkpoint - Fase 14 FastAPI

FASE: 14 - FastAPI.

Objetivo: expor somente marts aprovados, com filtros, paginacao, validacao e
respostas verificadas contra o PostgreSQL.

Implementado: `/health`, `/api/v1/nascimentos`, `/api/v1/mortalidade`, `/api/v1/morbidades`,
`/api/v1/indicadores/brasil` e `/api/v1/territorios/municipios`; OpenAPI
automatico; consultas parametrizadas; limite de 500 linhas e offsets nao
negativos; filtros de nivel, territorio, competencia, grupo e UF.

Privacidade: endpoints analiticos aceitam somente Brasil, regiao e estado.
Gold municipal permanece interno ate existir politica formal de supressao de
celulas pequenas. A lista municipal contem apenas dimensao territorial.

Validacoes executadas: banco indisponivel retorna 503 sem revelar detalhes;
parametros invalidos retornam 422; Brasil reconcilia 30.020 obitos infantis e
2.389.325 nascidos vivos; morbidades Brasil tem 240 linhas; mortalidade UF
tem 27; filtro municipal por UF e fronteira de privacidade aprovados.

Status: CONCLUIDA.
