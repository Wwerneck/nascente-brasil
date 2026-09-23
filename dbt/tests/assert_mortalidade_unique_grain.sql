select nivel_territorial, ano, codigo_territorio
from {{ ref('mart_mortalidade_territorial') }}
group by 1,2,3
having count(*) > 1
