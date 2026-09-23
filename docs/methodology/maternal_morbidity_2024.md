# Morbidades maternas no SIH/SUS 2024

## Unidade e elegibilidade

A unidade do fato e um grupo de **registros de AIH**, nao de mulheres ou
internacoes individuais comprovadamente unicas. O conjunto elegivel usa AIH
tipo 1, sexo codificado como `3` (feminino no SIH), diagnostico principal
iniciado por `O` e codigo encontrado no catalogo oficial CID-10. Os registros
sao agregados por competencia de processamento, municipio de residencia e
codigo CID principal. Diagnosticos secundarios nao geram outro evento nesta
versao, para evitar dupla contagem entre grupos.

Registros tipo 5 nao entram no numerador/denominador principal: representam
continuidade de longa permanencia e sao auditados separadamente. Numeros de
AIH repetidos nao sao convertidos em pessoas; o fato contabiliza registros
tal como publicados. O municipio corresponde a residencia, nao ao local do
hospital. O codigo IBGE vem da dimensao territorial 2024.

## Classificacao

`data/reference/cid/cid_materno.csv` contem os 502 codigos O presentes no
catalogo DATASUS, descricoes originais, grupo, subgrupo, periodo obstetrico,
fonte da regra e indicador `e_morbidade`. A classificacao inclui transtornos
hipertensivos, diabetes na gestacao, infeccoes, hemorragias, complicacoes
vasculares, anestesicas, da gestacao, do parto, do puerperio, desfechos
abortivos e outras condicoes maternas. Codigos O80-O84 de via/tipo de parto,
assistencia materna/fetal e outros codigos sem complicacao definida permanecem
no fato com `e_morbidade=0`, mas nao entram nos CSVs de morbidade.

O12 (edema/proteinuria sem hipertensao) nao e rotulado como hipertensao.
O40-O43 (liquido amniotico, membranas, placenta) sao complicacoes da gestacao.
O99.0 e classificado como anemia que complica a gestacao; nao se atribui
relacao materna a codigos de outros capitulos sem o enquadramento obstetrico
oficial. Cada CID principal pertence a um unico grupo analitico nesta versao.

## Indicadores

`registros_aih` e a contagem de linhas elegiveis com CID principal do grupo.
`denominador_aih_obstetricas` e a contagem de todas as AIHs tipo 1, sexo `3`,
com CID principal O valido na mesma competencia e geografia, inclusive parto
sem morbidade. A proporcao e `100 * registros_aih / denominador_aih_obstetricas`,
arredondada a quatro casas. Esta e uma **proporcao de registros hospitalares
obstetricos do SUS**, nao prevalencia em gestantes brasileiras.

`dias_permanencia`, `valor_total` e `obitos_hospitalares` somam as medidas das
AIHs do numerador. Valor e montante administrativo aprovado, nao custo social
ou economico. Obito hospitalar associado a AIH nao e indicador de mortalidade
materna; essa definicao exige a fase SIM e regras epidemiologicas proprias.

Nao foi calculada taxa por 1.000 nascidos vivos: o numerador SIH por
competencia de processamento nao e diretamente comparavel aos nascidos vivos
SINASC, e nem toda morbidade ocorre em parto com nascimento vivo. Nao foi
calculada evolucao historica alem dos 12 meses de 2024.

## Cobertura territorial e privacidade

Os quatro CSVs Gold representam Brasil, regiao, UF e municipio, agrupados por
competencia, grupo e subgrupo. Municipio/mes sem qualquer morbidade nao tem
linha Gold; seu denominador permanece no fato e e contado em
`denominator_coverage` no relatorio. Nao ha imputacao de zero evento no CSV.

Os Gold locais sao artefatos analiticos, nao tabelas publicas de acesso aberto.
Antes de disponibilizar dados municipais a terceiros, deve-se avaliar supressao
de celulas pequenas e risco de reidentificacao. SIH cobre apenas assistencia
financiada pelo SUS; frequencia hospitalar nao equivale a causalidade ou
prevalencia populacional.
