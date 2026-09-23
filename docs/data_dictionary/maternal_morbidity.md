# Dicionario - Morbidades maternas 2024

## Referencia CID

`data/reference/cid/cid_materno.csv` possui 502 linhas e oito campos:

| Campo | Tipo | Descricao |
|---|---|---|
| cid_codigo | texto | Codigo CID-10 sem ponto, de tres ou quatro caracteres |
| cid_categoria | texto | Categoria de tres caracteres |
| cid_descricao | texto | Descricao do catalogo DATASUS |
| grupo_morbidade | texto | Grupo analitico exclusivo |
| subgrupo | texto | Subgrupo analitico exclusivo |
| periodo_obstetrico | texto | Gestacao, parto, puerperio ou periodo misto |
| fonte_classificacao | texto | Fonte e versao da regra |
| e_morbidade | inteiro 0/1 | Inclusao no numerador de morbidade |

## Fato

`fact_morbidades_maternas_2024.parquet` tem granularidade
`competencia + codigo_ibge + cid_codigo` e preserva `cid_categoria`,
`cid_descricao`, `grupo_morbidade`, `subgrupo`, `periodo_obstetrico` e
`e_morbidade`. Medidas: `registros_aih` (inteiro), `dias_permanencia`
(inteiro), `valor_total` (decimal) e `obitos_hospitalares` (inteiro).

## Gold

Os quatro CSVs compartilham `competencia`, `codigo_territorio`, `territorio`,
`grupo_morbidade`, `subgrupo`, `registros_aih`,
`denominador_aih_obstetricas`, `proporcao_aih_obstetricas_pct`,
`dias_permanencia`, `valor_total` e `obitos_hospitalares`.
`codigo_territorio` e `BR`, codigo de regiao, sigla UF ou codigo IBGE municipal
conforme o arquivo. Somente grupos com `e_morbidade=1` aparecem nos Gold.
