# Indicadores SINASC 2024 - Fase 4

Fonte: Silver nacional SINASC 2024 produzida na Fase 3. Unidade de analise:
registro de nascido vivo no arquivo disponibilizado. Os resultados descrevem
o arquivo, sem ajuste por cobertura, duplicidade ou sub-registro. Nao sao
taxas populacionais nem inferencias causais.

| Indicador | Numerador | Denominador | Resultado nacional |
|---|---|---|---:|
| Registros de nascidos vivos | Todos os registros | Nao se aplica | 2.389.325 |
| Percentual de cesareas | `tipo_parto = '2'` | `tipo_parto IN ('1', '2')` | 60,62% |
| Percentual de baixo peso | `peso_nascimento_g` entre 200 e 2499 | `peso_nascimento_g` entre 200 e 7000 | 9,47% |
| Percentual de prematuridade | `semanas_gestacao` entre 20 e 36 | `semanas_gestacao` entre 20 e 45 | 12,39% |
| Percentual com 7 ou mais consultas pre-natais | `consultas_prenatal_numero` entre 7 e 50 | `consultas_prenatal_numero` entre 0 e 50 | 79,97% |

Cada percentual e `ROUND(100 * numerador / NULLIF(denominador, 0), 2)`.
Denominadores variam por indicador e excluem nulos, codigos ignorados e valores
fora das faixas de plausibilidade acima. As faixas de 200 a 7000 g, 20 a 45
semanas e 0 a 50 consultas sao regras operacionais locais para evitar extremos
inconsistentes; nao substituem criterios clinicos nem corrigem o registro.
Sete consultas e um corte descritivo e nao mede adequacao/qualidade do pre-natal.

O Ministerio da Saude define baixo peso ao nascer como inferior a 2500 g e
prematuridade como nascimento antes de 37 semanas:

- [Baixo peso - Linha de cuidado de puericultura](https://linhasdecuidado.saude.gov.br/portal/puericultura/unidade-hospitalar/planejamento-terapeutico/)
- [Prematuridade - Boletim epidemiologico, volume 55, numero 13](https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/boletins/epidemiologicos/edicoes/2024/boletim-epidemiologico-volume-55-no-13.pdf/@@download/file)
- [Saude materna - Ministerio da Saude](https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/s/saude-da-mulher/saude-materna)

As consultas SQL versionadas estao em `sql/duckdb/`. A tabela mensal agrupa
por mes da data de nascimento; data ausente permanece como grupo nulo para
permitir reconciliacao. A tabela por sexo preserva codigos como vieram na
Silver. As duas tabelas sao contagens, sem recalcular percentuais em subgrupos.

Validacoes: contagem independente do CSV Silver, total do Parquet, soma de cada
coluna de contagem mensal, soma por sexo e os nove componentes de contagem em
amostra das primeiras 1.000 linhas calculada com `csv.DictReader`. A amostra
serve como verificacao de implementacao, nao como estimativa estatistica.
