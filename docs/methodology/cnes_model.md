# Modelo CNES 2024

## Granularidade

Uma linha de `fact_capacidade_hospitalar_2024` representa o snapshot de um
estabelecimento com leitos em uma competencia mensal. A chave e
`competencia + codigo_cnes`. Uma linha nao representa paciente, internacao ou
leito individual. Medidas de competências diferentes nao devem ser somadas
como capacidade anual; para estoque, selecione uma competencia ou calcule uma
estatistica temporal explicitamente identificada.

`dim_estabelecimento_2024` tem uma linha por codigo CNES e usa os atributos da
ultima competencia em que o estabelecimento aparece. Os campos
`competencia_inicio`, `competencia_fim`, `competencias_observadas` e
`versoes_atributos` tornam a cobertura temporal explicita. O historico mensal
completo, inclusive mudancas de atributos, permanece na Silver.

## Geografia

O arquivo CNES nao possui codigo IBGE municipal. O relacionamento usa
`UF + nome municipal normalizado` contra a DTB 2024. A normalizacao remove
acentos, pontuacao e diferencas de caixa. Dezessete nomes historicos ou grafias
divergentes usam aliases explicitos versionados no codigo; o arquivo de
auditoria preserva o nome original, o nome IBGE, o codigo e o metodo do match.
Nao ha fuzzy matching automatico.

## SINASC

O relacionamento temporal usa `codigo_estabelecimento` e o mes de
`data_nascimento`. Os status sao:

- `matched_same_competence`: codigo presente no conjunto de hospitais/leitos no mesmo mes;
- `cnes_seen_other_competence`: codigo existe em outra competencia de 2024;
- `not_in_hospital_beds_2024`: codigo nao aparece neste conjunto especifico;
- `missing_cnes_code`, `invalid_cnes_format` ou `missing_birth_date`: chave insuficiente.

Ausencia neste conjunto nao prova inexistencia do estabelecimento no cadastro
CNES completo, pois a fonte e restrita a hospitais e leitos.

## Escopo das medidas

O dicionario oficial permite calcular leitos totais, SUS e UTI neonatal. Nao
ha campo de leitos obstetricos neste recurso. A Fase 6 nao deriva leitos
obstetricos a partir do nome ou tipo da unidade; esse indicador permanece
indisponivel ate uma fonte CNES com classificacao de leito adequada ser
incorporada.
