select nivel_territorial, ano, codigo_territorio
from {{ ref('mart_nascimentos_territoriais') }}
group by 1,2,3
having count(*) > 1
