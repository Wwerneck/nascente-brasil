# Checkpoint - Fase 11 PostgreSQL

FASE: 11 - PostgreSQL.

Objetivo: publicar dimensoes e Gold aprovados em banco relacional com cargas
transacionais, reconciliacao e idempotencia.

Implementado: instância Docker de desenvolvimento em `127.0.0.1:55433`,
banco `nascente_brasil`, schemas `raw`, `staging`, `intermediate`, `analytics`
e `metadata`; dimensao municipal, visoes de UF/regiao, fatos analiticos de
morbidades, mortalidade e nascimentos e auditoria `metadata.load_runs`.

Carregado: 5.571 municípios, 5.603 linhas Gold de nascimentos, 225.791 linhas
Gold de morbidades e 5.603 linhas Gold de mortalidade. Cada um dos 13 arquivos tem contagem e SHA-256
registrados. A transacao inteira falha se qualquer contagem divergir.

Validacoes: segunda carga sem duplicacao; PKs e chaves territoriais;
contagens arquivo/banco; 13 registros de auditoria únicos; 5 regiões; Brasil
reconciliado em 30.020 obitos infantis e 2.389.325 nascidos vivos.

Configuracao: `NASCENTE_POSTGRES_DSN`; valor local de desenvolvimento
`postgresql://nascente:nascente@127.0.0.1:55433/nascente_brasil`.

Status: CONCLUIDA.
