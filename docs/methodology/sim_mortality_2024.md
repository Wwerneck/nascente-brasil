# SIM 2024 - mortalidade observada

Fonte: `DOBR2024.dbc`, diretorio oficial DATASUS
`/dissemin/publicos/SIM/CID10/DORES/`. O arquivo nacional tem 1.532.015
declaracoes, todas `TIPOBITO=2` (nao fetal). **O valor zero para fetal no
arquivo nao e uma estimativa de obitos fetais no Brasil**; nenhum indicador
fetal e publicado nesta fase. O CSV RAW preserva os 87 campos da fonte, e o
Parquet Silver mantem apenas 17 campos analiticos, sem identificador direto.

Unidade: declaracao de obito, nao pessoa longitudinal. Numeradores usam ano
de `DTOBITO=2024` e municipio de residencia `CODMUNRES`. Denominador: todos os
2.389.325 nascidos vivos de 2024 no SINASC Silver, por residencia da mae.
Regiao/UF/municipio usam a DTB 2024 do IBGE. O Brasil inclui registros sem
municipio relacionado; os niveis subnacionais nao. Nao se deve somar taxas.

Indicadores Gold:

- `obitos_causa_obstetrica_cid_o`: declaracoes nao fetais do sexo feminino
  (`SEXO=2`) com causa basica CID `O00-O99`, exceto `O96/O97`. A razao
  observada e `100.000 * numerador / nascidos_vivos`. **Nao e a RMM oficial**:
  causas maternas de outros capitulos, investigacao, fatores de correcao e
  criterios de elegibilidade requerem tratamento adicional. `O96/O97` sao
  auditados separadamente; causas indiretas candidatas tambem, sem soma ao
  numerador. `CAUSAMAT` e causa externa associada e nao define o numerador.
- `obitos_infantis`: idade ao obito menor que um ano. `IDADE` codificada em
  minutos, horas, dias ou meses tem prioridade. Datas validas sao recurso
  subsidiario quando nao ha unidade etaria util. `obitos_neonatais` cobre
  0-27 dias, `obitos_neonatais_precoces` 0-6, e `obitos_pos_neonatais` e
  infantil menos neonatal. Taxas infantil e neonatal dividem por nascidos
  vivos do mesmo ano e residencia, multiplicadas por 1.000. Sao taxas
  observadas, nao estimativas oficiais corrigidas.
- Denominador zero gera taxa nula, nao zero. Contagens zero significam zero
  registros no recorte disponivel, nao prova de ausencia de eventos.

As 11 discordancias entre idade codificada infantil e datas sugerindo mais de
um ano ficam no relatorio de auditoria; a classificacao usa `IDADE`. Os CSVs
municipais sao produtos locais; antes de divulgacao publica, celulas pequenas
precisam de avaliacao de risco e politica de supressao.

Referencias oficiais: [sistema SIM](https://www.gov.br/saude/pt-br/composicao/svsa/sistemas-de-informacao/sim),
[dicionario SIM](https://svs.aids.gov.br/daent/cgiae/coesv/sistemas-informacao/sim/documentacao/dicionario-de-dados-SIM-tabela-DO.pdf),
[Indicadores Basicos para a Saude](https://bvsms.saude.gov.br/bvs/publicacoes/indicadores_bas_saude_brasil.pdf).
