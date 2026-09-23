# Dicionario SIH/SUS RD 2024

O CSV.GZ RAW preserva, em minusculas e na ordem original, os 113 campos do
layout RD. A Silver publica os campos abaixo; codigos e identificadores ficam
como texto para preservar zeros a esquerda.

| Campo original | Campo Silver | Tipo | Descricao |
|---|---|---|---|
| arquivo | arquivo_fonte | texto | Particao RD de origem |
| arquivo | uf_arquivo | texto | UF extraida do nome da particao |
| ANO_CMPT + MES_CMPT | competencia | texto | Competencia de processamento `AAAAMM` |
| UF_ZI | codigo_municipio_gestor | texto | Municipio gestor informado |
| ESPEC | especialidade_leito | texto | Especialidade do leito |
| N_AIH | numero_aih | texto | Numero da AIH com 13 caracteres |
| IDENT | tipo_aih | texto | Tipo 1 inicial ou tipo 5 continuidade |
| MUNIC_RES | codigo_municipio_residencia | texto | Codigo municipal SIH de residencia |
| enriquecimento IBGE | codigo_ibge_residencia | texto | Codigo IBGE de sete digitos |
| SEXO | sexo | texto | Codigo de sexo da fonte |
| UTI_MES_TO | uti_dias | inteiro | Diarias de UTI no mes |
| UTI_INT_TO | uci_dias | inteiro | Diarias de unidade intermediaria |
| DIAR_ACOM | diarias_acompanhante | inteiro | Diarias de acompanhante |
| QT_DIARIAS | quantidade_diarias | inteiro | Quantidade total de diarias |
| PROC_SOLIC | procedimento_solicitado | texto | Procedimento solicitado |
| PROC_REA | procedimento_realizado | texto | Procedimento realizado |
| VAL_SH | valor_servicos_hospitalares | decimal(14,2) | Servicos hospitalares |
| VAL_SP | valor_servicos_profissionais | decimal(14,2) | Servicos profissionais |
| VAL_TOT | valor_total | decimal(14,2) | Valor total aprovado |
| VAL_UTI | valor_uti | decimal(14,2) | Valor de UTI |
| DT_INTER | data_internacao | data | Data de internacao |
| DT_SAIDA | data_saida | data | Data de saida |
| DIAG_PRINC | diagnostico_principal | texto | CID-10 principal |
| DIAG_SECUN | diagnostico_secundario | texto | Diagnostico secundario legado |
| COBRANCA | motivo_cobranca | texto | Motivo de cobranca/saida |
| NAT_JUR | natureza_juridica | texto | Natureza juridica |
| GESTAO | gestao | texto | Esfera de gestao |
| MUNIC_MOV | codigo_municipio_estabelecimento | texto | Municipio do estabelecimento |
| enriquecimento IBGE | codigo_ibge_estabelecimento | texto | Codigo IBGE de sete digitos |
| COD_IDADE | unidade_idade | texto | Unidade usada no campo idade |
| IDADE | idade | inteiro | Idade na unidade informada |
| DIAS_PERM | dias_permanencia | inteiro | Dias de permanencia |
| MORTE | obito | inteiro | Indicador de obito |
| CAR_INT | carater_internacao | texto | Carater da internacao |
| NUM_FILHOS | numero_filhos | inteiro | Numero de filhos informado |
| INSTRU | instrucao | texto | Instrucao informada |
| CID_NOTIF | cid_notificacao | texto | CID de notificacao |
| GESTRISCO | gestacao_risco | texto | Indicador de gestacao de risco |
| SEQ_AIH5 | sequencia_aih5 | texto | Sequencia da AIH tipo 5 |
| CBOR | cbor | texto | Ocupacao codificada |
| CNES | codigo_cnes | texto | Codigo do estabelecimento |
| INFEHOSP | infeccao_hospitalar | texto | Indicador da fonte |
| CID_ASSO | cid_associado | texto | CID associado |
| CID_MORTE | cid_morte | texto | CID de morte |
| COMPLEX | complexidade | texto | Complexidade do procedimento |
| FINANC | financiamento | texto | Forma de financiamento |
| RACA_COR | raca_cor | texto | Codigo de raca/cor |
| ETNIA | etnia | texto | Codigo de etnia |
| DIAGSEC1..9 | diagnostico_secundario_1..9 | texto | Diagnosticos secundarios adicionais |
| TPDISEC1..9 | tipo_diagnostico_secundario_1..9 | texto | Tipo dos diagnosticos adicionais |

Valores vazios e sentinelas documentados sao convertidos para nulo na Silver,
sem imputacao. O contrato completo ordenado esta em
`src/nascente_brasil/ingestion/sih.py`; qualquer mudanca interrompe a ingestao.
