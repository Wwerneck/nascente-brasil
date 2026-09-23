# Checkpoint - Fase 12 dbt

FASE: 12 - dbt.

Objetivo: construir staging, intermediate e marts sobre as tabelas PostgreSQL
validadas, com contratos e testes executaveis.

Implementado: 4 modelos staging, 3 intermediários e 3 marts; 4 sources;
schemas de saida separados; documentacao de modelos; teste de unicidade de
grao, valores aceitos, not null, relacionamento municipal e reconciliacao dos
marts com as fontes.

Execução: `dbt debug` aprovado; `dbt build` concluiu 39 de 39 ações, sendo 10
modelos e 29 testes, sem warning, erro ou skip. Marts: 5.603 linhas de
nascimentos, 225.791 de morbidades e 5.603 de mortalidade. `dbt docs generate` produziu manifesto e
catalogo em `dbt/target/`.

Problemas encontrados/corrigidos: nenhum desvio de grao, geografia ou
contagem. As descricoes deixam explicito que AIH nao e pessoa e que medidas
de mortalidade observada nao sao estimativas oficiais corrigidas.

Status: CONCLUIDA.
