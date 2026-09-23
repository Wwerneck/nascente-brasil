# Qualidade do cruzamento IBGE x SINASC 2024

Unidade de analise: registro SINASC. O cruzamento foi feito separadamente para
municipio de residencia materna e municipio de ocorrencia do nascimento. Cada
registro contribui uma vez para cada perspectiva. Os codigos SINASC observados
tem seis digitos; a chave `codigo_sinasc_6` e formada pelos seis primeiros
digitos do codigo oficial de sete da DTB. A unicidade dessa chave foi verificada
nos 5.571 geocodigos antes de qualquer join. Nomes textuais nao sao chaves.

| Perspectiva | Entrada | Relacionados | Nao relacionados | Taxa de relacionamento | Geocodigos DTB sem evento |
|---|---:|---:|---:|---:|---:|
| Residencia | 2.389.325 | 2.389.271 | 54 | 99,9977% | 1 |
| Ocorrencia | 2.389.325 | 2.389.323 | 2 | 99,9999% | 1.744 |

Formula: `taxa = 100 * matched_rows / left_rows`. Em ambos os casos,
`matched_rows + unmatched_left = left_rows`; `duplicated_keys = 0`.
`unmatched_right` significa geocodigo sem evento daquela perspectiva, nao
perda de registros no join. O unico geocodigo sem residencia registrada e
5101837, Boa Esperanca do Norte (MT), instalada em 2025 conforme [IBGE](https://educa.ibge.gov.br/criancas/voce-sabia/22741-novo-municipio.html).

Os 54 registros de residencia usam 13 codigos distintos nao encontrados na
DTB: `330000` (22), `130000` (9), `520000` (5), `350000` (4), `260000`
(3), `320000` (3), `290000` (2) e seis codigos com um registro cada
(`140000`, `220000`, `270000`, `310000`, `410000`, `420000`). Os dois
registros de ocorrencia usam `260000` e `420000` (um cada). Todos possuem
seis digitos, terminam em `0000` e iniciam com prefixo de UF existente.
Isso sugere codificacao sem municipio especifico, mas a causa exata nao foi
confirmada pela documentacao da fonte. Portanto, continuam classificados como
`municipality_not_in_dtb`, sem municipio ou regiao atribuidos artificialmente.
Os campos `codigo_uf_prefixo` e `uf_prefixo` permitem examinar a UF que o
prefixo indica, sem transformar o registro em match municipal.

Cada codigo e sua contagem estao em `data/processed/sinasc/analytics/sinasc_2024_territory_join.csv`.
O arquivo preserva tanto matches quanto falhas e pode ser agregado por regiao,
UF ou municipio apenas quando `match_status = 'matched'`. Registros nao
relacionados devem ser mostrados separadamente em qualquer total territorial.
