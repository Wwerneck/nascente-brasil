# Avaliacao SINAN - sifilis em gestantes 2024

O Ministerio da Saude orienta acesso a microdados SINAN por agravo e ano.
Foram obtidos diretamente do FTP DATASUS:

- `DADOS/PRELIM/SIFGBR24.dbc`: 2.607.178 bytes, SHA-256
  `1bc199e9b20db9e80d36e730318b77479bd636ebacb6fb34a3cf88947ff0ab3d`.
- `DOCS/Docs_TAB_SINAN.zip`: 65.650.628 bytes, SHA-256
  `037e5d59597cb400c4b06c5d7a94b1d2f1daf9b59228120709816e547471a81a`.

O ZIP contem o dicionario `SIFIGEN_DIC_DADOS.pdf`, revisado em julho de 2010,
alem de ficha e nota informativa do agravo. O DBC possui 32 campos, 89.934
registros, `ID_AGRAVO=O981` e `NU_ANO=2024` em todas as linhas. A unidade de
analise e **notificacao**, nao gestante unica nem gestacao unica.

O arquivo esta no diretorio `PRELIM`. `CLASSI_FIN` esta vazio em todas as
89.934 notificacoes, logo este recorte nao sustenta indicador de casos
confirmados com classificacao final. Foram encontrados 18.747 valores de
`DTTESTE1` com codificacao nao numerica e 5 codigos de residencia sem match
na dimensao IBGE 2024. Esses valores nao foram convertidos silenciosamente.

**Decisao:** preservar, manifestar e auditar a fonte, mas nao incorporar
indicadores SINAN ao Gold nesta versao. Reavaliar quando houver fonte final e
criterios de caso documentados para o mesmo recorte. Nao fazer linkage
individual com SINASC/SIH/SIM, nem interpretar notificacoes como prevalencia.

Fontes: [orientacao oficial de acesso](https://www.gov.br/saude/pt-br/acesso-a-informacao/sic/dados-em-transparencia-ativa/svsa/agravos-de-notificacoes)
e [portal DATASUS](https://datasus.saude.gov.br/transferencia-de-arquivos/).
Metadados auditaveis: `data/metadata/sinan_2024_source_assessment.json`.
