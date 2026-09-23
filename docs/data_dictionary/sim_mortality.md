# Dicionario SIM 2024 Silver e Gold

Silver: `arquivo_fonte` identifica o DBC; `tipo_obito` distingue 1 fetal e 2
nao fetal; `data_obito`, `ano_obito`, `data_nascimento` sao datas/tipo ano;
`idade_original` preserva a codificacao DATASUS; `sexo` usa 2 para feminino;
`codigo_municipio_residencia` e `codigo_municipio_ocorrencia` preservam
CODMUNRES/CODMUNOCOR; `codigo_ibge_residencia` e
`codigo_ibge_ocorrencia` sao chaves IBGE de 7 digitos, nulas sem match;
`causa_basica` e `causa_basica_original` preservam CAUSABAS/CAUSABAS_O;
`causa_materna_associada` preserva CAUSAMAT, sem interpreta-la como causa
basica; `obito_gravidez`, `obito_puerperio` e `data_investigacao` preservam
OBITOGRAV, OBITOPUERP e DTINVESTIG tipada.

Gold: `ano`, `codigo_territorio`, `territorio`, `nascidos_vivos`,
`obitos_nao_fetais`, `obitos_causa_obstetrica_cid_o`,
`obitos_maternos_tardios_sequelas`, `causas_indiretas_candidatas`,
`obitos_infantis`, `obitos_neonatais`, `obitos_neonatais_precoces`,
`obitos_pos_neonatais`, `razao_observada_causa_obstetrica_por_100mil_nv`,
`taxa_observada_mortalidade_infantil_por_mil_nv` e
`taxa_observada_mortalidade_neonatal_por_mil_nv`. Todas as contagens sao de
declaracoes, exceto `nascidos_vivos`. Taxas sao nulas quando o denominador e
zero. Consulte o metodo para inclusoes, exclusoes e limites.
