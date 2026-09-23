select nivel_territorial, competencia, codigo_territorio, grupo_morbidade, subgrupo
from {{ ref('mart_morbidades_territoriais') }}
group by 1,2,3,4,5
having count(*) > 1
