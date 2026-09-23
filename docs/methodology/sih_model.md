# Modelo SIH/SUS 2024

## Granularidade

Uma linha do RD representa uma AIH reduzida aprovada na competencia de
processamento indicada no arquivo. A chave operacional preservada e
`arquivo_fonte + numero_aih`; ela e auditada por particao. A competencia de
processamento nao deve ser confundida com a data de internacao ou de saida.

O numero da AIH possui 13 caracteres e permanece texto. Uma AIH nao e uma
pessoa: um individuo pode ter mais de uma autorizacao, e a base nao fornece
um identificador analitico seguro de paciente para deduplicacao nominal.

## Tipos de AIH

`tipo_aih = 1` identifica a AIH inicial. `tipo_aih = 5` identifica continuidade
de internacao de longa permanencia, com renovacao mensal. `sequencia_aih5`
preserva a sequencia informada pela fonte. Contar linhas ou numeros de AIH
como pacientes produziria uma medida metodologicamente incorreta.

## Diagnosticos

`diagnostico_principal` e o CID-10 que motivou a internacao segundo o registro.
`diagnostico_secundario`, `diagnostico_secundario_1` a `_9` e seus tipos
preservam diagnosticos adicionais. A pipeline valida apenas a forma basica do
codigo CID-10; ela nao infere significado clinico, nao corrige codigos e nao
substitui vazios por ausencia de doenca.

## Temporalidade e CNES

As datas de internacao e saida sao tipadas separadamente da competencia. O
join com CNES usa `codigo_cnes + competencia` e classifica cada linha como
presente no mesmo mes, vista apenas em outro mes, ausente no recurso de
hospitais/leitos, ou com chave insuficiente. Ausencia nesse recurso nao prova
inexistencia no cadastro CNES completo.

## Privacidade e escopo

O CSV.GZ local preserva integralmente os campos da fonte para rastreabilidade.
A Silver omite nascimento exato, CEP do paciente, CPF e CNPJ operacionais,
mantendo somente campos necessarios ao modelo desta fase. Os artefatos de
dados nao sao versionados.

A Fase 7 encerra ingestao, compreensao, processamento e validacao do SIH/SUS.
Nenhuma analise obstetrica foi iniciada: selecao de codigos, denominadores e
regras clinicas pertencem a uma fase analitica posterior.
