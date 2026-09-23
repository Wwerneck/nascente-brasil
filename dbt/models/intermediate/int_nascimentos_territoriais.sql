select *
from {{ ref('stg_nascimentos') }}
where tipo_parto_informado <= nascidos_vivos
  and gestacao_informada <= nascidos_vivos
  and peso_informado <= nascidos_vivos
  and apgar5_informado <= nascidos_vivos
  and prenatal_informado <= nascidos_vivos
  and idade_mae_informada <= nascidos_vivos
  and tipo_gravidez_informado <= nascidos_vivos
