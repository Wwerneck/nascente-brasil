# Execucao por Fases

O projeto deve avancar sequencialmente.

## Fase 1 - Fundacao

Objetivo: criar uma base local importavel, configuravel, testavel e documentada.

Definition of Done:

- codigo implementado;
- configuracao funcional;
- logs gravados;
- manifesto inicial existente;
- testes automatizados aprovados;
- documentacao atualizada;
- checkpoint produzido.

## Fase 2 - SINASC RAW

Concluida com o arquivo nacional SINASC 2024 do Ministerio da Saude. O ZIP
original foi preservado, lido ate o fim, validado como CSV e registrado no
manifesto com checksum SHA-256, ETag, periodo e contagem de registros.

Definition of Done:

- fonte oficial e URL de download documentadas;
- arquivo nacional real baixado e mantido sem alteracoes;
- tamanho, assinatura ZIP, integridade CRC, header e registros validados;
- manifesto e log preenchidos;
- segunda execucao idempotente;
- testes e checkpoint aprovados.

## Fase 3 - SINASC CSV e Silver

Concluida com o arquivo nacional 2024. A conversao produz CSV UTF-8 de
valores preservados; a transformacao em lotes produz CSV Silver e Parquet
com tipos definidos. O dicionario cobre as 62 colunas, e as metricas de
qualidade registram nulos, sentinelas e valores fora de faixa.

Definition of Done:

- schema real inspecionado e contrato ordenado validado;
- CSV RAW e Silver reproduziveis sem modificar o ZIP;
- tipos e codigos documentados no dicionario;
- todos os registros reconciliados;
- checksums e Parquet validados independentemente;
- testes, relatorio de qualidade e checkpoint aprovados.

## Fase 4 - DuckDB e primeiros indicadores

Concluida com consultas SQL locais ao Parquet Silver do SINASC 2024. Foram
publicados indicadores nacionais e contagens por mes e sexo, com formulas,
denominadores e exclusoes documentados.

Definition of Done:

- SQL executado no conjunto nacional;
- contagem independente do CSV e total Parquet reconciliados;
- agregacoes mensais e por sexo reconciliadas;
- amostra manual em Python comparada com DuckDB;
- testes, metadados, validacao reproduzivel e checkpoint aprovados.

## Fase 5 - IBGE

Concluida com a DTB 2024 oficial e um snapshot da API de UFs do IBGE.
Foram criadas dimensoes de regiao, estado e municipio e auditados os joins
por municipio de residencia e de ocorrencia do SINASC 2024.

Definition of Done:

- fontes oficiais preservadas com checksum no manifesto;
- dimensoes geradas e chaves territoriais unicas validadas;
- contagens do join reconciliadas sem descarte de linhas;
- nao relacionados classificados e investigados;
- testes, validacao, documentacao e checkpoint aprovados.

## Fase 6 - CNES

Concluida com o recurso oficial Hospitais e Leitos 2024. As 12 competencias
foram preservadas em Silver e em um fato mensal de capacidade; a dimensao de
estabelecimento explicita inicio, fim, cobertura e mudancas de atributos.

Definition of Done:

- CSV e dicionario oficiais preservados e manifestados;
- 85.225 snapshots convertidos e tipados sem perda de linha;
- chave `competencia + codigo_cnes` unica e medidas reconciliadas;
- dimensao de 7.284 estabelecimentos e fato mensal publicados;
- geografia IBGE e join temporal SINASC auditados;
- testes, validacao, qualidade, lineage e checkpoint aprovados.

## Fase 7 - SIH/SUS

Concluida com as 324 particoes estaduais mensais da AIH Reduzida 2024. Os DBC
originais e o layout oficial sao preservados; a conversao produz CSV.GZ
integral e Parquet Silver tipado por UF e competencia. Granularidade, tipos de
AIH, diagnosticos, geografia e relacionamento temporal com CNES sao auditados.

Definition of Done:

