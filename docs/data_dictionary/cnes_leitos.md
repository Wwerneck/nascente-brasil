# Dicionario CNES Hospitais e Leitos 2024

| Campo original | Campo padronizado | Tipo Silver | Descricao |
|---|---|---|---|
| COMP | competencia | texto | Competencia mensal `AAAAMM` |
| REGIAO | regiao_fonte | texto | Grande regiao informada na fonte |
| UF | uf | texto | Sigla da UF |
| MUNICIPIO | municipio_fonte | texto | Nome municipal informado no CNES |
| MOTIVO_DESABILITACAO | motivo_desabilitacao | texto anulavel | Motivo de desabilitacao |
| CNES | codigo_cnes | texto | Codigo CNES com sete digitos |
| NOME_ESTABELECIMENTO | nome_estabelecimento | texto | Nome fantasia |
| RAZAO_SOCIAL | razao_social | texto | Razao social |
| TP_GESTAO | tipo_gestao | texto | M municipal, E estadual, D dupla ou S sem gestao |
| CO_TIPO_UNIDADE | codigo_tipo_unidade | texto | Codigo do tipo de unidade |
| DS_TIPO_UNIDADE | tipo_unidade | texto | Descricao do tipo de unidade |
| NATUREZA_JURIDICA | codigo_natureza_juridica | texto | Codigo da natureza juridica |
| DESC_NATUREZA_JURIDICA | natureza_juridica | texto | Descricao da natureza juridica |
| NO_LOGRADOURO | logradouro | texto | Logradouro do estabelecimento |
| NU_ENDERECO | numero_endereco | texto | Numero/endereco complementar da fonte |
| NO_COMPLEMENTO | complemento | texto anulavel | Complemento do endereco |
| NO_BAIRRO | bairro | texto | Bairro |
| CO_CEP | cep | texto | CEP preservando zeros |
| NU_TELEFONE | telefone | texto anulavel | Contato institucional |
| NO_EMAIL | email | texto anulavel | E-mail institucional |
| LEITOS_EXISTENTES | leitos_existentes | inteiro | Total de leitos existentes |
| LEITOS_SUS | leitos_sus | inteiro | Total de leitos SUS |
| UTI_TOTAL_EXIST | uti_total_existentes | inteiro | Total de UTI existentes |
| UTI_TOTAL_SUS | uti_total_sus | inteiro | Total de UTI SUS |
| UTI_ADULTO_EXIST | uti_adulto_existentes | inteiro | UTI adulta existente, niveis I a III |
| UTI_ADULTO_SUS | uti_adulto_sus | inteiro | UTI adulta SUS, niveis I a III |
| UTI_PEDIATRICO_EXIST | uti_pediatrica_existentes | inteiro | UTI pediatrica existente, niveis I a III |
| UTI_PEDIATRICO_SUS | uti_pediatrica_sus | inteiro | UTI pediatrica SUS, niveis I a III |
| UTI_NEONATAL_EXIST | uti_neonatal_existentes | inteiro | UTI neonatal existente, niveis I a III |
| UTI_NEONATAL_SUS | uti_neonatal_sus | inteiro | UTI neonatal SUS, niveis I a III |
| UTI_QUEIMADO_EXIST | uti_queimados_existentes | inteiro | UTI de queimados existente |
| UTI_QUEIMADO_SUS | uti_queimados_sus | inteiro | UTI de queimados SUS |
| UTI_CORONARIANA_EXIST | uti_coronariana_existentes | inteiro | UTI coronariana existente, niveis II e III |
| UTI_CORONARIANA_SUS | uti_coronariana_sus | inteiro | UTI coronariana SUS, niveis II e III |

Campos territoriais enriquecidos na Silver: `codigo_ibge`, `municipio`,
`codigo_uf`, `nome_uf`, `codigo_regiao`, `regiao`,
`territory_match_status` e `territory_match_method`. Identificadores, CEP e
codigos categoricos permanecem texto. Vazios nao sao convertidos em zero.
