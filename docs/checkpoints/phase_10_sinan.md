# Checkpoint - Fase 10 SINAN

FASE: 10 - avaliacao de fonte SINAN pertinente a saude materna.

Objetivo: decidir se ha fonte publica com cobertura e interpretacao
suficientes para incorporacao a plataforma.

Implementado e executado: consulta ao FTP oficial, download do DBC
preliminar de sifilis em gestantes 2024 e do pacote oficial de documentos;
validacao do DBC, ZIP, schema, checksum, agravo, ano, status e geografia;
manifesto e relatorio de avaliacao reproduzivel.

Dados processados: 89.934 notificacoes, 32 campos. `CLASSI_FIN` ausente em
89.934; 18.747 valores nao numericos em `DTTESTE1`; 5 residencias sem match.

Problemas encontrados: fonte disponivel apenas como preliminar no recorte
avaliado; classificacao final vazia. Decisao: nao publicar indicadores de
casos confirmados nem misturar essas notificacoes com eventos SIH/SINASC/SIM.
O arquivo original permanece preservado e rastreavel.

Testes: Pytest, validacao independente e reexecucao idempotente.

Status: CONCLUIDA COMO AVALIACAO, SEM INCORPORACAO ANALITICA.
