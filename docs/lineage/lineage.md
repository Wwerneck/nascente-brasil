# Data Lineage

Lineage planejado:

```text
fonte oficial
-> arquivo original em data/raw/{fonte}/original
-> CSV RAW em data/raw/{fonte}/csv
-> camada processed/silver
-> modelos analiticos/gold
-> consultas DuckDB, PostgreSQL e dbt
-> API e dashboard
```

Lineage realizado ate a Fase 3:

```text
recurso oficial SINASC 2024
-> ZIP imutavel em data/raw/sinasc/original/
-> manifesto de ingestao com SHA-256
-> CSV RAW padronizado em data/raw/sinasc/csv/
-> Silver CSV e Parquet em data/processed/sinasc/
-> metadados de processamento com checksums e metricas de qualidade
```

O mesmo checksum do ZIP aparece no nome dos produtos e no relatorio em
`data/metadata/`. Na Fase 4, o Parquet Silver alimenta as tres consultas
DuckDB em `sql/duckdb/`; os CSVs nacional, mensal e por sexo sao publicados em
`data/processed/sinasc/analytics/`. O relatorio de indicadores registra
checksums da Silver, do SQL e dos produtos, alem das reconciliacoes.

Na Fase 5, `DTB_2024.zip` e o snapshot JSON da API de UFs do IBGE entram em
`data/raw/ibge/original/` e no manifesto. A planilha ODS e a resposta JSON
geram CSV RAW em `data/raw/ibge/csv/` e tres dimensoes em
`data/reference/ibge/`. O Parquet Silver SINASC e cruzado com a dimensao
municipal pelo prefixo de seis digitos; o resultado, incluindo nao
relacionados, fica em `data/processed/sinasc/analytics/` e o relatorio com
checksums e metricas em `data/metadata/ibge_sinasc_2024_territory.json`.

Na Fase 6, o CSV Hospitais e Leitos 2024 e seu dicionario entram em
`data/raw/cnes/original/` e no manifesto. A copia UTF-8 segue para
`data/raw/cnes/csv/`; Silver CSV/Parquet e o fato mensal ficam em
`data/processed/cnes/`; a dimensao fica em `data/reference/cnes/`. A DTB 2024
fornece `codigo_ibge`, e o Parquet SINASC e auditado contra CNES por codigo do
estabelecimento e competencia do nascimento. Checksums, qualidade e metricas
dos joins estao em `data/metadata/cnes_leitos_2024_processing.json`.

Na Fase 7, as 324 particoes DBC de AIH reduzida e o informe tecnico do SIH
entram em `data/raw/sih/original/` e no manifesto. Cada DBC gera um CSV.GZ
UTF-8 completo em `data/raw/sih/csv/` e um Parquet Silver tipado e particionado
por UF/competencia em `data/processed/sih/silver/`. A dimensao municipal IBGE
enriquece residencia e estabelecimento; o fato mensal CNES classifica o join
temporal. Resumos, auditoria e checksums ficam em `data/processed/sih/analytics/`
e `data/metadata/sih_2024_processing.json`.

Na Fase 8, `CID10.DBF` e `CIDCAP10.DBF` oficiais entram em
`data/raw/cid/original/` e no manifesto. Os codigos O do catalogo geram a
referencia `data/reference/cid/cid_materno.csv`, enriquecida por regras
analiticas versionadas. O SIH Silver e filtrado por AIH tipo 1, sexo e CID
principal; o fato agregado fica em `data/processed/morbidades_maternas/`.
As quatro agregacoes territoriais ficam em `data/gold/morbidades/`, e os
checksums, exclusoes e reconciliacoes em
`data/metadata/maternal_morbidity_2024_processing.json`.

Na Fase 9, `DOBR2024.dbc` oficial entra em `data/raw/sim/original/` e no
manifesto. A conversao gera CSV.GZ integral em `data/raw/sim/csv/` e Parquet
Silver sem identificadores diretos em `data/processed/sim/`. SIM, SINASC e
dimensao IBGE alimentam os quatro CSVs em `data/gold/mortalidade/`; checksums,
qualidade e reconciliacoes ficam em
`data/metadata/sim_mortality_2024_processing.json`.

Na Fase 10, `SIFGBR24.dbc` preliminar e `Docs_TAB_SINAN.zip` entram em
`data/raw/sinan/original/` e no manifesto. A auditoria fica em
`data/metadata/sinan_2024_source_assessment.json`. Nenhuma camada Silver ou
Gold SINAN foi publicada por insuficiencia de classificacao final.

Na Fase 11, dimensoes IBGE e CSVs Gold aprovados sao carregados para o schema
`analytics` do PostgreSQL. `metadata.load_runs` registra caminho, nivel,
linhas e SHA-256 de cada entrada; o relatorio local fica em
`data/metadata/postgres_phase11_load.json`.

Na Fase 12, `analytics` e declarado como source dbt. Views em `dbt_staging` e
`dbt_intermediate` alimentam tabelas em `dbt_marts`; testes garantem que as
contagens e os graos permanecem reconciliados. Manifesto e catalogo dbt sao
artefatos locais reproduziveis em `dbt/target/`.

Na Fase 14, FastAPI consulta apenas `dbt_marts` e a dimensao territorial
aprovada em `analytics`. A API nao calcula regras epidemiologicas e nao expoe
os marts municipais.
