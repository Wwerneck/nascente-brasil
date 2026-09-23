# Qualidade - Morbidades maternas 2024

- SIH Silver de entrada: 14.171.364 linhas; 2.115.667 AIHs tipo 1 com CID
  principal O; 1.740 dessas com sexo diferente de `3`, auditadas e excluidas.
- Elegiveis: 2.113.927 registros. Catalogo CID sem match: zero; municipio IBGE
  ausente: zero; AIH tipo 5 com CID O: zero; repeticao de chave de AIH no
  recorte elegivel: zero.
- Com codigo classificado como morbidade: 873.345. Com codigo obstetrico de
  parto/assistencia ou outro sem morbidade definida: 1.240.582.
- Fato: 573.131 linhas agregadas; 12 competencias; 5.570 municipios.
- Gold: 240 linhas Brasil, 1.177 regiao, 5.895 UF, 218.479 municipio.
  Em cada nivel, a soma de `registros_aih` e 873.345.
- Denominador territorial: Brasil, regiao e UF cobrem os 2.113.927 registros.
  No Gold municipal, 2.090.092 estao em municipio/mes com morbidade; 23.835
  pertencem a municipio/mes sem linha de morbidade. O fato preserva todos.

Numeradores e denominadores sao reconciliados independentemente com o fato e
o SIH Silver. Tamanho, contagem e SHA-256 de cada produto estao em
`data/metadata/maternal_morbidity_2024_processing.json`. As regras de grupo
sao analiticas, versionadas e testadas; nao representam diagnosticos novos.
