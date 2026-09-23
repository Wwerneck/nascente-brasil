select
  codigo_ibge,
  codigo_sinasc_6,
  municipio,
  codigo_uf,
  uf,
  nome_uf,
  codigo_regiao,
  regiao
from {{ source('analytics', 'dim_municipio') }}
