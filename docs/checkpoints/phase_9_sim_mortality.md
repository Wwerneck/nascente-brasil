# Checkpoint - Fase 9 SIM e mortalidade

FASE: 9 - SIM 2024, mortalidade materna e infantil observadas.

Objetivo: incorporar o SIM oficial, validar definicoes epidemiologicas e
publicar indicadores somente com numerador e denominador reconciliados.

Implementado: ingestao do DBC nacional, inventario das 27 particoes UF,
validacao de header/layout/checksum, CSV.GZ integral, Silver tipado sem
identificador direto, joins SIM/SINASC/IBGE e quatro Gold territoriais.

Dados: 1.532.015 declaracoes nao fetais SIM e 2.389.325 nascidos vivos
SINASC em 2024. Numeradores: 1.326 causas basicas obstetricas CID O
elegiveis; 30.020 obitos infantis; 20.113 neonatais; 14.933 neonatais
precoces. Gold: 1 Brasil, 5 regioes, 27 UFs, 5.570 municipios.

Problemas encontrados e tratados: o arquivo DORES nacional nao possui
registros fetais, portanto nao ha indicador fetal; 2.290 obitos e 54 nascidos
vivos nao se relacionam a municipio IBGE e sao mantidos no Brasil e auditados
nas diferencas subnacionais. A razao por CID O nao equivale a RMM oficial.
Onze discordancias entre idade codificada e datas foram contabilizadas.

Validacoes: contagens DBC/CSV/Parquet, 87 campos RAW, 17 Silver, datas,
geografia, numeradores/denominadores, quatro Gold por conteudo e checksum,
reconciliacao UF/nacional, 46 testes Pytest, `pip check` e segunda execucao
idempotente. Metadados em
`data/metadata/sim_mortality_2024_processing.json`.

Limitacoes: revisoes oficiais e correcao por investigacao nao aplicadas;
produtos municipais locais exigem avaliacao de privacidade antes de
divulgacao externa. Fase 10 SINAN nao iniciada.

Status: CONCLUIDA.
