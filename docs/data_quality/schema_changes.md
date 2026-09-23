# Alteracoes de Schema

## Baseline SINASC 2024

O ZIP nacional possui um CSV com 62 colunas separadas por `;`. O contrato
ordenado esta em `src/nascente_brasil/conversion/sinasc.py` e o dicionario
completo em `docs/data_dictionary/sinasc.md`.

Fingerprint do cabecalho RAW:
`header-sha256:447a1c5696ee08fd534acfee47abd4bd35a5075967ca206795c50c1f1ceded5a`.

Na Fase 3 nao foi observado desvio em relacao ao arquivo 2024 validado.
A conversao interrompe a execucao se houver coluna nova, removida ou mudanca
na ordem. Nesse caso, a pipeline grava um diagnostico em
`data/metadata/sinasc_2024_<checksum>_schema_drift.json` e exige revisao do
dicionario e das regras antes de continuar. Mudancas de dominio e de tipo
sao contadas no relatorio de qualidade; codigos desconhecidos nao sao
recodificados silenciosamente.

## SIH/SUS RD 2024

As 324 particoes estaduais mensais apresentam o mesmo contrato ordenado de
113 campos e comprimento de registro de 702 bytes. A assinatura dos descritores
DBF e verificada em cada DBC antes da descompressao. Coluna nova, removida,
reordenada ou com descritor alterado interrompe a Fase 7; nao ha uniao
silenciosa de schemas. O CSV.GZ preserva todos os campos, enquanto o schema
Silver tipado e versionado por `phase7-v1`.

## CID-10 DATASUS e Fase 8

`CID10.DBF` possui 14.257 registros e campos `CID10`, `OPC`, `CAT`,
`SUBCAT`, `DESCR`, `RESTRSEXO`. `CIDCAP10.DBF` possui 22 registros e campos
`DESCRICAO`, `CAUSAS`; o capitulo XV declara `O00-O99`. A Fase 8 valida esses
contratos antes de construir os 502 codigos obstetricos da referencia local.

## SIM DORES 2024

`DOBR2024.dbc` possui 87 campos e registro DBF de 490 bytes. A Fase 9 valida
campos obrigatorios, assinatura dos descritores, quantidade de registros e
checksum antes da conversao. O CSV.GZ preserva todos os campos; o Silver
tipado contem 17 campos analiticos. Qualquer alteracao no arquivo registrada
no manifesto invalida a execucao, sem adaptacao silenciosa.
