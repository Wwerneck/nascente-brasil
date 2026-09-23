# Qualidade SINASC 2024 - Fase 3

Fonte: ZIP nacional SINASC 2024, SHA-256
`27e55de6359e1b1914301dc1d752d78e9535a7a52cc0640931dd94876aca6027`.
Execucao: `phase3-v3`. Metricas detalhadas e checksums dos produtos em
`data/metadata/sinasc_2024_27e55de6359e_processing.json`.

## Reconciliacao

| Etapa | Registros |
|---|---:|
| CSV interno do ZIP | 2.389.325 |
| CSV RAW padronizado | 2.389.325 |
| Silver CSV | 2.389.325 |
| Silver Parquet | 2.389.325 |

Nao houve descarte de registros. Os codigos territoriais foram mantidos
como texto; nenhum deles apresentou comprimento fora de 6 ou 7 digitos.
Datas de nascimento invalidas ou fora de 2024: 0.

## Completude e sentinelas

| Campo Silver | Nulos finais | Sentinelas convertidas em nulo |
|---|---:|---:|
| `idade_mae` | 32 | 11 |
| `semanas_gestacao` | 17.830 | 0 |
| `consultas_prenatal_numero` | 37.265 | 6.749 |
| `peso_nascimento_g` | 221 | 0 |
| `apgar_1min` | 25.667 | 1.962 |
| `apgar_5min` | 25.082 | 1.459 |
| `data_nascimento` | 0 | nao se aplica |
| `tipo_parto` | 1.132 | preservado |
| `tipo_gravidez` | 1.244 | preservado |
| `sexo` | 0 | preservado |

Nao foram encontrados valores nao numericos nos seis campos convertidos
para inteiros. Nos campos categoricos auditados, nao houve codigo fora dos
dominios configurados. Codigos de categoria ignorada foram preservados:
41 em `tipo_parto` (9), 366 em `sexo` (0) e 61 em `tipo_gravidez` (9).

## Valores fora da faixa de referencia

| Campo | Registros |
|---|---:|
| `idade_mae` fora de 10 a 65 | 3 |
| `semanas_gestacao` fora de 20 a 45 | 292 |
| `consultas_prenatal_numero` fora de 0 a 50 | 23 |
| `peso_nascimento_g` fora de 200 a 7000 | 132 |

Esses valores foram **mantidos** para investigacao posterior. As faixas sao
regras de plausibilidade desta pipeline, nao criterios clinicos de exclusao.
Valores sentinela 99 e 9999 nos campos especificados foram convertidos para
nulo e contabilizados; o valor original continua acessivel no RAW CSV e ZIP.

O CSV RAW preserva valores textuais e zeros a esquerda; a Silver tipa seis
campos numericos e a data de nascimento. Os demais campos continuam texto
ate a revisao de seus dominios. Esta etapa nao mede cobertura populacional
ou deduplicacao de declaracoes; o total e de registros administrativos.
