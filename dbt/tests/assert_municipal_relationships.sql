select m.codigo_territorio
from {{ ref('mart_mortalidade_territorial') }} m
left join {{ ref('stg_dim_municipio') }} d on m.codigo_territorio = d.codigo_ibge
where m.nivel_territorial = 'municipio' and d.codigo_ibge is null
