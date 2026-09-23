# Dicionario SINASC 2024

Contrato observado no CSV nacional `SINASC_2024.csv` (62 colunas). A fonte e um
CSV `;` com todos os valores inicialmente textuais. As descricoes foram
conferidas com o [dicionario da tabela DN do Ministerio da Saude](https://svs.aids.gov.br/daent/cgiae/coesv/sistemas-informacao/sinasc/documentacao/)
e com o cabecalho real de 2024. O dicionario oficial consultado e antigo;
para campos de uso tecnico sem dominio confirmado, o codigo e mantido como
texto e nenhuma interpretacao analitica e presumida.

`RAW CSV` preserva cada valor textual e altera apenas a codificacao para
UTF-8, o separador para virgula e os nomes para minusculas/snake_case.
`Silver CSV` representa datas como `AAAA-MM-DD`, inteiros em decimal e nulos
como vazio. `Silver Parquet` registra os tipos fisicos. Os demais campos
permanecem texto, inclusive os codigos com zeros a esquerda.

| Campo original | Campo padronizado | Tipo original | Tipo final | Descricao | Valores validos / dominio | Tratamento Silver |
|---|---|---|---|---|---|---|
| contador | contador | texto | texto | Contador da linha na publicacao | Identificador textual; sem uso como chave | Preservado |
| ORIGEM | origem | texto | texto | Identificacao tecnica da origem do registro | Dominio nao confirmado | Preservado |
| CODESTAB | codigo_estabelecimento | texto | texto | Codigo do estabelecimento de nascimento | Codigo CNES quando preenchido | Preservado |
| CODMUNNASC | codigo_municipio_nascimento | texto | texto | Municipio de ocorrencia do nascimento | 6 ou 7 digitos observaveis | Espaços externos retirados; formato auditado |
| LOCNASC | local_nascimento | texto | texto | Local de ocorrencia | 1 hospital; 2 outro servico; 3 domicilio; 4 outro | Preservado |
| IDADEMAE | idade_mae | texto | int64 anulavel | Idade materna em anos | 10 a 65 como faixa plausivel; 99 ignorado | 99 vira nulo; extremos mantidos e contados |
| ESTCIVMAE | estcivmae | texto | texto | Estado civil materno | Codigo da fonte; dominio a confirmar | Preservado |
| ESCMAE | escmae | texto | texto | Escolaridade materna na classificacao anterior | Codigo da fonte; dominio a confirmar | Preservado |
| CODOCUPMAE | codocupmae | texto | texto | Codigo da ocupacao materna | Codigo CBO quando preenchido | Preservado |
| QTDFILVIVO | qtdfilvivo | texto | texto | Filhos nascidos vivos anteriores | Numero textual; sentinelas a confirmar | Preservado |
| QTDFILMORT | qtdfilmort | texto | texto | Filhos nascidos mortos anteriores | Numero textual; sentinelas a confirmar | Preservado |
| CODMUNRES | codigo_municipio_residencia | texto | texto | Municipio de residencia materna | 6 ou 7 digitos observaveis | Espacos externos retirados; formato auditado |
| GESTACAO | gestacao_categoria | texto | texto | Faixa de duracao da gestacao | Codigo da fonte; dominio a confirmar | Preservado |
| GRAVIDEZ | tipo_gravidez | texto | texto | Tipo de gestacao | 1 unica; 2 dupla; 3 tripla ou mais; 9 ignorado | Espacos externos retirados; inesperados contados |
| PARTO | tipo_parto | texto | texto | Tipo de parto | 1 vaginal; 2 cesareo; 9 ignorado | Espacos externos retirados; inesperados contados |
| CONSULTAS | consultas_prenatal_categoria | texto | texto | Faixa de consultas pre-natais | 1 nenhuma; 2 de 1 a 3; 3 de 4 a 6; 4 sete ou mais; 9 ignorado | Preservado |
| DTNASC | data_nascimento | texto ddmmaaaa | data/timestamp | Data do nascimento | Data calendario valida | Parse estrito; invalida vira nulo e e contada |
| HORANASC | horanasc | texto | texto | Hora do nascimento | HHMM quando preenchido | Preservado |
| SEXO | sexo | texto | texto | Sexo do nascido vivo | 0 ignorado; 1 masculino; 2 feminino | Espacos externos retirados; ignorado contado |
| APGAR1 | apgar_1min | texto | int64 anulavel | Apgar no primeiro minuto | 0 a 10; 99 ignorado | 99 vira nulo; extremos mantidos e contados |
| APGAR5 | apgar_5min | texto | int64 anulavel | Apgar no quinto minuto | 0 a 10; 99 ignorado | 99 vira nulo; extremos mantidos e contados |
| RACACOR | racacor | texto | texto | Raca/cor do recem-nascido | Codigo da fonte; dominio a confirmar | Preservado |
| PESO | peso_nascimento_g | texto | int64 anulavel | Peso ao nascer em gramas | 200 a 7000 como faixa plausivel; 9999 ignorado | 9999 vira nulo; extremos mantidos e contados |
| IDANOMAL | idanomal | texto | texto | Indicador de anomalia congenita | Codigo da fonte; dominio a confirmar | Preservado |
| DTCADASTRO | dtcadastro | texto | texto | Data de cadastro no sistema | Data textual; formato nao tipado nesta fase | Preservado |
| CODANOMAL | codanomal | texto | texto | Codigo de anomalia congenita | Codigo da fonte; dominio a confirmar | Preservado |
| NUMEROLOTE | numerolote | texto | texto | Numero do lote de processamento | Identificador textual | Preservado |
| VERSAOSIST | versaosist | texto | texto | Versao do sistema de origem | Identificador textual | Preservado |
| DTRECEBIM | dtrecebim | texto | texto | Data do recebimento do lote | Data textual; formato nao tipado nesta fase | Preservado |
| DIFDATA | difdata | texto | texto | Diferenca tecnica de datas | Dominio nao confirmado para 2024 | Preservado |
| OPORT_DN | oport_dn | texto | texto | Campo tecnico de oportunidade da DN | Dominio nao confirmado | Preservado |
| DTRECORIGA | dtrecoriga | texto | texto | Data de recebimento original | Data textual; formato nao tipado nesta fase | Preservado |
| NATURALMAE | naturalmae | texto | texto | Naturalidade materna | Codigo da fonte | Preservado |
| CODMUNNATU | codmunnatu | texto | texto | Municipio de naturalidade materna | Codigo territorial da fonte | Preservado |
| CODUFNATU | codufnatu | texto | texto | UF de naturalidade materna | Codigo da fonte | Preservado |
| ESCMAE2010 | escolaridade_mae_2010 | texto | texto | Escolaridade materna na classificacao 2010 | 0 sem; 1 Fundamental I; 2 Fundamental II; 3 Medio; 4 Superior incompleto; 5 Superior completo; 9 ignorado | Preservado |
| SERIESCMAE | seriescmae | texto | texto | Serie escolar concluida pela mae | 1 a 8 quando aplicavel | Preservado |
| DTNASCMAE | dtnascmae | texto | texto | Data de nascimento materna | Data textual ddmmaaaa | Preservado |
| RACACORMAE | raca_cor_mae | texto | texto | Raca/cor materna | 1 branca; 2 preta; 3 amarela; 4 parda; 5 indigena | Preservado |
| QTDGESTANT | qtdgestant | texto | texto | Gestacoes anteriores | Numero textual; sentinelas a confirmar | Preservado |
| QTDPARTNOR | qtdpartnor | texto | texto | Partos vaginais anteriores | Numero textual; sentinelas a confirmar | Preservado |
| QTDPARTCES | qtdpartces | texto | texto | Cesareas anteriores | Numero textual; sentinelas a confirmar | Preservado |
| IDADEPAI | idadepai | texto | texto | Idade paterna | Numero textual; sentinelas a confirmar | Preservado |
| DTULTMENST | dtultmenst | texto | texto | Data da ultima menstruacao | Data textual ddmmaaaa | Preservado |
| SEMAGESTAC | semanas_gestacao | texto | int64 anulavel | Semanas completas de gestacao | 20 a 45 como faixa plausivel; 99 ignorado | 99 vira nulo; extremos mantidos e contados |
| TPMETESTIM | tpmetestim | texto | texto | Metodo de estimacao gestacional | 1 exame fisico; 2 outro; 9 ignorado | Preservado |
| CONSPRENAT | consultas_prenatal_numero | texto | int64 anulavel | Numero de consultas pre-natais | 0 a 50 como faixa plausivel; 99 ignorado | 99 vira nulo; extremos mantidos e contados |
| MESPRENAT | mesprenat | texto | texto | Mes gestacional de inicio do pre-natal | Codigo da fonte; dominio a confirmar | Preservado |
| TPAPRESENT | tpapresent | texto | texto | Apresentacao fetal | 1 cefalica; 2 pelvica; 3 transversa; 9 ignorado | Preservado |
| STTRABPART | sttrabpart | texto | texto | Trabalho de parto induzido | 1 sim; 2 nao; 3 nao aplicavel; 9 ignorado | Preservado |
| STCESPARTO | stcesparto | texto | texto | Cesarea antes do trabalho de parto | 1 sim; 2 nao; 3 nao aplicavel; 9 ignorado | Preservado |
| TPNASCASSI | tpnascassi | texto | texto | Profissional que assistiu ao nascimento | Codigo da fonte; dominio a confirmar | Preservado |
| TPFUNCRESP | tpfuncresp | texto | texto | Funcao do responsavel pela DN | Dominio nao confirmado | Preservado |
| TPDOCRESP | tpdocresp | texto | texto | Documento do responsavel pela DN | Dominio nao confirmado | Preservado |
| DTDECLARAC | dtdeclarac | texto | texto | Data da declaracao | Data textual; formato nao tipado nesta fase | Preservado |
| ESCMAEAGR1 | escmaeagr1 | texto | texto | Escolaridade materna agrupada | Dominio nao confirmado para 2024 | Preservado |
| STDNEPIDEM | stdnepidem | texto | texto | Status tecnico da DN em epidemiologia | Dominio nao confirmado | Preservado |
| STDNNOVA | stdnnova | texto | texto | Status tecnico da nova DN | Dominio nao confirmado | Preservado |
| CODPAISRES | codpaisres | texto | texto | Pais de residencia materna | Codigo da fonte | Preservado |
| TPROBSON | tprobson | texto | texto | Grupo de Robson registrado | Codigo da fonte; derivacao nao revista | Preservado |
| PARIDADE | paridade | texto | texto | Paridade registrada | Codigo da fonte; derivacao nao revista | Preservado |
| KOTELCHUCK | kotelchuck | texto | texto | Indice Kotelchuck registrado | Codigo da fonte; derivacao nao revista | Preservado |

Os codigos de municipio no arquivo observado tem seis digitos. A validacao
admite seis ou sete digitos e preserva o valor recebido. Na Fase 5, o
relacionamento com a DTB 2024 do IBGE utiliza uma chave auxiliar formada pelos
seis primeiros digitos do codigo oficial de sete, cuja unicidade foi validada.
O codigo original permanece intacto e os nao relacionados sao auditados em
`docs/data_quality/ibge_sinasc_2024.md`. Nenhum identificador pessoal foi criado.