- inventario nacional oficial preservado e manifestado;
- 113 campos de origem e quantidade de registros reconciliados por particao;
- granularidade e diferenca entre AIH e pessoa documentadas;
- AIH inicial e continuidade, diagnosticos e datas tipados sem inferencia;
- geografia IBGE e join temporal CNES auditados sem descarte;
- testes, validacao integral, idempotencia, qualidade e checkpoint aprovados;
- analise obstetrica explicitamente mantida fora do escopo desta fase.

## Fase 8 - Morbidades maternas

Concluida com catalogo CID-10 oficial, classificacao de 502 codigos O,
fato agregado de AIHs obstetricas 2024 e quatro CSVs Gold por territorio.
O denominador e AIH obstetrica tipo 1 no mesmo mes e geografia; nao representa
mulheres unicas nem nascidos vivos.

Definition of Done:

- CID oficial preservado, manifestado e validado;
- grupos e exclusoes documentados com testes especificos;
- fato com numeradores reconciliados ao SIH;
- Brasil, regiao, UF e municipio reconciliados ao fato;
- cobertura do denominador municipal explicitamente auditada;
- testes, validacao, idempotencia, qualidade, lineage e checkpoint aprovados.

## Fase 9 - SIM e mortalidade

Concluida com `DOBR2024.dbc` oficial, CSV RAW completo, Parquet Silver
tipado e quatro Gold territoriais. Razoes/taxas observadas usam nascidos vivos
SINASC por residencia e nao sao indicadores oficiais corrigidos. A fonte
nacional usada so contem obitos nao fetais; nenhum indicador fetal foi criado.

Definition of Done:

- fonte, inventario, schema, checksum e registros reconciliados;
- idade, causa basica, denominador e diferencas territoriais auditados;
- medidas e limites epidemiologicos documentados;
- testes, validador, idempotencia, qualidade e checkpoint aprovados.

## Fase 10 - SINAN

Concluida como avaliacao de fonte. O DBC preliminar de sifilis em gestantes
2024 foi baixado, validado e manifestado. A classificacao final esta vazia em
todas as notificacoes; por isso nao foram criados indicadores Gold nem
vinculos individuais com outras fontes. Detalhes e limites em
`docs/sources/sinan_2024_assessment.md`.

## Fase 11 - PostgreSQL

Concluida com cinco schemas, dimensoes territoriais e tabelas analiticas de
morbidades/mortalidade. As cargas sao transacionais, auditadas por arquivo e
idempotentes; contagens arquivo/banco sao validadas apos cada execucao.

## Fase 12 - dbt

Concluida com staging, intermediate e marts no PostgreSQL. O build executa
testes de schema e de dados para grao, dominio, relacionamento e reconciliacao
com as tabelas de origem. A documentacao dbt e gerada localmente.

## Fase 13 - Airflow

Concluida em Docker Linux com LocalExecutor. A DAG valida fases 9/10, publica
PostgreSQL e executa dbt; retries e falha controlada foram comprovados. dbt
fica em ambiente Python isolado para preservar as dependencias do Airflow.

## Fase 14 - FastAPI

Concluida com endpoints paginados sobre marts dbt, consultas parametrizadas,
OpenAPI e testes de integracao. Indicadores municipais nao sao expostos ate
ser aprovada uma politica de supressao de celulas pequenas.

## Fase 15 - Streamlit

Concluída com oito áreas analíticas que consomem exclusivamente a API.
Visualização responsiva validada em desktop e mobile, com indicadores de
nascimento, morbidade, mortalidade, comparação estadual e qualidade.

## Fase 16 - Docker

Concluída com PostgreSQL, inicialização do pipeline, API, dashboard e Airflow
em uma composição única. Dependências, healthchecks e ordem de inicialização
impedem a publicação da interface antes da reconciliação e do build dbt.

## Fase 17 - Encerramento

Concluída com testes integrais, revisão de documentação, validação das fases,
healthchecks, inspeção visual e checkpoints de entrega.
