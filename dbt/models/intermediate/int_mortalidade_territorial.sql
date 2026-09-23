select
  *,
  case when nascidos_vivos > 0
    then round(1000.0 * obitos_pos_neonatais / nascidos_vivos, 4)
  end as taxa_observada_mortalidade_pos_neonatal_por_mil_nv
from {{ ref('stg_mortalidade') }}
where obitos_neonatais <= obitos_infantis
  and obitos_neonatais_precoces <= obitos_neonatais
