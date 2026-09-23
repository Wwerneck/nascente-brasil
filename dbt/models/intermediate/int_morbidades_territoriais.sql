select
  nivel_territorial,
  competencia,
  codigo_territorio,
  territorio,
  grupo_morbidade,
  subgrupo,
  registros_aih,
  denominador_aih_obstetricas,
  proporcao_aih_obstetricas_pct,
  dias_permanencia,
  valor_total,
  obitos_hospitalares
from {{ ref('stg_morbidades') }}
where registros_aih >= 0 and denominador_aih_obstetricas > 0
